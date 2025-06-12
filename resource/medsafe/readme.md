## Readme

1. MedSafeのデータをCSVで取得 (`resource/medsafe/MedicalReportPub.csv`; PayloadはAppendixを参照)
1. DocIDは `MEDSAFE_2010_2025` とする（クエリ）
1. フォーマットに合わせてコピー（IDなど）
1. 関係ない場合はNAとする
    - 無関係なケース
    - 名前の聞き間違え (患者の個人情報でそもそもアクセス不可)
    - どちらかわからない場合、音が似ていれば追加
    - 聞き間違えと思い、系もある。明らかな場合はアノテーション
    - 重複 (HC43333DEE1D22446) 
1. Noteには事例の内容, 事例の背景要因の概要, あるは適宜編集したもの
1. EnvIDに場所、電話は一旦, 電話と追記
    - https://trello.com/c/1AvP0SRk で電話を列に
    - https://trello.com/c/xbwARLDz でEnvID→Env
    - でスキーマを修正
1. アノテーションしたファイルも保存 (`resource/medsafe/2025-06-10_medsafe_annotation.csv`)
1. na列を削除
1. resource/medsafe/2025-06-10_medsafe.csv をベースに、tagやenvを分離する。
   分離したあと、再度mergeしてこのファイルとのdiffを確かめる。
   ブリッジテーブルを使って対応する。

## Appendix

### Payload

```json
{
  "mode": "both",  // "new" or "old" or "both"
  "report_type": ["事故", "ヒヤリハット"],
  "year_from": 2010,
  "year_to": 2025,
  "per_page": 100,  # トータルが47件だったので100で出力
  "summary": "",  // 概要検索（空欄）
  "full_text_search": [
    {
      "keyword": "と聞き間違",  # 「を聞き間違え」より聞き間違えの対象が明らか
      "condition": "or"  // 「いずれかを含む」
    }
  ]
}```
