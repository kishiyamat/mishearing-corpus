"""Read and serve one committed, validated public pair-review snapshot."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, cast

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from git import Blob, Repo, Tree
from git.exc import GitError
from pydantic import BaseModel, ConfigDict, Field

from .dataset import CorpusSnapshot, canonical_json
from .pair_workflow import PAIR_FIELDS, load_reviews, originals_hash, validate_artifacts

_RUN_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_ARTIFACTS = (
    "manifest.json",
    "draft.csv",
    "reviewed.csv",
    "pending.csv",
    "records.csv",
    "changes.csv",
)
_ANNOTATIONS = "data/annotations/reviews.csv"


@dataclass(frozen=True)
class PairSnapshot:
    """Hold validated reviewed rows and provenance from one resolved Git commit."""

    pair_version: str
    dataset_version: str
    dataset_sha256: str
    source_commit: str
    checksum: str
    coverage: Mapping[str, int | bool]
    rows: tuple[Mapping[str, str], ...]


def _blob(commit_tree: Tree, path: str) -> bytes | None:
    """Return regular committed blob bytes, rejecting symlinks and non-files."""
    try:
        item = commit_tree / path
    except (KeyError, GitError):
        return None
    if not isinstance(item, Blob):
        raise TypeError(f"Expected committed file at {path}")
    if item.mode not in (0o100644, 0o100755):
        raise ValueError(f"Expected regular committed file at {path}")
    return cast(bytes, item.data_stream.read())


def _read_rows(payload: bytes, filename: str) -> tuple[Mapping[str, str], ...]:
    """Parse a pair CSV with the exact v2 flat-string column contract."""
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""))
        if tuple(reader.fieldnames or ()) != PAIR_FIELDS:
            raise ValueError(f"Unexpected columns in {filename}")
        rows: list[Mapping[str, str]] = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed row in {filename}")
            rows.append(cast(dict[str, str], row))
        return tuple(rows)
    except (UnicodeError, csv.Error) as error:
        raise ValueError(f"Invalid pair CSV in {filename}: {error}") from error


def load_pair_snapshot(
    root: Path, ref: str, corpus: CorpusSnapshot
) -> PairSnapshot | None:
    """Load only allowlisted Git blobs and validate them against the corpus."""
    try:
        with Repo(root, search_parent_directories=False) as repo:
            commit = repo.commit(ref)
            pointer_bytes = _blob(commit.tree, "resource/pairs_v2/current.json")
            if pointer_bytes is None:
                return None
            pointer = json.loads(pointer_bytes.decode("utf-8"))
            if not isinstance(pointer, dict) or set(pointer) != {"directory"}:
                raise ValueError("Invalid current pair pointer")
            directory = pointer["directory"]
            if not isinstance(directory, str) or not _RUN_NAME.fullmatch(directory):
                raise ValueError("Invalid pair run directory")
            base = f"resource/pairs_v2/{directory}"
            files: dict[str, bytes] = {}
            for name in _ARTIFACTS:
                payload = _blob(commit.tree, f"{base}/{name}")
                if payload is None:
                    raise ValueError(f"Missing pair artifact: {name}")
                files[name] = payload
            annotation_bytes = _blob(commit.tree, _ANNOTATIONS)
            if annotation_bytes is None:
                raise ValueError("Missing committed pair review annotations")
            decisions = load_reviews(annotation_bytes)
            manifest = validate_artifacts(files, corpus, decisions)
            source_ref = str(manifest["source_commit"])
            source_commit = repo.commit(source_ref)
            if source_commit.hexsha != source_ref:
                raise ValueError(
                    "source provenance must identify an exact local commit"
                )
            source_state = manifest.get("source_state", "committed")
            if source_state not in ("committed", "working-tree"):
                raise ValueError("unknown original source state")
            if source_state == "committed":
                source_corpus = CorpusSnapshot.from_git(root, source_ref)
                if originals_hash(source_corpus) != manifest["originals_sha256"]:
                    raise ValueError(
                        "claimed source commit contains different originals"
                    )
            reviewed = _read_rows(files["reviewed.csv"], "reviewed.csv")
            coverage_keys = (
                "input_count",
                "reviewed_record_count",
                "pending_record_count",
                "excluded_record_count",
                "unprocessed_count",
            )
            coverage: dict[str, int | bool] = {
                key: int(cast(int, manifest[key])) for key in coverage_keys
            }
            # Processing coverage is not a claim that pending linguistic decisions
            # have been resolved. Preserve the validated flags as JSON booleans.
            for key in ("review_complete", "linguistic_quality_complete"):
                coverage[key] = cast(bool, manifest[key])
            digest = hashlib.sha256()
            for name, payload in sorted(
                {**files, _ANNOTATIONS: annotation_bytes}.items()
            ):
                digest.update(name.encode("utf-8"))
                digest.update(b"\0")
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
            return PairSnapshot(
                pair_version=directory,
                dataset_version=commit.hexsha,
                dataset_sha256=corpus.info.dataset_sha256,
                source_commit=str(manifest["source_commit"]),
                checksum=digest.hexdigest(),
                coverage=coverage,
                rows=reviewed,
            )
    except (
        GitError,
        KeyError,
        OSError,
        TypeError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            f"Cannot load committed pair snapshot at {root} ref {ref!r}: {error}"
        ) from error


class PairFilters(BaseModel):
    """Validate filters shared by pair search and evaluation export."""

    model_config = ConfigDict(extra="forbid")
    q: str | None = Field(default=None, min_length=1, max_length=500)
    mishear_id: str | None = Field(default=None, min_length=1, max_length=128)
    unit_type: Literal["word", "particle-inclusive", "compound", "phrase"] | None = None
    dataset_version: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")


class PairQuery(PairFilters):
    """Validate pair list filters and stable pagination controls."""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class PairVersionQuery(BaseModel):
    """Reject unknown parameters on individual pair lookups."""

    model_config = ConfigDict(extra="forbid")
    dataset_version: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")


class PairExportQuery(PairFilters):
    """Validate pair filters and format while forbidding list pagination."""

    format: Literal["csv", "jsonl"] = "csv"


def _filter_rows(
    rows: tuple[Mapping[str, str], ...], query: PairFilters
) -> tuple[Mapping[str, str], ...]:
    """Apply the same exact ID/unit and literal casefold text filters everywhere."""
    return tuple(
        row
        for row in rows
        if (query.mishear_id is None or row["MishearID"] == query.mishear_id)
        and (query.unit_type is None or row["UnitType"] == query.unit_type)
        and (
            query.q is None
            or any(
                query.q.casefold() in row[field].casefold()
                for field in ("Src", "Tgt", "SrcReading", "TgtReading")
            )
        )
    )


def _applied_filters(query: PairFilters) -> dict[str, object]:
    """Return effective user filters without transport format or version controls."""
    return {
        "q": query.q,
        "mishear_id": query.mishear_id,
        "unit_type": query.unit_type,
    }


def _pair_payload(snapshot: PairSnapshot, row: Mapping[str, str]) -> dict[str, object]:
    """Add immutable source and pair provenance to one flat pair row."""
    payload: dict[str, object] = dict(row)
    payload.update(
        {
            "dataset_version": snapshot.dataset_version,
            "dataset_sha256": snapshot.dataset_sha256,
            "pair_version": snapshot.pair_version,
            "pair_sha256": snapshot.checksum,
        }
    )
    return payload


def _export_bytes(
    snapshot: PairSnapshot, rows: tuple[Mapping[str, str], ...], format: str
) -> bytes:
    """Encode included reviewed rows with provenance columns on every row."""
    fields = (
        *PAIR_FIELDS,
        "dataset_version",
        "dataset_sha256",
        "pair_version",
        "pair_sha256",
    )
    payloads = [
        _pair_payload(snapshot, row)
        for row in rows
        if row["TargetDecision"] == "include"
    ]
    if format == "jsonl":
        return "".join(canonical_json(row) + "\n" for row in payloads).encode("utf-8")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(payloads)
    return stream.getvalue().encode("utf-8")


def register_pair_routes(app: FastAPI) -> None:
    """Register read-only pair search, lookup, and evaluation export routes."""

    def pair_snapshot(version: str | None = None) -> PairSnapshot:
        """Get the startup snapshot or explicitly reject an unavailable data version."""
        snapshot = cast(PairSnapshot | None, getattr(app.state, "pair_snapshot", None))
        if snapshot is None:
            raise HTTPException(
                status_code=503, detail="Pair annotations are not available"
            )
        if version is not None and version != snapshot.dataset_version:
            raise HTTPException(
                status_code=404, detail="Dataset version is not served by this instance"
            )
        return snapshot

    @app.get("/v1/pairs")
    def list_pairs(query: Annotated[PairQuery, Query()]) -> dict[str, object]:
        """Search reviewed rows, including explicit exclusions, with stable pagination."""
        snapshot = pair_snapshot(query.dataset_version)
        matches = _filter_rows(snapshot.rows, query)
        end = query.offset + query.limit
        return {
            "dataset_version": snapshot.dataset_version,
            "dataset_sha256": snapshot.dataset_sha256,
            "pair_version": snapshot.pair_version,
            "pair_sha256": snapshot.checksum,
            "source_commit": snapshot.source_commit,
            "coverage": dict(snapshot.coverage),
            "total": len(matches),
            "limit": query.limit,
            "offset": query.offset,
            "next_offset": end if end < len(matches) else None,
            "pairs": [
                _pair_payload(snapshot, row) for row in matches[query.offset : end]
            ],
        }

    @app.get("/v1/pairs/export", response_class=Response)
    def export_pairs(query: Annotated[PairExportQuery, Query()]) -> Response:
        """Export included decisions only after every source record was reviewed."""
        snapshot = pair_snapshot(query.dataset_version)
        if snapshot.coverage["unprocessed_count"]:
            raise HTTPException(
                status_code=409,
                detail="Unprocessed records remain; no evaluation export",
            )
        matches = _filter_rows(snapshot.rows, query)
        included = tuple(row for row in matches if row["TargetDecision"] == "include")
        payload = _export_bytes(snapshot, included, query.format)
        coverage = canonical_json(dict(snapshot.coverage), ascii_only=True)
        filters = _applied_filters(query)
        return Response(
            content=payload,
            media_type="text/csv" if query.format == "csv" else "application/x-ndjson",
            headers={
                "Content-Disposition": f'attachment; filename="pairs-{snapshot.pair_version}.{query.format}"',
                "X-Dataset-Version": snapshot.dataset_version,
                "X-Dataset-SHA256": snapshot.dataset_sha256,
                "X-Pair-Version": snapshot.pair_version,
                "X-Pair-SHA256": snapshot.checksum,
                "X-Coverage": coverage,
                "X-Applied-Filters": canonical_json(filters, ascii_only=True),
                "X-Result-Count": str(len(included)),
                "X-Export-SHA256": hashlib.sha256(payload).hexdigest(),
            },
        )

    @app.get("/v1/pairs/{pair_id}")
    def get_pair(
        pair_id: str, query: Annotated[PairVersionQuery, Query()]
    ) -> dict[str, object]:
        """Return an exact PairID including reviewed exclusions."""
        snapshot = pair_snapshot(query.dataset_version)
        row = next((item for item in snapshot.rows if item["PairID"] == pair_id), None)
        if row is None:
            raise HTTPException(status_code=404, detail="PairID not found")
        return {
            "dataset_version": snapshot.dataset_version,
            "dataset_sha256": snapshot.dataset_sha256,
            "pair_version": snapshot.pair_version,
            "pair_sha256": snapshot.checksum,
            "source_commit": snapshot.source_commit,
            "coverage": dict(snapshot.coverage),
            "pair": _pair_payload(snapshot, row),
        }
