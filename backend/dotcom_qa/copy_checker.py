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


def page_text(html: str) -> str:
    t = re.sub(r"<script[\s\S]*?</script>", " ", html or "", flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


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


def _finalize(f: Dict[str, Any], code: str, lang: str = "ko") -> Dict[str, Any]:
    f["code"] = code
    msg = render(code, lang, f)
    f["as_is"], f["to_be"] = msg["as_is"], msg["to_be"]
    return f


def check_copy(html: str, product_rules: Dict[str, Any],
               key_specs: Optional[List[Dict[str, Any]]] = None, lang: str = "ko") -> Dict[str, Any]:
    text = page_text(html)
    findings: List[Dict[str, Any]] = []
    ok = warn = fail = 0

    # 1) 스펙 토큰 존재
    for tok in product_rules.get("spec_tokens", []):
        hit = _present(tok, text)
        ok += hit; fail += (not hit)
        f = {"kind": "spec", "token": tok, "status": "pass" if hit else "fail"}
        findings.append(_finalize(f, "copy.spec_missing", lang) if not hit else {**f, "as_is": "", "to_be": "", "code": "copy.spec_ok"})

    # 2) 고유명사 존재
    for pn in product_rules.get("proper_nouns", []):
        hit = _present(pn, text)
        ok += hit; warn += (not hit)
        f = {"kind": "proper_noun", "token": pn, "status": "pass" if hit else "warn"}
        findings.append(_finalize(f, "copy.noun_missing", lang) if not hit else {**f, "as_is": "", "to_be": "", "code": "copy.noun_ok"})

    # 3) 핵심 스펙 값 대조 (31 hours 인데 29 hours 로 들어간 오기 검출)
    vmiss = vmis = 0
    for spec in (key_specs or []):
        cat = spec.get("category", ""); val = str(spec.get("value", "")).strip(); unit = spec.get("unit", "")
        expected = (val + (" " + unit if unit else "")).strip()
        if not val:
            continue
        vals = _values_with_unit(text, unit) if unit else []
        present = (val in vals) or _present(expected, text) or (not unit and _present(val, text))
        if present:
            ok += 1
            findings.append({"kind": "spec_value", "token": cat, "category": cat, "expected": expected,
                             "status": "pass", "as_is": "", "to_be": "", "code": "copy.value_ok"})
            continue
        found = sorted(set(v for v in vals if v != val))
        if found:
            fail += 1; vmis += 1
            f = {"kind": "spec_value", "token": cat, "category": cat, "expected": expected,
                 "found": found, "status": "fail"}
            findings.append(_finalize(f, "copy.value_mismatch", lang))
        else:
            warn += 1; vmiss += 1
            f = {"kind": "spec_value", "token": cat, "category": cat, "expected": expected, "status": "warn"}
            findings.append(_finalize(f, "copy.value_missing", lang))

    return {
        "summary": {
            "spec_total": len(product_rules.get("spec_tokens", [])),
            "noun_total": len(product_rules.get("proper_nouns", [])),
            "keyspec_total": len(key_specs or []),
            "pass": ok, "warn": warn, "fail": fail,
            "value_mismatch": vmis, "value_missing": vmiss, "text_len": len(text),
        },
        "findings": findings,
    }


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
