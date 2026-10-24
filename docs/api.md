# Public corpus API v1

公開CSVを研究・ブログ・一般のアプリから同じ方法で取得するための、読み取り専用APIです。
このリポジトリの公開データだけを扱います。非公開の注釈・実験刺激・参加者データ、
音声生成、ブログの表示処理は含みません。既存のStreamlit viewerはそのまま残します。

## 起動とローカル検証

```bash
uv sync --locked --extra api
uv run --locked --extra api uvicorn corpus_api.main:create_app --factory --host 127.0.0.1
# 対話的仕様: http://127.0.0.1:8000/docs
# 機械可読仕様: http://127.0.0.1:8000/openapi.json

uv run --locked --extra api python -m pytest --ignore=tests/asa2025
uv run --locked ruff check corpus_api tests/test_corpus_api.py
uv run --locked ruff format --check corpus_api tests/test_corpus_api.py
uv run --locked --extra api mypy corpus_api
```

`api` extraがない環境ではAPIテストをスキップし、既存のデータ検証は実行できます。
Actionsの復旧・APIの外部配備はこの変更には含みません。

## データ版の契約

- `/v1`はAPIの形式の版です。`dataset_version`は**データを読み出したGitコミットの完全なSHA**です。
- 起動時に一つのコミットを解決し、そのGitオブジェクトの公開CSV・スキーマを読み込みます。
  作業ツリーの未コミットCSV、親リポジトリは読みません。records APIは
  `resource/`を読みません。ペアAPIだけは後述の明示的な校正成果物を読みます。
- 既定はこのリポジトリの`HEAD`。`MISHEARING_DATASET_REF`でローカルに存在するコミットやタグを
  指定できます。別のcheckoutは`MISHEARING_CORPUS_ROOT`で指定します。Git checkoutが必要です。
- 稼働中は固定し、ブランチの更新を自動で追いません。更新は再起動時に明示的に行います。
- 応答の`dataset_version`を後続リクエストの同名パラメーターへ指定してください。
  このインスタンスが提供していない版は404です。履歴をリクエストごとにcheckoutしたり、
  存在しない版を最新に置き換えたりしません。旧版には、その版を設定したインスタンスまたはサブモジュールを使います。
- `dataset_sha256`は、読み込んだ`data/mishearing/`・`data/tag/`・`data/environment/`の全CSV
  （翻訳CSVを含む）と`schema/`のJSONを対象とする内容指紋です。
  相対パス順の`[{"path":...,"sha256":...}, ...]`を、UTF-8・キー順・空白なし・非ASCIIを
  そのまま使うJSONへ直列化し、SHA-256を計算します。コミットが違っても同内容なら一致します。
- API処理自体の版も再現に必要です。データSHAとともにAPIコードの採用コミットを記録してください。

```bash
MISHEARING_DATASET_REF=af65870567fab3edb2e6d67381588129a2bf284c \
  uv run --locked --extra api uvicorn corpus_api.main:create_app --factory
```

## エンドポイント

| GET | 用途 |
| --- | --- |
| `/v1/datasets` | このインスタンスで利用できる一つのデータ版、件数、指紋、タグ・環境・言語・収集元のID一覧 |
| `/v1/records` | 条件検索とページ単位の取得 |
| `/v1/records/{MishearID}` | 完全一致IDでの単件取得 |
| `/v1/export` | 同じ検索条件の全一致行をCSVまたはJSONLで取得 |

検索とexportの共通条件:

| パラメーター | 意味 |
| --- | --- |
| `dataset_version` | 提供中の完全SHAとの一致確認。省略時は提供中の版 |
| `q` | `Src`または`Tgt`への部分一致 |
| `src`, `tgt` | 各列への部分一致。`q`を含む他条件とANDで結合 |
| `tags` | `tags=A&tags=B`のようにIDを繰り返す。表示ラベルではない |
| `tag_mode` | `and`（既定）または`or` |
| `environments`, `environment_mode` | 同様に`EnvID`を指定。既定は`and` |
| `language` | `Language`の完全一致。`ja/en`を勝手に分割しない |
| `source` | `data/mishearing/`からCSVの親ディレクトリまでの相対パスの完全一致 |

部分一致はUnicodeの`casefold()`後に**文字列として**比較します。正規表現、分かち書き、
かな・漢字変換、全角半角変換、タグ同義語の統合は行いません。
タグ内・環境内のAND/ORを計算した後、それぞれと他の条件をANDで結合します。
未指定の分類は制限しません。未知の分類ID・言語・収集元は0件です。
パラメーター名の誤記・空の検索語・不正なmode・範囲外のページ指定は422です。
文字列条件は最大500文字、分類IDは1つ128文字まで、分類ごとに最大50指定です。

`/v1/records`のみ`limit`（既定100、1〜1000）と`offset`（既定0、0以上）を受け取ります。
`MishearID`の文字列昇順で固定し、全一致件数`total`、`next_offset`、適用条件`filters`と
データ版を返します。提供版を固定してページをめくることで重複・取りこぼしを防ぎます。
単件の不明IDは404です。すべての応答データは読み取り専用です。

## 返却レコードと欠測

スキーマの11列を元の名前で返します。CSVの文字列と空文字列を保持します。
`OriginalFlag`も原表記の文字列（`True`、`False`、`1`、`0`など）です。
人物プロフィールや音声URLなど、元データにない情報を補完しません。
追加列は`TagIDs`・`EnvIDs`（重複除去したID昇順の配列）、`source`・`source_file`です。
`source_file`は`data/mishearing/収集元/ファイル.csv`というリポジトリ相対パスです。
一覧に返す分類IDは、実在する事例に付いたIDに限ります。
収集元URLの欠測は空文字列のままです。

起動時に空・重複の`MishearID`、事例・ブリッジCSVの列不一致・行破損を検出したら起動を失敗させます。
一方、事例が存在しないタグ・環境リンクは事例を増やさず、`quality`内の孤立リンク行数で報告します。
関連リンクがない事例も検索条件が未指定なら保持します。元のCSVは自動修正しません。
翻訳CSVは内容指紋には含めますが、初版では解釈・返却しません。
既存のタグ翻訳には`MIDDLE_AGED,ja、中年`という列区切り不整合が1行あり、
ラベル付きカタログを実装する際に原本の確認と修正を別途行う必要があります。

## exportと保存

`format=csv`（既定）または`format=jsonl`。ページ指定は受け付けず、全一致行を出力します。
どちらもUTF-8、ID昇順。各行に`dataset_version`・`dataset_sha256`も付与します。
CSVの`TagIDs`・`EnvIDs`セルはJSON配列です。自由記述の改行やカンマはCSV引用で保持します。
0件のCSVはヘッダー行のみ、JSONLは空ファイルです。
CSVセルは元の文字列を保持し、表計算ソフトの数式を無害化する変換は行いません。
外部由来の文字列として、スプレッドシートへの取り込み方法を選んでください。

exportのHTTPヘッダー:

- `X-Dataset-Version`, `X-Dataset-SHA256`: 入力の版と指紋
- `X-Applied-Filters`: 適用条件をキー順のASCII JSONで記録（非ASCIIはJSONエスケープ）
- `X-Result-Count`: 出力件数
- `X-Export-SHA256`: **応答本文のバイト列**のSHA-256

ファイルだけでは適用条件が失われるため、ヘッダーも一緒に保存してください。
ブラウザーからの読み取り用にCORSを許可し、これらのヘッダーを公開します。書き込み・認証付きCORSは提供しません。

```bash
curl 'http://127.0.0.1:8000/v1/datasets'
# 返された完全SHAをdataset_versionに指定
curl --get 'http://127.0.0.1:8000/v1/records' \
  --data-urlencode 'q=聞き間違い' --data-urlencode 'language=ja' --data-urlencode 'limit=5'
curl --get 'http://127.0.0.1:8000/v1/export' \
  --data-urlencode 'format=jsonl' --data-urlencode 'language=ja' \
  -D corpus.headers -o corpus.jsonl
sha256sum corpus.jsonl
```

研究用の取得では、上の例に`--data-urlencode 'dataset_version=<版一覧で確認した完全SHA>'`を追加します。
ヘッダーを保存することで、0件の場合も版・条件・本文指紋を記録できます。

## 校正済みペア（Issue #63）

[抽出・校正の手順と列契約](pair_workflow.md)で生成した成果物を読みます。
`resource/pairs_v2/current.json` が選ぶrunの6ファイルと
`data/annotations/reviews.csv` のコミット済みblobだけが対象です。
他のresourceやPrivate資産、未コミットの校正を探索・配信しません。

- `GET /v1/pairs`: `q`（表記・読みの部分一致）、`mishear_id`、`unit_type`、`unit_group`、
  `limit`、`offset`で校正済みの採用・除外行を検索。
- `unit_group=lexical`は`word` / `compound`、`contextual`は
  `particle-inclusive` / `phrase`。`unit_type`との併用は積集合で、無指定時は全種類。
- `GET /v1/pairs/{pair_id}`: PairID完全一致。
- `GET /v1/pairs/export?format=csv|jsonl`: 一覧と同じ検索条件で採用行のみを出力。
  ページング指定は不可。未処理原本があれば409、保留は出力しない。
  単語・複合語CSVは`?format=csv&unit_group=lexical`で取得する。

原本の `dataset_version` / `dataset_sha256` と、ペアの `pair_version` /
`pair_sha256` は別に返します。exportは各行にも版・ハッシュを付加し、
`X-Pair-Version` / `X-Pair-SHA256` / `X-Coverage` と既存の出力検証ヘッダーを返します。
未収録PairID・別の版は404、校正成果物のない旧コミットはペアAPIだけ503です。
原本・注釈・成果物の不整合は起動時に拒否します。

`RecordValidity`（記録の種類）と `TargetDecision`（音韻的適否）は独立です。
保留件数が残る出力は「確定した部分集合」であり、全件の言語的品質を保証しません。
新しい版を旧研究入力・評価分母へ自動で置換しないでください。

## 利用上の注意と今後

収集事例の件数は、実社会での誤聴発生率や代表的な分布ではありません。
ブログやアプリでは`URL`・`DocID`・`source_file`を保持し、欠測を明記してください。
APIは既存の公開範囲・ライセンスを変更しません。READMEの利用条件と原出典の制約を確認してください。
既存のREADMEとLICENSEの表記不一致は、この実装で新たな利用許諾を推定して解決しません。

バッチID取得、ラベル付き分類カタログ、統計、音素・アクセント、Web/ブログの分離は後続の対象です。
現段階で未収録の音声・音素・アクセントをAPIが提供しているとは扱わないでください。

実装に使う標準機能: [FastAPI query models](https://fastapi.tiangolo.com/tutorial/query-param-models/)、
[lifespan](https://fastapi.tiangolo.com/advanced/events/)、[TestClient](https://fastapi.tiangolo.com/tutorial/testing/)、
[GitPython Git objects](https://gitpython.readthedocs.io/en/stable/tutorial.html#understanding-objects)。
