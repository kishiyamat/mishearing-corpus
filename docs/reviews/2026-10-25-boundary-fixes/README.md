# 2026-10-25 word-boundary fixes

This review records eight evidence-backed boundary corrections to the 2026-10-24
`2026-10-24-word-units-final-v5` run. The two researcher-requested examples are
`coffee_break_parts_similar200603_007` (中水 / 注水) and
`39mag_benesse_16332_002` (誤って / 謝って). A focused lexical-unit screen found
six additional cases where the selected span stopped at an inflectional stem:
`ohanashi_yokota_blog_001`, `togetter_1803542_001`,
`trilltrill_3469235_001`, `coffee_break_parts_similar200404_006`,
`coffee_break_parts_similar200404_009`, and
`www_1101_com_m_iimatugai_1315_html_007`.

The updated canonical review preserves every prior Evidence and Reason verbatim
under a clearly labeled historical section, then appends the current boundary
evidence and rationale. This keeps obsolete stem readings visibly historical.
The engine’s opt-in `preserve_previous_rationale` path is protected by a
regression test; its default behavior is unchanged. The 39mag meanings distinguish 過失で from
謝罪して; its existing empty qualifiers remain empty, while the uncrawled source
article and unverified audio are stated in Evidence. The 中水 / 注水 reading is
researcher-confirmed; its original audio remains unverified. For the other six,
the full contextual inflected forms and separate readings are recorded without
inventing typed meanings. Their original qualifiers remain unchanged.

| ID | Selected source / target | Reading | Boundary |
| --- | --- | --- | --- |
| `coffee_break_parts_similar200603_007` | 中水 / 注水 | チュウスイ / チュウスイ | `[9,11)` / `[9,11)` |
| `39mag_benesse_16332_002` | 誤って / 謝って | アヤマッテ / アヤマッテ | `[0,3)` / `[0,3)` |
| `ohanashi_yokota_blog_001` | 乗ります / 降ります | ノリマス / オリマス | `[0,4)` / `[0,4)` |
| `togetter_1803542_001` | あります / いります | アリマス / イリマス | `[1,5)` / `[1,5)` |
| `trilltrill_3469235_001` | 洗いたい / 会いたい | アライタイ / アイタイ | `[0,4)` / `[0,4)` |
| `coffee_break_parts_similar200404_006` | 伺えない / 疑えない | ウカガエナイ / ウタガエナイ | `[0,4)` / `[0,4)` |
| `coffee_break_parts_similar200404_009` | 見込めない / 認めない | ミコメナイ / ミトメナイ | `[0,5)` / `[0,4)` |
| `www_1101_com_m_iimatugai_1315_html_007` | 知りたい / 死にたい | シリタイ / シニタイ | `[0,4)` / `[0,4)` |

All eight revised spans receive new PairIDs and point to their prior PairIDs with
`SupersedesPairID`. The complete old-to-new mapping is in
[`word-pair-decisions-audit.csv`](word-pair-decisions-audit.csv). The patch binds
to the exact initial review hash and validates each old ID, range, unit type, and
original hash through `scripts/apply_word_pair_decisions.py`.

The Sol structural screen covered 3,433 included lexical pairs. It found 154
compound candidates with shared trailing token sequences; inspection found no
additional justified compound shortening. Whole technical terms and names remain
intact, including 三角橋 / 参宮橋, 皮下注射 / 筋肉注射, and
ホットコーヒー / アイスコーヒー. `syunkon_12835221992_013` already selects the
full 誤って / 謝って forms and remains unchanged. The criteria and screen are
preserved in [`sol-criteria-audit.md`](sol-criteria-audit.md).

## Run and invariants

`resource/pairs_v2/current.json` points to
`2026-10-25-pr64-boundary-fixes`. Both the prior v5 run and the first 2026-10-24
audit remain unchanged. The 11-column source CSVs are unchanged. The new run keeps
4,341 evaluation pairs, 4,318 reviewed records, 26 excluded records, 172 pending
records, 12 zero-candidate records, and zero unprocessed records. Included unit
counts changed from 2,209 word / 1,224 compound / 908 phrase to 2,210 word /
1,223 compound / 908 phrase: one compound became a word, while the other seven
revisions retained their word type. The original data hash is unchanged. Eight
old PairIDs are superseded by eight new IDs; every other selected run row is
byte-for-byte unchanged.

`linguistic_quality_complete` remains false in the run manifest; complete review
coverage does not claim that every corpus item has finished linguistic research.
