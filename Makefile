# Makefile for deploying the Streamlit app

.PHONY: setup install run clean build-datapackage asa2025 test asa2025-test api api-test api-check

# プロジェクト用の仮想環境作成＋依存関係インストール
setup:
	uv sync --locked
	@echo "\n[OK] Activate environment with: source .venv/bin/activate"

# コミット済みロックと環境を同期
install:
	uv sync --locked

# 読み取り専用API（配備は行わない）
api:
	uv run --locked --extra api uvicorn corpus_api.main:create_app --factory --host 127.0.0.1

api-test:
	uv run --locked --extra api python -m pytest --ignore=tests/asa2025

api-check:
	uv run --locked ruff check corpus_api tests/test_corpus_api.py
	uv run --locked ruff format --check corpus_api tests/test_corpus_api.py
	uv run --locked --extra api mypy corpus_api

run:
	streamlit run app.py

ggl:
	streamlit run task/google_search_mishearing.py

clean:
	rm -rf __pycache__ *.db

build-datapackage:
	python scripts/build_datapackage.py

friction:
	frictionless validate datapackage.json

test:
	pytest --ignore=tests/asa2025

# ASA2025関連のテストだけを実行（必要なら事前に make asa2025）
asa2025-test:
	pytest tests/asa2025

asa2025:
	sudo apt-get install mecab libmecab-dev mecab-ipadic-utf8
	. .venv/bin/activate && pip install mecab-python3
	@echo "export MECABRC=/etc/mecabrc" >> ~/.bashrc
	. .venv/bin/activate && pip install pykakasi
	. .venv/bin/activate && pip install python-Levenshtein
	@echo "\n[OK] Restart shell or run: export MECABRC=/etc/mecabrc"
	@echo "\n[chiVe] Downloading chive-1.3-mc5_gensim model ..."
	mkdir -p resource
	cd resource && curl -L -O https://sudachi.s3-ap-northeast-1.amazonaws.com/chive/chive-1.3-mc5_gensim.tar.gz
	cd resource && tar -xzvf chive-1.3-mc5_gensim.tar.gz
	@echo "\n[chiVe] Extracted to resource/chive-1.3-mc5_gensim"

# test
# lint
# mypy
# autopep8
