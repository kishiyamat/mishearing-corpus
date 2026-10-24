from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from git import Actor, Repo

from corpus_api.dataset import CorpusSnapshot
from corpus_api.pair_workflow import (
    build_artifacts,
    load_reviews,
    original_hash,
    review_csv,
    validate_artifacts,
    validate_index,
    working_snapshot,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
pytest.importorskip("httpx")

from corpus_api.pairs import load_pair_snapshot

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


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    """Write test CSV rows with a stable header and line ending."""
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _mishearing_row(identifier: str, src: str, tgt: str) -> dict[str, str]:
    """Construct one complete source record for the public corpus fixture."""
    return dict.fromkeys(FIELDS, "") | {
        "MishearID": identifier,
        "Src": src,
        "Tgt": tgt,
        "OriginalFlag": "True",
        "DocID": f"doc-{identifier}",
        "Language": "ja",
    }


def _commit_public_fixture(root: Path, content: str) -> str:
    """Commit a tiny valid corpus and return its immutable source revision."""
    from corpus_api.models import CSV_FIELDS

    root.mkdir(parents=True)
    repo = Repo.init(root)
    _write_csv(root / "data/mishearing/sample/records.csv", list(CSV_FIELDS), [])
    # Replace empty file with the exact supplied original CSV bytes.
    (root / "data/mishearing/sample/records.csv").write_text(
        content, encoding="utf-8", newline=""
    )
    for kind, key in (("tag", "TagID"), ("environment", "EnvID")):
        _write_csv(root / f"data/{kind}/source/records.csv", ["MishearID", key], [])
        _write_csv(root / f"data/{kind}/translation.csv", [key, "Lang", "Label"], [])
    schema_source = Path(__file__).parents[1] / "schema/mishearing.schema.json"
    target = root / "schema/mishearing.schema.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(schema_source.read_bytes())
    repo.index.add(
        [str(path.relative_to(root)) for path in [*root.glob("data/**/*.csv"), target]]
    )
    commit = repo.index.commit(
        "corpus fixture",
        author=Actor("tests", "tests@example.invalid"),
        committer=Actor("tests", "tests@example.invalid"),
    )
    repo.close()
    return commit.hexsha


def _review(
    record: dict[str, str], decision: str, status: str = "reviewed"
) -> dict[str, object]:
    """Create an explicitly attributed source-bound fixture review."""
    return {
        "MishearID": record["MishearID"],
        "OriginalHash": original_hash(record),
        "Reviewer": "fixture-reviewer",
        "ReviewedAt": "2026-10-24",
        "Evidence": "fixture evidence",
        "Reason": "fixture decision",
        "Status": status,
        "TargetDecision": decision,
        "SrcAnnotations": [],
        "TgtAnnotations": [],
        "PairSpans": [
            {
                "src_start": 0,
                "src_end": len(record["Src"]),
                "tgt_start": 0,
                "tgt_end": len(record["Tgt"]),
                "unit_type": "phrase",
            }
        ],
    }


def _fixture_repository(root: Path, *, complete: bool = True) -> tuple[Path, str, str]:
    """Create corpus and pair artifacts in immutable commits for adapter tests."""
    rows = [
        _mishearing_row("include", "|熊谷《くまがや》", "|反町《そりまち》"),
        _mishearing_row("exclude", "|銀行《ぎんこう》", "|金庫《きんこ》"),
        _mishearing_row("pending", "|下手《したて》", "|下手《へた》"),
        _mishearing_row("untouched", "|駅《えき》", "|液《えき》"),
    ]
    # Use the existing tiny committed corpus helper to establish schema and relations.
    import csv
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    initial_commit = _commit_public_fixture(root, stream.getvalue())
    corpus = CorpusSnapshot.from_git(root, initial_commit)
    raw_records = [
        {
            key: str(getattr(record, key))
            for key in (
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
            )
        }
        for record in corpus.records
    ]
    records_by_id = {record["MishearID"]: record for record in raw_records}
    reviews = [
        _review(records_by_id["include"], "include"),
        _review(records_by_id["exclude"], "exclude"),
        _review(records_by_id["pending"], "undecided", "pending"),
    ]
    if complete:
        reviews.append(_review(records_by_id["untouched"], "exclude"))
    review_payload = review_csv(reviews)
    reviews = load_reviews(review_payload)
    artifacts = build_artifacts(
        corpus, reviews, tokenizer=lambda text: [(0, len(text))] if text else []
    )
    run_dir = root / "resource/pairs_v2/2026-10-24-initial"
    run_dir.mkdir(parents=True)
    for filename, payload in artifacts.items():
        (run_dir / filename).write_bytes(payload)
    annotation_path = root / "data/annotations/reviews.csv"
    annotation_path.parent.mkdir(parents=True)
    annotation_path.write_bytes(review_payload)
    pointer = root / "resource/pairs_v2/current.json"
    pointer.write_text('{"directory":"2026-10-24-initial"}\n', encoding="utf-8")
    repo = Repo(root)
    repo.index.add(
        [
            str(path.relative_to(root))
            for path in [*run_dir.iterdir(), annotation_path, pointer]
        ]
    )
    commit = repo.index.commit(
        "pair fixture",
        author=Actor("tests", "tests@example.invalid"),
        committer=Actor("tests", "tests@example.invalid"),
    )
    repo.close()
    return root, initial_commit, commit.hexsha


@pytest.fixture
def served_pairs(tmp_path: Path) -> Any:
    """Start a service from a commit containing its committed pair snapshot."""
    root, _, ref = _fixture_repository(tmp_path / "pairs", complete=True)
    from corpus_api.main import create_app

    with TestClient(create_app(repository=root, dataset_ref=ref)) as client:
        yield {"client": client, "root": root, "ref": ref}


def test_pair_snapshot_uses_only_allowlisted_committed_blobs_and_hashes_them(
    served_pairs: Any,
) -> None:
    """Uncommitted pair edits must not affect the selected committed snapshot."""
    repo_path = served_pairs["root"]
    repo = Repo(repo_path)
    corpus = CorpusSnapshot.from_git(repo_path, served_pairs["ref"])
    snapshot = load_pair_snapshot(repo_path, served_pairs["ref"], corpus)
    before = snapshot.checksum

    dirty = repo_path / "resource/pairs_v2/2026-10-24-initial/reviewed.csv"
    dirty.write_text("corrupt worktree content", encoding="utf-8")
    assert load_pair_snapshot(repo_path, served_pairs["ref"], corpus).checksum == before
    repo.close()


def test_pair_routes_search_filter_and_paginate(served_pairs: Any) -> None:
    """Search, pagination, exact lookup and version constraints share provenance."""
    client = served_pairs["client"]
    first = client.get("/v1/pairs", params={"limit": 1})
    assert first.status_code == 200
    body = first.json()
    assert body["total"] == 3
    assert len(body["pairs"]) == 1
    assert body["next_offset"] == 1
    filtered = client.get("/v1/pairs", params={"q": "くま", "mishear_id": "include"})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["pairs"][0]["TargetDecision"] == "include"
    dataset = client.get("/v1/datasets").json()["datasets"][0]
    assert filtered.json()["dataset_sha256"] == dataset["dataset_sha256"]
    assert filtered.json()["dataset_sha256"] != filtered.json()["pair_sha256"]
    assert client.get("/v1/pairs", params={"q": "KUMA"}).json()["total"] == 0
    assert client.get("/v1/pairs", params={"unit_type": "phrase"}).json()["total"] == 3
    assert client.get("/v1/pairs", params={"unknown": "x"}).status_code == 422
    assert client.get("/v1/pairs", params={"unit_type": "invalid"}).status_code == 422
    assert client.get("/v1/pairs/export", params={"extra": "x"}).status_code == 422
    assert (
        client.get("/v1/pairs", params={"dataset_version": "0" * 40}).status_code == 404
    )
    assert client.get("/v1/pairs/not-present").status_code == 404
    pair_id = filtered.json()["pairs"][0]["PairID"]
    assert client.get(f"/v1/pairs/{pair_id}").json()["pair"]["MishearID"] == "include"
    assert (
        client.get(f"/v1/pairs/{pair_id}").json()["dataset_sha256"]
        == dataset["dataset_sha256"]
    )
    assert client.get(f"/v1/pairs/{pair_id}", params={"extra": "x"}).status_code == 422


def test_pair_export_blocks_unprocessed_and_emits_only_includes_when_complete(
    tmp_path: Path,
) -> None:
    """Evaluation export refuses incomplete record review coverage."""
    root, _, incomplete_ref = _fixture_repository(
        tmp_path / "incomplete", complete=False
    )
    from corpus_api.main import create_app

    with TestClient(create_app(repository=root, dataset_ref=incomplete_ref)) as client:
        response = client.get("/v1/pairs/export")
        assert response.status_code == 409


def test_pair_export_csv_and_jsonl_share_provenance_and_exclude_excluded_rows(
    served_pairs: Any,
) -> None:
    """Both formats expose identical versions and only included reviewed pairs."""
    client = served_pairs["client"]
    csv_response = client.get("/v1/pairs/export", params={"format": "csv"})
    jsonl_response = client.get("/v1/pairs/export", params={"format": "jsonl"})
    assert csv_response.status_code == jsonl_response.status_code == 200
    assert (
        csv_response.headers["x-pair-version"]
        == jsonl_response.headers["x-pair-version"]
    )
    assert (
        csv_response.headers["x-pair-sha256"] == jsonl_response.headers["x-pair-sha256"]
    )
    assert csv_response.headers["x-coverage"] == jsonl_response.headers["x-coverage"]
    coverage = json.loads(csv_response.headers["x-coverage"])
    assert coverage["pending_record_count"] == 1
    assert coverage["excluded_record_count"] == 2
    assert "exclude" not in csv_response.text
    assert "exclude" not in jsonl_response.text
    assert "include" in csv_response.text and "include" in jsonl_response.text


def test_pair_export_uses_list_filters_and_reports_them(served_pairs: Any) -> None:
    """Exports apply the same literal search and unit filters as list requests."""
    client = served_pairs["client"]
    params = {"q": "そり", "mishear_id": "include", "unit_type": "phrase"}
    listed = client.get("/v1/pairs", params=params)
    exported = client.get("/v1/pairs/export", params=params)

    assert listed.status_code == exported.status_code == 200
    assert listed.json()["total"] == 1
    assert exported.headers["x-result-count"] == "1"
    assert json.loads(exported.headers["x-applied-filters"]) == params
    assert "include" in exported.text
    assert "exclude" not in exported.text
    assert "untouched" not in exported.text


def test_pair_routes_absent_without_pointer_but_existing_records_remain(
    tmp_path: Path,
) -> None:
    """Old snapshots without pair artifacts retain the existing record API."""
    root = tmp_path / "no-pairs"
    import csv
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(_mishearing_row("one", "left", "right"))
    ref = _commit_public_fixture(root, stream.getvalue())
    from corpus_api.main import create_app

    with TestClient(create_app(repository=root, dataset_ref=ref)) as client:
        assert client.get("/v1/records").status_code == 200
        assert client.get("/v1/pairs").status_code == 503
        assert client.get("/v1/pairs/export").status_code == 503


def test_invalid_pair_artifact_hash_fails_startup(tmp_path: Path) -> None:
    """Committed corrupt artifacts fail before any pair endpoints serve data."""
    root, _, _ref = _fixture_repository(tmp_path / "bad", complete=True)
    repo = Repo(root)
    path = root / "resource/pairs_v2/2026-10-24-initial/reviewed.csv"
    path.write_text("tampered", encoding="utf-8")
    repo.index.add([str(path.relative_to(root))])
    bad_commit = repo.index.commit(
        "tamper pair fixture",
        author=Actor("tests", "tests@example.invalid"),
        committer=Actor("tests", "tests@example.invalid"),
    )
    repo.close()
    from corpus_api.main import create_app

    with (
        pytest.raises(ValueError),
        TestClient(create_app(repository=root, dataset_ref=bad_commit.hexsha)),
    ):
        pass


@pytest.mark.parametrize("source_commit", ["not-a-sha", "f" * 40])
def test_pair_source_commit_must_resolve_to_real_source(
    tmp_path: Path, source_commit: str
) -> None:
    """A checksum does not prove a manifest's claimed Git provenance."""
    # Arrange
    root, _, _ = _fixture_repository(tmp_path / "bad-source", complete=True)
    path = root / "resource/pairs_v2/2026-10-24-initial/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["source_commit"] = source_commit
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with Repo(root) as repo:
        repo.index.add([str(path.relative_to(root))])
        commit = repo.index.commit(
            "invalid source claim",
            author=Actor("test", "test@example.invalid"),
            committer=Actor("test", "test@example.invalid"),
        )
        ref = commit.hexsha
    from corpus_api.main import create_app

    # Act / Assert
    with (
        pytest.raises(ValueError),
        TestClient(create_app(repository=root, dataset_ref=ref)),
    ):
        pass


def test_precommit_validates_staged_blobs_not_unstaged_reviews(tmp_path: Path) -> None:
    """A valid working tree must not hide an inconsistent partial Git stage."""
    # Arrange
    import csv

    root, _, ref = _fixture_repository(tmp_path / "partial-stage", complete=True)
    source = root / "data/mishearing/sample/records.csv"
    rows = list(csv.DictReader(source.open(encoding="utf-8", newline="")))
    rows[0]["Note"] = "new source evidence reviewed in working tree only"
    _write_csv(source, FIELDS, rows)
    annotation = root / "data/annotations/reviews.csv"
    reviews = load_reviews(annotation.read_bytes())
    by_id = {row["MishearID"]: row for row in rows}
    for review in reviews:
        review["OriginalHash"] = original_hash(by_id[str(review["MishearID"])])
    annotation.write_bytes(review_csv(reviews))
    corpus = working_snapshot(root, CorpusSnapshot.from_git(root, ref))
    artifacts = build_artifacts(
        corpus, reviews, tokenizer=lambda text: [(0, len(text))] if text else []
    )
    for name, payload in artifacts.items():
        (root / "resource/pairs_v2/2026-10-24-initial" / name).write_bytes(payload)
    with Repo(root) as repo:
        repo.index.add([str(source.relative_to(root))])

    # Act: ordinary worktree validation passes; the staged set is deliberately invalid.
    validate_artifacts(artifacts, corpus, reviews)

    # Assert
    with pytest.raises(ValueError, match="different original"):
        validate_index(root)


def test_precommit_accepts_a_consistent_committed_index(tmp_path: Path) -> None:
    """The staged validator reads a valid committed snapshot without MeCab."""
    # Arrange
    root, _, _ = _fixture_repository(tmp_path / "consistent-index", complete=True)

    # Act
    manifest = validate_index(root)

    # Assert
    assert manifest["unprocessed_count"] == 0


@pytest.mark.skipif(shutil.which("mecab") is None, reason="optional MeCab CLI missing")
def test_machine_draft_does_not_apply_stale_reviews(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Changed originals can be inspected before updating old review decisions."""
    # Arrange
    import csv
    import sys

    from corpus_api.pair_workflow import main

    root, _, _ = _fixture_repository(tmp_path / "new-originals", complete=True)
    source = root / "data/mishearing/sample/records.csv"
    rows = list(csv.DictReader(source.open(encoding="utf-8", newline="")))
    rows[0]["Note"] = "changed source; original annotations are intentionally stale"
    _write_csv(source, FIELDS, rows)
    output = tmp_path / "new-machine-draft"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pair_workflow",
            "draft",
            "--repository",
            str(root),
            "--working-tree",
            "--output",
            str(output),
        ],
    )

    # Act
    main()

    # Assert
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["unprocessed_count"] == 4
    assert manifest["reviewed_record_count"] == 0
    assert manifest["source_state"] == "working-tree"
    assert len(list(csv.DictReader((output / "reviewed.csv").open()))) == 0
