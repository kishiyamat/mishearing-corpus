"""Behavior contracts for Issue 63, written before the v2 extraction pipeline."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from corpus_api.dataset import CorpusSnapshot, canonical_json
from corpus_api.models import DatasetInfo, LinkQuality, Record
from corpus_api.pair_workflow import (
    RecordReview,
    build_artifacts,
    csv_bytes,
    extract_record,
    load_reviews,
    mecab_tokens,
    original_hash,
    pair_table_schema,
    review_csv,
    review_record,
    validate_artifacts,
    validate_release,
    working_snapshot,
)


def snapshot(rows: list[dict[str, str]]) -> CorpusSnapshot:
    """Make a tiny immutable source fixture, without deriving expected outputs."""
    records = tuple(
        Record.model_validate(
            row | {"source_file": "data/mishearing/test.csv", "source": "test"}
        )
        for row in rows
    )
    info = DatasetInfo(
        dataset_version="a" * 40,
        dataset_sha256="b" * 64,
        record_count=len(rows),
        file_count=1,
        tag_ids=(),
        environment_ids=(),
        languages=("ja",),
        sources=("test",),
        quality=LinkQuality(),
    )
    return CorpusSnapshot(info, records, {row.MishearID: row for row in records})


def record(src: str, tgt: str) -> dict[str, str]:
    """Build an original record with the existing eleven-column contract."""
    from corpus_api.models import CSV_FIELDS

    return dict.fromkeys(CSV_FIELDS, "") | {
        "MishearID": "example",
        "Src": src,
        "Tgt": tgt,
        "Language": "ja",
    }


def tokens(text: str) -> list[tuple[int, int]]:
    """Use explicit fixture word boundaries, independent of a dictionary install."""
    if text == "三角橋":
        return [(0, 2), (2, 3)]
    if text == "参宮橋":
        return [(0, 2), (2, 3)]
    return [(0, len(text))] if text else []


def review(raw: dict[str, str], **extra: object) -> dict[str, object]:
    """Prepare an explicit, source-bound review, never an automatic approval."""
    return {
        "MishearID": raw["MishearID"],
        "OriginalHash": original_hash(raw),
        "Reviewer": "test-reviewer",
        "ReviewedAt": "2026-10-24",
        "Evidence": "fixture: explicit readings in original",
        "Reason": "checked both sides",
        "Status": "reviewed",
        "TargetDecision": "include",
        "SrcAnnotations": [],
        "TgtAnnotations": [],
        "PairSpans": [
            {
                "src_start": 0,
                "src_end": len(raw["Src"]),
                "tgt_start": 0,
                "tgt_end": len(raw["Tgt"]),
                "unit_type": "word",
            }
        ],
    } | extra


def test_typed_meaning_difference_is_not_a_phonological_candidate() -> None:
    """Meaning notes must be separated before tokenization and comparison."""
    # Arrange
    raw = record("|退社《たいしゃ》【意味：帰宅】", "|退社《たいしゃ》【意味：退職】")

    # Act
    rows, audit = extract_record(raw, "data/mishearing/test.csv", tokens)

    # Assert
    assert rows == []
    assert audit["CandidateCount"] == 0
    assert audit["ZeroReason"] == "same_surface"
    assert audit["ReviewStatus"] == "draft"


def test_machine_audit_has_explicit_unknown_record_validity() -> None:
    """Extraction does not infer an observed event from a differing word pair."""
    # Arrange
    raw = record("かめ", "かね")

    # Act
    _, audit = extract_record(raw, "test.csv", tokens)

    # Assert
    assert audit["RecordValidity"] == "unclear"


def test_illustrative_pair_is_not_automatically_phonologically_excluded() -> None:
    """Issue 43 separates event validity from phonological target eligibility."""
    # Arrange
    raw = record("|かめ《かめ》", "|かね《かね》")
    decision = review(raw, RecordValidity="illustrative")

    # Act
    rows, audit = review_record(raw, "test.csv", decision)

    # Assert
    assert rows[0]["TargetDecision"] == "include"
    assert rows[0]["RecordValidity"] == audit["RecordValidity"] == "illustrative"


def test_legacy_parentheses_are_not_silently_removed() -> None:
    """Unknown legacy annotations remain visible and require review."""
    # Arrange
    raw = record("退社（帰宅）", "退社（退職）")

    # Act
    rows, _ = extract_record(raw, "data/mishearing/test.csv", tokens)

    # Assert
    assert rows[0]["Src"] == "退社（帰宅）"
    assert "legacy_parentheses" in rows[0]["Flags"]
    assert rows[0]["ReviewStatus"] == "draft"


def test_homograph_with_explicitly_different_readings_is_not_lost() -> None:
    """Equal written surfaces can still encode different pronunciations."""
    # Arrange
    raw = record("|下手《したて》", "|下手《へた》")

    # Act
    rows, audit = extract_record(raw, "test.csv", tokens)

    # Assert
    assert len(rows) == 1
    assert (rows[0]["SrcReading"], rows[0]["TgtReading"]) == ("したて", "へた")
    assert rows[0]["SrcReadingStatus"] == "proposed"
    assert audit["CandidateCount"] == 1


def test_kana_script_difference_cannot_be_approved_as_phonological_difference() -> None:
    """Hiragana versus katakana alone must not create an evaluation pair."""
    # Arrange
    raw = record("|退社《タイシャ》", "|退社《たいしゃ》")
    decision = review(raw)

    # Act / Assert
    with pytest.raises(ValueError, match="identical"):
        review_record(raw, "test.csv", decision)


def test_whole_compound_alternative_keeps_shared_suffix() -> None:
    """A shared 橋 must not disappear from the alternatives for review."""
    # Arrange
    raw = record("三角橋", "参宮橋")

    # Act
    rows, _ = extract_record(raw, "data/mishearing/test.csv", tokens)

    # Assert
    assert (rows[0]["Src"], rows[0]["Tgt"]) == ("三角", "参宮")
    assert any((r["Src"], r["Tgt"]) == ("三角橋", "参宮橋") for r in rows)


def test_pair_ids_are_independent_of_file_order() -> None:
    """Moving source files must not renumber logical candidates."""
    # Arrange
    raw = record("三角橋", "参宮橋")

    # Act
    left, _ = extract_record(raw, "old.csv", tokens)
    right, _ = extract_record(raw, "new.csv", tokens)

    # Assert
    assert [r["PairID"] for r in left] == [r["PairID"] for r in right]


def test_manual_pair_id_cannot_be_a_csv_row_number() -> None:
    """Custom retained IDs use UUIDs, not unstable row indexes."""
    # Arrange
    raw = record("|熊谷《くまがや》", "|反町《そりまち》")
    decision = review(
        raw,
        PairSpans=[
            {
                "src_start": 0,
                "src_end": len(raw["Src"]),
                "tgt_start": 0,
                "tgt_end": len(raw["Tgt"]),
                "unit_type": "word",
                "PairID": "123",
            }
        ],
    )

    # Act / Assert
    with pytest.raises(ValueError):
        review_record(raw, "test.csv", decision)


def test_review_keeps_asymmetric_boundaries_and_original_provenance() -> None:
    """A reviewer may select 舞台が/豚肉 without inventing 豚肉が."""
    # Arrange
    raw = record("舞台が見える", "豚肉見える")
    decision = review(
        raw,
        PairSpans=[
            {
                "src_start": 0,
                "src_end": 3,
                "tgt_start": 0,
                "tgt_end": 2,
                "unit_type": "particle-inclusive",
            }
        ],
        Status="pending",
        TargetDecision="undecided",
    )

    # Act
    rows, audit = review_record(raw, "test.csv", decision)

    # Assert
    assert (rows[0]["Src"], rows[0]["Tgt"]) == ("舞台が", "豚肉")
    assert rows[0]["SrcOriginal"] == "舞台が見える"
    assert rows[0]["TgtReadingStatus"] == "unknown"
    assert audit["ReviewStatus"] == "pending"


def test_explicit_legacy_reading_and_qualifier_can_be_corrected() -> None:
    """Source-grounded mixed parentheses become typed annotation fields."""
    # Arrange
    raw = record("大山町（おおやまちょう；渋谷区）", "大山町（おおやまちょう；板橋区）")
    decision = review(
        raw,
        TargetDecision="exclude",
        SrcAnnotations=[
            {
                "start": 0,
                "end": len(raw["Src"]),
                "surface": "大山町",
                "reading": "おおやまちょう",
                "qualifiers": ["渋谷区"],
                "meanings": [],
            }
        ],
        TgtAnnotations=[
            {
                "start": 0,
                "end": len(raw["Tgt"]),
                "surface": "大山町",
                "reading": "おおやまちょう",
                "qualifiers": ["板橋区"],
                "meanings": [],
            }
        ],
    )

    # Act
    rows, _ = review_record(raw, "test.csv", decision)

    # Assert
    assert rows[0]["Src"] == rows[0]["Tgt"] == "大山町"
    assert rows[0]["SrcReading"] == "おおやまちょう"
    assert rows[0]["SrcAnnotated"] == "|大山町《おおやまちょう》【識別：渋谷区】"
    assert rows[0]["TargetDecision"] == "exclude"


@pytest.mark.parametrize(
    "mutation",
    [
        {"OriginalHash": "outdated"},
        {"Reviewer": ""},
        {"Evidence": ""},
        {"Status": "reviewed", "TargetDecision": "include"},
    ],
)
def test_invalid_or_unconfirmed_review_is_rejected(mutation: dict[str, object]) -> None:
    """No stale evidence or unknown readings may become evaluation truth."""
    # Arrange
    raw = record("熊谷", "反町")
    decision = review(raw, **mutation)

    # Act / Assert
    with pytest.raises(ValueError):
        review_record(raw, "test.csv", decision)


def test_hash_preserves_original_strings_not_csv_location() -> None:
    """All eleven fields, including notes, bind a review to its original."""
    # Arrange
    raw = record("Src", "Tgt")
    changed = raw | {"Note": "new evidence"}

    # Act
    first, second = original_hash(raw), original_hash(changed)

    # Assert
    assert first != second
    assert len(first) == 64


def test_review_csv_roundtrip_preserves_typed_fields() -> None:
    """CSV is the edit source; structured cells must survive quoting/newlines."""
    # Arrange
    raw = record("|熊谷《くまがや》", "|反町《そりまち》")
    decision = review(raw, Evidence="source, with\nnewline")

    # Act
    result = load_reviews(review_csv([decision]))

    # Assert
    assert result[0]["Evidence"] == "source, with\nnewline"
    assert result[0]["PairSpans"] == [
        {
            "src_start": 0,
            "src_end": len(raw["Src"]),
            "tgt_start": 0,
            "tgt_end": len(raw["Tgt"]),
            "unit_type": "word",
            "PairID": "",
            "SupersedesPairID": "",
        }
    ]


def test_release_rejects_missing_coverage(tmp_path: Path) -> None:
    """The evaluation gate must fail when any source record lacks a review."""
    # Arrange
    (tmp_path / "manifest.json").write_text(json.dumps({"unprocessed_count": 1}))

    # Act / Assert
    with pytest.raises(ValueError):
        validate_release(tmp_path)


@pytest.mark.parametrize(
    "field",
    [
        "input_count",
        "candidate_count",
        "zero_candidate_count",
        "reviewed_record_count",
        "pending_record_count",
        "excluded_record_count",
        "evaluation_pair_count",
        "review_complete",
        "linguistic_quality_complete",
    ],
)
def test_validation_recomputes_coverage_not_just_file_checksums(field: str) -> None:
    """Reported coverage cannot be forged by editing only the manifest."""
    # Arrange
    raw = record("|熊谷《くまがや》", "|反町《そりまち》")
    corpus = snapshot([raw])
    decisions = [review(raw)]
    files = build_artifacts(corpus, decisions, tokens)
    manifest = json.loads(files["manifest.json"])
    manifest[field] = 12345
    files["manifest.json"] = canonical_json(manifest).encode()

    # Act / Assert
    with pytest.raises(ValueError):
        validate_artifacts(files, corpus, decisions)


@pytest.mark.parametrize("filename", ["records.csv", "changes.csv", "draft.csv"])
def test_validation_checks_rehashed_artifact_content(filename: str) -> None:
    """Rehashing altered audit files must not bypass source-bound validation."""
    # Arrange
    raw = record("|熊谷《くまがや》", "|反町《そりまち》")
    corpus = snapshot([raw])
    decisions = [review(raw)]
    files = build_artifacts(corpus, decisions, tokens)
    files[filename] = files[filename].replace("熊谷".encode(), "別語".encode())
    manifest = json.loads(files["manifest.json"])
    manifest["files"][filename] = hashlib.sha256(files[filename]).hexdigest()
    files["manifest.json"] = canonical_json(manifest).encode()

    # Act / Assert
    with pytest.raises(ValueError):
        validate_artifacts(files, corpus, decisions)


def test_local_validation_sees_uncommitted_original_changes(tmp_path: Path) -> None:
    """A pre-commit gate must not validate old Git bytes while ignoring edited CSVs."""
    # Arrange
    from corpus_api.models import CSV_FIELDS

    raw = record("|熊谷《くまがや》", "|反町《そりまち》")
    corpus = snapshot([raw])
    decisions = [review(raw)]
    files = build_artifacts(corpus, decisions, tokens)
    path = tmp_path / "data/mishearing/test.csv"
    path.parent.mkdir(parents=True)
    path.write_bytes(csv_bytes([raw | {"Note": "edited"}], CSV_FIELDS))

    # Act
    edited = working_snapshot(tmp_path, corpus)

    # Assert
    with pytest.raises(ValueError, match="different original"):
        validate_artifacts(files, edited, decisions)


@pytest.mark.skipif(
    shutil.which("mecab") is None, reason="optional MeCab CLI is not installed"
)
def test_real_mecab_offsets_preserve_whitespace_and_repeated_tokens() -> None:
    """Exercise the installed CLI, not a mock of its tokenization protocol."""
    # Arrange
    text = "  三角橋\n参宮橋 三角橋　"

    # Act
    result = mecab_tokens(text)

    # Assert
    assert result[0][0] == 2
    assert "".join(text[s:e] for s, e in result) == "三角橋参宮橋三角橋"
    assert result == sorted(result)
    assert all(s < e for s, e in result)


def test_derived_pair_csv_validates_against_table_schema(tmp_path: Path) -> None:
    """Exercise Frictionless itself on the generated flat-string CSV contract."""
    # Arrange
    from frictionless import Schema, validate

    raw = record("|熊谷《くまがや》", "|反町《そりまち》")
    files = build_artifacts(snapshot([raw]), [review(raw)], tokens)
    path = tmp_path / "reviewed.csv"
    path.write_bytes(files["reviewed.csv"])

    # Act
    report = validate(
        path.name,
        basepath=str(tmp_path),
        schema=Schema.from_descriptor(pair_table_schema()),
    )

    # Assert
    assert report.valid, report.flatten(["type", "message"])


def test_saved_schemas_match_the_executable_contract() -> None:
    """A model change must not leave a stale published schema behind."""
    # Arrange
    directory = Path(__file__).parents[1] / "schema"
    review_schema = json.loads((directory / "pair_review.schema.json").read_text())
    csv_schema = json.loads((directory / "pair.table.schema.json").read_text())

    # Act / Assert
    assert review_schema == RecordReview.model_json_schema()
    assert csv_schema == pair_table_schema()
