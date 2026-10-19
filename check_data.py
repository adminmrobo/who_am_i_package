#!/usr/bin/env python3
"""who_am_i 데이터 검사기.

사용법:
  python3 check_data.py            # 모든 언어 검사
  python3 check_data.py en ja      # 지정한 언어만 검사

한국어 원본(data/profile.ko.json)을 기준으로 번역 파일(data/profile.<lang>.json)이
구조·고정값·자리표시·HTML 태그·용어 일관성을 지키는지 확인한다.
문제가 하나라도 있으면 종료 코드 1을 돌려준다.
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
LANGS = ["en", "zh", "ja", "uz", "ru"]

# 번역하지 않고 원본과 똑같아야 하는 키 (값이 문자열·숫자·불리언 모두 포함)
FIXED_KEYS = {
    "updated", "who", "mood", "from", "to", "date", "no", "app", "filed", "reg",
    "img", "field", "kind", "roleType", "solo", "minister", "hackathon", "url", "h1small",
}
# 원본과 똑같아야 하는 특정 경로 (고유 명칭)
FIXED_PATHS = {
    "ui.names.robo", "ui.toc.robo", "about.infoH",
    "about.links[0].label", "about.links[1].label", "about.links[2].label", "about.links[3].label",
}
HANGUL = re.compile(r"[가-힣ㄱ-ㆎ]")
PH = re.compile(r"\{[a-zA-Z]+\}")
TAG = re.compile(r"</?[a-zA-Z]+(?:\s[^>]*)?>")


def walk(a, b, path, errs, lang, pairs):
    if isinstance(a, dict):
        if not isinstance(b, dict):
            errs.append(f"{path}: 객체여야 함"); return
        if set(a) != set(b):
            miss = set(a) - set(b); extra = set(b) - set(a)
            if miss: errs.append(f"{path}: 빠진 키 {sorted(miss)}")
            if extra: errs.append(f"{path}: 남는 키 {sorted(extra)}")
        for k in a:
            if k in b:
                walk(a[k], b[k], f"{path}.{k}" if path else k, errs, lang, pairs)
        return
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            errs.append(f"{path}: 목록 길이가 원본({len(a)})과 다름 ({len(b) if isinstance(b, list) else '목록 아님'})"); return
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", errs, lang, pairs)
        return
    key = re.sub(r"\[\d+\]$", "", path).split(".")[-1]
    if key in FIXED_KEYS or path in FIXED_PATHS:
        if a != b:
            errs.append(f"{path}: 고정값이 바뀜 ({a!r} → {b!r})")
        return
    if path == "meta.lang":
        if b != lang: errs.append(f"meta.lang 은 '{lang}' 이어야 함")
        return
    if isinstance(a, str):
        if not isinstance(b, str) or (a.strip() and not b.strip()):
            errs.append(f"{path}: 비어 있거나 문자열이 아님"); return
        if sorted(PH.findall(a)) != sorted(PH.findall(b)):
            errs.append(f"{path}: 자리표시 불일치 {PH.findall(a)} → {PH.findall(b)}")
        if sorted(TAG.findall(a)) != sorted(TAG.findall(b)):
            errs.append(f"{path}: HTML 태그 불일치 {TAG.findall(a)} → {TAG.findall(b)}")
        if lang != "ko" and HANGUL.search(b):
            errs.append(f"{path}: 한국어가 남음 → {b[:60]}")
        pairs.setdefault(a, set()).add(b)


def check(lang, ko):
    p = DATA / f"profile.{lang}.json"
    if not p.exists():
        return [f"{p.name} 없음"]
    try:
        tr = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"{p.name}: JSON 오류 {e}"]
    errs, pairs = [], {}
    walk(ko, tr, "", errs, lang, pairs)
    # 같은 한국어 문장 = 같은 번역 하나 (학교 이름처럼 반복되는 값이 같아야 개수 집계가 맞는다)
    by_school = {}
    for x, y in zip(ko["teach"]["items"], tr["teach"]["items"]):
        by_school.setdefault(x["school"], set()).add(y["school"])
    for s, v in by_school.items():
        if len(v) > 1:
            errs.append(f"teach.items.school: 같은 학교 '{s}'의 번역이 여러 개 {sorted(v)}")
    # 서로 다른 학교가 같은 번역으로 합쳐지면 안 된다
    rev = {}
    for x, y in zip(ko["teach"]["items"], tr["teach"]["items"]):
        rev.setdefault(y["school"], set()).add(x["school"])
    for s, v in rev.items():
        if len(v) > 1:
            errs.append(f"teach.items.school: 다른 학교 {sorted(v)}가 같은 번역 '{s}'로 합쳐짐")
    for src, outs in pairs.items():
        if len(outs) > 1 and len(src) <= 40:
            errs.append(f"같은 원문의 번역이 여러 개: '{src}' → {sorted(outs)}")
    return errs


def main():
    ko = json.loads((DATA / "profile.ko.json").read_text(encoding="utf-8"))
    errs0 = []
    walk(ko, ko, "", errs0, "ko", {})
    langs = sys.argv[1:] or LANGS
    bad = 0
    for lang in langs:
        errs = check(lang, ko)
        if errs:
            bad += 1
            print(f"[{lang}] 문제 {len(errs)}건")
            for e in errs[:80]:
                print("  -", e)
        else:
            print(f"[{lang}] 통과")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
