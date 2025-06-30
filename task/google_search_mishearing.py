import pandas as pd
import streamlit as st
import requests
from io import StringIO
import json
from pathlib import Path
from joblib import Memory

# parent directoryもpathに追加
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import MishearingApp

# TODO
# 1. 以下のEndpointが機能しているか確かめる
# 2. Rerunしたときでも再度おなじURLを検索しないよう修正
GOOGLE_SEARCH_ENDPOINT = "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items"
MISHEARING_SCRAPE_AND_SAVER_ENDPOINT = "http://127.0.0.1:7860/api/v1/run/cbda4a09-af9d-41b7-8376-232e50b75e3f"  # The complete API endpoint URL for this flow
API_URL_CATEGORIZE_CSV_ENDPOINT = "http://localhost:7860/api/v1/run/8e66efed-1840-42e0-9778-9ced64bf978d"
API_URL_FIX_CSV_ENDPOINT = "http://127.0.0.1:7860/api/v1/run/688463f5-255f-4368-88f9-e3fb5ed17a50"
URL_SET = set(MishearingApp().urls)


# 1. Google Search
memory = Memory(location=Path(".cache"), verbose=0)

@memory.cache
def google_search(
    queries: str,
    results_per_page: int,
    max_pages_per_query: int,
):
    payload = {
        "queries": queries,
        "resultsPerPage": results_per_page,
        "maxPagesPerQuery": max_pages_per_query,
        "countryCode": "jp",
        "searchLanguage": "ja",
        "languageCode": "ja"
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f'Bearer {st.secrets["apify"]["token"]}'
    }
    try:
        # Send API request
        response = requests.request("POST", GOOGLE_SEARCH_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes

        # Print response
        try:
            response_text = response.text  # Get response text
            response_json_pages = json.loads(response_text)  # Parse text as JSON
            return response_json_pages
        except json.JSONDecodeError as e:
            st.error(f"Error parsing response text as JSON: {e}")

    except requests.exceptions.RequestException as e:
        st.error(f"Error making API request: {e}")
    except ValueError as e:
        st.error(f"Error parsing response: {e}")

st.write("## 異聴データ収集 (Google Search Scraper)")

"""
手続き

1. 検索するクエリを決める
1. クエリに基づいて、保存するディレクトリの名前を決める
1. ApifyのGoogle Search Scraperを実行して、検索結果を取得
1. 取得した検索結果のURLを使って、mishearing-scrapeを実行
1. 保存された結果のCSVを手動で確認、分類
    1. not_relevant
    2. relevant
1. 修正したCSVをAPIに送ってフォーマット修正する

改善点
- descriptionを取得してXなどの際でも推定できるようにした
- 取得の過程をrequestsベースで行わせた
- プロセスを一つのファイルにまとめた
- ValidationはできるだけCSVを作成するタイミングで行った
"""

st.write("### クエリと保存ディレクトリの設定")

st.warning("queriesとsave_pathは適宜変更してください。")
st.warning("results_per_pageとmax_pages_per_queryも適宜変更してください。")
# ToDo: 修正したCSVファイルをAPIに送ってフォーマット修正する
# 一旦、「え」をすすめる
queries = '仕事 "聞き間違い"'
save_path = "/home/kishiyamat/mishearing-corpus/data/mishearing/google_search_shigoto_kikimachigai"
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
# st.write(organic_results)

def mishearing_scrape_and_save(target_url, description, save_path):
    input_str = json.dumps({"url": target_url, "description": description, "save_dir": save_path}, ensure_ascii=False)
    st.write(input_str)
    payload = {
        "input_value": input_str,  # The input value to be processed by the flow
        "output_type": "chat",  # Specifies the expected output format
        "input_type": "text"  # Specifies the input format
    }
    headers = { "Content-Type": "application/json" }

    try:
        response = requests.request("POST", MISHEARING_SCRAPE_AND_SAVER_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes

        try:
            response_text = response.text  # Get response text
            response_json = json.loads(response_text)  # Parse text as JSON
            return response_json  # Display the JSON in a formatted way
        except json.JSONDecodeError as e:
            st.error(f"Error parsing response text as JSON: {e}")

    except requests.exceptions.RequestException as e:
        st.error(f"Error making API request: {e}")
    except ValueError as e:
        st.error(f"Error parsing response: {e}")

st.write("### Scrape URLs from Search Results")

if st.button("Run Scrape and Save"):
    for result in organic_results:
        url_tgt = result.get("url")
        description_tgt = result.get("description")
        if url_tgt in URL_SET:
            st.warning(f"URL `{url_tgt}` はすでに存在します。スキップします。")
            continue
        try:
            st.write(f"Scraping URL: {url_tgt}")
            json_out = mishearing_scrape_and_save(url_tgt, description_tgt, save_path)
            json_out = json.loads(json_out["outputs"][0]["outputs"][0]["outputs"]["message"]["message"] )
            st.json(json_out)  # Assuming the output is in this format
            st.write(json_out[0]["URL"])  # かならず1件はあるはずなので、最初の要素を表示
        except Exception as e:
            st.error(f"Error processing URL `{url_tgt}`: {e}")

st.write("### RelevantとNot Relevantの分類")

st.info("not_relevantとrelevantディレクトリを作成して分類します。")
save_path = save_path
save_dir_relevant =  "relevant"
save_dir_not_relevant =  "not_relevant"
save_dir_maybe_relevant =  "maybe_relevant" # maybeも
# 設定をwrite
st.write(f"save_path: `{save_path}`")
st.write(f"save_dir_relevant: `{save_dir_relevant}`")
st.write(f"save_dir_not_relevant: `{save_dir_not_relevant}`")
st.write(f"save_dir_maybe_relevant: `{save_dir_maybe_relevant}`")

files_tobe_cat = st.file_uploader(
    "分類するCSV を選択（複数可）", type="csv", accept_multiple_files=True
)

# ▼ 2. 「送信」ボタンを押すまで処理を待機
# 行数が同じことは保証したい。
if files_tobe_cat and st.button("分類を送信"):
    st.write("送信中...")
    for f in files_tobe_cat:
        st.write(f)

        # 2-A. ファイル内容を文字列として取得
        csvStringIO = StringIO(f.getvalue().decode("utf-8"))
        df = pd.read_csv(csvStringIO, sep=",", header=0)
        original_nrow = len(df)
        st.write(df)

        def is_vacant(x):
            return pd.isna(x) or x == "" or x == "nan"

        # f"{save_path}/{save_dir_fixed}/{f.name}")が存在するならcontinue
        if any(Path(f"{save_path}/{dir}/{f.name}").exists() for dir in [save_dir_relevant, save_dir_not_relevant, save_dir_maybe_relevant]):
            st.warning(f"{f.name} はすでに存在します。スキップします。")
            continue

        # 2-C. JSON 文字列を作成
        payload_input = {
            "save_path": save_path,
            "dir_relevant": save_dir_relevant,
            "dir_not_relevant": save_dir_not_relevant,
            "dir_maybe_relevant": save_dir_maybe_relevant,
            "csv_name": f.name,
            "json_text": df.to_json(orient="records", force_ascii=False),
        }
        payload_input_str = json.dumps(payload_input, ensure_ascii=False)
        st.code(payload_input_str, language="json")
        payload = {
            "input_value": payload_input_str,  # The input value to be processed by the flow
            "output_type": "chat",  # Specifies the expected output format
            "input_type": "text"  # Specifies the input format
        }
        # Request headers
        headers = {
            "Content-Type": "application/json"
        }
        # 2-E. API へ POST
        try:
            r = requests.request("POST", API_URL_CATEGORIZE_CSV_ENDPOINT, json=payload, headers=headers)
            r.raise_for_status()
        except requests.RequestException as e:
            st.error(f"API Error: {e}")
            continue  # エラーが出ても次のファイルへ進む

st.write("### 修正したCSVファイルをAPIに送ってフォーマット修正する")
# ▼ 1. 複数ファイルを受け取る
save_path = save_path + "/relevant"
save_dir_fixed =  "fixed"
save_dir_envs =  "envs"
save_dir_tags =  "tags"
# 設定をwrite
st.write(f"save_path: `{save_path}`")
st.write(f"save_dir_fixed: `{save_dir_fixed}`")
st.write(f"save_dir_envs: `{save_dir_envs}`")
st.write(f"save_dir_tags: `{save_dir_tags}`")

files = st.file_uploader(
    "CSV を選択（複数可）", type="csv", accept_multiple_files=True
)

# ▼ 2. 「送信」ボタンを押すまで処理を待機
# 行数が同じことは保証したい。
if files and st.button("送信"):
    st.write("送信中...")
    for f in files:
        st.write(f)

        # 2-A. ファイル内容を文字列として取得
        csvStringIO = StringIO(f.getvalue().decode("utf-8"))
        df = pd.read_csv(csvStringIO, sep=",", header=0)
        original_nrow = len(df)
        st.write(df)
        st.write(df["Tags"].values[0])
        st.write(df["Envs"].values[0])

        def is_vacant(x):
            return pd.isna(x) or x == "" or x == "nan"

        # f"{save_path}/{save_dir_fixed}/{f.name}")が存在するならcontinue
        if Path(f"{save_path}/{save_dir_fixed}/{f.name}").exists():
            st.warning(f"{f.name} はすでに存在します。スキップします。")
            st.write(pd.read_csv(f"{save_path}/{save_dir_fixed}/{f.name}"))
            if  not is_vacant(df["Tags"].values[0]):
                st.write(pd.read_csv(f"{save_path}/{save_dir_tags}/{f.name}"))
            if  not is_vacant(df["Envs"].values[0]):
                st.write(pd.read_csv(f"{save_path}/{save_dir_envs}/{f.name}"))
            continue


        # 2-C. JSON 文字列を作成
        payload_input = {
            "save_path": save_path,
            "fixed_dir": save_dir_fixed,
            "envs_dir": save_dir_envs,
            "tags_dir": save_dir_tags,
            "csv_name": f.name,
            "json_text": df.to_json(orient="records", force_ascii=False),
        }
        payload_input_str = json.dumps(payload_input, ensure_ascii=False)
        payload = {
            "input_value": payload_input_str,  # The input value to be processed by the flow
            "output_type": "chat",  # Specifies the expected output format
            "input_type": "text"  # Specifies the input format
        }
        # Request headers
        headers = {
            "Content-Type": "application/json"
        }

        # 2-D. 送信内容を画面に表示（デバッグ用）
        st.code(payload_input_str, language="json")

        # 2-E. API へ POST
        try:
            r = requests.request("POST", API_URL_FIX_CSV_ENDPOINT, json=payload, headers=headers)
            r.raise_for_status()
        except requests.RequestException as e:
            st.error(f"API Error: {e}")
            continue  # エラーが出ても次のファイルへ進む

        new_df = pd.read_csv(f"{save_path}/{save_dir_fixed}/{f.name}")
        st.write(new_df)
        st.write(pd.read_csv(f"{save_path}/{save_dir_envs}/{f.name}"))
        st.write(pd.read_csv(f"{save_path}/{save_dir_tags}/{f.name}"))
        assert original_nrow==len(new_df)
        # ここで出力のファイルの正しさを保証
        # 2-F. 結果を表示
        st.success(f"{f.name} → 成功")
        st.json(r.json())