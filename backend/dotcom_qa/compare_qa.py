"""
compare_qa.py — 큐비 — Compare Pipeline · Step 2 (CompareQA)

Compare QA는 Spec 하나당 "Product별" 값을 모두 검사한다.
  예) Battery — Fold7 ✔ / Fold6 ✔ / Fold5 ✖

정답지 소스(신규 룰셋 없이 기존 Rule DB를 그대로 재사용한다)
  · 자사(크롤 대상, market_product) 값  → spec_rule_db.load(market_product)["rules"]
      (attribute/expected/unit/validation)
  · 이전 세대(Compare에 함께 뜨는 Fold6/Fold5 등) 값 → 같은 룰셋의
    ruleset["previous_models"] = [{"model","aliases","specs":[{"attribute","values","unit"}]}]
    (이미 전작 오귀속 방지용으로 존재하던 데이터를 여기서는 "그 전작 자신의 정답"으로 활용)
  · product_aliases(자사) + previous_models[].aliases(전작) 를 합쳐 Compare Header의
    표기(현지어 포함: "갤럭시 Z 폴드6")를 정답지의 제품과 매칭한다.

룰셋에 없는 제품(예: 경쟁사 제품, 등록되지 않은 세대)이 Compare에 함께 노출된 경우는
"unchecked"로 표시한다 — 정답 데이터가 없다는 뜻이지 페이지 오류가 아니다(오탐 방지).

기존 PDP QA(spec_engine.run)는 이 모듈과 완전히 분리되어 있으며 전혀 수정하지 않는다.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

import spec_rule_db
import spec_value_match as svm
import spec_engine  # 정규화/alias 매칭 유틸(_aliases_for/_label_hit) 재사용 — 값 자체가 아니라 로직만 공유


def _norm_loose(s: str) -> str:
    return re.sub(r"[^\w]|_", "", svm.normalize_text(s))


def _build_answer_key(ruleset: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """룰셋 → {canonical_product_name: {"aliases": [...], "specs": [rule-shaped dict, ...]}}."""
    answer_key: Dict[str, Dict[str, Any]] = {}

    # 자사(현재 룰셋의 제품)
    self_aliases = ruleset.get("product_aliases") or [ruleset.get("product", "")]
    self_name = self_aliases[0] if self_aliases else ruleset.get("product", "")
    if self_name:
        answer_key[self_name] = {"aliases": self_aliases, "specs": list(ruleset.get("rules") or [])}

    # 전작들
    for pm in ruleset.get("previous_models") or []:
        model = pm.get("model")
        if not model:
            continue
        specs = []
        for sp in pm.get("specs") or []:
            expected = "|".join(str(v) for v in (sp.get("values") or []) if v is not None and str(v) != "")
            if not expected:
                continue
            specs.append({
                "attribute": sp.get("attribute", ""),
                "expected": expected,
                "unit": sp.get("unit", ""),
                # previous_models 값은 숫자/단위 표기가 정형화돼 있어 다음 순서로 판정한다:
                # 단위가 있으면 numeric_exact, 없으면 exact(문자열 값).
                "validation": "numeric_exact" if sp.get("unit") else "exact",
            })
        answer_key[model] = {"aliases": [model] + list(pm.get("aliases") or []), "specs": specs}

    return answer_key


def _resolve_product(raw_hint: str, answer_key: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Compare Header/셀의 product_hint 문자열을 정답지의 canonical 제품명으로 해석.
    순서 의존 없이 alias(제품명 표기 전체 — 다국어 포함) 매칭만으로 결정한다."""
    hn = _norm_loose(raw_hint)
    if not hn:
        return None
    best, best_len = None, 0
    for canon, entry in answer_key.items():
        for alias in entry.get("aliases", []):
            an = _norm_loose(alias)
            if an and (an == hn or an in hn or hn in an):
                if len(an) > best_len:
                    best, best_len = canon, len(an)
    return best


def _find_rule(spec_label: str, category: str, specs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """(category, spec) 텍스트에 매칭되는 정답 룰을 찾는다 — dictionary alias는 자사 룰(Rule DB)에만
    존재하므로 있으면 쓰고, 전작 specs처럼 attribute만 있는 경우 label 직접 비교로 폴백한다."""
    label_norm = _norm_loose(f"{category} {spec_label}")
    spec_only_norm = _norm_loose(spec_label)
    for rule in specs:
        attr = rule.get("attribute", "")
        an = _norm_loose(attr)
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

    def evaluate(self, matrix: Dict[str, Any], market_product: str) -> Dict[str, Any]:
        ruleset = spec_rule_db.load(market_product) if market_product else None
        if not ruleset:
            return {"summary": {"checked": False,
                                 "reason": f"'{market_product}' Rule DB 없음 — Compare QA 스킵"},
                    "rows": matrix.get("rows", []), "products": matrix.get("products", [])}

        answer_key = _build_answer_key(ruleset)
        rows_out = []
        product_scores: Dict[str, Dict[str, int]] = {}

        for row in matrix.get("rows", []):
            category, spec = row.get("category", ""), row.get("spec", "")
            out_values = []
            for cell in row.get("values", []):
                raw_product, value = cell.get("product", ""), cell.get("value", "")
                canon = _resolve_product(raw_product, answer_key)
                if canon is None:
                    out_values.append({**cell, "status": "unchecked",
                                       "message": "정답 데이터 없음(미등록 제품/세대)"})
                    continue
                rule = _find_rule(spec, category, answer_key[canon]["specs"])
                if rule is None:
                    out_values.append({**cell, "status": "unchecked",
                                       "message": "이 항목의 Rule DB 정답 없음"})
                    continue
                status, message = _evaluate_cell(rule, value)
                out_values.append({**cell, "product_canonical": canon,
                                   "status": status, "message": message})
                bucket = product_scores.setdefault(canon, {"pass": 0, "fail": 0, "warn": 0, "na": 0, "unchecked": 0})
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


def run_compare_qa(matrix: Dict[str, Any], market_product: str) -> Dict[str, Any]:
    """함수형 진입점 — CompareQA().evaluate(matrix, market_product)와 동일."""
    return CompareQA().evaluate(matrix, market_product)
