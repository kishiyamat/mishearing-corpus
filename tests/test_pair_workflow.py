"""Behavior contracts for Issue 63, written before the v2 extraction pipeline."""

import csv
import hashlib
import io
import json
import shutil
from pathlib import Path

import pytest

from corpus_api.dataset import CorpusSnapshot, canonical_json
from corpus_api.models import DatasetInfo, LinkQuality, Record
from corpus_api.pair_workflow import (
    PAIR_FIELDS,
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
    return [(0, len(text))] if text else []


class TaggedTokens(list[tuple[int, int]]):
    """Provide fixture POS tags through the same list-shaped tokenizer boundary."""

    def __init__(self, spans: list[tuple[int, int]], pos_tags: list[str]) -> None:
        super().__init__(spans)
        self.pos_tags = pos_tags


def tokenized_parts(text: str, parts: list[tuple[str, str]]) -> TaggedTokens:
    """Align fixture token surfaces to unchanged text and attach POS labels."""
    cursor = 0
    spans: list[tuple[int, int]] = []
    tags: list[str] = []
    for surface, tag in parts:
        assert text[cursor : cursor + len(surface)] == surface
        spans.append((cursor, cursor + len(surface)))
        tags.append(tag)
        cursor += len(surface)
    assert cursor == len(text)
    return TaggedTokens(spans, tags)


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


def test_typed_meaning_difference_is_retained_as_a_semantic_alternative() -> None:
    """Separate meaning notes from the surface without dropping a sense contrast."""
    # Arrange
    raw = record("|退社《たいしゃ》【意味：帰宅】", "|退社《たいしゃ》【意味：退職】")

    # Act
    rows, audit = extract_record(raw, "data/mishearing/test.csv", tokens)

    # Assert
    assert len(rows) == audit["CandidateCount"] == 1
    assert rows[0]["Src"] == rows[0]["Tgt"] == "退社"
    assert json.loads(rows[0]["SrcMeaning"]) == ["帰宅"]
    assert json.loads(rows[0]["TgtMeaning"]) == ["退職"]
    assert rows[0]["TargetDecision"] == "undecided"
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


def test_same_word_variant_remains_excluded_by_explicit_lexical_review() -> None:
    """Script normalization is grounds for this review, not a universal sound gate."""
    # Arrange
    raw = record("|退社《タイシャ》", "|退社《たいしゃ》")
    decision = review(
        raw,
        TargetDecision="exclude",
        Evidence="fixture: same lexical surface 退社 and same sense; kana scripts vary only",
        Reason="Same word and meaning; only the reading notation script differs",
    )

    # Act
    rows, audit = review_record(raw, "test.csv", decision)

    # Assert
    assert rows[0]["TargetDecision"] == audit["TargetDecision"] == "exclude"
    assert rows[0]["Evidence"] == decision["Evidence"]


@pytest.mark.parametrize(
    ("src", "tgt"),
    [
        ("|高地《こうち》", "|高知《コウチ》"),
        ("|右中間《うちゅうかん》", "|宇宙感《うちゅうかん》"),
        ("|退社《たいしゃ》【意味：帰宅】", "|退社《たいしゃ》【意味：退職】"),
        (
            "|松屋《まつや》【識別：百貨店】",
            "|松屋《まつや》【識別：飲食店】",
        ),
    ],
)
def test_review_can_include_homophones_with_distinct_words_or_interpretations(
    src: str, tgt: str
) -> None:
    """Same reading alone never vetoes an attributed word/sense/referent review."""
    # Arrange
    raw = record(src, tgt)
    decision = review(raw, Reason="Different lexical interpretations retained")

    # Act
    rows, audit = review_record(raw, "test.csv", decision)

    # Assert
    assert len(rows) == 1
    assert rows[0]["TargetDecision"] == audit["TargetDecision"] == "include"
    assert rows[0]["SrcReadingStatus"] == rows[0]["TgtReadingStatus"] == "confirmed"


def test_identical_surface_reading_and_meaning_remain_a_zero_difference_draft() -> None:
    """Adding homophones must not make an identical interpretation a new contrast."""
    # Arrange
    raw = record("|退社《タイシャ》【意味：帰宅】", "|退社《たいしゃ》【意味：帰宅】")

    # Act
    rows, audit = extract_record(raw, "test.csv", tokens)

    # Assert
    assert rows == []
    assert audit["CandidateCount"] == 0
    assert audit["ZeroReason"] == "same_surface"


def test_proper_name_tokens_keep_shared_suffix_inside_the_word() -> None:
    """The tokenizer's whole-name boundary is retained even with a shared suffix."""
    # Arrange
    raw = record("三角橋", "参宮橋")

    # Act
    rows, _ = extract_record(
        raw,
        "data/mishearing/test.csv",
        lambda text: tokenized_parts(text, [(text, "名詞-固有名詞")]),
    )

    # Assert
    candidate = next(row for row in rows if row["UnitType"] != "phrase")
    assert (candidate["Src"], candidate["Tgt"]) == ("三角橋", "参宮橋")


@pytest.mark.parametrize(
    ("src", "tgt", "src_parts", "tgt_parts", "expected"),
    [
        (
            "その人に幸福をもたらすことができるか",
            "その人に交付金をもたらすことができるか",
            [
                ("その人に", "名詞"),
                ("幸福", "名詞"),
                ("をもたらすことができるか", "助詞"),
            ],
            [
                ("その人に", "名詞"),
                ("交付", "名詞"),
                ("金", "名詞-接尾-一般"),
                ("をもたらすことができるか", "助詞"),
            ],
            ("幸福", "交付金", "compound", 4, 6, 4, 7),
        ),
        (
            "欧州問題が深刻化し、投資家のリスク回避姿勢が強まってきますと、",
            "欧州本体が深刻化し、投資家のリスク回避性が強まってきますと、",
            [
                ("欧州", "名詞"),
                ("問題", "名詞"),
                ("が", "助詞"),
                ("深刻化し、投資家のリスク", "名詞"),
                ("回避", "名詞"),
                ("姿勢", "名詞"),
                ("が強まってきますと、", "助詞"),
            ],
            [
                ("欧州", "名詞"),
                ("本体", "名詞"),
                ("が", "助詞"),
                ("深刻化し、投資家のリスク", "名詞"),
                ("回避", "名詞"),
                ("性", "名詞-接尾-一般"),
                ("が強まってきますと、", "助詞"),
            ],
            ("問題", "本体", "word", 2, 4, 2, 4),
        ),
    ],
)
def test_machine_candidate_uses_minimal_lexical_contrast(
    src: str,
    tgt: str,
    src_parts: list[tuple[str, str]],
    tgt_parts: list[tuple[str, str]],
    expected: tuple[str, str, str, int, int, int, int],
) -> None:
    """Common sentence context is omitted from lexical candidate spans."""

    # Arrange
    def tokenizer(text: str) -> TaggedTokens:
        return tokenized_parts(text, src_parts if text == src else tgt_parts)

    raw = record(src, tgt)

    # Act
    rows, _ = extract_record(raw, "test.csv", tokenizer)

    # Assert
    src_word, tgt_word, unit_type, src_start, src_end, tgt_start, tgt_end = expected
    candidate = next(
        row for row in rows if (row["Src"], row["Tgt"]) == (src_word, tgt_word)
    )
    assert candidate["UnitType"] == unit_type
    assert (
        int(candidate["SrcStart"]),
        int(candidate["SrcEnd"]),
        int(candidate["TgtStart"]),
        int(candidate["TgtEnd"]),
    ) == (src_start, src_end, tgt_start, tgt_end)
    assert candidate["SrcReadingStatus"] == candidate["TgtReadingStatus"] == "unknown"


def test_review_can_calibrate_compound_candidate_as_word_with_exact_reading_evidence() -> (
    None
):
    """A reviewed lexical decision supersedes the tokenizer's compound candidate."""
    # Arrange
    raw = record(
        "その人に幸福をもたらすことができるか",
        "その人に交付金をもたらすことができるか",
    )
    decision = review(
        raw,
        Evidence="Original source and IPADIC tokens: 幸福=コウフク, 交付=コウフ, 金=キン",
        Reason="The reviewed pair is the independent lexical contrast at the stated spans.",
        SrcAnnotations=[
            {
                "start": 4,
                "end": 6,
                "surface": "幸福",
                "reading": "こうふく",
                "meanings": [],
                "qualifiers": [],
            }
        ],
        TgtAnnotations=[
            {
                "start": 4,
                "end": 7,
                "surface": "交付金",
                "reading": "こうふきん",
                "meanings": [],
                "qualifiers": [],
            }
        ],
        PairSpans=[
            {
                "src_start": 4,
                "src_end": 6,
                "tgt_start": 4,
                "tgt_end": 7,
                "unit_type": "word",
            }
        ],
    )

    # Act
    rows, _ = review_record(raw, "test.csv", decision)

    # Assert
    assert len(rows) == 1
    assert (rows[0]["Src"], rows[0]["Tgt"], rows[0]["UnitType"]) == (
        "幸福",
        "交付金",
        "word",
    )
    assert rows[0]["SrcReadingStatus"] == rows[0]["TgtReadingStatus"] == "confirmed"


def test_suffix_difference_restores_shared_lexical_stem_as_compound() -> None:
    """A suffix alone is not mislabeled as a standalone word contrast."""
    # Arrange
    src = "東京都回避姿勢"
    tgt = "県回避性"

    def tokenizer(text: str) -> TaggedTokens:
        parts = (
            [("東京都", "名詞"), ("回避", "名詞"), ("姿勢", "名詞")]
            if text == src
            else [("県", "名詞"), ("回避", "名詞"), ("性", "名詞-接尾-一般")]
        )
        return tokenized_parts(text, parts)

    raw = record(src, tgt)

    # Act
    rows, _ = extract_record(raw, "test.csv", tokenizer)

    # Assert
    candidate = next(row for row in rows if row["Src"] == "回避姿勢")
    assert (candidate["Tgt"], candidate["UnitType"]) == ("回避性", "compound")
    assert (candidate["SrcStart"], candidate["SrcEnd"]) == ("3", "7")
    assert (candidate["TgtStart"], candidate["TgtEnd"]) == ("1", "4")


def test_nonlexical_phrase_difference_is_not_labeled_as_word() -> None:
    """A phrase fragment containing a particle remains a contextual candidate."""
    # Arrange
    src = "聞き分けのない女の頬を"
    tgt = "父は毛のない女の頬を"

    def tokenizer(text: str) -> TaggedTokens:
        if text == src:
            parts = [("聞き分け", "名詞"), ("のない女の頬を", "助詞")]
        else:
            parts = [
                ("父", "名詞"),
                ("は", "助詞"),
                ("毛", "名詞"),
                ("のない女の頬を", "助詞"),
            ]
        return tokenized_parts(text, parts)

    raw = record(src, tgt)

    # Act
    rows, _ = extract_record(raw, "test.csv", tokenizer)

    # Assert
    candidate = next(row for row in rows if row["Src"] == "聞き分け")
    assert (candidate["Tgt"], candidate["UnitType"]) == ("父は毛", "phrase")
    assert (candidate["SrcStart"], candidate["SrcEnd"]) == ("0", "4")
    assert (candidate["TgtStart"], candidate["TgtEnd"]) == ("0", "3")


@pytest.mark.parametrize(
    ("src", "tgt", "expected_type"),
    [
        ("食べる", "しゃべる", "word"),
        (
            "書いた",
            "描いた",
            "word",
        ),
        ("コンポーネントになる", "根本になる", "phrase"),
    ],
)
def test_independent_predicate_forms_and_phrase_chains_are_not_confused(
    src: str, tgt: str, expected_type: str
) -> None:
    """Keep full inflected words while avoiding multi-token predicate phrases."""

    # Arrange
    def tokenizer(text: str) -> TaggedTokens:
        if src == "食べる":
            tokens_for_text = [
                [("食べ", "動詞-自立"), ("る", "助動詞")],
                [("しゃべ", "動詞-自立"), ("る", "助動詞")],
            ][text == tgt]
        elif src == "書いた":
            tokens_for_text = [
                [("書い", "動詞-自立"), ("た", "助動詞")],
                [("描い", "動詞-自立"), ("た", "助動詞")],
            ][text == tgt]
        else:
            tokens_for_text = (
                [("コンポーネント", "名詞"), ("に", "助詞"), ("なる", "動詞-自立")]
                if text == src
                else [("根本", "名詞"), ("に", "助詞"), ("なる", "動詞-自立")]
            )
        return tokenized_parts(text, tokens_for_text)

    raw = record(src, tgt)

    # Act
    rows, _ = extract_record(raw, "test.csv", tokenizer)

    # Assert
    candidate = next(row for row in rows if (row["Src"], row["Tgt"]) == (src, tgt))
    assert (candidate["Src"], candidate["Tgt"]) == (src, tgt)
    assert candidate["UnitType"] == expected_type


def test_proper_name_is_not_cut_at_a_shared_character_inside_words() -> None:
    """Only token boundaries are candidates; shared 橋 does not force a split."""
    # Arrange
    raw = record("三角橋", "参宮橋")

    # Act
    rows, _ = extract_record(
        raw,
        "test.csv",
        lambda text: tokenized_parts(text, [(text, "名詞-固有名詞")]),
    )

    # Assert
    candidate = next(row for row in rows if row["UnitType"] != "phrase")
    assert (candidate["Src"], candidate["Tgt"], candidate["UnitType"]) == (
        "三角橋",
        "参宮橋",
        "word",
    )
    assert (candidate["SrcStart"], candidate["SrcEnd"]) == ("0", "3")


def test_connected_verb_stem_includes_its_te_conjunctive_particle() -> None:
    """Keep a contrastive verb's required て-form ending with its non-independent stem."""
    # Arrange
    raw = record("誤って", "謝って")

    def pos_tokenizer(text: str) -> TaggedTokens:
        if text == "誤って":
            return tokenized_parts(
                text, [("誤っ", "動詞-自立"), ("て", "助詞-接続助詞")]
            )
        return tokenized_parts(text, [("謝っ", "動詞-自立"), ("て", "助詞-接続助詞")])

    # Act
    rows, _ = extract_record(raw, "data/mishearing/test.csv", pos_tokenizer)

    # Assert
    candidate = next(
        row for row in rows if (row["Src"], row["Tgt"]) == ("誤って", "謝って")
    )
    assert candidate["UnitType"] == "word"
    assert (
        candidate["SrcStart"],
        candidate["SrcEnd"],
        candidate["TgtStart"],
        candidate["TgtEnd"],
    ) == ("0", "3", "0", "3")


def test_shared_de_after_nouns_is_not_added_to_the_lexical_candidate() -> None:
    """The verb-form repair must not absorb a generic shared particle after nouns."""
    # Arrange
    raw = record("針で", "糸で")

    def pos_tokenizer(text: str) -> TaggedTokens:
        first = "針" if text.startswith("針") else "糸"
        return tokenized_parts(text, [(first, "名詞-一般"), ("で", "助詞-格助詞")])

    # Act
    rows, _ = extract_record(raw, "data/mishearing/test.csv", pos_tokenizer)

    # Assert
    lexical = [row for row in rows if row["UnitType"] in {"word", "compound"}]
    assert [(row["Src"], row["Tgt"]) for row in lexical] == [("針", "糸")]


def test_shared_copula_after_nouns_is_not_added_to_the_lexical_candidate() -> None:
    """A shared nominal copula must not turn two noun words into phrases."""
    # Arrange
    raw = record("リンゴです", "バナナです")

    def pos_tokenizer(text: str) -> TaggedTokens:
        noun = "リンゴ" if text.startswith("リンゴ") else "バナナ"
        return tokenized_parts(
            text, [(noun, "名詞-一般"), ("です", "助動詞-特殊・デス")]
        )

    # Act
    rows, _ = extract_record(raw, "data/mishearing/test.csv", pos_tokenizer)

    # Assert
    candidate = next(row for row in rows if row["UnitType"] != "phrase")
    assert (candidate["Src"], candidate["Tgt"], candidate["UnitType"]) == (
        "リンゴ",
        "バナナ",
        "word",
    )


def test_shared_nominal_suffix_keeps_full_noun_compound_as_compound() -> None:
    """A shared nominal suffix belongs to the full compound, not a standalone word."""
    # Arrange
    raw = record("革命性", "改革性")

    def pos_tokenizer(text: str) -> TaggedTokens:
        stem = "革命" if text.startswith("革命") else "改革"
        return tokenized_parts(text, [(stem, "名詞-一般"), ("性", "名詞-接尾-一般")])

    # Act
    rows, _ = extract_record(raw, "data/mishearing/test.csv", pos_tokenizer)

    # Assert
    candidate = next(row for row in rows if row["UnitType"] != "phrase")
    assert (candidate["Src"], candidate["Tgt"], candidate["UnitType"]) == (
        "革命性",
        "改革性",
        "compound",
    )


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
    """Classified parentheses preserve distinct place referents even at one reading."""
    # Arrange
    raw = record("大山町（おおやまちょう；渋谷区）", "大山町（おおやまちょう；板橋区）")
    decision = review(
        raw,
        TargetDecision="include",
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
    assert rows[0]["TargetDecision"] == "include"


def test_parenthetical_orthographic_note_stays_outside_shortened_pair() -> None:
    """Keep an explanatory parenthesis classified without leaking it into reading."""
    # Arrange
    raw = record("あくしゅ（握手）", "はくしゅ（拍手）")
    decision = review(
        raw,
        SrcAnnotations=[
            {
                "start": 0,
                "end": 4,
                "surface": "あくしゅ",
                "reading": "あくしゅ",
                "meanings": ["握手"],
                "qualifiers": ["原音未確認"],
            },
            {
                "start": 4,
                "end": 8,
                "surface": "握手",
                "reading": "",
                "meanings": [],
                "qualifiers": ["括弧内表記補足（非発話）"],
            },
        ],
        TgtAnnotations=[
            {
                "start": 0,
                "end": 4,
                "surface": "はくしゅ",
                "reading": "はくしゅ",
                "meanings": ["拍手"],
                "qualifiers": [],
            },
            {
                "start": 4,
                "end": 8,
                "surface": "拍手",
                "reading": "",
                "meanings": [],
                "qualifiers": ["括弧内表記補足（非発話）"],
            },
        ],
        PairSpans=[
            {
                "src_start": 0,
                "src_end": 4,
                "tgt_start": 0,
                "tgt_end": 4,
                "unit_type": "word",
            }
        ],
    )

    # Act
    rows, _ = review_record(raw, "data/mishearing/test.csv", decision)

    # Assert
    assert rows[0]["SrcOriginal"] == "あくしゅ（握手）"
    assert rows[0]["TgtOriginal"] == "はくしゅ（拍手）"
    assert (rows[0]["Src"], rows[0]["Tgt"]) == ("あくしゅ", "はくしゅ")
    assert (rows[0]["SrcReading"], rows[0]["TgtReading"]) == (
        "あくしゅ",
        "はくしゅ",
    )
    assert json.loads(rows[0]["SrcMeaning"]) == ["握手"]
    assert json.loads(rows[0]["SrcQualifier"]) == ["原音未確認"]
    assert json.loads(rows[0]["TgtMeaning"]) == ["拍手"]
    assert rows[0]["SrcOriginal"] not in rows[0]["SrcAnnotated"]
    assert "握手" not in rows[0]["SrcReading"]


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


def test_validation_rejects_removing_a_same_surface_meaning_contrast() -> None:
    """A forged zero-candidate ledger cannot hide a typed semantic distinction."""
    # Arrange
    raw = record("|退社《たいしゃ》【意味：帰宅】", "|退社《たいしゃ》【意味：退職】")
    corpus = snapshot([raw])
    files = build_artifacts(corpus, [], tokens)
    ledger_reader = csv.DictReader(io.StringIO(files["records.csv"].decode()))
    ledger = list(ledger_reader)
    ledger[0].update(CandidateCount="0", ZeroReason="same_surface")
    files["records.csv"] = csv_bytes(ledger, list(ledger_reader.fieldnames or []))
    files["draft.csv"] = csv_bytes([], PAIR_FIELDS)
    manifest = json.loads(files["manifest.json"])
    manifest.update(candidate_count=0, zero_candidate_count=1)
    for name in ("records.csv", "draft.csv"):
        manifest["files"][name] = hashlib.sha256(files[name]).hexdigest()
    files["manifest.json"] = canonical_json(manifest).encode()

    # Act / Assert
    with pytest.raises(ValueError, match="context candidate"):
        validate_artifacts(files, corpus, [])


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
    assert len(result.pos_tags) == len(result)


@pytest.mark.skipif(
    shutil.which("mecab") is None, reason="optional MeCab CLI is not installed"
)
def test_real_mecab_proposes_lexical_and_contextual_units_at_expected_boundaries() -> (
    None
):
    """Installed IPADIC boundaries and POS keep fixed word/compound/phrase cases."""
    # Arrange
    coffee_src = "欧州問題が深刻化し、投資家のリスク回避姿勢が強まってきますと、円高になる傾向が生まれやすくなります。そのことが企業マインド、あるいは収益等を通じて、日本経済を下押すことがあります。"
    coffee_tgt = "欧州本体が深刻化し、投資家のリスク回避性が強まってきますと、円高になる傾向が生まれやすくなります。そのことが企業マインド、あるいは収益等を通じて、日本経済を下押すことがあります。"
    cases = [
        (
            "その人に幸福をもたらすことができるか",
            "その人に交付金をもたらすことができるか",
            "幸福",
            "交付金",
            "compound",
            (4, 6, 4, 7),
        ),
        (coffee_src, coffee_tgt, "問題", "本体", "word", (2, 4, 2, 4)),
        (coffee_src, coffee_tgt, "回避姿勢", "回避性", "compound", (17, 21, 17, 20)),
        (
            "聞き分けのない女の頬を（ジュリーの歌）",
            "父は毛のない女の頬を",
            "聞き分け",
            "父は毛",
            "phrase",
            (0, 4, 0, 3),
        ),
        ("三角橋", "参宮橋", "三角橋", "参宮橋", "compound", (0, 3, 0, 3)),
        ("革命性", "改革性", "革命性", "改革性", "compound", (0, 3, 0, 3)),
        ("リンゴです", "バナナです", "リンゴ", "バナナ", "word", (0, 3, 0, 3)),
        ("誤って", "謝って", "誤って", "謝って", "word", (0, 3, 0, 3)),
    ]

    # Act
    outputs = [
        extract_record(record(src, tgt), "test.csv")[0] for src, tgt, *_ in cases
    ]

    # Assert
    for rows, (_, _, expected_src, expected_tgt, unit_type, bounds) in zip(
        outputs, cases, strict=True
    ):
        candidate = next(
            row
            for row in rows
            if (row["Src"], row["Tgt"]) == (expected_src, expected_tgt)
        )
        assert candidate["UnitType"] == unit_type
        assert (
            tuple(
                int(candidate[field])
                for field in ("SrcStart", "SrcEnd", "TgtStart", "TgtEnd")
            )
            == bounds
        )
        assert (
            candidate["SrcReadingStatus"],
            candidate["TgtReadingStatus"],
        ) == ("unknown", "unknown")


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
