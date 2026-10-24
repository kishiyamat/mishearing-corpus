"""Acceptance regressions for review-calibrated lexical pair boundaries."""

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _current_reviewed_rows() -> dict[str, list[dict[str, str]]]:
    """Read the reviewed output selected by the canonical pointer."""
    pointer = json.loads((ROOT / "resource/pairs_v2/current.json").read_text())
    run_dir = ROOT / "resource/pairs_v2" / pointer["directory"]
    with (run_dir / "reviewed.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        by_id: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            by_id.setdefault(row["MishearID"], []).append(row)
    return by_id


def _pair(
    rows: dict[str, list[dict[str, str]]], mishear_id: str, src: str, tgt: str
) -> dict[str, str]:
    """Find one explicitly expected selected unit by ID and surface pair."""
    return next(
        row for row in rows[mishear_id] if (row["Src"], row["Tgt"]) == (src, tgt)
    )


def test_canonical_coffee_break_review_uses_minimal_multi_pair_spans() -> None:
    """Retain the two independent contrasts, not their sentence context or suffix alone."""
    # Arrange
    rows = _current_reviewed_rows()

    # Act
    lexical = [
        row
        for row in rows["coffee_break_parts_similar201209_009"]
        if row["Src"] in {"問題", "回避姿勢"}
    ]

    # Assert
    assert [
        (
            row["Src"],
            row["Tgt"],
            row["UnitType"],
            row["SrcStart"],
            row["SrcEnd"],
            row["TgtStart"],
            row["TgtEnd"],
        )
        for row in lexical
    ] == [
        ("問題", "本体", "word", "2", "4", "2", "4"),
        ("回避姿勢", "回避性", "compound", "17", "21", "17", "20"),
    ]


def test_canonical_yahoo_pair_uses_reviewed_word_boundary_and_readings() -> None:
    """Keep source-grounded short readings and the calibrated word classification."""
    # Arrange
    rows = _current_reviewed_rows()

    # Act
    candidate = _pair(rows, "yahooexpert_73e6a209_002", "幸福", "交付金")

    # Assert
    assert (
        candidate["UnitType"],
        candidate["SrcStart"],
        candidate["SrcEnd"],
        candidate["TgtStart"],
        candidate["TgtEnd"],
    ) == ("word", "4", "6", "4", "7")
    assert (candidate["SrcReading"], candidate["TgtReading"]) == (
        "コウフク",
        "コウフキン",
    )
    assert (candidate["SrcReadingStatus"], candidate["TgtReadingStatus"]) == (
        "confirmed",
        "confirmed",
    )


def test_canonical_eichie_pair_remains_a_contextual_phrase_fragment() -> None:
    """Do not trim a phrase fragment to a guessed single word or transfer source notes."""
    # Arrange
    rows = _current_reviewed_rows()

    # Act
    candidate = _pair(rows, "eichie_9568_008", "聞き分け", "父は毛")

    # Assert
    assert (candidate["UnitType"], candidate["SrcStart"], candidate["SrcEnd"]) == (
        "phrase",
        "0",
        "4",
    )
    assert (candidate["TgtStart"], candidate["TgtEnd"]) == ("0", "3")
    assert candidate["SrcReading"] == "キキワケ"
    assert candidate["TgtReading"] == "チチワケ"
    assert json.loads(candidate["SrcQualifier"]) == []


def test_proper_name_word_pair_keeps_shared_suffix_and_full_surfaces() -> None:
    """Do not split shared 橋 from the proper-name contrast 三角橋/参宮橋."""
    # Arrange
    rows = _current_reviewed_rows()

    # Act
    candidate = _pair(rows, "AcrugLVnrLE_024", "三角橋", "参宮橋")

    # Assert
    assert (
        candidate["UnitType"],
        candidate["SrcReading"],
        candidate["TgtReading"],
    ) == (
        "word",
        "みすみばし",
        "さんぐうばし",
    )
    assert json.loads(candidate["SrcQualifier"]) == [
        "東北沢の公式地名読み。原Tipsのさんかくばしとは不一致。実際の発話は未確認"
    ]


def test_recorded_phrase_contrasts_do_not_enter_lexical_exports_as_word() -> None:
    """Known contextual examples remain outside the lexical group after calibration."""
    # Arrange
    rows = _current_reviewed_rows()
    expected = {
        ("ape_news_25286_009", "まだ好きだからあー", "マザーフッカー", "phrase"),
        ("coffee_break_parts_similar200707_001", "ローマ規程", "まあ、規定", "phrase"),
        (
            "coffee_break_parts_similar201512_001",
            "コンポーネント",
            "根本になる",
            "phrase",
        ),
        ("coffee_break_parts_similar201610_003", "区に対して", "繰り返して", "phrase"),
        ("niftykids_200408100935_003", "一児の", "一時は", "phrase"),
        ("niftykids_200408100935_038", "二度寝しとう", "インドネシア", "phrase"),
        ("plaza_rakuten_biwako1031_001", "の仕方", "した方", "phrase"),
        ("20190115_002", "モデレートな", "戻り得た", "phrase"),
        ("39mag_benesse_16332_004", "多機能", "滝のお", "phrase"),
        ("coffee_break_parts_similar200909_007", "モデル", "も出る", "phrase"),
        ("togetter_193527_003", "藤沢周平", "富士山周辺", "compound"),
    }

    # Act
    actual = {
        (mishear_id, row["Src"], row["Tgt"], row["UnitType"])
        for mishear_id, records in rows.items()
        for row in records
        if any(
            mishear_id == item[0] and (row["Src"], row["Tgt"]) == item[1:3]
            for item in expected
        )
    }

    # Assert
    assert actual == expected


@pytest.mark.parametrize(
    ("mishear_id", "src", "tgt", "full_src", "full_tgt"),
    [
        (
            "yukarionishi_linkedin_001",
            "ボーイスカウト",
            "暴走族",
            "昔、ボーイスカウトだったんです",
            "昔、暴走族だったんです",
        ),
        (
            "audee_670796_001",
            "焼きそば",
            "焼きさば",
            "焼きそばでいい？",
            "焼きさばでいい？",
        ),
        (
            "yomifami_post1501_001",
            "ショートケーキ",
            "消毒液",
            "ショートケーキ持ってきます",
            "消毒液持ってきます",
        ),
        (
            "39mag_benesse_16332_006",
            "さよう",
            "サイ",
            "さようでございますか",
            "サイでございますか",
        ),
        (
            "posfie_OOEDO4_054",
            "レイコ",
            "礼子",
            "レイコください",
            "礼子ください",
        ),
        (
            "benesse_ikuji_184163_005",
            "持てる",
            "モテる",
            "持てるでしょ？",
            "モテるでしょ？",
        ),
        (
            "syunkon_12835221992_013",
            "誤って",
            "謝って",
            "誤って転落",
            "謝って転落",
        ),
    ],
    ids=[
        "yukarionishi-scouting",
        "audee-yakisoba",
        "yomifami-cake",
        "benesse-sayou",
        "posfie-reiko",
        "benesse-moteru",
        "syunkon-ayamatte",
    ],
)
def test_minimal_lexical_units_are_selected_instead_of_full_shared_context(
    mishear_id: str,
    src: str,
    tgt: str,
    full_src: str,
    full_tgt: str,
) -> None:
    """Do not classify full contextual comparisons as lexical when a smaller contrast exists."""
    # Arrange
    rows = _current_reviewed_rows()
    # Act
    candidate = _pair(rows, mishear_id, src, tgt)
    full_pair = next(
        (
            row
            for row in rows[mishear_id]
            if (row["Src"], row["Tgt"]) == (full_src, full_tgt)
        ),
        None,
    )

    # Assert
    assert candidate["UnitType"] in {"word", "compound"}
    if full_pair is not None:
        assert full_pair["UnitType"] not in {"word", "compound"}
