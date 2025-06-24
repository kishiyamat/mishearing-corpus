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
