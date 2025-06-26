# app.py
from __future__ import annotations
import os, glob, pandas as pd, streamlit as st
import pathlib

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

# ───────────────────────── I/O helpers ───────────────────────── #
@st.cache_data(show_spinner=False)
def load_csv_tree(*args, **kwargs):
    return _load_csv_tree(*args, **kwargs)

def _load_csv_tree(root: str, *, exclude: str | None = None) -> pd.DataFrame:
    pat = os.path.join(root, "**/*.csv")
    files = [f for f in glob.glob(pat, recursive=True) if not exclude or exclude not in f]
    dataframes = []
    for f in files:
        # 問題があるファイルはファイル名を出力
        try:
            df = pd.read_csv(f)
            df["path"] = f  # Add a column with the file path
            dataframes.append(df)
        except:
            st.error(f"Error reading {f}. Please check the file format.")
            st.stop()
    return pd.concat(dataframes, ignore_index=True)

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
        self.mishear_root = f"{self.ROOT}/mishearing"

        self.tag_trans = load_translation(tag_root)
        self.env_trans = load_translation(env_root)

        self.tag_link = load_csv_tree(tag_root, exclude="translation.csv")
        self.env_link = load_csv_tree(env_root, exclude="translation.csv")
        self.corpus   = load_csv_tree(self.mishear_root)

        # Pre-compute counts
        self.tag_counts = self.tag_link["TagID"].value_counts()
        self.env_counts = self.env_link["EnvID"].value_counts()

    @property
    def urls(self) -> set[str]:
        """
        Returns a dictionary of URLs for the tag and environment links.
        キャッシュを使わずに常に最新のURLのセットを取得する。
        """
        return set(_load_csv_tree(self.mishear_root).URL)

    # ------------- UI ------------ #
    def form(self):
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
        submitted, lang, p_tag_lbl, tag_logic, p_env_lbl, env_logic = self.form()
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

    def check(self):
        # MishearIDが2つ以上の行を抽出
        dup_ids = self.corpus["MishearID"].value_counts()
        dup_ids = dup_ids[dup_ids > 1].index.tolist()
        if dup_ids:
            dup_paths = self.corpus[self.corpus["MishearID"].isin(dup_ids)][["MishearID", "path"]]
            st.warning("Duplicate MishearIDs found:")
            st.dataframe(dup_paths)

# ──────────────────────────── Bootstrap ────────────────────────── #

def main():
    st.title("Mishearing Corpus Viewer")
    MishearingApp().check()
    MishearingApp().run()

st.set_page_config(page_title="Mishearing Corpus")

main_tab, stats_tab, progress_tab = st.tabs(["main", "stats", "progress"])

with main_tab:
    main()

with stats_tab:
    df = MishearingApp().corpus
    df["dir"] = df["path"].apply(extract_dir)
    counts = df["dir"].value_counts(dropna=False).reset_index()
    counts.columns = ["Directory", "Count"]
    total = len(df)

    # ─── 表示 ──────────────────────────────────────────
    st.subheader("ディレクトリ別件数")
    st.dataframe(counts)

    st.subheader("合計")
    st.metric(label="総件数", value=total)

import subprocess
import shlex
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from pathlib import Path
from datetime import datetime, timezone
import csv, git

def show_history():
    st.subheader("Corpus 行数の推移（Git 履歴から自動取得）")
    repo = git.Repo(Path(__file__).resolve().parent)
    records = []

    for c in repo.iter_commits(paths="data/mishearing"):
        ts = datetime.fromtimestamp(c.committed_date, tz=timezone.utc).isoformat()
        total = 0
        for b in c.tree.traverse():
            p = b.path
            if p.startswith("data/mishearing/") and p.endswith(".csv"):
                rows = b.data_stream.read().decode("utf-8", "ignore").splitlines()
                total += max(len(rows) - 1, 0)      # ヘッダーを除外
        records.append({
            "commit": c.hexsha,
            "timestamp": ts,
            "rows": total
        })

    df = pd.DataFrame(records)

    # ① タイムスタンプを日付（00:00 UTC）に丸める
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["date"] = df["timestamp"].dt.normalize()

    # ② 同一日の中で最後（= 行数が最新）のレコードを残す
    daily = (
        df.sort_values("timestamp")
        .groupby("date", as_index=False)
        .last()                     # 最後の commit が残る
        .set_index("date")
    )

    # ③ 欠損日のインデックスを補完
    full_idx = pd.date_range(
        start=daily.index.min(),
        end=daily.index.max(),
        freq="D",
        tz="UTC"
    )
    daily = daily.reindex(full_idx)

    # ④ rows と commit を前方埋め
    daily["rows"] = daily["rows"].ffill()
    # ⑤ Streamlit で利用
    st.line_chart(daily["rows"])
    st.dataframe(daily.reset_index(names="date"))

with progress_tab:
    show_history()
