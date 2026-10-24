"""Protect researcher-directed choices without presenting them as recorded audio."""

from pathlib import Path

import pytest

from corpus_api.pair_workflow import load_reviews


@pytest.fixture(scope="module")
def reviews() -> dict[str, dict]:
    root = Path(__file__).resolve().parents[1]
    return {
        row["MishearID"]: row
        for row in load_reviews((root / "data/annotations/reviews.csv").read_bytes())
    }


def test_user_excluded_unit_confusion_is_retained_but_not_exported(reviews):
    # Arrange
    review = reviews["H6E3F490D977F6CC1"]

    # Act
    decision = (review["Status"], review["TargetDecision"])

    # Assert
    assert decision == ("reviewed", "exclude")
    assert "研究者指定" in review["Reason"]
    assert "0.5" in review["Reason"]
    assert review["OriginalHash"]


@pytest.mark.parametrize(
    ("identifier", "src_reading", "tgt_reading"),
    [
        ("gloriaxxx_exblog_2744779_004", "サイキ", "サエキ"),
        ("etsfuture_338_001", "ジーディー", "シーディー"),
        ("H0322FBB58A5268B0", "レイテンゴ", "ニテンゴ"),
        ("posfie_OOEDO4_037", "エヌイーシー", "ディズニーシー"),
        ("niftykids_200408100935_030", "ショウショッカン", "チュウショッカン"),
        (
            "tiktok_7493022714685426951_001",
            "ヨロシクオネガイシマス",
            "ケッコンシテクダサイ",
        ),
    ],
)
def test_conditional_choices_keep_the_assumption_visible(
    reviews, identifier, src_reading, tgt_reading
):
    # Arrange
    review = reviews[identifier]

    # Act
    annotations = (review["SrcAnnotations"], review["TgtAnnotations"])

    # Assert
    assert (review["Status"], review["TargetDecision"]) == ("reviewed", "include")
    assert "研究者方針" in review["Reason"]
    assert "原音未確認" in review["Reason"]
    for side, expected in zip(annotations, (src_reading, tgt_reading), strict=True):
        assert side[0]["reading"] == expected
        assert any("研究者方針" in value for value in side[0]["qualifiers"])


def test_explicit_kana_is_not_rejected_for_distance_or_hearing_loss(reviews):
    # Arrange
    review = reviews["sponichi_20250108_001"]

    # Act
    target = review["TgtAnnotations"][0]

    # Assert
    assert review["TargetDecision"] == "include"
    assert target["reading"] == "トーシンエイザック"
    assert "仮名" in review["Reason"]


def test_hidden_target_sounds_are_not_invented(reviews):
    # Arrange
    review = reviews["girlschannel_5697216_027"]

    # Act
    decision = (review["Status"], review["TargetDecision"])

    # Assert
    assert decision == ("pending", "undecided")


def test_preexisting_phrase_lineage_survives_adjudication(reviews):
    # Arrange
    review = reviews["tiktok_7493022714685426951_001"]

    # Act
    span = review["PairSpans"][0]

    # Assert
    assert span["SupersedesPairID"] == "37d827cc-7861-5ccf-a249-a12440dd3850"
    assert (span["src_start"], span["src_end"]) == (0, 10)
    assert (span["tgt_start"], span["tgt_end"]) == (0, 8)
