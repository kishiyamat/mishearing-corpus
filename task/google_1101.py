import streamlit as st  
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from task.google_search import google_search
import requests

st.write("### クエリと保存ディレクトリの設定")

st.warning("queriesとsave_pathは適宜変更してください。")
st.warning("results_per_pageとmax_pages_per_queryも適宜変更してください。")
# ToDo: 修正したCSVファイルをAPIに送ってフォーマット修正する
# 一旦、「え」をすすめる
# queries = '仕事 "聞き間違い"'
# save_path = "/home/kishiyamat/mishearing-corpus/data/mishearing/google_search_shigoto_kikimachigai"
queries = '"聞きまつがい" site:https://www.1101.com/'
save_path = "/home/kishiyamat/mishearing-corpus/data/mishearing/googole_1101_kikimatsugai"
results_per_page = 20
max_pages_per_query = 30
# 設定をwrite
st.write(f"queries: `{queries}`")
st.write(f"save_path: `{save_path}`")
st.write(f"results_per_page: `{results_per_page}`")
st.write(f"max_pages_per_query: `{max_pages_per_query}`")


if not queries:
    st.warning("Please enter a query to run the Apify Actor.")
    st.stop()  # Stop further execution if no query is provided

if "response_json_pages" not in st.session_state:
    st.session_state["response_json_pages"] = []

st.write("### Google Search Scraperを実行")

if st.button("Run Apify Actor (Google)") or st.session_state["response_json_pages"] == []:
    st.session_state["response_json_pages"] = google_search(queries=queries, results_per_page=results_per_page, max_pages_per_query=max_pages_per_query)

organic_results = []
for p in st.session_state["response_json_pages"]:
    organic_results.extend(p["organicResults"])

st.write(f"queries: `{queries}`で取得したページ数: {len(organic_results)}")

import html
from html.parser import HTMLParser
from io import StringIO
import re

class TextExtractor(HTMLParser):
    """<script><style> を除外し、段落系タグで改行を入れる簡易パーサ"""
    _BREAK_TAGS = {"p", "br", "div", "li", "tr"}

    def __init__(self):
        super().__init__()
        self._buf = StringIO()
        self._skip = False           # script/style 内フラグ

    # --- タグ処理 ---
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        if tag in self._BREAK_TAGS:
            self._buf.write("\n")

    # --- テキストノード ---
    def handle_data(self, data):
        if not self._skip:
            self._buf.write(data)

    def text(self):
        return self._buf.getvalue()

def html_to_text(raw_html: str) -> str:
    """HTML 文字列 → プレーンテキスト"""
    parser = TextExtractor()
    parser.feed(raw_html)
    text = html.unescape(parser.text())              # &nbsp; 等をデコード
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)                     # 連続空白 → 1
    text = re.sub(r"(?:\s*\n\s*){3,}", "\n\n", text)        # 3 行以上 → 2 行
    return text.strip()


try:
    i = 6
    url = organic_results[i]["url"]
    st.write(f"Fetching content from: {url}")
    response = requests.get(url)
    response.encoding = response.apparent_encoding  # Set encoding based on response content
    fetched_text = response.text
    st.write("Fetched content:")
    st.text_area("Content", fetched_text, height=300)
    fetched_txt = html_to_text(fetched_text)
    st.text_area("Content", fetched_txt, height=300)


except Exception as e:
    st.error(f"Failed to fetch the URL content: {e}")