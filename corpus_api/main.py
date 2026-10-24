"""FastAPI adapter for the versioned, read-only public corpus service."""

import csv
import hashlib
import io
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal, cast

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .dataset import CorpusSnapshot, canonical_json
from .models import (
    AppliedFilters,
    DatasetsResponse,
    ExportQuery,
    Record,
    RecordResponse,
    RecordsQuery,
    RecordsResponse,
    VersionQuery,
)
from .pairs import load_pair_snapshot, register_pair_routes

EXPORT_HEADERS = (
    "X-Dataset-Version",
    "X-Dataset-SHA256",
    "X-Applied-Filters",
    "X-Result-Count",
    "X-Export-SHA256",
    "X-Pair-Version",
    "X-Pair-SHA256",
    "X-Coverage",
    "Content-Disposition",
)


def _export_bytes(
    snapshot: CorpusSnapshot,
    records: tuple[Record, ...],
    format: Literal["csv", "jsonl"],
) -> bytes:
    """Encode all matching rows, preserving CSV strings and per-row provenance."""
    provenance = {
        "dataset_version": snapshot.info.dataset_version,
        "dataset_sha256": snapshot.info.dataset_sha256,
    }
    rows = [record.model_dump(mode="json") | provenance for record in records]
    if format == "jsonl":
        return "".join(canonical_json(row) + "\n" for row in rows).encode("utf-8")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=[*Record.model_fields, *provenance], lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            row | {key: canonical_json(row[key]) for key in ("TagIDs", "EnvIDs")}
        )
    return stream.getvalue().encode("utf-8")


def create_app(
    repository: Path | None = None, dataset_ref: str | None = None
) -> FastAPI:
    """Create an app that loads one committed public snapshot during startup.

    Explicit arguments override MISHEARING_CORPUS_ROOT and MISHEARING_DATASET_REF.
    Defaults are the checkout containing this module and its HEAD. Use as a
    Uvicorn factory, or with TestClient in a context manager to run the lifespan.
    Invalid inputs fail startup; no request changes files or resolves new refs.
    """
    root = (
        repository
        if repository is not None
        else Path(
            os.environ.get(
                "MISHEARING_CORPUS_ROOT", str(Path(__file__).resolve().parents[1])
            )
        )
    )
    ref = (
        dataset_ref
        if dataset_ref is not None
        else os.environ.get("MISHEARING_DATASET_REF", "HEAD")
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """Load before serving and discard the in-memory snapshot after shutdown."""
        application.state.snapshot = CorpusSnapshot.from_git(root.resolve(), ref)
        application.state.pair_snapshot = load_pair_snapshot(
            root.resolve(), ref, application.state.snapshot
        )
        try:
            yield
        finally:
            del application.state.pair_snapshot
            del application.state.snapshot

    application = FastAPI(
        title="Mishearing Corpus API",
        version="1.0.0",
        description="Read-only public CSV snapshots. See docs/api.md for reproducibility and reuse.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_credentials=False,
        expose_headers=list(EXPORT_HEADERS),
    )
    register_pair_routes(application)

    def snapshot_for(version: str | None = None) -> CorpusSnapshot:
        """Get the startup snapshot, rejecting an unavailable version without fallback."""
        snapshot = cast(CorpusSnapshot, application.state.snapshot)
        if version is not None and version != snapshot.info.dataset_version:
            raise HTTPException(
                status_code=404, detail="Dataset version is not served by this instance"
            )
        return snapshot

    @application.get("/v1/datasets")
    def datasets() -> DatasetsResponse:
        """List the one loaded version and its available filter IDs and quality counts."""
        return DatasetsResponse(datasets=(snapshot_for().info,))

    @application.get("/v1/records")
    def records(query: Annotated[RecordsQuery, Query()]) -> RecordsResponse:
        """Search the fixed snapshot with stable pagination and explicit conditions."""
        snapshot = snapshot_for(query.dataset_version)
        filters = query.applied()
        matches = snapshot.search(filters)
        end = query.offset + query.limit
        return RecordsResponse(
            dataset_version=snapshot.info.dataset_version,
            dataset_sha256=snapshot.info.dataset_sha256,
            filters=filters,
            total=len(matches),
            limit=query.limit,
            offset=query.offset,
            next_offset=end if end < len(matches) else None,
            records=matches[query.offset : end],
        )

    @application.get("/v1/records/{mishear_id}")
    def record(
        mishear_id: str, query: Annotated[VersionQuery, Query()]
    ) -> RecordResponse:
        """Find a complete, case-sensitive MishearID or return 404."""
        snapshot = snapshot_for(query.dataset_version)
        found = snapshot.by_id.get(mishear_id)
        if found is None:
            raise HTTPException(status_code=404, detail="MishearID not found")
        return RecordResponse(
            dataset_version=snapshot.info.dataset_version,
            dataset_sha256=snapshot.info.dataset_sha256,
            record=found,
        )

    @application.get("/v1/export", response_class=Response)
    def export(query: Annotated[ExportQuery, Query()]) -> Response:
        """Export all matches and preserve effective filters and body checksum in headers."""
        snapshot = snapshot_for(query.dataset_version)
        filters: AppliedFilters = query.applied()
        matches = snapshot.search(filters)
        payload = _export_bytes(snapshot, matches, query.format)
        version = snapshot.info.dataset_version
        return Response(
            content=payload,
            media_type="text/csv" if query.format == "csv" else "application/x-ndjson",
            headers={
                "Content-Disposition": f'attachment; filename="mishearing-{version}.{query.format}"',
                "X-Dataset-Version": version,
                "X-Dataset-SHA256": snapshot.info.dataset_sha256,
                "X-Applied-Filters": canonical_json(
                    filters.model_dump(), ascii_only=True
                ),
                "X-Result-Count": str(len(matches)),
                "X-Export-SHA256": hashlib.sha256(payload).hexdigest(),
            },
        )

    return application
