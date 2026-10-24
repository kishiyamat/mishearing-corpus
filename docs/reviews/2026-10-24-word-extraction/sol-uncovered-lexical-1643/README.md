# Remaining 1,643 lexical-pair unit decisions

This is an agent research judgment, not researcher approval or an automatic change to adoption/meaning/reading. It covers exactly the old `word` 1,221 and `compound` 422 PairIDs marked `RESEARCH_REQUIRED` in the full pair audit. The input dossier joined each immutable original/source row, existing reviewed annotations and readings, current pair, MeCab/IPADIC alternatives, and prior evidence. Every output item has old PairID, OriginalHash, selected surfaces/bounds/readings, desired UnitType, rule or individual decision, and source/POS/dictionary evidence.

| Artifact | SHA-256 |
| --- | --- |
| Input dossier `/tmp/uncovered-word-units-lexical.json` | `6144b08bd6a2194cbf98cfa7543cc6e4887bc6e35f3088a70f4ba09ef533148c` |
| Input canonical reviews (embedded dossier hash) | `0805dc7cc103e499757012475b357424f2ba9f35491a8974245f335ce9814f1d` |
| `classify_uncovered_lexical_sol.py` | `56722352f1198be30ebd88dfacc446224bf8726549cbfdb9afa08c01f22b6f63` |
| `uncovered-lexical-sol-decisions.json` | `6e31cae3f7be35f72a17546e7bd4a48456f875ebfd0be4249962c273ca70523d` |

KEEP_WORD 1,145; KEEP_COMPOUND 382; RETYPE_COMPOUND 76; RETYPE_WORD 28; RETYPE_CONTEXTUAL 12. No new spans/readings/adoption changes are proposed. The conservative automatic rules require either exact whole-surface dictionary entries with existing readings and independent POS on both sides (822) or exact dictionary-supported nominal components whose readings concatenate to the existing full readings (317). Other nominal/name/technical-term cases cite the source Note and preserve the previously reviewed readings; false-positive MeCab splits do not establish phrasehood. Twenty-five old `compound` pairs that MeCab treats as one nominal token on both sides were individually checked; four remain compound because an unknown-token parse hides internal structure. Non-lexical adverb/determiner/enumeration material is retyped contextual in 12 individually identified cases. The final migration must verify current signatures and preserve meanings, qualifiers, uncertainty, and lineage.
