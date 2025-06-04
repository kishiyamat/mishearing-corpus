# Mishearing Corpus (Japanese)  
_Approximately 10 k rows of Japanese mis-hearing instances, kept as plain CSV/TSV plus Table Schema and automatically validated with Frictionless + pre-commit + GitHub Actions._

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

* predicting mis-hearings in daily life, working, or learning environments
* phonetic and psycholinguistic research on perceptual epenthesis or dialect differences  
* training / evaluating speech-recognition or TTS robustness  
* data-driven pronunciation teaching materials

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
````

VS Code users: install **Edit CSV** + **Rainbow CSV** for spreadsheet-like editing.

---

## 3. Directory layout

```
mishearing-corpus/
├─ data/
│  ├─ mishearing.csv          # Main table (≈10 k rows)
│  ├─ source_utterance.csv
│  ├─ speaker.csv
│  ├─ listener.csv
│  ├─ environment.csv
│  └─ document.csv
├─ schema/                    # Frictionless Table Schemas
│  ├─ mishearing.schema.json
│  └─ …                       # one per table
├─ scripts/
│  ├─ validate.py             # optional helpers
│  ├─ stats.py                # row counts etc.
│  └─ to_duckdb.py            # ad-hoc SQL on CSV
├─ .pre-commit-config.yaml
└─ .github/workflows/validate.yml
```

---

## 4. Data model (overview)

| Table                  | Key          | Purpose                                  |
| ---------------------- | ------------ | ---------------------------------------- |
| `mishearing.csv`       | `MishearID`  | one mis-hearing event                    |
| `source_utterance.csv` | `SrcID`      | original utterance text + phonetic info  |
| `speaker.csv`          | `SpeakerID`  | speaker metadata (gender, dialect, age…) |
| `listener.csv`         | `ListenerID` | listener metadata                        |
| `environment.csv`      | `EnvID`      | channel / noise / mic specs              |
| `document.csv`         | `DocID`      | bibliographic source of each record      |

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

1. **Fork → Branch → PR**.
2. Append rows only; don’t rearrange column order.
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

> You may copy, modify, distribute and use the corpus—including commercially—
> provided you credit **“Mishearing Corpus (2025)”** and link back to this repository.

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
  howpublished = {\url{https://github.com/<your-org>/mishearing-corpus}},
  note         = {Version 1.0}
}
```

---

## 9. Contact · acknowledgements

Maintainer : **岸山 健**  〈kishiyamat at example.com〉
Issues   : please open a GitHub issue or discussion thread.

We thank all annotators, as well as the maintainers of CSJ, NPCMJ, BCCWJ, and other resources cited herein.
