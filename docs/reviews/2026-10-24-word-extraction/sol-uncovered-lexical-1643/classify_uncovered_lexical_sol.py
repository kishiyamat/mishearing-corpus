"""Classify every remaining old lexical pair by whole-unit research criteria."""

import argparse
import collections
import functools
import hashlib
import json
import sys
from pathlib import Path

DOSSIER = Path("/tmp/uncovered-word-units-lexical.json")
OUT = Path("/tmp/uncovered-lexical-sol-decisions.json")
sys.path.insert(0, "/home/kishi/.codex/worktrees/ca66/mishearing-corpus/corpus")
from corpus_api.dictionary import dictionary_entries

# Manually inspected nonnominal old compound surfaces against stored source Note.
CONTEXTUAL = {
    "coffee_break_parts_similar200610_006",  # とてもいい
    "coffee_break_parts_similar200801_001",  # どうも都知事さん
    "coffee_break_parts_similar201006_001",  # 長い都市化
    "coffee_break_parts_similar201502_007",  # この点
    "coffee_break_parts_similar201508_005",  # もう処分権
    "coffee_break_parts_similar201511_004",  # こんなの
    "coffee_break_parts_similar201610_002",  # よく四囲
    "coffee_break_parts_similar201806_003",  # この段階
    "coffee_break_parts_similar201810_002",  # 戻し等
    "coffee_break_parts_similar201903_003",  # どうか結構
    "coffee_break_parts_similar202201_002",  # ほとんど苦戦／ほんと独占
    "coffee_break_parts_similar202206_002",  # こういう名称
}
WORD_FROM_COMPOUND = {
    "coffee_break_parts_similar201008_001",  # 描く／核, both exact whole entries
    "coffee_break_parts_similar200903_009",  # ＪＢＩＣ／ぜひ
    "coffee_break_parts_similar201208_001",  # 読み上げ／お土産
    "coffee_break_parts_similar201304_007",  # 紐解ける／紐づける
    "coffee_break_parts_similar201410_008",  # 手控える／照り返る
    "coffee_break_parts_similar201505_008",  # 着手／しゃくし
    "coffee_break_parts_similar201805_009",  # おあり／終わり
}
COMPOUND_FROM_WORD = {
    "coffee_break_parts_similar200707_006",  # 平常時／正常時
    "syunkon_12835221992_001",  # 茶碗蒸し／チャー蒸し
    "www1101com_iimatugai_archive_more051128_018",  # ウナくさい／フナくさい
    "www1101iimatugai20100126_007",  # ひげそり／胃薬
    "www_1101_com_iimatugai_archive_more061211_008",  # すえまつさん
    "www_1101_com_m_iimatugai_1031_html_008",  # duplicate source
}
WORD_SOURCE_EXCEPTION = {
    "coffee_break_parts_similar201201_003",  # １０ / 党: source selects numeral as one word
    "denwadaikou_20231009_002",  # 小鳥遊 / 高無: source identifies surname
    "gakumado_10925_001",  # 英語 / A5: source identifies format name
    "grape_1466943_002",  # reverse 英語 / A5
    "girlschannel_307226_010",  # 公衆 / 子牛, latter whole animal word
    "girlschannel_307226_018",  # 倖田來未 full person name
    "komachi816730_052",  # つまようじ / マヨネーズ whole utensils/food
    "www_1101_com_iimatugai_archive_more050720_html_016",  # パソコン / おすもう
    "www_1101_com_iimatugai_archive_more050912_008",  # おたま / グラマー
    "www_1101_com_iimatugai_archive_more070523_html_010",  # ヘアピン / ナプキン
}
SINGLE_TOKEN_COMPOUND_KEEP = {
    "coffee_break_parts_similar201801_002",  # デイ・バイ・デイ is multiword idiom
    "niftykids_200408100935_013",  # ヒカキン / 皮下脂肪
    "posfie_OOEDO4_013",  # 三菱銀行 / ビチビチウンコ
    "posfie_OOEDO4_040",  # 毎日新聞 / マイルドセブン
}


def katakana(s):
    return "".join(chr(ord(c) + 96) if "ぁ" <= c <= "ゖ" else c for c in s)


def is_nominal(ts):
    return all(t["pos"].startswith(("名詞", "接頭詞")) for t in ts)


def reading_matches_tokens(ts, reading):
    return katakana("".join(t["reading"] for t in ts)) == katakana(reading)


def independent(entries):
    return [
        e
        for e in entries
        if e["features"][0]
        in ("名詞", "動詞", "形容詞", "形容動詞", "副詞", "連体詞", "感動詞")
        and e["features"][1] != "非自立"
    ]


@functools.lru_cache(None)
def component_entries(surface, reading):
    return [
        {"reading": e["reading"], "pos": e["features"][:4]}
        for e in dictionary_entries(surface)["entries"]
        if katakana(e["reading"]) == katakana(reading)
        and e["features"][0] in ("名詞", "接頭詞")
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dossier", type=Path, default=DOSSIER)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    raw = args.dossier.read_bytes()
    dossier = json.loads(raw)
    assert len(dossier["items"]) == 1643
    items = []
    for d in dossier["items"]:
        p = d["pos_profile_existing"]
        cur = d["current_pairs"]
        assert len(cur) == 1
        c = cur[0]
        old = d["old_pair"]
        assert c["Src"] == old["OldSrc"] and c["Tgt"] == old["OldTgt"]
        assert c["SrcReading"] == old["src_annotations"][0]["reading"]
        assert c["TgtReading"] == old["tgt_annotations"][0]["reading"]
        assert c["SrcStart"] == old["OldSrcStart"] and c["SrcEnd"] == old["OldSrcEnd"]
        assert c["TgtStart"] == old["OldTgtStart"] and c["TgtEnd"] == old["OldTgtEnd"]
        mid = d["MishearID"]
        old_type = old["OldUnitType"]
        st, tt = p["src_tokens"], p["tgt_tokens"]
        sx, tx = (
            independent(p["src_reading_matched_entries"]),
            independent(p["tgt_reading_matched_entries"]),
        )
        whole = bool(sx and tx)
        nominal = is_nominal(st) and is_nominal(tt)
        components_read = reading_matches_tokens(
            st, c["SrcReading"]
        ) and reading_matches_tokens(tt, c["TgtReading"])
        component_proof = (
            [component_entries(t["surface"], t["reading"]) for t in st + tt]
            if nominal and components_read
            else []
        )
        components_dictionary_proven = bool(component_proof and all(component_proof))
        if mid in CONTEXTUAL:
            typ, decision, mode = "phrase", "RETYPE_CONTEXTUAL", "SOL_INDIVIDUAL"
            reason = (
                "Source comparison contains a contrast-essential adverb, determiner, "
                "enumeration, or adjective plus an independent nominal/predicate; "
                "the complete selected span is a contextual phrase, not one lexical unit."
            )
        elif mid in WORD_FROM_COMPOUND:
            typ, decision, mode = "word", "RETYPE_WORD", "SOL_INDIVIDUAL"
            reason = (
                "Stored source compares complete single lexical words or single inflected "
                "verbs on the two sides. MeCab nonnominal splitting is not a sentence "
                "boundary; no shared context is being removed."
            )
        elif mid in COMPOUND_FROM_WORD:
            typ, decision, mode = "compound", "RETYPE_COMPOUND", "SOL_INDIVIDUAL"
            reason = (
                "Stored source compares complete internally formed lexical compounds "
                "or name plus suffix; keep every morpheme and both old readings."
            )
        elif mid in WORD_SOURCE_EXCEPTION:
            typ, decision, mode = "word", "KEEP_WORD", "SOL_INDIVIDUAL_SOURCE_WORD"
            reason = (
                "The stored source explicitly identifies the whole numeral, personal "
                "name, format code, or lexicalized everyday name as one contrasted word; "
                "MeCab segmentation is not an instruction to retype it as a productive "
                "noun chain. Both source-selected surfaces and reviewed readings remain."
            )
        elif whole:
            typ = "word"
            decision = "KEEP_WORD" if old_type == "word" else "RETYPE_WORD"
            mode = "AUTO_WHOLE_ENTRY"
            reason = (
                "Both exact whole surfaces have installed IPADIC headword entries with "
                "the pre-existing side-specific reviewed readings and independent lexical "
                "POS. The selected boundaries equal the old review and original hash; "
                "source Note supplies the utterance context. No reading is newly inferred."
            )
        elif nominal and old_type == "compound":
            if len(st) == len(tt) == 1 and mid not in SINGLE_TOKEN_COMPOUND_KEEP:
                typ, decision, mode = (
                    "word",
                    "RETYPE_WORD",
                    "SOL_INDIVIDUAL_SINGLE_NOMINAL",
                )
                reason = (
                    "Both complete source-selected forms are individual lexical words "
                    "or established acronyms/terms, with no grammar inside the pair; "
                    "the source row names their whole contrast. MeCab single-token "
                    "status alone is insufficient, so the visible whole forms and "
                    "reviewed readings were individually checked."
                )
            else:
                typ, decision = "compound", "KEEP_COMPOUND"
                mode = (
                    "SOL_INDIVIDUAL_SINGLE_NOMINAL"
                    if mid in SINGLE_TOKEN_COMPOUND_KEEP
                    else "AUTO_NOMINAL_CHAIN"
                    if components_dictionary_proven
                    else "SOURCE_NOMINAL_CHAIN"
                )
                reason = (
                    "Both selected surfaces are nominal/prefix chains with no particles "
                    "or independent predicates. Full source-selected spans and old readings "
                    "are retained. "
                    + (
                        "Every component has an exact dictionary reading/nominal POS entry "
                        "and these readings concatenate to the reviewed full reading."
                        if components_dictionary_proven
                        else "At least one component lacks unique matching dictionary support or "
                        "its MeCab best-path reading differs; source Note and existing "
                        "side-specific review reading, not that best path, support the "
                        "unit classification. This does not reconfirm original audio."
                    )
                )
                if mid in SINGLE_TOKEN_COMPOUND_KEEP:
                    reason = (
                        "Despite MeCab treating each full surface as a single unknown "
                        "nominal token, the source-selected forms contain an idiom or "
                        "internally compound organization/person/brand and noun. Keep "
                        "the conservative lexical compound subtype, original bounds, "
                        "side-specific readings, and referent notes."
                    )
        elif nominal and old_type == "word":
            proper = any("固有名詞" in t["pos"] for t in st + tt)
            single = len(st) == len(tt) == 1
            if single or proper:
                typ, decision = "word", "KEEP_WORD"
                mode = "SOURCE_SINGLE_OR_NAMED_ENTITY"
                reason = (
                    "The selected whole surfaces are standalone nominal words, "
                    "source-named entities, or lexicalized loan/name expressions; "
                    "MeCab splitting of a whole name does not authorize an inner "
                    "character diff. No functional syntax is inside the pair. "
                    "Old side-specific readings remain as reviewed, including where "
                    "the generic dictionary lacks this name or pronunciation."
                )
            else:
                typ, decision = "compound", "RETYPE_COMPOUND"
                mode = (
                    "AUTO_NOMINAL_CHAIN"
                    if components_dictionary_proven
                    else "SOURCE_NOMINAL_CHAIN"
                )
                reason = (
                    "At least one side is a transparent noun/prefix chain without a "
                    "matching whole-surface dictionary entry on both sides. Both whole "
                    "compared lexical forms, not character-only differences, are retained. "
                    "Existing readings and source Note remain unchanged."
                )
        elif old_type == "word":
            typ, decision, mode = "word", "KEEP_WORD", "SOL_INDIVIDUAL_NONNOMINAL"
            reason = (
                "Individually inspected complete source forms denote an inflected "
                "lexical word, nickname, technical term, or name on each side. "
                "Generic MeCab POS splits/unknown-word paths are not phrase evidence; "
                "no particle or independent clause is inside the selected comparison."
            )
        else:
            typ, decision, mode = (
                "compound",
                "KEEP_COMPOUND",
                "SOL_INDIVIDUAL_NONNOMINAL",
            )
            reason = (
                "Individually inspected source forms are complete derived or combined "
                "lexical expressions despite MeCab splitting one component as a verb, "
                "adverb, or conjunction. Neither side includes an independent clause "
                "requiring contextual classification. Existing readings are preserved."
            )
        evidence = {
            "source_file": d["source"].get("source_row_file")
            or d["source"].get("source_ref"),
            "source_url": d["source"].get("URL"),
            "source_note": d["source"].get("Note"),
            "source_src": d["source"].get("Src"),
            "source_tgt": d["source"].get("Tgt"),
            "old_review_reason": d["record"].get("Reason"),
            "src_tokens": st,
            "tgt_tokens": tt,
            "src_exact_reading_entries": [
                {"reading": e["reading"], "pos": e["features"][:4]} for e in sx
            ],
            "tgt_exact_reading_entries": [
                {"reading": e["reading"], "pos": e["features"][:4]} for e in tx
            ],
            "component_readings_match": components_read,
            "component_dictionary_proven": components_dictionary_proven,
            "component_exact_reading_entries": component_proof,
            "dictionary_identity": next(iter(d["dictionary_cache"].values()))[
                "dictionary_sha256"
            ],
        }
        items.append(
            {
                "MishearID": mid,
                "OriginalHash": d["OriginalHash"],
                "OldPairID": old["OldPairID"],
                "CurrentPairID": c["PairID"],
                "old_unit_type": old_type,
                "desired_unit_type": typ,
                "old_src": c["Src"],
                "old_tgt": c["Tgt"],
                "src_span": [int(c["SrcStart"]), int(c["SrcEnd"])],
                "tgt_span": [int(c["TgtStart"]), int(c["TgtEnd"])],
                "src_reading": c["SrcReading"],
                "tgt_reading": c["TgtReading"],
                "bounds_action": "KEEP_BOUNDS",
                "decision_class": decision,
                "decision_mode": mode,
                "reason": reason,
                "evidence": evidence,
                "preservation": (
                    "No adoption, sense, referent, pronunciation, or original-text "
                    "change. Keep side-specific meanings/qualifiers and old lineage."
                ),
            }
        )
    assert len({x["OldPairID"] for x in items}) == len(items) == 1643
    payload = {
        "schema": "uncovered-lexical-sol-decisions/v1",
        "reviewer": "agent:gpt-6-sol",
        "dossier_sha256": hashlib.sha256(raw).hexdigest(),
        "input_canonical_reviews_sha256": dossier["input_canonical_reviews_sha256"],
        "input_audit_sha256": dossier["input_audit_sha256"],
        "baseline_ref": dossier["baseline_ref"],
        "counts_by_decision": dict(
            collections.Counter(x["decision_class"] for x in items)
        ),
        "counts_by_mode": dict(collections.Counter(x["decision_mode"] for x in items)),
        "items": items,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(payload["counts_by_decision"])
    print(payload["counts_by_mode"])
    print(args.output)


if __name__ == "__main__":
    main()
