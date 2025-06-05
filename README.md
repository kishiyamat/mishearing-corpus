# Mishearing Corpus (Japanese)  

_Approximately 10 k rows of Japanese (for now) mis-hearing instances,
kept as plain CSV/TSV plus Table Schema 
and automatically validated with `frictionless` + `pre-commit` + GitHub Actions._

---

## Project Roadmap

| Phase                        | Target Size      | Estimated Period | Main Tasks                                                                 | Quick Checkpoint                        |
|-----------------------------|------------------|------------------|----------------------------------------------------------------------------|-----------------------------------------|
| **0. Schema Design**        | 0 → 100          | 1 week           | Transfer samples from existing papers/reports, finalize columns & foreign keys | *Is Frictionless CI green?*             |
| **1. Existing Data Import**  | 100 → 1,500      | 1–1.5 months     | Extract explicit mishearing cases from available sources (search + manual fix) | *Record search queries & extraction rules in markdown* |
| **2. Literature Mining**    | 1,500 → 3,000    | 1 month          | Copy tables from conference papers, theses, tech reports → append to CSV      | *Clear copyright & always fill citation*|
| **3. Crowdsourcing ①**      | 3,000 → 6,000    | 2 months         | Taskify mishearing spots in ASR logs for manual review                        | *Run UI & instructions as MVP, get feedback* |
| **4. Crowdsourcing ②**      | 6,000 → 9,000    | 1 month          | Subject task: listen to short audio, type exactly what was heard             | *Auto-record mic/noise conditions in EnvID* |
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
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # frictionless & pre-commit
pre-commit install                       # auto-validation on commit

# see summary
python scripts/stats.py

# query with DuckDB
python scripts/to_duckdb.py
```

VS Code users: install **Edit CSV** + **Rainbow CSV** for spreadsheet-like editing.

---

## 3. Directory layout

```
mishearing-corpus/
├─ data/                         # —— テーブルごとにサブフォルダ
│  ├─ mishearing/                #   多数のシャードCSV を格納
│  │   ├─ yamato/                #   データソースごとにサブディレクトリ
│  │   │   ├─ 2019-01-15_yamato.csv
│  │   │   └─ ...
│  │   └─ ...
│  ├─ source_utterance/          #   （あとから必要になれば作成）
│  │   └─ …                      #
│  ├─ speaker/                   #   単一ファイルで足りる表はそのまま 1 枚
│  │   └─ speaker.csv
│  ├─ listener/
│  │   └─ listener.csv
│  ├─ environment/
│  │   └─ environment.csv
│  └─ document/
│      └─ document.csv
│
├─ schema/                       # Frictionless Table Schemas
│  └─ mishearing.schema.json
│
├─ scripts/
│  ├─ build_datapackage.py       # シャード(注参照)一覧から datapackage.json を再生成
│  └─ hooks/
│      └─ check_filename.py      # YYYY-MM-DD 形式の命名規則を検査
│
├─ datapackage.json              # ← build_datapackage.py が自動出力
├─ requirements.txt              # frictionless / pre-commit 等
├─ .pre-commit-config.yaml       # ローカル検証フック
└─ .github/
    └─ workflows/
        └─ validate.yml          # CI: ファイル名→datapackage→validate の順で実行
```

- シャード (shard): 大きなテーブルやコレクションを
  意味や順序を保ったまま、複数の小さなファイルやパーティションに分割して管理する方式
- `_slug`: オプションで付ける、わかりやすい短い識別子

---

## 4. Data model (overview)

| Table                  | Key          | Purpose                                  |
| ---------------------- | ------------ | ---------------------------------------- |
| `mishearing/`           | `MishearID`  | one mis-hearing event (sharded CSV files)        |
| `source_utterance/`     | `SrcID`      | original utterance text + phonetic info          |
| `speaker/`              | `SpeakerID`  | speaker metadata (gender, dialect, age…)         |
| `listener/`             | `ListenerID` | listener metadata                                |
| `environment/`          | `EnvID`      | channel / noise / mic specs                      |
| `document/`             | `DocID`      | bibliographic source of each record              |

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
