import os
import gensim
import MeCab
import difflib
import pandas as pd
import streamlit as st
import pykakasi
from Levenshtein import distance as levenshtein_distance

def extract_mishear_pairs(src: str, tgt: str):
    """
    MeCabで分かち書きし、LCS（最長共通部分列）以外の部分を「前→後」のペアで返す
    例: 右中間, 宇宙間 → [('右中間', '宇宙間')]
    """
    import os
    os.environ["MECABRC"] = "/etc/mecabrc"

    # MeCabのTaggerを初期化（-Owakatiオプションで分かち書き）
    tagger = MeCab.Tagger('-Owakati')

    # 入力文字列を分かち書きして単語リストに変換
    src_words = tagger.parse(src).strip().split()
    tgt_words = tagger.parse(tgt).strip().split()

    # 結果を格納するリスト
    pairs = []

    # 一時的に変更部分を格納するバッファ
    s_buf, t_buf = [], []

    # difflib.SequenceMatcherを使って2つの単語リストの差分を計算
    matcher = difflib.SequenceMatcher(None, src_words, tgt_words)

    # 差分の操作コード（opcodes）を順に処理
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':  # 共通部分の場合
            # バッファに内容があればペアとして追加
            if s_buf or t_buf:
                pairs.append((''.join(s_buf), ''.join(t_buf)))
                s_buf, t_buf = [], []  # バッファをリセット
        else:  # 'replace', 'insert', 'delete' の場合
            # ソースとターゲットの変更部分をバッファに追加
            s_buf.extend(src_words[i1:i2])
            t_buf.extend(tgt_words[j1:j2])

        # 共通部分に戻った場合、バッファの内容をペアとして追加
        if tag == 'equal' and (s_buf or t_buf):
            pairs.append((''.join(s_buf), ''.join(t_buf)))
            s_buf, t_buf = [], []  # バッファをリセット

    # 最後にバッファに残った内容をペアとして追加
    if s_buf or t_buf:
        pairs.append((''.join(s_buf), ''.join(t_buf)))

    # 空のペア（完全一致の場合など）を除外
    pairs = [p for p in pairs if p != ('', '')]

    return pairs


def extract_word_mishear_pairs_from_df(input_df):
    expanded = []
    for idx, row in input_df.iterrows():
        pairs = extract_mishear_pairs(str(row['Src']), str(row['Tgt']))
        for src, tgt in pairs:
            expanded.append({'index': idx, 'Src': src, 'Tgt': tgt})
    expanded_df = pd.DataFrame(expanded)
    return expanded_df


def add_romaji_columns(df):
    kks = pykakasi.kakasi()
    def to_romaji(text):
        return ''.join([item['hepburn'] for item in kks.convert(str(text))])
    df = df.copy()
    df['Src_romaji'] = df['Src'].apply(to_romaji)
    df['Tgt_romaji'] = df['Tgt'].apply(to_romaji)
    # 編集距離の計算
    def calc_norm_edit(row):
        src_r = row['Src_romaji']
        tgt_r = row['Tgt_romaji']
        d1 = levenshtein_distance(src_r, tgt_r)
        d2 = levenshtein_distance(tgt_r, src_r)
        avg_dist = (d1 + d2) / 2
        avg_len = (len(src_r) + len(tgt_r)) / 2
        if avg_len == 0:
            return 0.0
        return avg_dist / avg_len
    df['romaji_edit_distance'] = df.apply(calc_norm_edit, axis=1)
    return df


@st.cache_resource
def load_word_vectors():
    model_dir = "resource/chive-1.3-mc5_gensim/chive-1.3-mc5.kv"
    model = gensim.models.KeyedVectors.load(model_dir)
    return model


def add_in_word_vector_vocab_column(df):
    # https://stackoverflow.com/questions/78279136/importerror-cannot-import-name-triu-from-scipy-linalg-when-importing-gens
    # pip install scipy==1.10.1
    # pip install numpy==1.26.4
    # pip install gensim==4.3.2
    model = load_word_vectors()
    def in_vocab(row):
        return (row['Src'] in model.key_to_index) and (row['Tgt'] in model.key_to_index)
    df = df.copy()
    df['in_word_vector_vocab'] = df.apply(in_vocab, axis=1)
    return df


def extract_word_mishear_pairs(input_df):
    st.write(len(input_df))
    expanded_df = extract_word_mishear_pairs_from_df(input_df)  # expand word-level mishear pairs
    # （）や()を落とす
    st.write(len(expanded_df))
    expanded_df = expanded_df.drop_duplicates(subset=['Src', 'Tgt'])  # Src と Tgt で 重複を削除
    assert set(expanded_df.columns) == {'Src', 'Tgt', 'index'}, "Input DataFrame must contain only 'Src', 'Tgt', and 'index' columns"
    st.write(len(expanded_df))
    # 単語が語彙にあることを保証
    # expanded_df = add_in_word_vector_vocab_column(input_df)
    # to romaji
    expanded_df_with_romaji = add_romaji_columns(expanded_df)
    st.write("抽出結果 (1行が0行やN行になる):")
    st.dataframe(expanded_df_with_romaji)