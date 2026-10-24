"""Apply only the mechanically evidenced, span-preserving AUTO_WORD_RETYPE rows."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from corpus_api.dictionary import DictionaryEntry
from corpus_api.pair_workflow import original_hash

ROOT = Path.cwd()
AUDIT_DIR = ROOT / "docs/reviews/2026-10-24-word-extraction"
REVIEW_PATH = ROOT / "data/annotations/reviews.csv"
AUDIT_PATH = AUDIT_DIR / "pair-level-audit.csv"
DICT_PATH = AUDIT_DIR / "dictionary-evidence.jsonl"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"missing CSV header: {path}")
        return list(reader.fieldnames), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def reading_key(reading: str) -> str:
    return "".join(
        chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char
        for char in unicodedata.normalize("NFKC", reading)
    )


def eligible_entry(entry: DictionaryEntry, reading: str) -> bool:
    features = entry["features"]
    part_of_speech = features[0]
    if part_of_speech not in {"名詞", "動詞", "形容詞", "副詞", "連体詞", "感動詞"}:
        return False
    if (
        part_of_speech == "名詞"
        and len(features) > 1
        and features[1] in {"接尾", "接頭", "非自立"}
    ):
        return False
    return reading_key(str(entry["reading"])) == reading_key(reading)


def source_rows() -> dict[str, tuple[str, dict[str, str]]]:
    result: dict[str, tuple[str, dict[str, str]]] = {}
    for path in sorted((ROOT / "data/mishearing").rglob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                result[row["MishearID"]] = (path.relative_to(ROOT).as_posix(), row)
    return result


def main() -> None:
    review_fields, reviews = read_csv(REVIEW_PATH)
    audit_fields, audits = read_csv(AUDIT_PATH)
    dictionary = {
        row["surface"]: row for row in map(json.loads, DICT_PATH.open(encoding="utf-8"))
    }
    originals = source_rows()
    review_by_id = {row["MishearID"]: row for row in reviews}
    audit_by_pair_id = {row["PairID"]: row for row in audits}
    if len(audit_by_pair_id) != len(audits):
        raise ValueError("duplicate PairID in the baseline audit ledger")

    evidence_columns = {
        "AutoRuleConditions",
        "SrcDictionaryMatch",
        "TgtDictionaryMatch",
        "DictionarySHA256",
    }
    for column in evidence_columns:
        if column not in audit_fields:
            audit_fields.append(column)
            for row in audits:
                row[column] = ""

    changed = 0
    skipped: Counter[str] = Counter()
    changed_ids: list[str] = []
    for audit in audits:
        if audit["DecisionClass"] != "RESEARCH_REQUIRED":
            continue
        mishear_id = audit["MishearID"]
        review = review_by_id[mishear_id]
        source_path, source = originals[mishear_id]
        if review["Status"] != "reviewed" or review["TargetDecision"] != "include":
            raise ValueError(f"unexpected current decision for {mishear_id}")
        if review["OriginalHash"] != audit["OriginalHash"]:
            raise ValueError(f"baseline annotation hash mismatch for {mishear_id}")
        if original_hash(source) != audit["OriginalHash"]:
            raise ValueError(f"original source hash mismatch for {mishear_id}")
        spans = json.loads(review["PairSpans"])
        span = next(
            (
                row
                for row in spans
                if row.get("PairID") == audit["PairID"]
                or (
                    int(row["src_start"]) == int(audit["OldSrcStart"])
                    and int(row["src_end"]) == int(audit["OldSrcEnd"])
                    and int(row["tgt_start"]) == int(audit["OldTgtStart"])
                    and int(row["tgt_end"]) == int(audit["OldTgtEnd"])
                    and row["unit_type"] == audit["OldUnitType"]
                )
            ),
            None,
        )
        if span is None:
            raise ValueError(f"baseline PairSpan not found for {audit['PairID']}")
        s0, s1 = int(span["src_start"]), int(span["src_end"])
        t0, t1 = int(span["tgt_start"]), int(span["tgt_end"])
        src_surface, tgt_surface = source["Src"][s0:s1], source["Tgt"][t0:t1]
        src_annotations = json.loads(review["SrcAnnotations"])
        tgt_annotations = json.loads(review["TgtAnnotations"])
        src_exact_annotations = [
            a
            for a in src_annotations
            if a["start"] == s0 and a["end"] == s1 and a["surface"] == src_surface
        ]
        tgt_exact_annotations = [
            a
            for a in tgt_annotations
            if a["start"] == t0 and a["end"] == t1 and a["surface"] == tgt_surface
        ]
        src_exact = bool(src_exact_annotations)
        tgt_exact = bool(tgt_exact_annotations)
        src_reading_matches = any(
            reading_key(a["reading"]) == reading_key(audit["OldSrcReading"])
            for a in src_exact_annotations
        )
        tgt_reading_matches = any(
            reading_key(a["reading"]) == reading_key(audit["OldTgtReading"])
            for a in tgt_exact_annotations
        )
        src_dictionary_sha = dictionary.get(src_surface, {}).get(
            "dictionary_sha256", ""
        )
        tgt_dictionary_sha = dictionary.get(tgt_surface, {}).get(
            "dictionary_sha256", ""
        )
        sha_matches = (
            bool(src_dictionary_sha) and src_dictionary_sha == tgt_dictionary_sha
        )
        same_span_word = any(
            p["unit_type"] == "word"
            and (p["src_start"], p["src_end"], p["tgt_start"], p["tgt_end"])
            == (s0, s1, t0, t1)
            for p in json.loads(audit["SameSpanProposals"])
        )
        src_dict = dictionary.get(src_surface, {}).get("entries", [])
        tgt_dict = dictionary.get(tgt_surface, {}).get("entries", [])
        src_matches = [e for e in src_dict if eligible_entry(e, audit["OldSrcReading"])]
        tgt_matches = [e for e in tgt_dict if eligible_entry(e, audit["OldTgtReading"])]
        conditions = {
            "full_span_annotation_and_surface_match": src_exact and tgt_exact,
            "annotation_readings_match_pair_and_dictionary": src_reading_matches
            and tgt_reading_matches
            and bool(src_matches)
            and bool(tgt_matches),
            "self_standing_parts_of_speech": bool(src_matches) and bool(tgt_matches),
            "extractor_selects_same_span_as_word": same_span_word,
            "original_hash_matches": original_hash(source) == audit["OriginalHash"],
            "dictionary_sha_matches_both_sides": sha_matches,
        }
        audit.update(
            AutoRuleConditions=json.dumps(
                conditions, ensure_ascii=False, sort_keys=True
            ),
            SrcDictionaryMatch=json.dumps(
                src_matches, ensure_ascii=False, separators=(",", ":")
            ),
            TgtDictionaryMatch=json.dumps(
                tgt_matches, ensure_ascii=False, separators=(",", ":")
            ),
            DictionarySHA256=(
                dictionary[src_surface]["dictionary_sha256"]
                if src_surface in dictionary
                else ""
            ),
        )
        if not all(conditions.values()):
            skipped["failed_rule_conditions"] += 1
            continue
        if span["unit_type"] == "word":
            skipped["already_word"] += 1
            continue

        span["unit_type"] = "word"
        span["PairID"] = audit["PairID"]
        review["PairSpans"] = json.dumps(
            spans, ensure_ascii=False, separators=(",", ":")
        )
        review["Reviewer"] = "rule + Sol approved"
        review["Reason"] = (
            review["Reason"].rstrip()
            + " UnitType reclassified as word under AUTO_WORD_RETYPE: the selected span is an independent whole-surface dictionary word on both sides, supported by exact matching readings; the extractor selects the same spans as word candidates."
        )
        for side, matches in (("Src", src_matches), ("Tgt", tgt_matches)):
            review["Evidence"] += (
                f" {side} exact IPADIC entry checked: "
                + json.dumps(matches, ensure_ascii=False, separators=(",", ":"))
                + f"; dictionary SHA256 {dictionary[src_surface if side == 'Src' else tgt_surface]['dictionary_sha256']}."
            )
        audit.update(
            ProposedSrcStart=str(s0),
            ProposedSrcEnd=str(s1),
            ProposedTgtStart=str(t0),
            ProposedTgtEnd=str(t1),
            ProposedSrcSurface=src_surface,
            ProposedTgtSurface=tgt_surface,
            ProposedUnitType="word",
            DecisionClass="AUTO_WORD_RETYPE",
            DecisionBasis="AUTO_WORD_RETYPE conditions verified against original review, source, extractor proposal, and installed IPADIC entries",
            HoldReason="",
            Reviewer="rule + Sol approved",
            EvidenceChecked="yes; exact reading-matched IPADIC entries and feature tuples recorded",
            SourceLocationChecked=f"yes; {source_path} row {mishear_id}",
            LineageAction="existing PairID retained; same spans/readings; UnitType-only correction",
        )
        changed += 1
        changed_ids.append(audit["PairID"])

    write_csv(REVIEW_PATH, review_fields, reviews)
    write_csv(AUDIT_PATH, audit_fields, audits)
    manifest_path = AUDIT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    class_counts = Counter(row["DecisionClass"] for row in audits)
    manifest["decision_class_counts"] = dict(class_counts)
    previous_auto = manifest.get("auto_word_retype", {})
    manifest["auto_word_retype"] = {
        "changed_pair_count": previous_auto.get("changed_pair_count", 0) + changed,
        "skipped_counts": previous_auto.get("skipped_counts", dict(skipped)),
        "pair_ids": list(
            dict.fromkeys(previous_auto.get("pair_ids", []) + changed_ids)
        ),
        "dictionary_evidence": DICT_PATH.name,
        "dictionary_evidence_sha256": hashlib.sha256(
            DICT_PATH.read_bytes()
        ).hexdigest(),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"AUTO_WORD_RETYPE updated {changed} pairs; skipped={dict(skipped)}")


if __name__ == "__main__":
    main()
