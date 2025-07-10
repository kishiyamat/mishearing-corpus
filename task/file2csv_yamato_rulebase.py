"""
1. filenameを指定
2. fileを読んでhtmlからtextに変換
3. 間違いをtgt,正解をsrcに変換
【間違い】
設計積雪深の中で作高が決まってしまい～
【正解】
設計積雪深の中で柵高が決まってしまい～
"""

import streamlit as st  
import sys
import os

test_set = [
  {
    "Src": "大きな<strong>氷河</strong>が動きつつあるように",
    "Tgt": "国の権限を地方の自主性に委ねるという方向へ、大きな<strong>評価</strong>が動きつつあるように",
    "Wnt": "国の権限を地方の自主性に委ねるという方向へ、大きな<strong>氷河</strong>が動きつつあるように",
  },
  {
    "Src": "大口の<strong>与信</strong>の管理体制のチェックは",
    "Tgt": "大口の<strong>預金</strong>の管理体制のチェックは、これまでの通年・専担検査の一部に入っていたのか",
    "Wnt": "大口の<strong>与信</strong>の管理体制のチェックは、これまでの通年・専担検査の一部に入っていたのか",
  },
  {
    "Src": "これは<strong>公党間</strong>の約束であり",
    "Tgt": "先般の与野党合意について、これは<strong>高等官</strong>の約束であり合意は履行していただきたい。",
    "Wnt": "先般の与野党合意について、これは<strong>公党間</strong>の約束であり合意は履行していただきたい。"
  },
  {
    "Src": "<strong>富裕団体</strong>になるべきだとおっしゃるが",
    "Tgt": "行革に努力し<strong>不交付団体</strong>になるべきだとおっしゃるが、",
    "Wnt": "行革に努力し<strong>富裕団体</strong>になるべきだとおっしゃるが、",
  },
  {
    "Src": "<strong>輸出を主体</strong>とする海外への",
    "Tgt": "国内からの<strong>輸出をしたいとする</strong>、海外への一貫輸送の問題",
    "Wnt": "国内からの<strong>輸出を主体</strong>とする海外への一貫輸送の問題",
  },
  {
    "Src": "私たち<strong>隗より始めて</strong>",
    "Tgt": "部を挙げて、私たち<strong>課より始めて</strong>",
    "Wnt": "部を挙げて、私たち<strong>隗より始めて</strong>",
  },
  {
    "Src": "<strong>後年度負担</strong>に耐えられないという",
    "Tgt": "予算編成をし直さないと<strong>今年度負担</strong>に耐えられないという",
    "Wnt": "予算編成をし直さないと<strong>後年度負担</strong>に耐えられないという",
  },
  {
    "Src": "<strong>中国の宝山</strong>が安売りをしなくなった",
    "Tgt": "日本の素材産業が突然よくなったのは<strong>中国のほう</strong>が安売りをしなくなった",
    "Wnt": "日本の素材産業が突然よくなったのは<strong>中国の宝山</strong>が安売りをしなくなった",
  },
  {
    "Src": "幾つかの要点について<strong>県として</strong>こういうスタンスで",
    "Tgt": "幾つかの要点について<strong>検討して</strong>、こういうスタンスで臨みたいと",
    "Wnt": "幾つかの要点について<strong>県として</strong>こういうスタンスで臨みたいと",
  },
  {  # 複数タグがある場合
    "Src": "幾つかの<x>観点</x>について<strong>県として</strong>、こういうスタンスで",
    "Tgt": "幾つかの<x>要点</x>について<strong>検討して</strong>、こういうスタンスで臨みたいと",
    "Wnt": "幾つかの<x>観点</x>について<strong>県として</strong>、こういうスタンスで臨みたいと",
  },
  {
    "Src": "ほとんど<strong>自動車用途向けです</strong>が",
    "Tgt": "エレクトロデバイスの多層基板事業は、ほとんど<strong>自動車用と模型です</strong>が",
    "Wnt": "エレクトロデバイスの多層基板事業は、ほとんど<strong>自動車用途向けです</strong>が",
  }
]


# file:///home/kishiyamat/mishearing-corpus/resource/yamato/gochou_goyaku/coffee_break_parts_similar200407.html
# が良い例。

import difflib

def apply_diff(src, tgt):
    sm = difflib.SequenceMatcher(None, src, tgt)
    result = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            result.append(src[i1:i2])
        elif tag == "insert":
            result.append(tgt[j1:j2])  # insertはTgtから借りてくる
        elif tag == "replace":
            # 差し替えではSrcの語を優先する（Tgtで置換された部分は使わない）
            result.append(src[i1:i2])
        elif tag == "delete":
            result.append("")  # 削除なら何も追加しない
    return ''.join(result)


# 検証ループ
for i, sample in enumerate(test_set, 1):
    generated = apply_diff(sample["Src"], sample["Tgt"])
    is_match = generated == sample["Wnt"]
    st.write(f"事例 {i}: {'✅ OK' if is_match else '❌ NG'}")
    if not is_match:
        st.write(f"  Src : {sample['Src']}")
        st.write(f"  Tgt : {sample['Tgt']}")
        st.write(f"  Wnt : {sample['Wnt']}")
        st.write(f"  Gen : {generated}")


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
import re
from bs4 import BeautifulSoup

st.write("### クエリと保存ディレクトリの設定 (Yamato Sokki)")

st.warning("queriesとsave_pathは適宜変更してください。")
st.warning("results_per_pageとmax_pages_per_queryも適宜変更してください。")
# ToDo: 修正したCSVファイルをAPIに送ってフォーマット修正する
# 一旦、「え」をすすめる
# queries = '仕事 "聞き間違い"'
# save_path = "/home/kishiyamat/mishearing-corpus/data/mishearing/google_search_shigoto_kikimachigai"
save_path = "/home/kishiyamat/mishearing-corpus/data/mishearing/yamato_gochou"
# saved_path = "/home/kishiyamat/mishearing-corpus/data/mishearing/yamato_gochou"
# 設定をwrite
st.write(f"save_path: `{save_path}`")

html_files = st.file_uploader(
    "HTMLを選択（複数可）", type="html", accept_multiple_files=True
)

API_URL_TO_CSV_ENDPOINT = "http://localhost:7860/api/v1/run/cb20fbd9-8699-4fa1-a833-24f978420e02"

import json


# file:///home/kishiyamat/mishearing-corpus/resource/yamato/gochou_goyaku/coffee_break_parts_similar200407.html

if html_files and st.button("送信"):
    for html_i in html_files:
        txt = html_i.getvalue().decode("utf-8")
        st.write(f"Processing file: {html_i.name}")
        st.text_area(f"Content of {html_i.name}", txt, height=300)
        # Read the HTML content as a string
        html_content = html_i.getvalue().decode("utf-8")
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove all <h3> tags
        for h3_tag in soup.find_all("h3"):
            h3_tag.decompose()

        # Remove all tags from the text content
        # ここで差分のタグを除去しているよがよくない
        for tag in soup.find_all(True):
            if tag.name != "strong":
                tag.unwrap()

        clean_text = str(soup)
        tgt_tag_src_list = clean_text.split("【間違い】")
        tgt_src_list = map(lambda x: x.split("【正解】"), tgt_tag_src_list)
        tgt_src_list = filter(lambda x: len(x)==2, tgt_src_list)
        text = ""
        for idx, (tgt, src) in enumerate(tgt_src_list, start=1):
            src = src.strip()
            tgt = tgt.strip()
            src = apply_diff(src, tgt)
            x = f"事例 {idx}: <Src>{src}</Src><Tgt>{tgt}</Tgt></br>"
            text += x
        st.code(text)
        st.write(text.replace("</br>", "\n\n").replace("</Src><Tgt>", "</Src>\n<Tgt>").replace("<S", "\n- <S").replace("<T", "- <T"))

        save_name = html_i.name.replace(".html", "")
        input_str = json.dumps({"text": text, "save_name": save_name, "save_dir": save_path}, ensure_ascii=False)
        st.code(input_str)
        payload = {
            "input_value": input_str,  # The input value to be processed by the flow
            "output_type": "chat",  # Specifies the expected output format
            "input_type": "text"  # Specifies the input format
        }
        headers = { "Content-Type": "application/json" }
        requests.request("POST", API_URL_TO_CSV_ENDPOINT, json=payload, headers=headers)