"""Build a non-mutating working-source patch from Sol phrase-span tables.

The patch is only a proposal: the application engine performs the final
source-hash, PairID, old-signature, and full-record validation before writing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

from apply_word_pair_decisions import rebuild_current_pair_rows

from corpus_api.pair_workflow import load_reviews, original_hash


def _json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object in {path}")
    return cast(dict[str, Any], value)


def _source_originals(root: Path) -> dict[str, tuple[dict[str, str], str]]:
    originals: dict[str, tuple[dict[str, str], str]] = {}
    for path in sorted((root / "data/mishearing").rglob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                row["source_file"] = path.relative_to(root).as_posix()
                originals[row["MishearID"]] = (row, row["source_file"])
    return originals


def _ranges(item: dict[str, Any]) -> list[tuple[int, int, int, int, str, str, str]]:
    pairs = item.get("new_pairs")
    if pairs is None:
        pair = item.get("new_pair")
        pairs = [pair] if pair is not None else []
    rows = []
    for pair in pairs:
        if isinstance(pair, dict):
            nested_pair = pair.get("new_pair", pair)
            if isinstance(nested_pair, dict):
                src, tgt = nested_pair["src_span"], nested_pair["tgt_span"]
                src_surface, tgt_surface = nested_pair["src"], nested_pair["tgt"]
                src_reading, tgt_reading = (
                    nested_pair["src_reading"],
                    nested_pair["tgt_reading"],
                )
            else:
                src, tgt = nested_pair
                src_surface, tgt_surface = src[2], tgt[2]
                src_reading, tgt_reading = src[3], tgt[3]
            unit = pair.get(
                "new_unit_type",
                pair.get("unit_type", item.get("new_unit_type", "phrase")),
            )
        else:
            src, tgt = pair
            src_surface, tgt_surface = src[2], tgt[2]
            src_reading, tgt_reading = src[3], tgt[3]
            unit = item["new_unit_type"]
        rows.append((src[0], src[1], tgt[0], tgt[1], unit, src_reading, tgt_reading))
        # Surface strings from the adjudication table are used as a consistency
        # check against the original source by the review_record validator.
        if src_surface != src[2] or tgt_surface != tgt[2]:
            raise ValueError(f"table surface/bounds mismatch for {item['MishearID']}")
    return rows


def _annotation_replacements(
    current: dict[str, Any],
    original: dict[str, str],
    old_row: dict[str, str],
    new_pairs: list[tuple[int, int, int, int, str, str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result: list[list[dict[str, Any]]] = []
    for side, start_key, end_key, surface_key, reading_key, other_start, other_end in (
        ("Src", "src_start", "src_end", "Src", "SrcReading", "SrcStart", "SrcEnd"),
        ("Tgt", "tgt_start", "tgt_end", "Tgt", "TgtReading", "TgtStart", "TgtEnd"),
    ):
        source = original[side]
        old_start, old_end = int(old_row[other_start]), int(old_row[other_end])
        new_specs = [
            (
                p[0] if side == "Src" else p[2],
                p[1] if side == "Src" else p[3],
                p[5] if side == "Src" else p[6],
            )
            for p in new_pairs
        ]
        old_annotations = current[f"{side}Annotations"]
        kept = []
        inherited: list[dict[str, Any]] = []
        removed_ranges: list[tuple[int, int]] = []
        for annotation in old_annotations:
            if annotation["start"] < old_end and old_start < annotation["end"]:
                removed_ranges.append((annotation["start"], annotation["end"]))
                if not inherited:
                    inherited = [
                        {key: annotation[key] for key in ("meanings", "qualifiers")}
                    ]
            else:
                kept.append(annotation)
        # Each reviewed contrast gets a precise override; inherited meanings and
        # qualifiers stay on-pair rather than leaking into removed context.
        for start, end, reading in new_specs:
            note = inherited[0] if inherited else {"meanings": [], "qualifiers": []}
            kept.append(
                {
                    "start": start,
                    "end": end,
                    "surface": source[start:end],
                    "reading": reading,
                    "meanings": list(note["meanings"]),
                    "qualifiers": list(note["qualifiers"]),
                }
            )
        # If a complete parenthetical was removed from the selected spoken span,
        # preserve it as a non-pair explanatory annotation with no reading.
        new_coverage = [(a, b) for a, b, _ in new_specs]
        for match in re.finditer(r"[（(]([^（）()]*)[）)]", source):
            a, b = match.start(), match.end()
            if not any(a < old_b and old_a < b for old_a, old_b in removed_ranges):
                continue
            if any(a < end and start < b for start, end in new_coverage):
                continue
            inner = match.group(1)
            if inner:
                kept.append(
                    {
                        "start": a,
                        "end": b,
                        "surface": inner,
                        "reading": "",
                        "meanings": [],
                        "qualifiers": ["括弧内表記補足（非発話）"],
                    }
                )
        result.append(sorted(kept, key=lambda a: (a["start"], a["end"])))
    return result[0], result[1]


def build_patch(
    root: Path,
    review_payload: bytes,
    originals: dict[str, tuple[dict[str, str], str]],
    pair_rows: list[dict[str, str]],
    base_path: Path,
    overlay_path: Path,
) -> tuple[dict[str, Any], dict[str, int]]:
    base = _json(base_path)
    overlay_items: dict[str, dict[str, Any]] = {}
    if overlay_path.exists():
        overlay = _json(overlay_path)
        overlay_items = {item["MishearID"]: item for item in overlay["items"]}
    decisions: dict[str, dict[str, Any]] = {}
    for item in base["items"]:
        if item["decision"] != "KEEP_CONTEXTUAL":
            decisions[item["MishearID"]] = item
    for item in overlay_items.values():
        if item["decision"] not in {"KEEP", "KEEP_CONTEXTUAL", "SPLIT_REQUIRED"}:
            decisions[item["MishearID"]] = item

    records = {str(x["MishearID"]): x for x in load_reviews(review_payload)}
    rows_by_mishear: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pair_rows:
        if row["TargetDecision"] == "include":
            rows_by_mishear[row["MishearID"]].append(row)

    patch_decisions: list[dict[str, Any]] = []
    skipped: dict[str, int] = defaultdict(int)
    for mishear_id, item in decisions.items():
        current = records[mishear_id]
        original, _ = originals[mishear_id]
        if (
            item["OriginalHash"] != original_hash(original)
            or current["OriginalHash"] != item["OriginalHash"]
        ):
            skipped["hash_mismatch"] += 1
            continue
        matching = [
            row
            for row in rows_by_mishear[mishear_id]
            if row["PairID"] == item["OldPairID"]
        ]
        if len(matching) != 1:
            skipped["pairid_mismatch"] += 1
            continue
        old_row = matching[0]
        expected = item.get("old_pair")
        if expected is None:
            expected = item.get("old_pairs")
        if (
            isinstance(expected, list)
            and len(expected) == 2
            and isinstance(expected[0], list)
        ):
            src, tgt = expected
            if (
                int(old_row["SrcStart"]),
                int(old_row["SrcEnd"]),
                int(old_row["TgtStart"]),
                int(old_row["TgtEnd"]),
            ) != (src[0], src[1], tgt[0], tgt[1]):
                skipped["bounds_mismatch"] += 1
                continue
        new_specs = _ranges(item)
        if not new_specs:
            skipped["no_spans"] += 1
            continue
        new_spans = []
        for row in rows_by_mishear[mishear_id]:
            if row["PairID"] != item["OldPairID"]:
                new_spans.append(
                    {
                        "src_start": int(row["SrcStart"]),
                        "src_end": int(row["SrcEnd"]),
                        "tgt_start": int(row["TgtStart"]),
                        "tgt_end": int(row["TgtEnd"]),
                        "unit_type": row["UnitType"],
                        "PairID": row["PairID"],
                        "SupersedesPairID": row["SupersedesPairID"],
                    }
                )
                continue
            for s0, s1, t0, t1, unit, _, _ in new_specs:
                same_bounds = (s0, s1, t0, t1) == (
                    int(row["SrcStart"]),
                    int(row["SrcEnd"]),
                    int(row["TgtStart"]),
                    int(row["TgtEnd"]),
                )
                new_spans.append(
                    {
                        "src_start": s0,
                        "src_end": s1,
                        "tgt_start": t0,
                        "tgt_end": t1,
                        "unit_type": unit,
                        "PairID": row["PairID"] if same_bounds else "",
                        "SupersedesPairID": "" if same_bounds else row["PairID"],
                    }
                )
        old_pairs = [
            {
                "PairID": row["PairID"],
                "src_start": int(row["SrcStart"]),
                "src_end": int(row["SrcEnd"]),
                "tgt_start": int(row["TgtStart"]),
                "tgt_end": int(row["TgtEnd"]),
                "unit_type": row["UnitType"],
            }
            for row in rows_by_mishear[mishear_id]
        ]
        src_annotations, tgt_annotations = _annotation_replacements(
            current, original, old_row, new_specs
        )
        basis_parts = [
            str(item.get("basis", item.get("reason", item.get("decision", "reviewed"))))
        ]
        source_parts = [
            str(item.get(key, ""))
            for key in (
                "source_evidence",
                "source_note",
                "source_note_excerpt",
                "old_review_evidence",
            )
            if item.get(key)
        ]
        for child in item.get("new_pairs", []):
            if isinstance(child, dict):
                basis_parts.extend(
                    str(child[key])
                    for key in ("basis", "reading_basis", "reading_caveat")
                    if child.get(key)
                )
        basis_text = " | ".join(dict.fromkeys(basis_parts))
        evidence = (
            str(current["Evidence"]).rstrip() + " Sol phrase audit: " + basis_text
        )
        if source_parts:
            evidence += " Source/adjudication detail: " + " | ".join(
                dict.fromkeys(source_parts)
            )
        reason = (
            str(current["Reason"]).rstrip()
            + " Unit classification/boundary reviewed against source evidence: "
            + basis_text
        )
        patch_decisions.append(
            {
                "MishearID": mishear_id,
                "OriginalHash": item["OriginalHash"],
                "old_pairs": old_pairs,
                "new_pair_spans": new_spans,
                "SrcAnnotations": src_annotations,
                "TgtAnnotations": tgt_annotations,
                "Evidence": evidence,
                "Reason": reason,
                "Reviewer": "agent:gpt-6-sol",
                "ReviewedAt": "2026-10-24",
            }
        )
    sha = hashlib.sha256(review_payload).hexdigest()
    patch = {
        "schema_version": 1,
        "source_run": "working-reviews:" + sha,
        "source_review_sha256": sha,
        "decisions": patch_decisions,
    }
    return patch, dict(skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    review_payload = (root / "data/annotations/reviews.csv").read_bytes()
    originals = _source_originals(root)
    pair_rows = rebuild_current_pair_rows(review_payload, originals)
    patch, skipped = build_patch(
        root,
        review_payload,
        originals,
        pair_rows,
        Path("/tmp/uncovered-phrases-sol-final-decisions.json"),
        Path("/tmp/no-overlay-final-table-is-integrated"),
    )
    args.output.write_text(
        json.dumps(patch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "decision_count": len(patch["decisions"]),
                "skipped": skipped,
                "source_review_sha256": patch["source_review_sha256"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
