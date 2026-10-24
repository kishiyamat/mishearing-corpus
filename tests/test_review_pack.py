"""Contracts for exporting excluded records for a separate researcher review."""

import csv
import json
from pathlib import Path

import pytest
from git import Repo

from corpus_api.models import CSV_FIELDS
from corpus_api.pair_workflow import original_hash, review_csv
from corpus_api.review_pack import export_review_pack


def record(src: str, tgt: str, identifier: str) -> dict[str, str]:
    """Build a source row using the public CSV contract."""
    return dict.fromkeys(CSV_FIELDS, "") | {
        "MishearID": identifier,
        "Src": src,
        "Tgt": tgt,
        "Language": "ja",
    }


def review(
    raw: dict[str, str],
    *,
    decision: str,
    spans: list[dict[str, object]],
    status: str = "reviewed",
) -> dict[str, object]:
    """Build a valid source-bound excluded or included record review."""
    return {
        "MishearID": raw["MishearID"],
        "OriginalHash": original_hash(raw),
        "Reviewer": "test-reviewer",
        "ReviewedAt": "2026-10-24",
        "Evidence": "fixture evidence",
        "Reason": "checked both sides",
        "Status": status,
        "TargetDecision": decision,
        "RecordValidity": "unclear",
        "SrcAnnotations": [],
        "TgtAnnotations": [],
        "PairSpans": spans,
    }


def _repository(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    """Create a tiny committed public snapshot with reviewed and excluded rows."""
    root = tmp_path / "repo"
    root.mkdir()
    repo = Repo.init(root)
    (root / "data/mishearing").mkdir(parents=True)
    (root / "data/tag").mkdir()
    (root / "data/environment").mkdir()
    (root / "data/annotations").mkdir(parents=True)
    (root / "schema").mkdir()
    from corpus_api.models import CSV_FIELDS

    rows = [
        record("甲甲乙", "甲乙乙", "ex1")
        | {
            "URL": "![x](https://evil.test) <img src=x onerror=alert(1)>",
            "Note": "[click](https://evil.test) `code` | <b>unsafe</b>",
        },
        record("甲", "乙", "zero"),
        record("甲乙", "乙丙", "inc"),
    ]
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (root / "data/mishearing/test.csv").write_text(stream.getvalue(), encoding="utf-8")
    schema = {"fields": [{"name": name} for name in CSV_FIELDS]}
    (root / "schema/mishearing.schema.json").write_text(
        json.dumps(schema), encoding="utf-8"
    )
    (root / "data/tag/.keep").write_text("", encoding="utf-8")
    (root / "data/environment/.keep").write_text("", encoding="utf-8")
    excluded = review(
        rows[0],
        decision="exclude",
        spans=[
            {
                "src_start": 0,
                "src_end": 1,
                "tgt_start": 0,
                "tgt_end": 1,
                "unit_type": "word",
            },
            {
                "src_start": 1,
                "src_end": 3,
                "tgt_start": 1,
                "tgt_end": 3,
                "unit_type": "phrase",
            },
        ],
    )
    zero = review(rows[1], decision="exclude", spans=[])
    included = review(
        rows[2],
        decision="undecided",
        status="pending",
        spans=[
            {
                "src_start": 0,
                "src_end": 2,
                "tgt_start": 0,
                "tgt_end": 2,
                "unit_type": "phrase",
            }
        ],
    )
    payload = review_csv([excluded, zero, included]).decode("utf-8")
    (root / "data/annotations/reviews.csv").write_text(payload, encoding="utf-8")
    repo.index.add(["data", "schema"])
    repo.index.commit("fixture")
    return root, repo.head.commit.hexsha, {row["MishearID"]: row for row in rows}


def test_pack_is_record_level_complete_and_keeps_review_pending(tmp_path: Path) -> None:
    """Export one row per excluded record, including zero-pair records."""
    # Arrange
    root, ref, originals = _repository(tmp_path)
    output = tmp_path / "pack"

    # Act
    result = export_review_pack(root, ref, output)

    # Assert
    with output.joinpath("excluded.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert [row["MishearID"] for row in rows] == ["ex1", "zero"]
    assert len(rows) == 2
    assert rows[0]["Src"] == originals["ex1"]["Src"]
    for field in CSV_FIELDS:
        assert rows[0][field] == originals["ex1"][field]
    assert rows[0]["SourceFile"] == "data/mishearing/test.csv"
    assert rows[0]["Reason"] == "checked both sides"
    assert rows[0]["ResearcherDecision"] == rows[0]["ResearcherComment"] == ""
    assert json.loads(rows[0]["SelectedUnits"])[0]["Src"] == "甲"
    assert "甲〔読み不明〕 → 甲〔読み不明〕" in rows[0]["SelectedReadings"]
    assert rows[1]["SelectedUnits"] == "[]"
    assert result["excluded_count"] == 2


def test_pack_uses_same_git_ref_and_refuses_existing_output(tmp_path: Path) -> None:
    """Dirty worktree edits cannot affect data, and output is create-only."""
    # Arrange
    root, ref, _ = _repository(tmp_path)
    original = (root / "data/annotations/reviews.csv").read_text(encoding="utf-8")
    (root / "data/annotations/reviews.csv").write_text("dirty", encoding="utf-8")
    output = tmp_path / "pack"

    # Act
    export_review_pack(root, ref, output)

    # Assert
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(FileExistsError):
        export_review_pack(root, ref, output)
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}
    assert (root / "data/annotations/reviews.csv").read_text(
        encoding="utf-8"
    ) == "dirty"
    assert original != "dirty"


def test_markdown_escapes_untrusted_values(tmp_path: Path) -> None:
    """Page text must render hostile markdown literally and never link unsafe URLs."""
    # Arrange
    root, ref, _ = _repository(tmp_path)
    output = tmp_path / "pack"

    # Act
    export_review_pack(root, ref, output)
    pages = "\n".join(
        path.read_text(encoding="utf-8") for path in output.glob("page-*.md")
    )

    # Assert
    assert "&#33;&#91;x&#93;&#40;https&#58;&#47;&#47;evil&#46;test&#41;" in pages
    assert "![x](https://evil.test)" not in pages
    assert "<img" not in pages
    assert "[click](https://evil.test)" not in pages
    assert "<b>unsafe</b>" not in pages
    assert "page-001.md" in (output / "README.md").read_text(encoding="utf-8")


def test_pending_review_is_not_exported(tmp_path: Path) -> None:
    """Only explicit exclusions enter the researcher review CSV."""
    # Arrange
    root, ref, _ = _repository(tmp_path)
    repo = Repo(root)
    reviews_path = root / "data/annotations/reviews.csv"
    from corpus_api.pair_workflow import load_reviews

    decisions = load_reviews(reviews_path.read_bytes())
    decisions[2]["Status"] = "pending"
    decisions[2]["TargetDecision"] = "undecided"
    reviews_path.write_bytes(review_csv(decisions))
    repo.index.add(["data/annotations/reviews.csv"])
    pending_ref = repo.index.commit("pending review").hexsha
    output = tmp_path / "pack"

    # Act
    export_review_pack(root, pending_ref, output)

    # Assert
    with (output / "excluded.csv").open(encoding="utf-8-sig", newline="") as handle:
        identifiers = [row["MishearID"] for row in csv.DictReader(handle)]
    assert identifiers == ["ex1"]
    assert ref != pending_ref


def test_missing_review_prevents_any_output(tmp_path: Path) -> None:
    """A canonical review set must cover every source record before export."""
    # Arrange
    root, _, _ = _repository(tmp_path)
    repo = Repo(root)
    reviews_path = root / "data/annotations/reviews.csv"
    from corpus_api.pair_workflow import load_reviews

    decisions = load_reviews(reviews_path.read_bytes())[:-1]
    reviews_path.write_bytes(review_csv(decisions))
    repo.index.add(["data/annotations/reviews.csv"])
    ref = repo.index.commit("missing review").hexsha
    output = tmp_path / "pack"

    # Act / Assert
    with pytest.raises(ValueError, match="review set does not match"):
        export_review_pack(root, ref, output)
    assert not output.exists()


def test_pack_pages_have_complete_navigation(tmp_path: Path) -> None:
    """All paginated exclusions must be reachable in both directions."""
    # Arrange
    root, ref, _ = _repository(tmp_path)
    output = tmp_path / "pack"

    # Act
    export_review_pack(root, ref, output, page_size=1)

    # Assert
    first = (output / "page-001.md").read_text(encoding="utf-8")
    last = (output / "page-002.md").read_text(encoding="utf-8")
    index = (output / "README.md").read_text(encoding="utf-8")
    assert "[次へ](page-002.md)" in first
    assert "[前へ](page-001.md)" in last
    assert "[次へ]" not in last
    assert "[一覧へ](README.md)" in first and "[一覧へ](README.md)" in last
    assert "(page-001.md)" in index and "(page-002.md)" in index
