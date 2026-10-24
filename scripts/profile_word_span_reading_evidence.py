"""Profile dictionary evidence for shorter word-span candidates without approving them."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import subprocess
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from corpus_api.dictionary import dictionary_entries
from corpus_api.pair_workflow import extract_record, extractor_hash


def _reading_key(reading: str) -> str:
    """Normalize kana width and katakana/hiragana for evidence comparison."""
    normalized = unicodedata.normalize("NFKC", reading)
    return "".join(
        chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char for char in normalized
    )


@lru_cache(maxsize=4096)
def _best_path_tokens(surface: str) -> tuple[tuple[str, str], ...]:
    """Return MeCab's best-path surface/reading sequence as diagnostic evidence."""
    result = subprocess.run(
        ["mecab", "-Ochasen"],
        input=surface,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=30,
    )
    tokens: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) >= 2 and fields[0] not in {"EOS", ""}:
            tokens.append((fields[0], fields[1]))
    return tuple(tokens)


@lru_cache(maxsize=8192)
def _entry_readings(surface: str) -> tuple[str, ...]:
    """Return all exact known dictionary readings, excluding best-path guessing."""
    entries = json.loads(_exact_entries_json(surface))
    return tuple(sorted({entry["reading"] for entry in entries}))


@lru_cache(maxsize=8192)
def _exact_entries_json(surface: str) -> str:
    """Cache immutable JSON for exact whole-surface dictionary alternatives."""
    if not surface:
        return "[]"
    return json.dumps(
        dictionary_entries(surface)["entries"],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _unique_alignment(surface: str, target_reading: str) -> dict[str, object]:
    """Count exact dictionary-reading token combinations, saturating at two."""
    tokens = _best_path_tokens(surface)
    alternatives = [_entry_readings(token_surface) for token_surface, _ in tokens]
    if not tokens or any(not readings for readings in alternatives):
        return {
            "status": "unknown_token_or_empty_analysis",
            "best_path_reading": "".join(reading for _, reading in tokens),
            "best_path_matches": _reading_key("".join(reading for _, reading in tokens))
            == _reading_key(target_reading),
            "matching_dictionary_combinations": 0,
            "token_readings": [list(readings) for readings in alternatives],
        }
    target = _reading_key(target_reading)
    # Keep only target prefixes and cap the number of distinct alignments at two.
    states: dict[str, int] = {"": 1}
    for readings in alternatives:
        next_states: dict[str, int] = {}
        for prefix, count in states.items():
            for reading in readings:
                combined = prefix + _reading_key(reading)
                if target.startswith(combined):
                    next_states[combined] = min(2, next_states.get(combined, 0) + count)
        states = next_states
    matches = states.get(target, 0)
    best_path_reading = "".join(reading for _, reading in tokens)
    return {
        "status": "unique_dictionary_alignment"
        if matches == 1
        else "ambiguous_dictionary_alignment"
        if matches > 1
        else "no_dictionary_alignment",
        "best_path_reading": best_path_reading,
        "best_path_matches": _reading_key(best_path_reading) == target,
        "matching_dictionary_combinations": matches,
        "token_surfaces": [token_surface for token_surface, _ in tokens],
        "token_readings": [list(readings) for readings in alternatives],
    }


def _covering_annotations(
    annotations: list[dict[str, Any]], start: int, end: int
) -> list[dict[str, Any]]:
    """Select existing overrides that contain a proposed source range."""
    return [
        annotation
        for annotation in annotations
        if int(annotation["start"]) <= start and int(annotation["end"]) >= end
    ]


def _candidate_token_mapping(
    annotation_surface: str, candidate_start: int, candidate_end: int
) -> dict[str, object]:
    """Check whether candidate offsets map to whole MeCab tokens in an override."""
    token_rows = _best_path_tokens(annotation_surface)
    positioned: list[tuple[int, int, str, str]] = []
    cursor = 0
    for token_surface, reading in token_rows:
        start = annotation_surface.find(token_surface, cursor)
        if start < 0:
            return {"status": "token_surface_alignment_failed", "tokens": []}
        end = start + len(token_surface)
        positioned.append((start, end, token_surface, reading))
        cursor = end
    selected = [
        token
        for token in positioned
        if candidate_start <= token[0] and token[1] <= candidate_end
    ]
    exact = (
        bool(selected)
        and selected[0][0] == candidate_start
        and selected[-1][1] == candidate_end
        and all(left[1] == right[0] for left, right in itertools.pairwise(selected))
    )
    return {
        "status": "exact_token_boundary_mapping"
        if exact
        else "candidate_cuts_or_gaps_tokens",
        "candidate_relative_start": candidate_start,
        "candidate_relative_end": candidate_end,
        "tokens": [
            {
                "start": start,
                "end": end,
                "surface": token_surface,
                "best_path_reading": reading,
                "exact_dictionary_readings": list(_entry_readings(token_surface)),
            }
            for start, end, token_surface, reading in selected
        ],
    }


def _original_rows(root: Path) -> dict[str, dict[str, str]]:
    """Read immutable corpus CSVs to map review IDs back to original surfaces."""
    records: dict[str, dict[str, str]] = {}
    for path in sorted((root / "data/mishearing").rglob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            records.update({row["MishearID"]: row for row in csv.DictReader(stream)})
    return records


def profile(root: Path, output: Path) -> dict[str, object]:
    """Write proposal/annotation/dictionary diagnostics without changing reviews."""
    review_path = root / "data/annotations/reviews.csv"
    review_bytes = review_path.read_bytes()
    with review_path.open(encoding="utf-8-sig", newline="") as stream:
        reviews = list(csv.DictReader(stream))
    originals = _original_rows(root)
    rows: list[dict[str, str]] = []
    for review in reviews:
        if review["Status"] != "reviewed" or review["TargetDecision"] != "include":
            continue
        original = originals[review["MishearID"]]
        source_annotations = json.loads(review["SrcAnnotations"])
        target_annotations = json.loads(review["TgtAnnotations"])
        proposals, _ = extract_record(original, "word-span-reading-profile")
        for proposal in proposals:
            if proposal["UnitType"] == "phrase":
                continue
            sides: dict[str, object] = {}
            for side, original_field, start_field, end_field, side_annotations in (
                (
                    "Src",
                    "Src",
                    "SrcStart",
                    "SrcEnd",
                    source_annotations,
                ),
                (
                    "Tgt",
                    "Tgt",
                    "TgtStart",
                    "TgtEnd",
                    target_annotations,
                ),
            ):
                start, end = int(proposal[start_field]), int(proposal[end_field])
                candidate_surface = proposal[side]
                covering = _covering_annotations(side_annotations, start, end)
                exact_candidates = json.loads(_exact_entries_json(candidate_surface))
                old_annotation_diagnostics: list[dict[str, object]] = []
                for annotation in covering:
                    old_start, old_end = (
                        int(annotation["start"]),
                        int(annotation["end"]),
                    )
                    raw_surface = original[original_field][old_start:old_end]
                    if raw_surface != annotation["surface"]:
                        alignment: dict[str, object] = {
                            "status": "override_surface_differs_from_original_range"
                        }
                    elif annotation["reading"]:
                        alignment = _unique_alignment(
                            raw_surface, annotation["reading"]
                        )
                    else:
                        alignment = {"status": "old_reading_unset"}
                    mapping = _candidate_token_mapping(
                        raw_surface, start - old_start, end - old_start
                    )
                    old_annotation_diagnostics.append(
                        {
                            "start": old_start,
                            "end": old_end,
                            "surface": annotation["surface"],
                            "reading": annotation["reading"],
                            "range_equals_candidate": (old_start, old_end)
                            == (start, end),
                            "dictionary_alignment": alignment,
                            "candidate_token_mapping": mapping,
                        }
                    )
                sides[side] = {
                    "candidate_start": start,
                    "candidate_end": end,
                    "candidate_surface": candidate_surface,
                    "exact_surface_dictionary_entries": exact_candidates,
                    "covering_old_overrides": old_annotation_diagnostics,
                    "candidate_reading_auto_confirmed": False,
                }
            rows.append(
                {
                    "MishearID": review["MishearID"],
                    "OriginalHash": review["OriginalHash"],
                    "CandidateUnitType": proposal["UnitType"],
                    "CandidateSrc": json.dumps(sides["Src"], ensure_ascii=False),
                    "CandidateTgt": json.dumps(sides["Tgt"], ensure_ascii=False),
                    "CandidatePairID": proposal["PairID"],
                    "CurrentPairSpanCount": str(len(json.loads(review["PairSpans"]))),
                    "Status": "DIAGNOSTIC_ONLY_REVIEW_REQUIRED",
                }
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    fields = list(rows[0]) if rows else []
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "purpose": "read-only candidate span reading evidence; no review approval",
        "review_csv_sha256": hashlib.sha256(review_bytes).hexdigest(),
        "extractor_sha256": extractor_hash(),
        "candidate_count": len(rows),
        "unit_type_counts": dict(Counter(row["CandidateUnitType"] for row in rows)),
        "output": str(output),
        "best_path_and_all_dictionary_alignments_are_reported_separately": True,
        "unknown_or_ambiguous_entries_remain_unconfirmed": True,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    """Profile current proposals into a new output path without editing source data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (root / args.output).resolve()
    print(json.dumps(profile(root, output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
