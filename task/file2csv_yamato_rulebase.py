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

# 前提: 違う部分は挿入のみ
test_set = [
  {  # 前削除 + 置換
    "Src": "大きな<strong>氷河</strong>が動きつつあるように",
    "Tgt": "国の権限を地方の自主性に委ねるという方向へ、大きな<strong>評価</strong>が動きつつあるように",
    "Wnt": "国の権限を地方の自主性に委ねるという方向へ、大きな<strong>氷河</strong>が動きつつあるように",
  },
  {  # 前削除 + 置換
    "Src": "これは<strong>公党間</strong>の約束であり",
    "Tgt": "先般の与野党合意について、これは<strong>高等官</strong>の約束であり合意は履行していただきたい。",
    "Wnt": "先般の与野党合意について、これは<strong>公党間</strong>の約束であり合意は履行していただきたい。"
  },
  {  # 後削除 + 置換
    "Src": "大口の<strong>与信</strong>の管理体制のチェックは",
    "Tgt": "大口の<strong>預金</strong>の管理体制のチェックは、これまでの通年・専担検査の一部に入っていたのか",
    "Wnt": "大口の<strong>与信</strong>の管理体制のチェックは、これまでの通年・専担検査の一部に入っていたのか",
  },
  {  # 前削除 + 置換/挿入
    "Src": "<strong>富裕団体</strong>になるべきだとおっしゃるが",
    "Tgt": "行革に努力し<strong>不交付団体</strong>になるべきだとおっしゃるが、",
    "Wnt": "行革に努力し<strong>富裕団体</strong>になるべきだとおっしゃるが、",
  },
  {  # 前後削除 + 置換
    "Src": "<strong>輸出を主体</strong>とする海外への",
    "Tgt": "国内からの<strong>輸出をしたいとする</strong>、海外への一貫輸送の問題",
    "Wnt": "国内からの<strong>輸出を主体</strong>とする海外への一貫輸送の問題",
  },
  {  # 前削除 + 置換
    "Src": "私たち<strong>隗より始めて</strong>",
    "Tgt": "部を挙げて、私たち<strong>課より始めて</strong>",
    "Wnt": "部を挙げて、私たち<strong>隗より始めて</strong>",
  },
  {  # 前削除 + 置換
    "Src": "<strong>後年度負担</strong>に耐えられないという",
    "Tgt": "予算編成をし直さないと<strong>今年度負担</strong>に耐えられないという",
    "Wnt": "予算編成をし直さないと<strong>後年度負担</strong>に耐えられないという",
  },
  {  # 前削除 + 置換
    "Src": "<strong>中国の宝山</strong>が安売りをしなくなった",
    "Tgt": "日本の素材産業が突然よくなったのは<strong>中国のほう</strong>が安売りをしなくなった",
    "Wnt": "日本の素材産業が突然よくなったのは<strong>中国の宝山</strong>が安売りをしなくなった",
  },
  {  # 後ろ削除x2
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
  },
  {
    "Src": "ほとんど<strong>自動車用途向けです</strong>が",
    "Tgt": "エレクトロデバイスの多層基板事業は、ほとんど<strong>自動車用と模型です</strong>が",
    "Wnt": "エレクトロデバイスの多層基板事業は、ほとんど<strong>自動車用途向けです</strong>が",
  },
  {
    "Src": "西武鉄道に対しても、国土省としては他社同様に、安全面、サービス面でのチェック、<strong>政策金融、</strong>各種補助制度の活用等を行っていきたいと……。",
    "Tgt": "西武鉄道に対しても、国土省としては他社同様に、安全面、サービス面でのチェック、<strong>精算金、</strong>各種補助制度の活用等を行っていきたいと……。",
    "Wnt": "西武鉄道に対しても、国土省としては他社同様に、安全面、サービス面でのチェック、<strong>政策金融、</strong>各種補助制度の活用等を行っていきたいと……。",
  },
  { # 変化なし+削除
    "Src": "気候変動枠組み条約第○回<strong>締結国会議、閣僚級会議</strong>への出席と～～",
    "Tgt": "気候変動枠組み条約第○回<strong>締結会議、閣僚会議</strong>への出席と～～",
    "Wnt": "気候変動枠組み条約第○回<strong>締結国会議、閣僚級会議</strong>への出席と～～",
  },
  { # 変化なし+挿入
    "Src": "気候変動枠組み条約第○回<strong>締結国会、閣僚会議</strong>への出席と～～",
    "Tgt": "気候変動枠組み条約第○回<strong>締結国会、閣僚級会議</strong>への出席と～～",
    "Wnt": "気候変動枠組み条約第○回<strong>締結国会、閣僚会議</strong>への出席と～～",
  },
  {  # src削除+削除
    "Src": "<strong>締結国会議、閣僚級会議</strong>への出席と～～",
    "Tgt": "気候変動枠組み条約第○回<strong>締結国会、閣僚会議</strong>への出席と～～",
    "Wnt": "気候変動枠組み条約第○回<strong>締結国会議、閣僚級会議</strong>への出席と～～",
  },
  {  # src削除+挿入  # <strong> タグの中身はいじらない
    "Src": "<strong>締結国会、閣僚会議</strong>への出席と～～",
    "Tgt": "気候変動枠組み条約第○回<strong>締結国会、閣僚級会議</strong>への出席と～～",
    "Wnt": "気候変動枠組み条約第○回<strong>締結国会、閣僚会議</strong>への出席と～～",
  },
  {  # src削除+挿入+削除  # <strong> タグの中身はいじらない
    "Src": "<strong>締結国会、閣僚会議</strong>への<strong>ご出席</strong>と～～",
    "Tgt": "気候変動枠組み条約第○回<strong>締結国会、閣僚級会議</strong>への<strong>出席</strong>と～～",
    "Wnt": "気候変動枠組み条約第○回<strong>締結国会、閣僚会議</strong>への<strong>ご出席</strong>と～～",
  },
  {  # src削除+挿入+削除  # <strong> タグの中身はいじらない
    "Src":"気候変動枠組み条約第○回<strong>締結国会議、閣僚級会議</strong>への出席と～～",
    "Tgt":"気候変動枠組み条約第○回<strong>締結国会、閣僚会議</strong>への出席と～～"  ,
    "Wnt":"気候変動枠組み条約第○回<strong>締結国会議、閣僚級会議</strong>への出席と～～",
  },
]


# file:///home/kishiyamat/mishearing-corpus/resource/yamato/gochou_goyaku/coffee_break_parts_similar200407.html
# が良い例。

import difflib

import difflib
import re

def protect_strong(text, placeholder_format="__STRONG_{}__"):
    """<strong>〜</strong>をプレースホルダに置き換え"""
    protected = []
    strong_map = {}
    count = 0

    def replacer(match):
        nonlocal count
        placeholder = placeholder_format.format(count)
        strong_map[placeholder] = match.group(0)
        protected.append(placeholder)
        count += 1
        return placeholder

    protected_text = re.sub(r"<strong>.*?</strong>", replacer, text)
    return protected_text, strong_map

def restore_strong(text, strong_map):
    """プレースホルダを元の<strong>〜</strong>に戻す"""
    for placeholder, strong_text in strong_map.items():
        text = text.replace(placeholder, strong_text)
    return text

def apply_diff_protected(src, tgt):
    # Step 1: protect <strong> blocks
    src_protected, src_map = protect_strong(src)
    tgt_protected, tgt_map = protect_strong(tgt)

    # Step 2: run difflib diff
    sm = difflib.SequenceMatcher(None, src_protected, tgt_protected)
    result = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        src_seg = src_protected[i1:i2]
        tgt_seg = tgt_protected[j1:j2]

        # Check for protected tokens
        if any(ph in src_seg for ph in src_map) or any(ph in tgt_seg for ph in tgt_map):
            if tag in ("equal", "replace"):
                result.append(src_seg)  # keep src version
            elif tag == "insert":
                result.append("")  # no insert into protected zones
            elif tag == "delete":
                result.append("")
        else:
            if tag == "equal":
                result.append(src_seg)
            elif tag == "insert":
                result.append(tgt_seg)
            elif tag == "replace":
                result.append(src_seg)
            elif tag == "delete":
                result.append("")

    # Step 3: restore strong blocks
    final = ''.join(result)
    final = restore_strong(final, src_map)
    return final

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
    generated = apply_diff_protected(sample["Src"], sample["Tgt"])
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
# トピックのみを出力させたほうが良さそう
# Envも必要だけど
# coffee_break_parts_similar200506_002,かんじていたか,感じていたか,「かんじて」と「かんで」の発音が近い。,報道機関の会議で、番組制作局次長らの意見についての発言。,
# -> たぶんLLM側での余計な補足
# offee_break_parts_similar200506_003,逐一／政治絡みだ,逐次／政治家なんだ,「ちくいち」と「ちくじ」、「からみ」と「かなんだ」の混同に注意。,政治的な事案の経緯説明中の発言。複数箇所での聞き間違
# -> LLMが省略した
# <strong>遺漏のない</strong>考え方
# <strong>色のない</strong>考え方で取り組む
# <strong>遺漏のない</strong>考え方で取り組む
# 全省庁が一緒になって、<strong>遺漏なきよう</strong>、議論漏れがなきように～～。
# 全省庁が一緒になって、<strong>いろんな機能</strong>、議論漏れがなきように～～。全省庁が一緒になって、<strong>異論なきよう</strong>、議論漏れがなきように～～。
# 全省庁が一緒になって、<strong>遺漏なきよう</strong>、議論漏れがなきように～～。
# <br/> があるのが3例ある。

st.button("ファイルを選択したら、送信ボタンを押してください。")

if html_files and st.button("送信"):
    for html_i in html_files:
        saved_name = html_i.name.replace(".html", ".csv")
        # if os.path.exists(f"{save_path}/{saved_name}"):
        #     st.warning(f"{html_i.name} はすでに存在します。スキップします。")
        #     continue
        txt = html_i.getvalue().decode("utf-8")
        st.write(f"Processing file: {html_i.name}")
        # st.text_area(f"Content of {html_i.name}", txt, height=300)
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
                # == 他のなにか
                if tag.name != "br":
                    tag.unwrap()

        clean_text = str(soup)
        tgt_tag_src_list = clean_text.split("【間違い】")
        tgt_src_list = map(lambda x: x.split("【正解】"), tgt_tag_src_list)
        tgt_src_list = filter(lambda x: len(x)==2, tgt_src_list)
        text = ""
        # </br> があるケースはエラーになりうるので注意
        for idx, (tgt, src) in enumerate(tgt_src_list, start=1):
            if "<br/>" in tgt:
                st.warning(f"異聴事例 {idx} に <br/> が含まれています。手動で修正してください。\n File: {html_i.name}")
            tgt.replace("<br/>","")
            src = src.strip()
            tgt = tgt.strip()
            src = apply_diff_protected(src, tgt)
            x = f"事例 {idx}: <Src>{src}</Src><Tgt>{tgt}</Tgt></br>"
            text += x
        
        # 動作を保証するまでは保留
        st.code(text)
        st.write(text.replace("</br>", "\n\n").replace("</Src><Tgt>", "</Src>\n\n<Tgt>").replace("<S", "\n- <S").replace("<T", "- <T"))

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
