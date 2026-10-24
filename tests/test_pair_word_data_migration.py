"""Regression checks for evidence-gated, idempotent word-pair migrations."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

from corpus_api.models import CSV_FIELDS
from corpus_api.pair_workflow import original_hash

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/apply_auto_word_pair_retypes.py"
_SPEC = importlib.util.spec_from_file_location("auto_word_pair_retypes", SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
MIGRATOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MIGRATOR)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _fixture(tmp_path: Path, *, readings_match: bool = True) -> tuple[Path, Path, Path]:
    root = tmp_path / "repo"
    review_path = root / "data/annotations/reviews.csv"
    audit_dir = root / "docs/reviews/2026-10-24-word-extraction"
    audit_path = audit_dir / "pair-level-audit.csv"
    dict_path = audit_dir / "dictionary-evidence.jsonl"
    source = {field: "" for field in CSV_FIELDS} | {
        "MishearID": "example_001",
        "Src": "高地",
        "Tgt": "高知",
        "Language": "ja",
    }
    digest = original_hash(source)
    pair_id = "c7826088-676c-5f03-a3da-a59a03ba52c6"
    review = {
        "MishearID": "example_001",
        "OriginalHash": digest,
        "Status": "reviewed",
        "TargetDecision": "include",
        "Reviewer": "agent:gpt-6-sol",
        "ReviewedAt": "2026-10-24",
        "Evidence": "Source row example_001; exact readings are independently confirmed.",
        "Reason": "The selected comparison is included.",
        "SrcAnnotations": json.dumps(
            [
                {
                    "start": 0,
                    "end": 2,
                    "surface": "高地",
                    "reading": "コウチ",
                    "meanings": [],
                    "qualifiers": [],
                }
            ],
            ensure_ascii=False,
        ),
        "TgtAnnotations": json.dumps(
            [
                {
                    "start": 0,
                    "end": 2,
                    "surface": "高知",
                    "reading": "コウチ",
                    "meanings": [],
                    "qualifiers": [],
                }
            ],
            ensure_ascii=False,
        ),
        "PairSpans": json.dumps(
            [
                {
                    "PairID": "",
                    "SupersedesPairID": "",
                    "src_start": 0,
                    "src_end": 2,
                    "tgt_start": 0,
                    "tgt_end": 2,
                    "unit_type": "phrase",
                }
            ]
        ),
    }
    review_fields = list(review)
    _write_csv(review_path, review_fields, [review])
    _write_csv(root / "data/mishearing/source.csv", list(CSV_FIELDS), [source])

    audit = {
        "MishearID": "example_001",
        "PairID": pair_id,
        "SupersedesPairID": "",
        "OriginalHash": digest,
        "OldSrcStart": "0",
        "OldSrcEnd": "2",
        "OldTgtStart": "0",
        "OldTgtEnd": "2",
        "OldSrcSurface": "高地",
        "OldTgtSurface": "高知",
        "OldSrcReading": "コウチ",
        "OldTgtReading": "コウチ",
        "OldUnitType": "phrase",
        "AnnotationSpanFit": "src:exact_range_surface_match;tgt:exact_range_surface_match",
        "SameSpanProposals": json.dumps(
            [
                {
                    "src_start": 0,
                    "src_end": 2,
                    "tgt_start": 0,
                    "tgt_end": 2,
                    "unit_type": "word",
                }
            ]
        ),
        "DecisionClass": "RESEARCH_REQUIRED",
        "ProposedSrcStart": "",
        "ProposedSrcEnd": "",
        "ProposedTgtStart": "",
        "ProposedTgtEnd": "",
        "ProposedSrcSurface": "",
        "ProposedTgtSurface": "",
        "ProposedUnitType": "",
        "DecisionBasis": "",
        "HoldReason": "",
        "Reviewer": "automated-profile",
        "EvidenceChecked": "no",
        "SourceLocationChecked": "no",
        "LineageAction": "undetermined",
    }
    _write_csv(audit_path, list(audit), [audit])
    dictionary_sha = "c8e456c6a753a7960b4bfab6a4264f78038abe9c5ba885b6e40593557d1c56ba"
    entries = []
    for surface, reading in (("高地", "コウチ"), ("高知", "コウチ")):
        entries.append(
            json.dumps(
                {
                    "surface": surface,
                    "dictionary_info": "IPADIC test fixture",
                    "dictionary_sha256": dictionary_sha,
                    "entries": [
                        {
                            "surface": surface,
                            "reading": reading
                            if readings_match or surface == "高地"
                            else "タカチ",
                            "features": [
                                "名詞",
                                "固有名詞",
                                "地域",
                                "一般",
                                "*",
                                "*",
                                "*",
                                reading,
                                reading,
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )
    dict_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
    (audit_dir / "manifest.json").write_text(
        json.dumps(
            {"decision_class_counts": {"RESEARCH_REQUIRED": 1}}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    return root, review_path, audit_path


def _run(root: Path) -> None:
    MIGRATOR.ROOT = root
    MIGRATOR.AUDIT_DIR = root / "docs/reviews/2026-10-24-word-extraction"
    MIGRATOR.REVIEW_PATH = root / "data/annotations/reviews.csv"
    MIGRATOR.AUDIT_PATH = MIGRATOR.AUDIT_DIR / "pair-level-audit.csv"
    MIGRATOR.DICT_PATH = MIGRATOR.AUDIT_DIR / "dictionary-evidence.jsonl"
    MIGRATOR.main()


def test_auto_retype_persists_span_unit_and_pair_id(tmp_path: Path) -> None:
    root, review_path, audit_path = _fixture(tmp_path)

    _run(root)

    with review_path.open(encoding="utf-8", newline="") as stream:
        review = next(csv.DictReader(stream))
    span = json.loads(review["PairSpans"])[0]
    assert span["unit_type"] == "word"
    assert span["PairID"] == "c7826088-676c-5f03-a3da-a59a03ba52c6"
    assert review["TargetDecision"] == "include"
    assert "AUTO_WORD_RETYPE" in review["Reason"]
    assert "dictionary SHA256" in review["Evidence"]
    with audit_path.open(encoding="utf-8", newline="") as stream:
        audit = next(csv.DictReader(stream))
    assert audit["DecisionClass"] == "AUTO_WORD_RETYPE"
    assert json.loads(audit["AutoRuleConditions"])["original_hash_matches"] is True
    assert json.loads(audit["SrcDictionaryMatch"])[0]["reading"] == "コウチ"


def test_ineligible_dictionary_reading_does_not_change_review(tmp_path: Path) -> None:
    root, review_path, audit_path = _fixture(tmp_path, readings_match=False)
    before = review_path.read_bytes()

    _run(root)

    assert review_path.read_bytes() == before
    with audit_path.open(encoding="utf-8", newline="") as stream:
        audit = next(csv.DictReader(stream))
    assert audit["DecisionClass"] == "RESEARCH_REQUIRED"
    conditions = json.loads(audit["AutoRuleConditions"])
    assert conditions["annotation_readings_match_pair_and_dictionary"] is False


def test_reapplying_auto_migration_is_idempotent(tmp_path: Path) -> None:
    root, review_path, audit_path = _fixture(tmp_path)
    _run(root)
    first = (
        review_path.read_bytes(),
        audit_path.read_bytes(),
        (MIGRATOR.AUDIT_DIR / "manifest.json").read_bytes(),
    )

    _run(root)

    second = (
        review_path.read_bytes(),
        audit_path.read_bytes(),
        (MIGRATOR.AUDIT_DIR / "manifest.json").read_bytes(),
    )
    assert second == first
