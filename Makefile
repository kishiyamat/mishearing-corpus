# Makefile for deploying the Streamlit app

.PHONY: install run clean build-datapackage
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
	pytest

asa2025:
	sudo apt-get install mecab libmecab-dev mecab-ipadic-utf8
	pip install mecab-python3
	export MECABRC=/etc/mecabrc
	pip install pykakasi
	pip install python-Levenshtein
	pip install numpy==1.26.4
	pip install gensim==4.3.2
    pip install scipy==1.10.1

# test
# lint
# mypy
# autopep8
