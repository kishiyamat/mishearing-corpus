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
            expanded.append({'index': idx, "MishearID": row["MishearID"],'Src': src, 'Tgt': tgt})
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



# （）や()内の文字を削除する
def remove_parentheses(df, columns):
    for col in columns:
        df[col] = df[col].str.replace(r'[（(][^）)]*[）)]', '', regex=True)
    return df

def extract_word_mishear_pairs(input_df):
    """
    Extracts word mishearing pairs from the input DataFrame and performs various processing steps 
    to filter and enhance the data.
    Args:
        input_df (pd.DataFrame): Input DataFrame containing mishearing data. 
                                 Expected columns include 'Src', 'Tgt', 'index', and 'MishearID'.
    Returns:
        pd.DataFrame: A processed DataFrame containing word mishearing pairs with additional 
                      columns such as 'Src_romaji', 'Tgt_romaji', 'romaji_edit_distance', 
                      'in_word_vector_vocab', and 'similarity'.
    Processing Steps:
        1. Displays the number of rows in the input DataFrame.
        2. Expands word-level mishearing pairs using `extract_word_mishear_pairs_from_df`.
        3. Removes parentheses and their contents from the 'Src' and 'Tgt' columns.
        4. Removes duplicate rows based on 'Src' and 'Tgt' columns.
        5. Adds romaji representations for the words in 'Src' and 'Tgt' columns.
        6. Filters rows where the romaji edit distance is less than 1.
        7. Ensures that both 'Src_romaji' and 'Tgt_romaji' consist of only alphabetic characters.
        8. Adds a column indicating whether the words are present in the word vector vocabulary.
        9. Filters rows where both words are in the word vector vocabulary.
       10. Calculates the similarity between 'Src' and 'Tgt' using the word vector model and adds 
           it as a new column.
    Notes:
        - The function relies on external helper functions such as `load_word_vectors`, 
          `extract_word_mishear_pairs_from_df`, `remove_parentheses`, and `add_romaji_columns`.
        - The word vector model is expected to be loaded using `load_word_vectors`.
        - The function uses Streamlit (`st`) for displaying intermediate results and debugging 
          information.
        - The input DataFrame must contain specific columns ('Src', 'Tgt', 'index', 'MishearID') 
          for the function to work correctly.
    """
    model = load_word_vectors()  # localで定義

    def add_in_word_vector_vocab_column(df):
        # https://stackoverflow.com/questions/78279136/importerror-cannot-import-name-triu-from-scipy-linalg-when-importing-gens
        # pip install scipy==1.10.1
        # pip install numpy==1.26.4
        # pip install gensim==4.3.2
        def in_vocab(row):
            return (row['Src'] in model.key_to_index) and (row['Tgt'] in model.key_to_index)
        df = df.copy()
        df['in_word_vector_vocab'] = df.apply(in_vocab, axis=1)
        return df
     
    # 入力DataFrameの行数を表示
    st.write(len(input_df))
    # 単語レベルの誤聴ペアを展開
    expanded_df = extract_word_mishear_pairs_from_df(input_df)  # expand word-level mishear pairs
    # （）や()内の文字を削除
    expanded_df = remove_parentheses(expanded_df, ['Src', 'Tgt'])
    st.write(len(expanded_df))

    # 重複を削除
    expanded_df = expanded_df.drop_duplicates(subset=['Src', 'Tgt'])  # Src と Tgt で 重複を削除
    assert set(expanded_df.columns) == {'Src', 'Tgt', 'index', 'MishearID'}, "Input DataFrame must contain only 'Src', 'Tgt', 'index', and 'MishearID' columns"
    st.write(len(expanded_df))

    # 単語にromaji列を追加
    expanded_df_with_romaji = add_romaji_columns(expanded_df)
    st.dataframe(expanded_df_with_romaji)

    # romaji_edit_distance列があることを確認しromaji_edit_distance列の値が1未満の行を抽出
    assert 'romaji_edit_distance'  in expanded_df_with_romaji.columns
    df_with_similar_romaji = expanded_df_with_romaji[expanded_df_with_romaji['romaji_edit_distance'] < 1]
    st.dataframe(df_with_similar_romaji)
    st.write(len(df_with_similar_romaji))

    # _romaji の両方が [a-z] で構成されている行のみを抽出
    df_with_similar_romaji = df_with_similar_romaji[df_with_similar_romaji['Src_romaji'].str.isalpha() & df_with_similar_romaji['Tgt_romaji'].str.isalpha()]
    st.dataframe(df_with_similar_romaji)
    st.write(len(df_with_similar_romaji))

    # 単語が語彙にあることを保証
    df_with_similar_romaji_in_vocab = add_in_word_vector_vocab_column(df_with_similar_romaji)
    df_with_similar_romaji_in_vocab = df_with_similar_romaji_in_vocab[df_with_similar_romaji_in_vocab['in_word_vector_vocab']]
    def calculate_similarity(row):
        if row['Src'] in model.key_to_index and row['Tgt'] in model.key_to_index:
            return model.similarity(row['Src'], row['Tgt'])
        return None  # Return None if either word is not in the vocabulary

    df_with_similar_romaji_in_vocab['similarity'] = df_with_similar_romaji_in_vocab.apply(calculate_similarity, axis=1)
    st.dataframe(df_with_similar_romaji_in_vocab)
    st.write(len(df_with_similar_romaji_in_vocab))
    # similarityという列を追加
    # to romaji
    st.write("抽出結果 (1行が0行やN行になる):")
    return df_with_similar_romaji_in_vocab