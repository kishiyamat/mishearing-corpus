# Pair review: integrity audit and research policy (2026-10-24)

The current policy is documented in [the homophone re-audit](pair_review_homophones_2026-10-24.md). Same-reading words, senses, and referents remain eligible. Only a supported same-word/same-interpretation spelling relation warrants variant consolidation; equal kana does not establish lexical identity. `RecordValidity` records provenance (`documented`, `illustrative`, `production`, `visual`, or `unclear`); it does not determine `TargetDecision` automatically. The default `unclear` is not a claim that an event occurred.

An `include` requires independently selected source and target units and grounded readings; the readings may be identical. Different senses and referents must be retained in typed annotations, including when written surfaces match. Explicit kana, actually queried dictionary entries, and documented contextual researcher choices can ground readings. Context-checked lexical composition can ground ordinary phrases: a whole-phrase headword is not required. Do not invent component readings or mistake an unchecked morphological best path for evidence (e.g. hydraulic 樋門 is ヒモン, not トイモン). Exclusions require lexical identity evidence, a demonstrated structural problem with the comparison, or an explicit scope instruction—not a same-reading, modality, or sound-distance rule. Unqueried ordinary words remain work to investigate.

The historical adjudications below included the erroneous same-reading rule introduced in `bc56dad` on 2026-10-24. They are not the current adoption policy. The re-audit revisits all 567 previously excluded records and records each former and corrected decision without changing historical runs.

All 4,490 original rows were represented exactly once in the canonical `data/annotations/reviews.csv`, retained their original hashes, and passed `RecordReview` plus `review_record` against the raw CSV. The **initial run** had 381 include, 106 exclude, and 4,003 pending. This was ledger coverage, **not completed research** or 4,490 confirmed phonological pairs. Further source/dictionary research updates the canonical CSV and current run; the initial counts below are historical, not current totals. The following names identify the temporary initial review batches, consolidated into that CSV; they are not additional editable sources of truth. Counts by initial batch:

| File | Rows | Include | Exclude | Pending |
| --- | ---: | ---: | ---: | ---: |
| `initial_review.json` | 17 | 2 | 3 | 12 |
| `review_kana.json` | 23 | 23 | 0 | 0 |
| `review_parentheses.json` | 317 | 13 | 34 | 270 |
| `review_plain_a.json` | 1,377 | 94 | 41 | 1,242 |
| `review_plain_b.json` | 1,034 | 178 | 26 | 830 |
| `review_plain_c.json` | 689 | 24 | 1 | 664 |
| `review_plain_d.json` | 1,033 | 47 | 1 | 985 |

## Historical initial adjudications

The following describes the initial run. Its pending descriptions are not a
current queue: later source research is recorded in the canonical CSV and the
run selected by `resource/pairs_v2/current.json`. The initial 17 questions and
their resolutions are summarised in [pair_review_questions.md](pair_review_questions.md).

Initial adjudications:

- `sakamotojidousha_7952_014` and `_026` remain included: the source explicitly gives 向原（むかいはら；板橋区） versus 向原（むこうはら；豊島区）. The note describes likely mistaken rides, so event validity is illustrative, not a documented ride.
- `coffee_break_parts_similar202302_005` now compares whole words 射程/下手, grounded by an exact ordinary-word IPADIC entry and the archive's explicit 下手（したて）; `coffee_break_parts_similar200807_009` compares whole words 木賃/持ち with exact dictionary readings, without asserting a full-compound reading.
- `www_1101_com_iimatugai_archive_more080521_008` is a production error (アリとキリギリス/アリギリス), but its complete original-kana forms support a phonological include. Six other original-kana production/visual contrasts in `review_plain_d.json` were judged independently of modality: three included as plausible sound contrasts, and three left pending because semantic/name retrieval or partial sound overlap does not resolve phonological suitability. No numeric sound-distance threshold was imposed.
- `coffee_break_parts_similar200510_008` and `_200605_004` are pending because complete phrase readings were previously composed from pieces without phrase-level evidence. `denwadaikou_000815_005` remains pending: the `(t)`/`(p)` letters are contrastive text, not removable semantic glosses, but the spoken letter forms need grounding.
- Exclusions left in the non-B files were rechecked for same-sound, same-utterance, or independently implausible sound-pair grounds. Ten `review_plain_d.json` rows previously excluded solely for production, written modality, intent, or direction were changed to pending rather than calling modality a phonological failure. `transcosmos_cotra_order_002` remains excluded because exact whole-surface entries give サイトウ for both 斉藤 and 斎藤.

Pending review questions remain source- and span-specific in each row's `Evidence` and `Reason`. In particular, proper names with multiple possible readings, long mixed-script phrases, and parenthetical letter names need explicit pronunciation evidence or a better-supported smaller unit before promotion. No unverified reading is converted to a confirmed target merely because the row is documented in an archive.
