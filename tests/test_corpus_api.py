"""Contract tests for the read-only public corpus API described in docs/api.md."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from git import Actor, Repo

TestClient = pytest.importorskip("fastapi.testclient").TestClient
pytest.importorskip("httpx")


FIELDS = [
    "MishearID",
    "Src",
    "Tgt",
    "Tips",
    "Note",
    "OriginalFlag",
    "DocID",
    "URL",
    "SpeakerID",
    "ListenerID",
    "Language",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write deterministic UTF-8 CSV fixture data, preserving multiline cells."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _commit_public_fixture(repository: Path, mishearing_csv: str) -> str:
    """Commit a minimal public repository with caller-supplied mishearing CSV bytes."""
    repository.mkdir(parents=True)
    repo = Repo.init(repository)
    for kind, key in [("tag", "TagID"), ("environment", "EnvID")]:
        _write_csv(
            repository / "data" / kind / "source" / "records.csv",
            ["MishearID", key],
            [],
        )
        _write_csv(
            repository / "data" / kind / "translation.csv", [key, "Lang", "Label"], []
        )
    mishearing_path = repository / "data" / "mishearing" / "source" / "records.csv"
    mishearing_path.parent.mkdir(parents=True, exist_ok=True)
    mishearing_path.write_text(mishearing_csv, encoding="utf-8", newline="")
    schema_source = Path(__file__).parents[1] / "schema" / "mishearing.schema.json"
    schema_target = repository / "schema" / "mishearing.schema.json"
    schema_target.parent.mkdir(parents=True)
    schema_target.write_bytes(schema_source.read_bytes())
    input_files = [
        *(repository / "data").rglob("*.csv"),
        *(repository / "schema").rglob("*.json"),
    ]
    repo.index.add([str(path.relative_to(repository)) for path in input_files])
    actor = Actor("API tests", "api-tests@example.invalid")
    commit = repo.index.commit("malformed fixture", author=actor, committer=actor)
    version = commit.hexsha
    repo.close()
    return version


def _mishearing_row(
    identifier: str,
    src: str,
    tgt: str,
    *,
    flag: str = "True",
    language: str = "ja",
    tips: str = "",
    note: str = "",
    url: str = "",
) -> dict[str, str]:
    """Build one source-shaped fixture row without normalizing its string values."""
    return {
        "MishearID": identifier,
        "Src": src,
        "Tgt": tgt,
        "Tips": tips,
        "Note": note,
        "OriginalFlag": flag,
        "DocID": f"doc-{identifier}",
        "URL": url,
        "SpeakerID": "",
        "ListenerID": "",
        "Language": language,
    }


@pytest.fixture
def api_fixture(tmp_path: Path) -> Iterator[dict[str, Any]]:
    """Create and open a tiny committed corpus with intentional edge cases."""
    # Arrange: create a local Git corpus whose input order differs from ID order.
    repository_path = tmp_path / "public-corpus"
    repository_path.mkdir()
    repo = Repo.init(repository_path)
    mishearing = repository_path / "data" / "mishearing" / "sample-source"
    _write_csv(
        mishearing / "examples.csv",
        FIELDS,
        [
            _mishearing_row(
                "zeta",
                "CaseFold Café",
                "wrong, answer",
                flag="1",
                tips="first\nsecond",
                note="comma, inside",
                url="https://example.test/z",
            ),
            _mishearing_row(
                "alpha",
                "聞き間違い",
                "正しい解釈",
                flag="0",
                language="ja/en",
                tips="tip",
                note="note",
            ),
            _mishearing_row(
                "mu", "literal [brackets]", "target", flag="False", language="en"
            ),
        ],
    )
    _write_csv(
        repository_path / "data" / "tag" / "sample-source" / "examples.csv",
        ["MishearID", "TagID"],
        [
            {"MishearID": "zeta", "TagID": "TOPIC"},
            {"MishearID": "alpha", "TagID": "TOPIC"},
            {"MishearID": "alpha", "TagID": "FORMAL"},
            {"MishearID": "ghost", "TagID": "ORPHAN"},
        ],
    )
    _write_csv(
        repository_path / "data" / "environment" / "sample-source" / "examples.csv",
        ["MishearID", "EnvID"],
        [
            {"MishearID": "zeta", "EnvID": "PHONE"},
            {"MishearID": "alpha", "EnvID": "OFFICE"},
        ],
    )
    _write_csv(
        repository_path / "data" / "tag" / "translation.csv",
        ["TagID", "Lang", "Label"],
        [{"TagID": "TOPIC", "Lang": "en", "Label": "Topic"}],
    )
    _write_csv(
        repository_path / "data" / "environment" / "translation.csv",
        ["EnvID", "Lang", "Label"],
        [{"EnvID": "PHONE", "Lang": "en", "Label": "Phone"}],
    )
    schema_source = Path(__file__).parents[1] / "schema" / "mishearing.schema.json"
    schema_target = repository_path / "schema" / "mishearing.schema.json"
    schema_target.parent.mkdir(parents=True)
    schema_target.write_bytes(schema_source.read_bytes())

    input_files = [
        *(repository_path / "data").rglob("*.csv"),
        *(repository_path / "schema").rglob("*.json"),
    ]
    repo.index.add([str(path.relative_to(repository_path)) for path in input_files])
    actor = Actor("API tests", "api-tests@example.invalid")
    commit = repo.index.commit("fixture corpus", author=actor, committer=actor)

    # Arrange: the API instance must load exactly the committed revision.
    from corpus_api.main import create_app

    app = create_app(repository=repository_path, dataset_ref=commit.hexsha)
    try:
        with TestClient(app) as client:
            yield {
                "client": client,
                "repo": repo,
                "repository": repository_path,
                "version": commit.hexsha,
            }
    finally:
        repo.close()


def _record_rows(response: Any) -> list[dict[str, Any]]:
    """Return record results from a successful list response."""
    assert response.status_code == 200, response.text
    return response.json()["records"]


def test_datasets_reports_snapshot_counts_catalogs_and_orphans(
    api_fixture: dict[str, Any],
) -> None:
    """The catalog describes one immutable corpus snapshot and its link quality."""
    # Arrange: use the fixture's already-started API client.
    client = api_fixture["client"]

    # Act: retrieve the advertised dataset.
    response = client.get("/v1/datasets")

    # Assert: expose committed version, record count and link anomaly counts.
    assert response.status_code == 200
    dataset = response.json()["datasets"][0]
    assert dataset["dataset_version"] == api_fixture["version"]
    assert dataset["record_count"] == 3
    assert dataset["tag_ids"] == ["FORMAL", "TOPIC"]
    assert dataset["environment_ids"] == ["OFFICE", "PHONE"]
    assert dataset["languages"] == ["en", "ja", "ja/en"]
    assert dataset["sources"] == ["sample-source"]
    assert dataset["quality"] == {"orphan_tag_links": 1, "orphan_environment_links": 0}
    assert len(dataset["dataset_sha256"]) == 64


def test_default_head_api_matches_all_committed_public_csv_inputs() -> None:
    """The default HEAD API returns every public record with exact source joins."""
    # Arrange: build expected records and bridges directly from committed Git blobs.
    from corpus_api.main import create_app

    repository = Path(__file__).parents[1]
    repo = Repo(repository, search_parent_directories=False)
    try:
        commit = repo.commit("HEAD")
        expected: dict[str, dict[str, Any]] = {}
        tags: dict[str, set[str]] = {}
        environments: dict[str, set[str]] = {}
        for item in commit.tree.traverse():
            path = str(item.path)
            if not path.endswith(".csv") or not path.startswith(
                ("data/mishearing/", "data/tag/", "data/environment/")
            ):
                continue
            if path.endswith("/translation.csv"):
                continue
            with io.StringIO(
                item.data_stream.read().decode("utf-8-sig"), newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            if path.startswith("data/mishearing/"):
                for row in rows:
                    expected[row["MishearID"]] = {"values": row, "path": path}
            elif path.startswith("data/tag/"):
                for row in rows:
                    tags.setdefault(row["MishearID"], set()).add(row["TagID"])
            else:
                for row in rows:
                    environments.setdefault(row["MishearID"], set()).add(row["EnvID"])

        # Act: run the default app and collect every stable ID-sorted page.
        with TestClient(create_app()) as client:
            catalog_response = client.get("/v1/datasets")
            catalog = catalog_response.json()["datasets"][0]
            api_records: list[dict[str, Any]] = []
            offset = 0
            while True:
                response = client.get(
                    "/v1/records",
                    params={
                        "dataset_version": commit.hexsha,
                        "limit": 1000,
                        "offset": offset,
                    },
                )
                assert response.status_code == 200, response.text
                payload = response.json()
                api_records.extend(payload["records"])
                if payload["next_offset"] is None:
                    break
                offset = payload["next_offset"]

        # Assert: all source cells and bridge/source associations agree exactly.
        assert catalog_response.status_code == 200
        assert catalog["dataset_version"] == commit.hexsha
        assert catalog["record_count"] == len(expected)
        assert len(api_records) == len(expected)
        assert [record["MishearID"] for record in api_records] == sorted(expected)
        for record in api_records:
            source = expected[record["MishearID"]]
            for column in FIELDS:
                assert record[column] == source["values"][column]
            assert record["TagIDs"] == sorted(tags.get(record["MishearID"], set()))
            assert record["EnvIDs"] == sorted(
                environments.get(record["MishearID"], set())
            )
            assert record["source_file"] == source["path"]
            assert (
                record["source"]
                == Path(source["path"]).parent.relative_to("data/mishearing").as_posix()
            )
    finally:
        repo.close()


def test_records_are_sorted_keep_source_strings_and_include_linkless_record(
    api_fixture: dict[str, Any],
) -> None:
    """List results preserve CSV strings and empty associations without dropping rows."""
    # Arrange: request the complete result set in one page.
    client = api_fixture["client"]

    # Act: read all records from the committed snapshot.
    response = client.get(
        "/v1/records", params={"dataset_version": api_fixture["version"], "limit": 10}
    )

    # Assert: IDs sort independently of file order and original strings survive.
    payload = response.json()
    assert payload["dataset_version"] == api_fixture["version"]
    assert payload["total"] == 3
    assert payload["next_offset"] is None
    assert [row["MishearID"] for row in payload["records"]] == ["alpha", "mu", "zeta"]
    alpha, mu, zeta = payload["records"]
    assert alpha["OriginalFlag"] == "0"
    assert alpha["Language"] == "ja/en"
    assert mu["OriginalFlag"] == "False"
    assert mu["TagIDs"] == [] and mu["EnvIDs"] == []
    assert zeta["OriginalFlag"] == "1"
    assert zeta["Tips"] == "first\nsecond"
    assert zeta["Note"] == "comma, inside"
    assert zeta["source"] == "sample-source"
    assert zeta["source_file"] == "data/mishearing/sample-source/examples.csv"
    assert zeta["URL"] == "https://example.test/z"


def test_filters_are_echoed_with_sorted_deduplicated_classification_ids(
    api_fixture: dict[str, Any],
) -> None:
    """Responses report normalized effective filters, independent of input order."""
    # Arrange: repeat and reorder classification IDs while adding a text condition.
    client = api_fixture["client"]
    params = [
        ("tags", "TOPIC"),
        ("tags", "FORMAL"),
        ("tags", "TOPIC"),
        ("tag_mode", "or"),
        ("environments", "PHONE"),
        ("environments", "OFFICE"),
        ("environment_mode", "or"),
        ("src", "casefold"),
    ]

    # Act: retrieve one row matching both text and classification filters.
    response = client.get("/v1/records", params=params)

    # Assert: IDs are canonicalized and conditions intersect across filter kinds.
    assert response.status_code == 200
    assert response.json()["filters"] == {
        "q": None,
        "src": "casefold",
        "tgt": None,
        "tags": ["FORMAL", "TOPIC"],
        "tag_mode": "or",
        "environments": ["OFFICE", "PHONE"],
        "environment_mode": "or",
        "language": None,
        "source": None,
    }
    assert [row["MishearID"] for row in response.json()["records"]] == ["zeta"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"tags": ["TOPIC", "FORMAL"], "tag_mode": "and"}, ["alpha"]),
        ({"tags": ["TOPIC", "FORMAL"], "tag_mode": "or"}, ["alpha", "zeta"]),
        ({"environments": ["PHONE", "OFFICE"], "environment_mode": "and"}, []),
        (
            {"environments": ["PHONE", "OFFICE"], "environment_mode": "or"},
            ["alpha", "zeta"],
        ),
        ({"tags": ["UNKNOWN"]}, []),
    ],
)
def test_classification_filters_apply_and_or_and_unknown_ids_match_none(
    api_fixture: dict[str, Any], params: dict[str, Any], expected: list[str]
) -> None:
    """Tag and environment modes combine within their own classification."""
    # Arrange: use one or more repeated classification query parameters.
    client = api_fixture["client"]

    # Act: apply the requested classification filter.
    response = client.get("/v1/records", params=params)

    # Assert: preserve the specified AND/OR semantics and unknown-ID behavior.
    assert [row["MishearID"] for row in _record_rows(response)] == expected


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"q": "CAFÉ"}, ["zeta"]),
        ({"src": "聞き間違い", "language": "ja/en"}, ["alpha"]),
        ({"src": "[brackets]"}, ["mu"]),
        ({"source": "sample-source"}, ["alpha", "mu", "zeta"]),
    ],
)
def test_text_language_and_source_filters_use_literal_matching(
    api_fixture: dict[str, Any], params: dict[str, Any], expected: list[str]
) -> None:
    """Search uses Unicode casefold and literal substrings without normalization."""
    # Arrange: provide literal text, language or source filters.
    client = api_fixture["client"]

    # Act: query records using the supplied conditions.
    response = client.get("/v1/records", params=params)

    # Assert: only exact language/source or literal casefolded substrings match.
    assert [row["MishearID"] for row in _record_rows(response)] == expected


@pytest.mark.parametrize(
    "params",
    [
        {"typo": "value"},
        {"q": ""},
        {"tag_mode": "xor"},
        {"limit": 0},
        {"offset": -1},
    ],
)
def test_invalid_parameters_return_422(
    api_fixture: dict[str, Any], params: dict[str, Any]
) -> None:
    """Unknown, empty or out-of-range query parameters are rejected."""
    # Arrange: use a query violating one documented validation rule.
    client = api_fixture["client"]

    # Act: send the invalid query to the list endpoint.
    response = client.get("/v1/records", params=params)

    # Assert: report a client validation error.
    assert response.status_code == 422


def test_pagination_is_stable_and_dataset_version_is_enforced(
    api_fixture: dict[str, Any],
) -> None:
    """Pages use stable ID ordering and requests cannot silently change snapshots."""
    # Arrange: address one advertised version and request consecutive pages.
    client = api_fixture["client"]
    version = api_fixture["version"]

    # Act: read two pages, then request an unavailable dataset revision.
    first = client.get("/v1/records", params={"dataset_version": version, "limit": 2})
    second = client.get(
        "/v1/records", params={"dataset_version": version, "limit": 2, "offset": 2}
    )
    missing = client.get("/v1/records", params={"dataset_version": "f" * 40})

    # Assert: page boundaries are explicit and unknown versions return 404.
    assert [row["MishearID"] for row in first.json()["records"]] == ["alpha", "mu"]
    assert first.json()["next_offset"] == 2
    assert [row["MishearID"] for row in second.json()["records"]] == ["zeta"]
    assert second.json()["next_offset"] is None
    assert missing.status_code == 404


def test_single_record_uses_exact_id_and_returns_404_for_unknown_id(
    api_fixture: dict[str, Any],
) -> None:
    """Single-record lookup is a complete ID match against the fixed snapshot."""
    # Arrange: address the record by its exact identifier.
    client = api_fixture["client"]

    # Act: fetch one present and one absent identifier.
    found = client.get(
        "/v1/records/alpha", params={"dataset_version": api_fixture["version"]}
    )
    missing = client.get("/v1/records/Alpha")

    # Assert: return the source record and a not-found response respectively.
    assert found.status_code == 200
    assert found.json()["record"]["MishearID"] == "alpha"
    assert missing.status_code == 404


def test_export_csv_round_trips_fields_metadata_filters_and_body_hash(
    api_fixture: dict[str, Any],
) -> None:
    """CSV export includes all matches, metadata and a digest of response bytes."""
    # Arrange: select all records and request CSV output.
    client = api_fixture["client"]

    # Act: export rows and parse the returned UTF-8 CSV.
    response = client.get("/v1/export", params={"format": "csv", "q": "wrong"})
    parsed = list(csv.DictReader(io.StringIO(response.text)))

    # Assert: keep quoted commas, original columns and snapshot provenance.
    assert response.status_code == 200
    assert len(parsed) == 1
    assert parsed[0]["MishearID"] == "zeta"
    assert parsed[0]["Note"] == "comma, inside"
    assert parsed[0]["Tips"] == "first\nsecond"
    assert json.loads(parsed[0]["TagIDs"]) == ["TOPIC"]
    assert parsed[0]["dataset_version"] == api_fixture["version"]
    assert response.headers["X-Dataset-Version"] == api_fixture["version"]
    assert response.headers["X-Dataset-SHA256"]
    assert response.headers["X-Applied-Filters"] == json.dumps(
        response.headers.get("X-Applied-Filters")
        and json.loads(response.headers["X-Applied-Filters"]),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    assert response.headers["X-Result-Count"] == "1"
    assert (
        response.headers["X-Export-SHA256"]
        == hashlib.sha256(response.content).hexdigest()
    )


def test_csv_and_jsonl_export_contain_the_same_complete_enriched_rows(
    api_fixture: dict[str, Any],
) -> None:
    """Both export formats represent the same full match set and associations."""
    # Arrange: select all rows in both supported serialization formats.
    client = api_fixture["client"]

    # Act: fetch the two complete exports.
    csv_response = client.get("/v1/export", params={"format": "csv"})
    jsonl_response = client.get("/v1/export", params={"format": "jsonl"})
    csv_rows = list(csv.DictReader(io.StringIO(csv_response.text)))
    jsonl_rows = [json.loads(line) for line in jsonl_response.text.splitlines()]

    # Assert: every original and added field agrees after decoding CSV arrays.
    decoded_csv_rows = [
        row | {"TagIDs": json.loads(row["TagIDs"]), "EnvIDs": json.loads(row["EnvIDs"])}
        for row in csv_rows
    ]
    assert [row["MishearID"] for row in decoded_csv_rows] == ["alpha", "mu", "zeta"]
    assert decoded_csv_rows == jsonl_rows


def test_cors_exposes_export_provenance_headers(api_fixture: dict[str, Any]) -> None:
    """Browser clients can read the export provenance headers cross-origin."""
    # Arrange: prepare a cross-origin request for an export response.
    client = api_fixture["client"]

    # Act: retrieve the export with a browser Origin header.
    response = client.get(
        "/v1/export",
        headers={"Origin": "https://consumer.example"},
    )

    # Assert: allow read access and expose all documented response metadata.
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    exposed = {
        value.strip().lower()
        for value in response.headers["Access-Control-Expose-Headers"].split(",")
    }
    assert {
        "x-dataset-version",
        "x-dataset-sha256",
        "x-applied-filters",
        "x-result-count",
        "x-export-sha256",
    }.issubset(exposed)


def test_export_jsonl_round_trips_and_empty_exports_have_documented_shapes(
    api_fixture: dict[str, Any],
) -> None:
    """JSONL returns one enriched row per line and empty outputs retain format shape."""
    # Arrange: request a JSONL result and a zero-match export in each format.
    client = api_fixture["client"]

    # Act: fetch JSONL and empty CSV/JSONL responses.
    jsonl = client.get("/v1/export", params={"format": "jsonl"})
    empty_csv = client.get(
        "/v1/export", params={"format": "csv", "language": "not-present"}
    )
    empty_jsonl = client.get(
        "/v1/export", params={"format": "jsonl", "language": "not-present"}
    )

    # Assert: JSONL preserves strings and IDs; empty responses follow the contract.
    rows = [json.loads(line) for line in jsonl.text.splitlines()]
    assert [row["MishearID"] for row in rows] == ["alpha", "mu", "zeta"]
    assert rows[-1]["OriginalFlag"] == "1"
    assert jsonl.headers["X-Result-Count"] == "3"
    assert (
        empty_csv.text.endswith("\n")
        and len(list(csv.reader(io.StringIO(empty_csv.text)))) == 1
    )
    assert empty_jsonl.content == b""
    assert empty_csv.headers["X-Result-Count"] == "0"
    assert empty_jsonl.headers["X-Export-SHA256"] == hashlib.sha256(b"").hexdigest()


def test_export_rejects_pagination_parameters(api_fixture: dict[str, Any]) -> None:
    """Export is an all-matches operation and does not accept page controls."""
    # Arrange: include a list-only pagination parameter.
    client = api_fixture["client"]

    # Act: request an export with an offset.
    response = client.get("/v1/export", params={"offset": 1})

    # Assert: reject the unsupported parameter.
    assert response.status_code == 422


def test_startup_snapshot_ignores_uncommitted_csv_and_survives_head_advance(
    api_fixture: dict[str, Any],
) -> None:
    """A running API instance remains bound to its startup Git object."""
    # Arrange: retain the active client and alter the worktree after startup.
    client = api_fixture["client"]
    repo = api_fixture["repo"]
    version = api_fixture["version"]
    dirty_path = (
        api_fixture["repository"]
        / "data"
        / "mishearing"
        / "sample-source"
        / "uncommitted.csv"
    )
    _write_csv(dirty_path, FIELDS, [_mishearing_row("dirty", "new", "row")])

    # Act: query the existing process and advance HEAD with another committed row.
    before_commit = client.get("/v1/records")
    repo.index.add([str(dirty_path.relative_to(api_fixture["repository"]))])
    actor = Actor("API tests", "api-tests@example.invalid")
    new_commit = repo.index.commit("advance corpus", author=actor, committer=actor)
    after_commit = client.get("/v1/records")

    # Assert: worktree and branch changes do not change the live process snapshot.
    assert new_commit.hexsha != version
    assert [row["MishearID"] for row in before_commit.json()["records"]] == [
        "alpha",
        "mu",
        "zeta",
    ]
    assert [row["MishearID"] for row in after_commit.json()["records"]] == [
        "alpha",
        "mu",
        "zeta",
    ]
    assert after_commit.json()["dataset_version"] == version


def test_new_instance_ignores_uncommitted_csv_at_selected_commit(
    api_fixture: dict[str, Any],
) -> None:
    """A fresh API instance reads the selected commit rather than a dirty worktree."""
    # Arrange: add an untracked data shard to the fixture's working tree.
    from corpus_api.main import create_app

    repository = api_fixture["repository"]
    version = api_fixture["version"]
    _write_csv(
        repository / "data" / "mishearing" / "sample-source" / "dirty.csv",
        FIELDS,
        [_mishearing_row("dirty", "uncommitted", "row")],
    )

    # Act: start a new process view pinned to the original commit.
    with TestClient(create_app(repository=repository, dataset_ref=version)) as client:
        response = client.get("/v1/records")

    # Assert: the uncommitted ID is absent and the original record count remains.
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert "dirty" not in [row["MishearID"] for row in response.json()["records"]]


def test_explicit_old_commit_ref_loads_that_revision(
    api_fixture: dict[str, Any],
) -> None:
    """A newly created app can load an explicitly selected local historical commit."""
    # Arrange: create a later commit after the fixture snapshot.
    repository = api_fixture["repository"]
    repo = api_fixture["repo"]
    original_version = api_fixture["version"]
    note_path = repository / "unrelated.txt"
    note_path.write_text("advance HEAD\n", encoding="utf-8")
    repo.index.add(["unrelated.txt"])
    actor = Actor("API tests", "api-tests@example.invalid")
    latest = repo.index.commit("newer commit", author=actor, committer=actor)
    assert latest.hexsha != original_version

    # Act: initialize a fresh app at the old, still-local Git commit.
    from corpus_api.main import create_app

    app = create_app(repository=repository, dataset_ref=original_version)
    with TestClient(app) as client:
        response = client.get("/v1/datasets")

    # Assert: the requested historical revision is advertised exactly.
    assert response.status_code == 200
    assert response.json()["datasets"][0]["dataset_version"] == original_version


def test_duplicate_mishear_ids_fail_during_startup(
    api_fixture: dict[str, Any], tmp_path: Path
) -> None:
    """Duplicate primary keys are rejected instead of silently overwriting rows."""
    # Arrange: create a new committed repository containing a duplicate primary key.
    repository = tmp_path / "duplicate-corpus"
    repository.mkdir()
    repo = Repo.init(repository)
    source = repository / "data" / "mishearing" / "source"
    _write_csv(
        source / "duplicates.csv",
        FIELDS,
        [_mishearing_row("same", "first", "a"), _mishearing_row("same", "second", "b")],
    )
    for kind, fields in [
        ("tag", ["MishearID", "TagID"]),
        ("environment", ["MishearID", "EnvID"]),
    ]:
        _write_csv(repository / "data" / kind / "source" / "duplicates.csv", fields, [])
    for kind, fields in [
        ("tag", ["TagID", "Lang", "Label"]),
        ("environment", ["EnvID", "Lang", "Label"]),
    ]:
        _write_csv(repository / "data" / kind / "translation.csv", fields, [])
    schema_source = Path(__file__).parents[1] / "schema" / "mishearing.schema.json"
    schema_target = repository / "schema" / "mishearing.schema.json"
    schema_target.parent.mkdir()
    schema_target.write_bytes(schema_source.read_bytes())
    input_files = [
        *(repository / "data").rglob("*.csv"),
        *(repository / "schema").rglob("*.json"),
    ]
    repo.index.add([str(path.relative_to(repository)) for path in input_files])
    actor = Actor("API tests", "api-tests@example.invalid")
    commit = repo.index.commit("duplicate fixture", author=actor, committer=actor)

    # Act and assert: starting the API raises the documented validation error.
    from corpus_api.main import create_app

    with (
        pytest.raises(ValueError),
        TestClient(create_app(repository=repository, dataset_ref=commit.hexsha)),
    ):
        pass
    repo.close()


@pytest.mark.parametrize(
    "csv_content",
    [
        "MishearID,Src,Tgt,Tips,Note,OriginalFlag,DocID,URL,SpeakerID,ListenerID,Language\n,src,tgt,,,,,,,,ja\n",
        "MishearID,Src,Tgt,Tips,Note,OriginalFlag,DocID,URL,SpeakerID,ListenerID\nid,src,tgt,tips,note,flag,doc,url,speaker,listener\n",
        "MishearID,Src,Tgt,Tips,Note,OriginalFlag,DocID,URL,SpeakerID,ListenerID,Language,Extra\nid,src,tgt,tips,note,flag,doc,url,speaker,listener,ja,x\n",
        "MishearID,Src,Tgt,Tips,Note,OriginalFlag,DocID,URL,SpeakerID,ListenerID,Language\nid,src,tgt\n",
        'MishearID,Src,Tgt,Tips,Note,OriginalFlag,DocID,URL,SpeakerID,ListenerID,Language\nid,"unterminated\n',
    ],
    ids=["empty-id", "missing-column", "extra-column", "short-row", "unclosed-quote"],
)
def test_malformed_mishear_csv_fails_startup(tmp_path: Path, csv_content: str) -> None:
    """Invalid source headers, keys and rows fail instead of being discarded."""
    # Arrange: commit one malformed CSV into an otherwise complete public fixture.
    from corpus_api.main import create_app

    repository = tmp_path / "malformed-corpus"
    version = _commit_public_fixture(repository, csv_content)

    # Act and assert: loading the selected revision fails before serving requests.
    with (
        pytest.raises(ValueError),
        TestClient(create_app(repository=repository, dataset_ref=version)),
    ):
        pass


def test_environment_variables_select_repository_and_dataset_ref(
    api_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Configured environment values select the same local repository and commit."""
    # Arrange: point both supported configuration variables at the committed fixture.
    from corpus_api.main import create_app

    monkeypatch.setenv("MISHEARING_CORPUS_ROOT", str(api_fixture["repository"]))
    monkeypatch.setenv("MISHEARING_DATASET_REF", api_fixture["version"])

    # Act: create the app without explicit arguments and run its lifespan.
    with TestClient(create_app()) as client:
        response = client.get("/v1/datasets")

    # Assert: the selected commit is exactly the advertised version.
    assert response.status_code == 200
    assert response.json()["datasets"][0]["dataset_version"] == api_fixture["version"]


def test_dataset_fingerprint_tracks_public_input_bytes_not_unrelated_files(
    api_fixture: dict[str, Any],
) -> None:
    """The content fingerprint ignores unrelated files and changes with CSV bytes."""
    # Arrange: retain the baseline digest and prepare a new unrelated Git commit.
    from corpus_api.main import create_app

    repository = api_fixture["repository"]
    repo = api_fixture["repo"]
    original_sha = (
        api_fixture["client"]
        .get("/v1/datasets")
        .json()["datasets"][0]["dataset_sha256"]
    )
    note_path = repository / "unrelated.txt"
    note_path.write_text("metadata outside the public dataset\n", encoding="utf-8")
    repo.index.add(["unrelated.txt"])
    actor = Actor("API tests", "api-tests@example.invalid")
    unrelated_commit = repo.index.commit(
        "unrelated file", author=actor, committer=actor
    )

    # Act: compare the unchanged corpus snapshot, then commit a CSV byte change.
    with TestClient(
        create_app(repository=repository, dataset_ref=unrelated_commit.hexsha)
    ) as client:
        unchanged_sha = client.get("/v1/datasets").json()["datasets"][0][
            "dataset_sha256"
        ]
    csv_path = repository / "data" / "mishearing" / "sample-source" / "examples.csv"
    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["Tips"] += " changed"
    _write_csv(csv_path, FIELDS, rows)
    repo.index.add([str(csv_path.relative_to(repository))])
    changed_commit = repo.index.commit(
        "change public CSV", author=actor, committer=actor
    )
    with TestClient(
        create_app(repository=repository, dataset_ref=changed_commit.hexsha)
    ) as client:
        changed_sha = client.get("/v1/datasets").json()["datasets"][0]["dataset_sha256"]

    # Assert: unrelated Git history does not affect the digest; data bytes do.
    assert unchanged_sha == original_sha
    assert changed_sha != original_sha


def test_unknown_dataset_version_is_rejected_for_export_and_single_record(
    api_fixture: dict[str, Any],
) -> None:
    """Version pinning is enforced consistently on every applicable endpoint."""
    # Arrange: request a syntactically valid but unavailable dataset SHA.
    client = api_fixture["client"]
    unknown_version = "f" * 40

    # Act: request an export and a single record from that unavailable version.
    export = client.get("/v1/export", params={"dataset_version": unknown_version})
    record = client.get(
        "/v1/records/alpha", params={"dataset_version": unknown_version}
    )

    # Assert: neither endpoint silently falls back to the loaded snapshot.
    assert export.status_code == 404
    assert record.status_code == 404
