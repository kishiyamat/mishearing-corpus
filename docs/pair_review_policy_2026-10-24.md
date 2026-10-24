# 研究者方針による再判定と除外レビュー（2026-10-24）

## 今回変更した前提

研究者の指示に従い、「聞き間違いが起きている」という前提で、文脈に合う自然な
読みを選ぶ。原音がないという理由だけで通常の日本語の比較を止めない。一方、
音の差を作るために不自然な読みや伏せ字の中身を作らず、確認できた事実と
研究者の条件付き解釈を混同しない。これは前版からの**判断方針の変更**であり、
原音の発見や単なる件数修正ではない。

今回、原音未確認で選んだ読みには `qualifiers`（派生ペアでは識別注釈）、
`Evidence`、`Reason` に「研究者方針」「原音未確認」を記録した。
`ReadingStatus=confirmed` は当該方針に基づいて注釈を採用したことを示し、
録音で実際の発音が検証されたことを意味しない。実証された発音だけが必要な
分析では、根拠・識別注釈まで確認し、今回の条件付き採用を一括して実測値にしない。
既存の `RecordValidity`（記録の種類）も維持し、参照ページ不一致や例示を
実在する出来事として格上げしない。

非日本語の発音表記拡張は今回行わない。日本語の会話中の略称・外来語を日本語読みと
解釈した例はその仮定を明示し、英語等の実発音をかなで確定したとは扱わない。

## 前版との比較

比較元: `c76277a3046913a9796c5af7e371692bc6320d36`。
選択run: `resource/pairs_v2/2026-10-24-conditional-review/`。

| 段階 | 前版 | 今回 |
| --- | ---: | ---: |
| 原本レコード | 4,490 | 4,490 |
| 採用レコード | 3,730 | 3,765 |
| 採用ペア | 3,752 | 3,787 |
| 除外レコード | 562 | 567 |
| 未確定レコード | 198 | 158 |
| 未処理レコード | 0 | 0 |

未確定42件を再確認し、35件を採用、5件を除外、2件は確認点を具体化して未確定を維持。
そのため未確定は40件減った。前版の除外562件の判定・根拠・原本ハッシュは
一件も変更していない。新たな除外は以下の5件で、いずれも確認用一覧に含める。

| MishearID | 対比 | 除外理由 |
| --- | --- | --- |
| H6E3F490D977F6CC1 | 0.5cc／0.5A | 研究者指定：単位の取り違えとして今回の評価対象外 |
| coffee_break_parts_similar200406_009 | 軌／機（期・基） | キ／キの同音。CSVにある「を一」の重複は転記上の問題で、音韻差にしない |
| coffee_break_parts_similar201809_002 | SHINE／社員 | 文脈上選んだシャイン／シャインでは同音。別の読みの可能性も根拠に残す |
| coffee_break_parts_similar202304_005 | 預超／予兆 | 選定したヨチョウ／ヨチョウでは同音 |
| coffee_break_parts_similar201905_001 | 余積って／寄せ切って | 選定したヨセキッテ／ヨセキッテでは同音 |

除外は原本削除ではない。「同音だからコーパス全体に不要」とも判断しない。
今回の音韻比較用エクスポートから外す判断を、研究者が見直せる状態にした。

## 確認用ファイル

- [除外567件のページ一覧](reviews/2026-10-24-excluded/README.md)：50件ずつ読むためのMarkdown。
- [除外CSV](reviews/2026-10-24-excluded/excluded.csv)：元の11列、選択範囲・読み、理由、根拠、出典、参照コミット、原本ハッシュを保持。
- [今回42件の旧判定／新判定](reviews/2026-10-24-policy/decisions.json)：各RecordReviewを変更前後で追跡する生成済み監査記録。
- [残る未確定158件](reviews/2026-10-24-policy/pending.csv)：原文と個別の未確定理由、次の確認先。

除外CSVの `ResearcherDecision` と `ResearcherComment` はすべて空欄。
確認時はこの2列に記入する。判断値は例えば `keep_excluded`（除外維持）、
`reconsider`（再検討）、`include`（採用希望）。元列や根拠を直接書き換えない。
このコピーは注釈の第二正本ではなく、記入しても自動で採否は変わらない。
再検討時は元のMishearID・原本ハッシュと照合し、根拠を確認して
`data/annotations/reviews.csv` を更新し、新runを生成する。
CSVは式評価を避けるため、表計算ソフトで「テキスト」として取り込む。

## 残件をどう扱うか

158件中155件は [Issue #65](https://github.com/kishiyamat/mishearing-corpus/issues/65)
の非日本語・言語混在の発音表記の課題。日本語優先という既存の指示を維持する。
残る3件は次のとおり。

| MishearID | 未確定の具体的な理由 |
| --- | --- |
| H97CDF35E61389A42 | 1cc/hと1ccの投与動作の取り違えは記録されるが、相手が実際に聞いた語句がない。動作を架空の発話へ変換しない。[Issue #66](https://github.com/kishiyamat/mishearing-corpus/issues/66)で確認 |
| girlschannel_5697216_027 | 「キンキン◯マ◯マ」の伏せ字部分の音が欠ける。元発話を推測で復元しない |
| coffee_break_parts_similar201508_008 | 「損益月」の原表記は確認できるが、文脈に合う自然な読みを選べない。月の読みを恣意的にヅキにしない |

医療事例で今回選定した数詞・単位・略号の読みも、実際の口頭呼称が判明したわけではない。
Issue #66は閉じず、医療機関での呼称確認と条件付きの比較読みの選定を別々に管理する。
H6E3F490D977F6CC1だけは今回の明示指示により対象外とし、他の単位事例まで自動的に除外しない。

## 再生成とローカル検証

編集正本は `data/annotations/reviews.csv` のみ。原本11列、旧run、研究用の
旧1,908行ペアや1,816件の評価分母は変更しない。比較単位が変わった9スパンには
旧PairIDへの対応を保存し、単位が同じ場合は既存IDとその来歴を維持した。

- 原本内容SHA256: `e6b09c686e3f004c5395388488f94d487b1bad75b75fd7d169b3c63415285ab0`（前版と同一）
- 注釈CSVのバイト列SHA256: `067b72feb3879d7d935a72a5353a56df80ca743cb420a85c0143e9957291963d`
- 正規化注釈入力SHA256: `6b5d62a4a302e1e613028b620f87eb422e56c6d6a5f2d339cdaf7254eb2c3d75`
- Python 3.13.3、MeCab 0.996、UTF-8 IPADIC版102。抽出器・辞書の同定値は前版と同一。
- 変更前に回帰テスト7件の失敗を確認。変更後はローカル153件成功。
- RuffのLint・整形検証、mypyのAPI全9モジュールも成功。Actionsには依存しない。
- コミット済みAPIのCSV/JSONL出力3,787件の一致、除外指定例が出力されないこと、
  条件付き読みの根拠・識別注釈がAPIからも失われないことを確認した。

```bash
uv run --locked python -m corpus_api.pair_workflow build \
  --output resource/pairs_v2/NEW-RUN --require-complete
uv run --locked python -m corpus_api.pair_workflow check --require-complete
uv run --locked python -m corpus_api.pair_workflow check --staged --require-complete
uv run --locked --extra api python -m pytest --ignore=tests/asa2025
make api-check

# REFは注釈・原本を含む確定コミット。確認済み出力を上書きしない。
uv run --locked python -m corpus_api.review_pack \
  --repository . --ref REF --output docs/reviews/NEW-EXCLUSION-REVIEW
```

`review_complete=true` は未処理ゼロを示すだけで、今回も
`linguistic_quality_complete=false`。構文検証・テスト合格は、条件付きの読みが
実際の発音であった証明や、研究者による除外の承認の代わりにはならない。
