import streamlit as st
import requests
from io import StringIO
import json
from pathlib import Path


API_URL_FIX_CSV = (
    "http://127.0.0.1:7860/api/v1/run/"
    "688463f5-255f-4368-88f9-e3fb5ed17a50"
)

import pandas as pd

"""複数 CSV を API に送るメイン処理"""
st.header("修正したCSVファイルをAPIに送ってフォーマット修正する")
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
            r = requests.request("POST", API_URL_FIX_CSV, json=payload, headers=headers)
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