"""
spec_engine.py — 큐비 — Spec QA [V3]
Value-first Validation → Qualifier/Predecessor Cross-check → QA Result(+Rule Trace)

[2026-07 V3 전면 재설계 — 툴의 목적 재정의에 따른 판정 모델 전환]
  운영 결정 사항 (요구사항 확정 문답 기준):
    1) 값 없음 ≠ 오류. "미노출" 판정 경로와 exists(Present)류 룰을 전면 삭제한다.
       FAIL은 "틀린 값이 실제로 적혀 있다"는 적극적 증거가 있을 때만 발생한다.
    2) 판정은 label-first가 아니라 value-first다 — 30여 개 언어의 attribute 라벨
       번역에 의존하지 않고, 정답 값 자체(숫자+단위 동의어)를 언어 중립적으로 찾는다.
       라벨(사전)은 "오답이 항목과 함께 적혔는가"의 FAIL 승격 근거로만 쓴다.
    3) 복수 정답: expected '4400|4272' — 어느 표기든 노출되면 PASS.
       한정어(qualifier) 오짝(예: '일반 4,272mAh')은 숫자가 집합 안이어도 FAIL.
    4) 근사('약 8인치')·단위 환산(inch→cm) 표기는 FAIL이 아닌 확인(warn).
    5) 전작 비교 문구가 PDP에 매우 흔하므로, 같은 블록에 전작 모델명이 있으면 그
       숫자는 전작 소속으로 귀속 — 전작 정답지(previous_models)와 대조해 판정한다.
    6) Compare 페이지는 표 컬럼(제품) 귀속을 적용한다 — 이웃 제품 컬럼의 값이
       검수 대상 제품의 값으로 오인되지 않게 한다.

  V2에서 유지하는 것:
    · Deterministic (AI 추론 없음), 모든 판정에 trace.
    · Dictionary 후보(candidate_hits) 수집 — SPEC_LIKE_SECTIONS 구조 페어에서만.
    · 결과 스키마(summary/categories/items/candidate_hits) — 프론트 호환.
      단, 'na'는 "이 페이지에 값이 없어 판정하지 않음(오류 아님)"의 내부 상태로만
      남고, 프론트는 표시하지 않는다.

  V2에서 삭제한 것 (스크린샷 오탐의 근본 원인):
    · 폴백 텍스트 윈도우에서 '라벨 주변 텍스트'를 잘라 정답과 diff하던 경로 전체.
      ('고해상도의 동영상…' 저장공간 마케팅 문장이 Resolution의 찾은 값이 되고,
       '밝기와 최대 120Hz…'에서 첫 숫자만 비교해 2600 vs 120 오탐을 내던 코드)
    · exists 검증 타입 (rule DB 파서도 해당 행을 건너뛴다).
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

import spec_extractor
import spec_value_match as svm

# ── 정규화 (V2 호환 유지 — pair 라벨 비교/사전용) ─────────────────────
_norm = svm.normalize_text


def _norm_loose(s: str) -> str:
    """느슨한 정규화(Dictionary 비교용): 모든 스크립트의 문자·숫자만 남김."""
    return re.sub(r"[^\w]|_", "", _norm(s))


def _num(s: str) -> Optional[float]:
    m = re.search(r"-?\d+(?:\.\d+)?", _norm(s))
    return float(m.group()) if m else None


# ── Dictionary Mapping ────────────────────────────────────────────────
def _aliases_for(rule: Dict[str, Any], dictionary: Dict[str, List[str]]) -> List[str]:
    attr = rule["attribute"]
    na = _norm_loose(attr)
    out = [attr]
    for rep, aliases in (dictionary or {}).items():
        nr = _norm_loose(rep)
        if nr and (nr == na or nr in na):
            out.append(rep)
            out += aliases
    return list(dict.fromkeys(out))


def _label_hit(lab_norm: str, alias_list: List[str]) -> bool:
    for a in alias_list:
        na_ = _norm_loose(a)
        if not na_:
            continue
        if na_ == lab_norm or (len(na_) >= 4 and na_ in lab_norm):
            return True
    return False


def _make_label_in_block(aliases: List[str]):
    """블록 원문에 이 룰의 라벨/alias가 (경계 안전하게) 들어있는지.
    · ASCII alias: 단어 경계.
    · CJK alias: 바로 앞이 한글/한자/가나면 다른 단어의 일부('고'+해상도, '高'+解像度)
      이므로 제외 — 조사·어미가 '뒤'에 붙는 것(해상도의/解像度の)은 정상이라 뒤 경계는
      두지 않는다. (V2 오탐 원인 ①의 수정 — 회귀 테스트로 고정)"""
    pats = []
    for a in aliases:
        if not a:
            continue
        if a.isascii():
            pats.append(re.compile(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])", re.I))
        else:
            pats.append(re.compile(r"(?<![가-힣一-鿿ぁ-ゖァ-ヺ])" + re.escape(a), re.I))

    def _in(block: str) -> bool:
        return any(p.search(block) for p in pats)
    return _in


# ── 페이지타입 적용 여부 ──────────────────────────────────────────────
def _applicable(rule_page: str, page_type: str) -> bool:
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


def _candidate_worthy(label: str) -> bool:
    if not label or len(label) < 2 or len(label) > 60:
        return False
    if re.fullmatch(r"[\d\W_]+", label):
        return False
    return True


# ── 단위별 정답 합집합 (같은 단위 다른 스펙의 정답끼리 오답 취급 방지) ──
def _unit_accepted_union(rules: List[Dict], prev_models: List[Dict]) -> Dict[str, set]:
    union: Dict[str, set] = {}
    def _add(unit: str, raw: str):
        cu = svm.canon_unit(unit)
        if not cu:
            return
        for part in re.split(r"[|/,]", str(raw or "")):
            m = re.search(r"\d+(?:\.\d+)?", svm.normalize_text(part))
            if m:
                union.setdefault(cu, set()).add(float(m.group()))
    for r in rules:
        _add(r.get("unit", ""), r.get("expected", ""))
        # '256 / 512 / 1TB' — GB 룰의 TB 옵션은 TB 합집합에도 넣는다
        if "tb" in svm.normalize_text(r.get("expected", "")):
            for part in re.split(r"[|/,]", str(r.get("expected", ""))):
                np_ = svm.normalize_text(part)
                if "tb" in np_:
                    m = re.search(r"\d+(?:\.\d+)?", np_)
                    if m:
                        union.setdefault("tb", set()).add(float(m.group()))
    for pm in prev_models or []:
        for sp in pm.get("specs") or []:
            for v in sp.get("values") or []:
                _add(sp.get("unit", ""), str(v))
    return union


# ── Compare 컬럼 귀속 ────────────────────────────────────────────────
def _pair_owner(pair: Dict[str, Any], target_tokens: List[str],
                prev_tokens: List[Tuple[str, str]]) -> Optional[str]:
    """Compare 표 페어의 소속 제품. None=검수 대상(또는 미상), 'skip'=무관 제품,
    그 외 문자열=전작 모델키."""
    hint = svm.normalize_text(pair.get("product_hint", ""))
    if not hint:
        return None
    for t in target_tokens:
        if t and t in hint:
            return None
    for tok, model in prev_tokens:
        if tok in hint:
            return model
    return "skip"


# ── 메인 ──────────────────────────────────────────────────────────────
def run(html: str, ruleset: Dict[str, Any], page_type: str = "PDP",
        sitecode: str = "", rendered_by: str = "source") -> Dict[str, Any]:
    rules: List[Dict] = [r for r in ruleset.get("rules", [])
                         if r.get("validation") != "exists"]  # (결정 1) exists 전면 제외
    dictionary: Dict[str, List[str]] = ruleset.get("dictionary", {})
    prev_models: List[Dict] = ruleset.get("previous_models", []) or []
    unit_synonyms = svm.build_unit_synonyms(ruleset)
    unit_union = _unit_accepted_union(rules, prev_models)
    prev_tokens = svm.model_tokens(prev_models)
    target_tokens = [svm.normalize_text(ruleset.get("product", ""))]
    for r in rules:
        if svm.normalize_text(r.get("attribute", "")) == "product name":
            target_tokens += [svm.normalize_text(v) for v in svm.parse_accepted(r.get("expected", ""))]
    target_tokens = [t for t in dict.fromkeys(target_tokens) if t]

    country_exc = [c for c in ruleset.get("country_exceptions", [])
                   if _norm(c.get("country", "")) == _norm(sitecode)]

    ex = spec_extractor.extract(html)
    pairs, sections, section_blocks = ex["pairs"], ex["sections"], ex["section_blocks"]
    if any("promotion" in _norm(e.get("rule", "") + e.get("description", ""))
           for e in ruleset.get("exceptions", [])):
        sections.pop("promotion", None)
        section_blocks.pop("promotion", None)
        pairs = [p for p in pairs if p["section"] != "promotion"]

    items: List[Dict[str, Any]] = []
    candidate_hits: List[Dict[str, str]] = []
    seen_candidate_keys = set()

    for rule in rules:
        trace: List[Dict[str, str]] = [{"step": "rendering", "detail": f"input={rendered_by}"}]
        aliases = _aliases_for(rule, dictionary)
        allowed_secs = _sections_for(rule["page"])
        label_in_block = _make_label_in_block(aliases)
        accepted_str = svm.parse_accepted(rule.get("expected", ""))
        item = {
            "rule_id": rule["rule_id"], "category": rule["category"],
            "attribute": rule["attribute"], "priority": rule["priority"],
            "page": rule["page"], "validation": rule["validation"],
            "expected": rule["expected"], "unit": rule["unit"],
            "fix_guide": rule.get("fix_guide", ""),
            "found": "", "matched_alias": "", "section": "", "source": "", "confidence": "",
            "status": "na", "message": "", "trace": trace,
        }

        skip = next((c for c in country_exc if _norm(c.get("rule", "")) in
                     (_norm(rule["rule_id"]), _norm(rule["attribute"]), _norm(rule["category"]))), None)
        if skip:
            trace.append({"step": "exception", "detail": f"country exception ({skip.get('country')}): {skip.get('action') or 'skip'}"})
            item["message"] = "Skipped by country exception"
            items.append(item); continue

        if not _applicable(rule["page"], page_type):
            trace.append({"step": "section", "detail": f"page '{rule['page']}' not applicable on {page_type}"})
            item["message"] = f"Not applicable on {page_type}"
            items.append(item); continue

        trace.append({"step": "section", "detail": f"target sections={list(allowed_secs)}"})
        trace.append({"step": "value-first", "detail":
                      f"accepted={accepted_str}" + (f" · qualifier={rule.get('qualifier')}" if rule.get("qualifier") else "")})

        # 검사 대상 블록: 허용 섹션 + body (마케팅형 PDP에 스펙 수치가 흔함 — 단
        # V3는 값 우선이라 body의 무관 문장이 '찾은 값'으로 오려지지 않는다)
        blocks: List[str] = []
        for sec in dict.fromkeys(list(allowed_secs) + ["body"]):
            blocks += section_blocks.get(sec, [])

        # ── ① 구조 페어 (Section→Attribute→Value) — 라벨 동반 근거, Compare 귀속 ──
        pair_verdict = None  # (status, found, message, pair)
        for p in pairs:
            if p["section"] not in allowed_secs and p["section"] != "body":
                continue
            if not _label_hit(_norm_loose(p["label"]), aliases):
                continue
            owner = _pair_owner(p, target_tokens, prev_tokens) if p.get("product_hint") else \
                svm.attribute_block(svm.normalize_text(p["label"] + " " + p["value"]), prev_tokens)
            if owner == "skip":
                continue
            v_norm = svm.normalize_text(p["value"])
            if owner:  # 전작 컬럼/문구 — 전작 정답과 대조
                pv = svm.prev_accepted_for(prev_models, owner, rule.get("unit", ""))
                pn = _num(p["value"])
                if pv is None or pn is None:
                    trace.append({"step": "pair", "detail": f"[{owner}] '{p['label']}' → '{p['value'][:40]}' — 전작 스펙 미등록/숫자 없음, 보류"})
                    continue
                if pn in pv:
                    trace.append({"step": "pair", "detail": f"[{owner}] {pn:g}{rule.get('unit','')} — 전작 정답 일치"})
                else:
                    pair_verdict = ("fail", p["value"],
                                    f"전작 오기재 — '{owner}'의 정답은 {'/'.join(f'{v:g}' for v in pv)}{rule.get('unit','')}인데 {pn:g}로 표기됨", p)
                    break
                continue
            # 검수 대상 제품의 페어
            hit_ok = any(svm.normalize_text(a) and svm.normalize_text(a) in v_norm for a in accepted_str)
            if not hit_ok and rule["validation"] == "numeric_exact":
                pn = _num(p["value"])
                acc_nums = [_num(a) for a in accepted_str]
                hit_ok = pn is not None and pn in [a for a in acc_nums if a is not None]
            if hit_ok:
                pair_verdict = ("pass", p["value"], "OK", p)
            else:
                pair_verdict = ("fail", p["value"],
                                f"오기재 — 정답 '{rule['expected']}'{(' ' + rule['unit']) if rule['unit'] else ''}이 아닌 값이 항목에 표기됨: '{p['value'][:60]}'", p)
            break

        # Dictionary 후보 수집 (V2 유지)
        for p in pairs:
            if p["section"] not in spec_extractor.SPEC_LIKE_SECTIONS:
                continue
            lab_raw = p["label"]
            key = (_norm_loose(lab_raw), p["section"])
            if key in seen_candidate_keys:
                continue
            if _label_hit(_norm_loose(lab_raw), aliases):
                continue
            if not _candidate_worthy(lab_raw):
                continue
            seen_candidate_keys.add(key)
            candidate_hits.append({"alias": lab_raw, "section": p["section"], "source": p["source"]})

        # ── ② 값 우선 판정 ──
        vtype = rule["validation"]
        if pair_verdict and pair_verdict[0] == "fail":
            st, found, msg, p = pair_verdict
            item.update(status="fail", found=found[:120], matched_alias=p["label"],
                        section=p["section"], source=p["source"], confidence="high", message=msg)
            trace.append({"step": "result", "detail": f"FAIL (structured pair) — {msg}"})
            items.append(item); continue

        if vtype == "numeric_exact":
            res = svm.evaluate_numeric(rule, blocks, unit_synonyms, prev_models,
                                       unit_union, label_in_block=label_in_block)
            for d in res.get("detail", []):
                trace.append({"step": "value-scan", "detail": d})
            if res["status"] == "na" and pair_verdict and pair_verdict[0] == "pass":
                res = {"status": "pass", "found": pair_verdict[1], "confidence": "high", "message": "OK"}
            item.update(status=res["status"], found=(res.get("found") or "")[:120],
                        confidence=res.get("confidence", ""), message=res["message"],
                        source=item["source"] or "value-scan")
            trace.append({"step": "result", "detail": f"{res['status'].upper()} — {res['message']}"})
            items.append(item); continue

        if vtype in ("exact", "dictionary", "prefix"):
            # 값 자체(숫자·고유 토큰)는 언어 불문이므로 값 우선 존재 검색이 성립한다.
            variants = list(accepted_str)
            if vtype == "prefix":
                variants = [rule["expected"]]
            hit_block = svm.find_exact(blocks, variants)
            if hit_block is None and vtype == "dictionary":
                # dictionary 타입(Snapdragon 8 Elite 등)은 현지어 별칭도 정답 —
                # attribute alias가 아니라 '값의 사전': expected의 사전 항목이 있으면 사용
                val_aliases = (dictionary.get(rule["expected"]) or [])
                if val_aliases:
                    hit_block = svm.find_exact(blocks, val_aliases)
            if hit_block is not None:
                item.update(status="pass", found=hit_block[:120], confidence="high",
                            message="OK", source=item["source"] or "value-scan")
                trace.append({"step": "result", "detail": "PASS — 정답 값 노출 확인"})
                items.append(item); continue
            # 해상도류('NNNN x NNNN') 오답 탐지 — 라벨 동반 시에만 FAIL
            if re.search(r"\d\s*x\s*\d", svm.normalize_text(rule["expected"])):
                conflict = svm.find_resolution_conflict(blocks, accepted_str, prev_models,
                                                        label_in_block=label_in_block)
                if conflict:
                    item.update(status="fail", found=conflict["block"][:120], confidence="high",
                                message=(f"오기재 — 정답 '{rule['expected']}'이 아닌 "
                                         f"'{conflict['found_token']}'이 항목 라벨과 함께 표기됨"))
                    trace.append({"step": "result", "detail": "FAIL — labeled wrong resolution"})
                    items.append(item); continue
            if pair_verdict and pair_verdict[0] == "pass":
                item.update(status="pass", found=pair_verdict[1][:120], confidence="high", message="OK")
                trace.append({"step": "result", "detail": "PASS (structured pair)"})
                items.append(item); continue
            trace.append({"step": "result", "detail": "값 없음 — 오류 아님 (표시·집계 제외)"})
            item["message"] = "정답 값이 이 페이지에 없음 (오류 아님)"
            items.append(item); continue

        if vtype == "option_match":
            # (결정 1) 옵션 미노출은 오류가 아니다 — 발견된 옵션이 하나라도 있으면 PASS,
            # 옵션 계열의 오답(정답 집합 밖 GB/TB)은 numeric 룰들의 unit_union 스캔과
            # 동일 로직으로 여기서 잡는다.
            opts = [o.strip() for o in re.split(r"[/|,]", rule["expected"]) if o.strip()]
            found_opts, unit = [], svm.canon_unit(rule.get("unit", ""))
            for o in opts:
                token_variants = [o, o + (rule.get("unit") or "")]
                if svm.find_exact(blocks, token_variants):
                    found_opts.append(o)
            wrong = None
            if unit:
                for h in svm.scan_unit_hits(blocks, unit, unit_synonyms):
                    owner = svm.attribute_block(h["block_norm"], prev_tokens)
                    if owner:
                        continue
                    if h["value"] not in unit_union.get(unit, set()):
                        if label_in_block(h["block"]):
                            wrong = h
                            break
            if wrong:
                item.update(status="fail", found=wrong["block"][:120], confidence="high",
                            message=f"오기재 — 정답 옵션({rule['expected']}) 밖 {wrong['text']} 표기")
                trace.append({"step": "result", "detail": "FAIL — labeled wrong option value"})
            elif found_opts:
                item.update(status="pass", found=", ".join(found_opts), confidence="high",
                            message=f"노출 옵션: {', '.join(found_opts)}")
                trace.append({"step": "result", "detail": f"PASS — options found: {found_opts}"})
            else:
                item["message"] = "옵션 값이 이 페이지에 없음 (오류 아님)"
                trace.append({"step": "result", "detail": "값 없음 — 오류 아님"})
            items.append(item); continue

        # 알 수 없는 검증 타입 — 판정하지 않음
        item["message"] = f"unknown validation '{vtype}'"
        items.append(item)

    # ── 집계 (na는 '판정 대상 아님' — 점수·표시 모두 제외) ──
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
        "warning": sum(1 for i in items if i["status"] == "warn"),
        "pass": sum(1 for i in items if i["status"] == "pass"),
        "na": sum(1 for i in items if i["status"] == "na"),
        "dictionary_pending": len(candidate_hits),
    }
    return {"summary": summary, "categories": categories, "items": items,
            "candidate_hits": candidate_hits[:40]}
