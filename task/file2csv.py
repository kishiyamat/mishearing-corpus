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

from task.google_search import google_search

st.write("## 異聴データ収集 (File Editor)")

"""
手続き

1. テキストファイルを収集（1101, yamatoなど）
1. Fileを指定
1. 保存ディレクトリを指定
1. filestr2csvを実行
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

files_tobe_csv = st.file_uploader(
    "CSVにするtxtファイルを選択（複数可）", type="txt", accept_multiple_files=True
)
save_path = "/home/kishiyamat/mishearing-corpus/data/mishearing/google_search_1101_kikimatsugai"

if files_tobe_csv and st.button("分類を送信"):
    st.write("送信中...")
    for f in files_tobe_csv:
        # 保存先のファイルパスを作成
        save_name = os.path.splitext(f.name)[0]
        save_file_path = os.path.join(save_path, f"{save_name}.csv")
        
        # すでにファイルが存在する場合はスキップ
        if os.path.exists(save_file_path):
            st.write(f"{save_file_path} は既に存在します。スキップします。")
            continue
        
        # ファイル内容を取得
        text = f.getvalue().decode("utf-8")
        st.write(text)
        text = text.replace("\n", "<br>").replace("\t", "\\t")
        
        # APIに送信するペイロードを作成
        payload_input = {
            "text": text,
            "save_dir": save_path,
            "save_name": os.path.splitext(f.name)[0],  # 拡張子を除去
        }
        payload_input_str = json.dumps(payload_input, ensure_ascii=False)
        st.json(payload_input_str)

        payload = {
            "input_value": payload_input_str,  # The input value to be processed by the flow
            "output_type": "chat",  # Specifies the expected output format
            "input_type": "text"  # Specifies the input format
        }
        # Request headers
        headers = {
            "Content-Type": "application/json"
        }
        API_URL_FFILE_TO_CSV_ENDPOINT = "http://localhost:7860/api/v1/run/ed387577-19fb-45dd-94ef-1fdb47f56a30"
        try:
            r = requests.request("POST", API_URL_FFILE_TO_CSV_ENDPOINT, json=payload, headers=headers)
            r.raise_for_status()
        except requests.RequestException as e:
            st.error(f"API Error: {e}")
            continue  # エラーが出ても次のファイルへ進む
