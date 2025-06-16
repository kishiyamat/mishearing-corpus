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
m, s = st.tabs(["main", "scraping"])

with m:
    main()

import requests
import json

def scrape():
    # Scrapeの対象のURL
    target_url = st.text_input("URL: ")

    url = "http://127.0.0.1:7860/api/v1/run/cbda4a09-af9d-41b7-8376-232e50b75e3f"  # The complete API endpoint URL for this flow
    # Request payload configuration
    payload = {
        "input_value": target_url,  # The input value to be processed by the flow
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
        

with s:
    scrape()
