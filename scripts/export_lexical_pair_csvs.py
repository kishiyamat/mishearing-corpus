"""Save full and reviewer-friendly lexical pair CSVs from the committed API."""

from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
from pathlib import Path

from corpus_api.pair_workflow import PAIR_FIELDS

EXPORT_FIELDS = (
    *PAIR_FIELDS,
    "dataset_version",
    "dataset_sha256",
    "pair_version",
    "pair_sha256",
)

REVIEW_COLUMNS = (
    "Src",
    "Tgt",
    "SrcReading",
    "TgtReading",
    "SrcMeaning",
    "TgtMeaning",
    "SrcQualifier",
    "TgtQualifier",
    "UnitType",
    "MishearID",
    "PairID",
    "URL",
    "Language",
)


def fetch_export(base_url: str) -> tuple[bytes, dict[str, str]]:
    """Fetch the lexical CSV and provenance headers from a running committed API."""
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/pairs/export?format=csv&unit_group=lexical",
        headers={"Accept": "text/csv"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read(), dict(response.headers.items())


def write_exports(output_dir: Path, payload: bytes, headers: dict[str, str]) -> None:
    """Write both CSV views and API provenance into a new directory."""
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing directory: {output_dir}")
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline="")))
    if not rows:
        raise ValueError("lexical API export is empty")
    fields = list(rows[0])
    if fields != list(EXPORT_FIELDS):
        raise ValueError("lexical API export does not match the 39-column schema")
    missing = set(REVIEW_COLUMNS) - set(fields)
    if missing:
        raise ValueError(f"lexical API export lacks required review columns: {missing}")
    if any(row["UnitType"] not in {"word", "compound"} for row in rows):
        raise ValueError("lexical export contains a non-lexical UnitType")
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "lexical-pairs-full.csv").write_bytes(payload)
    with (output_dir / "lexical-pairs-review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {field: row[field] for field in REVIEW_COLUMNS} for row in rows
        )
    metadata = {
        key.lower(): value
        for key, value in headers.items()
        if key.lower().startswith("x-")
    }
    (output_dir / "export-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    """Fetch the API's lexical export into an empty output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload, headers = fetch_export(args.base_url)
    write_exports(args.output_dir, payload, headers)
    print(
        f"wrote lexical-pairs-full.csv and lexical-pairs-review.csv to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
