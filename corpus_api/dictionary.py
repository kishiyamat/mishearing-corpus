"""Read lexical dictionary alternatives as review evidence, never as auto-approval."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import TypedDict


class DictionaryEntry(TypedDict):
    """One whole-surface known IPADIC entry, including its original feature tuple."""

    surface: str
    reading: str
    features: list[str]


class DictionaryResult(TypedDict):
    """A query and the installed dictionary fingerprint backing its alternatives."""

    surface: str
    dictionary_info: str
    dictionary_sha256: str
    entries: list[DictionaryEntry]


@lru_cache(maxsize=1)
def _dictionary_identity() -> tuple[str, str]:
    """Fingerprint this process's dictionary; restart after changing dictionary files."""
    result = subprocess.run(
        ["mecab", "-D"],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=30,
    )
    paths = [
        Path(line.split(":", 1)[1].strip())
        for line in result.stdout.splitlines()
        if line.startswith("filename:")
    ]
    if (
        result.returncode not in (0, 1)
        or not paths
        or "charset:\tUTF-8" not in result.stdout
    ):
        raise ValueError("a supported UTF-8 MeCab/IPADIC dictionary is required")
    manifest = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    digest = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return result.stdout, digest


def dictionary_entries(surface: str) -> DictionaryResult:
    """Return all known whole-word IPADIC entries, not the best-path reading.

    Entries can contain multiple readings, homographs and proper names. An agent
    still must check context and cite the selected entry. Unknown words and
    multi-token phrases return no whole-word evidence. No result updates reviews.
    The IPADIC feature layout (reading at index 7) is checked, not assumed for a
    different dictionary. See https://taku910.github.io/mecab/format.html.
    """
    if not surface or any(char in surface for char in "\n\r\t"):
        raise ValueError("dictionary queries must be nonempty single-line surfaces")
    info, digest = _dictionary_identity()
    # %s=0 means known dictionary node; -a includes non-best alternatives.
    result = subprocess.run(
        [
            "mecab",
            "--all-morphs",
            "--node-format=%m\t%s\t%H\n",
            "--unk-format=",
            "--bos-format=",
            "--eos-format=",
        ],
        input=surface,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=30,
    )
    entries: list[DictionaryEntry] = []
    seen: set[tuple[str, ...]] = set()
    for line in result.stdout.splitlines():
        values = line.split("\t", 2)
        if len(values) != 3 or values[0] != surface or values[1] != "0":
            continue
        features = next(csv.reader(io.StringIO(values[2]), strict=True))
        if len(features) != 9:
            raise ValueError(
                "dictionary feature layout is not IPADIC; do not guess reading columns"
            )
        if features[7] == "*" or tuple(features) in seen:
            continue
        seen.add(tuple(features))
        entries.append(
            {"surface": surface, "reading": features[7], "features": features}
        )
    return {
        "surface": surface,
        "dictionary_info": info,
        "dictionary_sha256": digest,
        "entries": entries,
    }


def main() -> None:
    """Print source-backed alternatives for deliberate review without editing CSVs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("surfaces", nargs="+")
    args = parser.parse_args()
    for surface in args.surfaces:
        print(
            json.dumps(dictionary_entries(surface), ensure_ascii=False, sort_keys=True)
        )


if __name__ == "__main__":
    main()
