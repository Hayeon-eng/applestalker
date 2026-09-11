"""
copy_checker.py — 큐비 — Dotcom QA 체커 [Phase C]

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

페이지 텍스트를 '언어 불변' 값과 대조한다:
  - spec_tokens : 없으면 FAIL (누락/오기). 공백 무시(200 MP == 200MP)
  - proper_nouns: 없으면 WARN (현지어 대체 가능)
  - key_specs(선택): 기준값 vs 페이지값 대조 →
        같은 단위의 다른 값이 있으면 value_mismatch(FAIL, 예: 31 hours→29 hours),
        해당 단위 값이 아예 없으면 value_missing(WARN)
문구는 qa_messages 로 ko/en 렌더(화면 ko, 엑셀 en).
"""
from __future__ import annotations
import html as htmllib
import json
import re
from typing import Any, Dict, List, Optional

from qa_messages import render


def page_regions(html: str) -> tuple:
    """페이지 텍스트를 (본문, disclaimer/각주) 로 분리한다.
    - disclaimer/footnote/legal/cookie/terms 성격의 영역은 본문에서 떼어낸다
      → 본문 스펙 검사가 각주 참조번호(02, 03, 1965 …)나 법적고지 숫자를 오인하지 않게.
    - 각주 영역의 값(예: rated capacity 4855 mAh)은 별도(Disclaimer 스코프) 검사에 사용.
    [2026-09 속도] page_doc 의 공유 soup 을 쓰고(재파싱 없음), decompose/extract 대신 조상 검사로 제외한다."""
    try:
        import page_doc
        soup = page_doc.soup_for(html)
        kw = re.compile(r"(disclaimer|footnote|legal|terms|cookie|cp-disc|sub-disc|fineprint|fine-print)", re.I)
        # 1) 각주/법적고지 요소와 <sup> 를 한 번 훑어 모으고, 그 안의 문자열 id 집합을 만든다(조상 탐색 없이 O(n)).
        disc_els = []
        for el in soup.find_all(True):
            if el.name == "sup":
                disc_els.append(el); continue
            attrs = getattr(el, "attrs", None) or {}
            idc = " ".join(filter(None, [str(attrs.get("id", "") or "")] + list(attrs.get("class") or [])))
            if idc and kw.search(idc):
                disc_els.append(el)
        disc_string_ids = set()
        disc_parts = []
        for el in disc_els:
            if el.name != "sup":
                disc_parts.append(page_doc.text_of(el))
            for st_ in el.strings:
                disc_string_ids.add(id(st_))
        # 2) 본문 = 전체 문자열 − (각주/sup 내부 문자열) − script/style
        body = re.sub(r"\s+", " ", " ".join(str(x) for x in page_doc.visible_strings(soup) if id(x) not in disc_string_ids))
        disc = re.sub(r"\s+", " ", " ".join(disc_parts))
        return body, disc
    except Exception:
        t = _strip(html)
        return t, ""


def _strip(html: str) -> str:
    t = re.sub(r"<script[\s\S]*?</script>", " ", html or "", flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def page_text(html: str) -> str:
    body, _ = page_regions(html)
    return body


# 단위 신뢰도: STRONG=값이 다르면 오류로 볼 만큼 고유 / WEAK=페이지에 무관한 숫자가 흔해 오탐 위험
_WEAK_UNITS = {"x", "mm", "min", "meter", "w", "%", "°"}


def _present(token: str, text: str) -> bool:
    pat = re.escape(token).replace(r"\ ", r"\s?")
    return re.search(pat, text, re.IGNORECASE) is not None


# 단위 → 페이지에서 값 뽑을 정규식 조각(대소문자 무시). inch 는 " ” 도 허용.
_UNIT_RX = {
    "inch": r"(?:inch|”|\")", "nits": r"nits?", "hz": r"Hz", "mp": r"MP",
    "x": r"[x×]", "hours": r"hours?", "gb": r"GB", "tb": r"TB", "mah": r"mAh",
    "w": r"W", "mm": r"mm", "min": r"min",
}


def _values_with_unit(text: str, unit: str) -> List[str]:
    u = _UNIT_RX.get((unit or "").lower())
    if not u:
        return []
    if unit.lower() == "x":  # 줌: 숫자 뒤 x
        rx = re.compile(r"(\d+(?:\.\d+)?)\s?" + u, re.I)
    else:
        rx = re.compile(r"(\d+(?:\.\d+)?)\s?" + u, re.I)
    return [m.group(1) for m in rx.finditer(text)]


def _norm_num(s: str) -> str:
    """숫자 표기 정규화: 콤마·공백 제거, 전각→반각. '2,600'→'2600', '2 600'→'2600'."""
    s = str(s)
    trans = {ord(c): ord(c) - 0xFEE0 for c in "０１２３４５６７８９"}
    s = s.translate(trans)
    return re.sub(r"[,\s]", "", s)


def _num_present(num: str, unit: str, text: str) -> bool:
    """숫자+단위가 페이지에 있는지 — 콤마·공백 표기차 흡수(2,600 nits == 2600 nits),
    소수점(6.9, 1.5)도 정확히 처리."""
    u = _UNIT_RX.get((unit or "").lower())
    # 숫자를 글자 단위로 조립: 자릿수 사이엔 천단위 콤마/공백 허용, 소수점(.)은 그대로
    pat = ""
    for ch in str(num):
        if ch.isdigit():
            pat += re.escape(ch) + r"[,\s]*"
        else:
            pat += re.escape(ch)
    if u:
        rx = re.compile(pat + r"\s?" + u, re.I)
    else:
        rx = re.compile(pat, re.I)
    return rx.search(text) is not None


def _values_with_unit(text: str, unit: str) -> List[str]:
    u = _UNIT_RX.get((unit or "").lower())
    if not u:
        return []
    rx = re.compile(r"(\d[\d,\s]*(?:\.\d+)?)\s?" + u, re.I)
    return [_norm_num(m.group(1)) for m in rx.finditer(text)]


def _finalize(f: Dict[str, Any], code: str, lang: str = "ko") -> Dict[str, Any]:
    f["code"] = code
    msg = render(code, lang, f)
    f["as_is"], f["to_be"] = msg["as_is"], msg["to_be"]
    return f


def check_copy(html: str, product_rules: Dict[str, Any],
               key_specs: Optional[List[Dict[str, Any]]] = None, lang: str = "ko",
               page_type: str = "PDP") -> Dict[str, Any]:
    body, disc = page_regions(html)
    text = body  # 본문 스펙은 본문에서만 검사(각주 숫자 오인 방지)
    findings: List[Dict[str, Any]] = []
    ok = warn = fail = na = 0
    key_specs = key_specs or []
    noun_toks = product_rules.get("proper_nouns", [])

    def _scope_text(pts):
        # 스펙의 적용 영역: Disclaimer 스코프면 각주 텍스트, 아니면 본문
        return disc if ("Disclaimer" in pts) else body

    # 0) 수집 품질 가드 (본문 기준)
    exp = [s for s in key_specs if page_type in (s.get("page_types") or ["PDP"]) or "Disclaimer" in (s.get("page_types") or [])]
    def _spec_present(s):
        vals = [str(v) for v in (s.get("values") or [])]; unit = s.get("unit", "")
        t = _scope_text(s.get("page_types") or ["PDP"])
        return any(_num_present(_norm_num(v), unit, t) if v[:1].isdigit() else _present(v, t) for v in vals)
    present_cnt = sum(1 for s in exp if _spec_present(s))
    if exp and (len(body) < 1500 or present_cnt == 0):
        ko = lang != "en"
        findings.append({"kind": "collection", "token": "(collection quality)", "status": "fail", "code": "copy.collection",
            "as_is": (f"페이지 텍스트가 비정상적으로 적음(본문 {len(body):,}자, 기대 스펙 {present_cnt}/{len(exp)} 검출)"
                      if ko else f"Page text abnormally small ({len(body):,} chars, {present_cnt}/{len(exp)} expected specs found)"),
            "to_be": ("수집 실패/차단 또는 JS 미렌더링 가능성 — 재수집(JS 렌더링) 후 재검수." if ko
                      else "Likely fetch failure/block or non-rendered JS — re-crawl (with JS) then re-check.")})
        return {"summary": {"keyspec_total": len(key_specs), "pass": 0, "warn": 0, "fail": 1, "na": 0,
                            "value_mismatch": 0, "value_missing": 0, "text_len": len(body),
                            "collection_suspect": True}, "findings": findings}

    # 1) 핵심 스펙 값 대조
    vmis = vmiss = 0
    for s in key_specs:
        cat = s.get("category", ""); unit = s.get("unit", "")
        vals = [str(v) for v in (s.get("values") or []) if str(v).strip()]
        pts = s.get("page_types") or ["PDP"]
        if not vals:
            continue
        is_disc = "Disclaimer" in pts
        region = "disclaimer" if is_disc else "본문"
        scope = _scope_text(pts)
        exp_label = " / ".join(f"{v}{(' ' + unit) if unit else ''}" for v in vals)
        # (a) 이 페이지타입에서 기대하지 않는 스펙(디스클레이머 스코프는 페이지타입 무관하게 검사)
        if not is_disc and page_type not in pts:
            na += 1
            findings.append({"kind": "spec_value", "token": cat, "category": cat, "expected": exp_label,
                             "region": region, "status": "na", "code": "copy.na",
                             "as_is": (f"{cat}: 이 페이지타입({page_type})엔 해당 없음" if lang != "en" else f"{cat}: N/A on {page_type}"),
                             "to_be": ""})
            continue
        is_num = vals[0][:1].isdigit()
        present = any(_num_present(_norm_num(v), unit, scope) if is_num else _present(v, scope) for v in vals)
        base = {"kind": "spec_value", "token": cat, "category": cat, "expected": exp_label, "region": region}
        if present:
            ok += 1
            findings.append({**base, "status": "pass", "as_is": "", "to_be": "", "code": "copy.value_ok"})
            continue
        # 같은 단위의 '다른 값'이 있으면 값 불일치(오류) — 단, 신뢰도 낮은 단위(x/mm/% 등)는 오탐이 많아 오류로 안 봄
        weak = (unit or "").lower() in _WEAK_UNITS
        others = sorted(set(_values_with_unit(scope, unit)) - {_norm_num(v) for v in vals}) if (unit and is_num and not weak) else []
        if others:
            fail += 1; vmis += 1
            findings.append(_finalize({**base, "found": others, "status": "fail"}, "copy.value_mismatch", lang))
        else:
            warn += 1; vmiss += 1
            findings.append(_finalize({**base, "status": "warn"}, "copy.value_missing", lang))

    # 2) 고유명사 존재(WARN) — 본문+각주 합쳐서 확인
    all_text = body + " " + disc
    for pn in noun_toks:
        hit = _present(pn, all_text)
        ok += hit; warn += (not hit)
        f = {"kind": "proper_noun", "token": pn, "region": "본문", "status": "pass" if hit else "warn"}
        findings.append(_finalize(f, "copy.noun_missing", lang) if not hit else {**f, "as_is": "", "to_be": "", "code": "copy.noun_ok"})

    return {"summary": {"keyspec_total": len(key_specs), "pass": ok, "warn": warn, "fail": fail, "na": na,
                        "value_mismatch": vmis, "value_missing": vmiss, "text_len": len(body)},
            "findings": findings}


if __name__ == "__main__":
    import sys
    rules = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "copy_rules.json", encoding="utf-8"))
    html = open(sys.argv[2] if len(sys.argv) > 2 else "/mnt/user-data/uploads/index.html", encoding="utf-8", errors="ignore").read()
    product = sys.argv[3] if len(sys.argv) > 3 else "M3"
    try:
        ks = json.load(open("key_specs.json", encoding="utf-8"))["products"].get("galaxy-s26-ultra", [])
    except Exception:
        ks = []
    res = check_copy(html, rules["products"][product], key_specs=ks)
    s = res["summary"]
    print(f"스펙 {s['spec_total']} · 고유명사 {s['noun_total']} · 핵심스펙 {s['keyspec_total']} "
          f"→ PASS {s['pass']} / WARN {s['warn']} / FAIL {s['fail']} (값불일치 {s['value_mismatch']})")
    for f in res["findings"]:
        if f["status"] != "pass":
            print(f"  [{f['status']}] {f.get('kind')}: {f['as_is']}  → {f['to_be']}")
