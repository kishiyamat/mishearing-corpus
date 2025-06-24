import streamlit as st
from pages.experiments.src.google_to_star_no_kikimatigai import scrape

# Scrapeの対象のURL
st.write("""
このタブでは、指定したURLからデータをスクレイピングし、
CSVファイルとして保存することができます。
""")
target_url = st.text_input("URL: ", "https://note.com/imominty/n/ne9a96dee1118")
save_path = st.text_input("base path: ", "/home/kishiyamat/mishearing-corpus/directory")
if not (target_url and save_path):
    st.warning("Please enter a URL to scrape and Directory to save it to.")
else:
    if st.button("Save CSV"):
        scrape(target_url, save_path)

