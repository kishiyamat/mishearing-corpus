# Initial 129 word retypes: exact replay record

This records the historical two-script replay from the baseline review snapshot to the known-v1 input. It does not modify the canonical review file, current pointer, or run.

## Hash chain

| Stage | SHA-256 |
|---|---|
| Baseline `data/annotations/reviews.csv` at Git `772419eab62e67e39e09a0bec31eede78e255ac4` | `42b17d86f1cec33fb1bbd0b3018a587f38b4adfa695a1ae25b8f1c7846ee49ea` |
| After `apply_confirmed_word_pair_retypes.py` (25 individually adjudicated pairs) | `57cccf37efb534d34c2ea8cf9e42a1b99edac97ccf489ff641ab2ba0a7b15d61` |
| After `apply_auto_word_pair_retypes.py` (104 additional pairs; known-v1 input) | `9603161087f638b80ab07a81771319dbef7ba87bcd1cfbb91bcb5a5be684fd3c` |

Both outputs were obtained by executing the scripts in isolated copies of the corpus. The recorded script SHA-256 values are in `manifest.json`. `pair-level-audit-reset.csv` is the replay input audit: it was reconstructed from the retained post-run audit by changing the 25 `RETYPE_VERIFIED` and 104 `AUTO_WORD_RETYPE` rows back to `RESEARCH_REQUIRED`. The post-run audit and manifest are also retained as provenance. This reset affects only the audit/control input, not the baseline annotations.

## Replay procedure

From the repository root, create an isolated temporary worktree/sandbox containing the baseline tree and this evidence directory. Restore `data/annotations/reviews.csv` from baseline commit `772419eab62e67e39e09a0bec31eede78e255ac4`, copy `pair-level-audit-reset.csv` to `docs/reviews/2026-10-24-word-extraction/pair-level-audit.csv`, and ensure the dictionary evidence file is present. The evidence SHA is listed in `manifest.json`.

Run, in order:

```sh
PATH="/path/to/corpus/.venv/bin:$PATH" python scripts/apply_confirmed_word_pair_retypes.py
sha256sum data/annotations/reviews.csv
PATH="/path/to/corpus/.venv/bin:$PATH" python scripts/apply_auto_word_pair_retypes.py
sha256sum data/annotations/reviews.csv
```

The first checksum must be `57cccf37efb534d34c2ea8cf9e42a1b99edac97ccf489ff641ab2ba0a7b15d61`; the second must be `9603161087f638b80ab07a81771319dbef7ba87bcd1cfbb91bcb5a5be684fd3c`. Script hashes and exact replay environment are recorded in `manifest.json`. The dictionary profile/evidence source is the baseline run `resource/pairs_v2/2026-10-24-homophones-retained/` and `docs/reviews/2026-10-24-word-extraction/dictionary-evidence.jsonl`.

An independent replay using the saved reset audit and baseline Git blob reproduced both intermediate checksums exactly (`57cccf...` and `960316...`). Use the repository virtualenv because the scripts import `GitPython`. The exact replay claim is limited to these two historical scripts and output hashes; no generic decision-engine replay is claimed. The later known-v1 manifest declares the resulting `960316...` SHA as its input.
