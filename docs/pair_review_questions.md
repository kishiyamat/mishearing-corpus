# Issue 63 public-source review: remaining questions

The initial targeted review checked candidate rows in `data/mishearing` using public source links and locally archived public text where available. Of its 17 cases, two are now included using exact dictionary readings and source evidence, three are excluded (two same-reading place-name disambiguations and one same-word sense ambiguity), and 12 remain pending. Event provenance is separate from phonological suitability: an illustrative example is not automatically excluded. The CSV `Note` fields are not treated as independent pronunciation evidence. The complete 4,490-row review is recorded in `data/annotations/reviews.csv`; this page lists only the initial targeted questions.

| MishearID | Question to resolve |
| --- | --- |
| `AcrugLVnrLE_017` | Inspect the cited YouTube video/comment and verify the actual 田町→反町 event and readings. |
| `AcrugLVnrLE_021` | Inspect the cited YouTube video/comment and verify 祖師ヶ谷→獅子ケ谷 and readings. |
| `AcrugLVnrLE_022` | Inspect the cited YouTube video/comment and verify 獅子ケ谷→越谷 and readings. |
| `AcrugLVnrLE_024` | Inspect the cited YouTube comment and verify 三角橋→参宮橋 and readings. |
| `oshiete_2625074_024` | Read the cited Goo Q&A to establish the comparison context and phonological suitability of 谷原（やはら）→谷和原（やわら）; classify documented versus illustrative provenance separately. |
| `oshiete_2625074_039` | Read the cited Goo Q&A and establish readings for 獅子ケ谷→市ヶ谷 from public or authoritative sources. |
| `oshiete_2625074_045` | Read the cited Goo Q&A and establish readings for 市沢町→三ツ沢 from public or authoritative sources. |
| `iimatugai_2398_008` | Locate the 1101/ほぼ日 page for the 熊谷→我が家 exchange; the matching transcript was not found in `resource/txt_1101`. |
| `worldlife_7873_001` | Retrieve the cited article and verify the 舞台→豚肉 exchange and readings. |
| `coffee_break_parts_similar201205_008` | Yamato archive confirms 経済リスクが転換 is the mistake and テールリスクが低下 the correction. Establish readings from an authoritative source. |
| `coffee_break_parts_similar201402_003` | Yamato archive confirms 留意中 is the mistake and 理由中 the correction. Establish both readings from an authoritative source. |

The current candidates with direct local public-text evidence are:

- `www_1101_com_iimatugai_archive_more060208_html_003`: the archived narrative explicitly contrasts 「ぶたいぬの顔」 with 「舞台向きの顔」. The phrase spans are corrected in the review record, but the kanji phrase reading is not explicit in the narrative and the case remains pending.
- `sakamotojidousha_7952_002` and `_016`: both rows give the same surface and reading for 大山町 and differ only by ward, so they are excluded as location disambiguation rather than mishearing pairs.
- `sakidori_tel01_008`: both sides are 退社 with parenthetical senses 帰宅 and 退職, so it is excluded as sense ambiguity. The row does not independently establish a pronunciation.

Resolved reading questions: `coffee_break_parts_similar200807_009` now includes the narrower 木賃（キチン）/持ち（モチ）pair, without asserting whole-phrase readings. `coffee_break_parts_similar202302_005` now includes 射程（シャテイ）/下手（したて）. Exact whole-word IPADIC entries and archived correction direction ground these decisions; details and dictionary fingerprints are retained in the canonical review rows.

Candidate coverage from the specified Issue 63 terms: 17 distinct rows. Current dispositions: 5 reviewed (2 include, 3 exclude) and 12 pending. Searches of the raw CSV corpus did not locate a candidate row containing either 二国間 or 二極間.
