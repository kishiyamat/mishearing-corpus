"""Test-first contracts for guarded, lineage-preserving word-pair migrations."""

import csv
import hashlib
import io
import json

import pytest

from corpus_api.pair_workflow import (
    original_hash,
    review_csv,
    review_record,
)
from scripts.apply_word_pair_decisions import (
    apply_decisions,
    apply_patch_to_directory,
    rebuild_current_pair_rows,
)


def _raw_record() -> dict[str, str]:
    """Build the original row used by the migration contract fixture."""
    from corpus_api.models import CSV_FIELDS

    return dict.fromkeys(CSV_FIELDS, "") | {
        "MishearID": "example",
        "Src": "その人に幸福をもたらす",
        "Tgt": "その人に交付金をもたらす",
        "Language": "ja",
        "URL": "https://example.test/source",
    }


def _review(raw: dict[str, str]) -> dict[str, object]:
    """Build the existing full-range reviewed decision with grounded readings."""
    return {
        "MishearID": raw["MishearID"],
        "OriginalHash": original_hash(raw),
        "Reviewer": "researcher",
        "ReviewedAt": "2026-10-24",
        "Evidence": "Original paired example supplies both full readings.",
        "Reason": "Original annotation before lexical boundary correction.",
        "Status": "reviewed",
        "TargetDecision": "include",
        "RecordValidity": "documented",
        "SrcAnnotations": [
            {
                "start": 0,
                "end": len(raw["Src"]),
                "surface": raw["Src"],
                "reading": "ソノヒトニコウフクヲモタラス",
                "meanings": [],
                "qualifiers": [],
            }
        ],
        "TgtAnnotations": [
            {
                "start": 0,
                "end": len(raw["Tgt"]),
                "surface": raw["Tgt"],
                "reading": "ソノヒトニコウフキンヲモタラス",
                "meanings": [],
                "qualifiers": [],
            }
        ],
        "PairSpans": [
            {
                "src_start": 0,
                "src_end": len(raw["Src"]),
                "tgt_start": 0,
                "tgt_end": len(raw["Tgt"]),
                "unit_type": "phrase",
            }
        ],
    }


def _patch(
    raw: dict[str, str], review_payload: bytes, old_pair: dict[str, str]
) -> dict[str, object]:
    """Build a single-span-to-word patch with exact replacement annotations."""
    return {
        "schema_version": 1,
        "source_run": "fixture-run",
        "source_review_sha256": hashlib.sha256(review_payload).hexdigest(),
        "decisions": [
            {
                "MishearID": raw["MishearID"],
                "OriginalHash": original_hash(raw),
                "old_pairs": [
                    {
                        "PairID": old_pair["PairID"],
                        "src_start": int(old_pair["SrcStart"]),
                        "src_end": int(old_pair["SrcEnd"]),
                        "tgt_start": int(old_pair["TgtStart"]),
                        "tgt_end": int(old_pair["TgtEnd"]),
                        "unit_type": old_pair["UnitType"],
                    }
                ],
                "new_pair_spans": [
                    {
                        "src_start": 4,
                        "src_end": 6,
                        "tgt_start": 4,
                        "tgt_end": 7,
                        "unit_type": "word",
                        "PairID": "",
                        "SupersedesPairID": old_pair["PairID"],
                    }
                ],
                "SrcAnnotations": [
                    {
                        "start": 4,
                        "end": 6,
                        "surface": "幸福",
                        "reading": "コウフク",
                        "meanings": [],
                        "qualifiers": [],
                    }
                ],
                "TgtAnnotations": [
                    {
                        "start": 4,
                        "end": 7,
                        "surface": "交付金",
                        "reading": "コウフキン",
                        "meanings": [],
                        "qualifiers": [],
                    }
                ],
                "Evidence": "Source text and exact IPADIC entries confirm 幸福 and 交付金 readings.",
                "Reason": "Reviewed the minimal independent lexical contrast.",
                "Reviewer": "researcher",
                "ReviewedAt": "2026-10-24",
                "RecordValidity": "documented",
            }
        ],
    }


def _fixture() -> tuple[dict[str, str], bytes, list[dict[str, str]], dict[str, object]]:
    """Create source-bound old artifacts and one proposed migration patch."""
    raw = _raw_record()
    old_review = _review(raw)
    review_payload = review_csv([old_review])
    old_pairs, _ = review_record(raw, "data/mishearing/test.csv", old_review)
    patch = _patch(raw, review_payload, old_pairs[0])
    return raw, review_payload, old_pairs, patch


def test_apply_decision_preserves_inclusion_and_links_replacement_to_old_pair() -> None:
    """Shorten one pair, retain its old ID as lineage, and validate the whole review."""
    # Arrange
    raw, review_payload, old_pairs, patch = _fixture()

    # Act
    result = apply_decisions(
        review_payload,
        {raw["MishearID"]: (raw, "data/mishearing/test.csv")},
        old_pairs,
        patch,
        current_run="fixture-run",
    )

    # Assert
    new_reviews = list(
        csv.DictReader(io.StringIO(result.review_csv.decode("utf-8"), newline=""))
    )
    review = new_reviews[0]
    spans = json.loads(review["PairSpans"])
    assert review["Status"] == "reviewed"
    assert review["TargetDecision"] == "include"
    assert review["RecordValidity"] == "documented"
    assert len(spans) == 1
    assert (spans[0]["src_start"], spans[0]["src_end"]) == (4, 6)
    assert (spans[0]["tgt_start"], spans[0]["tgt_end"]) == (4, 7)
    assert spans[0]["SupersedesPairID"] == old_pairs[0]["PairID"]
    assert spans[0]["PairID"] != old_pairs[0]["PairID"]
    assert result.audit_rows[0]["OldPairID"] == old_pairs[0]["PairID"]
    assert result.audit_rows[0]["NewSrc"] == "幸福"
    assert result.audit_rows[0]["NewTgt"] == "交付金"
    assert result.audit_rows[0]["NewUnitType"] == "word"


def test_current_pair_rows_can_be_rebuilt_from_the_exact_review_payload() -> None:
    """Sequential patches use current reviewed decisions rather than a stale run."""
    # Arrange
    raw, review_payload, old_pairs, _ = _fixture()

    # Act
    current_rows = rebuild_current_pair_rows(
        review_payload,
        {raw["MishearID"]: (raw, "data/mishearing/test.csv")},
    )

    # Assert
    assert current_rows == old_pairs


def test_patch_can_preserve_previous_evidence_before_adding_boundary_evidence() -> None:
    """Keep prior citations and reading evidence when a boundary is revised."""
    # Arrange
    raw, _, old_pairs, patch = _fixture()
    original_review = _review(raw)
    original_review["Evidence"] = "Historical source citation and dictionary record."
    original_review["Reason"] = "Historical reading and interpretation rationale."
    review_payload = review_csv([original_review])
    patch["source_review_sha256"] = hashlib.sha256(review_payload).hexdigest()
    patch["decisions"][0]["old_pairs"] = [
        {
            "PairID": old_pairs[0]["PairID"],
            "src_start": int(old_pairs[0]["SrcStart"]),
            "src_end": int(old_pairs[0]["SrcEnd"]),
            "tgt_start": int(old_pairs[0]["TgtStart"]),
            "tgt_end": int(old_pairs[0]["TgtEnd"]),
            "unit_type": old_pairs[0]["UnitType"],
        }
    ]
    patch["preserve_previous_rationale"] = True
    current_rows, _ = review_record(raw, "data/mishearing/test.csv", original_review)

    # Act
    result = apply_decisions(
        review_payload,
        {raw["MishearID"]: (raw, "data/mishearing/test.csv")},
        current_rows,
        patch,
        current_run="fixture-run",
    )

    # Assert
    applied = next(
        row
        for row in csv.DictReader(
            io.StringIO(result.review_csv.decode("utf-8"), newline="")
        )
    )
    assert applied["Evidence"].startswith(
        "Historical rationale for superseded span/reading (retained verbatim):\n"
        "Historical source citation and dictionary record."
    )
    assert "Current boundary review evidence:" in applied["Evidence"]
    assert "Source text and exact IPADIC entries" in applied["Evidence"]
    assert "Historical rationale for superseded span/reading" in applied["Reason"]
    assert "Historical reading and interpretation rationale." in applied["Reason"]
    assert "Current boundary review rationale:" in applied["Reason"]
    assert "minimal independent lexical contrast" in applied["Reason"]


def test_split_children_both_reference_the_superseded_pair() -> None:
    """Two independent short contrasts retain explicit lineage to one old pair."""
    # Arrange
    raw = _raw_record() | {
        "MishearID": "multi-contrast",
        "Src": "欧州問題と回避姿勢",
        "Tgt": "欧州本体と回避性",
    }
    old_review = _review(raw)
    old_review["SrcAnnotations"] = [
        {
            "start": 0,
            "end": len(raw["Src"]),
            "surface": raw["Src"],
            "reading": "オウシュウモンダイトカイヒシセイ",
            "meanings": [],
            "qualifiers": [],
        }
    ]
    old_review["TgtAnnotations"] = [
        {
            "start": 0,
            "end": len(raw["Tgt"]),
            "surface": raw["Tgt"],
            "reading": "オウシュウホンタイトカイヒセイ",
            "meanings": [],
            "qualifiers": [],
        }
    ]
    old_payload = review_csv([old_review])
    old_rows, _ = review_record(raw, "test.csv", old_review)
    old_pair = old_rows[0]
    patch = {
        "schema_version": 1,
        "source_run": "fixture-run",
        "source_review_sha256": hashlib.sha256(old_payload).hexdigest(),
        "decisions": [
            {
                "MishearID": raw["MishearID"],
                "OriginalHash": original_hash(raw),
                "old_pairs": [
                    {
                        "PairID": old_pair["PairID"],
                        "src_start": 0,
                        "src_end": len(raw["Src"]),
                        "tgt_start": 0,
                        "tgt_end": len(raw["Tgt"]),
                        "unit_type": "phrase",
                    }
                ],
                "new_pair_spans": [
                    {
                        "src_start": 2,
                        "src_end": 4,
                        "tgt_start": 2,
                        "tgt_end": 4,
                        "unit_type": "word",
                        "SupersedesPairID": old_pair["PairID"],
                    },
                    {
                        "src_start": 5,
                        "src_end": 9,
                        "tgt_start": 5,
                        "tgt_end": 8,
                        "unit_type": "compound",
                        "SupersedesPairID": old_pair["PairID"],
                    },
                ],
                "SrcAnnotations": [
                    {"start": 2, "end": 4, "surface": "問題", "reading": "モンダイ"},
                    {
                        "start": 5,
                        "end": 9,
                        "surface": "回避姿勢",
                        "reading": "カイヒシセイ",
                    },
                ],
                "TgtAnnotations": [
                    {"start": 2, "end": 4, "surface": "本体", "reading": "ホンタイ"},
                    {
                        "start": 5,
                        "end": 8,
                        "surface": "回避性",
                        "reading": "カイヒセイ",
                    },
                ],
                "Evidence": "Original paired context and exact selected spans were checked.",
                "Reason": "Two independent contrasts are preserved separately.",
                "Reviewer": "researcher",
                "ReviewedAt": "2026-10-24",
                "RecordValidity": "documented",
            }
        ],
    }

    # Act
    result = apply_decisions(
        old_payload,
        {raw["MishearID"]: (raw, "test.csv")},
        old_rows,
        patch,
        current_run="fixture-run",
    )

    # Assert
    updated = next(
        row for row in csv.DictReader(io.StringIO(result.review_csv.decode()))
    )
    selected, _ = review_record(
        raw,
        "test.csv",
        {
            **updated,
            "SrcAnnotations": json.loads(updated["SrcAnnotations"]),
            "TgtAnnotations": json.loads(updated["TgtAnnotations"]),
            "PairSpans": json.loads(updated["PairSpans"]),
        },
    )
    assert [(row["Src"], row["Tgt"]) for row in selected] == [
        ("問題", "本体"),
        ("回避姿勢", "回避性"),
    ]
    assert {row["SupersedesPairID"] for row in selected} == {old_pair["PairID"]}
    assert len({row["PairID"] for row in selected}) == 2
    assert len(result.audit_rows) == 2


def test_same_boundary_unit_retype_preserves_manual_pair_id() -> None:
    """A taxonomy-only correction keeps PairID and previous ancestry unchanged."""
    # Arrange
    raw = _raw_record()
    old_review = _review(raw)
    old_review["SrcAnnotations"] = [
        {
            "start": 4,
            "end": 6,
            "surface": "幸福",
            "reading": "コウフク",
            "meanings": [],
            "qualifiers": [],
        }
    ]
    old_review["TgtAnnotations"] = [
        {
            "start": 4,
            "end": 7,
            "surface": "交付金",
            "reading": "コウフキン",
            "meanings": [],
            "qualifiers": [],
        }
    ]
    old_review["PairSpans"] = [
        {
            "src_start": 4,
            "src_end": 6,
            "tgt_start": 4,
            "tgt_end": 7,
            "unit_type": "phrase",
        }
    ]
    review_payload = review_csv([old_review])
    old_pairs, _ = review_record(raw, "data/mishearing/test.csv", old_review)
    old_pair = old_pairs[0]
    patch = _patch(raw, review_payload, old_pair)
    decision = patch["decisions"][0]
    assert isinstance(decision, dict)
    decision["new_pair_spans"] = [
        {
            "src_start": 4,
            "src_end": 6,
            "tgt_start": 4,
            "tgt_end": 7,
            "unit_type": "word",
        }
    ]

    # Act / Assert
    result = apply_decisions(
        review_payload,
        {raw["MishearID"]: (raw, "data/mishearing/test.csv")},
        old_pairs,
        patch,
        current_run="fixture-run",
    )
    updated = next(csv.DictReader(io.StringIO(result.review_csv.decode())))
    span = json.loads(updated["PairSpans"])[0]
    assert span["PairID"] == old_pair["PairID"]
    assert span["SupersedesPairID"] == old_pair["SupersedesPairID"]


@pytest.mark.parametrize("stale_field", ["OriginalHash", "PairID", "bounds"])
def test_stale_pair_or_original_fails_closed(stale_field: str) -> None:
    """Reject source changes, replaced IDs, or span drift before writing anything."""
    # Arrange
    raw, review_payload, old_pairs, patch = _fixture()
    decision = patch["decisions"][0]
    assert isinstance(decision, dict)
    if stale_field == "OriginalHash":
        decision["OriginalHash"] = "0" * 64
    elif stale_field == "PairID":
        decision["old_pairs"][0]["PairID"] = "00000000-0000-4000-8000-000000000000"
    else:
        decision["old_pairs"][0]["src_start"] += 1

    # Act / Assert
    with pytest.raises(ValueError):
        apply_decisions(
            review_payload,
            {raw["MishearID"]: (raw, "data/mishearing/test.csv")},
            old_pairs,
            patch,
            current_run="fixture-run",
        )


def test_patch_cannot_be_reapplied_after_review_hash_changes() -> None:
    """A successful patch makes its base hash stale, preventing duplicate children."""
    # Arrange
    raw, review_payload, old_pairs, patch = _fixture()
    inputs = {raw["MishearID"]: (raw, "data/mishearing/test.csv")}

    # Act
    result = apply_decisions(
        review_payload,
        inputs,
        old_pairs,
        patch,
        current_run="fixture-run",
    )
    current_new_reviews = list(csv.DictReader(io.StringIO(result.review_csv.decode())))
    new_review_decisions = [
        {
            **current_new_reviews[0],
            "SrcAnnotations": json.loads(current_new_reviews[0]["SrcAnnotations"]),
            "TgtAnnotations": json.loads(current_new_reviews[0]["TgtAnnotations"]),
            "PairSpans": json.loads(current_new_reviews[0]["PairSpans"]),
        }
    ]
    new_pairs, _ = review_record(
        raw, "data/mishearing/test.csv", new_review_decisions[0]
    )

    # Assert
    with pytest.raises(ValueError, match="review CSV hash"):
        apply_decisions(
            result.review_csv,
            inputs,
            new_pairs,
            patch,
            current_run="fixture-run",
        )


def test_invalid_later_patch_writes_no_earlier_record_outputs(tmp_path) -> None:
    """An invalid later decision prevents the entire batch from writing files."""
    # Arrange
    raw, review_payload, old_pairs, patch = _fixture()
    decisions = patch["decisions"]
    assert isinstance(decisions, list)
    decisions.append(
        {
            **decisions[0],
            "MishearID": "unknown-record",
        }
    )
    output_dir = tmp_path / "must-not-be-created"

    # Act / Assert
    with pytest.raises(ValueError, match="unknown review or original"):
        apply_patch_to_directory(
            review_payload,
            {raw["MishearID"]: (raw, "data/mishearing/test.csv")},
            old_pairs,
            patch,
            current_run="fixture-run",
            output_dir=output_dir,
        )
    assert not output_dir.exists()
