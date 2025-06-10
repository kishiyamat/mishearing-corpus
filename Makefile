# Makefile for deploying the Streamlit app

install:
	pip install -r requirements.txt

run:
	streamlit run app.py

clean:
	rm -rf __pycache__ *.db