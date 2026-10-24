# ペア抽出・校正 v2（Issue #63）

原本の11列CSVは `data/mishearing/`、編集する構造化注釈の正本は
`data/annotations/reviews.csv`。`resource/pairs_v2/<run>/` は生成物であり、
手修正しない。Langflow、Streamlit、chiVe、公開サーバーはこの経路に不要。
従来の `resource/extracted_word_pairs*.csv` と研究入力・評価結果は上書きしない。

現行抽出器は `pairs-v2.3`。`word` / `compound` は校正済みの単位分類であり、
機械候補のトークン数や品詞だけでは確定しない。単語・複合語の取得は
`unit_group=lexical` を明示すると単語・複合語だけを取得する。無指定では
全種類を取得し、`unit_group=contextual` では句・文脈単位だけを取得する。

現在の方針・件数・研究者確認用一覧は
[同音排除の撤回と全除外の再確認](pair_review_homophones_2026-10-24.md)を参照。
原音のない場合の条件付き読みは、その根拠を明示して採用し、原音確認済みとは区別する。

## 最初にテストする

```bash
uv sync --locked --extra api
make pairs-test
make api-check
```

MeCab CLI と UTF-8 辞書は実コーパスの抽出時のみ必要。単体/APIテストは小さな
固定トークン列で実行できる。Ubuntuでは `mecab` と `mecab-ipadic-utf8` を利用する。
インストール済みの実行版・辞書情報・辞書ハッシュを実行マニフェストに記録する。
利用した標準APIは `difflib.SequenceMatcher(autojunk=False)` と `csv.DictReader` /
`DictWriter`、MeCab CLIの `-Ochasen`。POS情報は境界候補の分類だけに使い、語彙ベクトルの有無は校正対象の選別に使わない。
run manifestには extractor version/hash、MeCab CLI version、辞書情報と辞書ファイル
SHA-256が記録される。入力・抽出器・辞書設定が対応しない成果物はAPI起動時に拒否される。
仕様の参照は [Python difflib](https://docs.python.org/3.13/library/difflib.html) と
[MeCab公式出力形式](https://taku910.github.io/mecab/format.html)。
Frictionless 5.18.1のPython検証は `Schema.from_descriptor(...)` を渡す契約を
実物のCSVと統合テストで確認している。

## 注釈の契約

- 読み `|下手《したて》`、意味 `|退社《》【意味：帰宅】`、
  識別 `|大山町《おおやまちょう》【識別：渋谷区】`。
- ルビはかな専用。空の読みは不明であり、意味やアクセントを埋めない。
  非日本語の読みがこの記法で確定できなければ保留する。
- 型付き注記は直前のルビ対象に付く。同じ対象への意味・識別注記は複数保持できる。
  隣接するルビ対象も扱える。入れ子・未接続の注記・未知の型・不正構文はエラー。
- 記号 `\ | 《 》 【 】` を実際の本文・補足に含める場合はバックスラッシュで
  エスケープする。従来の `()` / `（）` は形だけで解釈せず、そのまま要確認とする。
- CSVの `SrcAnnotations` / `TgtAnnotations` / `PairSpans` セルはJSON配列。
  原文中の位置はUnicode文字単位の半開区間 `[start,end)`。左右の範囲は独立でよい。
  `Override.surface` は原文の指定範囲内に実在する表記。構造化注釈から表示を生成し、
  表示と構造化フィールドを別々に手編集しない。
- 原文の括弧を分離するときは括弧を含む範囲と、残す `surface`・読み・意味・識別を
  明示する。実際の発話に属する括弧を機械的に消さない。
  例：原文 `谷原（やはら）` は `start=0,end=7,surface="谷原",reading="やはら"`。
  この語を選ぶPairSpanも元の `[0,7)` を指す。読み括弧を外した `[0,2)` だけの
  Overrideでは原文の未分類括弧が残る。採用時は選択ペアの外にある括弧も含めて
  原文全体を分類し、必要な別Overrideを追加する。これは既存の契約で扱える。
- `ReviewStatus` と `TargetDecision` は別物。同音異義語、別語義、別指示対象は残す。
  読みの一致だけで `exclude` にしない。同じ語・同じ解釈の表記違いは、辞書の
  同一見出し・該当語義・原資料の文脈で同一性を確認して整理する。
  同じ読みの別見出しが並ぶだけでは、同一語の証拠にならない。
  `pending` は `undecided` のまま残す。
- `RecordValidity` は記録の種類（`documented` / `illustrative` / `production` /
  `visual` / `unclear`）で、音韻的な対象判定とは独立。
  [Issue #43の確認済み基準](https://github.com/kishiyamat/mishearing-corpus/issues/43#issuecomment-6378482555)
  は「異聴として音韻的に妥当か」。例示・未遂・歌唱・難しい予測だからといって
  自動的に対象外にしない。実際の出来事・方向の確認不足は別の確認事項に記録する。
  今回のエージェントによる採否を、既存の研究者ラベルや1,816件の評価分母へ自動適用しない。
- 同じ表記でも `退社【帰宅】／退社【退職】`、`松屋【百貨店】／松屋【飲食店】`
  のように解釈が異なる場合は意味・識別注釈を保持して採用できる。
  機械抽出もこれらの注釈差を候補として残す。全表記・読み・解釈が同じなら
  機械候補ゼロとするが、読みの一致だけでは候補を落とさない。
  派生ペア/APIも同じ読みの行をまとめず、表記・注釈・PairIDを保持する。
  予測モデルの同読み候補への順位減点や、正解との同音一致による評価はこの処理には加えない。
- 読みを評価に採用するには、原資料の明示・辞書・研究者判断の根拠を `Evidence` に
  記録する。LLMやMeCabの推定だけで正解扱いにしない。かな表記だけの原本も、
  事例の方向・実際の聞き間違いかを文脈と照合する。
- PairSpanは原文の対立単位を表す。共通の左右文脈・助詞・述語は外す一方、
  語内部には切らず、差分が複数離れている場合は独立ペアに分ける。MeCab候補の
  `UnitType` は仮分類で、人手レビューの `PairSpan.unit_type` が採用分類を決める。
- 長い旧Overrideから短いPairSpanへ変更するとき、旧全文読みを機械的に切り出して
  短縮後の読みとして `confirmed` にしてはならない。短縮境界と既存の根拠付き注釈が
  完全一致する場合、根拠に短縮表面の読みが明示される場合、または正確な辞書見出しと
  文脈適合読みの根拠が記録されている場合だけ確定できる。MeCab最適経路、連結推定、
  単一の辞書候補だけでは不十分。注釈は新PairSpan単位に再構成し、意味・識別・読みの
  根拠も対応づける。根拠を移せなければそのペアは `pending` / `undecided` のまま残す。

復号後のレビュー行のスキーマは `schema/pair_review.schema.json`。
派生ペアの列順は `corpus_api.pair_workflow.PAIR_FIELDS` に固定する。
意味・識別の複数値はペアCSVでもJSON配列のセルとして保存する。
`SrcReadingStatus` / `TgtReadingStatus` は `proposed` / `confirmed` / `unknown`。
ローマ字・音素に変換するときは `confirmed` の読みを入力にし、漢字表記の自動読みに
戻さない。今回アクセント・音素体系自体は新設しない。

`confirmed` は注釈上の採用状態であり、原音で確認された実際の発音を保証しない。
研究者方針で選定した読みは、識別注釈（qualifiers）・`Evidence`・`Reason` に
条件と原音未確認を明記する。読みの候補を選べても、出典・出来事の不確かさは
`RecordValidity` と根拠に残す。

## 追加・変更・再校正の手順

辞書を根拠にするときは、読みを推測してから辞書名だけを付けない。
`uv run --locked python -m corpus_api.dictionary 筋肉 熊谷` で、実際のIPADIC辞書に
存在する単語全体の項目・全候補読み・素性・辞書ハッシュを確認できる。
最適経路の自動読みや未知語の推測とは別である。選んだ項目と文脈をEvidenceに記録する。
固有名詞の複数読み、辞書にない語、複合句の読みはこの照合だけで確定しない。

読みの未記入は、まず担当者が調査して埋める。辞書を引いていない通常語や、
保存済み原資料を読んでいない候補を、単に「要確認」として調査完了に数えない。
複合句は、原資料の文脈と実際の辞書項目を照合し、活用・助詞・接辞・連濁も
確認して読みを確定できる。句全体が辞書の見出しであることは必須ではない。
一方、形態素解析の最適経路を連結しただけでは確定しない（例：樋門は
「樋＝とい」＋「門＝もん」ではなく「ひもん」、剣道の素振りは「すぶり」）。
人名の明示読みは一般的な辞書読みより優先する。原資料が非標準の読みそのものを
報告している場合は、正式名称の読みと混同せず識別注釈と根拠に区別を残す。
取得できない資料があっても、確認できる語形・読み・音韻比較と、未確認の出来事の
来歴を分けて調査する。調査を尽くしても根拠が得られない論点だけを確認待ちにする。

1. 元資料と11列原本を追加・変更する。元のMishearIDを追跡可能に保つ。
2. 新しいrun名で機械抽出する。まだ全件の注釈がなくても下書き・未処理を保存できる。

   ```bash
   uv run --locked python -m corpus_api.pair_workflow draft \
     --working-tree --output resource/pairs_v2/YYYY-MM-DD-draft
   ```

   コミット済み原本だけを使う場合は `--working-tree` を省き、必要なら `--ref <SHA>`。
   `source_commit` は読み取り元コミット（working-treeでは編集前の基点）、
   `source_state` と全原本ハッシュで未コミット入力との違いも記録する。
   既存runディレクトリへの上書きは拒否する。
   `draft` は既存レビューを適用しないので、原文変更で古いレビューが失効していても
   新しい機械候補を確認できる。校正正本と過去の確認済みrunは変更しない。

3. `draft.csv` と `records.csv` を原資料と照合する。全候補と候補ゼロの記録を確認し、
   比較単位・注釈・読みを `reviews.csv` へ記入する。新規行は `RecordReview` の必須欄
   を満たすこと。原本ハッシュは `original_hash(raw_row)` で11列すべてから計算する。
   既存原文・読み・根拠の変更を、ハッシュの機械的な差し替えだけで承認しない。
4. 意味・固有名詞の読み・発話方向が不確かなら、論点と根拠を記録して研究者へ確認する。
   独立して確認できる他の行は進める。校正者・日付・変更理由を必ず残す。
5. 注釈変更後に別runへ再生成し、差分を確認する。

   ```bash
   uv run --locked python -m corpus_api.pair_workflow build \
     --working-tree --output resource/pairs_v2/YYYY-MM-DD-reviewed
   uv run --locked python -m corpus_api.pair_workflow validate \
     --output resource/pairs_v2/YYYY-MM-DD-reviewed
   ```

6. 採用するrunを `resource/pairs_v2/current.json` の `directory` で指定する。
   `make pairs-check` は作業ツリーの原本・注釈・生成結果を照合する。
   評価版の確定にはさらに `validate --require-complete` を実行する。
   追加・変更に未対応のレビューや古い成果物があれば失敗する。

   ```bash
   uv run --locked python -m corpus_api.pair_workflow check --require-complete
   ```

7. 原本・注釈・run・ポインター・訂正ログを同じPRでレビューする。
   pre-commitでは `check --staged` によりGit indexの原本・注釈・生成物を直接照合する。
   一部だけステージして不整合になる場合も拒否する。最終的なコミットでも
   APIの起動検証を行う。

レビュー途中のJSONをCSVに取り込む補助手段もある。出力既存ファイルは上書きせず、
生成した新CSVとの差分を確認して正本へ適用する。JSONを第二の編集正本にしない。

旧全文Overrideを短縮候補へ移す調査では、
`scripts/profile_word_span_reading_evidence.py --output /tmp/word-span-evidence.csv` が
候補表面の完全一致辞書項目、旧Overrideの全トークン辞書読み連結の一意性、候補範囲の
MeCabトークン境界対応を診断出力する。best-path readingの一致も別に記録するが、
いずれも診断であって承認ではない。短い読みの自動確定やレビューCSVの編集は行わない。

```bash
uv run --locked python -m corpus_api.pair_workflow import-reviews \
  --inputs /tmp/deliberate-reviews.json --output /tmp/reviews-next.csv
```

## 生成物と件数

| ファイル | 内容 |
| --- | --- |
| `draft.csv` | 機械候補と全文比較案。正解データではない |
| `records.csv` | 全原本の台帳。候補ゼロ、未処理、保留、除外も含む |
| `reviewed.csv` | 校正済みの比較単位。採用／除外を区別 |
| `pending.csv` | 校正中の比較単位。候補を選べない保留も台帳には残る |
| `changes.csv` | 機械候補と校正後の差、根拠を辿れる校正者・理由 |
| `manifest.json` | 入力版、原本・抽出コード・成果物のハッシュ、環境、各段階の件数 |

`reviewed_record_count + pending_record_count + unprocessed_count = input_count`。
`excluded_record_count` は校正済みの内数。訂正件数や候補数とは別に数える。
採用ペアは `evaluation_pair_count`。保留は出力対象外だが、件数を隠さない。
未処理ゼロは全件に判断を記録した状態であり、保留があれば言語的品質の確定完了ではない。
構文・ハッシュ・件数検証は意味や発音の正しさそのものを保証しない。

PairIDは原本と原文位置・比較単位に基づくUUID。校正で同じペアを訂正するときは
`PairSpans[].PairID` で既存IDを維持できる。分割・統合は新IDにし
`SupersedesPairID` に旧IDを記録する。原本や抽出条件が変わったときは、該当レビューと
比較単位を再確認してから新runを作る。

## ローカルHTTP

`make api`。APIは選択コミットのGit blobだけを読み、未コミットの校正を配信しない。

- `GET /v1/pairs?q=...&mishear_id=...&unit_type=compound&unit_group=lexical&limit=100&offset=0`
  校正済みの採用・除外行を検索する。`q` は表記・読みの部分一致。
- `unit_group=lexical` は `word` / `compound`、`contextual` は
  `particle-inclusive` / `phrase` を選ぶ。`unit_type` を併用すると積集合になる。
  無指定時は従来どおり全種類を返す。
- `GET /v1/pairs/{PairID}` は完全一致の単件取得。
- `GET /v1/pairs/export?format=csv` または `format=jsonl`。
  一覧と同じ検索条件を指定でき、採用された校正済みペアだけを出力する。
  未処理が残る場合はHTTP 409。保留は除外し、全体の保留件数を返す。
- 単語・複合語だけのCSVは
  `GET /v1/pairs/export?format=csv&unit_group=lexical`。句・句断片を含めた出力は
  `unit_group=contextual` で明示する。UnitTypeの訂正前のrunでは分類が反映されない。
- `dataset_version=<40桁SHA>` で配信版を照合する。別版へ勝手にフォールバックしない。
  原本の版・ハッシュとペアの版・ハッシュを別々に返す。
  校正成果物のない旧コミットではペアAPIだけ503、既存records APIは利用できる。

KikoePredは元の1,816ペアの評価を保存し、訂正版は別版として取り込む。
データ訂正・読み指定・文脈単位・予測ロジック変更の効果を混ぜて報告しない。

## 初回校正の状況

正確な進捗は採用runの `manifest.json` と `records.csv` を参照する。
個別の確認事項は [pair_review_questions.md](pair_review_questions.md)。
未処理・保留が残る版を「全件品質確認済み」と呼ばない。
初回runの保留は調査の完了を意味しない。追加調査の訂正を反映した最新runを
`current.json` で選択し、初回runは経緯の記録として保持する。
追加調査の方法・訂正内容は [追加調査ノート](pair_review_research_2026-10-24.md) を参照。
