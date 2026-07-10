"""
spec_engine.py — 큐비 — Spec QA [V2] Step 5~9
Dictionary Mapping → Normalization → Validation → Exception → QA Result(+Rule Trace)

원칙
  · Deterministic: AI 추론 없음. 같은 입력 → 항상 같은 결과.
  · Context 우선: Section → Attribute → Value 순으로 좁혀서 비교 (Typical vs Rated FP 방지)
  · 모든 판정에 trace(판정 과정)를 남겨 사람이 검증 가능하게 한다.
  · 기존 copy_checker/score는 건드리지 않는다 — 결과는 별도 spec_v2 구조.

결과 구조
  {
    "summary": {"score", "critical", "warning", "pass", "na", "total"},
    "categories": [{"category","score","pass","fail","warn","na","total"}],
    "items": [{
        "rule_id","category","attribute","priority","page","validation",
        "expected","unit","status"(pass|fail|warn|na),
        "found","matched_alias","section","source",
        "fix_guide","message","trace":[{"step","detail"}...]
    }],
    "candidates": [ … AI/미등록 표현 후보(3단계에선 규칙기반 자리만) ]
  }
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

import spec_extractor

# ── Normalization (Step 6) ────────────────────────────────────────────
_UNICODE_MAP = {
    "\u2011": "-", "\u2010": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",  # 하이픈류
    "\u00d7": "x", "\u2715": "x", "\u2716": "x",                                # ×
    "\u00a0": " ", "\u202f": " ", "\u2009": " ",                                # 공백류
}


def _norm(s: str) -> str:
    """기본 정규화: 유니코드 통일 → 소문자 → 천단위 구분자 제거 → 공백 압축.
    천단위: 5,000(EN) · 4.400(DE/ES 등) · 4 400(FR 좁은공백 포함) 모두 → 4400.
    소수점 오인 방지: '뒤에 정확히 3자리 숫자'일 때만 구분자로 본다(8.0 inch, 5.4 등은 보존)."""
    s = str(s or "")
    for k, v in _UNICODE_MAP.items():
        s = s.replace(k, v)
    s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s)   # 5,000 / 4,300mAh → 5000 / 4300mah
    s = re.sub(r"(?<=\d)\.(?=\d{3}(?!\d))", "", s)  # 4.400 → 4400 (DE) · 5.4/8.0은 보존
    s = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", s)   # 4 400 → 4400 (FR — 좁은공백은 위에서 일반공백화)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _norm_loose(s: str) -> str:
    """느슨한 정규화(Dictionary 비교용): 모든 스크립트의 문자·숫자만 남김.
    Wi-Fi/WiFi → wifi, '배터리 용량(일반)' → '배터리용량일반', Akkukapazität의 ä 보존."""
    return re.sub(r"[^\w]|_", "", _norm(s))


def _num(s: str) -> Optional[float]:
    m = re.search(r"-?\d+(?:\.\d+)?", _norm(s))
    return float(m.group()) if m else None


def _nums(s: str) -> List[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", _norm(s))]


# ── Dictionary Mapping (Step 5) ───────────────────────────────────────
def _aliases_for(rule: Dict[str, Any], dictionary: Dict[str, List[str]]) -> List[str]:
    """이 룰의 Attribute를 대표로 하는 모든 표현(대표 + Alias).
    대표어가 attribute의 부분어여도 상속한다 — 예: Dictionary 대표 'Storage'(alias
    'Internal Storage')는 attribute 'Storage Option'에도 적용된다."""
    attr = rule["attribute"]
    na = _norm_loose(attr)
    out = [attr]
    for rep, aliases in (dictionary or {}).items():
        nr = _norm_loose(rep)
        if nr and (nr == na or nr in na):
            out.append(rep)
            out += aliases
    return list(dict.fromkeys(out))


def _forbidden_aliases(rule: Dict[str, Any], all_rules: List[Dict], dictionary: Dict) -> List[str]:
    """Exception(예: 'Do not compare with Rated') → 비교 금지 대상 attribute의 alias 목록.
    같은 카테고리의 다른 룰만 대상으로 한다 — 'Typical value tested'(Disclaimer 문구 룰)처럼
    단어만 겹치는 다른 카테고리 룰까지 차단하는 과잉 방지."""
    exc = _norm(rule.get("exception", ""))
    if "do not compare" not in exc and "비교 금지" not in exc:
        return []
    out = []
    for other in all_rules:
        if other["rule_id"] == rule["rule_id"]:
            continue
        if other.get("category") != rule.get("category"):
            continue
        # exception 문구에 상대 attribute의 핵심 단어가 들어있으면 금지 대상
        key = _norm(other["attribute"]).split()[0]  # rated / typical …
        if key and key in exc:
            out += _aliases_for(other, dictionary)
    return out


# ── Validation (Step 7) ───────────────────────────────────────────────
def _validate(vtype: str, expected: str, unit: str, found: str,
              section_text: str = "") -> Tuple[bool, str]:
    """(pass여부, 비교 설명) — 비교 설명은 trace에 그대로 들어간다."""
    e, f = _norm(expected), _norm(found)
    if vtype == "exact":
        ok = e == f or e in f
        return ok, f"exact: '{e}' vs '{f}'"
    if vtype == "numeric_exact":
        en, fn = _num(expected), _num(found)
        ok = en is not None and fn is not None and en == fn
        return ok, f"numeric: {en} vs {fn}"
    if vtype == "prefix":
        ok = bool(f) and _norm_loose(f).startswith(_norm_loose(expected))
        return ok, f"prefix: '{e}*' vs '{f}'"
    if vtype == "dictionary":
        ok = _norm_loose(expected) == _norm_loose(found) or _norm_loose(expected) in _norm_loose(found)
        return ok, f"dictionary(loose): '{_norm_loose(expected)}' vs '{_norm_loose(found)}'"
    if vtype == "option_match":
        # '256 / 512 / 1TB' → 각 옵션이 found(또는 섹션 텍스트)에 모두 존재해야 함
        opts = [o.strip() for o in re.split(r"[/,]", expected) if o.strip()]
        hay = _norm_loose(found + " " + section_text)
        missing = []
        for o in opts:
            token = _norm_loose(o)
            token_u = _norm_loose(o + (unit or ""))  # 256 → 256gb 도 허용
            if token not in hay and token_u not in hay:
                missing.append(o)
        return (not missing), ("options all present" if not missing
                               else f"missing options: {', '.join(missing)}")
    if vtype == "exists":
        hay = _norm_loose(found + " " + section_text)
        ok = bool(_norm_loose(expected)) and (
            _norm_loose(expected) in hay or _norm_loose(expected) in ("present", "included", "supported"))
        # expected가 Present/Included/Supported 류면 '항목 자체 발견'이 곧 존재
        if _norm_loose(expected) in ("present", "included", "supported"):
            ok = bool(found)
        return ok, f"exists: '{e}' in page → {ok}"
    return False, f"unknown validation '{vtype}'"


# ── 페이지타입 적용 여부 ──────────────────────────────────────────────
def _applicable(rule_page: str, page_type: str) -> bool:
    """MasterSpec Page(PDP/Buy Box/Compare/Disclaimer/What's in the box, 'PDP/Compare' 복수 허용)
    vs 검수 페이지타입(PDP/Compare/Buying)."""
    pt = (page_type or "PDP").lower()
    tokens = [t.strip().lower() for t in re.split(r"[/,]", rule_page or "PDP")]
    for t in tokens:
        if t in ("pdp", "disclaimer", "what's in the box", "buy box") and pt in ("pdp", "buying"):
            return True
        if t == "compare" and pt == "compare":
            return True
        if t == "buy box" and pt == "buying":
            return True
    return False


def _sections_for(rule_page: str) -> Tuple[str, ...]:
    first = re.split(r"[/,]", (rule_page or "PDP"))[0].strip().lower()
    return spec_extractor.PAGE_TO_SECTIONS.get(first, ("spec", "body"))


# ── 메인 (Step 1~9 조립) ──────────────────────────────────────────────
def run(html: str, ruleset: Dict[str, Any], page_type: str = "PDP",
        sitecode: str = "", rendered_by: str = "source") -> Dict[str, Any]:
    rules: List[Dict] = ruleset.get("rules", [])
    dictionary: Dict[str, List[str]] = ruleset.get("dictionary", {})
    country_exc = [c for c in ruleset.get("country_exceptions", [])
                   if _norm(c.get("country", "")) == _norm(sitecode)]

    ex = spec_extractor.extract(html)
    pairs, sections = ex["pairs"], ex["sections"]
    # Promotion 무시(ExceptionRule: "Promotions ignored")
    if any("promotion" in _norm(e.get("rule", "") + e.get("description", ""))
           for e in ruleset.get("exceptions", [])):
        sections.pop("promotion", None)
        pairs = [p for p in pairs if p["section"] != "promotion"]

    items: List[Dict[str, Any]] = []
    seen_alias_hits: List[str] = []  # 후보(미등록 표현) 감지용 — 페어 라벨 수집

    for rule in rules:
        trace: List[Dict[str, str]] = [{"step": "rendering", "detail": f"input={rendered_by}"}]
        aliases = _aliases_for(rule, dictionary)
        forbidden = _forbidden_aliases(rule, rules, dictionary)
        allowed_secs = _sections_for(rule["page"])
        item = {
            "rule_id": rule["rule_id"], "category": rule["category"],
            "attribute": rule["attribute"], "priority": rule["priority"],
            "page": rule["page"], "validation": rule["validation"],
            "expected": rule["expected"], "unit": rule["unit"],
            "fix_guide": rule.get("fix_guide", ""),
            "found": "", "matched_alias": "", "section": "", "source": "",
            "status": "na", "message": "", "trace": trace,
        }

        # 국가 예외: 해당 룰 검사 제외
        skip = next((c for c in country_exc if _norm(c.get("rule", "")) in
                     (_norm(rule["rule_id"]), _norm(rule["attribute"]), _norm(rule["category"]))), None)
        if skip:
            trace.append({"step": "exception", "detail": f"country exception ({skip.get('country')}): {skip.get('action') or 'skip'}"})
            item["status"] = "na"; item["message"] = "Skipped by country exception"
            items.append(item); continue

        if not _applicable(rule["page"], page_type):
            trace.append({"step": "section", "detail": f"page '{rule['page']}' not applicable on {page_type}"})
            item["message"] = f"Not applicable on {page_type}"
            items.append(item); continue
        trace.append({"step": "section", "detail": f"target sections={list(allowed_secs)}"})
        trace.append({"step": "dictionary", "detail": f"aliases={aliases}"
                      + (f" · forbidden={forbidden}" if forbidden else "")})

        # ① 구조 페어에서 attribute 매칭 (Section→Attribute→Value)
        def _label_hit(lab: str, alias_list) -> bool:
            for a in alias_list:
                na_ = _norm_loose(a)
                if not na_:
                    continue
                # 완전 일치 또는 (4자 이상 alias의) 부분 포함 — 'AP'⊂'Akkukapazität' 류 오탐 방지
                if na_ == lab or (len(na_) >= 4 and na_ in lab):
                    return True
            return False

        found_pair = None
        for p in pairs:
            if p["section"] not in allowed_secs and p["section"] != "body":
                continue
            lab = _norm_loose(p["label"])
            if _label_hit(lab, aliases):
                # 금지 alias가 라벨에 있으면 다른 attribute의 값 → 제외 (FP 방지)
                if _label_hit(lab, forbidden):
                    continue
                found_pair = p
                break
        seen_alias_hits += [p["label"] for p in pairs if p["section"] in allowed_secs]

        raw_value = ""
        if found_pair:
            raw_value = found_pair["value"]
            item.update(matched_alias=found_pair["label"], section=found_pair["section"],
                        source=found_pair["source"])
            trace.append({"step": "attribute", "detail":
                          f"matched pair [{found_pair['source']}] '{found_pair['label']}' @ {found_pair['section']}"})
        else:
            # ② 폴백: 섹션 텍스트 윈도우 검색 (4자 이상 alias만 — 짧은 약어 오탐 방지)
            long_aliases = [a for a in aliases if len(_norm_loose(a)) >= 4 or not a.isascii()]
            for sec in allowed_secs:
                text = sections.get(sec, "")
                if not text:
                    continue
                wins = spec_extractor.window_search(text, long_aliases)
                # 금지 alias가 같은 윈도우에 들어있으면 제외 (Typical 창에 Rated 값 유입 방지)
                fb_norms = [x for x in (_norm_loose(fb) for fb in forbidden) if x]
                wins = [(a, w) for a, w in wins
                        if not any(fb in _norm_loose(a + w) for fb in fb_norms)]
                if wins:
                    a, w = wins[0]
                    raw_value = w
                    item.update(matched_alias=a, section=sec, source="window")
                    trace.append({"step": "attribute", "detail": f"window match '{a}' @ {sec} → '{w[:50]}'"})
                    break
            # exists 룰은 attribute 없이 expected 값 자체 존재도 인정
            if not raw_value and rule["validation"] == "exists":
                for sec in allowed_secs:
                    if _norm_loose(rule["expected"]) and _norm_loose(rule["expected"]) in _norm_loose(sections.get(sec, "")):
                        raw_value = rule["expected"]
                        item.update(matched_alias="(value itself)", section=sec, source="window")
                        trace.append({"step": "attribute", "detail": f"expected value found directly @ {sec}"})
                        break
                # attribute명 자체 존재 (Galaxy AI 등)
                if not raw_value:
                    for sec in allowed_secs:
                        if _norm_loose(rule["attribute"]) in _norm_loose(sections.get(sec, "")):
                            raw_value = rule["attribute"]
                            item.update(matched_alias=rule["attribute"], section=sec, source="window")
                            trace.append({"step": "attribute", "detail": f"attribute name found @ {sec}"})
                            break

        if not raw_value:
            trace.append({"step": "attribute", "detail": "not found in target sections"})
            trace.append({"step": "result", "detail": "N/A (not found on this page)"})
            item["status"] = "na"
            item["message"] = f"'{rule['attribute']}' not found on the page"
            items.append(item); continue

        norm_value = _norm(raw_value)
        item["found"] = raw_value.strip()[:120]
        trace.append({"step": "normalization", "detail": f"'{raw_value.strip()[:60]}' → '{norm_value[:60]}'"})

        sec_text = sections.get(item["section"], "")
        ok, why = _validate(rule["validation"], rule["expected"], rule["unit"], raw_value, sec_text)
        trace.append({"step": "validation", "detail": why})

        if rule.get("exception"):
            trace.append({"step": "exception", "detail": rule["exception"]})
        trace.append({"step": "result", "detail": "PASS" if ok else "FAIL"})

        if ok:
            item["status"] = "pass"
            item["message"] = "OK"
        else:
            item["status"] = "fail"
            fnum = _num(raw_value)
            cur = f"{fnum:g}" if (rule["validation"] == "numeric_exact" and fnum is not None) else item["found"]
            item["message"] = f"Expected '{rule['expected']}'{(' ' + rule['unit']) if rule['unit'] else ''} but page shows '{cur}'"
        items.append(item)

    # ── 미등록 표현 후보(규칙 기반 자리) — 스펙 섹션 라벨 중 어떤 alias에도 안 걸린 것 ──
    known = set()
    for r in rules:
        for a in _aliases_for(r, dictionary):
            known.add(_norm_loose(a))
    candidates = []
    for lab in dict.fromkeys(seen_alias_hits):
        nl = _norm_loose(lab)
        if nl and len(lab) < 60 and not any(k in nl or nl in k for k in known):
            candidates.append({"alias": lab, "representative": "", "confidence": None,
                               "note": "unmapped label found in spec section"})

    # ── 집계 ──
    def _score(rows):
        applicable = [i for i in rows if i["status"] != "na"]
        p = sum(1 for i in applicable if i["status"] == "pass")
        return round(100 * p / len(applicable), 1) if applicable else None

    cats: Dict[str, List] = {}
    for i in items:
        cats.setdefault(i["category"], []).append(i)
    categories = []
    for cat, rows in cats.items():
        categories.append({
            "category": cat, "score": _score(rows), "total": len(rows),
            "pass": sum(1 for i in rows if i["status"] == "pass"),
            "fail": sum(1 for i in rows if i["status"] == "fail"),
            "warn": sum(1 for i in rows if i["status"] == "warn"),
            "na": sum(1 for i in rows if i["status"] == "na"),
        })
    summary = {
        "score": _score(items), "total": len(items),
        "critical": sum(1 for i in items if i["status"] == "fail"),
        # Warning = 딕셔너리에 없는 표현 발견 → 번역/표기 재확인 필요 (candidates)
        "warning": len(candidates),
        "pass": sum(1 for i in items if i["status"] == "pass"),
        "na": sum(1 for i in items if i["status"] == "na"),
    }
    applicable_total = sum(1 for i in items if not i["message"].startswith("Not applicable")
                           and "country exception" not in i["message"].lower())
    checked = summary["pass"] + summary["critical"]
    # 적용 대상 룰의 절반 이상을 페이지에서 못 찾으면(=N/A) 커버리지 부족 의심 —
    # 딕셔너리에 이 언어의 표현이 없거나, 추출기가 이 페이지 DOM 구조를 모르는 경우.
    summary["coverage_low"] = bool(applicable_total) and checked < applicable_total * 0.5
    return {"summary": summary, "categories": categories, "items": items,
            "candidates": candidates[:20]}
