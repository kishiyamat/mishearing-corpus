"""Protect the corrected lexical/sense policy against sound-only exclusions."""

import csv
from pathlib import Path
from typing import Any

import pytest

from corpus_api.pair_workflow import load_reviews


@pytest.fixture(scope="module")
def reviews() -> dict[str, dict[str, Any]]:
    """Read the canonical review input, rather than a second editable corpus."""
    root = Path(__file__).resolve().parents[1]
    return {
        str(row["MishearID"]): row
        for row in load_reviews((root / "data/annotations/reviews.csv").read_bytes())
    }


@pytest.mark.parametrize(
    "identifier",
    [
        "20190115_004",  # 高地/高知: different lexemes
        "39mag_benesse_16332_003",  # 右中間/宇宙感: different interpretations
        "sakidori_tel01_008",  # 退社: going home/leaving employment
        "sakamotojidousha_7952_002",  # 大山町: different ward referents
        "taxi_gendai_007",  # 松屋: department store/restaurant
        "transcosmos_cotra_order_002",  # surname identity is not proved by reading
    ],
)
def test_distinct_homophone_interpretations_return_to_included_records(
    reviews: dict[str, dict[str, Any]], identifier: str
) -> None:
    """Neither matching kana nor matching written surface is a lexical identity proof."""
    # Arrange
    decision = reviews[identifier]

    # Act
    state = (decision["Status"], decision["TargetDecision"])

    # Assert
    assert state == ("reviewed", "include")
    assert decision["PairSpans"]
    assert decision["Evidence"] and decision["Reason"]


def test_specified_medical_unit_exclusion_is_not_undone_by_homophone_recovery(
    reviews: dict[str, dict[str, Any]],
) -> None:
    """The researcher's explicit unit-confusion scope exclusion remains independent."""
    # Arrange
    decision = reviews["H6E3F490D977F6CC1"]

    # Act
    state = (decision["Status"], decision["TargetDecision"])

    # Assert
    assert state == ("reviewed", "exclude")
    assert "研究者指定" in decision["Reason"]


def test_primary_comic_corrects_paper_tape_target_instead_of_calling_it_a_variant(
    reviews: dict[str, dict[str, Any]],
) -> None:
    """The primary comic says カビテープ, not the erroneous CSV's カミテープ."""
    # Arrange
    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "data/mishearing/google_to_star_no_kikimatigai_100_4-1/grapee_1466943.csv"
    )

    # Act
    with path.open(encoding="utf-8", newline="") as handle:
        original = next(
            row
            for row in csv.DictReader(handle)
            if row["MishearID"] == "grape_1466943_003"
        )
    decision = reviews["grape_1466943_003"]

    # Assert
    assert original["Tgt"] == "カビテープ"
    assert decision["TargetDecision"] == "include"
    assert decision["TgtAnnotations"][0]["reading"] == "カビテープ"
    assert "95350_03.jpg" in decision["Evidence"]


@pytest.mark.parametrize(
    "identifier",
    [
        "coffee_break_parts_similar200409_007",  # 沿う/添う: same contextual sense
        "coffee_break_parts_similar200507_006",  # 調う/整う: negotiation settled
        "coffee_break_parts_similar200510_001",  # 推し進め/押し進め: advance reform
        "coffee_break_parts_similar201004_002",  # 温め/暖め: retain an idea
    ],
)
def test_spelling_variants_require_contextual_lexical_identity_evidence(
    reviews: dict[str, dict[str, Any]], identifier: str
) -> None:
    """A same-word exclusion cites meaning identity, rather than reading equality."""
    # Arrange
    decision = reviews[identifier]

    # Act
    reason = str(decision["Reason"])

    # Assert
    assert decision["TargetDecision"] == "exclude"
    assert "同一語義" in reason
    assert "https://" in decision["Evidence"]


def test_resegmentation_keeps_complete_interpretations_not_an_isolated_suffix(
    reviews: dict[str, dict[str, Any]],
) -> None:
    """牡蠣やタラ/牡蠣やたら must not become the misleading タラ/たら fragment."""
    # Arrange
    decision = reviews["www_1101_com_iimatugai_2009-08-26_html_008"]

    # Act
    source = decision["SrcAnnotations"][0]
    target = decision["TgtAnnotations"][0]

    # Assert
    assert decision["TargetDecision"] == "include"
    assert source["surface"] == "牡蠣やタラ"
    assert target["surface"] == "牡蠣やたら"
    assert source["reading"] == target["reading"] == "カキヤタラ"
    assert source["meanings"] != target["meanings"]
    assert decision["PairSpans"][0]["SupersedesPairID"]
