"""Produce a pair-level Sol research-decision ledger for reproducible POS risks.

The input is the immutable pre-migration audit. Index sets below were reviewed
against the numbered 297-row surface listing, not inferred from tags alone.
"""

import csv
import functools
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/kishi/.codex/worktrees/ca66/mishearing-corpus/corpus")
sys.path.insert(0, str(ROOT))
from corpus_api.dictionary import dictionary_entries

SOURCE = ROOT / "docs/reviews/2026-10-24-word-extraction/pair-level-audit.csv"
OUT = Path("/tmp/lexical-pos-risk-sol-decisions.json")

CONTEXT = {
    int(x)
    for x in [
        "2",
        "3",
        "5",
        "14",
        "15",
        "16",
        "21",
        "24",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "39",
        "40",
        "41",
        "44",
        "45",
        "46",
        "47",
        "48",
        "49",
        "50",
        "51",
        "53",
        "54",
        "56",
        "57",
        "59",
        "60",
        "67",
        "68",
        "69",
        "70",
        "71",
        "72",
        "73",
        "76",
        "77",
        "79",
        "80",
        "82",
        "83",
        "84",
        "85",
        "86",
        "87",
        "88",
        "89",
        "90",
        "91",
        "92",
        "93",
        "95",
        "96",
        "97",
        "99",
        "100",
        "101",
        "102",
        "103",
        "105",
        "106",
        "107",
        "108",
        "109",
        "110",
        "111",
        "113",
        "114",
        "115",
        "116",
        "117",
        "118",
        "119",
        "120",
        "121",
        "122",
        "123",
        "124",
        "125",
        "126",
        "128",
        "129",
        "130",
        "131",
        "132",
        "133",
        "135",
        "136",
        "137",
        "139",
        "141",
        "142",
        "143",
        "144",
        "145",
        "147",
        "148",
        "149",
        "150",
        "151",
        "184",
        "186",
        "240",
        "241",
        "243",
        "244",
        "245",
        "246",
        "249",
        "253",
        "255",
        "257",
        "262",
        "263",
        "271",
        "272",
        "273",
        "275",
        "280",
        "287",
        "288",
        "291",
        "292",
        "293",
        "294",
    ]
}
SHORTEN = {
    4: ("恐縮", "キョウシュク"),
    6: ("魚", "山田"),
    7: ("代位", "代理"),
    11: ("遺漏", "色"),
    13: ("代替", "大体"),
    17: ("徒過", "渡河"),
    18: ("協働", "共同"),
    19: ("運航", "運行"),
    20: ("最終財", "最終材"),
    22: ("居宅", "委託"),
    23: ("俎上", "遡上"),
    27: ("季節調整値", "規制調整値"),
    42: ("捕捉", "補足"),
    55: ("深化", "進化"),
    58: ("深化", "進化"),
    61: ("実務", "３つ"),
    62: ("徴取", "聴取"),
    63: ("投開票", "東海地方"),
    64: ("触発", "紹介"),
    65: ("党利党略", "通り一遍"),
    66: ("再燃", "対立"),
    74: ("常幹", "朝刊"),
    78: ("問題", "本体"),
    81: ("廃案", "廃棄"),
    104: ("箍", "ただ"),
    134: ("ＯＳＳ", "大磯"),
    146: ("輸贏", "故"),
    160: ("聞き分け", "父は毛"),
    159: ("丸谷", "マリア"),
    162: ("鍛高譚", "タンタカポン"),
    163: ("太子堂", "体脂肪"),
    169: ("仲垣内", "なかがいと"),
    178: ("井原", "ミハラ"),
    181: ("エヌ", "エム"),
    182: ("画像処理", "課長処理"),
    185: ("魚民", "ウォーターミント"),
    187: ("オヤマ", "大山"),
    188: ("オヤマ", "大山"),
    190: ("東京タワー", "東京タワーズ"),
    198: ("石田", "三島"),
    200: ("千川", "仙川"),
    201: ("新丸子", "下丸子"),
    211: ("センター街", "千駄ヶ谷"),
    212: ("北広島市", "北広島町"),
    214: ("谷原", "谷和原"),
    221: ("向原", "向原"),
    222: ("向原", "向原"),
    219: ("アグリ", "アグリー"),
    224: ("作務衣", "サムウェイ"),
    242: ("鋼", "鼻毛"),
    248: ("小中井", "トナカイ"),
    254: ("濱下", "ハムスター"),
    256: ("生中", "老酒"),
    261: ("生麩", "なまこ"),
    264: ("小菅", "スウェーデン"),
    266: ("樹木医", "ジモピー"),
    267: ("標準", "風神"),
    285: ("合田", "オーダー"),
    286: ("布袋寅泰", "ポテトもやし"),
}
NEED_SOURCE = {int(x) for x in []}
PARTICLE_INCLUSIVE = {59, 87, 113, 142, 170, 240, 246, 271}
LEXICAL_RETYPE = {43: "word", 205: "compound", 260: "compound"}
SHORTEN_MULTI = {
    8: [(("Ｂ５判", "Ｂ５版"), "compound"), (("Ａ４判", "Ａ４版"), "compound")],
    282: [(("お日さま", "おっさん"), "word"), (("匂い", "臭い"), "word")],
    284: [(("ワケギ", "ワキゲ"), "word"), (("ハネギ", "ハナゲ"), "word")],
}
EXPAND_CONTEXTUAL = {
    252: ("静かなるドン", "静かなうどん", "シズカナルドン", "シズカナウドン"),
}


@functools.cache
def tokens(surface):
    proc = subprocess.run(
        ["mecab", "-Ochasen"],
        input=surface,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=30,
    )
    result = []
    for line in proc.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) >= 4:
            result.append({"surface": fields[0], "pos": fields[3]})
    return result


def risk_flags(src, tgt):
    flags = []
    for side, surface in [("src", src), ("tgt", tgt)]:
        pos = [x["pos"] for x in tokens(surface)]
        if any(x.startswith("助詞") for x in pos):
            flags.append(side + ":particle")
        if sum(x.startswith("動詞") for x in pos) > 1:
            flags.append(side + ":multiple_verbs")
        if sum(x.startswith("形容詞") for x in pos) > 1:
            flags.append(side + ":multiple_adjectives")
        if any(x.startswith("助動詞") for x in pos):
            flags.append(side + ":auxiliary")
        if any(x.startswith("記号") for x in pos):
            flags.append(side + ":punctuation")
    return flags


def main():
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8-sig", newline="")))
    risks = []
    for row in rows:
        if row["OldUnitType"] not in ("word", "compound"):
            continue
        flags = risk_flags(row["OldSrcSurface"], row["OldTgtSurface"])
        if flags:
            risks.append((row, flags))
    assert len(risks) == 297, len(risks)
    numbers = set(range(1, len(risks) + 1))
    assert not (
        (CONTEXT & SHORTEN.keys())
        or (CONTEXT & NEED_SOURCE)
        or (SHORTEN.keys() & NEED_SOURCE)
        or (CONTEXT & LEXICAL_RETYPE.keys())
        or (SHORTEN.keys() & LEXICAL_RETYPE.keys())
        or (NEED_SOURCE & LEXICAL_RETYPE.keys())
        or (CONTEXT & SHORTEN_MULTI.keys())
        or (SHORTEN.keys() & SHORTEN_MULTI.keys())
        or (NEED_SOURCE & SHORTEN_MULTI.keys())
        or (LEXICAL_RETYPE.keys() & SHORTEN_MULTI.keys())
        or (CONTEXT & EXPAND_CONTEXTUAL.keys())
        or (SHORTEN.keys() & EXPAND_CONTEXTUAL.keys())
        or (SHORTEN_MULTI.keys() & EXPAND_CONTEXTUAL.keys())
    )
    assert (
        CONTEXT
        | SHORTEN.keys()
        | NEED_SOURCE
        | LEXICAL_RETYPE.keys()
        | SHORTEN_MULTI.keys()
        | EXPAND_CONTEXTUAL.keys()
    ) <= numbers
    items = []
    for i, (row, flags) in enumerate(risks, 1):
        src, tgt = row["OldSrcSurface"], row["OldTgtSurface"]
        item = {
            "index": i,
            "MishearID": row["MishearID"],
            "PairID": row["PairID"],
            "OriginalHash": row["OriginalHash"],
            "old": {
                "src": src,
                "tgt": tgt,
                "src_span": [int(row["OldSrcStart"]), int(row["OldSrcEnd"])],
                "tgt_span": [int(row["OldTgtStart"]), int(row["OldTgtEnd"])],
                "unit_type": row["OldUnitType"],
            },
            "pos_flags": flags,
            "src_tokens": tokens(src),
            "tgt_tokens": tokens(tgt),
        }
        if i in CONTEXT:
            item["decision_class"] = "RETYPE_CONTEXTUAL"
            item["target_unit_type"] = (
                "particle-inclusive" if i in PARTICLE_INCLUSIVE else "phrase"
            )
            item["reason"] = (
                "The reviewed surface contains contrast-essential particles, "
                "dependent predicate material, enumeration, or asymmetric phrase "
                "material. The selected comparison is contextual, not two complete "
                "independent lexical units. This retype preserves old bounds and "
                "readings; a separate shorter candidate requires verified evidence."
            )
            if i == 41:
                item["reason"] = (
                    "Both sides are causative predicate forms (転じさせる/展示させる); "
                    "the apparent lexical base alone is not the reviewed comparison. "
                    "Keep full bounds/readings but mark the pair contextual."
                )
        elif i in LEXICAL_RETYPE:
            item["decision_class"] = "RETYPE_LEXICAL"
            item["target_unit_type"] = LEXICAL_RETYPE[i]
            item["reason"] = (
                "Source Note and whole-surface morphology establish a complete "
                "inflected verb pair or uninterrupted nominal compound. MeCab POS "
                "risk does not make it contextual, but the old lexical subtype "
                "needs correction."
            )
        elif i in SHORTEN_MULTI:
            item["decision_class"] = "SHORTEN_MULTI"
            item["new_pairs"] = []
            for (short_src, short_tgt), subtype in SHORTEN_MULTI[i]:
                ss, ts = src.find(short_src), tgt.find(short_tgt)
                assert ss >= 0 and ts >= 0
                item["new_pairs"].append(
                    {
                        "src": short_src,
                        "tgt": short_tgt,
                        "unit_type": subtype,
                        "src_span": [
                            int(row["OldSrcStart"]) + ss,
                            int(row["OldSrcStart"]) + ss + len(short_src),
                        ],
                        "tgt_span": [
                            int(row["OldTgtStart"]) + ts,
                            int(row["OldTgtStart"]) + ts + len(short_tgt),
                        ],
                    }
                )
            item["old_review_readings"] = {
                "src": row["OldSrcReading"],
                "tgt": row["OldTgtReading"],
            }
            item["reading_basis"] = (
                "B5/A4: archived Yamato source and old full reading segmented "
                "at the shared から; kana-name pair: original katakana surfaces; "
                "お日さま/おっさん: old full readings show distinct first nouns "
                "and the same ニオイ reading for 匂い/臭い. Each new component "
                "still needs exact reviewed annotation/read alignment."
            )
            item["reason"] = (
                "There are two independent contrasts in the old pair. Both "
                "must survive as separate lexical pairs with lineage to the "
                "same old PairID; one short span would lose an observation."
            )
        elif i in EXPAND_CONTEXTUAL:
            full_src, full_tgt, read_src, read_tgt = EXPAND_CONTEXTUAL[i]
            item["decision_class"] = "EXPAND_CONTEXTUAL"
            item["new"] = {
                "src": full_src,
                "tgt": full_tgt,
                "unit_type": "phrase",
                "src_span": [0, len(full_src)],
                "tgt_span": [0, len(full_tgt)],
                "src_reading": read_src,
                "tgt_reading": read_tgt,
            }
            item["reading_basis"] = (
                "Original source Note names 静かなるドン as the whole title and "
                "静かなうどん as the heard phrase; shared 静か is included because "
                "old tails なるドン/なうどん are not independent lexical units. "
                "Prefix シズカ plus current short readings gives the full forms; "
                "source-backed review still precedes confirmed annotation."
            )
            item["reason"] = (
                "The old word label covers only dependent tail fragments of a "
                "proper title versus an adjective+noun phrase. Preserve the full "
                "source contrast as contextual phrase."
            )
        elif i in SHORTEN:
            short_src, short_tgt = SHORTEN[i]
            ss, ts = src.find(short_src), tgt.find(short_tgt)
            assert ss >= 0 and ts >= 0, (i, src, tgt, short_src, short_tgt)
            item["decision_class"] = "SHORTEN"
            item["target_unit_type"] = (
                "phrase" if i == 160 else "compound" if i in (27, 286) else "word"
            )
            item["new"] = {
                "src": short_src,
                "tgt": short_tgt,
                "src_span": [
                    int(row["OldSrcStart"]) + ss,
                    int(row["OldSrcStart"]) + ss + len(short_src),
                ],
                "tgt_span": [
                    int(row["OldTgtStart"]) + ts,
                    int(row["OldTgtStart"]) + ts + len(short_tgt),
                ],
            }
            item["old_review_readings"] = {
                "src": row["OldSrcReading"],
                "tgt": row["OldTgtReading"],
            }
            item["new_whole_surface_dictionary_entries"] = {
                "src": [
                    {"reading": e["reading"], "pos": e["features"][:3]}
                    for e in dictionary_entries(short_src)["entries"]
                ],
                "tgt": [
                    {"reading": e["reading"], "pos": e["features"][:3]}
                    for e in dictionary_entries(short_tgt)["entries"]
                ],
            }
            item["reading_basis"] = (
                "Old reviewed annotation readings and the listed exact whole-surface "
                "dictionary entries or a source-specific place/name reading must "
                "uniquely align. This is a research shortening decision, not an "
                "automatically confirmed new pronunciation. If alignment fails, "
                "retain as NEED_SOURCE; never use MeCab best path alone."
            )
            if i == 160:
                item["reading_basis"] = (
                    "Source https://eichie.jp/advisements/9568 plus the particle "
                    "は=ワ yields キキワケ/チチワケ; this known decision is already "
                    "separately applied to canonical review and must not be repatched "
                    "from the old word span."
                )
            item["reason"] = (
                "Compared word or proper name is smaller than the old span; the "
                "old span includes shared syntax, auxiliary, punctuation, or a "
                "parenthetical reading/source note. Preserve complete lexical "
                "forms and every independent contrast."
            )
        elif i in NEED_SOURCE:
            item["decision_class"] = "NEED_SOURCE"
            item["reason"] = (
                "The surface/POS heuristic alone cannot distinguish a lexicalized "
                "expression, complete inflected form, source note, or phrase. "
                "Inspect the original Note/source and verified reading before "
                "changing the selected comparison."
            )
            if i in (8, 220, 282, 284):
                item["reason"] = (
                    "Multiple independent contrasts or alternative referents occur "
                    "inside this old pair. A one-pair retype or one short candidate "
                    "would drop information; inspect source and create all required "
                    "spans with explicit lineage."
                )
        else:
            item["decision_class"] = "KEEP_LEXICAL"
            item["target_unit_type"] = row["OldUnitType"]
            item["reason"] = (
                "The apparent POS trigger comes from MeCab splitting kana, a "
                "proper name, parenthetical reading, middle dot, or a single "
                "inflected lexical item; inspection of both selected surfaces "
                "finds no contrast-essential clause. Keep the reviewed full pair "
                "and its side-specific annotation, not an inner character diff."
            )
            if i in (12, 152, 156, 213, 220):
                item["reason"] = (
                    "Current exact reviewed Override already selects one whole "
                    "lexical surface from a raw parenthetical/slash explanation; "
                    "the other reading or referent is retained as a side-specific "
                    "qualifier, and source Evidence marks actual audio uncertainty. "
                    "Do not treat the raw note text as spoken or silently add "
                    "unwitnessed alternative pairs."
                )
        items.append(item)
    payload = {
        "schema": "lexical-pos-risk-sol-decisions/v1",
        "source": str(SOURCE),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "selection_rule": (
            "OldUnitType in {word,compound}; flag if either old surface has "
            "MeCab/Chasen particle, multiple verbs/adjectives, auxiliary or symbol."
        ),
        "reviewer": "agent:gpt-6-sol",
        "status": "research judgment, not data patch; NEED_SOURCE is unresolved",
        "counts": {
            key: sum(x["decision_class"] == key for x in items)
            for key in (
                "KEEP_LEXICAL",
                "RETYPE_LEXICAL",
                "RETYPE_CONTEXTUAL",
                "SHORTEN",
                "SHORTEN_MULTI",
                "EXPAND_CONTEXTUAL",
                "NEED_SOURCE",
            )
        },
        "items": items,
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(payload["counts"])
    print(OUT)


if __name__ == "__main__":
    main()
