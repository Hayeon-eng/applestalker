"""
qa_messages.py — 큐비 — 검수 문구 한/영 렌더러

체커는 문구 문자열 대신 finding 에 code + 구조화 필드를 담고,
화면은 ko, 엑셀 리포트는 en 으로 이 함수가 렌더한다.

render(code, lang, f) -> {"as_is": str, "to_be": str}
  f: finding dict (필요한 파라미터 필드 포함)
"""
from __future__ import annotations
from typing import Any, Dict


def _join(v):
    return ", ".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v)


def render(code: str, lang: str, f: Dict[str, Any]) -> Dict[str, str]:
    ko = lang != "en"
    name = f.get("block", "")
    types = "/".join(f.get("types", []) or [])
    idslug = f.get("id_slug", "")

    if code == "schema.pass":
        return {"as_is": (f"{name} 정상" if ko else f"{name} OK"), "to_be": ""}

    if code == "schema.missing":
        if f.get("conditional"):
            return {
                "as_is": (f"{name} 스키마 없음" if ko else f"{name} schema not found"),
                "to_be": (f"조건부 항목({name}) — 해당 국가에 필요하면 추가"
                          if ko else f"Conditional block ({name}) — add if required for this locale"),
            }
        return {
            "as_is": (f"{name} 스키마 없음" if ko else f"{name} schema not found"),
            "to_be": (f"@type={types}, @id={idslug} 형태로 {name} 스키마 추가"
                      if ko else f"Add {name} schema with @type={types}, @id={idslug}"),
        }

    if code == "schema.optional":
        soft = _join(f.get("optional_missing", []))
        tc = f.get("translate_confirm") or []
        bits_as, bits_to = [], []
        if soft:
            bits_as.append(f"{name} 정상 (선택 속성 미적용: {soft})" if ko else f"{name} OK (optional not set: {soft})")
            bits_to.append(f"선택 항목 — {soft}: 필요 시 추가 검토" if ko else f"Optional — consider adding: {soft}")
        for t in tc:
            av = str(t.get("actual", ""))
            bits_as.append(f"{t['prop']} 번역 확인 필요 (현재 '{av}')" if ko else f"{t['prop']} translation check (currently '{av}')")
            bits_to.append(f"{t['prop']} 가 현지어로 올바르게 번역됐는지 확인 (오류 아님)" if ko else f"Confirm {t['prop']} is correctly localized (not an error)")
        for prop in (f.get("array_where_object") or []):
            bits_as.append(f"{prop} 가 배열([...])로 되어 있음 — Google은 허용, 가이드는 object 권장"
                           if ko else f"{prop} is an array — Google allows it, guide recommends a single object")
            bits_to.append(f"{prop} 를 단일 object({{'@id':…}})로 정리 권장 (오류 아님)"
                           if ko else f"Prefer a single object for {prop} (not an error)")
        for li in (f.get("lang_issue") or []):
            bits_as.append(f"페이지 언어({li['prop']}={li['actual']})가 사이트 언어({li['expected']})와 다름"
                           if ko else f"inLanguage {li['actual']} differs from site language {li['expected']}")
            bits_to.append(f"의도된 현지화면 정상, 아니면 {li['expected']} 로 수정 (경고)"
                           if ko else f"OK if intended; otherwise set to {li['expected']}")
        if not bits_as:
            bits_as.append(f"{name} 정상" if ko else f"{name} OK")
        return {"as_is": " / ".join(bits_as), "to_be": "; ".join(bits_to)}

    if code == "schema.parse_error":
        ln = f.get("parse_lineno"); col = f.get("parse_colno"); msg = f.get("parse_msg", "")
        line = f.get("parse_line", "")
        cat = f.get("syntax_category", "syntax"); hint = f.get("syntax_hint", "")
        cat_ko = {"smart_quote": "스마트 따옴표", "invisible_char": "비표시 문자",
                  "missing_comma": "쉼표 누락", "trailing_comma": "후행 쉼표",
                  "unbalanced": "괄호 불균형", "unescaped": "이스케이프 오류",
                  "syntax": "문법 오류"}.get(cat, "문법 오류")
        loc = (f"{ln}행 {col}열" if ln else "위치 미상"); loc_en = (f"line {ln}, col {col}" if ln else "unknown position")
        snip = (f" · 문제 줄: {line}" if line else ""); snip_en = (f" · offending line: {line}" if line else "")
        tag = "[Google Rich Result 기준]"
        return {
            "as_is": (f"{tag} JSON-LD {cat_ko} — {loc}에서 {msg}{snip}" if ko
                      else f"[Google Rich Result] JSON-LD {cat} — {msg} at {loc_en}{snip_en}"),
            "to_be": (hint or ("해당 줄 문법 수정 — 후행 콤마·따옴표·중괄호 확인" if ko else "Fix syntax — commas/quotes/braces")),
        }

    if code == "schema.na":
        return {"as_is": f.get("as_is", ""), "to_be": ""}

    if code == "schema.problem":
        bits, fixes = [], []
        if f.get("id_mismatch"):
            bits.append(("@id 불일치(" if ko else "@id mismatch (") + str(f["id_mismatch"]) + ")")
            fixes.append((f"@id 를 {idslug} 규칙에 맞게 수정" if ko else f"Fix @id to match {idslug}"))
        if f.get("missing_props"):
            mp = _join(f["missing_props"])
            bits.append(("누락 속성: " if ko else "Missing properties: ") + mp)
            fixes.append((f"{name}에 {mp} 속성 추가" if ko else f"Add {mp} to {name}"))
        if f.get("haspart_missing"):
            hp = _join(f["haspart_missing"])
            bits.append(("hasPart 누락: " if ko else "hasPart missing: ") + hp)
            fixes.append(("Product.hasPart 에 " + hp + " @id 추가" if ko else f"Add @id {hp} to Product.hasPart"))
        for vm in (f.get("val_mismatch") or []):
            if ko:
                bits.append(f"{vm['prop']} 값 불일치(기대 '{vm['expected']}' / 실제 '{vm['actual']}')")
                fixes.append(f"{vm['prop']} 값을 '{vm['expected']}' 로 수정")
            else:
                bits.append(f"{vm['prop']} value mismatch (expected '{vm['expected']}', actual '{vm['actual']}')")
                fixes.append(f"Correct {vm['prop']} to '{vm['expected']}'")
        for ni in (f.get("name_issue") or []):
            miss = ", ".join(ni.get("missing") or []); bad = ", ".join(ni.get("forbidden") or [])
            if ko:
                parts = []
                if miss: parts.append(f"'{miss}' 누락")
                if bad: parts.append(f"다른 모델명 '{bad}' 혼입")
                bits.append(f"제품명 오기 — {' · '.join(parts)} (현재 '{ni['actual']}')")
                fixes.append(f"제품명에 '{miss or ''}'{' 포함' if miss else ''}{(' · ' + bad + ' 제거') if bad else ''} — 올바른 제품명으로 수정")
            else:
                bits.append(f"name error (current '{ni['actual']}')")
                fixes.append("Fix product name")
        return {"as_is": f"{name} — " + " / ".join(bits), "to_be": "; ".join(fixes)}

    if code == "copy.spec_missing":
        tok = f.get("token", "")
        return {
            "as_is": (f"스펙 '{tok}' 이(가) 페이지에 없음" if ko else f"Spec '{tok}' not found on page"),
            "to_be": (f"기준값 '{tok}' 이(가) 페이지에 노출되는지 확인(누락/오기)"
                      if ko else f"Verify spec value '{tok}' appears on the page (missing/typo)"),
        }

    if code == "copy.noun_missing":
        pn = f.get("token", "")
        return {
            "as_is": (f"고유명사 '{pn}' 미검출" if ko else f"Proper noun '{pn}' not found"),
            "to_be": (f"'{pn}' 이(가) 현지어로 대체됐는지/누락인지 확인(영문 유지 대상일 수 있음)"
                      if ko else f"Check if '{pn}' was localized or omitted (should usually remain in English)"),
        }

    if code == "copy.value_mismatch":
        cat = f.get("category", ""); exp = f.get("expected", ""); found = _join(f.get("found", []))
        return {
            "as_is": (f"{cat}: 기준 '{exp}' 인데 페이지엔 '{found}'" if ko else f"{cat}: expected '{exp}' but page shows '{found}'"),
            "to_be": (f"{cat} 값을 기준 '{exp}' 로 수정(오기 의심)" if ko else f"Correct {cat} to '{exp}' (suspected typo)"),
        }

    if code == "copy.value_missing":
        cat = f.get("category", ""); exp = f.get("expected", "")
        return {
            "as_is": (f"{cat}: 기준값 '{exp}' 이(가) 페이지에 없음" if ko else f"{cat}: expected value '{exp}' not found on page"),
            "to_be": (f"{cat} 기준값 '{exp}' 노출 여부 확인" if ko else f"Verify {cat} value '{exp}' appears on the page"),
        }

    if code == "copy.na":
        cat = f.get("category", "")
        return {
            "as_is": (f"{cat}: 이 페이지타입엔 해당 없음" if ko else f"{cat}: not applicable on this page type"),
            "to_be": "",
        }

    if code == "copy.collection":
        return {
            "as_is": (f.get("as_is", "") if ko else "Page text abnormally short — likely collection failure or unrendered JS"),
            "to_be": (f.get("to_be", "") if ko else "Recrawl with JS rendering, then re-run QA"),
        }

    return {"as_is": f.get("as_is", ""), "to_be": f.get("to_be", "")}