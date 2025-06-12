# streamlit_app.py
from __future__ import annotations
import os
import glob
import pandas as pd
import streamlit as st

# ──────────────────────────────── I / O  ──────────────────────────────── #
@st.cache_data(show_spinner=False)
def load_csv_tree(root: str, *, exclude: str | None = None) -> pd.DataFrame:
    """Recursively load every CSV under *root* (optionally excluding *exclude*)."""
    pattern = os.path.join(root, "**/*.csv")
    files = [
        f for f in glob.glob(pattern, recursive=True)
        if not exclude or exclude not in f
    ]
    return pd.concat((pd.read_csv(f) for f in files), ignore_index=True)

@st.cache_data(show_spinner=False)
def load_translation(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

# ──────────────────────── Translation helpers ─────────────────────────── #
# ── helpers.py ──────────────────────────────────────────────────────────
def id_to_label(ids, trans_df: pd.DataFrame, lang: str):
    """TagID / EnvID → 表示ラベル"""
    mapping = (
        trans_df
        .loc[trans_df["Lang"] == lang]
        .set_index(trans_df.columns[0])["Label"]
        .to_dict()
    )
    return [mapping.get(i, i) for i in ids]          # fallback = 原値


def label_to_id(labels, trans_df: pd.DataFrame, lang: str | None = None):
    """ラベル → TagID / EnvID  
       lang を渡せばその言語だけ、None なら全体から検索
    """
    df = trans_df if lang is None else trans_df.loc[trans_df["Lang"] == lang]
    mapping = df.set_index("Label")[df.columns[0]].to_dict()
    return [mapping[lbl] for lbl in labels if lbl in mapping]


# ────────────────────────── Filtering logic ───────────────────────────── #
def make_mask(link_df, key_col, picked_ids, logic: str) -> set[str]:
    """Return a set of MishearIDs that match *picked_ids* under *logic*."""
    if not picked_ids:        # nothing picked → allow everything
        return set(link_df["MishearID"].unique())

    if logic == "すべて含む (AND)":
        ok = (
            link_df.groupby("MishearID")[key_col]
            .apply(lambda s: set(picked_ids).issubset(s))
        )
        return set(ok[ok].index)
    # OR
    return set(link_df[link_df[key_col].isin(picked_ids)]["MishearID"].unique())


# ──────────────────────────────── UI  ─────────────────────────────────── #
def main():
    # ---------- Paths ----------
    ROOT_DATA = "data"
    mishear_path = f"{ROOT_DATA}/mishearing"
    tag_root = f"{ROOT_DATA}/tag"
    env_root = f"{ROOT_DATA}/environment"

    tag_trans = load_translation(f"{tag_root}/translation.csv")
    env_trans = load_translation(f"{env_root}/translation.csv")

    tag_link = load_csv_tree(tag_root, exclude="translation.csv")   # TagID, MishearID
    env_link = load_csv_tree(env_root, exclude="translation.csv")   # EnvID, MishearID
    corpus   = load_csv_tree(mishear_path)                          # Mishearing corpus

    # ---------- Language ----------
    lang = st.radio("Language", ("en", "ja"), horizontal=True, index=1)

    # ---------- Tag & Env selectors ----------
    tag_counts = tag_link["TagID"].value_counts()
    env_counts = env_link["EnvID"].value_counts()

    tag_labels = id_to_label(tag_counts.index, tag_trans, lang)
    env_labels = id_to_label(env_counts.index, env_trans, lang)

    st.header("Query by Tags and Environments")
    st.markdown("Select tags and environments to filter the mishearing corpus.")

    picked_tag_lbls = st.multiselect("Tags", tag_labels)
    tag_logic = st.radio("Tag rule", ["すべて含む (AND)", "いずれか含む (OR)"])
    picked_tag_ids = label_to_id(picked_tag_lbls, tag_trans, lang)
    with st.expander("Tag counts", expanded=False):
        st.bar_chart(tag_counts.rename(index=dict(zip(tag_counts.index, tag_labels))))
    keep_by_tag = make_mask(tag_link, "TagID", picked_tag_ids, tag_logic)

    picked_env_lbls = st.multiselect("Environments", env_labels)
    env_logic = st.radio("Env rule", ["すべて含む (AND)", "いずれか含む (OR)"])
    picked_env_ids = label_to_id(picked_env_lbls, env_trans, lang)
    with st.expander("Environment counts", expanded=False):
        st.bar_chart(env_counts.rename(index=dict(zip(env_counts.index, env_labels))))
    keep_by_env = make_mask(env_link, "EnvID", picked_env_ids, env_logic)

    final_keep  = keep_by_tag & keep_by_env

    st.markdown(f"### Results – {len(final_keep)} rows")
    st.dataframe(corpus[corpus["MishearID"].isin(final_keep)])


st.set_page_config(page_title="Mishearing Corpus")
st.title("Mishearing Corpus Viewer")
main()
