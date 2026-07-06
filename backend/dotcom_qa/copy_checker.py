"""
copy_checker.py — 큐비 — Dotcom QA 체커 [Phase C]

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

페이지 HTML의 '보이는 텍스트'를 copy_rules(스펙 토큰 + 고유명사)와 대조한다.
번역 사이트를 고려해 '언어 불변' 값만 검사한다:
  - spec_tokens : 없으면 FAIL (스펙 누락/오기). 공백 유무는 무시(200 MP == 200MP)
  - proper_nouns: 없으면 WARN (현지어로 대체됐을 수 있어 소프트 경고)
서술형 문장 자체는 == 검사하지 않는다.
"""
from __future__ import annotations
import html as htmllib
import json
import re
from typing import Any, Dict, List


def page_text(html: str) -> str:
    """HTML에서 script/style 제거 후 보이는 텍스트만 정규화."""
    t = re.sub(r"<script[\s\S]*?</script>", " ", html or "", flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def _present(token: str, text: str) -> bool:
    # 숫자-단위 사이 공백 유무 무시하여 매칭 (200 MP == 200MP)
    pat = re.escape(token).replace(r"\ ", r"\s?")
    return re.search(pat, text, re.IGNORECASE) is not None


def check_copy(html: str, product_rules: Dict[str, Any]) -> Dict[str, Any]:
    text = page_text(html)
    findings: List[Dict[str, Any]] = []
    ok = warn = fail = 0

    for tok in product_rules.get("spec_tokens", []):
        hit = _present(tok, text)
        if hit:
            ok += 1
        else:
            fail += 1
        findings.append({
            "kind": "spec", "token": tok, "status": "pass" if hit else "fail",
            "as_is": ("" if hit else f"스펙 '{tok}' 이(가) 페이지에 없음"),
            "to_be": ("" if hit else f"카피덱 기준 '{tok}' 값이 페이지에 노출되는지 확인(누락/오기 점검)"),
        })

    for pn in product_rules.get("proper_nouns", []):
        hit = _present(pn, text)
        if hit:
            ok += 1
        else:
            warn += 1
        findings.append({
            "kind": "proper_noun", "token": pn, "status": "pass" if hit else "warn",
            "as_is": ("" if hit else f"고유명사 '{pn}' 미검출"),
            "to_be": ("" if hit else f"'{pn}' 이(가) 현지어로 대체됐는지/누락인지 확인(영문 유지 대상일 수 있음)"),
        })

    return {
        "summary": {
            "spec_total": len(product_rules.get("spec_tokens", [])),
            "noun_total": len(product_rules.get("proper_nouns", [])),
            "pass": ok, "warn": warn, "fail": fail, "text_len": len(text),
        },
        "findings": findings,
    }


if __name__ == "__main__":
    import sys
    rules_path = sys.argv[1] if len(sys.argv) > 1 else "copy_rules.json"
    html_path = sys.argv[2] if len(sys.argv) > 2 else "/mnt/user-data/uploads/index.html"
    product = sys.argv[3] if len(sys.argv) > 3 else "M3"

    rules = json.load(open(rules_path, encoding="utf-8"))
    html = open(html_path, encoding="utf-8", errors="ignore").read()
    res = check_copy(html, rules["products"][product])
    s = res["summary"]
    print(f"검수 대상: {html_path.rsplit('/',1)[-1]}  (규칙: {product})")
    print(f"스펙 {s['spec_total']} · 고유명사 {s['noun_total']} → PASS {s['pass']} / WARN {s['warn']} / FAIL {s['fail']}\n")
    icon = {"pass": "✅", "warn": "⚠️ ", "fail": "❌"}
    for f in res["findings"]:
        if f["status"] == "pass":
            continue
        print(f"{icon[f['status']]} [{f['kind']}] {f['token']}")
        print(f"      to-be: {f['to_be']}")
