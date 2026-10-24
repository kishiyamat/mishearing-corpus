# Word-pair extraction audit (2026-10-24)

The immutable baseline is run `resource/pairs_v2/2026-10-24-homophones-retained`
at code revision `772419e`. It contains 4,292 included records and 4,315
selected pair rows. The canonical annotation table is
`data/annotations/reviews.csv`; the original 11-column source CSVs, inclusion
decisions, and the historical 1,908-row research export were not edited.

`pair-level-audit.csv` records the structural baseline only. Extractor
proposals, dictionary matches, POS profiles, and annotation alignment are
evidence, not automatic semantic decisions. The adjudicated decisions and
applied changes are recorded in batch directories below. Each batch
`manifest.json` pins its input/output review SHA-256, patch SHA-256, and actual
before/after audit SHA-256. Apply batches in this order; the output SHA of each
batch must equal the next batch's input SHA:

1. [Initial 129 retypes replay record](initial-retypes-129/README.md) (25
   confirmed + 104 automatic same-span retypes; it reproduces baseline to
   `960316...`), then `known-decisions-v1`
2. `referents-v2`
3. `eichie-normalization`, then `eichie-evidence-correction`
4. `shared-syntax-85`, then `contextual-known`
5. `contextual-false-positives-22`, then `shortener-174`, then `pos-contextual-97`
6. `togetter-compound`, `additional-shortener-4`, `pos-retype-lexical-3`,
   `pos-shortener-verified-1`
7. `dictionary-shortener-24`, `pos-shorten-multi-3`, `split-verified-14`,
   `pos-shortener-exceptions-48`, `dictionary-multipair-2`,
   `verified-shortener-42`
8. `same-span-compound-113`, then `effective-type-overlay-76`,
   `final-source-warning`, `conditional-rationale-preservation-12`
9. `uncovered-lexical-116`, `uncovered-phrases-final-795`,
   `acrug024-qualifier-repair-1`, `conditional-cue-repair-2`, then
   `niftykids-phrase-correction-1`

The initial four-record decision patch is preserved at
`known-decisions-v1/decision-patch.json`; its source and output hashes are in
that directory's manifest. Full intermediate `reviews.csv` snapshots are kept
in `/tmp` during this working session rather than duplicated in the repository.
The canonical CSV plus the ordered patches and hash manifests are the
reproducible source of truth.

`pair-level-audit-final.csv` has one row per baseline PairID and maps all 4,341
current included pairs. Every endpoint is checked against the baseline
MishearID and OriginalHash; there are no missing lineages or orphan current
pairs. The current run is `resource/pairs_v2/2026-10-24-word-units-final-v5`
with extractor `pairs-v2.3`. The canonical table contains 4,490 records (4,292
included, 26 excluded, 172 pending).

The integrated audit has no `RESEARCH_REQUIRED` rows: every baseline PairID
has a reviewed decision or rule-backed keep, and every current included pair
is reachable through retained or superseding lineage. See
`final-audit-manifest.json` for exact counts and validation hashes.

The uncertainty-cue scan found 572 baseline records with audio/source
uncertainty or conditional-policy language. Two had lost the explicit
original-audio-unverified caveat during unit adjudication; `conditional-cue-repair-2`
restores it in Evidence and Reason. The `AcrugLVnrLE_024` pronunciation
qualifier is restored verbatim. Eichie's parenthetical source note
`ジュリーの歌` is intentionally kept in Evidence/Reason, outside the extracted
pair and reading. Baseline annotations contain 260 qualifier instances (99
distinct strings); all remain on their corresponding current annotations except
that intentional Eichie source-note move, which does not become speech or a
pair-level qualifier. A final source review also restored `一児の/一時は` as a
phrase; the particles の/は carry the contrast, so the apparent shorter noun
pair is not treated as a lexical child.

## Reproduce the baseline profile

Use a clean temporary directory and the immutable baseline tree. The narrow
archive avoids importing later annotation changes into the baseline:

```sh
baseline_dir=$(mktemp -d)
git archive 772419e corpus_api data/annotations/reviews.csv data/mishearing \
  resource/pairs_v2/2026-10-24-homophones-retained pyproject.toml \
  | tar -x -C "$baseline_dir"
mkdir -p "$baseline_dir/scripts"
cp scripts/profile_word_pair_migration.py "$baseline_dir/scripts/"
PYTHONPATH="$baseline_dir" .venv/bin/python \
  "$baseline_dir/scripts/profile_word_pair_migration.py" \
  --root "$baseline_dir" \
  --output /tmp/word-pair-baseline-profile \
  --input-run 2026-10-24-homophones-retained \
  --annotation-ref 772419e \
  --annotation-file "$baseline_dir/data/annotations/reviews.csv"
```

The verified baseline profile contains 4,315 included pair rows. The standalone
profile script also accepts an explicit annotation reference so the immutable
baseline can be profiled without relying on the repository's current working
tree.
