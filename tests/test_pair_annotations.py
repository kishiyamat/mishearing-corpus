from __future__ import annotations

import pytest

from corpus_api.annotations import (
    AnnotatedText,
    Annotation,
    parse_annotation,
    render_annotation,
)


def test_parses_multiple_typed_annotations_on_same_span() -> None:
    """Keep repeated meanings and qualifiers attached to their single target span."""
    result = parse_annotation(
        "|銀行《ぎんこう》【意味：金融機関】【意味：銀行の建物】【識別：固有名詞】"
    )

    assert result == AnnotatedText(
        surface="銀行",
        annotations=(
            Annotation(0, 2, "ぎんこう", ("金融機関", "銀行の建物"), ("固有名詞",)),
        ),
        original_spans=((1, 2), (2, 3)),
    )


def test_parses_ruby_only_and_adjacent_annotated_spans() -> None:
    """Ruby needs neither a typed note nor separating literal text."""
    ruby_only = parse_annotation("|下手《したて》")
    adjacent = parse_annotation("|熊谷《くまがや》|反町《そりまち》")

    assert ruby_only.surface == "下手"
    assert ruby_only.annotations == (Annotation(0, 2, "したて"),)
    assert adjacent.surface == "熊谷反町"
    assert adjacent.annotations == (
        Annotation(0, 2, "くまがや"),
        Annotation(2, 4, "そりまち"),
    )


@pytest.mark.parametrize("reading", ["かな", "カナ", "カー", "ゝゞヽヾ", ""])
def test_accepts_kana_readings(reading: str) -> None:
    """Accept kana marks and explicitly unknown readings."""
    parsed = parse_annotation(f"|語《{reading}》")

    assert parsed.annotations == (Annotation(0, 1, reading),)


def test_rejects_non_kana_reading_from_parser_and_renderer() -> None:
    """Both input directions reject semantics and whitespace in reading fields."""
    with pytest.raises(ValueError):
        parse_annotation("|語《帰宅》")
    with pytest.raises(ValueError):
        render_annotation("語", (Annotation(0, 1, "帰宅"),))
    with pytest.raises(ValueError):
        render_annotation("語", (Annotation(0, 1, "か な"),))


def test_typed_notes_allow_escaped_reserved_characters_and_render_them() -> None:
    """Escape literal annotation delimiters inside note values on roundtrip."""
    parsed = parse_annotation(r"|語《ご》【意味：A\【B\】C\|D\\E】")
    annotation = Annotation(0, 1, "ご", ("A【B】C|D\\E",), ())

    assert parsed.annotations == (annotation,)
    rendered = render_annotation("語", (annotation,))
    assert rendered == r"|語《ご》【意味：A\【B\】C\|D\\E】"
    assert parse_annotation(rendered).annotations == (annotation,)


def test_meaning_only_unknown_reading_empty_and_offsets() -> None:
    """Unknown pronunciation does not erase meaning or raw source offsets."""
    result = parse_annotation("前|語《》【意味：内容】後")

    assert result.surface == "前語後"
    assert result.annotations == (Annotation(1, 2, "", ("内容",), ()),)
    assert result.original_spans == ((0, 1), (2, 3), (12, 13))


def test_parses_explicit_issue_example_without_confusing_unmarked_brackets() -> None:
    """Escaped spoken punctuation remains surface, not semantic annotation."""
    source = "\\《500mL\\》ソルデム３Ａ注に|追加《ついか》【意味：加えること】。"
    result = parse_annotation(source)

    assert result.surface == "《500mL》ソルデム３Ａ注に追加。"
    assert result.annotations == (Annotation(15, 17, "ついか", ("加えること",), ()),)
    assert result.original_spans[0] == (0, 2)
    assert result.original_spans[8] == (10, 11)


def test_escapes_reserved_characters_and_render_round_trips() -> None:
    """Every reserved literal character survives rendering and parsing."""
    surface = "\\|《》【】"
    rendered = render_annotation(surface, ())

    assert rendered == "\\\\\\|\\《\\》\\【\\】"
    assert parse_annotation(rendered).surface == surface
    assert render_annotation(parse_annotation(rendered).surface, ()) == rendered


def test_render_rejects_invalid_spans_and_overlap() -> None:
    """Generated displays must not silently select empty, overlapping or invalid spans."""
    with pytest.raises(ValueError):
        render_annotation("語", (Annotation(-1, 1, "ご"),))
    with pytest.raises(ValueError):
        render_annotation("語", (Annotation(0, 2, "ご"),))
    with pytest.raises(ValueError):
        render_annotation("語", (Annotation(0, 1, "ご"), Annotation(0, 1, "か")))


@pytest.mark.parametrize(
    "source",
    [
        "|語《ご",
        "|語《ご【意味：意味】",
        "【意味：未接続】",
        "|語《ご|字《じ》",
        "|語《ご\n》",
        "\\x",
        "|語《ご》【未知：値】",
        "|語【意味：値】《ご》",
    ],
)
def test_rejects_malformed_or_unclassified_annotations(source: str) -> None:
    """Malformed explicit annotation is an error rather than silently plain text."""
    with pytest.raises(ValueError):
        parse_annotation(source)


def test_legacy_parentheses_are_literal_and_flagged() -> None:
    """Unclassified parentheses remain in the original comparison surface."""
    result = parse_annotation("語（ご）(word)")

    assert result.surface == "語（ご）(word)"
    assert result.annotations == ()
    assert result.legacy_parentheses is True
