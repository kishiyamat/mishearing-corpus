"""Source-bound, two-stage pair extraction; machine proposals are never approvals."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath
from typing import Literal, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from git import Blob, Repo
from pydantic import BaseModel, ConfigDict, Field

from .annotations import AnnotatedText, Annotation, parse_annotation, render_annotation
from .dataset import CorpusSnapshot, _rows, canonical_json
from .models import CSV_FIELDS, Record

EXTRACTOR_VERSION = "pairs-v2.3"
TOKENIZER_SETTINGS = "mecab -Ochasen; difflib autojunk=False; no vocabulary filter"
Tokenizer = Callable[[str], list[tuple[int, int]]]
PAIR_FIELDS = (
    "PairID",
    "MishearID",
    "OriginalHash",
    "SourceFile",
    "URL",
    "Language",
    "RecordValidity",
    "SrcOriginal",
    "TgtOriginal",
    "Src",
    "Tgt",
    "SrcReading",
    "TgtReading",
    "SrcReadingStatus",
    "TgtReadingStatus",
    "SrcMeaning",
    "TgtMeaning",
    "SrcQualifier",
    "TgtQualifier",
    "SrcAnnotated",
    "TgtAnnotated",
    "SrcStart",
    "SrcEnd",
    "TgtStart",
    "TgtEnd",
    "UnitType",
    "Flags",
    "ReviewStatus",
    "TargetDecision",
    "Reviewer",
    "ReviewedAt",
    "Evidence",
    "Reason",
    "ExtractorVersion",
    "SupersedesPairID",
)


class Override(BaseModel):
    """Replace one explicitly reviewed original span, retaining its literal surface."""

    model_config = ConfigDict(extra="forbid", strict=True)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    surface: str
    reading: str = ""
    meanings: list[str] = Field(default_factory=list)
    qualifiers: list[str] = Field(default_factory=list)


class PairSpan(BaseModel):
    """Select independent source and target ranges in original Unicode offsets."""

    model_config = ConfigDict(extra="forbid", strict=True)
    src_start: int = Field(ge=0)
    src_end: int = Field(ge=0)
    tgt_start: int = Field(ge=0)
    tgt_end: int = Field(ge=0)
    unit_type: Literal["word", "particle-inclusive", "compound", "phrase"]
    PairID: str = ""
    SupersedesPairID: str = ""


class TokenSpans(list[tuple[int, int]]):
    """Keep token offsets list-compatible while attaching corresponding POS labels.

    Construct with parallel span and tag sequences, for example
    ``TokenSpans([(0, 2)], ["名詞"])``. Existing callers can still iterate or index
    the instance as a list of source offset pairs; extraction can also inspect
    ``pos_tags`` to classify suffix and particle boundaries.
    """

    def __init__(
        self, spans: Sequence[tuple[int, int]], pos_tags: Sequence[str]
    ) -> None:
        super().__init__(spans)
        if len(self) != len(pos_tags):
            raise ValueError("each MeCab token span requires one POS tag")
        self.pos_tags = tuple(pos_tags)


class RecordReview(BaseModel):
    """One deliberate review covers all selected units and zero-candidate records."""

    model_config = ConfigDict(extra="forbid", strict=True)
    MishearID: str
    OriginalHash: str
    Reviewer: str = Field(min_length=1)
    ReviewedAt: str
    Evidence: str = Field(min_length=1)
    Reason: str = Field(min_length=1)
    Status: Literal["reviewed", "pending"]
    TargetDecision: Literal["include", "exclude", "undecided"]
    RecordValidity: Literal[
        "documented", "illustrative", "production", "visual", "unclear"
    ] = "unclear"
    SrcAnnotations: list[Override] = Field(default_factory=list)
    TgtAnnotations: list[Override] = Field(default_factory=list)
    PairSpans: list[PairSpan]


REVIEW_FIELDS = tuple(RecordReview.model_fields)
REVIEW_JSON_FIELDS = ("SrcAnnotations", "TgtAnnotations", "PairSpans")


def extractor_hash() -> str:
    """Identify the actual extraction/parser code, including uncommitted edits."""
    root = Path(__file__).parent
    payload = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ("pair_workflow.py", "annotations.py")
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def load_reviews(payload: bytes) -> list[dict[str, object]]:
    """Read the canonical annotation CSV; nested span columns contain JSON arrays."""
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), strict=True)
    if reader.fieldnames != list(REVIEW_FIELDS):
        raise ValueError("unsupported annotation CSV columns")
    reviews: list[dict[str, object]] = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("malformed annotation CSV row")
        value: dict[str, object] = dict(row)
        for field in REVIEW_JSON_FIELDS:
            value[field] = json.loads(row[field])
        reviews.append(RecordReview.model_validate(value).model_dump())
    return reviews


def review_csv(decisions: list[dict[str, object]]) -> bytes:
    """Serialize structured decisions into the single editable annotation table."""
    values: list[dict[str, object]] = []
    for decision in sorted(decisions, key=lambda row: str(row["MishearID"])):
        value = RecordReview.model_validate(decision).model_dump()
        for field in REVIEW_JSON_FIELDS:
            value[field] = canonical_json(value[field])
        values.append(value)
    return csv_bytes(values, REVIEW_FIELDS)


def pair_table_schema() -> dict[str, object]:
    """Generate the flat CSV Table Schema from the same fixed output columns."""
    enums = {
        "UnitType": ["word", "particle-inclusive", "compound", "phrase"],
        "ReviewStatus": ["draft", "pending", "reviewed"],
        "TargetDecision": ["include", "exclude", "undecided"],
        "RecordValidity": [
            "documented",
            "illustrative",
            "production",
            "visual",
            "unclear",
        ],
        "SrcReadingStatus": ["proposed", "confirmed", "unknown"],
        "TgtReadingStatus": ["proposed", "confirmed", "unknown"],
    }
    arrays = {"SrcMeaning", "TgtMeaning", "SrcQualifier", "TgtQualifier", "Flags"}
    positions = {"SrcStart", "SrcEnd", "TgtStart", "TgtEnd"}
    fields: list[dict[str, object]] = []
    for name in PAIR_FIELDS:
        field: dict[str, object] = {
            "name": name,
            "type": "array"
            if name in arrays
            else "integer"
            if name in positions
            else "string",
        }
        constraints: dict[str, object] = {}
        if name in enums:
            constraints["enum"] = enums[name]
        if name in positions:
            constraints["minimum"] = 0
        if name in ("PairID", "MishearID", "OriginalHash"):
            constraints["required"] = True
        if constraints:
            field["constraints"] = constraints
        fields.append(field)
    return {"fields": fields, "primaryKey": "PairID", "missingValues": [""]}


def original_hash(record: Mapping[str, str]) -> str:
    """Bind all original eleven string fields, not a row number or file location."""
    payload = {field: record[field] for field in CSV_FIELDS}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def originals_hash(snapshot: CorpusSnapshot) -> str:
    """Fingerprint original fields independently of unrelated API/schema commits."""
    rows = [
        {
            "id": record.MishearID,
            "path": record.source_file,
            "hash": original_hash(
                {key: str(getattr(record, key)) for key in CSV_FIELDS}
            ),
        }
        for record in snapshot.records
    ]
    return hashlib.sha256(canonical_json(rows).encode()).hexdigest()


def _reading_key(reading: str) -> str:
    """Compare kana scripts without changing the stored evidence-backed reading."""
    return "".join(
        chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c
        for c in unicodedata.normalize("NFKC", reading)
    )


def working_snapshot(root: Path, committed: CorpusSnapshot) -> CorpusSnapshot:
    """Read local originals explicitly for pre-commit checks, never for HTTP serving."""
    records: dict[str, Record] = {}
    for path in sorted((root / "data/mishearing").rglob("*.csv")):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("working-tree originals cannot be external symlinks")
        relative = path.relative_to(root).as_posix()
        for raw in _rows(relative, path.read_bytes(), CSV_FIELDS):
            identifier = raw["MishearID"]
            if not identifier or identifier in records:
                raise ValueError("empty or duplicate working-tree MishearID")
            records[identifier] = Record.model_validate(
                raw
                | {
                    "source_file": relative,
                    "source": path.parent.relative_to(
                        root / "data/mishearing"
                    ).as_posix(),
                }
            )
    if not records:
        raise ValueError("no working-tree originals")
    return CorpusSnapshot(
        committed.info, tuple(records[key] for key in sorted(records)), records
    )


def mecab_tokens(text: str) -> TokenSpans:
    """Use MeCab's public Chasen output to align source offsets and POS tags."""
    if not text:
        return TokenSpans([], [])
    result = subprocess.run(
        ["mecab", "-Ochasen"],
        input=text,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=30,
    )
    cursor = 0
    offsets: list[tuple[int, int]] = []
    pos_tags: list[str] = []
    for line in result.stdout.splitlines():
        if not line or line == "EOS":
            continue
        fields = line.split("\t")
        if len(fields) < 4:
            raise ValueError("MeCab Chasen output is missing token features")
        token, pos = fields[0], fields[3]
        start = text.find(token, cursor)
        if start < 0 or text[cursor:start].strip():
            raise ValueError("MeCab tokens do not align with original surface")
        cursor = start + len(token)
        if token.isspace():
            continue
        offsets.append((start, start + len(token)))
        pos_tags.append(pos)
    if text[cursor:].strip():
        raise ValueError("MeCab omitted non-whitespace source text")
    return TokenSpans(offsets, pos_tags)


def _prepared(text: str, overrides: Sequence[Override] = ()) -> AnnotatedText:
    """Apply reviewed legacy-note separation while mapping every surface character."""
    if not overrides:
        return parse_annotation(text)
    surface = ""
    annotations: list[Annotation] = []
    positions: list[tuple[int, int]] = []
    cursor = 0
    for override in overrides:
        if not cursor <= override.start < override.end <= len(text):
            raise ValueError("overlapping or out-of-range original annotation")
        prefix = parse_annotation(text[cursor : override.start])
        annotations.extend(
            replace(a, start=a.start + len(surface), end=a.end + len(surface))
            for a in prefix.annotations
        )
        surface += prefix.surface
        positions.extend((s + cursor, e + cursor) for s, e in prefix.original_spans)
        start = text.find(override.surface, override.start, override.end)
        if not override.surface or start < 0:
            raise ValueError("reviewed surface must occur within its original span")
        annotation = Annotation(
            len(surface),
            len(surface) + len(override.surface),
            override.reading,
            tuple(override.meanings),
            tuple(override.qualifiers),
        )
        # Renderer and parser share the same typed-note and reading validation.
        parse_annotation(
            render_annotation(
                override.surface,
                (replace(annotation, start=0, end=len(override.surface)),),
            )
        )
        annotations.append(annotation)
        surface += override.surface
        positions.extend(
            (i, i + 1) for i in range(start, start + len(override.surface))
        )
        cursor = override.end
    suffix = parse_annotation(text[cursor:])
    annotations.extend(
        replace(a, start=a.start + len(surface), end=a.end + len(surface))
        for a in suffix.annotations
    )
    surface += suffix.surface
    positions.extend((s + cursor, e + cursor) for s, e in suffix.original_spans)
    return AnnotatedText(
        surface,
        tuple(annotations),
        tuple(positions),
        any(c in surface for c in "()（）"),
    )


def _slice(
    text: AnnotatedText, start: int, end: int
) -> tuple[str, tuple[Annotation, ...]]:
    """Select a raw original range without allowing partial annotation boundaries."""
    indexes = [
        i for i, (s, e) in enumerate(text.original_spans) if start <= s and e <= end
    ]
    if not indexes:
        return "", ()
    first, last = indexes[0], indexes[-1] + 1
    selected: list[Annotation] = []
    for annotation in text.annotations:
        if annotation.start < last and annotation.end > first:
            if annotation.start < first or annotation.end > last:
                raise ValueError("candidate cuts through an explicitly annotated unit")
            selected.append(
                replace(
                    annotation,
                    start=annotation.start - first,
                    end=annotation.end - first,
                )
            )
    return text.surface[first:last], tuple(selected)


def _side_fields(
    prefix: str, text: AnnotatedText, start: int, end: int
) -> dict[str, str]:
    """Derive display and known readings only from structured, selected annotations."""
    surface, annotations = _slice(text, start, end)
    whole = next(
        (a for a in annotations if a.start == 0 and a.end == len(surface)), None
    )
    reading = whole.reading if whole else ""
    return {
        prefix: surface,
        prefix + "Reading": reading,
        prefix + "ReadingStatus": "confirmed" if reading else "unknown",
        prefix + "Meaning": canonical_json(
            [m for a in annotations for m in a.meanings]
        ),
        prefix + "Qualifier": canonical_json(
            [q for a in annotations for q in a.qualifiers]
        ),
        prefix + "Annotated": render_annotation(surface, annotations),
        prefix + "Start": str(start),
        prefix + "End": str(end),
    }


def _pair(
    record: Mapping[str, str],
    path: str,
    src: AnnotatedText,
    tgt: AnnotatedText,
    span: PairSpan,
    flags: list[str],
) -> dict[str, str]:
    """Create a provenance-complete candidate; defaults cannot imply approval."""
    for identifier in (span.PairID, span.SupersedesPairID):
        if identifier and str(UUID(identifier)) != identifier:
            raise ValueError("retained/superseded PairID must be a canonical UUID")
    if not (
        0 <= span.src_start <= span.src_end <= len(record["Src"])
        and 0 <= span.tgt_start <= span.tgt_end <= len(record["Tgt"])
    ):
        raise ValueError("pair span outside original")
    digest = original_hash(record)
    identity = [
        record["MishearID"],
        digest,
        span.src_start,
        span.src_end,
        span.tgt_start,
        span.tgt_end,
        span.unit_type,
    ]
    row = dict.fromkeys(PAIR_FIELDS, "") | {
        "PairID": span.PairID or str(uuid5(NAMESPACE_URL, canonical_json(identity))),
        "MishearID": record["MishearID"],
        "OriginalHash": digest,
        "SourceFile": path,
        "URL": record["URL"],
        "Language": record["Language"],
        "RecordValidity": "unclear",
        "SrcOriginal": record["Src"],
        "TgtOriginal": record["Tgt"],
        "UnitType": span.unit_type,
        "Flags": canonical_json(flags),
        "ReviewStatus": "draft",
        "TargetDecision": "undecided",
        "ExtractorVersion": EXTRACTOR_VERSION,
        "SupersedesPairID": span.SupersedesPairID,
    }
    row.update(_side_fields("Src", src, span.src_start, span.src_end))
    row.update(_side_fields("Tgt", tgt, span.tgt_start, span.tgt_end))
    for side in ("Src", "Tgt"):
        if row[side + "Reading"]:
            row[side + "ReadingStatus"] = "proposed"
    return row


def _audit(
    record: Mapping[str, str], path: str, count: int, zero_reason: str = ""
) -> dict[str, object]:
    """Account for every input, including records producing no machine candidates."""
    return {
        "MishearID": record["MishearID"],
        "OriginalHash": original_hash(record),
        "SourceFile": path,
        "SrcOriginal": record["Src"],
        "TgtOriginal": record["Tgt"],
        "CandidateCount": count,
        "ZeroReason": zero_reason,
        "RecordValidity": "unclear",
        "ReviewStatus": "draft",
        "TargetDecision": "undecided",
        "Reason": "",
    }


def _same_interpretation(src: AnnotatedText, tgt: AnnotatedText) -> bool:
    """Compare surface and typed interpretation, normalizing only reading notation."""
    return src.surface == tgt.surface and [
        replace(a, reading=_reading_key(a.reading)) for a in src.annotations
    ] == [replace(a, reading=_reading_key(a.reading)) for a in tgt.annotations]


def _pos_tags(tokens: list[tuple[int, int]]) -> tuple[str, ...]:
    """Return available tokenizer tags without requiring custom tokenizers to add them."""
    tags = getattr(tokens, "pos_tags", ())
    if not tags:
        return tuple("" for _ in tokens)
    if len(tags) != len(tokens):
        raise ValueError("tokenizer returned mismatched offsets and POS tags")
    return tuple(str(tag) for tag in tags)


def _is_suffix(pos: str) -> bool:
    """Recognize IPADIC suffix categories that cannot stand alone as a lexical contrast."""
    return "接尾" in pos


def _is_particle(pos: str) -> bool:
    """Recognize particles for distinguishing contextual fragments from words."""
    return pos.startswith("助詞")


def _token_surface(
    text: AnnotatedText, spans: list[tuple[int, int]], index: int
) -> str:
    """Return the original surface for one token, independent of its absolute offset."""
    start, end = spans[index]
    return text.surface[start:end]


def extract_record(
    record: Mapping[str, str], path: str, tokenizer: Tokenizer = mecab_tokens
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Propose token or interpretation contrasts without treating homophony as identity."""
    flags: list[str] = []
    try:
        src, tgt = _prepared(record["Src"]), _prepared(record["Tgt"])
    except ValueError as error:
        audit = _audit(record, path, 0, "annotation_syntax_error")
        audit["Reason"] = str(error)
        return [], audit
    if src.legacy_parentheses or tgt.legacy_parentheses:
        flags.append("legacy_parentheses")
    if _same_interpretation(src, tgt):
        return [], _audit(record, path, 0, "same_surface")
    src_tokens, tgt_tokens = tokenizer(src.surface), tokenizer(tgt.surface)
    src_pos, tgt_pos = _pos_tags(src_tokens), _pos_tags(tgt_tokens)
    matcher = SequenceMatcher(
        None,
        [src.surface[s:e] for s, e in src_tokens],
        [tgt.surface[s:e] for s, e in tgt_tokens],
        autojunk=False,
    )

    def raw_bounds(
        text: AnnotatedText, offsets: list[tuple[int, int]], start: int, end: int
    ) -> tuple[int, int]:
        """Map token bounds back to raw input, supporting zero-width insertions."""
        if start == end:
            point = (
                text.original_spans[offsets[start][0]][0]
                if start < len(offsets)
                else (text.original_spans[-1][1] if text.original_spans else 0)
            )
            return point, point
        return text.original_spans[offsets[start][0]][0], text.original_spans[
            offsets[end - 1][1] - 1
        ][1]

    rows: list[dict[str, str]] = []
    for op, i, j, k, l in matcher.get_opcodes():
        if op == "equal":
            continue
        left_i, right_i, left_k, right_k = i, j, k, l
        expanded_left_suffix = False
        expanded_right_nominal_suffix = False
        expanded_right_verb_ending = False
        # A suffix-only mismatch such as 姿勢/性 needs its shared lexical stem.
        if (
            ((i < j and _is_suffix(src_pos[i])) or (k < l and _is_suffix(tgt_pos[k])))
            and i > 0
            and k > 0
            and _token_surface(src, src_tokens, i - 1)
            == _token_surface(tgt, tgt_tokens, k - 1)
            and not _is_particle(src_pos[i - 1])
        ):
            left_i -= 1
            left_k -= 1
            expanded_left_suffix = True
        # A shared suffix can belong to both proper-name alternatives (三角橋/参宮橋).
        if (
            right_i < len(src_tokens)
            and right_k < len(tgt_tokens)
            and _token_surface(src, src_tokens, right_i)
            == _token_surface(tgt, tgt_tokens, right_k)
            and _is_suffix(src_pos[right_i])
            and _is_suffix(tgt_pos[right_k])
        ):
            right_i += 1
            right_k += 1
            expanded_right_nominal_suffix = True
        # Shared inflection auxiliaries are part of the contrasting full forms.
        if (
            i < j
            and k < l
            and right_i < len(src_tokens)
            and right_k < len(tgt_tokens)
            and _token_surface(src, src_tokens, right_i)
            == _token_surface(tgt, tgt_tokens, right_k)
            and src_pos[right_i].startswith("助動詞")
            and tgt_pos[right_k].startswith("助動詞")
            and src_pos[j - 1].startswith(("動詞", "形容詞"))
            and tgt_pos[l - 1].startswith(("動詞", "形容詞"))
        ):
            right_i += 1
            right_k += 1
            expanded_right_verb_ending = True
        # In matched te-forms, て/で is required to express the verb form; keep it
        # with the contrasting verb stems rather than emitting non-independent stems.
        if (
            right_i < len(src_tokens)
            and right_k < len(tgt_tokens)
            and right_i > left_i
            and right_k > left_k
            and _token_surface(src, src_tokens, right_i)
            == _token_surface(tgt, tgt_tokens, right_k)
            and _token_surface(src, src_tokens, right_i) in {"て", "で"}
            and src_pos[right_i].startswith("助詞-接続助詞")
            and tgt_pos[right_k].startswith("助詞-接続助詞")
            and src_pos[right_i - 1].startswith("動詞-")
            and tgt_pos[right_k - 1].startswith("動詞-")
        ):
            right_i += 1
            right_k += 1
            expanded_right_verb_ending = True
        s, e = raw_bounds(src, src_tokens, left_i, right_i)
        t, u = raw_bounds(tgt, tgt_tokens, left_k, right_k)
        source_tags = src_pos[left_i:right_i]
        target_tags = tgt_pos[left_k:right_k]
        has_particle = any(map(_is_particle, (*source_tags, *target_tags)))
        if expanded_left_suffix:
            unit_type: Literal["word", "particle-inclusive", "compound", "phrase"] = (
                "compound"
            )
        elif expanded_right_nominal_suffix:
            unit_type = "compound"
        elif expanded_right_verb_ending:
            unit_type = "word"
        elif has_particle:
            larger = source_tags if len(source_tags) > len(target_tags) else target_tags
            smaller = (
                target_tags if len(source_tags) > len(target_tags) else source_tags
            )
            only_particle_extension = (
                abs(len(source_tags) - len(target_tags)) == 1
                and len(larger) == 2
                and len(smaller) == 1
                and sum(_is_particle(tag) for tag in larger) == 1
                and all(
                    tag.startswith("名詞")
                    for tag in (*[t for t in larger if not _is_particle(t)], *smaller)
                )
            )
            unit_type = "particle-inclusive" if only_particle_extension else "phrase"
        elif all(
            not tag or tag.startswith("名詞") for tag in source_tags + target_tags
        ):
            unit_type = (
                "word" if len(source_tags) == len(target_tags) == 1 else "compound"
            )
        elif all(
            len(tags) == 1
            and (
                not tags[0] or tags[0].startswith(("動詞-自立", "形容詞-自立", "副詞-"))
            )
            for tags in (source_tags, target_tags)
        ):
            unit_type = "word"
        else:
            unit_type = "phrase"
        span = PairSpan(
            src_start=s,
            src_end=e,
            tgt_start=t,
            tgt_end=u,
            unit_type=unit_type,
        )
        try:
            rows.append(
                _pair(
                    record, path, src, tgt, span, flags + ["boundary_review_required"]
                )
            )
        except ValueError:
            flags.append("annotated_unit_boundary")
    full = PairSpan(
        src_start=0,
        src_end=len(record["Src"]),
        tgt_start=0,
        tgt_end=len(record["Tgt"]),
        unit_type="phrase",
    )
    context = _pair(record, path, src, tgt, full, flags + ["context_alternative"])
    if not any((r["Src"], r["Tgt"]) == (context["Src"], context["Tgt"]) for r in rows):
        rows.append(context)
    return rows, _audit(
        record, path, len(rows), "no_token_difference" if not rows else ""
    )


def review_record(
    record: Mapping[str, str], path: str, decision: Mapping[str, object]
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Apply a deliberate review; stale originals or ungrounded approvals fail closed."""
    review = RecordReview.model_validate(decision)
    date.fromisoformat(review.ReviewedAt)
    if review.MishearID != record["MishearID"] or review.OriginalHash != original_hash(
        record
    ):
        raise ValueError("review does not match current original hash/ID")
    if any(not s.strip() for s in (review.Reviewer, review.Evidence, review.Reason)):
        raise ValueError("review evidence and attribution cannot be blank")
    if review.Status == "reviewed" and review.TargetDecision == "undecided":
        raise ValueError("reviewed records require an explicit target decision")
    if review.Status == "pending" and review.TargetDecision != "undecided":
        raise ValueError("pending reviews must remain undecided")
    src, tgt = (
        _prepared(record["Src"], review.SrcAnnotations),
        _prepared(record["Tgt"], review.TgtAnnotations),
    )
    rows: list[dict[str, str]] = []
    for span in review.PairSpans:
        if not (
            span.src_start <= span.src_end <= len(record["Src"])
            and span.tgt_start <= span.tgt_end <= len(record["Tgt"])
        ):
            raise ValueError("pair span outside original")
        row = _pair(record, path, src, tgt, span, [])
        row.update(
            ReviewStatus=review.Status,
            TargetDecision=review.TargetDecision,
            Reviewer=review.Reviewer,
            ReviewedAt=review.ReviewedAt,
            Evidence=review.Evidence,
            Reason=review.Reason,
            RecordValidity=review.RecordValidity,
        )
        for side in ("Src", "Tgt"):
            if row[side + "Reading"]:
                row[side + "ReadingStatus"] = "confirmed"
        if review.TargetDecision == "include":
            if (
                not row["Src"]
                or not row["Tgt"]
                or any(row[s + "ReadingStatus"] != "confirmed" for s in ("Src", "Tgt"))
            ):
                raise ValueError(
                    "included pairs require both surfaces and confirmed readings"
                )
            if src.legacy_parentheses or tgt.legacy_parentheses:
                raise ValueError("unclassified parentheses cannot enter evaluation")
        rows.append(row)
    if review.TargetDecision == "include" and not rows:
        raise ValueError("an included record must select at least one pair")
    audit = _audit(
        record, path, len(rows), "review_selected_no_pairs" if not rows else ""
    )
    audit.update(
        ReviewStatus=review.Status,
        TargetDecision=review.TargetDecision,
        Reason=review.Reason,
        RecordValidity=review.RecordValidity,
    )
    return rows, audit


def csv_bytes(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> bytes:
    """Serialize deterministic UTF-8 CSV, preserving original text and newlines."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def build_artifacts(
    snapshot: CorpusSnapshot,
    decisions: list[dict[str, object]],
    tokenizer: Tokenizer = mecab_tokens,
) -> dict[str, bytes]:
    """Build a complete audit ledger; missing reviews remain explicitly unprocessed."""
    reviews: dict[str, dict[str, object]] = {}
    for entry in decisions:
        parsed = RecordReview.model_validate(entry)
        if parsed.MishearID in reviews or parsed.MishearID not in snapshot.by_id:
            raise ValueError("duplicate or unknown review MishearID")
        reviews[parsed.MishearID] = entry
    draft: list[dict[str, str]] = []
    reviewed: list[dict[str, str]] = []
    pending: list[dict[str, str]] = []
    ledger: list[dict[str, object]] = []
    changes: list[dict[str, object]] = []
    for record in snapshot.records:
        raw = {key: str(getattr(record, key)) for key in CSV_FIELDS}
        proposals, audit = extract_record(raw, record.source_file, tokenizer)
        draft.extend(proposals)
        decision = reviews.get(record.MishearID)
        if decision is not None:
            selected, checked = review_record(raw, record.source_file, decision)
            checked["CandidateCount"] = audit["CandidateCount"]
            checked["ZeroReason"] = audit["ZeroReason"]
            audit = checked
            (reviewed if checked["ReviewStatus"] == "reviewed" else pending).extend(
                selected
            )
            changes.append(
                {
                    "MishearID": record.MishearID,
                    "OriginalHash": original_hash(raw),
                    "Before": canonical_json(proposals),
                    "After": canonical_json(selected),
                    "Reviewer": decision["Reviewer"],
                    "Reason": decision["Reason"],
                }
            )
        ledger.append(audit)
    all_ids = [row["PairID"] for row in reviewed + pending]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("duplicate reviewed PairID")
    unprocessed = sum(row["ReviewStatus"] == "draft" for row in ledger)
    manifest: dict[str, object] = {
        "format_version": 2,
        "source_commit": snapshot.info.dataset_version,
        "source_dataset_sha256": snapshot.info.dataset_sha256,
        "originals_sha256": originals_hash(snapshot),
        "extractor_version": EXTRACTOR_VERSION,
        "extractor_sha256": extractor_hash(),
        "settings": TOKENIZER_SETTINGS,
        "input_count": len(ledger),
        "candidate_count": len(draft),
        "zero_candidate_count": sum(row["CandidateCount"] == 0 for row in ledger),
        "reviewed_record_count": sum(
            row["ReviewStatus"] == "reviewed" for row in ledger
        ),
        "pending_record_count": sum(row["ReviewStatus"] == "pending" for row in ledger),
        "excluded_record_count": sum(
            row["TargetDecision"] == "exclude" for row in ledger
        ),
        "unprocessed_count": unprocessed,
        "evaluation_pair_count": sum(
            row["TargetDecision"] == "include" for row in reviewed
        ),
        "review_complete": unprocessed == 0,
        "linguistic_quality_complete": unprocessed == 0
        and not any(row["ReviewStatus"] == "pending" for row in ledger),
        "review_input_sha256": hashlib.sha256(
            canonical_json(decisions).encode()
        ).hexdigest(),
    }
    result = {
        "draft.csv": csv_bytes(draft, PAIR_FIELDS),
        "reviewed.csv": csv_bytes(reviewed, PAIR_FIELDS),
        "pending.csv": csv_bytes(pending, PAIR_FIELDS),
        "records.csv": csv_bytes(
            ledger, tuple(ledger[0]) if ledger else ("MishearID",)
        ),
        "changes.csv": csv_bytes(
            changes,
            ("MishearID", "OriginalHash", "Before", "After", "Reviewer", "Reason"),
        ),
    }
    manifest["files"] = {
        name: hashlib.sha256(payload).hexdigest()
        for name, payload in sorted(result.items())
    }
    result["manifest.json"] = (canonical_json(manifest) + "\n").encode()
    return result


def validate_artifacts(
    files: Mapping[str, bytes],
    snapshot: CorpusSnapshot,
    decisions: list[dict[str, object]],
) -> dict[str, object]:
    """Recompute review outputs from current originals; hashes alone aren't approval."""
    manifest = cast(dict[str, object], json.loads(files["manifest.json"]))
    if not isinstance(manifest.get("source_commit"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", cast(str, manifest["source_commit"])
    ):
        raise ValueError("source_commit must be a full Git SHA")
    if (
        manifest.get("extractor_version") != EXTRACTOR_VERSION
        or manifest.get("settings") != TOKENIZER_SETTINGS
    ):
        raise ValueError("extractor/settings changed; regenerate and recheck reviews")
    if manifest.get("extractor_sha256") != extractor_hash():
        raise ValueError(
            "extractor code changed; regenerate and recheck affected reviews"
        )
    if manifest["format_version"] != 2 or manifest[
        "originals_sha256"
    ] != originals_hash(snapshot):
        raise ValueError("pair artifacts belong to different original data")
    expected = cast(dict[str, str], manifest["files"])
    required = {
        "draft.csv",
        "reviewed.csv",
        "pending.csv",
        "records.csv",
        "changes.csv",
    }
    if set(expected) != required:
        raise ValueError("incomplete artifact manifest")
    for name, digest in expected.items():
        if hashlib.sha256(files[name]).hexdigest() != digest:
            raise ValueError(f"artifact checksum mismatch: {name}")
    if (
        manifest["review_input_sha256"]
        != hashlib.sha256(canonical_json(decisions).encode()).hexdigest()
    ):
        raise ValueError("annotations changed without regenerating pair artifacts")
    draft = list(_rows("draft.csv", files["draft.csv"], PAIR_FIELDS))
    drafts_by_id: dict[str, list[dict[str, str]]] = {}
    for row in draft:
        identifier = row["MishearID"]
        if identifier not in snapshot.by_id:
            raise ValueError("unknown draft MishearID")
        record = snapshot.by_id[identifier]
        raw = {key: str(getattr(record, key)) for key in CSV_FIELDS}
        flags = json.loads(row["Flags"])
        if not isinstance(flags, list) or any(
            f
            not in (
                "legacy_parentheses",
                "boundary_review_required",
                "annotated_unit_boundary",
                "context_alternative",
            )
            for f in flags
        ):
            raise ValueError("invalid draft flags")
        span = PairSpan.model_validate(
            {
                "src_start": int(row["SrcStart"]),
                "src_end": int(row["SrcEnd"]),
                "tgt_start": int(row["TgtStart"]),
                "tgt_end": int(row["TgtEnd"]),
                "unit_type": row["UnitType"],
            }
        )
        expected_row = _pair(
            raw,
            record.source_file,
            _prepared(raw["Src"]),
            _prepared(raw["Tgt"]),
            span,
            flags,
        )
        if row != expected_row:
            raise ValueError("draft row does not match original spans/annotations")
        drafts_by_id.setdefault(identifier, []).append(row)
    if len({row["PairID"] for row in draft}) != len(draft):
        raise ValueError("duplicate draft PairID")
    reviewed: list[dict[str, str]] = []
    pending: list[dict[str, str]] = []
    seen: set[str] = set()
    decisions_by_id: dict[str, dict[str, object]] = {}
    for decision in decisions:
        review = RecordReview.model_validate(decision)
        if review.MishearID in seen or review.MishearID not in snapshot.by_id:
            raise ValueError("duplicate or unknown review record")
        seen.add(review.MishearID)
        decisions_by_id[review.MishearID] = decision
        record = snapshot.by_id[review.MishearID]
        raw = {key: str(getattr(record, key)) for key in CSV_FIELDS}
        rows, _ = review_record(raw, record.source_file, decision)
        (reviewed if review.Status == "reviewed" else pending).extend(rows)
    selected_ids = [row["PairID"] for row in reviewed + pending]
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("duplicate selected PairID")
    # Source order, not the order of manual reviews, determines release ordering.
    reviewed.sort(key=lambda row: (row["MishearID"], row["PairID"]))
    pending.sort(key=lambda row: (row["MishearID"], row["PairID"]))
    for name, rows in (("reviewed.csv", reviewed), ("pending.csv", pending)):
        actual = list(csv.DictReader(io.StringIO(files[name].decode("utf-8"))))
        if sorted(actual, key=lambda row: (row["MishearID"], row["PairID"])) != rows:
            raise ValueError(f"{name} does not match source-bound review decisions")
    ledger: list[dict[str, object]] = []
    changes: list[dict[str, object]] = []
    for record in snapshot.records:
        raw = {key: str(getattr(record, key)) for key in CSV_FIELDS}
        candidates = drafts_by_id.get(record.MishearID, [])
        zero_reason = ""
        parse_error = ""
        if not candidates:
            try:
                src, tgt = _prepared(raw["Src"]), _prepared(raw["Tgt"])
                if not _same_interpretation(src, tgt):
                    raise ValueError(
                        "distinct interpretations cannot have no context candidate"
                    )
                zero_reason = "same_surface"
            except ValueError as error:
                # Distinguish an actual syntax error from a removed context candidate.
                if (
                    str(error)
                    == "distinct interpretations cannot have no context candidate"
                ):
                    raise
                zero_reason, parse_error = "annotation_syntax_error", str(error)
        audit = _audit(raw, record.source_file, len(candidates), zero_reason)
        if parse_error:
            audit["Reason"] = parse_error
        selected_decision = decisions_by_id.get(record.MishearID)
        if selected_decision is not None:
            rows, checked = review_record(raw, record.source_file, selected_decision)
            checked["CandidateCount"], checked["ZeroReason"] = (
                len(candidates),
                zero_reason,
            )
            audit = checked
            changes.append(
                {
                    "MishearID": record.MishearID,
                    "OriginalHash": original_hash(raw),
                    "Before": canonical_json(candidates),
                    "After": canonical_json(rows),
                    "Reviewer": selected_decision["Reviewer"],
                    "Reason": selected_decision["Reason"],
                }
            )
        ledger.append(audit)
    if files["records.csv"] != csv_bytes(ledger, tuple(ledger[0])):
        raise ValueError("records.csv coverage ledger does not match original/reviews")
    if files["changes.csv"] != csv_bytes(
        changes, ("MishearID", "OriginalHash", "Before", "After", "Reviewer", "Reason")
    ):
        raise ValueError("changes.csv does not match actual review corrections")
    actual_unprocessed = len(snapshot.records) - len(seen)
    if manifest["unprocessed_count"] != actual_unprocessed:
        raise ValueError("review coverage count mismatch")
    counters: dict[str, object] = {
        "input_count": len(snapshot.records),
        "candidate_count": len(draft),
        "zero_candidate_count": sum(row["CandidateCount"] == 0 for row in ledger),
        "reviewed_record_count": sum(
            row["ReviewStatus"] == "reviewed" for row in ledger
        ),
        "pending_record_count": sum(row["ReviewStatus"] == "pending" for row in ledger),
        "excluded_record_count": sum(
            row["TargetDecision"] == "exclude" for row in ledger
        ),
        "evaluation_pair_count": sum(
            row["TargetDecision"] == "include" for row in reviewed
        ),
        "review_complete": actual_unprocessed == 0,
        "linguistic_quality_complete": actual_unprocessed == 0
        and not any(row["ReviewStatus"] == "pending" for row in ledger),
    }
    for key, value in counters.items():
        if type(manifest[key]) is not type(value) or manifest[key] != value:
            raise ValueError(f"coverage metadata mismatch: {key}")
    return manifest


def validate_release(directory: Path) -> dict[str, object]:
    """Fail evaluation finalization until every original has a deliberate review."""
    manifest = cast(
        dict[str, object], json.loads((directory / "manifest.json").read_text())
    )
    if manifest.get("unprocessed_count") != 0 or not manifest.get("review_complete"):
        raise ValueError(
            "unprocessed records remain; this is not an evaluation release"
        )
    return manifest


def validate_index(root: Path) -> dict[str, object]:
    """Validate staged originals/reviews/artifacts, not a possibly different worktree."""
    base = CorpusSnapshot.from_git(root, "HEAD")
    with Repo(root, search_parent_directories=False) as repo:
        entries = repo.index.entries

        def staged(path: str) -> bytes:
            """Read an exact stage-zero regular Git blob without filesystem fallback."""
            entry = entries.get((path, 0))
            if entry is None or entry.mode not in (0o100644, 0o100755):
                raise ValueError(
                    f"missing/unmerged/nonregular staged pair input: {path}"
                )
            return cast(
                bytes, Blob(repo, entry.binsha, entry.mode, path).data_stream.read()
            )

        records: dict[str, Record] = {}
        for entry_path, stage in sorted(entries):
            path = str(entry_path)
            if not (path.startswith("data/mishearing/") and path.endswith(".csv")):
                continue
            if stage != 0:
                raise ValueError("unmerged staged original CSV")
            for raw in _rows(path, staged(path), CSV_FIELDS):
                identifier = raw["MishearID"]
                if not identifier or identifier in records:
                    raise ValueError("empty or duplicate staged MishearID")
                records[identifier] = Record.model_validate(
                    raw
                    | {
                        "source_file": path,
                        "source": PurePosixPath(path)
                        .parent.relative_to("data/mishearing")
                        .as_posix(),
                    }
                )
        if not records:
            raise ValueError("no staged original CSV records")
        snapshot = CorpusSnapshot(
            base.info, tuple(records[key] for key in sorted(records)), records
        )
        decisions = load_reviews(staged("data/annotations/reviews.csv"))
        pointer = json.loads(staged("resource/pairs_v2/current.json"))
        directory = pointer.get("directory")
        if (
            set(pointer) != {"directory"}
            or not isinstance(directory, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", directory)
        ):
            raise ValueError("invalid staged pair run pointer")
        names = (
            "manifest.json",
            "draft.csv",
            "reviewed.csv",
            "pending.csv",
            "records.csv",
            "changes.csv",
        )
        artifacts = {
            name: staged(f"resource/pairs_v2/{directory}/{name}") for name in names
        }
        return validate_artifacts(artifacts, snapshot, decisions)


def main() -> None:
    """Generate immutable run directories, or validate current worktree review artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("draft", "build", "validate", "check", "import-reviews", "schema"),
    )
    parser.add_argument(
        "--repository", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument(
        "--annotations", type=Path, default=Path("data/annotations/reviews.csv")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--inputs", type=Path, nargs="*")
    parser.add_argument("--kind", choices=("review", "pair-table"), default="review")
    parser.add_argument(
        "--working-tree",
        action="store_true",
        help="Build from explicit dirty originals; never used by HTTP",
    )
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check exact Git index inputs, including partial staging",
    )
    args = parser.parse_args()
    root: Path = args.repository.resolve()
    if args.staged:
        if args.command != "check":
            parser.error("--staged is only supported with check")
        manifest = validate_index(root)
        if args.require_complete and manifest["unprocessed_count"]:
            raise ValueError("unprocessed staged records remain")
        print(canonical_json(manifest))
        return
    snapshot = CorpusSnapshot.from_git(root, args.ref)
    if args.working_tree or args.command in ("validate", "check"):
        snapshot = working_snapshot(root, snapshot)
    annotation_path = (
        args.annotations if args.annotations.is_absolute() else root / args.annotations
    )
    if args.command == "check":
        pointer = json.loads((root / "resource/pairs_v2/current.json").read_text())
        directory = pointer["directory"]
        if (
            not isinstance(directory, str)
            or not directory
            or any(
                c
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for c in directory
            )
        ):
            raise ValueError("invalid pair run pointer")
        output = root / "resource/pairs_v2" / directory
    elif args.output is None:
        parser.error("--output is required for this command")
    else:
        output = args.output if args.output.is_absolute() else root / args.output
    if args.command == "schema":
        # Generated schema, not a separately maintained competing contract.
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                RecordReview.model_json_schema()
                if args.kind == "review"
                else pair_table_schema(),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return
    if args.command == "import-reviews":
        if output.exists():
            raise ValueError(
                "review output exists; choose a new path and inspect the diff"
            )
        imported: list[dict[str, object]] = []
        for path in args.inputs or []:
            path = path if path.is_absolute() else root / path
            imported.extend(json.loads(path.read_text(encoding="utf-8")))
        seen: set[str] = set()
        for entry in imported:
            review = RecordReview.model_validate(entry)
            if review.MishearID in seen:
                raise ValueError("duplicate review ID in import")
            seen.add(review.MishearID)
            record = snapshot.by_id[review.MishearID]
            review_record(
                {key: str(getattr(record, key)) for key in CSV_FIELDS},
                record.source_file,
                entry,
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(review_csv(imported))
        print(f"Imported {len(imported)} deliberate reviews; no automatic approvals")
        return
    decisions = (
        [] if args.command == "draft" else load_reviews(annotation_path.read_bytes())
    )
    if args.command in ("draft", "build"):
        if output.exists():
            raise ValueError(
                "output exists; use a new run directory, never overwrite reviews"
            )
        artifacts = build_artifacts(snapshot, decisions)
        manifest = json.loads(artifacts["manifest.json"])
        manifest["source_state"] = "working-tree" if args.working_tree else "committed"
        try:
            manifest["tokenizer_version"] = subprocess.check_output(
                ["mecab", "--version"], text=True
            ).strip()
            dictionary = subprocess.run(
                ["mecab", "-D"], text=True, capture_output=True, timeout=30, check=False
            )
            # MeCab 0.996's dictionary-info mode exits 1 even on a valid report.
            if (
                dictionary.returncode not in (0, 1)
                or "filename:" not in dictionary.stdout
                or "charset:" not in dictionary.stdout
            ):
                raise ValueError("invalid MeCab dictionary report")
            manifest["dictionary_info"] = dictionary.stdout
            dictionary_files = []
            for line in dictionary.stdout.splitlines():
                if line.startswith("filename:"):
                    path = Path(line.split(":", 1)[1].strip())
                    dictionary_files.append(
                        {
                            "name": path.name,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }
                    )
            manifest["dictionary_files"] = dictionary_files
        except (OSError, subprocess.SubprocessError) as error:
            raise ValueError(
                "cannot record actual MeCab dictionary environment"
            ) from error
        artifacts["manifest.json"] = (canonical_json(manifest) + "\n").encode()
        validate_artifacts(artifacts, snapshot, decisions)
        output.mkdir(parents=True)
        for name, payload in artifacts.items():
            (output / name).write_bytes(payload)
    else:
        artifacts = {
            path.name: path.read_bytes() for path in output.iterdir() if path.is_file()
        }
        manifest = validate_artifacts(artifacts, snapshot, decisions)
    if args.require_complete:
        validate_release(output)
    print(canonical_json(manifest))


if __name__ == "__main__":
    main()
