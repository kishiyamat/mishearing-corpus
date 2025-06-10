# Makefile for deploying the Streamlit app

.PHONY: install run clean
install:
	pip install -r requirements.txt

run:
	streamlit run app.py

clean:
	rm -rf __pycache__ *.db