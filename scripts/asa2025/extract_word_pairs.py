import MeCab


import difflib


def extract_mishear_pairs(src: str, tgt: str):
    """
    MeCabで分かち書きし、LCS（最長共通部分列）以外の部分を「前→後」のペアで返す
    例: 右中間, 宇宙間 → [('右中間', '宇宙間')]
    """
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