"""
1. filenameを指定
2. fileを読んでhtmlからtextに変換
3. 間違いをtgt,正解をsrcに変換
【間違い】
設計積雪深の中で作高が決まってしまい～
【正解】
設計積雪深の中で柵高が決まってしまい～

coffee_break_parts_similar202403_00N のようにMishearIDを付与
SpeakerID: N/A
ListenerID: 速記者
Language: ja
TagやEnvsも指定する。この時点でLLMが有効

（レク→レクチャ－の略）のように補足がある場合はNoteに配置

MishearID,Src,Tgt,Tips,Note,OriginalFlag,DocID,URL,SpeakerID,ListenerID,Language
20190115_001,十分周知していたのに、今ごろテール・ヘビーに乗っかってこられちゃ～,十分周知していたのに、今ごろ定例日に乗っかってこられちゃ～,,誤:「テール・ヘビー（tail heavy）」を「定例日」と誤聴,1,YAMATO_201901,https://www.yamatosokki.co.jp/mistake/similar201901,N/A,N/A,ja
20190115_002,当初の案よりもずいぶんとモデレートなものにはなってきたと思うけど～,当初の案よりもずいぶんと戻り得たものにはなってきたと思うけど～,,誤:「モデレート(moderate)」を「戻り得た」と誤聴,1,YAMATO_201901,https://www.yamatosokki.co.jp/mistake/similar201901,N/A,N/A,ja
20190115_003,将来へ向けて、競争を勝ち抜くための礎を構築する～,将来へ向けて、競争を勝ち抜くための位置づけを構築する～,,誤:「礎」を「位置づけ」と誤聴,1,YAMATO_201901,https://www.yamatosokki.co.jp/mistake/similar201901,N/A,N/A,ja
20190115_004,南米の案件ですが、現地の空港が高地にあってですね～,南米の案件ですが、現地の空港が高知にあってですね～,,誤:「高地」を「高知」と誤聴,1,YAMATO_201901,https://www.yamatosokki.co.jp/mistake/similar201901,N/A,N/A,ja
20190115_005,優秀な人材の地方還流をぜひにも～,優秀な人材の地方管理をぜひにも～,,誤:「還流」を「管理」と誤聴,1,YAMATO_201901,https://www.yamatosokki.co.jp/mistake/similar201901,N/A,N/A,ja
"""


import streamlit as st  
import sys
import os

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

if html_files and st.button("送信"):
    for html_i in html_files:
        saved_name = html_i.name.replace(".html", ".csv")
        if os.path.exists(f"{save_path}/{saved_name}"):
            st.warning(f"{html_i.name} はすでに存在します。スキップします。")
            continue
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
        clean_text = soup.get_text()

        tgt_tag_src_list = clean_text.split("【間違い】")
        tgt_src_list = map(lambda x: x.split("【正解】"), tgt_tag_src_list)
        tgt_src_list = filter(lambda x: len(x)==2, tgt_src_list)
        text = ""
        for idx, (tgt, src) in enumerate(tgt_src_list, start=1):
            x = f"事例 {idx}: <Src>{src.strip()}</Src><Tgt>{tgt.strip()}</Tgt></br>"
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

# for result in organic_results:
#     try:
#         url = result["url"]
#         # Save the result to resource/txt_1101
#         save_dir = "resource/txt_1101"
#         file_name = url.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "_") + ".txt"
#         file_path = os.path.join(save_dir, file_name)
#         if os.path.exists(file_path):
#             st.info(f"File already exists, skipping: {file_path}")
#             continue
#         st.write(f"Fetching content from: {url}")
#         response = requests.get(url)
#         response.encoding = response.apparent_encoding  # Set encoding based on response content
#         fetched_text = response.text
#         st.write("Fetched content:")
#         # Clean up the URL for use as a file name
#         st.text_area(f"Content from {url}", fetched_text, height=300)
#         fetched_txt = html_to_text(fetched_text)
#         st.text_area(f"Processed Content from {url}", fetched_txt, height=300)
# 
#         os.makedirs(save_dir, exist_ok=True)
#         with open(file_path, "w", encoding="utf-8") as f:
#             f.write(fetched_txt)
#         st.success(f"Content saved to: {file_path}")
# 
#         time.sleep(1)  # Sleep for 1 second between requests
#     except Exception as e:
#         st.error(f"Failed to fetch the URL content from {url}: {e}")
# 
