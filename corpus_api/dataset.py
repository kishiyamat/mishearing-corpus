"""Load committed public inputs without reading dirty files or research assets."""

import csv
import hashlib
import io
import json
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from git import Blob, Repo, Tree
from git.exc import GitError

from .models import CSV_FIELDS, AppliedFilters, DatasetInfo, LinkQuality, Record


def canonical_json(value: object, *, ascii_only: bool = False) -> str:
    """Serialize deterministic JSON for checksums, exports and ASCII headers."""
    return json.dumps(
        value, ensure_ascii=ascii_only, sort_keys=True, separators=(",", ":")
    )


def _committed_inputs(repository: Path, ref: str) -> tuple[str, dict[str, bytes]]:
    """Read only allowlisted CSV/schema blobs from one resolved local commit.

    No checkout, fetch, filesystem traversal of data, or parent-repo discovery is
    performed. A Git checkout and all four input trees must be present.
    """
    try:
        with Repo(repository, search_parent_directories=False) as repo:
            commit = repo.commit(ref)
            files: dict[str, bytes] = {}
            for directory, suffix in (
                ("data/mishearing", ".csv"),
                ("data/tag", ".csv"),
                ("data/environment", ".csv"),
                ("schema", ".json"),
            ):
                tree = commit.tree / directory
                if not isinstance(tree, Tree):
                    raise TypeError(f"Missing committed input directory: {directory}")
                for item in tree.traverse():
                    if isinstance(item, Blob) and str(item.path).endswith(suffix):
                        if item.mode not in (0o100644, 0o100755):
                            raise ValueError(
                                f"Input must be a regular Git blob: {item.path}"
                            )
                        files[str(item.path)] = item.data_stream.read()
            return commit.hexsha, files
    except (GitError, KeyError, OSError, TypeError) as error:
        raise ValueError(
            f"Cannot load committed public dataset at {repository} ref {ref!r}: {error}"
        ) from error


def _rows(
    path: str, payload: bytes, columns: tuple[str, ...]
) -> Iterator[dict[str, str]]:
    """Parse exact UTF-8 CSV columns, preserving empty cells and embedded newlines."""
    try:
        reader = csv.reader(
            io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True
        )
        header = next(reader, None)
        if header != list(columns):
            raise ValueError(f"Unexpected CSV columns in {path}: {header!r}")
        for values in reader:
            # Empty physical lines have no cells and are not data records.
            if not values:
                continue
            if len(values) != len(columns):
                raise ValueError(
                    f"Malformed CSV row in {path} at line {reader.line_num}"
                )
            yield dict(zip(columns, values))
    except (UnicodeError, csv.Error) as error:
        raise ValueError(f"Invalid UTF-8 CSV in {path}: {error}") from error


def _links(
    files: Mapping[str, bytes], directory: str, key: str, record_ids: set[str]
) -> tuple[dict[str, set[str]], int]:
    """Join bridge rows to real records and count, rather than hide, orphan rows."""
    associations: dict[str, set[str]] = defaultdict(set)
    orphans = 0
    for path in sorted(files):
        if not path.startswith(f"data/{directory}/"):
            continue
        if path == f"data/{directory}/translation.csv":
            # Labels are not served by v1. Retain their bytes in the fingerprint,
            # without interpreting legacy translation rows or inferring synonyms.
            continue
        for row in _rows(path, files[path], ("MishearID", key)):
            if not row["MishearID"] or not row[key]:
                raise ValueError(f"Empty bridge key in {path}")
            if row["MishearID"] not in record_ids:
                orphans += 1
            else:
                associations[row["MishearID"]].add(row[key])
    return associations, orphans


def _classification_matches(
    actual: tuple[str, ...], selected: list[str], mode: str
) -> bool:
    """Apply AND/OR within one classification; an empty selection is unrestricted."""
    if not selected:
        return True
    if mode == "and":
        return set(selected).issubset(actual)
    return not set(selected).isdisjoint(actual)


def _matches(record: Record, filters: AppliedFilters) -> bool:
    """Combine literal text, exact metadata and classification conditions with AND."""
    if filters.q is not None and not any(
        filters.q.casefold() in text.casefold() for text in (record.Src, record.Tgt)
    ):
        return False
    for query, text in ((filters.src, record.Src), (filters.tgt, record.Tgt)):
        if query is not None and query.casefold() not in text.casefold():
            return False
    return (
        (filters.language is None or filters.language == record.Language)
        and (filters.source is None or filters.source == record.source)
        and _classification_matches(record.TagIDs, filters.tags, filters.tag_mode)
        and _classification_matches(
            record.EnvIDs, filters.environments, filters.environment_mode
        )
    )


@dataclass(frozen=True)
class CorpusSnapshot:
    """Hold validated, immutable records and metadata for one committed snapshot.

    Use ``snapshot = CorpusSnapshot.from_git(public_checkout, "HEAD")``, then
    ``snapshot.search(AppliedFilters(language="ja"))``. Git and filesystem changes
    after construction do not affect the instance. No Git handles remain open.
    """

    info: DatasetInfo
    records: tuple[Record, ...]
    by_id: Mapping[str, Record]

    @classmethod
    def from_git(cls, repository: Path, ref: str = "HEAD") -> "CorpusSnapshot":
        """Read and validate public blobs; reject unsupported schemas and duplicate IDs."""
        version, files = _committed_inputs(repository, ref)
        try:
            schema = json.loads(files["schema/mishearing.schema.json"])
            if [field["name"] for field in schema["fields"]] != list(CSV_FIELDS):
                raise ValueError("Unsupported mishearing schema columns")
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(
                "Missing or invalid schema/mishearing.schema.json"
            ) from error

        originals: dict[str, tuple[dict[str, str], str]] = {}
        for path in sorted(files):
            if not path.startswith("data/mishearing/"):
                continue
            for row in _rows(path, files[path], CSV_FIELDS):
                identifier = row["MishearID"]
                if not identifier or identifier in originals:
                    raise ValueError(
                        f"Empty or duplicate MishearID {identifier!r} in {path}"
                    )
                originals[identifier] = (row, path)
        if not originals:
            raise ValueError("The committed corpus contains no mishearing records")
        record_ids = set(originals)
        tags, orphan_tags = _links(files, "tag", "TagID", record_ids)
        environments, orphan_environments = _links(
            files, "environment", "EnvID", record_ids
        )
        records = tuple(
            Record(
                **row,
                TagIDs=tuple(sorted(tags.get(identifier, set()))),
                EnvIDs=tuple(sorted(environments.get(identifier, set()))),
                source=PurePosixPath(path)
                .relative_to("data/mishearing")
                .parent.as_posix(),
                source_file=path,
            )
            for identifier, (row, path) in sorted(originals.items())
        )
        manifest = [
            {"path": path, "sha256": hashlib.sha256(payload).hexdigest()}
            for path, payload in sorted(files.items())
        ]
        info = DatasetInfo(
            dataset_version=version,
            dataset_sha256=hashlib.sha256(
                canonical_json(manifest).encode("utf-8")
            ).hexdigest(),
            record_count=len(records),
            file_count=len(files),
            tag_ids=tuple(sorted({tag for record in records for tag in record.TagIDs})),
            environment_ids=tuple(
                sorted({env for record in records for env in record.EnvIDs})
            ),
            languages=tuple(sorted({record.Language for record in records})),
            sources=tuple(sorted({record.source for record in records})),
            quality=LinkQuality(
                orphan_tag_links=orphan_tags,
                orphan_environment_links=orphan_environments,
            ),
        )
        return cls(
            info,
            records,
            MappingProxyType({record.MishearID: record for record in records}),
        )

    def search(self, filters: AppliedFilters) -> tuple[Record, ...]:
        """Return all matches in stable MishearID order, including linkless records."""
        return tuple(record for record in self.records if _matches(record, filters))
