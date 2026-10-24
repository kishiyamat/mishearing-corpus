"""Validate generated full and review-focused lexical export views."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from scripts.export_lexical_pair_csvs import (
    EXPORT_FIELDS,
    REVIEW_COLUMNS,
    write_exports,
)


def test_write_exports_preserves_full_schema_and_creates_review_view(
    tmp_path: Path,
) -> None:
    """The compact view selects review columns without changing the full CSV."""
    # Arrange
    fields = list(EXPORT_FIELDS)
    row = dict.fromkeys(fields, "") | {
        "PairID": "pair-1",
        "Src": "幸福",
        "Tgt": "交付金",
        "SrcReading": "コウフク",
        "TgtReading": "コウフキン",
        "UnitType": "word",
        "MishearID": "example-1",
        "URL": "https://example.test/",
        "Language": "ja",
        "TargetDecision": "include",
    }
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow(row)
    payload = stream.getvalue().encode()
    output_dir = tmp_path / "exports"

    # Act
    write_exports(output_dir, payload, {"X-Pair-Version": "run-1"})

    # Assert
    full = (output_dir / "lexical-pairs-full.csv").read_bytes()
    assert full == payload
    with (output_dir / "lexical-pairs-review.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        compact_rows = list(csv.DictReader(stream))
    assert list(compact_rows[0]) == list(REVIEW_COLUMNS)
    assert compact_rows[0]["Src"] == "幸福"
    assert compact_rows[0]["Tgt"] == "交付金"
    assert (output_dir / "export-metadata.json").exists()


def test_write_exports_rejects_nonlexical_rows_and_existing_directories(
    tmp_path: Path,
) -> None:
    """Invalid payloads fail before output; existing data is never overwritten."""
    # Arrange
    fields = list(EXPORT_FIELDS)
    row = dict.fromkeys(fields, "") | {"UnitType": "phrase"}
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow(row)
    payload = stream.getvalue().encode()

    # Act / Assert
    with pytest.raises(ValueError, match="non-lexical"):
        write_exports(tmp_path / "bad", payload, {})
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        write_exports(existing, payload, {})
