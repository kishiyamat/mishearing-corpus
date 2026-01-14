# app.py
from datetime import datetime, timezone
import os, glob, pandas as pd, streamlit as st
import pathlib
import git
import difflib

# 言語別UIテキスト
UI_STR = {
    "ja": {
        "tags": "タグ",
        "tag_rule": "タグの条件",
        "tag_rule_opts": {"AND": "すべて含む (AND)", "OR": "いずれか含む (OR)"},
        "envs": "環境",
        "env_rule": "環境の条件",
        "env_rule_opts": {"AND": "すべて含む (AND)", "OR": "いずれか含む (OR)"},
        "apply_filters": "フィルタを適用",
        "diff_toggle": "差分を強調",
        "diff_slow_notice": "Diff を強調すると表示に時間がかかる場合があります。",
        "info_select_filters": "左のサイドバーでフィルタを選んで「フィルタを適用」を押してください。",
        "results": "結果 – {n} 件",
        "dup_warning": "重複した MishearID が見つかりました:",
        "help_title": "使い方",
        "help_usage": (
            "- タグ/環境を選び、AND/OR ルールを設定します（未選択は全件ヒット）。\n"
            "- 『フィルタを適用』を押して結果を更新します。\n"
            "- Results では『差分を強調』のトグルと『列の幅』ラジオ（small/medium/large, Src/Tgt 共通）を変更できます。\n"
            "- 差分強調は Src/Tgt の置換部分のみを **** で強調します（一部環境で表示が遅くなる場合がありますが、計算はキャッシュされます）。\n"
            "- 表では `Src`=話し手の意図、`Tgt`=聞き手の解釈 を示します。"
        ),
    "src_width_label": "Src列の幅",
    "tgt_width_label": "Tgt列の幅",
    "width_label": "列の幅",
        "width_help": "small / medium / large を選択",
        "stats_dir": "ディレクトリ別件数",
        "stats_total": "合計",
        "stats_total_metric": "総件数",
        "progress_header": "Corpus 行数の推移",
        "src_tgt_desc": "src は話し手が意図した言葉、tgt は聞き手の解釈です。",
    },
    "en": {
        "tags": "Tags",
        "tag_rule": "Tag rule",
        "tag_rule_opts": {"AND": "Must include all (AND)", "OR": "Include any (OR)"},
        "envs": "Environments",
        "env_rule": "Env rule",
        "env_rule_opts": {"AND": "Must include all (AND)", "OR": "Include any (OR)"},
        "apply_filters": "Apply filters",
        "diff_toggle": "Emphasize diff",
        "diff_slow_notice": "Enabling diff emphasis may slow down rendering.",
        "info_select_filters": "Select filters on the left and press Apply filters.",
        "results": "Results – {n} rows",
        "dup_warning": "Duplicate MishearIDs found:",
        "help_title": "How to use",
        "help_usage": (
            "- Pick Tags and Environments, then set the AND/OR rule (leaving them empty matches all rows).\n"
            "- Press Apply filters to update the results.\n"
            "- In Results you can toggle Emphasize diff and choose Column width (small/medium/large; common for Src/Tgt).\n"
            "- Diff highlights only replaced segments in Src/Tgt. It may be slower on big tables, but the computation is cached.\n"
            "- In the table, `Src` is the intended utterance; `Tgt` is the listener’s interpretation."
        ),
    "src_width_label": "Src width",
    "tgt_width_label": "Tgt width",
    "width_label": "Column width",
        "width_help": "Choose small / medium / large",
        "stats_dir": "Counts by directory",
        "stats_total": "Total",
        "stats_total_metric": "Total rows",
        "progress_header": "Corpus row count over time",
        "src_tgt_desc": "src is the intended word/utterance; tgt is the listener's interpretation.",
    },
}

from scripts.asa2025.extract_word_pairs import extract_word_mishear_pairs

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

def make_mask(link_df, key_col, picked_ids, logic_key) -> set[str]:
    """
    logic_key: "AND" or "OR"
    """
    if not picked_ids:
        return set(link_df["MishearID"])
    if logic_key == "AND":
        ok = link_df.groupby("MishearID")[key_col].apply(lambda s: set(picked_ids).issubset(s))
        return set(ok[ok].index)
    return set(link_df[link_df[key_col].isin(picked_ids)]["MishearID"])


@st.cache_resource(show_spinner=False)
def _mark_replace_only(src: str, tgt: str) -> tuple[str, str]:
    if pd.isna(src) or pd.isna(tgt):
        s0 = "" if pd.isna(src) else str(src).replace("\n", " ⏎ ")
        t0 = "" if pd.isna(tgt) else str(tgt).replace("\n", " ⏎ ")
        return s0, t0
    s, t = str(src), str(tgt)
    sm = difflib.SequenceMatcher(a=s, b=t)
    out_s, out_t = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out_s.append(s[i1:i2])
            out_t.append(t[j1:j2])
        elif tag == "replace":
            out_s.append(f" **{s[i1:i2]}** ")
            out_t.append(f" **{t[j1:j2]}** ")
        elif tag == "delete":
            out_s.append(s[i1:i2])
        elif tag == "insert":
            out_t.append(t[j1:j2])
    return "".join(out_s).replace("\n", " ⏎ "), "".join(out_t).replace("\n", " ⏎ ")

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
        lang_options = ["en", "ja", "zh", "ko"]
        lang_labels = {
            "en": "English",
            "ja": "日本語",
            "zh": "中文 (Not implemented)",
            "ko": "한국어 (Not implemented)",
        }
        lang = st.radio(
            "Language",
            options=lang_options,
            format_func=lambda x: lang_labels[x],
            index=1,
            horizontal=True,
        )
        if lang in ("zh", "ko"):
            st.warning("This language is not supported yet. Displaying in English.")
            lang = "en"

        # 現在の言語を共有
        st.session_state["lang"] = lang
        ui = UI_STR.get(lang, UI_STR["ja"])

        with st.form(key="filter_form"):
            # 使い方 (アプリ内ヘルプ) をフォーム内の先頭に配置
            with st.expander(ui.get("help_title", ""), expanded=True):
                st.markdown(ui.get("help_usage", ""))
            # Tag "mishearing" は選択肢から除外
            allowed_tag_ids = [tid for tid in self.tag_counts.index if str(tid) != "MISHEARING"]
            tag_lbls = id_to_label(allowed_tag_ids, self.tag_trans, lang)
            env_lbls = id_to_label(self.env_counts.index, self.env_trans, lang)

            picked_tags = st.multiselect(ui["tags"], tag_lbls)

            tag_logic_key = st.radio(
                ui["tag_rule"],
                options=["AND", "OR"],
                format_func=lambda k: ui["tag_rule_opts"][k],
                horizontal=True,
            )

            picked_envs = st.multiselect(ui["envs"], env_lbls)

            env_logic_key = st.radio(
                ui["env_rule"],
                options=["AND", "OR"],
                format_func=lambda k: ui["env_rule_opts"][k],
                horizontal=True,
            )

            # フィルタ適用ボタンのみ（差分/列幅は結果エリアで指定）
            submitted = st.form_submit_button(ui["apply_filters"])

        return submitted, lang, picked_tags, tag_logic_key, picked_envs, env_logic_key

    def run(self):
        submitted, lang, p_tag_lbl, tag_logic_key, p_env_lbl, env_logic_key = self.form()

        # フィルタの状態をセッションに保持（初回は適用ボタンが必要）
        if submitted:
            p_tag_ids = label_to_id(p_tag_lbl, self.tag_trans, lang)
            p_env_ids = label_to_id(p_env_lbl, self.env_trans, lang)
            st.session_state["filters"] = {
                "tag_ids": p_tag_ids,
                "env_ids": p_env_ids,
                "tag_logic": tag_logic_key,
                "env_logic": env_logic_key,
                "lang": lang,
            }

        filters = st.session_state.get("filters")
        if not filters:
            st.info(UI_STR.get(lang, UI_STR["ja"]) ["info_select_filters"])
            return

        # --- translate back to IDs (from stored filters) --- #
        p_tag_ids = filters["tag_ids"]
        p_env_ids = filters["env_ids"]
        keep_tag = make_mask(self.tag_link, "TagID", p_tag_ids, filters["tag_logic"])
        keep_env = make_mask(self.env_link, "EnvID", p_env_ids, filters["env_logic"])
        final_ids = keep_tag & keep_env

        # --- main pane --- #
        ui = UI_STR.get(st.session_state.get("lang", lang), UI_STR["ja"])
        st.header(ui["results"].format(n=len(final_ids)))
        # Show explanation of src/tgt
        if "src_tgt_desc" in ui:
            st.caption(ui["src_tgt_desc"])

        # 結果セクションの表示オプション（差分と列幅）

        col_opt1, col_opt2 = st.columns([1, 2])
        with col_opt1:
            # st.toggle が無い環境に配慮
            _toggle = getattr(st, "toggle", st.checkbox)
            emphasize_diff = _toggle(
                ui["diff_toggle"],
                help=ui["diff_slow_notice"],
                key="emphasize_diff",
            )
        width_opts = ["small", "medium", "large"]
        with col_opt2:
            col_width = st.radio(
                ui.get("width_label", "Column width"),
                options=width_opts,
                index=1,
                horizontal=True,
                key="col_width",
            )

        result_df = self.corpus[self.corpus["MishearID"].isin(final_ids)].copy()

        # 常に DataFrame を使用。Diff ON の場合のみ Src/Tgt テキストに ** を埋め込む
        src_width = col_width
        tgt_width = col_width
        if emphasize_diff:
            src_col, tgt_col = "Src", "Tgt"

            # 変換したテキストを反映
            marked_src = []
            marked_tgt = []
            for _, row in result_df[[src_col, tgt_col]].iterrows():
                s_mark, t_mark = _mark_replace_only(row[src_col], row[tgt_col])
                marked_src.append(s_mark)
                marked_tgt.append(t_mark)
            result_df[src_col] = marked_src
            result_df[tgt_col] = marked_tgt

            # Markdown として解釈してもらう（サポートが無い場合は自動フォールバック）
            src_cfg = st.column_config.TextColumn(width=src_width, help="Src")
            tgt_cfg = st.column_config.TextColumn(width=tgt_width, help="Tgt")
            st.dataframe(
                result_df,
                hide_index=True,
                use_container_width=True,
                column_config={src_col: src_cfg, tgt_col: tgt_cfg},
            )
        else:
            # Diff OFF 時も Src/Tgt の幅と折返しを指定
            cfg = {}
            cfg["Src"] = st.column_config.TextColumn(width=src_width, help="Src")
            cfg["Tgt"] = st.column_config.TextColumn(width=tgt_width, help="Tgt")
            st.dataframe(result_df, hide_index=True, use_container_width=True, column_config=cfg)

    def check(self):
        # MishearIDが2つ以上の行を抽出
        dup_ids = self.corpus["MishearID"].value_counts()
        dup_ids = dup_ids[dup_ids > 1].index.tolist()
        if dup_ids:
            dup_paths = self.corpus[self.corpus["MishearID"].isin(dup_ids)][["MishearID", "path"]]
            lang = st.session_state.get("lang", "ja")
            st.warning(UI_STR.get(lang, UI_STR["ja"])["dup_warning"])
            st.dataframe(dup_paths)

# ──────────────────────────── Bootstrap ───────────────────────── #

def main():
    st.title("Mishearing Corpus Viewer")
    MishearingApp().check()
    MishearingApp().run()

st.set_page_config(
    page_title="Mishearing Corpus",
    layout="wide",
    page_icon="📂",
)

main_tab, stats_tab, progress_tab, disclaimer_tab, extractor_tab = st.tabs(["Viewer", "Stats", "Progress", "Disclaimer", "Extractor"])

with main_tab:
    main()

with stats_tab:
    lang = st.session_state.get("lang", "ja")
    ui = UI_STR.get(lang, UI_STR["ja"])
    df = MishearingApp().corpus
    df["dir"] = df["path"].apply(extract_dir)
    counts = df["dir"].value_counts(dropna=False).reset_index()
    counts.columns = ["Directory", "Count"]
    total = len(df)

    # ─── 表示 ──────────────────────────────────────────
    st.subheader(ui["stats_dir"])
    st.dataframe(counts)

    st.subheader(ui["stats_total"])
    st.metric(label=ui["stats_total_metric"], value=total)


@st.cache_data(show_spinner="Git 履歴を解析中 …")
def build_history() -> pd.DataFrame:
    repo = git.Repo(pathlib.Path(__file__).resolve().parent)
    records = []

    # mishearing に変更があったコミットを走査
    for c in repo.iter_commits(paths="data/mishearing"):
        ts = datetime.fromtimestamp(c.committed_date, tz=timezone.utc)
        env_files, tag_files, mis_blobs = set(), set(), []

        # ツリーを一度だけ走査して 3 種のファイルを収集
        for b in c.tree.traverse():
            p = b.path
            if p.endswith(".csv"):
                name = pathlib.Path(p).name  # ファイル名のみ
                if p.startswith("data/environment/"):
                    env_files.add(name)
                elif p.startswith("data/tag/"):
                    tag_files.add(name)
                elif p.startswith("data/mishearing/"):
                    mis_blobs.append((name, b))  # 後で読むので blob も保持

        # 同名 CSV が三箇所すべてにある場合(データを適切に追加していenv, tagを生成した場合)だけカウント
        total = 0
        for name, blob in mis_blobs:
            if name in env_files and name in tag_files:
                rows = blob.data_stream.read().decode("utf-8", "ignore").splitlines()
                total += max(len(rows) - 1, 0)  # ヘッダー 1 行を除外

        if total:  # 行数 0 は除外
            records.append({"commit": c.hexsha[:7], "timestamp": ts, "rows": total})

    # DataFrame 化と日付補完
    df = pd.DataFrame(records).sort_values("timestamp")
    df["date"] = df["timestamp"].dt.normalize()

    daily = (
        df.groupby("date", as_index=False)
          .last()                                # 同日の最新コミットを採用
          .set_index("date")
    )

    full_idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D", tz="UTC")
    daily = (
        daily.reindex(full_idx)
             .ffill()                            # 前回値で埋める
    )
    return daily.reset_index(names="date")

with progress_tab:
    lang = st.session_state.get("lang", "ja")
    ui = UI_STR.get(lang, UI_STR["ja"])
    st.subheader(ui["progress_header"])
    daily = build_history()

    st.line_chart(daily.set_index("date")["rows"], height=300)
    st.dataframe(daily, height=250, hide_index=True)

with disclaimer_tab:
    # Language-aware disclaimer page
    lang = st.session_state.get("lang", "ja")
    if lang == "en":
        st.header("Disclaimer")
        st.subheader("Usage notes")
        st.markdown(
            "\n".join(
                [
                    "- This corpus is provided primarily for research and educational purposes.",
                    "- Listed URLs and external contents reflect the state at the time of collection and may have changed or been removed since then.",
                    "- Minor inconsistencies or errors may remain. Contributions and fixes are welcome — please use GitHub Issues.",
                ]
            )
        )
        st.subheader("Disclaimer of warranty and liability")
        st.markdown(
            "\n".join(
                [
                    "- The authors make no warranties regarding accuracy, completeness, or fitness for a particular purpose.",
                    "- The authors shall not be liable for any damages arising from the use of this corpus or viewer.",
                    "- Please comply with the terms of use and copyright laws of any referenced/linked sites when using the data.",
                ]
            )
        )
        st.subheader("Contact")
        st.markdown(
            "\n".join(
                [
                    "- For bug reports, improvement proposals, and questions, please open an Issue on GitHub.",
                    "- Issues: https://github.com/kishiyamat/mishearing-corpus/issues",
                ]
            )
        )
    else:
        st.header("免責事項 / 利用上の注意")
        st.subheader("利用上の注意")
        st.markdown(
            "\n".join(
                [
                    "- 本コーパスは主に研究・教育目的で公開しています。",
                    "- 記載された URL や外部サイトの内容は収集時点のものであり、現在は変更・削除されている可能性があります。",
                    "- 表記ゆれや誤りが残っている場合があります。修正や改善の提案は GitHub の Issue へお寄せください。",
                ]
            )
        )
        st.subheader("免責事項")
        st.markdown(
            "\n".join(
                [
                    "- 本コーパスおよびビューアの内容について、正確性・完全性・有用性等を保証するものではありません。",
                    "- 本コーパスの利用により生じたいかなる損害についても、作成者は一切の責任を負いません。",
                    "- 参照・収集対象サイトの利用規約・著作権法等を遵守のうえ、適切にご利用ください。",
                ]
            )
        )
        st.subheader("連絡先")
        st.markdown(
            "\n".join(
                [
                    "- 不具合報告、改善提案、質問などは GitHub の Issues にて受け付けています。",
                    "- Issues: https://github.com/kishiyamat/mishearing-corpus/issues",
                ]
            )
        )

with extractor_tab:
    st.subheader("Extractor")
    st.markdown(
        """
抽出処理は Streamlit から切り離され、スクリプトとして実行できます。

次のコマンドをリポジトリのルートで実行してください:

```bash
source .venv/bin/activate
python scripts/asa2025/extract_word_pairs.py
```

これにより `resource/extracted_word_pairs.csv` が生成 / 上書きされます。
"""
    )