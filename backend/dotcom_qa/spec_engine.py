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
        # [FIX] Compare(제품비교) 스펙은 별도 /compare URL뿐 아니라, PDP 페이지 안에
        # 임베드된 Compare 위젯(예: samsung.com/.../galaxy-z-fold7의 비교 표)에도
        # 흔히 존재한다. 기존엔 page_type이 정확히 "compare"일 때만 적용되어, PDP URL로
        # 크롤한 페이지 안의 Compare 표 스펙은 룰 자체가 전부 "not applicable"로
        # 건너뛰어졌다(허용 섹션엔 이미 "compare"가 포함되어 있어 실제 오탐 위험은 없음).
        if t == "compare" and pt in ("compare", "pdp"):
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


# ── 전작 텍스트 값 혼입 검사 (Processor 등 텍스트 스펙의 유일한 FAIL 근거) ──
def _prev_text_value_in(prev_models: List[Dict], rule: Dict, v_norm: str) -> Optional[Tuple[str, str]]:
    """전작 정답지의 같은 attribute 텍스트 값이 v_norm에 들어있으면 (모델, 값) 반환.
    숫자 단독 값(2600 등)은 오탐 위험이 커서 텍스트(글자 포함) 값만 본다."""
    attr_norm = _norm_loose(rule.get("attribute", ""))
    for pm in prev_models or []:
        for sp in pm.get("specs") or []:
            if _norm_loose(sp.get("attribute", "")) != attr_norm:
                continue
            for v in sp.get("values") or []:
                nv = svm.normalize_text(str(v))
                if nv and re.search(r"[a-z가-힣一-鿿]", nv) and nv in v_norm:
                    return (pm.get("model", ""), str(v))
    return None


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
    그 외 문자열=전작 모델키.

    [2026-07 FIX — 이름 포함 관계 오귀속]
    'Galaxy Watch8 Classic'/'Galaxy Z Flip7 FE'처럼 이웃 모델명이 대상 제품명을
    문자열로 포함하는 경우, 기존 '대상 토큰 우선' 검사로는 그 컬럼이 대상 제품으로
    오귀속됐다(실측: Classic 컬럼 64GB → Watch8 오류 오탐). 이제 대상/전작 양쪽에서
    '가장 긴 매칭 토큰'을 찾아 더 구체적인(긴) 쪽으로 귀속한다 — 'galaxy watch8
    classic'(전작 등록)이 'galaxy watch8'(대상)보다 길므로 Classic으로 정확히 귀속."""
    hint = svm.normalize_text(pair.get("product_hint", ""))
    if not hint:
        return None
    best_target = max((len(t) for t in target_tokens if t and t in hint), default=0)
    best_prev, best_prev_model = 0, None
    for tok, model in prev_tokens:
        if tok and tok in hint and len(tok) > best_prev:
            best_prev, best_prev_model = len(tok), model
    if best_target or best_prev:
        return None if best_target >= best_prev else best_prev_model
    # [V3.3] 제품명으로 보이는 헤더("갤럭시 …", "Galaxy …")인데 대상/전작 어느 쪽도
    # 아니면 무관 제품 컬럼 → skip. 그 외("사양", "Spec", 빈 헤더 등 일반 컬럼명)는
    # 제품 정보가 아니므로 대상 페어로 취급 — 통째로 버려서 전부 미감지가 되는 것 방지.
    if re.search(r"galaxy|갤럭시|iphone|아이폰|xiaomi|pixel", hint):
        return "skip"
    return None


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
    # [V3.3] Compare 헤더는 현지어 제품명("갤럭시 Z 폴드7")이 흔하다 — 시드/엑셀의
    # product_aliases(다국어 제품명)를 대상 토큰에 포함해 컬럼 귀속이 끊기지 않게 한다.
    target_tokens += [svm.normalize_text(a) for a in (ruleset.get("product_aliases") or [])]
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
                break
            # [V3.1] 페어 불일치 ≠ 곧바로 오류. "값 없음 ≠ 오류" 원칙은 구조 페어에도
            # 적용된다 — 라벨 옆 서술이 다르다는 것만으로는 '틀린 값'의 증거가 아니다.
            #   · dictionary형(Processor 등 텍스트 스펙): 페이지가 "3나노 프로세서"처럼
            #     다르게 서술하는 것은 미노출이지 오기재가 아님 → FAIL 금지.
            #     단, 전작의 값(예: 'Snapdragon 8 Gen 3')이 현 제품 라벨에 붙어 있으면
            #     그건 적극적 오기재 증거 → FAIL.
            #   · exact/prefix: 같은 형태의 '비교 가능한 토큰'이 실제로 있을 때만 FAIL —
            #     해상도(NxM) 정답엔 다른 NxM, 숫자 포함 정답(Bluetooth 5.4)엔 다른 숫자.
            #     비교 가능한 토큰이 없으면 오기재 증거가 아니므로 판정 보류.
            prev_hit = _prev_text_value_in(prev_models, rule, v_norm)
            if prev_hit:
                pair_verdict = ("fail", p["value"],
                                f"전작 값 혼입 — '{rule['attribute']}'에 전작({prev_hit[0]})의 값 '{prev_hit[1]}'이 표기됨", p)
                break
            if rule["validation"] == "numeric_exact":
                # [V3.2] 숫자 룰의 페어 불일치도 "실제 다른 숫자"가 있을 때만 오류다.
                # Compare 표에서 라벨 셀 텍스트("커버 디스플레이 크기", "무게")가 값으로
                # 잡히는 경우 숫자가 없다 — 그건 오기재 증거가 아니라 미노출이므로 보류.
                pn = _num(p["value"])
                if pn is None:
                    trace.append({"step": "pair", "detail":
                                  f"'{p['label']}' → '{p['value'][:40]}' — 숫자 없음(라벨성 텍스트), 오기재 증거 아님 → 보류"})
                    break
                cu = svm.canon_unit(rule.get("unit", ""))
                prev_vals = svm.prev_accepted_for(prev_models, None, cu, any_model=True) or []
                if pn in prev_vals:
                    pair_verdict = ("fail", p["value"],
                                    f"전작 값 혼입 의심 — '{rule['attribute']}'에 전작 정답 {pn:g}{rule.get('unit','')}이 표기됨 (현 제품 정답: {rule['expected']})", p)
                elif pn in unit_union.get(cu, set()):
                    pair_verdict = ("warn", p["value"],
                                    f"확인 필요 — 같은 단위의 다른 스펙 정답값 {pn:g}{rule.get('unit','')}이 이 항목에 표기됨 (행/값 배치 확인)", p)
                else:
                    pair_verdict = ("fail", p["value"],
                                    f"오기재 — 정답 '{rule['expected']}'{(' ' + rule['unit']) if rule['unit'] else ''}이 아닌 {pn:g}이 항목에 표기됨", p)
                break
            if rule["validation"] in ("exact", "prefix"):
                # [2026-07] '24 hours'처럼 숫자+단위인 exact 룰은 여기서 문자열 충돌로 FAIL시키지
                # 않는다 — 아래 값 우선 단계에서 다국어 단위(24 時間=24시간=24 hrs) numeric으로
                # 판정한다. (기존엔 v_norm에 숫자만 있어도 오기재 FAIL → JP/KR 페이지 오탐)
                if rule["validation"] == "exact" and svm.split_expected_numeric_unit(
                        rule.get("expected", ""), rule.get("unit", ""), unit_synonyms):
                    trace.append({"step": "pair", "detail":
                                  f"'{p['label']}' → '{p['value'][:40]}' — 숫자+단위 exact 룰은 다국어 numeric으로 판정(보류)"})
                    break
                exp_norm = svm.normalize_text(rule["expected"])
                conflict = False
                if re.search(r"\d\s*x\s*\d", exp_norm):
                    conflict = bool(re.search(r"\d{3,4}\s*x\s*\d{3,4}", v_norm))
                elif re.search(r"\d", exp_norm):
                    conflict = bool(re.search(r"\d", v_norm))
                if conflict:
                    pair_verdict = ("fail", p["value"],
                                    f"오기재 — 정답 '{rule['expected']}'{(' ' + rule['unit']) if rule['unit'] else ''}이 아닌 값이 항목에 표기됨: '{p['value'][:60]}'", p)
                    break
            trace.append({"step": "pair", "detail":
                          f"'{p['label']}' → '{p['value'][:40]}' — 정답 미포함이나 오기재 증거 아님(서술 상이), 판정 보류"})
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
                                       unit_union, label_in_block=label_in_block,
                                       target_tokens=target_tokens)
            for d in res.get("detail", []):
                trace.append({"step": "value-scan", "detail": d})
            if res["status"] == "na" and pair_verdict and pair_verdict[0] == "pass":
                res = {"status": "pass", "found": pair_verdict[1], "confidence": "high", "message": "OK"}
            elif res["status"] == "na" and pair_verdict and pair_verdict[0] == "warn":
                res = {"status": "warn", "found": pair_verdict[1], "confidence": "medium",
                       "message": pair_verdict[2]}
            item.update(status=res["status"], found=(res.get("found") or "")[:120],
                        confidence=res.get("confidence", ""), message=res["message"],
                        source=item["source"] or "value-scan")
            trace.append({"step": "result", "detail": f"{res['status'].upper()} — {res['message']}"})
            items.append(item); continue

        if vtype in ("exact", "dictionary", "prefix"):
            # [2026-07 FIX — '24 hours' exact 룰이 '24 時間'을 오류로 잡던 문제]
            # expected가 '숫자 + 알려진 단위'(24 hours / 2600 nits …)면 문자열 일치가 아니라
            # numeric(다국어 단위 동의어) 판정으로 위임한다. 문자열 exact는 언어가 바뀌는 순간
            # ('24 hours' ⊄ '24 時間') 정상 페이지를 오기재로 판정했다 — 실제 리포트로 확인.
            if vtype == "exact":
                nu = svm.split_expected_numeric_unit(rule.get("expected", ""), rule.get("unit", ""),
                                                     unit_synonyms)
                if nu:
                    num_expected, cu = nu
                    num_rule = {**rule, "expected": num_expected, "unit": cu,
                                "validation": "numeric_exact"}
                    trace.append({"step": "value-first", "detail":
                                  f"exact '{rule['expected']}' → 숫자+단위({cu})로 재해석해 다국어 numeric 판정"})
                    res = svm.evaluate_numeric(num_rule, blocks, unit_synonyms, prev_models,
                                               unit_union, label_in_block=label_in_block,
                                               target_tokens=target_tokens)
                    for d in res.get("detail", []):
                        trace.append({"step": "value-scan", "detail": d})
                    if res["status"] == "na" and pair_verdict and pair_verdict[0] == "pass":
                        res = {"status": "pass", "found": pair_verdict[1], "confidence": "high", "message": "OK"}
                    item.update(status=res["status"], found=(res.get("found") or "")[:120],
                                confidence=res.get("confidence", ""), message=res["message"],
                                source=item["source"] or "value-scan")
                    trace.append({"step": "result", "detail": f"{res['status'].upper()} — {res['message']}"})
                    items.append(item); continue
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

    # ── 집계 ──
    # [V3.1 운영 결정] 점수 = 일치 ÷ (일치 + 불일치). 확인(warn)은 "오답 단정 불가 —
    # 사람이 봐달라"는 표시일 뿐 감점 사유가 아니므로 분모에서 제외한다 (확인만 있는
    # 페이지는 100% + 확인 배지). na(값 없음)도 오류가 아니므로 당연히 제외.
    def _score(rows):
        applicable = [i for i in rows if i["status"] in ("pass", "fail")]
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
    # [V3.3] 진단 — 적용 대상 룰이 있는데 아무것도(pass/fail/warn) 감지되지 않으면,
    # 원인 판별에 필요한 추출 통계를 함께 내려 프론트가 안내 배너를 띄울 수 있게 한다.
    summary["detected"] = summary["pass"] + summary["critical"] + summary["warning"]
    applicable_cnt = sum(1 for i in items if not str(i.get("message", "")).startswith("Not applicable")
                         and "country exception" not in str(i.get("message", "")).lower())
    if applicable_cnt and summary["detected"] == 0:
        all_blocks = [b for bl in section_blocks.values() for b in bl]
        digit_blocks = sum(1 for b in all_blocks if re.search(r"\d", b))
        summary["diagnosis"] = {
            "rendered_by": rendered_by,
            "blocks": len(all_blocks), "digit_blocks": digit_blocks,
            "pairs": len(pairs),
            "hint": ("크롤 HTML에 텍스트가 거의 없음 — JS 렌더링 전 HTML일 가능성"
                     if len(all_blocks) < 30 or digit_blocks == 0 else
                     "텍스트는 있으나 스펙 값 패턴(숫자+단위)이 없음 — 값이 이미지/스크립트로 노출되거나 단위 표기가 미등록일 가능성"),
        }
    return {"summary": summary, "categories": categories, "items": items,
            "candidate_hits": candidate_hits[:40]}
