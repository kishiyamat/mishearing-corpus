"""Parse and render inline, span-based annotations for corpus text."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

_RESERVED = "\\|《》【】"
_OPEN_TYPED = "【"
_CLOSE_TYPED = "】"


@dataclass(frozen=True)
class Annotation:
    """Typed information attached to a half-open surface character span."""

    start: int
    end: int
    reading: str = ""
    meanings: tuple[str, ...] = ()
    qualifiers: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnnotatedText:
    """Surface text, annotations, and per-character original source spans."""

    surface: str
    annotations: tuple[Annotation, ...]
    original_spans: tuple[tuple[int, int], ...]
    legacy_parentheses: bool = False


class _Parser:
    """Track notation state and map decoded surface characters to original offsets."""

    def __init__(self, text: str) -> None:
        """Start parsing without altering the caller's original string."""
        self.text = text
        self.index = 0
        self.surface: list[str] = []
        self.spans: list[tuple[int, int]] = []
        self.annotations: list[Annotation] = []
        self.legacy_parentheses = False

    def parse(self) -> AnnotatedText:
        """Consume the whole input, rejecting malformed or unattached annotation syntax."""
        while self.index < len(self.text):
            char = self.text[self.index]
            if char == "\\":
                self._append_escaped()
            elif char == "|":
                self._parse_annotated_span()
            elif char in "《》【】":
                raise ValueError(
                    f"unescaped reserved character {char!r} at {self.index}"
                )
            else:
                self._append_literal()
        return AnnotatedText(
            "".join(self.surface),
            tuple(self.annotations),
            tuple(self.spans),
            self.legacy_parentheses,
        )

    def _append_literal(self) -> None:
        """Keep one literal character and its original source position."""
        source_index = self.index
        char = self.text[self.index]
        if char in "（）()":
            self.legacy_parentheses = True
        self.surface.append(char)
        self.spans.append((source_index, source_index + 1))
        self.index += 1

    def _append_escaped(self) -> None:
        """Decode one reserved character while preserving its two-character raw span."""
        start = self.index
        if start + 1 >= len(self.text) or self.text[start + 1] not in _RESERVED:
            raise ValueError(f"invalid escape at {start}")
        self.surface.append(self.text[start + 1])
        self.spans.append((start, start + 2))
        self.index += 2

    def _parse_annotated_span(self) -> None:
        """Read one surface/ruby unit and any following ordered typed notes."""
        self.index += 1
        span_start = len(self.surface)
        self._read_surface_until("《", allow_annotations=False)
        span_end = len(self.surface)
        if span_start == span_end:
            raise ValueError("annotated surface must not be empty")
        self.index += 1  # opening 《
        reading = self._read_reading()
        if self.index >= len(self.text) or self.text[self.index] != "》":
            raise ValueError("unclosed reading")
        self.index += 1

        meanings: list[str] = []
        qualifiers: list[str] = []
        while self.index < len(self.text) and self.text[self.index] == _OPEN_TYPED:
            kind, value = self._read_typed_note()
            if kind == "意味":
                meanings.append(value)
            else:
                qualifiers.append(value)
        self.annotations.append(
            Annotation(
                span_start, span_end, reading, tuple(meanings), tuple(qualifiers)
            )
        )

    def _read_surface_until(self, delimiter: str, *, allow_annotations: bool) -> None:
        """Read surface characters up to the ruby opener, checking reserved syntax."""
        while self.index < len(self.text) and self.text[self.index] != delimiter:
            char = self.text[self.index]
            if char == "\\":
                self._append_escaped()
            elif char == "|" or char in "》【】":
                if not allow_annotations:
                    raise ValueError(
                        f"unexpected reserved character {char!r} at {self.index}"
                    )
                self._append_literal()
            else:
                self._append_literal()
        if self.index >= len(self.text):
            raise ValueError(f"missing delimiter {delimiter!r}")

    def _read_reading(self) -> str:
        """Read a kana-only reading through its closing guillemet."""
        result: list[str] = []
        while self.index < len(self.text) and self.text[self.index] != "》":
            char = self.text[self.index]
            if not _is_kana(char):
                raise ValueError(f"invalid character in reading at {self.index}")
            result.append(char)
            self.index += 1
        if self.index >= len(self.text):
            raise ValueError("unclosed reading")
        if not result:
            # Empty reading is valid and denotes unknown pronunciation.
            return ""
        return "".join(result)

    def _read_typed_note(self) -> tuple[str, str]:
        """Read a typed note while decoding escapes in its value."""
        start = self.index
        cursor = start + 1
        content: list[str] = []
        while cursor < len(self.text) and self.text[cursor] != _CLOSE_TYPED:
            char = self.text[cursor]
            if char == "\\":
                if (
                    cursor + 1 >= len(self.text)
                    or self.text[cursor + 1] not in _RESERVED
                ):
                    raise ValueError(f"invalid escape at {cursor}")
                content.append(self.text[cursor + 1])
                cursor += 2
                continue
            if char in "【》":
                raise ValueError("nested or malformed typed note")
            content.append(char)
            cursor += 1
        if cursor >= len(self.text):
            raise ValueError("unclosed typed note")
        value_text = "".join(content)
        if value_text.startswith("意味："):
            kind, value = "意味", value_text[len("意味：") :]
        elif value_text.startswith("識別："):
            kind, value = "識別", value_text[len("識別：") :]
        else:
            raise ValueError("unknown or malformed typed note")
        if not value:
            raise ValueError("typed note value must be nonempty")
        self.index = cursor + 1
        return kind, value


def parse_annotation(text: str) -> AnnotatedText:
    """Parse inline annotation notation, retaining source offsets per character."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _Parser(text).parse()


def _validate_annotations(surface: str, annotations: tuple[Annotation, ...]) -> None:
    """Check span ordering and field values before rendering."""
    previous_end = 0
    for annotation in annotations:
        if not isinstance(annotation, Annotation):
            raise TypeError("annotations must contain Annotation values")
        if not (0 <= annotation.start < annotation.end <= len(surface)):
            raise ValueError("annotation span is empty or outside the surface")
        if annotation.start < previous_end:
            raise ValueError("annotation spans must be ordered and non-overlapping")
        if not isinstance(annotation.reading, str):
            raise TypeError("reading must be a string")
        if any(not item for item in (*annotation.meanings, *annotation.qualifiers)):
            raise ValueError("typed note values must not be empty")
        if any(not _is_kana(char) for char in annotation.reading):
            raise ValueError("reading must contain only kana")
        previous_end = annotation.end


def _escape(value: str) -> str:
    """Escape reserved syntax characters in literal surface or note text."""
    return "".join("\\" + char if char in _RESERVED else char for char in value)


def _is_kana(char: str) -> bool:
    """Return whether a character is hiragana, katakana, or a kana mark."""
    codepoint = ord(char)
    if char == "ー" or char in "ゝゞヽヾ〱〲〳〴〵":
        return True
    if unicodedata.name(char, "").startswith(("HIRAGANA ", "KATAKANA ")):
        return True
    return 0x1B000 <= codepoint <= 0x1B16F


def render_annotation(surface: str, annotations: tuple[Annotation, ...]) -> str:
    """Render valid surface spans into the canonical inline notation."""
    if not isinstance(surface, str):
        raise TypeError("surface must be a string")
    _validate_annotations(surface, annotations)
    by_start = {annotation.start: annotation for annotation in annotations}
    output: list[str] = []
    index = 0
    while index < len(surface):
        annotation = by_start.get(index)
        if annotation is None:
            output.append(_escape(surface[index]))
            index += 1
            continue
        output.append("|")
        output.append(_escape(surface[annotation.start : annotation.end]))
        output.append(f"《{annotation.reading}》")
        output.extend(f"【意味：{_escape(item)}】" for item in annotation.meanings)
        output.extend(f"【識別：{_escape(item)}】" for item in annotation.qualifiers)
        index = annotation.end
    return "".join(output)
