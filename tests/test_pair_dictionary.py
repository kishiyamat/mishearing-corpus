"""Inspect actual dictionary alternatives instead of accepting an LLM reading guess."""

import shutil

import pytest

from corpus_api.dictionary import dictionary_entries


@pytest.mark.skipif(shutil.which("mecab") is None, reason="optional MeCab CLI missing")
def test_dictionary_returns_all_whole_word_known_entries() -> None:
    """A source citation can name the exact installed dictionary and lexical entry."""
    # Arrange
    surface = "筋肉"

    # Act
    result = dictionary_entries(surface)

    # Assert
    assert result["surface"] == surface
    assert {row["reading"] for row in result["entries"]} == {"キンニク"}
    assert len(result["dictionary_sha256"]) == 64
    assert all(row["surface"] == surface for row in result["entries"])


@pytest.mark.skipif(shutil.which("mecab") is None, reason="optional MeCab CLI missing")
def test_dictionary_does_not_turn_unknown_letters_into_confirmed_readings() -> None:
    """A tokenizer's unknown-word fallback is not a dictionary reading citation."""
    # Arrange
    surface = "XYZQQVnotaword"

    # Act
    result = dictionary_entries(surface)

    # Assert
    assert result["entries"] == []


@pytest.mark.skipif(shutil.which("mecab") is None, reason="optional MeCab CLI missing")
def test_dictionary_exposes_name_ambiguity_instead_of_choosing_one() -> None:
    """A common name has multiple dictionary readings that require context."""
    # Arrange
    surface = "熊谷"

    # Act
    result = dictionary_entries(surface)

    # Assert
    readings = {entry["reading"] for entry in result["entries"]}
    assert {"クマガヤ", "クマガイ"}.issubset(readings)
    assert len(readings) > 1


@pytest.mark.parametrize("surface", ["", "語\n語", "語\t語"])
def test_dictionary_rejects_multiline_or_empty_queries(surface: str) -> None:
    """Keep command framing independent of corpus input text."""
    # Act / Assert
    with pytest.raises(ValueError):
        dictionary_entries(surface)
