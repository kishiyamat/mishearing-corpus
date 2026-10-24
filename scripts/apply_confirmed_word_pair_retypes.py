"""Apply the individually adjudicated, span-preserving word retypes."""

from __future__ import annotations

import csv
import json
from pathlib import Path

TARGET_IDS = {
    "AcrugLVnrLE_005",
    "AcrugLVnrLE_012",
    "AcrugLVnrLE_013",
    "AcrugLVnrLE_020",
    "AcrugLVnrLE_023",
    "africa_atlas_callcenter_001",
    "posfie_OOEDO4_008",
    "taxi_media_20250516_019",
    "taxi_media_20250516_020",
    "taxi_media_20250516_021",
    "taxi_media_20250516_022",
    "taxidriver_12777586_001",
    "tenshokudou_11188_002",
    "tenshokudou_11188_003",
    "tenshokudou_11188_005",
    "tenshokudou_11188_007",
    "tenshokudou_11188_008",
    "tenshokudou_11188_009",
    "tenshokudou_11188_011",
    "tenshokudou_11188_012",
    "tenshokudou_11188_014",
    "tenshokudou_11188_016",
    "togetter_1209435_007",
    "togetter_193527_004",
    "wink_audibility_001",
}
AUDIT_DIR = Path("docs/reviews/2026-10-24-word-extraction")
REVIEW_PATH = Path("data/annotations/reviews.csv")
AUDIT_PATH = AUDIT_DIR / "pair-level-audit.csv"


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


def main() -> None:
    review_fields, reviews = read_csv(REVIEW_PATH)
    audit_fields, audit = read_csv(AUDIT_PATH)
    review_by_id = {row["MishearID"]: row for row in reviews}
    audit_by_id = {row["MishearID"]: row for row in audit}
    missing = TARGET_IDS - review_by_id.keys()
    missing_audit = TARGET_IDS - audit_by_id.keys()
    if missing or missing_audit:
        raise ValueError(
            f"target rows missing: review={missing}, audit={missing_audit}"
        )

    for mishear_id in TARGET_IDS:
        review = review_by_id[mishear_id]
        audit_row = audit_by_id[mishear_id]
        spans = json.loads(review["PairSpans"])
        span_matches = [
            span
            for span in spans
            if (
                span["src_start"],
                span["src_end"],
                span["tgt_start"],
                span["tgt_end"],
            )
            == (
                int(audit_row["OldSrcStart"]),
                int(audit_row["OldSrcEnd"]),
                int(audit_row["OldTgtStart"]),
                int(audit_row["OldTgtEnd"]),
            )
        ]
        if len(span_matches) != 1:
            raise ValueError(f"expected one audited pair span for {mishear_id}")
        span = span_matches[0]
        if span["unit_type"] not in {"phrase", "compound", "word"}:
            raise ValueError(f"unexpected old UnitType for {mishear_id}")
        if audit_row["OldEvidence"].find("IPADIC") < 0:
            raise ValueError(f"missing dictionary evidence for {mishear_id}")
        if not audit_row["PairID"]:
            raise ValueError(f"missing current PairID for {mishear_id}")
        if span["PairID"] and span["PairID"] != audit_row["PairID"]:
            raise ValueError(f"PairID mismatch for {mishear_id}")

        if span["unit_type"] != "word":
            span["unit_type"] = "word"
            span["PairID"] = audit_row["PairID"]
            review["PairSpans"] = json.dumps(
                spans, ensure_ascii=False, separators=(",", ":")
            )
            review["Reviewer"] = "agent:gpt-6-sol"
            review["ReviewedAt"] = "2026-10-24"
            review["Reason"] = (
                review["Reason"].rstrip()
                + " UnitType reclassified as word after individual review: both selected full-surface IPADIC entries are self-contained lexical units in this comparison; spans and readings are unchanged."
            )

        audit_row.update(
            ProposedSrcStart=audit_row["OldSrcStart"],
            ProposedSrcEnd=audit_row["OldSrcEnd"],
            ProposedTgtStart=audit_row["OldTgtStart"],
            ProposedTgtEnd=audit_row["OldTgtEnd"],
            ProposedSrcSurface=audit_row["OldSrcSurface"],
            ProposedTgtSurface=audit_row["OldTgtSurface"],
            ProposedUnitType="word",
            DecisionClass="RETYPE_VERIFIED",
            DecisionBasis=(
                "Sol individually confirmed exact whole-surface IPADIC entries and contextual readings; comparison is self-contained lexical units"
            ),
            HoldReason="",
            Reviewer="agent:gpt-6-sol",
            EvidenceChecked="yes; exact whole-surface IPADIC entry in OldEvidence",
            SourceLocationChecked="yes; source row/location in OldEvidence",
            LineageAction="existing PairID retained; same spans/readings; UnitType-only correction",
        )

    if {r["MishearID"] for r in reviews if r["TargetDecision"] == "include"} != {
        r["MishearID"] for r in audit
    }:
        raise ValueError("audit rows no longer match included reviews")
    write_csv(REVIEW_PATH, review_fields, reviews)
    write_csv(AUDIT_PATH, audit_fields, audit)
    manifest_path = AUDIT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    class_counts: dict[str, int] = {}
    for row in audit:
        class_counts[row["DecisionClass"]] = (
            class_counts.get(row["DecisionClass"], 0) + 1
        )
    manifest["decision_class_counts"] = class_counts
    manifest["individually_adjudicated_batch"] = {
        "decision_class": "RETYPE_VERIFIED",
        "reviewer": "agent:gpt-6-sol",
        "pair_count": len(TARGET_IDS),
        "scope": "same spans and readings; UnitType-only corrections",
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"retyped {len(TARGET_IDS)} individually adjudicated pairs as word")


if __name__ == "__main__":
    main()
