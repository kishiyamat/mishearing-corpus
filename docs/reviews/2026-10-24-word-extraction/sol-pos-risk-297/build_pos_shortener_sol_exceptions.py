"""Record individual Sol adjudications of strict-gate-shortener failures."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/kishi/.codex/worktrees/ca66/mishearing-corpus/corpus")
AUDIT = ROOT / "docs/reviews/2026-10-24-word-extraction/pair-level-audit.csv"
GATES = (
    ROOT
    / "docs/reviews/2026-10-24-word-extraction/pos-shortener-verified-1/gate-rejections.json"
)
DECISIONS = (
    ROOT
    / "docs/reviews/2026-10-24-word-extraction/sol-pos-risk-297/lexical-pos-risk-sol-decisions.json"
)
OUT = Path("/tmp/pos-shortener-sol-exceptions-48.json")

# Individual readings justified by the cited old review Evidence/source excerpt.
# Each is a selected contextual reading, not a claim about an unavailable recording.
SEGMENT_READINGS = {
    17: ("トカ", "トカ"),
    18: ("キョウドウ", "キョウドウ"),
    19: ("ウンコウ", "ウンコウ"),
    20: ("サイシュウザイ", "サイシュウザイ"),
    23: ("ソジョウ", "ソジョウ"),
    62: ("チョウシュ", "チョウシュ"),
    63: ("トウカイヒョウ", "トウカイチホウ"),
    65: ("トウリトウリャク", "トオリイチヘン"),
}
# Semantic/reference glosses and phonetic alternatives must remain in side-specific
# qualifiers/Evidence; they are not spoken surface residuals.
REFERENT_CRITICAL = {4, 7, 74, 134, 146, 190, 200, 211, 212, 221, 222, 267}
COMPOUND_RETYPE = {20, 63}


def residual(old, new):
    before, found, after = old.partition(new)
    assert found
    return before, after


def main():
    old = {
        r["MishearID"]: r
        for r in csv.DictReader(AUDIT.open(encoding="utf-8-sig", newline=""))
    }
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    by_id = {i["MishearID"]: i for i in decisions["items"]}
    gate = json.loads(GATES.read_text(encoding="utf-8"))
    records = []
    for held in gate["held_records"]:
        mid = held["MishearID"]
        p, a = by_id[mid], old[mid]
        index = p["index"]
        assert p["decision_class"] == "SHORTEN"
        n = dict(p["new"])
        src_res = residual(p["old"]["src"], n["src"])
        tgt_res = residual(p["old"]["tgt"], n["tgt"])
        if held["gate"] == "residual_context_mismatch":
            assert src_res[0] + src_res[1] + tgt_res[0] + tgt_res[1]
            assert all(
                not (b + e)
                or ((b + e).startswith(("（", "(")) and (b + e).endswith(("）", ")")))
                for b, e in (src_res, tgt_res)
            )
            new_readings = (a["OldSrcReading"], a["OldTgtReading"])
            assert new_readings[0] and new_readings[1]
            reason = (
                "The only unmatched material is the literal source parenthetical shown "
                "in residual_before_after; the old selected reading already names the "
                "shortened whole spoken lexical surface. Side-specific parenthetical "
                "reading, sense, or referent notes must be preserved as qualifiers and "
                "immutable original/source Evidence, not imported into spoken PairSpan. "
                "Thus exact residual equality is inapplicable to this source notation."
            )
            if index in REFERENT_CRITICAL:
                reason += " The parenthetical distinction is meaning/reference-critical and must not be discarded."
        else:
            assert index in SEGMENT_READINGS, (index, held["gate"])
            new_readings = SEGMENT_READINGS[index]
            reason = (
                "The saved primary excerpt and old review Evidence explicitly identify "
                "the contrasted lexical base and its reading. The old full reading splits "
                "at the shared inflection, particle, enumeration, or silent punctuation "
                "shown in the original surfaces. This independently resolves the strict "
                "dictionary best-path/token-boundary/nonunique-alignment gate; do not "
                "generalize this exception to other records."
            )
        assert a["OldSrcReading"].startswith(new_readings[0])
        assert a["OldTgtReading"].startswith(new_readings[1])
        n.update(
            {
                "unit_type": "compound"
                if index in COMPOUND_RETYPE
                else p["target_unit_type"],
                "src_reading": new_readings[0],
                "tgt_reading": new_readings[1],
            }
        )
        records.append(
            {
                "index": index,
                "MishearID": mid,
                "OldPairID": p["PairID"],
                "OriginalHash": p["OriginalHash"],
                "gate": held["gate"],
                "old": p["old"],
                "old_review_readings": p["old_review_readings"],
                "new": n,
                "residual_before_after": {"src": list(src_res), "tgt": list(tgt_res)},
                "source_file": a["SourceFile"],
                "source_url": a["URL"],
                "source_evidence": a["OldEvidence"],
                "prior_review_reason": a["OldReason"],
                "exception_reason": reason,
                "annotation_rule": (
                    "Retain side-specific meanings and qualifiers from current reviewed annotations; "
                    "move selected annotation bounds to the short lexical surface, retaining the "
                    "specific reading above. Keep raw originals and prior Evidence immutable; "
                    "append this source-backed decision and preserve old-PairID lineage."
                ),
                "status": "agent-sol-individual-exception-approved; engine/full-record validation required",
            }
        )
    assert len(records) == 48
    assert len({r["OldPairID"] for r in records}) == 48
    payload = {
        "schema": "pos-shortener-sol-exceptions/v1",
        "reviewer": "agent:gpt-6-sol",
        "source_audit_sha256": hashlib.sha256(AUDIT.read_bytes()).hexdigest(),
        "parent_decisions_sha256": hashlib.sha256(DECISIONS.read_bytes()).hexdigest(),
        "gate_rejections_sha256": hashlib.sha256(GATES.read_bytes()).hexdigest(),
        "gate_run_input_review_sha256": gate["input_review_sha256"],
        "counts": {
            "approved_individual_exceptions": len(records),
            "parenthetical_source_notation": sum(
                r["gate"] == "residual_context_mismatch" for r in records
            ),
            "source_reading_segmentation": sum(
                r["gate"] != "residual_context_mismatch" for r in records
            ),
        },
        "policy": (
            "This is a finite source-backed decision set, not a relaxed automatic gate. "
            "Do not mark source audio verified; preserve current uncertainty qualifiers."
        ),
        "records": records,
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(payload["counts"])
    print(OUT)


if __name__ == "__main__":
    main()
