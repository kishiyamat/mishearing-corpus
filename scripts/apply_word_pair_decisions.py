"""Apply source-bound, reviewed word-span decisions without changing corpus targets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from corpus_api.pair_workflow import (
    PairSpan,
    RecordReview,
    load_reviews,
    original_hash,
    review_csv,
    review_record,
)


def _canonical_json(value: object) -> str:
    """Serialize JSON consistently with the canonical review CSV format."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class AppliedDecisions:
    """Hold validated review CSV bytes and actual before/after lineage rows."""

    review_csv: bytes
    audit_rows: list[dict[str, str]]


def _audit_csv(rows: list[dict[str, str]]) -> bytes:
    """Serialize the actual before/after lineage ledger deterministically."""
    stream = io.StringIO(newline="")
    fields = list(rows[0]) if rows else []
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def rebuild_current_pair_rows(
    review_payload: bytes,
    originals: dict[str, tuple[dict[str, str], str]],
) -> list[dict[str, str]]:
    """Rebuild pair rows from the exact current canonical review payload."""
    rows: list[dict[str, str]] = []
    for decision in load_reviews(review_payload):
        mishear_id = str(decision["MishearID"])
        if mishear_id not in originals:
            raise ValueError("canonical review references an unknown source original")
        original, source_file = originals[mishear_id]
        rebuilt, _ = review_record(original, source_file, decision)
        rows.extend(rebuilt)
    return rows


def _signature(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    """Return the source ranges and calibrated type identifying a selected span."""
    return (
        int(row["src_start"] if "src_start" in row else row["SrcStart"]),
        int(row["src_end"] if "src_end" in row else row["SrcEnd"]),
        int(row["tgt_start"] if "tgt_start" in row else row["TgtStart"]),
        int(row["tgt_end"] if "tgt_end" in row else row["TgtEnd"]),
        str(row["unit_type"] if "unit_type" in row else row["UnitType"]),
    )


def _pair_signature(row: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return span coordinates while ignoring a reviewed UnitType-only correction."""
    start_src, end_src, start_tgt, end_tgt, _ = _signature(row)
    return start_src, end_src, start_tgt, end_tgt


def _reviewed_pair_index(
    pair_rows: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Index selected current-run rows by immutable PairID, rejecting duplicates."""
    index: dict[str, dict[str, str]] = {}
    for row in pair_rows:
        if row["TargetDecision"] != "include":
            continue
        pair_id = row["PairID"]
        if not pair_id or pair_id in index:
            raise ValueError("current run has empty or duplicate included PairID")
        index[pair_id] = row
    return index


def _match_old_pairs(
    decision: dict[str, Any],
    old_pairs: object,
    pair_index: dict[str, dict[str, str]],
    original: dict[str, str],
) -> list[dict[str, str]]:
    """Validate every old span against both review CSV and selected run rows."""
    if not isinstance(old_pairs, list) or not old_pairs:
        raise ValueError("old_pairs must list the record's complete selected pair set")
    current_spans = decision["PairSpans"]
    if not isinstance(current_spans, list):
        raise TypeError("current review PairSpans must be a list")
    current_signatures = Counter(_signature(span) for span in current_spans)
    seen_ids: set[str] = set()
    matched: list[dict[str, str]] = []
    for old in old_pairs:
        if not isinstance(old, dict):
            raise TypeError("old pair signatures must be objects")
        pair_id = str(old.get("PairID", ""))
        if not pair_id or pair_id in seen_ids or pair_id not in pair_index:
            raise ValueError("old PairID is missing, duplicated, or stale")
        seen_ids.add(pair_id)
        row = pair_index[pair_id]
        if row["MishearID"] != decision["MishearID"]:
            raise ValueError("old PairID belongs to another MishearID")
        if row["OriginalHash"] != decision["OriginalHash"]:
            raise ValueError("current pair OriginalHash differs from review")
        if row["OriginalHash"] != original_hash(original):
            raise ValueError("original source hash no longer matches old pair")
        if _signature(old) != _signature(row):
            raise ValueError("old PairID bounds or UnitType do not match current run")
        if current_signatures[_signature(row)] < 1:
            raise ValueError("old pair does not match canonical review spans")
        current_signatures[_signature(row)] -= 1
        matched.append(row)
    if len(seen_ids) != sum(
        row["MishearID"] == decision["MishearID"] for row in pair_index.values()
    ):
        raise ValueError("old_pairs must cover the record's complete selected pair set")
    if any(current_signatures.values()):
        raise ValueError("canonical review contains a pair absent from old_pairs")
    return matched


def _with_lineage(
    new_spans: object, old_rows: list[dict[str, str]]
) -> list[dict[str, object]]:
    """Preserve IDs for unchanged ranges and require explicit ancestry for new spans."""
    if not isinstance(new_spans, list) or not new_spans:
        raise ValueError("new_pair_spans must be a nonempty complete replacement set")
    old_by_bounds: dict[tuple[int, int, int, int], dict[str, str]] = {}
    old_by_id = {row["PairID"]: row for row in old_rows}
    for old in old_rows:
        key = _pair_signature(old)
        if key in old_by_bounds:
            raise ValueError("old pairs share identical bounds; lineage is ambiguous")
        old_by_bounds[key] = old

    result: list[dict[str, object]] = []
    covered_old: set[str] = set()
    result_bounds: set[tuple[int, int, int, int, str]] = set()
    for item in new_spans:
        span = PairSpan.model_validate(item)
        coordinates = _pair_signature(span.model_dump())
        signature = _signature(span.model_dump())
        if signature in result_bounds:
            raise ValueError("replacement contains duplicate pair spans")
        result_bounds.add(signature)
        existing = old_by_bounds.get(coordinates)
        values = span.model_dump()
        if existing is not None:
            if values["PairID"] not in ("", existing["PairID"]):
                raise ValueError(
                    "same-boundary corrections must preserve the old PairID"
                )
            if values["SupersedesPairID"] not in ("", existing["SupersedesPairID"]):
                raise ValueError(
                    "same-boundary corrections must preserve old supersession"
                )
            values["PairID"] = existing["PairID"]
            values["SupersedesPairID"] = existing["SupersedesPairID"]
            covered_old.add(existing["PairID"])
        else:
            ancestor_id = values["SupersedesPairID"]
            if ancestor_id not in old_by_id:
                raise ValueError(
                    "changed bounds must name an old PairID as supersession"
                )
            if values["PairID"]:
                raise ValueError("new-boundary IDs are generated deterministically")
            covered_old.add(ancestor_id)
        result.append(values)
    if covered_old != set(old_by_id):
        raise ValueError(
            "every old pair must be retained or have explicit replacement lineage"
        )
    return result


def _audit_for_record(
    mishear_id: str,
    old_rows: list[dict[str, str]],
    new_rows: list[dict[str, str]],
    source_hash: str,
    prior_review_sha256: str,
    new_review_sha256: str,
) -> list[dict[str, str]]:
    """Record actual output pairs for every old PairID and its retained descendants."""
    audit: list[dict[str, str]] = []
    for old in old_rows:
        descendants = [
            row
            for row in new_rows
            if row["PairID"] == old["PairID"]
            or row["SupersedesPairID"] == old["PairID"]
        ]
        if not descendants:
            raise ValueError("old PairID has no retained or superseding output pair")
        for new in descendants:
            audit.append(
                {
                    "MishearID": mishear_id,
                    "OriginalHash": source_hash,
                    "OldPairID": old["PairID"],
                    "OldSrcStart": old["SrcStart"],
                    "OldSrcEnd": old["SrcEnd"],
                    "OldTgtStart": old["TgtStart"],
                    "OldTgtEnd": old["TgtEnd"],
                    "OldSrc": old["Src"],
                    "OldTgt": old["Tgt"],
                    "OldUnitType": old["UnitType"],
                    "NewPairID": new["PairID"],
                    "NewSupersedesPairID": new["SupersedesPairID"],
                    "NewSrcStart": new["SrcStart"],
                    "NewSrcEnd": new["SrcEnd"],
                    "NewTgtStart": new["TgtStart"],
                    "NewTgtEnd": new["TgtEnd"],
                    "NewSrc": new["Src"],
                    "NewTgt": new["Tgt"],
                    "NewSrcReading": new["SrcReading"],
                    "NewTgtReading": new["TgtReading"],
                    "NewUnitType": new["UnitType"],
                    "PriorReviewSHA256": prior_review_sha256,
                    "NewReviewSHA256": new_review_sha256,
                }
            )
    return audit


def apply_decisions(
    review_payload: bytes,
    originals: dict[str, tuple[dict[str, str], str]],
    current_pair_rows: list[dict[str, str]],
    patch: dict[str, object],
    *,
    current_run: str,
) -> AppliedDecisions:
    """Validate a whole patch batch, rebuild reviewed rows, then return new CSV bytes."""
    if patch.get("schema_version") != 1:
        raise ValueError("unsupported decision patch schema_version")
    if patch.get("source_run") != current_run:
        raise ValueError("decision patch source_run does not match current run")
    old_review_sha256 = hashlib.sha256(review_payload).hexdigest()
    if patch.get("source_review_sha256") != old_review_sha256:
        raise ValueError("decision patch review CSV hash does not match current input")
    raw_decisions = patch.get("decisions")
    if not isinstance(raw_decisions, list) or not raw_decisions:
        raise ValueError("decision patch must contain a nonempty decisions list")

    decisions = load_reviews(review_payload)
    decision_by_id = {str(item["MishearID"]): item for item in decisions}
    if len(decision_by_id) != len(decisions):
        raise ValueError("canonical reviews contain duplicate MishearID values")
    pair_index = _reviewed_pair_index(current_pair_rows)
    patches_by_id: dict[str, dict[str, Any]] = {}
    for item in raw_decisions:
        if not isinstance(item, dict):
            raise TypeError("each decision patch must be an object")
        mishear_id = str(item.get("MishearID", ""))
        if not mishear_id or mishear_id in patches_by_id:
            raise ValueError("patch MishearID is empty or duplicated")
        patches_by_id[mishear_id] = item

    original_review_sha256 = old_review_sha256
    audit_rows: list[dict[str, str]] = []
    old_rows_by_id: dict[str, list[dict[str, str]]] = {}
    for mishear_id, item in patches_by_id.items():
        if mishear_id not in decision_by_id or mishear_id not in originals:
            raise ValueError("patch references unknown review or original record")
        decision = decision_by_id[mishear_id]
        original, source_file = originals[mishear_id]
        if item.get("OriginalHash") != original_hash(original):
            raise ValueError("patch OriginalHash does not match source original")
        if decision["OriginalHash"] != original_hash(original):
            raise ValueError("canonical review hash does not match source original")
        if decision["Status"] != "reviewed" or decision["TargetDecision"] != "include":
            raise ValueError(
                "word-pair decisions may only edit reviewed included records"
            )
        old_rows = _match_old_pairs(
            decision, item.get("old_pairs"), pair_index, original
        )
        old_rows_by_id[mishear_id] = old_rows
        new_spans = _with_lineage(item.get("new_pair_spans"), old_rows)
        for field in ("SrcAnnotations", "TgtAnnotations"):
            if not isinstance(item.get(field), list):
                raise TypeError(f"patch {field} must replace the full annotation list")
        for field in ("Evidence", "Reason", "Reviewer", "ReviewedAt"):
            if not isinstance(item.get(field), str) or not str(item[field]).strip():
                raise ValueError(f"patch {field} must be nonempty")
        evidence = item["Evidence"]
        reason = item["Reason"]
        if patch.get("preserve_previous_rationale") is True:
            evidence = (
                "Historical rationale for superseded span/reading "
                "(retained verbatim):\n"
                f"{decision['Evidence']}\n\n"
                f"Current boundary review evidence:\n{evidence}"
            )
            reason = (
                "Historical rationale for superseded span/reading "
                "(retained verbatim):\n"
                f"{decision['Reason']}\n\n"
                f"Current boundary review rationale:\n{reason}"
            )
        replacement = decision | {
            "Evidence": evidence,
            "Reason": reason,
            "Reviewer": item["Reviewer"],
            "ReviewedAt": item["ReviewedAt"],
            "SrcAnnotations": item["SrcAnnotations"],
            "TgtAnnotations": item["TgtAnnotations"],
            "PairSpans": new_spans,
        }
        if "RecordValidity" in item:
            replacement["RecordValidity"] = item["RecordValidity"]
        try:
            validated = RecordReview.model_validate(replacement).model_dump()
        except ValidationError as error:
            raise ValueError(
                f"invalid patch review for {mishear_id}: {error}"
            ) from error
        decision_by_id[mishear_id] = validated

        new_rows, _ = review_record(original, source_file, validated)
        audit_rows.extend(
            _audit_for_record(
                mishear_id,
                old_rows,
                new_rows,
                original_hash(original),
                original_review_sha256,
                "",
            )
        )

    # Reconstruct all reviewed decisions before producing any output bytes.
    for decision in decision_by_id.values():
        mishear_id = str(decision["MishearID"])
        if mishear_id not in originals:
            raise ValueError("canonical review references an unknown source original")
        original, source_file = originals[mishear_id]
        review_record(original, source_file, decision)

    review_rows = [decision_by_id[str(item["MishearID"])] for item in decisions]
    result_csv = review_csv(review_rows)
    new_review_sha256 = hashlib.sha256(result_csv).hexdigest()
    # Rebuild actual after rows again to attach the final review CSV hash to the audit.
    audit_by_pair = {
        (row["MishearID"], row["OldPairID"], row["NewPairID"]): row
        for row in audit_rows
    }
    for mishear_id, item in patches_by_id.items():
        decision = decision_by_id[mishear_id]
        original, source_file = originals[mishear_id]
        new_rows, _ = review_record(original, source_file, decision)
        for row in _audit_for_record(
            mishear_id,
            old_rows_by_id[mishear_id],
            new_rows,
            original_hash(original),
            original_review_sha256,
            new_review_sha256,
        ):
            audit_by_pair[(mishear_id, row["OldPairID"], row["NewPairID"])] = row
    return AppliedDecisions(
        result_csv,
        sorted(
            audit_by_pair.values(),
            key=lambda row: (row["MishearID"], row["OldPairID"], row["NewPairID"]),
        ),
    )


def apply_patch_to_directory(
    review_payload: bytes,
    originals: dict[str, tuple[dict[str, str], str]],
    current_pair_rows: list[dict[str, str]],
    patch: dict[str, object],
    *,
    current_run: str,
    output_dir: Path,
) -> AppliedDecisions:
    """Validate the complete batch before writing review and audit files together."""
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_dir}")
    result = apply_decisions(
        review_payload,
        originals,
        current_pair_rows,
        patch,
        current_run=current_run,
    )
    audit_payload = _audit_csv(result.audit_rows)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "reviews.csv").write_bytes(result.review_csv)
    (output_dir / "word-pair-decisions-audit.csv").write_bytes(audit_payload)
    return result


def main() -> None:
    """Validate a patch and write both outputs to a new, empty directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--working-source",
        action="store_true",
        help="rebuild current pair rows from canonical reviews instead of a frozen run",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = (root / args.output_dir).resolve()
    patch = json.loads(args.patch.read_text(encoding="utf-8"))
    review_path = root / "data/annotations/reviews.csv"
    review_payload = review_path.read_bytes()
    originals: dict[str, tuple[dict[str, str], str]] = {}
    for path in sorted((root / "data/mishearing").rglob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for raw in csv.DictReader(stream):
                raw["source_file"] = path.relative_to(root).as_posix()
                originals[raw["MishearID"]] = (raw, raw["source_file"])
    if args.working_source:
        current_run = "working-reviews:" + hashlib.sha256(review_payload).hexdigest()
        pair_rows = rebuild_current_pair_rows(review_payload, originals)
    else:
        pointer = json.loads(
            (root / "resource/pairs_v2/current.json").read_text(encoding="utf-8")
        )
        current_run = str(pointer["directory"])
        run_dir = root / "resource/pairs_v2" / current_run
        with (run_dir / "reviewed.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            pair_rows = list(csv.DictReader(stream))
    result = apply_patch_to_directory(
        review_payload,
        originals,
        pair_rows,
        patch,
        current_run=current_run,
        output_dir=output_dir,
    )
    print(
        _canonical_json(
            {
                "patched_records": len(patch["decisions"]),
                "audit_rows": len(result.audit_rows),
                "review_csv_sha256": hashlib.sha256(result.review_csv).hexdigest(),
                "output_dir": str(output_dir),
            }
        )
    )


if __name__ == "__main__":
    main()
