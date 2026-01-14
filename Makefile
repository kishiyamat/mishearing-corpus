# Makefile for deploying the Streamlit app

.PHONY: setup install run clean build-datapackage asa2025 test asa2025-test

# プロジェクト用の仮想環境作成＋依存関係インストール
setup:
	python -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
	. .venv/bin/activate && pip install -r requirements.txt
	@echo "\n[OK] Activate environment with: source .venv/bin/activate"

# 既存環境に requirements.txt だけ入れる場合
install:
	pip install -r requirements.txt

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
