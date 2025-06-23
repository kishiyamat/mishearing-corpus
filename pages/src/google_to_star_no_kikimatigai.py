from joblib import Memory
from pathlib import Path
import streamlit as st
from apify_client import ApifyClient
# キャッシュを置く場所をプロジェクト直下 .cache/ に設定
memory = Memory(location=Path(".cache"), verbose=0)
import json

import requests

@memory.cache                        # ← st.cache_resource を置き換え
def run_apify_actor(
    queries: str,
    results_per_page: int,
    max_pages_per_query: int,
):
    """Apify Google Search Scraper を実行し、結果を joblib でキャッシュする"""
    # 日付とかも本当はキャッシュしたほうが良い.

    client = ApifyClient(
        st.secrets["apify"]["token"],
        max_retries = 10,
        min_delay_between_retries_millis = 2000,
        timeout_secs = 360,
    )

    run_input = {
        "queries": queries,
        "resultsPerPage": results_per_page,
        "maxPagesPerQuery": max_pages_per_query,
        "countryCode": "jp",
        "languageCode": "ja",
        "forceExactMatch": True,
    }

    # Actor 実行
    run = client.actor("apify/google-search-scraper").call(run_input=run_input, wait_secs=360)

    # データセット取得
    dataset = client.dataset(run["defaultDatasetId"])

    # Apify の Dataset オブジェクトそのままではシリアライズできない
    # list_items() で JSON 互換のリストに変換してから返す
    return list(dataset.iterate_items())


@st.cache_data(show_spinner=False)
def scrape(target_url, save_path):
    input_str = json.dumps({"url": target_url, "save_dir": save_path})
    st.write(input_str)
    url = "http://127.0.0.1:7860/api/v1/run/cbda4a09-af9d-41b7-8376-232e50b75e3f"  # The complete API endpoint URL for this flow
    # Request payload configuration
    payload = {
        "input_value": input_str,  # The input value to be processed by the flow
        "output_type": "chat",  # Specifies the expected output format
        "input_type": "text"  # Specifies the input format
    }

    # Request headers
    headers = {
        "Content-Type": "application/json"
    }

    try:
        # Send API request
        response = requests.request("POST", url, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes

        # Print response
        try:
            response_text = response.text  # Get response text
            response_json = json.loads(response_text)  # Parse text as JSON
            st.json(response_json)  # Display the JSON in a formatted way
        except json.JSONDecodeError as e:
            st.error(f"Error parsing response text as JSON: {e}")

    except requests.exceptions.RequestException as e:
        st.error(f"Error making API request: {e}")
    except ValueError as e:
        st.error(f"Error parsing response: {e}")


def extract_dir(path_str: str) -> str:
    """
    data/mishearing/<DIR_NAME>/file.csv から <DIR_NAME> を取り出す。
    想定外の形式なら空文字を返す。
    """
    try:
        parts = pathlib.Path(path_str).parts
        # parts = ('data', 'mishearing', '<DIR_NAME>', 'YYYY-MM-DD_xxx.csv')
        return parts[2] if len(parts) >= 3 else ""
    except Exception:
        return ""