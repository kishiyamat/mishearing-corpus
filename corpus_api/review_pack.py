"""Export excluded source records into a create-only researcher review pack."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections.abc import Sequence
from pathlib import Path

from git import Blob, Repo

from .dataset import CorpusSnapshot, canonical_json
from .models import CSV_FIELDS
from .pair_workflow import load_reviews, original_hash, review_record

PACK_FIELDS = (
    *CSV_FIELDS,
    "SourceFile",
    "SelectedUnits",
    "SelectedReadings",
    "Reason",
    "Evidence",
    "Reviewer",
    "RecordValidity",
    "ReferenceCommit",
    "OriginalHash",
    "ResearcherDecision",
    "ResearcherComment",
)


def _review_blob(repository: Path, ref: str) -> tuple[str, bytes]:
    """Read canonical review CSV bytes from the resolved Git commit."""
    with Repo(repository, search_parent_directories=False) as repo:
        commit = repo.commit(ref)
        blob = commit.tree / "data/annotations/reviews.csv"
        if not isinstance(blob, Blob) or blob.mode not in (0o100644, 0o100755):
            raise ValueError("canonical reviews.csv is missing or not a regular blob")
        return commit.hexsha, blob.data_stream.read()


def _markdown(value: str) -> str:
    """Render untrusted text as inert plain text in Markdown documents."""
    # Entity-encode every character with Markdown or HTML significance. Keep
    # whitespace readable while preventing links, images, tags, and code spans.
    escaped = []
    for char in value:
        if char.isalnum() or char.isspace() or char in "。、・ー（）「」『』":
            escaped.append(" " if char in "\r\n\t" else char)
        else:
            escaped.append(f"&#{ord(char)};")
    return "".join(escaped)


def _url(value: str) -> str:
    """Display external URLs inertly so no source value can trigger a link."""
    return _markdown(value)


def _readings(rows: list[dict[str, str]]) -> str:
    """Format selected source and target units with their confirmed readings."""
    return (
        " → ".join(
            f"{row['Src']}〔{row['SrcReading'] or '読み不明'}〕 → "
            f"{row['Tgt']}〔{row['TgtReading'] or '読み不明'}〕"
            for row in rows
        )
        or "選択単位なし"
    )


def _csv_bytes(rows: Sequence[dict[str, str]]) -> bytes:
    """Serialize the review copy with an Excel-compatible UTF-8 BOM."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=PACK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8")


def _write_page(
    path: Path, page: int, rows: list[dict[str, str]], total: int, page_count: int
) -> None:
    """Write one readable page while keeping large evidence only in the CSV."""
    lines = [
        f"# 除外記録の確認 {page}",
        "",
        f"全 {total} 記録のうち、このページは {len(rows)} 件です。",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {_markdown(row['MishearID'])}",
                "",
                f"- URL: {_url(row['URL'])}",
                f"- RecordValidity: {_markdown(row['RecordValidity'])}",
                f"- Reason: {_markdown(row['Reason'])}",
                f"- 選択単位・読み: {_markdown(row['SelectedReadings'])}",
                f"- 原文 Src: {_markdown(row['Src'])}",
                f"- 原文 Tgt: {_markdown(row['Tgt'])}",
                "",
            ]
        )
    links = ["[一覧へ](README.md)"]
    if page > 1:
        links.append(f"[前へ](page-{page - 1:03}.md)")
    if page < page_count:
        links.append(f"[次へ](page-{page + 1:03}.md)")
    lines.extend([" | ".join(links), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def export_review_pack(
    repository: Path, ref: str, output: Path, page_size: int = 50
) -> dict[str, object]:
    """Create an immutable, record-level review pack from one committed REF.

    The directory must not exist. The canonical annotation file is read from the
    same Git commit as the public snapshot; researcher decisions remain blank.
    """
    if page_size < 1:
        raise ValueError("page_size must be positive")
    if output.exists():
        raise FileExistsError(output)
    snapshot = CorpusSnapshot.from_git(repository, ref)
    commit, payload = _review_blob(repository, ref)
    if commit != snapshot.info.dataset_version:
        raise ValueError("snapshot and review CSV resolved to different commits")
    reviews = load_reviews(payload)
    by_id: dict[str, dict[str, object]] = {}
    for review in reviews:
        identifier = str(review["MishearID"])
        if identifier in by_id or identifier not in snapshot.by_id:
            raise ValueError("duplicate or unknown review MishearID")
        by_id[identifier] = review

    if set(by_id) != set(snapshot.by_id):
        missing = sorted(set(snapshot.by_id) - set(by_id))
        extra = sorted(set(by_id) - set(snapshot.by_id))
        raise ValueError(
            f"review set does not match committed records (missing={missing}, extra={extra})"
        )

    rows: list[dict[str, str]] = []
    for identifier in sorted(by_id):
        decision = by_id[identifier]
        if decision["TargetDecision"] != "exclude":
            continue
        record = snapshot.by_id[identifier]
        original = {field: str(getattr(record, field)) for field in CSV_FIELDS}
        selected, audit = review_record(original, record.source_file, decision)
        units = [
            {
                key: row[key]
                for key in (
                    "Src",
                    "Tgt",
                    "UnitType",
                    "SrcStart",
                    "SrcEnd",
                    "TgtStart",
                    "TgtEnd",
                )
            }
            for row in selected
        ]
        readable = _readings(selected)
        rows.append(
            original
            | {
                "SelectedUnits": canonical_json(units),
                "SelectedReadings": readable,
                "SourceFile": record.source_file,
                "Reason": str(decision["Reason"]),
                "Evidence": str(decision["Evidence"]),
                "Reviewer": str(decision["Reviewer"]),
                "RecordValidity": str(audit["RecordValidity"]),
                "ReferenceCommit": commit,
                "OriginalHash": original_hash(original),
                "ResearcherDecision": "",
                "ResearcherComment": "",
            }
        )

    output.mkdir(parents=True)
    csv_payload = _csv_bytes(rows)
    csv_path = output / "excluded.csv"
    csv_path.write_bytes(csv_payload)
    total = len(rows)
    page_count = (total + page_size - 1) // page_size
    for offset in range(0, total, page_size):
        page_rows = rows[offset : offset + page_size]
        _write_page(
            output / f"page-{offset // page_size + 1:03}.md",
            offset // page_size + 1,
            page_rows,
            total,
            page_count,
        )
    navigation = (
        "\n".join(
            f"- [ページ {page:03}](page-{page:03}.md)"
            + (f" · [次へ](page-{page + 1:03}.md)" if page < page_count else "")
            for page in range(1, page_count + 1)
        )
        or "対象記録はありません。"
    )
    readme = (
        "# 除外記録レビュー資料\n\n"
        f"- 対象コミット: `{commit}`\n- 除外記録: {total} 件\n"
        "- `excluded.csv` は研究者レビュー用コピーです。判断は未入力です。\n"
        "- `ResearcherDecision` と `ResearcherComment` を記入して確認してください。\n"
        "- この資料はレビュー待ちであり、承認済み・正本データではありません。\n"
        "- 確認済み資料を上書きせず、新しい出力先へ作成してください。\n"
        "- CSVには元記録、根拠、出典URL、選択単位・読みを保持しています。\n"
        "- CSVの元値を編集すると照合できなくなるため、Excelではテキストとして取り込んでください。\n"
        "  Excelで直接開くと先頭が`=`等のセルが数式として評価される場合があります。\n"
        "- ページ一覧（各ページ末尾にも次ページリンクがあります）:\n"
        f"{navigation}\n"
    )
    (output / "README.md").write_text(readme, encoding="utf-8")
    files = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.iterdir())
        if path.is_file()
    }
    manifest = {
        "reference_commit": commit,
        "excluded_count": total,
        "page_size": page_size,
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    """Run the review pack exporter command line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-size", type=int, default=50)
    args = parser.parse_args(argv)
    result = export_review_pack(args.repository, args.ref, args.output, args.page_size)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
