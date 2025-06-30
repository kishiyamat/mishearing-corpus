# Mishearing Corpus (Japanese)  

_Approximately 10 k rows of Japanese (for now) mis-hearing instances,
kept as plain CSV/TSV plus Table Schema 
and automatically validated with `frictionless` + `pre-commit` + GitHub Actions._

You can see the data [here](https://mishearing-corpus-dev.streamlit.app/).

---

## Project Roadmap

| Phase                        | Target Size      | Estimated Period | Main Tasks                                                                 | Quick Checkpoint                        |
|-----------------------------|------------------|------------------|----------------------------------------------------------------------------|-----------------------------------------|
| **0. Schema Design**        | 0 → 100          | 1 week           | Transfer samples from existing papers/reports, finalize columns & foreign keys | *Is Frictionless CI green?*             |
| **1. Existing Data Import**  | 100 → 1,500      | 1–1.5 months     | Extract explicit mishearing cases from available sources (search + manual fix) | *Record search queries & extraction rules in markdown* |
| **2. Literature Mining**    | 1,500 → 3,000    | 1 month          | Copy tables from conference papers, theses, tech reports → append to CSV      | *Clear copyright & always fill citation*|
| **3. Crowdsourcing ①**      | 3,000 → 6,000    | 2 months         | Taskify mishearing spots in ASR logs for manual review                        | *Run UI & instructions as MVP, get feedback* |
| **4. Crowdsourcing ②**      | 6,000 → 9,000    | 1 month          | Subject task: listen to short audio, type exactly what was heard             | *Auto-record mic/noise conditions in Env* |
| **5. Expansion & Review**   | 9,000 → 10,000+  | 1 month          | Add review labels (confidence, duplicate flag), fill missing genres           | *pre-commit: RED → fix → GREEN*         |

---

## Contents
- [1. What's inside?](#1-whats-inside)
- [2. Quick start](#2-quick-start)
- [3. Directory layout](#3-directory-layout)
- [4. Data model](#4-data-model)
- [5. Validation workflow](#5-validation-workflow)
- [6. Contributing](#6-contributing)
- [7. Licence](#7-licence)
- [8. Citation](#8-citation)
- [9. Contact / acknowledgements](#9-contact--acknowledgements)
- [10. Data Sources](#10-data-sources)
- [11. Applications](#11-applications)

---

## 1. What's inside?

The corpus records how spoken Japanese utterances were **mis-heard**,
together with speaker/listener profiles and recording conditions.  
Typical use-cases:

* Evaluation of models that predict mishearing events
* Predicting mis-hearings in daily life, work, or educational settings
* Phonetic and psycholinguistic research on perceptual epenthesis or dialect differences  
* Training and evaluating the robustness of speech recognition or TTS systems  
* Developing data-driven pronunciation teaching materials

The corpus includes a `Language` column, allowing for future expansion to non-Japanese data as well.
A `Category` column is also included to classify each instance by context
---some involve safety-critical mishearings 
(e.g., in medical or industrial settings),
while others come from everyday, educational, or entertainment situations.

---

## 2. Quick start

```bash
git clone https://github.com/kishiyamat/mishearing-corpus.git
cd mishearing-corpus

# set up tools (once)
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt          # frictionless & pre-commit
pre-commit install                       # auto-validation on commit

# see summary (Future)
# python scripts/stats.py

# query with DuckDB (Future)
# python scripts/to_duckdb.py
```

VS Code users: install **Edit CSV** + **Rainbow CSV** for spreadsheet-like editing.

---

## 3. Directory layout

各ディレクトリ・ファイルの役割を以下に示します。
追加時に mishearing, environment, tag は必須としています。

```
mishearing-corpus/
├─ app.py                         # https://mishearing-corpus-dev.streamlit.app/ で動く検索アプリ
├─ data/                          # データ本体。各テーブルごとにサブフォルダを分割
│  ├─ mishearing/                # 誤聴事例（メインテーブル）、複数CSVシャードで管理
│  │   ├─ yamato/               # データソースごとのサブディレクトリ
│  │   │   ├─ 2019-01-15_yamato.csv  # 日付＋ソース名で命名
│  │   │   └─ ...
│  │   └─ ...
│  ├─ environment/               # 録音環境情報
│  │   ├─ yamato/               # データソースごとのブリッジテーブル
│  │   │   ├─ 2019-01-15_yamato.csv  # 日付＋ソース名で命名
│  │   │   └─ ...
│  │   └─ translation.csv       # 環境(place, modal, ...)の翻訳
│  ├─ speaker/                   # 話者情 (未整備)報
│  │   └─ speaker.csv
│  ├─ listener/                  # 聞き手情報 (未整備)
│  │   └─ listener.csv
│  └─ tag/                       # タグ情報（ジャンルやテーマ分類）
│       ├─ yamato/               # データソースごとのサブディレクトリ
│       │   ├─ 2019-01-15_yamato.csv  # 日付＋ソース名で命名
│       │   └─ ...
│       └─ translation.csv       # タグ (genre, category, ...)の翻訳
│
├─ schema/                       # Frictionless Table Schema（各テーブルの定義JSON）
│  └─ mishearing.schema.json
│
├─ scripts/                      # 補助スクリプト類
│  ├─ build_datapackage.py       # シャード一覧からdatapackage.jsonを自動生成
│  └─ hooks/
│      └─ check_filename.py      # ファイル名に.や*をふくまないようテスト
│
├─ tests/                        # テストコード（スクリプトやバリデーションの自動テスト）
│  └─ test_scripts.py
│
├─ datapackage.json              # データパッケージ定義（自動生成）
├─ requirements.txt              # 必要なPythonパッケージ一覧
├─ .pre-commit-config.yaml       # pre-commit用フック設定
└─ .github/
  └─ workflows/
    └─ validate.yml          # GitHub Actions用CIワークフロー
```

各テーブルの詳細やカラム定義は `schema/` 配下のJSONファイルを参照してください。
```

- シャード (shard): 大きなテーブルやコレクションを
  意味や順序を保ったまま、複数の小さなファイルやパーティションに分割して管理する方式
- `_slug`: オプションで付ける、わかりやすい短い識別子

---

## 4. Data model (overview)

| Table                  | Key          | Purpose                                  |
| ---------------------- | ------------ | ---------------------------------------- |
| `mishearing/`          | `MishearID`  | one mis-hearing event (sharded CSV files)        |
| `tag/`                 | `TagID`      | ジャンルやテーマ分類              |
| `environment/`         | `EnvID`      | place / channel / noise / mic specs              |
| `speaker/`             | `SpeakerID`  | speaker metadata (gender, dialect, age…)         |
| `listener/`            | `ListenerID` | listener metadata                                |

Full column definitions live in the corresponding `*.schema.json`.

---

## 5. Validation workflow

| Stage            | Tool                     | Trigger                                                                             |
| ---------------- | ------------------------ | ----------------------------------------------------------------------------------- |
| Local edit       | VS Code + **pre-commit** | on every `git commit`                                                               |
| CI               | GitHub Actions           | on every push & PR                                                                  |
| What is checked? | `frictionless validate`  | – correct column types – primary/foreign-key integrity – no extra / missing columns |

If validation fails, the commit/merge is blocked and a detailed error list is shown.

---

## 6. Contributing

1. **Fork -> Branch -> PR**.
2. Append rows only; don't rearrange column order.
3. Run `frictionless validate --schema schema/*.json data/*.csv` locally until it passes.
4. Push; the CI must turn green.
5. PR template asks for:
   * new `MishearID` range
   * data source (paper / annotation task / synthetic)
   * statement that you own the rights or the excerpt is within quotation limits.

See `CONTRIBUTING.md` for step-by-step details.

---

## 7. Licence

### Data

**Creative Commons Attribution 4.0 International (CC BY 4.0)**
[https://creativecommons.org/licenses/by/4.0/](https://creativecommons.org/licenses/by/4.0/)

> You may copy, modify, distribute and use the corpus---including commercially---
> provided you credit **``Mishearing Corpus (2025)''** and link back to this repository.

⚠️ Rows flagged `OriginalFlag = 1` contain minimal quotations drawn from corpora whose full texts/audio cannot be redistributed. Those excerpts remain under their original licences; they are included here under Japanese quotation exceptions for research.

### Code / schemas

MIT License (see `LICENSE-MIT`).

---

## 8. Citation

```bibtex
@misc{MishearingCorpus2025,
  author       = {Kishiyama, T. and Contributors},
  title        = {Mishearing Corpus: A CC BY 4.0 dataset of Japanese speech misperceptions},
  year         = {2025},
  howpublished = {\url{https://github.com/kishiyamat/mishearing-corpus}},
  note         = {Version 1.0}
}
```

---

## 9. Contact · acknowledgements

Special thanks to [Yamato Sokki Co., Ltd.](https://www.yamatosokki.co.jp/mistake)
for generously providing a large amount of mishearing data used in this corpus.

Maintainer : Takeshi Kishiyama  〈kishiyamat at example.com〉
Issues   : please open a GitHub issue or discussion thread.

We thank all annotators and contributors to this project.

## 10. Data Sources

### Tenshokudou Taxi Media
- **Source**: Tenshokudou Media
- **URL**: [https://www.tenshokudou.com/media/?p=13401](https://www.tenshokudou.com/media/?p=13401)
- **Description**: Mishearing data collected from taxi-related media articles published by Tenshokudou.

### Yamato Sokki
- **Source**: Yamato Sokki Co., Ltd.
- **URL**: [https://www.yamatosokki.co.jp/mistake/similar201901](https://www.yamatosokki.co.jp/mistake/similar201901)
- **Description**: Mishearing data extracted from reports and articles provided by Yamato Sokki Co., Ltd.

## 10. Data Sources (N=196)

### Tenshokudou Taxi Media (N=22)
- **Source**: Tenshokudou Media
- **URL**: [https://www.tenshokudou.com/media/?p=13401](https://www.tenshokudou.com/media/?p=13401)
- **Archive**: https://megalodon.jp/2025-0609-1602-44/https://www.tenshokudou.com:443/media/?p=13401
- **Description**: Mishearing data collected from taxi-related media articles published by Tenshokudou.

### Yamato Sokki (N=5)
- **Source**: Yamato Sokki Co., Ltd.
- **URL**: [https://www.yamatosokki.co.jp/mistake/similar201901](https://www.yamatosokki.co.jp/mistake/similar201901)
- **Description**: Mishearing data extracted from reports and articles provided by Yamato Sokki Co., Ltd.

### Gendai Medi (N=8)a
- **Source**: Gendai Media
- **URL**: [https://gendai.media/articles/-/152393?imp=0](https://gendai.media/articles/-/152393?imp=0)
- **Archive**: https://megalodon.jp/2025-0610-1550-38/https://gendai.media:443/articles/-/152393?imp=0
- **Description**: Mishearing data derived from articles published by Gendai Media, focusing on public facilities and store names.

### Med Safe (N=42)
- **Source**: https://www.med-safe.jp/mpsearch/SearchReportResult.action
- **URL**: https://www.med-safe.jp/mpsearch/SearchReportResult.action
- **Description**: See `resource/medsafe/readme.md`

### Kikimatsugai 1101 (N=9)
- できれば加えたいデータ(かなり量がある)

### Google

基本的にpagesの下で回収する実験を行う。
できるだけLangflowで構成を作って、サーバーをローカルで立てて動かす。
`make run` でなく `make exp` などにして、走らせるファイルを変えたほうが良いかもしれない。

- **Source**: Various
- **URL**: Depends on the fetched URL
- **Archive**: N/A
- **Description**: 

どういう場合を除外したか: resourceのnot_relevantディレクトリに移動
- YouTubeの文字起こし
  - youtube_AcrugLVnrLE(https://www.youtube.com/watch?v=AcrugLVnrLE) は事例が多いので気合
  - ラファエルさんの動画はアルフォート→アルフォード？みたいなものだがスルー
- 判定のできない情報
  - 外国語 (4travel_10649575_001): アルトゥン（黄金）の塔,アルトゥ（6）の塔
  -  芸術は場数だ→芸術は爆発だ
- 小説や創作物: おっさんズラブの「嫁がイカゲームっつうのに」, ただし、同音語は許可
- 人外は含める (モデルをいれるなら犬も入れていい)
  - 犬による聞き取り: はさみ→ささみ
  - AIモデルは含めるが、タグをつける。学会→学会など。
- 聞き間違いじゃない場合
  - 聞き間違いかと思ったが
  - 想定の話: I like の I を eye と聞き間違えない理由は...
- ハルシネーション
  - takeeats_sushi_002,いくら,いか,ネタ名はゆっくり、はっきり伝える。,電話注文時、語尾が似ているため聞き間違いが発生しやすい。,True,takeeats_sushi,https://take-eats.jp/scenes/sushi/,日本語,"['寿司', '飲食', '電話注文', '聞き間違い', '接客', '日本語']","['電話注文', '店内', '雑音']"
  - pochistory_002,パッチーズ,ポチ,日本語話者注意,英語話者が「パッチーズ」と言い直したのを、日本人が「ポチ」と聞き間違えた。,False,pochistory_10455,https://xn--h9jua5ezakf0c3qner030b.com/10455.html,日本語,"['言葉の由来', '聞き間違い', '日本文化', '犬', '明治時代', '番組解説', '非母語話者（英語→日本語）']","['明治時代の横浜', '異文化交流']"

#### `"Mishearing of to*no聞き間違い"` (N=110)

1. Use APIFY's API to perform a Google search query and retrieve URLs.
  - APIを叩いても100件取得しきれていない。
  - その後、スクリプトを修正してみたが、　62件程度なのでむしろ良い方だった。
2. For each URL, use an LLM to output the data into a CSV: `url2json2csv`.
3. Manually review and correct the data.
4. Use an LLM to refine the CSV: `fix_csv_google_to_star_no_kikimatigai`.
    - Check CSV format
    - Generate EnvID
    - Generate TagID
5. Perform a final manual review and correction.
6. save to google_to_star_no_kikimatigai_100_4-1

#### `"Mishearing of to*no聞き間違え"` (N=32)

`google_to_star_no_kikimatigae` (commit_id: `259b981`)
1. 検索するクエリを決める
1. クエリに基づいて、保存するディレクトリの名前を決める
1. ApifyのGoogle Search Scraperを実行して、検索結果を取得
1. 取得した検索結果のURLを使って、mishearing-scrapeを実行
1. 保存された結果のCSVを手動で確認、分類
    1. not_relevant
    2. relevant
1. 修正したCSVをAPIに送ってフォーマット修正する

#### `"Mishearing of to*wo*聞き間違*"` (N=7)

`google_to_star_wo_kikimatiga` (commit_id: [31f1f79](https://github.com/kishiyamat/mishearing-corpus/pull/15/commits/31f1f7905cf7c06f85ade35af5f632820d5f0bde))

上に同じ

#### `"Mishearing of wo*to*聞き間違*"` (N=20)


### Google | Taxk (N=196)

- 作成したアプリで収集(`queries = 'タクシー "聞き間違え"'`)
- 重複もあるかもしれない。

### Google | Taxk (N=244)

- 作成したアプリで収集(`queries = 'タクシー "聞き間違い"'`)
- 重複するURLで事前にスキップ

ときおり、聞き間違いを集めているスレッドがあって大きく収集できる。

言い間違いのデータだったり、SrcとTgtが逆になっているパターンがあるので
注意して編集する.

### Google | Shigoto (N=?)

- 作成したアプリで収集(`queries = '仕事 "聞き間違え"'`) -> N=?
- 作成したアプリで収集(`queries = '仕事 "聞き間違い"'`) -> N=?

漫画の例は回収できればする。
言い間違いと思い込んで聞き間違えた場合は無視（酷暑のホットコーヒー→アイスコーヒーの確認。）
- 差別的な例は除外

ファイル名が.を含んでしまう場合がある。

### Google | Business (N=?)

- IgnoreのURLを指定できるように更新
  - resourceの中にあるnot_relevant directoryにあるcsvのurlを無視する。
- 作成したアプリで収集(`queries = 'ビジネス "聞き間違え"'`) -> N=?
- 作成したアプリで収集(`queries = 'ビジネス "聞き間違い"'`) -> N=?

### Indivisuals

- 個人の報告
- データを整理しやすいフォームを整備する
  - テキストを貼り付ける
    - Src, Tgt
    - 状況を述べる
    - カテゴリー
    - だれがなにを
  - LLMで自動整形

#### Kishiyama 

個人的な経験

## 11. Applications

### Machine Learning

* Evaluation of models that predict mishearing events
* Predicting mis-hearings in daily life, work, or educational settings

### Psycholinguistics

* Phonetic and psycholinguistic research on perceptual epenthesis or dialect differences  