# app.py
from __future__ import annotations
import os, glob, pandas as pd, streamlit as st

# ───────────────────────── I/O helpers ───────────────────────── #
@st.cache_data(show_spinner=False)
def load_csv_tree(root: str, *, exclude: str | None = None) -> pd.DataFrame:
    pat = os.path.join(root, "**/*.csv")
    files = [f for f in glob.glob(pat, recursive=True) if not exclude or exclude not in f]
    return pd.concat((pd.read_csv(f) for f in files), ignore_index=True)

@st.cache_data(show_spinner=False)
def load_translation(root: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(root, "translation.csv"))

def id_to_label(ids, trans_df, lang):
    mapping = (
        trans_df.loc[trans_df["Lang"] == lang]
        .set_index(trans_df.columns[0])["Label"]
        .to_dict()
    )
    return [mapping.get(i, i) for i in ids]

def label_to_id(labels, trans_df, lang):
    mapping = (
        trans_df.loc[trans_df["Lang"] == lang]
        .set_index("Label")[trans_df.columns[0]]
        .to_dict()
    )
    return [mapping[lbl] for lbl in labels if lbl in mapping]

def make_mask(link_df, key_col, picked_ids, logic) -> set[str]:
    """
    Generate a set of IDs based on filtering logic applied to a DataFrame.

    Args:
        link_df (pd.DataFrame): The input DataFrame containing the data to filter.
        key_col (str): The column name in the DataFrame to apply the filtering logic on.
        picked_ids (Iterable): A collection of IDs to filter against.
        logic (str): A string specifying the filtering logic. If it starts with "すべて",
                     the function checks if all `picked_ids` are a subset of the values
                     in `key_col` grouped by "MishearID". Otherwise, it filters rows
                     where `key_col` contains any of the `picked_ids`.

    Returns:
        set[str]: A set of "MishearID" values that match the filtering criteria.
    """
    if not picked_ids:
        return set(link_df["MishearID"])
    if logic.startswith("すべて"):
        # FIXME: 「すべて」というのはradioに依存している
        ok = link_df.groupby("MishearID")[key_col].apply(lambda s: set(picked_ids).issubset(s))
        return set(ok[ok].index)
    return set(link_df[link_df[key_col].isin(picked_ids)]["MishearID"])


# ──────────────────────── Core application class ─────────────────────── #
class MishearingApp:
    ROOT = "data"

    def __init__(self):
        tag_root = f"{self.ROOT}/tag"
        env_root = f"{self.ROOT}/environment"
        mishear_root = f"{self.ROOT}/mishearing"

        self.tag_trans = load_translation(tag_root)
        self.env_trans = load_translation(env_root)

        self.tag_link = load_csv_tree(tag_root, exclude="translation.csv")
        self.env_link = load_csv_tree(env_root, exclude="translation.csv")
        self.corpus   = load_csv_tree(mishear_root)

        # Pre-compute counts
        self.tag_counts = self.tag_link["TagID"].value_counts()
        self.env_counts = self.env_link["EnvID"].value_counts()

    # ------------- UI ------------ #
    def sidebar_form(self):
        with st.sidebar:
            st.title("🔍 Filter")
            lang = st.radio("Language", ("en", "ja"), horizontal=True, index=1)
            with st.form(key="filter_form"):
                tag_lbls = id_to_label(self.tag_counts.index, self.tag_trans, lang)
                env_lbls = id_to_label(self.env_counts.index, self.env_trans, lang)

                picked_tags = st.multiselect("Tags", tag_lbls)
                tag_logic   = st.radio("Tag rule", ["すべて含む (AND)", "いずれか含む (OR)"])

                picked_envs = st.multiselect("Environments", env_lbls)
                env_logic   = st.radio("Env rule", ["すべて含む (AND)", "いずれか含む (OR)"])

                submitted = st.form_submit_button("Apply filters")

            return submitted, lang, picked_tags, tag_logic, picked_envs, env_logic

    def run(self):
        submitted, lang, p_tag_lbl, tag_logic, p_env_lbl, env_logic = self.sidebar_form()
        if not submitted:
            st.info("左のサイドバーでフィルタを選んで **Apply filters** を押してください。")
            return

        # --- translate back to IDs --- #
        p_tag_ids = label_to_id(p_tag_lbl, self.tag_trans, lang)
        p_env_ids = label_to_id(p_env_lbl, self.env_trans, lang)

        keep_tag = make_mask(self.tag_link, "TagID", p_tag_ids, tag_logic)
        keep_env = make_mask(self.env_link, "EnvID", p_env_ids, env_logic)
        final_ids = keep_tag & keep_env

        # --- main pane --- #
        st.header(f"Results – {len(final_ids)} rows")
        st.dataframe(self.corpus[self.corpus["MishearID"].isin(final_ids)])

# ──────────────────────────── Bootstrap ────────────────────────── #

def main():
    st.title("Mishearing Corpus Viewer")
    MishearingApp().run()

st.set_page_config(page_title="Mishearing Corpus", layout="wide")
main_tab, google_tab, scraping_tab, loop_tab, fix_csv_tab = st.tabs(["main", "google", "scraping", "loop", "fix_csv"])

with main_tab:
    main()

import requests
import json


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
    

with scraping_tab:
    # Scrapeの対象のURL
    target_url = st.text_input("URL: ", "https://note.com/imominty/n/ne9a96dee1118")
    save_path = st.text_input("base path: ", "/home/kishiyamat/mishearing-corpus/directory")
    if not (target_url and save_path):
        st.warning("Please enter a URL to scrape and Directory to save it to.")
    else:
        if st.button("Save CSV"):
            scrape(target_url, save_path)


from apify_client import ApifyClient

# ─── joblib 導入 ─────────────────────────────────────────────
from pathlib import Path
from joblib import Memory
from apify_client import ApifyClient
import streamlit as st

# キャッシュを置く場所をプロジェクト直下 .cache/ に設定
memory = Memory(location=Path(".cache"), verbose=0)

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


with google_tab:
    st.write("This tab is for Apify integration. Currently, it is not implemented.")
    queries = st.text_input("Google Search Query", '"と*の聞き間違"')
    results_per_page = st.number_input("results_per_page", 10)
    max_pages_per_query = st.number_input("max_pages_per_query (1しか動かない)",1)
    if not queries:
        st.warning("Please enter a query to run the Apify Actor.")
    else: 
        if st.button("Run Apify Actor"):
            # Initialize the ApifyClient with your Apify API token
            # Replace '<YOUR_API_TOKEN>' with your token.
            run_input = {
                "queries": queries,
                "results_per_page": results_per_page,
                "max_pages_per_query": max_pages_per_query,
            }
            dataset = run_apify_actor(**run_input)
            items = []
            for item in dataset:
                items.extend(item["organicResults"]) 
            st.write(len(items))
            # You can add your Apify-related code here if needed.
            # organicResults に検索結果が入っているので、そこから必要な情報を抽出して表示することができます。

with loop_tab:
    st.write("This tab is for Apify integration. Currently, it is not implemented.")
    queries = st.text_input("Query to apply loop")
    save_path = st.text_input("base path (Loop): ", "/home/kishiyamat/mishearing-corpus/directory")
    results_per_page = st.number_input("results_per_page (loop)", 10)
    max_pages_per_query = st.number_input("max_pages_per_query (loop)",1)
    if not queries:
        st.warning("Please enter a query to run the Apify Actor.")
    else: 
        if st.button("Run Apify Actor Loop"):
            # Initialize the ApifyClient with your Apify API token
            # Replace '<YOUR_API_TOKEN>' with your token.
            run_input = {
                "queries": queries,
                "results_per_page": results_per_page,
                "max_pages_per_query": max_pages_per_query,
            }
            dataset = run_apify_actor(**run_input)
            for item in dataset:
                for organic_result in item["organicResults"]:
                    st.write(organic_result["url"])
                    scrape(organic_result["url"], save_path)
            # You can add your Apify-related code here if needed.
            # organicResults に検索結果が入っているので、そこから必要な情報を抽出して表示することができます。

# fix_csv_tab.py
import json
from pathlib import Path

import requests
import streamlit as st

API_URL_FIX_CSV = (
    "http://127.0.0.1:7860/api/v1/run/"
    "688463f5-255f-4368-88f9-e3fb5ed17a50"
)

import pandas as pd

from io import StringIO

with fix_csv_tab:
    """複数 CSV を API に送るメイン処理"""
    st.header("CSV ファイルを修正して API へ送信")
    # ▼ 1. 複数ファイルを受け取る
    save_path = st.text_input("Path where files to be fixed exist")
    save_dir_fixed = st.text_input("Path where fixed files to be fixed exist")
    save_dir_envs = st.text_input("Path where envs files to be fixed exist")
    save_dir_tags = st.text_input("Path where tags files to be fixed exist")
    files = st.file_uploader(
        "CSV を選択（複数可）", type="csv", accept_multiple_files=True
    )

    # ▼ 2. 「送信」ボタンを押すまで処理を待機
    # 行数が同じことは保証したい。
    if files and st.button("送信"):
        for f in files:
            st.write(f)
            # 2-A. ファイル内容を文字列として取得
            csv_text = f.getvalue().decode("utf-8")

            csvStringIO = StringIO(csv_text)
            df = pd.read_csv(csvStringIO, sep=",", header=0)
            original_nrow = len(df)
            st.write(df)

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
                r = requests.request("POST", API_URL_FIX_CSV, json=payload, headers=headers)
                r.raise_for_status()
            except requests.RequestException as e:
                st.error(f"API Error: {e}")
                continue  # エラーが出ても次のファイルへ進む

            new_df = pd.read_csv(f"{save_path}/{save_dir_fixed}/{f.name}")
            st.write(new_df)
            assert original_nrow==len(new_df)
            # ここで出力のファイルの正しさを保証
            # 2-F. 結果を表示
            st.success(f"{f.name} → 成功")
            st.json(r.json())
