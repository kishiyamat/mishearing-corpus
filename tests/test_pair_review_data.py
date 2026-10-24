"""Protect researched corrections that were previously left unresolved or misread."""

from pathlib import Path

import pytest

from corpus_api.pair_workflow import _reading_key, load_reviews


@pytest.fixture(scope="module")
def canonical_reviews() -> dict[str, dict[str, object]]:
    """Read the editable review source, not a second hard-coded dataset copy."""
    root = Path(__file__).resolve().parents[1]
    return {
        str(row["MishearID"]): row
        for row in load_reviews((root / "data/annotations/reviews.csv").read_bytes())
    }


@pytest.mark.parametrize(
    ("identifier", "decision", "src_reading", "tgt_reading"),
    [
        ("coffee_break_parts_similar200912_006", "include", "カンスイ", "カンセイ"),
        ("coffee_break_parts_similar202201_005", "include", "シュト", "シト"),
        ("coffee_break_parts_similar200810_007", "include", "ケンメイ", "ケンメイ"),
        ("www_1101_com_m_iimatugai_530_html_009", "include", "カアイ", "カワイ"),
        (
            "ameblo_bbtmba_10852900207_002",
            "include",
            "ハントウトウヨ",
            "サントウトウヨ",
        ),
        ("iimatugai_2398_008", "include", "クマガヤ", "ワガヤ"),
        ("AcrugLVnrLE_024", "include", "ミスミバシ", "サングウバシ"),
        ("hadanokitaurology_blog_001", "include", "スブリ", "スズリ"),
        ("kinabal_telephone_002", "include", "エヌ", "エム"),
        (
            "coffee_break_parts_similar200905_003",
            "include",
            "ソウバナテキ",
            "ソウゴウテキ",
        ),
        (
            "coffee_break_parts_similar202309_001",
            "include",
            "ヒモンオシメ",
            "ヒモオシメ",
        ),
    ],
)
def test_researched_readings_are_not_left_as_generic_pending(
    canonical_reviews: dict[str, dict[str, object]],
    identifier: str,
    decision: str,
    src_reading: str,
    tgt_reading: str,
) -> None:
    """Keep source-specific names and full phrase readings, not generic guesses."""
    # Arrange
    review = canonical_reviews[identifier]

    # Act
    annotations = (review["SrcAnnotations"], review["TgtAnnotations"])

    # Assert
    assert review["Status"] == "reviewed"
    assert review["TargetDecision"] == decision
    for side, expected in zip(annotations, (src_reading, tgt_reading), strict=True):
        assert isinstance(side, list) and len(side) == 1
        assert _reading_key(side[0]["reading"]) == _reading_key(expected)


def test_announcement_keeps_the_actual_name_contrast(
    canonical_reviews: dict[str, dict[str, object]],
) -> None:
    """Do not reduce 取手ゆき/鳥居みゆき to homophonous 発車/発射 alone."""
    # Arrange
    review = canonical_reviews["www_1101_com_m_iimatugai_2811_html_006"]

    # Act
    source = review["SrcAnnotations"]
    target = review["TgtAnnotations"]

    # Assert
    assert review["Status"] == "reviewed"
    assert review["TargetDecision"] == "include"
    assert isinstance(source, list) and isinstance(target, list)
    assert source[0]["surface"].startswith("取手ゆき")
    assert target[0]["surface"].startswith("鳥居みゆき")
    assert review["PairSpans"][0]["SupersedesPairID"]


def test_independent_contrasts_in_one_record_are_not_dropped(
    canonical_reviews: dict[str, dict[str, object]],
) -> None:
    """Preserve both changes explicitly highlighted in the same primary example."""
    # Arrange
    review = canonical_reviews["coffee_break_parts_similar200506_003"]

    # Act
    source = review["SrcAnnotations"]
    target = review["TgtAnnotations"]

    # Assert
    assert review["TargetDecision"] == "include"
    assert len(review["PairSpans"]) == 2
    assert [item["surface"] for item in source] == ["逐一", "政治絡みだ"]
    assert [item["surface"] for item in target] == ["逐次", "政治家なんだ"]
    assert review["PairSpans"][1]["SupersedesPairID"]
