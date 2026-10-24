"""Join the immutable pair baseline to current selected pairs and Sol decisions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8-SIG CSV as dictionaries."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write the deterministic integrated audit."""
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pair(row: dict[str, str]) -> dict[str, str]:
    return {
        "PairID": row["PairID"],
        "MishearID": row["MishearID"],
        "OriginalHash": row["OriginalHash"],
        "SrcStart": row["SrcStart"],
        "SrcEnd": row["SrcEnd"],
        "TgtStart": row["TgtStart"],
        "TgtEnd": row["TgtEnd"],
        "Src": row["Src"],
        "Tgt": row["Tgt"],
        "SrcReading": row["SrcReading"],
        "TgtReading": row["TgtReading"],
        "UnitType": row["UnitType"],
    }


def build(root: Path, run_dir: Path) -> list[dict[str, Any]]:
    """Assert exact lineage coverage and return one audit row per baseline PairID."""
    audit_root = root / "docs/reviews/2026-10-24-word-extraction"
    baseline = read_csv(audit_root / "pair-level-audit.csv")
    current = read_csv(run_dir / "reviewed.csv")
    by_current: dict[str, dict[str, str]] = {}
    for row in current:
        if row["TargetDecision"] != "include":
            continue
        pair_id = row["PairID"]
        if not pair_id or pair_id in by_current:
            raise ValueError("current included PairID is empty or duplicated")
        by_current[pair_id] = row

    edges: dict[str, set[str]] = defaultdict(set)
    direct_events: dict[str, list[tuple[str, dict[str, str]]]] = defaultdict(list)
    for path in sorted(audit_root.glob("*/word-pair-decisions-audit.csv")):
        batch = path.parent.name
        for event in read_csv(path):
            old_id, new_id = event.get("OldPairID", ""), event.get("NewPairID", "")
            if not old_id or not new_id:
                continue
            direct_events[old_id].append((batch, event))
            if old_id != new_id:
                edges[old_id].add(new_id)

    decision: dict[str, dict[str, str]] = {}
    sol_path = audit_root / "remaining-span-sol-decisions.json"
    if sol_path.exists():
        sol = json.loads(sol_path.read_text(encoding="utf-8"))
        for item in sol["effective_type_overlay"]["items"]:
            decision[item["PairID"]] = {
                "class": item["effective_decision_class"],
                "basis": "remaining-span-sol-decisions.json/effective_type_overlay",
                "reason": item.get("reason", ""),
                "reviewer": "agent:gpt-6-sol",
            }
        for key in (
            "decisions",
            "exceptions",
            "keeps",
            "remaining_word_judgments",
            "remaining_phrase_compound_judgments",
            "additional_verified_overrides",
            "split_verified_overrides",
            "dictionary_verified_overrides",
            "component_verified_overrides",
            "manual_verified_overrides",
            "source_compound_verified_overrides",
            "reading_review_keep_overrides",
            "contextual_candidate_keep_overrides",
            "split_exception_override",
        ):
            items = sol.get(key, [])
            if isinstance(items, dict):
                items = [items]
            for item in items:
                pair_id = item.get("PairID") or item.get("old_pair_id")
                if not pair_id:
                    continue
                decision.setdefault(
                    pair_id,
                    {
                        "class": item.get("decision_class", "REVIEWED_KEEP"),
                        "basis": f"remaining-span-sol-decisions.json/{key}",
                        "reason": item.get("reason", ""),
                        "reviewer": "agent:gpt-6-sol",
                    },
                )

    pos_path = audit_root / "sol-pos-risk-297/lexical-pos-risk-sol-decisions.json"
    if pos_path.exists():
        for item in json.loads(pos_path.read_text(encoding="utf-8"))["items"]:
            decision[item["PairID"]] = {
                "class": item["decision_class"],
                "basis": "sol-pos-risk-297/lexical-pos-risk-sol-decisions.json",
                "reason": item["reason"],
                "reviewer": "agent:gpt-6-sol",
            }
    compound_path = audit_root / "same-span-compound-sol-decisions.json"
    if compound_path.exists():
        for item in json.loads(compound_path.read_text(encoding="utf-8"))["items"]:
            decision[item["PairID"]] = {
                "class": item["decision"],
                "basis": "same-span-compound-sol-decisions.json",
                "reason": item["reason"],
                "reviewer": "agent:gpt-6-sol",
            }

    uncovered_lexical_path = (
        audit_root / "sol-uncovered-lexical-1643/uncovered-lexical-sol-decisions.json"
    )
    if uncovered_lexical_path.exists():
        for item in json.loads(uncovered_lexical_path.read_text(encoding="utf-8"))[
            "items"
        ]:
            decision[item["OldPairID"]] = {
                "class": item["decision_class"],
                "basis": "sol-uncovered-lexical-1643/uncovered-lexical-sol-decisions.json/"
                + item["decision_mode"],
                "reason": item["reason"],
                "reviewer": "agent:gpt-6-sol",
            }

    uncovered_phrase_path = (
        audit_root / "sol-uncovered-phrases-1249/uncovered-phrases-sol-decisions.json"
    )
    if uncovered_phrase_path.exists():
        phrase_table = json.loads(uncovered_phrase_path.read_text(encoding="utf-8"))
        for item in phrase_table["items"]:
            pair_id = item["OldPairID"]
            classification = item["decision"]
            if classification in {"KEEP_CONTEXTUAL", "RETYPE", "MANUAL_RETYPE"}:
                decision_class = (
                    "KEEP_CONTEXTUAL"
                    if classification == "KEEP_CONTEXTUAL"
                    else "REVIEWED_KEEP"
                )
            else:
                # Boundary/type changes are registered by actual batch lineage
                # below; this fallback still prevents an unadjudicated label.
                decision_class = "REVIEWED_KEEP"
            decision.setdefault(
                pair_id,
                {
                    "class": decision_class,
                    "basis": "sol-uncovered-phrases-1249/uncovered-phrases-sol-decisions.json/"
                    + classification,
                    "reason": item.get("basis", item.get("reason", "")),
                    "reviewer": "agent:gpt-6-sol",
                },
            )

    phrase_correction_path = (
        audit_root / "niftykids-phrase-correction-1/sol-correction-override.json"
    )
    if phrase_correction_path.exists():
        correction = json.loads(phrase_correction_path.read_text(encoding="utf-8"))
        for item in correction.get("items", []):
            decision[item["OldPairID"]] = {
                "class": "KEEP_CONTEXTUAL",
                "basis": "niftykids-phrase-correction-1/sol-correction-override.json",
                "reason": item["basis"],
                "reviewer": "agent:gpt-6-sol",
            }

    baseline_ids = [row["PairID"] for row in baseline]
    if len(baseline_ids) != 4315 or len(set(baseline_ids)) != len(baseline_ids):
        raise ValueError("baseline does not contain 4,315 unique PairIDs")
    descendants: dict[str, set[str]] = {}
    for item in baseline:
        start = item["PairID"]
        seen, stack = {start}, [start]
        while stack:
            old_id = stack.pop()
            for new_id in edges.get(old_id, ()):
                if new_id not in seen:
                    seen.add(new_id)
                    stack.append(new_id)
        endpoints = seen.intersection(by_current)
        if not endpoints:
            raise ValueError(f"baseline PairID has no current descendant: {start}")
        for endpoint in endpoints:
            row = by_current[endpoint]
            if (
                row["MishearID"] != item["MishearID"]
                or row["OriginalHash"] != item["OriginalHash"]
            ):
                raise ValueError(f"cross-record or hash-mismatched lineage: {start}")
        descendants[start] = endpoints

    referenced = set().union(*descendants.values()) if descendants else set()
    if referenced != set(by_current):
        raise ValueError("current selected pairs include orphan or unmapped PairIDs")

    output: list[dict[str, Any]] = []
    for item in baseline:
        old_id = item["PairID"]
        current_endpoint_ids = sorted(descendants[old_id])
        pairs = [_pair(by_current[endpoint]) for endpoint in current_endpoint_ids]
        events = direct_events.get(old_id, [])
        judgement = decision.get(old_id)
        old_bounds = tuple(
            item[key]
            for key in ("OldSrcStart", "OldSrcEnd", "OldTgtStart", "OldTgtEnd")
        )
        new_bounds = {
            (
                pair["SrcStart"],
                pair["SrcEnd"],
                pair["TgtStart"],
                pair["TgtEnd"],
            )
            for pair in pairs
        }
        new_types = {pair["UnitType"] for pair in pairs}
        if len(current_endpoint_ids) > 1:
            action = "SPLIT_LINEAGE"
        elif next(iter(new_bounds)) != old_bounds:
            action = "BOUNDARY_CHANGED"
        elif new_types != {item["OldUnitType"]}:
            action = "UNIT_TYPE_CHANGED"
        elif events:
            action = "REVIEWED_SAME_SPAN_OR_METADATA"
        else:
            action = "RETAINED"

        if (
            judgement is not None
            and judgement["basis"]
            == "niftykids-phrase-correction-1/sol-correction-override.json"
        ):
            classification = judgement["class"]
            basis = judgement["basis"]
            reason = judgement["reason"]
            reviewer = judgement["reviewer"]
        elif events:
            classes = sorted({batch for batch, _ in events})
            classification = "APPLIED_REVIEWED_CHANGE"
            basis = ";".join(classes)
            reason = " | ".join(
                dict.fromkeys(
                    event.get("Reason", "")
                    for _, event in events
                    if event.get("Reason")
                )
            )
            reviewer = "agent:gpt-6-sol"
        elif judgement is not None:
            classification = judgement["class"]
            basis = judgement["basis"]
            reason = judgement["reason"]
            reviewer = judgement["reviewer"]
        elif item["DecisionClass"] in {"AUTO_WORD_RETYPE", "RETYPE_VERIFIED"}:
            classification = item["DecisionClass"]
            basis = item["DecisionBasis"]
            reason = item["DecisionBasis"]
            reviewer = item["Reviewer"]
        else:
            classification = "RESEARCH_REQUIRED"
            basis = "no matching applied batch or explicit saved judgment table"
            reason = (
                item["HoldReason"]
                or "No explicit disposition was found in the saved audit inputs."
            )
            reviewer = ""

        output.append(
            {
                "MishearID": item["MishearID"],
                "OriginalHash": item["OriginalHash"],
                "OldPairID": old_id,
                "OldSrcStart": item["OldSrcStart"],
                "OldSrcEnd": item["OldSrcEnd"],
                "OldTgtStart": item["OldTgtStart"],
                "OldTgtEnd": item["OldTgtEnd"],
                "OldSrc": item["OldSrcSurface"],
                "OldTgt": item["OldTgtSurface"],
                "OldUnitType": item["OldUnitType"],
                "CurrentPairIDs": _json(current_endpoint_ids),
                "CurrentPairs": _json(pairs),
                "LineageAction": action,
                "DecisionClass": classification,
                "DecisionBasis": basis,
                "ReasonOrHold": reason,
                "Reviewer": reviewer,
                "EvidenceChecked": "yes"
                if events or judgement
                else item["EvidenceChecked"],
                "SourceLocationChecked": item["SourceLocationChecked"],
            }
        )
    return output


def main() -> None:
    """Build the integrated audit from baseline, current run, and saved judgments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.run if args.run.is_absolute() else args.root / args.run
    output = args.output if args.output.is_absolute() else args.root / args.output
    rows = build(args.root, run)
    write_csv(output, rows)
    from collections import Counter

    print(
        json.dumps(
            Counter(row["DecisionClass"] for row in rows),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
