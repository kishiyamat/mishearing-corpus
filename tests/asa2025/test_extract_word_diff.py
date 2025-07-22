import csv
import os
import pytest
import MeCab

# テスト用データのパス
data_path = os.path.join(os.path.dirname(__file__), 'data', 'word_diff.csv')

@pytest.fixture(scope="module")
def word_diff_records():
    records = []
    with open(data_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


def extract_mishear_pairs(src: str, tgt: str):
    """
    MeCabで分かち書きし、LCS以外の部分を「前→後」のペアで返す
    例: 右中間, 宇宙間 → [('右中間', '宇宙間')]
    """
    tagger = MeCab.Tagger('-Owakati')
    src_words = tagger.parse(src).strip().split()
    tgt_words = tagger.parse(tgt).strip().split()
    # LCSテーブル作成
    import numpy as np
    m, n = len(src_words), len(tgt_words)
    dp = np.zeros((m+1, n+1), dtype=int)
    for i in range(m):
        for j in range(n):
            if src_words[i] == tgt_words[j]:
                dp[i+1][j+1] = dp[i][j] + 1
            else:
                dp[i+1][j+1] = max(dp[i][j+1], dp[i+1][j])
    # LCS復元
    i, j = m, n
    lcs_idx_src = []
    lcs_idx_tgt = []
    while i > 0 and j > 0:
        if src_words[i-1] == tgt_words[j-1]:
            lcs_idx_src.append(i-1)
            lcs_idx_tgt.append(j-1)
            i -= 1
            j -= 1
        elif dp[i-1][j] >= dp[i][j-1]:
            i -= 1
        else:
            j -= 1
    lcs_idx_src = set(lcs_idx_src)
    lcs_idx_tgt = set(lcs_idx_tgt)
    # 差分部分を抽出
    pairs = []
    s_buf, t_buf = [], []
    i = j = 0
    while i < m or j < n:
        in_lcs_src = i in lcs_idx_src
        in_lcs_tgt = j in lcs_idx_tgt
        if in_lcs_src and in_lcs_tgt:
            if s_buf or t_buf:
                pairs.append((''.join(s_buf), ''.join(t_buf)))
                s_buf, t_buf = [], []
            i += 1
            j += 1
        else:
            if not in_lcs_src and i < m:
                s_buf.append(src_words[i])
                i += 1
            if not in_lcs_tgt and j < n:
                t_buf.append(tgt_words[j])
                j += 1
    if s_buf or t_buf:
        pairs.append((''.join(s_buf), ''.join(t_buf)))
    return pairs


def test_extract_mishear_pairs():
    test_cases = [
        ("右中間", "宇宙間", [("右中間", "宇宙間")]),
        ("千駄ヶ谷", "センター街", [("千駄ヶ谷", "センター街")]),
        ("たまプラ", "鎌倉", [("たまプラ", "鎌倉")]),
        ("千川（豊島区）", "仙川（調布市）", [("千川", "仙川"), ("豊島区", "調布市")]),
        ("青葉台", "青葉台", []),
        ("町田", "町家", [("町田", "町家")]),
        ("町田", "松戸", [("町田", "松戸")]),
        ("渋谷", "入谷", [("渋谷", "入谷")]),
        ("シングレア錠", "シンデレラ城", [("シングレア錠", "シンデレラ城")]),
        ("ジャカビ", "ジャガビー", [("カビ", "ガビー")]),
        ("MRI", "芋洗い", [("MRI", "芋洗い")]),
        ("ICU", "足湯", [("ICU", "足湯")]),
        ("包装のバイト", "放送のバイト", [("包装", "放送")]),
        ("第三者委員会", "大サンシャイン会", [("第三者委員", "大サンシャイン")]),
        ("詐欺にひっかかりそうになった", "猿に引っ掻かれそうになった", [('詐欺', '猿'), ('ひっかかり', '引っ掻かれ')]),
        ("藤本さん", "辻本さん", [("藤本", "辻本")]),
        ("洗いたい", "会いたい", [("洗い", "会い")]),
        ("加藤さん", "羽藤さん", [("加藤", "羽藤")]),
        ("加藤さん", "佐藤さん", [("加藤", "佐藤")]),
        ("A5のノート", "英語のノート", [("A5", "英語")]),
        ("紙テープ", "カミテープ", [("紙テープ", "カミテープ")]),
        ("お飲み物は？", "お名前は？", [("飲み物", "名前")]),
        ("権利証（けんりしょう）", "権利書（けんりしょ）", [('証', '書'), ('う', '')]),
        ("いわさし", "いわさき", [("いわさし", "いわさき")]),
        ("雨ざらし", "アザラシ", [("雨ざらし", "アザラシ")]),
        ("Gd（ガドリニウム）", "Cd（カドミウム）", [('Gd', 'Cd'), ('ガドリニウム', 'カドミウム')]),
        ("カドリニウム", "カドミウム", [("カドリニウム", "カドミウム")]),
        ("あおば歯科", "あおぞら歯科", [("あおば", "あおぞら")]),
        ("錦糸町", "警視庁", [("錦糸町", "警視庁")]),
        ("警視庁", "錦糸町", [("警視庁", "錦糸町")]),
        ("松屋", "松屋", []),
        ("理学部", "医学部", [("理学部", "医学部")]),
        ("工学部", "法学部", [("工学部", "法学部")]),
        ("冷凍枝豆結構高かったわ", "冷凍枝豆健康だわ買ったわ", [("結構高かっ", "健康だわ買っ")]),
        ("寒いからちょっとだけ閉めて", "寒いからちょっと抱き締めて", [("だけ閉め", "抱き締め")]),
        ("ご声援ありがとうございます", "五千円ありがとうございます！", [("ご声援", "五千円"), ('', '！')]),
        ("こないだコロナになって大変だったよ", "こないだ転んだって大変だったよ", [('コロナになって', '転んだって')]),
        ("Edyでお願いします。", "iDでお願いします。", [("Edy", "iD")]),
        ("iDでお願いします。", "Edyでお願いします。", [("iD", "Edy")]),
        # 追加: word_diff.csvの先頭4件
        ("これは100マイクロか", "これは100mgか", [("マイクロ", "mg")]),
        ("等比重でいいですか", "高比重でいいですか", [("等比重", "高比重")]),
        ("プロタミン", "ドブタミン", [("プロタミン", "ドブタミン")]),
        ("アドレナリン1mg iv", "ノルアドレナリン1mg iv", [("アドレナリン", "ノルアドレナリン")]),
    ]
    for i, (src, tgt, expected) in enumerate(test_cases):
        pairs = extract_mishear_pairs(src, tgt)
        assert pairs == expected, f"case {i}: {pairs} != {expected}"
