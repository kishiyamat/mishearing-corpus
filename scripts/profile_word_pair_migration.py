"""Create a read-only, pair-level baseline for the word-unit migration audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from corpus_api.dictionary import DictionaryEntry, DictionaryResult, dictionary_entries
from corpus_api.pair_workflow import extract_record


def _annotations_fit(
    original: str, start: int, end: int, annotations: list[dict[str, Any]]
) -> str:
    same_range = [
        annotation
        for annotation in annotations
        if annotation["start"] == start and annotation["end"] == end
    ]
    if any(annotation["surface"] == original[start:end] for annotation in same_range):
        return "exact_range_surface_match"
    if same_range:
        return "exact_range_different_surface_classified_note"
    covering = any(
        int(annotation["start"]) <= start and int(annotation["end"]) >= end
        for annotation in annotations
    )
    if covering:
        return "covered_by_wider_override"
    nested = any(
        annotation["start"] == start and annotation["end"] <= end
        for annotation in annotations
    )
    return "nested_override_needs_review" if nested else "no_covering_override"


def profile(
    root: Path,
    audit_dir: Path,
    input_run: str,
    annotation_ref: str,
    annotation_file: Path | None = None,
) -> tuple[int, Counter[str]]:
    run = root / "resource/pairs_v2" / input_run
    if annotation_file is not None:
        annotation_bytes = annotation_file.read_bytes()
    else:
        annotation_bytes = subprocess.check_output(
            [
                "git",
                "-C",
                str(root),
                "show",
                f"{annotation_ref}:data/annotations/reviews.csv",
            ]
        )
    annotation_sha256 = hashlib.sha256(annotation_bytes).hexdigest()
    with (run / "reviewed.csv").open(encoding="utf-8-sig", newline="") as stream:
        pair_rows = list(csv.DictReader(stream))
    import io

    with io.TextIOWrapper(
        io.BytesIO(annotation_bytes), encoding="utf-8-sig", newline=""
    ) as stream:
        reviews = list(csv.DictReader(stream))
    originals: dict[str, dict[str, str]] = {}
    for path in sorted((root / "data/mishearing").rglob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            originals.update({row["MishearID"]: row for row in csv.DictReader(stream)})

    included = {
        row["MishearID"]: row
        for row in reviews
        if row["Status"] == "reviewed" and row["TargetDecision"] == "include"
    }
    by_span: dict[tuple[str, int, int, int, int, str], dict[str, str]] = {}
    for row in pair_rows:
        if row["TargetDecision"] != "include":
            continue
        key = (
            row["MishearID"],
            int(row["SrcStart"]),
            int(row["SrcEnd"]),
            int(row["TgtStart"]),
            int(row["TgtEnd"]),
            row["UnitType"],
        )
        if key in by_span:
            raise ValueError(f"duplicate current pair key: {key}")
        by_span[key] = row

    audit_rows: list[dict[str, str]] = []
    for mishear_id, review in included.items():
        source = originals[mishear_id]
        proposals, _ = extract_record(source, "structural-profile")
        source_annotations = json.loads(review["SrcAnnotations"])
        target_annotations = json.loads(review["TgtAnnotations"])
        for span in json.loads(review["PairSpans"]):
            key = (
                mishear_id,
                int(span["src_start"]),
                int(span["src_end"]),
                int(span["tgt_start"]),
                int(span["tgt_end"]),
                span["unit_type"],
            )
            pair = by_span.pop(key)
            src_start, src_end = key[1:3]
            tgt_start, tgt_end = key[3:5]
            src_fit = _annotations_fit(
                source["Src"], src_start, src_end, source_annotations
            )
            tgt_fit = _annotations_fit(
                source["Tgt"], tgt_start, tgt_end, target_annotations
            )
            fit = f"src:{src_fit};tgt:{tgt_fit}"
            proposal_values = [
                {
                    "src_start": int(proposal["SrcStart"]),
                    "src_end": int(proposal["SrcEnd"]),
                    "tgt_start": int(proposal["TgtStart"]),
                    "tgt_end": int(proposal["TgtEnd"]),
                    "src": proposal["Src"],
                    "tgt": proposal["Tgt"],
                    "unit_type": proposal["UnitType"],
                }
                for proposal in proposals
            ]
            proposal_matches = [
                proposal
                for proposal in proposal_values
                if (
                    proposal["src_start"],
                    proposal["src_end"],
                    proposal["tgt_start"],
                    proposal["tgt_end"],
                )
                == (src_start, src_end, tgt_start, tgt_end)
            ]
            audit_rows.append(
                {
                    "MishearID": mishear_id,
                    "PairID": pair["PairID"],
                    "SupersedesPairID": pair["SupersedesPairID"],
                    "OriginalHash": review["OriginalHash"],
                    "SourceFile": pair["SourceFile"],
                    "URL": pair["URL"],
                    "OldSrcStart": str(src_start),
                    "OldSrcEnd": str(src_end),
                    "OldTgtStart": str(tgt_start),
                    "OldTgtEnd": str(tgt_end),
                    "OldSrcSurface": source["Src"][src_start:src_end],
                    "OldTgtSurface": source["Tgt"][tgt_start:tgt_end],
                    "OldSrcReading": pair["SrcReading"],
                    "OldTgtReading": pair["TgtReading"],
                    "OldUnitType": pair["UnitType"],
                    "AnnotationSpanFit": fit,
                    "MachineProposalCount": str(len(proposal_values)),
                    "SameSpanProposals": json.dumps(
                        proposal_matches, ensure_ascii=False, separators=(",", ":")
                    ),
                    "OtherProposals": json.dumps(
                        [p for p in proposal_values if p not in proposal_matches],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "OldEvidence": pair["Evidence"],
                    "OldReason": pair["Reason"],
                    "ProposedSrcStart": "",
                    "ProposedSrcEnd": "",
                    "ProposedTgtStart": "",
                    "ProposedTgtEnd": "",
                    "ProposedSrcSurface": "",
                    "ProposedTgtSurface": "",
                    "ProposedUnitType": "",
                    "DecisionClass": "RESEARCH_REQUIRED",
                    "DecisionBasis": "Structural profile only; no semantic or lexical review",
                    "HoldReason": "Unit boundaries and evidence for the selected comparison have not been individually reviewed",
                    "Reviewer": "automated-profile",
                    "EvidenceChecked": "no",
                    "SourceLocationChecked": "no",
                    "LineageAction": "undetermined",
                }
            )
    if by_span:
        raise ValueError(f"current run has {len(by_span)} unmatched included pairs")

    audit_dir.mkdir(parents=True, exist_ok=True)
    output = audit_dir / "pair-level-audit.csv"
    manifest_path = audit_dir / "manifest.json"
    if output.exists() or manifest_path.exists():
        raise FileExistsError(
            f"refusing to overwrite an existing reviewed audit directory: {audit_dir}"
        )
    fieldnames = list(audit_rows[0]) if audit_rows else []
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            sorted(audit_rows, key=lambda row: (row["MishearID"], row["PairID"]))
        )
    counts = Counter(row["AnnotationSpanFit"] for row in audit_rows)
    proposal_counts = Counter(
        "same_span_unit_retyped"
        if any(
            proposal["unit_type"] != row["OldUnitType"]
            for proposal in json.loads(row["SameSpanProposals"])
        )
        else "same_span_same_type"
        if json.loads(row["SameSpanProposals"])
        else "no_same_span_proposal"
        for row in audit_rows
    )
    record_count = len(included)
    manifest = {
        "profile": "read-only structural baseline; no pair semantics approved",
        "input_run": input_run,
        "annotation_ref": annotation_ref,
        "annotation_file": "data/annotations/reviews.csv",
        "annotation_sha256": annotation_sha256,
        "extractor_sha256": hashlib.sha256(
            (root / "corpus_api/pair_workflow.py").read_bytes()
        ).hexdigest(),
        "included_record_count": record_count,
        "included_pair_count": len(audit_rows),
        "annotation_span_fit_counts": dict(sorted(counts.items())),
        "extract_record_same_span_proposal_counts": dict(
            sorted(proposal_counts.items())
        ),
        "decision_class_counts": {"RESEARCH_REQUIRED": len(audit_rows)},
        "audit_file": output.name,
    }
    (audit_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(audit_rows), counts


def dictionary_profile(audit_dir: Path) -> None:
    """Check actual whole-surface IPADIC entries for every included side surface."""
    audit_path = audit_dir / "pair-level-audit.csv"
    output_path = audit_dir / "dictionary-evidence.jsonl"
    summary_path = audit_dir / "dictionary-profile.json"
    if output_path.exists() or summary_path.exists():
        raise FileExistsError("dictionary profile outputs already exist")
    with audit_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    surfaces = sorted(
        {row[field] for row in rows for field in ("OldSrcSurface", "OldTgtSurface")}
    )
    entry_surfaces = 0
    dictionary_hashes: set[str] = set()
    results_by_surface: dict[str, DictionaryResult] = {}
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        for index, surface in enumerate(surfaces, start=1):
            result = dictionary_entries(surface)
            results_by_surface[surface] = result
            dictionary_hashes.add(result["dictionary_sha256"])
            entry_surfaces += bool(result["entries"])
            line = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            stream.write(line + "\n")
            if index % 500 == 0:
                print(
                    f"checked dictionary entries for {index}/{len(surfaces)} surfaces"
                )

    def reading_key(reading: str) -> str:
        return "".join(
            chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char
            for char in unicodedata.normalize("NFKC", reading)
        )

    def qualifying(entry: DictionaryEntry) -> bool:
        features = entry["features"]
        part_of_speech = features[0]
        if part_of_speech not in {"名詞", "動詞", "形容詞", "副詞", "連体詞", "感動詞"}:
            return False
        return not (
            part_of_speech == "名詞"
            and len(features) > 1
            and features[1] in {"接尾", "接頭", "非自立"}
        )

    side_reading_matches: Counter[str] = Counter()
    side_qualifying_entries: Counter[str] = Counter()
    pair_both_supported = 0
    word_proposal_pairs = 0
    auto_retype_pairs = 0
    auto_retype_ids: list[str] = []
    for row in rows:
        readings_supported: list[bool] = []
        side_qualifying: list[bool] = []
        for side, surface_field, reading_field in (
            ("src", "OldSrcSurface", "OldSrcReading"),
            ("tgt", "OldTgtSurface", "OldTgtReading"),
        ):
            entries = results_by_surface[row[surface_field]]["entries"]
            reading_match = any(
                reading_key(entry["reading"]) == reading_key(row[reading_field])
                for entry in entries
            )
            pos_match = any(qualifying(entry) for entry in entries)
            side_reading_matches[side] += reading_match
            side_qualifying_entries[side] += pos_match
            readings_supported.append(reading_match)
            side_qualifying.append(pos_match)
        both_supported = all(readings_supported) and all(side_qualifying)
        pair_both_supported += both_supported
        proposals = json.loads(row["SameSpanProposals"])
        has_word_proposal = any(
            proposal["unit_type"] == "word" for proposal in proposals
        )
        word_proposal_pairs += has_word_proposal
        if (
            both_supported
            and has_word_proposal
            and row["AnnotationSpanFit"]
            == "src:exact_range_surface_match;tgt:exact_range_surface_match"
        ):
            auto_retype_pairs += 1
            auto_retype_ids.append(row["PairID"])
    evidence = {
        "included_pair_count": len(rows),
        "unique_side_surface_count": len(surfaces),
        "surfaces_with_exact_whole_surface_entry": entry_surfaces,
        "surfaces_without_exact_whole_surface_entry": len(surfaces) - entry_surfaces,
        "dictionary_sha256_values": sorted(dictionary_hashes),
        "side_reading_matches": dict(side_reading_matches),
        "side_qualifying_part_of_speech_entries": dict(side_qualifying_entries),
        "pairs_with_both_sides_supported_by_exact_dictionary_entry": pair_both_supported,
        "pairs_with_same_span_word_proposal": word_proposal_pairs,
        "potential_auto_word_retype_pairs": auto_retype_pairs,
        "potential_auto_word_retype_pair_ids": auto_retype_ids,
        "evidence_file": output_path.name,
        "qualification": "candidate count only; source context, common-context minimality, and annotation semantics still require checking",
    }
    summary_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False))


def candidate_dictionary_profile(audit_dir: Path) -> None:
    """Look up only shortened proposal surfaces; this never edits review decisions."""
    audit_path = audit_dir / "pair-level-audit.csv"
    output_path = audit_dir / "candidate-dictionary-evidence.jsonl"
    summary_path = audit_dir / "candidate-dictionary-profile.json"
    if output_path.exists() or summary_path.exists():
        raise FileExistsError("candidate dictionary outputs already exist")
    with audit_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    proposal_instances = 0
    surfaces: set[str] = set()
    proposal_inventory: list[dict[str, Any]] = []
    for row in rows:
        old_bounds = (
            int(row["OldSrcStart"]),
            int(row["OldSrcEnd"]),
            int(row["OldTgtStart"]),
            int(row["OldTgtEnd"]),
        )
        for proposal in json.loads(row["OtherProposals"]):
            new_bounds = (
                proposal["src_start"],
                proposal["src_end"],
                proposal["tgt_start"],
                proposal["tgt_end"],
            )
            if new_bounds == old_bounds:
                continue
            proposal_instances += 1
            surfaces.update(
                surface for surface in (proposal["src"], proposal["tgt"]) if surface
            )
            proposal_inventory.append(
                {
                    "PairID": row["PairID"],
                    "MishearID": row["MishearID"],
                    "old_src": row["OldSrcSurface"],
                    "old_tgt": row["OldTgtSurface"],
                    "old_src_reading": row["OldSrcReading"],
                    "old_tgt_reading": row["OldTgtReading"],
                    "new_src": proposal["src"],
                    "new_tgt": proposal["tgt"],
                    "new_bounds": list(new_bounds),
                    "unit_type": proposal["unit_type"],
                }
            )
    found: dict[str, DictionaryResult] = {}
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        for index, surface in enumerate(sorted(surfaces), start=1):
            result = dictionary_entries(surface)
            found[surface] = result
            stream.write(
                json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            if index % 500 == 0:
                print(
                    f"checked candidate dictionary entries for {index}/{len(surfaces)} surfaces"
                )
    reading_match_instances = 0
    for proposal in proposal_inventory:
        src_entries = found[str(proposal["new_src"])]["entries"]
        tgt_entries = found[str(proposal["new_tgt"])]["entries"]
        src_matches = [
            entry
            for entry in src_entries
            if entry["reading"] == proposal["old_src_reading"]
        ]
        tgt_matches = [
            entry
            for entry in tgt_entries
            if entry["reading"] == proposal["old_tgt_reading"]
        ]
        proposal["src_exact_reading_entries"] = src_matches
        proposal["tgt_exact_reading_entries"] = tgt_matches
        if src_matches and tgt_matches:
            reading_match_instances += 1
    inventory_path = audit_dir / "candidate-proposals.jsonl"
    inventory_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
            for item in proposal_inventory
        ),
        encoding="utf-8",
    )
    summary = {
        "shortened_proposal_instances": proposal_instances,
        "unique_candidate_side_surfaces": len(surfaces),
        "shortened_proposals_with_exact_reading_entries_on_both_sides": reading_match_instances,
        "dictionary_sha256_values": sorted(
            {result["dictionary_sha256"] for result in found.values()}
        ),
        "candidate_dictionary_evidence": output_path.name,
        "candidate_proposal_inventory": inventory_path.name,
        "qualification": "dictionary readings are evidence only; token alignment and meanings still require review",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reviews/2026-10-24-word-extraction"),
    )
    parser.add_argument("--input-run", default="2026-10-24-homophones-retained")
    parser.add_argument(
        "--annotation-ref", default="772419eab62e67e39e09a0bec31eede78e255ac4"
    )
    parser.add_argument(
        "--annotation-file",
        type=Path,
        help="read the baseline review CSV directly when --root is a git archive",
    )
    parser.add_argument(
        "--dictionary-evidence-only",
        action="store_true",
        help="add per-surface exact dictionary evidence without rebuilding the audit ledger",
    )
    parser.add_argument(
        "--candidate-dictionary-evidence-only",
        action="store_true",
        help="look up shortened proposal surfaces without editing the audit ledger",
    )
    args = parser.parse_args()
    audit_dir = (args.root / args.output).resolve()
    if args.candidate_dictionary_evidence_only:
        candidate_dictionary_profile(audit_dir)
    elif args.dictionary_evidence_only:
        dictionary_profile(audit_dir)
    else:
        count, fits = profile(
            args.root.resolve(),
            audit_dir,
            args.input_run,
            args.annotation_ref,
            args.annotation_file,
        )
        print(f"profiled {count} included pairs; annotation span fit: {dict(fits)}")


if __name__ == "__main__":
    main()
