"""
compare_qa.py — 큐비 — Compare Pipeline · Step 2 (CompareQA)

Compare QA는 Spec 하나당 "Product별" 값을 모두 검사한다.
  예) Battery — Fold7 ✔ / Fold4 ✔ / S22 Ultra ✖

[2026-07 변경] Compare에 뜨는 제품들은 전작/자사 구분 없이 전부 "각자 자기 자신의
Rule DB"를 갖는 독립된 자사 제품이다(예: Fold7 vs Fold4 vs S22 Ultra — 셋 다 자사
제품이고 각자 다른 정답을 대야 한다). 따라서 "market_product 하나의 룰셋 안에서
자사/전작을 구분"하던 기존 방식(product_aliases + previous_models)은 폐기하고,
컬럼마다 spec_rule_db에 등록된 제품 전체를 훑어 "이 컬럼 = 어느 제품 Rule DB인가"만
alias로 판별한다. 판별되면 그 제품 고유의 rules(MasterSpec 전체)로 채점한다.

Rule DB 자체가 없는 제품(신제품 대응 전, 혹은 경쟁사 제품 등)은 "오답도 정답도 아님"
— warn으로 표시한다(오탐 방지: 정답 데이터가 없다는 뜻이지 페이지 오류가 아니다).

기존 PDP QA(spec_engine.run)는 이 모듈과 완전히 분리되어 있으며 전혀 수정하지 않는다.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

import spec_rule_db
import spec_value_match as svm


def _norm_loose(s: str) -> str:
    return re.sub(r"[^\w]|_", "", svm.normalize_text(s))


def _load_all_rulesets() -> Dict[str, Dict[str, Any]]:
    """등록된 전체 제품의 룰셋을 {product_key: ruleset} 형태로 로드."""
    out: Dict[str, Dict[str, Any]] = {}
    for meta in spec_rule_db.list_products():
        key = meta.get("product")
        if not key:
            continue
        rs = spec_rule_db.load(key)
        if rs:
            out[key] = rs
    return out


def _match_ruleset(raw_hint: str, rulesets: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Compare 컬럼의 product_hint(현지어 표기 포함)를 등록된 제품 중 하나의 Rule DB에
    alias로 매칭한다. 여러 제품 중 "정답 후보 찾기"가 아니라 "내가 이미 아는 제품명 →
    그 제품 룰셋 불러오기"이므로 가장 긴 alias가 매칭된 제품을 채택한다."""
    hn = _norm_loose(raw_hint)
    if not hn:
        return None
    best, best_len = None, 0
    for key, rs in rulesets.items():
        aliases = rs.get("product_aliases") or [rs.get("product", key)]
        for alias in aliases:
            an = _norm_loose(alias)
            if an and (an == hn or an in hn or hn in an):
                if len(an) > best_len:
                    best, best_len = rs, len(an)
    return best


def _aliases_for(attr: str, dictionary: Dict[str, List[str]]) -> List[str]:
    """룰의 attribute(영문)를 dictionary(대표값→현지어 alias 목록)로 확장한다.
    spec_engine.py의 PDP용 _aliases_for와 동일한 패턴 — Compare도 같은 dictionary를 쓴다."""
    na = _norm_loose(attr)
    out = [attr]
    for rep, aliases in (dictionary or {}).items():
        nr = _norm_loose(rep)
        if nr and (nr == na or nr in na):
            out.append(rep)
            out += aliases
    return list(dict.fromkeys(out))


def _find_rule(spec_label: str, category: str, specs: List[Dict[str, Any]],
                dictionary: Optional[Dict[str, List[str]]] = None) -> Optional[Dict[str, Any]]:
    """(category, spec) 텍스트에 매칭되는 정답 룰을 찾는다.
    [2026-07 FIX] attribute 영문명만 비교해서 현지어 페이지(예: 일본어 'カメラ/背面カメラ')에서
    dictionary에 이미 등록된 alias('背面カメラ' 등)가 있는데도 매칭이 안 되던 버그 — 이제
    룰의 dictionary alias까지 함께 비교한다."""
    label_norm = _norm_loose(f"{category} {spec_label}")
    spec_only_norm = _norm_loose(spec_label)
    for rule in specs:
        attr = rule.get("attribute", "")
        if not attr:
            continue
        for alias in _aliases_for(attr, dictionary):
            an = _norm_loose(alias)
            if not an:
                continue
            if an == spec_only_norm or an == label_norm:
                return rule
            if len(an) >= 4 and (an in spec_only_norm or an in label_norm
                                  or spec_only_norm in an):
                return rule
    return None


def _evaluate_cell(rule: Dict[str, Any], cell_value: str) -> Tuple[str, str]:
    """단일 셀 값 vs 룰(expected/unit/validation) → (status, message).
    status: pass|fail|warn|na"""
    value = (cell_value or "").strip()
    if not value:
        return "na", "값 없음"

    vtype = rule.get("validation") or "exact"
    expected = str(rule.get("expected", ""))
    unit = rule.get("unit", "")
    accepted = svm.parse_accepted(expected)
    nv = svm.normalize_text(value)

    # [2026-07 FIX] 페이지에서 실제로 값을 못 찾았을 때(렌더 타이밍/추출 실패 등) '0'을
    # 그대로 내보내는 경우가 있다 — 프로세서명·치수(HxWxD)처럼 0이 될 수 없는 스펙까지
    # "정답과 다른 값"으로 fail 처리되던 원인. 기대값 자체가 0인 경우(예: 광학줌 0배처럼
    # 실제로 0이 맞는 스펙)만 정상 판정을 계속하고, 그 외엔 fail 대신 '확인 필요'로 낮춘다.
    if nv == "0" and not any(svm.normalize_text(a) == "0" for a in accepted):
        return "warn", "추출값이 '0'으로 나옴 — 페이지 미렌더/추출 실패 가능성, 원본 확인 필요"

    if vtype == "numeric_exact":
        m = re.search(r"-?\d+(?:\.\d+)?", nv)
        if not m:
            return "na", "숫자 값을 찾을 수 없음"
        found = float(m.group())
        accepted_nums = []
        for a in accepted:
            ma = re.search(r"-?\d+(?:\.\d+)?", svm.normalize_text(a))
            if ma:
                accepted_nums.append(float(ma.group()))
        if any(abs(found - a) < 1e-6 for a in accepted_nums):
            return "pass", "OK"
        if accepted_nums:
            return "fail", f"오기재 — 정답 '{expected}{unit}'이 아닌 '{value}' 표기"
        return "warn", "정답 숫자를 파싱하지 못해 확인 필요"

    if vtype == "option_match":
        opts = [o.strip() for o in re.split(r"[/|,]", expected) if o.strip()]
        if any(svm.normalize_text(o) and svm.normalize_text(o) in nv for o in opts):
            return "pass", "OK"
        return "fail", f"오기재 — 정답 옵션({expected}) 밖 값 표기"

    # exact / dictionary / prefix
    variants = accepted if vtype != "prefix" else [expected]
    for v in variants:
        vn = svm.normalize_text(v)
        if vn and (vn in nv or nv in vn):
            return "pass", "OK"
    return "fail", f"오기재 — 정답 '{expected}'이 아닌 '{value}' 표기"


class CompareQA:
    """Compare 페이지 전용 QA. PDP QA(spec_engine)와 별도 경로로 동작한다."""

    def evaluate(self, matrix: Dict[str, Any], market_product: Optional[str] = None) -> Dict[str, Any]:
        rulesets = _load_all_rulesets()
        if not rulesets:
            return {"summary": {"checked": False, "reason": "등록된 Rule DB가 하나도 없음 — Compare QA 스킵"},
                    "rows": matrix.get("rows", []), "products": matrix.get("products", [])}

        # 컬럼(product_hint) → 매칭된 룰셋 캐시(행마다 반복 매칭하지 않도록)
        column_ruleset: Dict[str, Optional[Dict[str, Any]]] = {}

        rows_out = []
        product_scores: Dict[str, Dict[str, int]] = {}

        for row in matrix.get("rows", []):
            category, spec = row.get("category", ""), row.get("spec", "")
            out_values = []
            for cell in row.get("values", []):
                raw_product, value = cell.get("product", ""), cell.get("value", "")

                if raw_product not in column_ruleset:
                    column_ruleset[raw_product] = _match_ruleset(raw_product, rulesets)
                rs = column_ruleset[raw_product]

                bucket = product_scores.setdefault(
                    raw_product, {"pass": 0, "fail": 0, "warn": 0, "na": 0, "unchecked": 0})

                if rs is None:
                    # 이 제품 자체의 Rule DB가 없음 — 오답도 정답도 아니므로 warn
                    out_values.append({**cell, "status": "warn",
                                       "message": "Rule DB 없음 — 판별 불가"})
                    bucket["warn"] += 1
                    continue

                rule = _find_rule(spec, category, rs.get("rules") or [], rs.get("dictionary") or {})
                if rule is None:
                    out_values.append({**cell, "status": "unchecked",
                                       "message": "이 스펙 항목이 Rule DB에 없음 — DB 보완 필요(페이지 오류 아님)"})
                    bucket["unchecked"] += 1
                    continue

                status, message = _evaluate_cell(rule, value)
                out_values.append({**cell, "product_canonical": rs.get("product", raw_product),
                                   "status": status, "message": message})
                bucket[status] = bucket.get(status, 0) + 1
            rows_out.append({"category": category, "spec": spec, "values": out_values})

        def _score(b: Dict[str, int]) -> Optional[float]:
            denom = b["pass"] + b["fail"]
            return round(100 * b["pass"] / denom, 1) if denom else None

        per_product = [{"product": p, **b, "score": _score(b)} for p, b in product_scores.items()]
        summary = {
            "checked": True,
            "market_product": market_product,
            "per_product": per_product,
            "total_rows": len(rows_out),
        }
        return {"summary": summary, "rows": rows_out, "products": matrix.get("products", [])}


def run_compare_qa(matrix: Dict[str, Any], market_product: Optional[str] = None) -> Dict[str, Any]:
    """함수형 진입점 — CompareQA().evaluate(matrix, market_product)와 동일."""
    return CompareQA().evaluate(matrix, market_product)
