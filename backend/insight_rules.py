"""
insight_rules.py — ABC 툴 공통 인사이트 엔진 [2026-11 신규]

화면(애플스토커·큐비·honeyComb·권역 오버뷰), 이메일 본문, Quick View 가 모두 이 모듈의 결과를 그대로 쓴다.
→ 같은 데이터에 대해 어디서 보든 같은 문장이 나온다.

문장 형식 (사용자 합의안, 2026-11)
    [누가] [무엇이] [수치] (비교 기준) 부족/열세/우세 → [어디에] [무엇을] 필요
    · 결론은 "~부족", "~열세", "~우세", 할 일은 "~필요"로 끝낸다.
    · 수집 데이터에 없는 원인은 쓰지 않는다. 할 일은 대상(페이지·속성·사이트)이 특정될 때만 쓴다.
    · '관찰', '시사점', '인사이트:', '그래서:' 같은 표현은 쓰지 않는다.

판단 기준 (사용자 합의안, 2026-11)
    · 70점(%) 미만 = 부족
    · 비교 대상보다 10%p 이상 낮음 = 열세 / 10%p 이상 높음 = 우세
각 결과에는 화면에 그대로 표시할 basis(판단 기준) 문구를 함께 담는다.

반환 형식 (모든 시스템 공통) — Insight dict
    {"rule": "D2", "sev": 1|2|3, "metric": "data|copy|visual|...", "site": "samsung",
     "text": "결론 문장", "action": "할 일 문장(없으면 \"\")", "line": "text → action"}
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

# [2026-11] 용량 제한(47KB)으로 공통·appleStalker·메일 HTML 은 insight_rules_base.py 로 분리.
#   아래에서 같은 이름으로 전부 다시 내보내므로 기존 호출부(insight_rules.xxx)는 수정 없이 동작한다.
from insight_rules_base import (  # noqa: F401
    BASIS_SCORE,
    CAT_KO,
    COMP_KO,
    FIELD_KO,
    GAP_PP,
    MAX_LINES,
    METRIC_EN,
    ROLE_KO,
    SCHEMA_MEANINGFUL,
    SCHEMA_PRIORITY,
    SCHEMA_WHERE,
    SITE_SHORT,
    WEAK_BELOW,
    _CASE,
    _PRICE_KW,
    _SEV_DOT_HTML,
    _avg,
    _bucket,
    _by_priority,
    _cat,
    _change_kind,
    _competitor_detail,
    _copy_pages,
    _esc,
    _evidence_ratio,
    _ins,
    _join,
    _num,
    _paths,
    _pct,
    _quant_avg,
    _role,
    _samsung_detail,
    _schema_types,
    _sent_counts,
    _top,
    apple_stalker_insights,
    change_insights,
    email_box_html,
    email_line_html,
    humanize_change_summary,
    metric_components,
    metric_total,
    page_insights,
    page_name,
    site_short,
)


# ════════════════════════════════════════════════════════════════
# 2. 큐비(QA Bee) — DATA QA / 스펙 QA / 공통페이지 QA  [Q1~Q4, C1]
#    100%가 아닐 때 '무엇이 문제인지'를 영향 사이트 수 순으로 최대 3줄
# ════════════════════════════════════════════════════════════════
BASIS_QA = "판단 기준: 100% 미만일 때만 원인 표시 · 영향 사이트 많은 순 상위 3개 · 권역은 전체 평균보다 10%p 이상 낮으면 열세"


def _sites_txt(codes: Iterable[str], n: int = 4) -> str:
    return _join([str(c or "").upper() for c in sorted(set(codes))], n)


_L1_ACTION = {
    "h_tag": "H1을 페이지당 1개로 정리 필요",
    "title": "타이틀 길이 권장 범위로 조정 필요",
    "meta": "검색 설명문(meta description) 길이 조정 필요",
    "description": "검색 설명문(meta description) 길이 조정 필요",
    "schema": "누락된 스키마 블록 추가 필요",
}


def _region_gap_line(rows: List[Dict[str, Any]], score_of, label: str) -> Optional[Dict[str, Any]]:
    by: Dict[str, List[float]] = {}
    for r in rows:
        v = score_of(r)
        if v is not None:
            by.setdefault(r.get("region") or "기타", []).append(v)
    if len(by) < 2:
        return None
    avg_all = _avg(v for vs in by.values() for v in vs)
    reg, vs = min(by.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
    ra = round(sum(vs) / len(vs), 1)
    if avg_all is None or avg_all - ra < GAP_PP:
        return None
    return _ins("Q2", 2, f"{reg} 권역 {label} {ra}%, 전체 평균 {avg_all}% 대비 열세 ({len(vs)}개 사이트)",
                f"{reg} 법인 우선 조치 필요", region=reg)


def qb_data_insights(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """DATA QA 행(사이트×페이지) → '어떤 속성이 몇 개 사이트에서 누락'. [Q1·Q2]"""
    req: Dict[Tuple[str, str, str], set] = {}
    rec: Dict[Tuple[str, str, str], set] = {}
    l1: Dict[Tuple[str, str], set] = {}
    for r in rows or []:
        hq = r.get("html_qa") or {}
        code = r.get("sitecode") or r.get("country") or ""
        pt = r.get("page_type") or "PDP"
        for typ, v in (((hq.get("level2") or {}).get("per_type")) or {}).items():
            for p in v.get("missing_required") or []:
                req.setdefault((typ, p, pt), set()).add(code)
            for p in v.get("weak_recommended") or []:
                rec.setdefault((typ, p, pt), set()).add(code)
        for it in ((hq.get("level1_apply_rate") or {}).get("items")) or []:
            if it.get("pass") is False:
                l1.setdefault((it.get("item") or "", it.get("category") or ""), set()).add(code)
    out = []
    for (typ, p, pt), codes in sorted(req.items(), key=lambda kv: -len(kv[1])):
        out.append(_ins("Q1", 1, f"{typ} {p} 필수 속성 누락 {len(codes)}개 사이트 ({_sites_txt(codes)})",
                        f"해당 사이트 {pt} {typ} 스키마에 {p} 등록 필요", n=len(codes)))
    for (item, cat), codes in sorted(l1.items(), key=lambda kv: -len(kv[1])):
        out.append(_ins("Q1", 2, f"{item} 미충족 {len(codes)}개 사이트 ({_sites_txt(codes)})",
                        _L1_ACTION.get(cat, "해당 항목 가이드 기준으로 수정 필요"), n=len(codes)))
    for (typ, p, pt), codes in sorted(rec.items(), key=lambda kv: -len(kv[1])):
        out.append(_ins("Q1", 3, f"{typ} {p} 권장 속성 미흡 {len(codes)}개 사이트 ({_sites_txt(codes)})",
                        f"{pt} {typ} 스키마에 {p} 보강 필요", n=len(codes)))
    rg = _region_gap_line(rows or [], lambda r: ((r.get("html_qa") or {}).get("overall") or {}).get("final_pct"), "AEO 퀄리티")
    lines = _top(out, 2 if rg else MAX_LINES) + ([rg] if rg else [])
    return {"top": _top(lines), "basis": BASIS_QA}


def qb_spec_insights(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """스펙 QA 행 → '어떤 스펙이 몇 개 사이트에서 틀렸고 정답은 무엇'. [Q3]"""
    fails: Dict[Tuple[str, str], Dict[str, Any]] = {}
    warns: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in rows or []:
        code = r.get("sitecode") or r.get("country") or ""
        for src in ("spec_v2", "compare_v2"):
            for it in ((r.get(src) or {}).get("items")) or []:
                st = it.get("status")
                if st not in ("fail", "warn"):
                    continue
                key = (it.get("attribute") or it.get("rule_id") or "", it.get("page") or r.get("page_type") or "")
                d = (fails if st == "fail" else warns).setdefault(key, {"codes": set(), "expected": it.get("expected") or "",
                                                                        "unit": it.get("unit") or ""})
                d["codes"].add(code)
    out = []
    for (attr, page), d in sorted(fails.items(), key=lambda kv: -len(kv[1]["codes"])):
        exp = f", 정답 {d['expected']}{(' ' + d['unit']) if d['unit'] and d['unit'] not in str(d['expected']) else ''}" if d["expected"] else ""
        out.append(_ins("Q3", 1, f"{attr} 오류 {len(d['codes'])}개 사이트 ({_sites_txt(d['codes'])}){exp}",
                        f"해당 사이트 {page or '페이지'} {attr} 표기 수정 필요", n=len(d["codes"])))
    for (attr, page), d in sorted(warns.items(), key=lambda kv: -len(kv[1]["codes"])):
        out.append(_ins("Q3", 2, f"{attr} 확인 필요 {len(d['codes'])}개 사이트 ({_sites_txt(d['codes'])})",
                        f"{attr} 표기 단위·형식 확인 필요", n=len(d["codes"])))
    rg = _region_gap_line(rows or [], lambda r: ((r.get("spec_v2") or {}).get("summary") or {}).get("score"), "스펙 정확도")
    lines = _top(out, 2 if rg else MAX_LINES) + ([rg] if rg else [])
    return {"top": _top(lines), "basis": BASIS_QA}


_STATIC_ACTION = {
    "파싱 실패": "JSON-LD 문법(따옴표·쉼표·괄호) 수정 필요",
    "오적용": "다른 국가 주소 참조를 해당 국가 @id로 교체 필요",
    "미해결 참조": "참조하는 @id 정의 블록 추가 필요",
    "페이지 없음": "URL 변경 여부 확인 후 대상 목록 갱신 필요",
    "접근 실패": "접근 차단·프록시 설정 확인 필요",
    "기타": "JSON-LD 스키마 추가 필요",
}
_STATIC_SEV = {"파싱 실패": 1, "오적용": 1, "미해결 참조": 2, "기타": 2, "페이지 없음": 3, "접근 실패": 3}
_PARSE_CAT_KO = {"smart_quote": "둥근 따옴표", "invisible_char": "보이지 않는 문자", "missing_comma": "쉼표 누락",
                 "unbalanced": "괄호 짝 불일치", "trailing_comma": "마지막 쉼표", "unescaped": "이스케이프 누락",
                 "syntax": "문법 오류"}


def qb_static_insights(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """공통페이지 QA → '어떤 페이지에서 어떤 오류가 몇 개 사이트'. [Q4]"""
    grp: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in results or []:
        st = r.get("status")
        if not st or st == "정상":
            continue
        d = grp.setdefault((r.get("page_label") or r.get("page") or "", st), {"codes": set(), "cats": Counter()})
        d["codes"].add(r.get("sitecode") or "")
        for pe in r.get("parse_errors") or []:
            d["cats"][pe.get("category") or "syntax"] += 1
    out = []
    for (page, st), d in sorted(grp.items(), key=lambda kv: (_STATIC_SEV.get(kv[0][1], 3), -len(kv[1]["codes"]))):
        why = ""
        if st == "파싱 실패" and d["cats"]:
            why = f", 주원인 {_PARSE_CAT_KO.get(d['cats'].most_common(1)[0][0], '문법 오류')}"
        out.append(_ins("Q4", _STATIC_SEV.get(st, 3), f"{page} {st} {len(d['codes'])}개 사이트 ({_sites_txt(d['codes'])}){why}",
                        _STATIC_ACTION.get(st, ""), n=len(d["codes"])))
    def _ok(r):
        return 100.0 if r.get("status") == "정상" else 0.0 if r.get("status") not in ("페이지 없음", "접근 실패") else None
    rg = _region_gap_line(results or [], _ok, "정상률")
    lines = _top(out, 2 if rg else MAX_LINES) + ([rg] if rg else [])
    return {"top": _top(lines), "basis": BASIS_QA}


# ════════════════════════════════════════════════════════════════
# 3. honeyComb — Google Shopping 노출 (삼성 vs Apple)  [H1~H6]
# ════════════════════════════════════════════════════════════════
BASIS_HC = (f"판단 기준: 1위 비율·속성 노출 {WEAK_BELOW}% 미만 = 부족 · Apple보다 {GAP_PP}%p 이상 낮음 = 열세 · "
            "가격은 1위 판매처가 5% 이상 저렴할 때 표시 · '확인 안 함' 속성은 계산에서 제외")

# GMC 속성 → 화면 영역(사용자 표현: '이미지 영역' 등)
HC_GROUPS = {
    "이미지": ["image_link", "additional_image_link", "lifestyle_image_link", "video_link", "virtual_model_link"],
    "가격·프로모션": ["price", "sale_price", "sale_price_effective_date", "installment", "promotion_id", "availability", "availability_date"],
    "식별자": ["brand", "gtin", "mpn"],
    "상세 정보": ["description", "product_highlight", "product_detail", "color", "size", "material", "product_weight",
              "product_length", "product_width", "product_height", "certification", "energy_efficiency_class"],
    "배송": ["shipping", "free_shipping_threshold"],
}
HC_STATUS_KO = {"top1": "1위", "topn": "상단", "low": "8위 밖", "absent": "미노출", "unranked": "순위 없음",
                "unchecked": "미조회", "error": "오류"}
_HC_RANK = {"top1": 0, "topn": 1, "low": 2, "absent": 3}


def _hc_checked(cells):
    return [c for c in cells if c.get("status") in ("top1", "topn", "low", "absent")]


def _hc_top1(cells) -> Optional[float]:
    ch = _hc_checked(cells)
    return round(100 * sum(1 for c in ch if c["status"] == "top1") / len(ch), 1) if ch else None


def _hc_group_rates(cells) -> Dict[str, Dict[str, Any]]:
    """영역별 노출률 — 공식몰 카드가 잡힌 셀만, entered/missed 만 계산('확인 안 함'·피드 전용 제외)."""
    out: Dict[str, Dict[str, Any]] = {}
    for g, codes in HC_GROUPS.items():
        ent = obs = 0
        missed: Counter = Counter()
        for c in cells:
            for k, v in (c.get("attrs") or {}).items():
                code = k.split("#")[0]
                if code not in codes or v not in ("entered", "missed"):
                    continue
                obs += 1
                if v == "entered":
                    ent += 1
                else:
                    missed[code] += 1
        out[g] = {"rate": round(100 * ent / obs, 1) if obs else None, "observed": obs,
                  "missed": [k for k, _ in missed.most_common()]}
    return out


def _price_num(p: Any) -> Optional[float]:
    if p is None:
        return None
    m = re.search(r"(\d[\d.,\s]*)", str(p))
    if not m:
        return None
    t = m.group(1).replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".") if len(t.split(",")[-1]) == 2 else t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def apple_compare(run: Dict[str, Any], label_of=None) -> Optional[Dict[str, Any]]:
    """PPT 8-3 — Apple 대비 전체·국가별 1위 비율, 영역별 속성 노출(우리만큼 자세히는 아님)."""
    cells = run.get("cells") or []
    sam = [c for c in cells if c.get("keyword_type", "brand") == "brand"]
    app = [c for c in cells if c.get("keyword_type") == "competitor"]
    if not app:
        return None
    # Apple 셀은 비교 대상 삼성 제품마다 복사돼 있으므로 (국가, Apple 모델) 단위로 중복 제거해 계산
    seen, app_u = set(), []
    for c in app:
        k = (c["country"], c["keyword"])
        if k not in seen:
            seen.add(k); app_u.append(c)
    countries = sorted({c["country"] for c in sam} | {c["country"] for c in app_u})
    sg, ag = _hc_group_rates([c for c in sam if c.get("attrs")]), _hc_group_rates([c for c in app_u if c.get("attrs")])
    return {
        "models": sorted({c["keyword"] for c in app_u}),
        "overall": {"samsung_top1": _hc_top1(sam), "apple_top1": _hc_top1(app_u)},
        "by_country": [{"country": ct, "samsung_top1": _hc_top1([c for c in sam if c["country"] == ct]),
                        "apple_top1": _hc_top1([c for c in app_u if c["country"] == ct])} for ct in countries],
        "by_group": [{"group": g, "samsung": sg[g]["rate"], "apple": ag[g]["rate"]} for g in HC_GROUPS],
        "by_attr": _hc_attr_compare(sam, app),
    }


def _hc_attr_compare(sam: List[Dict[str, Any]], app: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """[2026-11] 속성별 삼성 vs Apple 노출률 + 'Apple 만 보이는' 국가·제품.
    같은 국가·같은 삼성 제품 칸끼리 비교(Apple 셀은 비교 대상 삼성 제품마다 복사돼 있음). '확인 안 함'·na 제외."""
    stat: Dict[str, Dict[str, Any]] = {}
    def add(key, side, v):
        d = stat.setdefault(key, {"key": key, "group": next((g for g, cs in HC_GROUPS.items() if key.split("#")[0] in cs), "기타"),
                                  "s_ent": 0, "s_obs": 0, "a_ent": 0, "a_obs": 0, "apple_only": [], "samsung_only": []})
        if v in ("entered", "missed"):
            d[f"{side}_obs"] += 1
            d[f"{side}_ent"] += v == "entered"
    seen_a = set()
    for c in app:   # Apple 노출률은 (국가, 모델) 단위로 1회만
        k = (c["country"], c["keyword"])
        if k in seen_a:
            continue
        seen_a.add(k)
        for key, v in (c.get("attrs") or {}).items():
            add(key, "a", v)
    for c in sam:
        for key, v in (c.get("attrs") or {}).items():
            add(key, "s", v)
    # 같은 국가·제품 칸에서 한쪽만 보이는 경우
    s_by = {}
    for c in sam:
        if c.get("attrs"):
            s_by.setdefault((c["country"], c["product"]), []).append(c)
    for a in app:
        for sc in s_by.get((a["country"], a["product"]), []):
            for key, av in (a.get("attrs") or {}).items():
                sv = (sc.get("attrs") or {}).get(key)
                if key not in stat:
                    continue
                tag = f"{a['country']} {a['product']}"
                if av == "entered" and sv == "missed" and tag not in stat[key]["apple_only"]:
                    stat[key]["apple_only"].append(tag)
                elif av == "missed" and sv == "entered" and tag not in stat[key]["samsung_only"]:
                    stat[key]["samsung_only"].append(tag)
    out = []
    for d in stat.values():
        if not (d["s_obs"] or d["a_obs"]):
            continue
        sr = round(100 * d["s_ent"] / d["s_obs"], 1) if d["s_obs"] else None
        ar = round(100 * d["a_ent"] / d["a_obs"], 1) if d["a_obs"] else None
        out.append({"key": d["key"], "group": d["group"], "samsung": sr, "apple": ar,
                    "gap": (ar - sr) if (ar is not None and sr is not None) else None,
                    "apple_only": d["apple_only"], "samsung_only": d["samsung_only"]})
    out.sort(key=lambda x: (-(x["gap"] or -999), x["key"]))
    return out


def hc_insights(run: Dict[str, Any], prev: Optional[Dict[str, Any]] = None,
                product_label: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    plabel = product_label or {}
    pl = lambda s: plabel.get(s, s)
    cells = run.get("cells") or []
    sam = [c for c in cells if c.get("keyword_type", "brand") == "brand"]
    app = [c for c in cells if c.get("keyword_type") == "competitor"]
    out: List[Dict[str, Any]] = []
    checked = _hc_checked(sam)
    if not checked:
        return {"top": [], "all": [], "basis": BASIS_HC, "apple": apple_compare(run)}
    t1 = sum(1 for c in checked if c["status"] == "top1")
    rate = round(100 * t1 / len(checked), 1)
    a_rate = _hc_top1(app)
    stores = Counter(c.get("first_store") for c in checked if c["status"] != "top1" and c.get("first_store"))
    store_txt = _join([f"{s} {n}칸" for s, n in stores.most_common(3)], 3)
    # H1 1위 비율
    if rate < WEAK_BELOW or (a_rate is not None and a_rate - rate >= GAP_PP):
        behind1 = a_rate is not None and a_rate - rate >= GAP_PP
        state = ("로 부족" if rate < WEAK_BELOW else "") + (f", Apple {a_rate}% 대비 열세" if behind1 else "")
        out.append(_ins("H1", 1, f"1위 비율 {rate}% ({t1}/{len(checked)}칸){state}",
                        f"1위 판매처({store_txt}) 대비 삼성닷컴 피드 가격·배송·이미지 속성 보강 필요" if store_txt
                        else "삼성닷컴 피드 가격·배송·이미지 속성 보강 필요"))
    # H4 속성 영역 열세/부족
    sg = _hc_group_rates([c for c in sam if c.get("attrs")])
    ag = _hc_group_rates([c for c in app if c.get("attrs")]) if app else {}
    def _gap(g):
        v, av = sg[g]["rate"], (ag.get(g) or {}).get("rate")
        return (av - v) if (v is not None and av is not None) else (WEAK_BELOW - v if v is not None else -999)
    h4_n = 0
    for g in sorted(sg, key=_gap, reverse=True):
        v = sg[g]
        if v["rate"] is None or h4_n >= 2:     # 영역 열세는 격차 큰 2개까지만(다른 유형이 밀리지 않게)
            continue
        av = (ag.get(g) or {}).get("rate")
        behind = av is not None and av - v["rate"] >= GAP_PP
        if not (behind or v["rate"] < WEAK_BELOW):
            continue
        attrs = v["missed"][:3]
        if behind:
            text = f"상세 속성 중 {g} 영역 Apple 대비 열세 (삼성 {v['rate']}%, Apple {av}%)"
        else:
            text = f"상세 속성 중 {g} 영역 노출 {v['rate']}%로 부족"
        out.append(_ins("H4", 1 if behind else 2, text,
                        f"GMC 피드 내 {_join(attrs)} 속성 추가 필요" if attrs else f"GMC 피드 {g} 속성 점검 필요", group=g))
        h4_n += 1
    # H2 국가 집중
    by_ct: Dict[str, List[Dict[str, Any]]] = {}
    for c in checked:
        by_ct.setdefault(c["country"], []).append(c)
    all_absent = [ct for ct, cs in by_ct.items() if all(c["status"] == "absent" for c in cs)]
    if all_absent:
        out.append(_ins("H2", 1, f"{_join(all_absent)} 전 제품 미노출",
                        f"{_join(all_absent)} GMC 피드 등록·승인 상태 우선 확인 필요"))
    else:
        weak = sorted(((ct, sum(1 for c in cs if c["status"] == "absent") / len(cs)) for ct, cs in by_ct.items()), key=lambda x: -x[1])
        if weak and weak[0][1] >= 0.5:
            ct, r = weak[0]
            out.append(_ins("H2", 2, f"{ct} 제품 {round(r * 100)}% 미노출로 국가 중 가장 부족",
                            f"{ct} GMC 피드 등록·승인 상태 확인 필요"))
    # H3 제품 집중
    by_pr: Dict[str, List[Dict[str, Any]]] = {}
    for c in checked:
        by_pr.setdefault(c["product"], []).append(c)
    for prd, cs in sorted(by_pr.items(), key=lambda kv: -sum(1 for c in kv[1] if c["status"] == "absent")):
        n_abs = sum(1 for c in cs if c["status"] == "absent")
        if n_abs * 2 >= len(cs) and n_abs >= 2:
            out.append(_ins("H3", 2, f"{pl(prd)} {len(cs)}개국 중 {n_abs}개국 미노출",
                            f"{pl(prd)} 피드 등록·노출 우선 점검 필요"))
            break
    # H5 가격 격차 (1위가 타 판매처이고 삼성 카드도 있는 칸)
    best_gap = None
    for c in checked:
        top = (c.get("items_top") or [{}])[0]
        our = c.get("our_item") or {}
        if not top or not our or top.get("merchant") == our.get("merchant"):
            continue
        tp, op = _price_num(top.get("price")), _price_num(our.get("price"))
        if tp and op and op > tp:
            gap = round((op - tp) / op * 100, 1)
            if gap >= 5 and (best_gap is None or gap > best_gap[0]):
                best_gap = (gap, c, top, our)
    if best_gap:
        gap, c, top, our = best_gap
        out.append(_ins("H5", 2, f"{c['country']} {pl(c['product'])} 1위 {top.get('merchant')} 가격이 삼성닷컴보다 {gap}% 낮음 ({top.get('price')} vs {our.get('price')})",
                        "삼성닷컴 피드 sale_price·promotion 반영 여부 확인 필요"))
    # H6 주간 하락
    if prev:
        pk = {(c["country"], c["product"], c["keyword"]): c for c in prev.get("cells") or [] if c.get("keyword_type", "brand") == "brand"}
        drops = []
        for c in checked:
            o = pk.get((c["country"], c["product"], c["keyword"]))
            if o and o.get("status") in _HC_RANK and _HC_RANK[c["status"]] > _HC_RANK[o["status"]]:
                drops.append((c, o))
        if drops:
            c, o = max(drops, key=lambda x: _HC_RANK[x[0]["status"]] - _HC_RANK[x[1]["status"]])
            more = f" 외 {len(drops) - 1}칸" if len(drops) > 1 else ""
            out.append(_ins("H6", 2, f"{c['country']} {pl(c['product'])} {HC_STATUS_KO[o['status']]} → {HC_STATUS_KO[c['status']]}로 하락{more}",
                            "해당 국가·제품 피드 변경 이력 확인 필요"))
    return {"top": _top(out), "all": sorted(out, key=lambda x: x["sev"]), "basis": BASIS_HC, "apple": apple_compare(run)}


# ════════════════════════════════════════════════════════════════
# 4. 권역별 OVERVIEW — 세 도구 신호등 → 권역별 주원인 + 공통 이슈  [R1·R2]
# ════════════════════════════════════════════════════════════════
BASIS_REGION = "통일 기준: 문제 사이트 = 도구별 판정이 🔴(지금 고쳐야 함)인 사이트 · 🟡 = 확인 필요 · 절반 이상 권역에 같은 도구 문제가 있으면 공통 이슈로 묶음"
TOOL_KO = {"data": "DATA QA(스키마)", "spec": "스펙 QA", "static": "공통페이지 QA", "hc": "honeyComb 노출"}
TOOL_ACTION = {"data": "PDP 스키마 필수 속성 등록 필요", "spec": "PDP·Compare 스펙 표기 수정 필요",
               "static": "공통페이지 JSON-LD 수정 필요", "hc": "GMC 피드 등록·노출 점검 필요"}


# ── [2026-11 E1 v2] 권역 OVERVIEW: 이슈 문장은 '무엇을 검사했고 · 어디가 · 왜 문제인지'가 읽히게 ──
PROP_KO = {"offers.price": "가격", "offers.priceCurrency": "통화", "offers.availability": "재고 상태", "offers": "판매 정보",
           "aggregateRating": "평점", "review": "리뷰", "image": "이미지", "description": "설명", "brand": "브랜드",
           "sku": "SKU", "gtin": "GTIN", "mpn": "모델 번호", "name": "제품명", "url": "URL", "itemListElement": "목록 항목",
           "mainEntity": "질문·답변", "acceptedAnswer": "답변"}
STATIC_MEANING = {"파싱 실패": "JSON-LD(구조화 데이터)에 문법 오류가 있어 검색엔진이 읽지 못함",
                  "오적용": "다른 국가 사이트의 주소(@id)를 가리키고 있음",
                  "미해결 참조": "페이지 안에 정의되지 않은 @id 를 참조하고 있음",
                  "페이지 없음": "페이지가 열리지 않음(404 등)", "접근 실패": "수집기가 페이지에 접근하지 못함(차단·타임아웃)",
                  "기타": "필요한 JSON-LD 가 없음"}


def _prop_ko(tp: str) -> str:
    t, _, prop = tp.partition(" ")
    ko = PROP_KO.get(prop) or PROP_KO.get(prop.split(".")[0])
    return f"{t} 스키마의 {ko}({prop})" if ko else f"{t} 스키마의 {prop}"


def _site_issues(site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """사이트 1곳 × 도구별 이슈. text = 설명형 문장(길어도 됨), short = 표 칸용 짧은 라벨, go = 이동 대상."""
    out: List[Dict[str, Any]] = []
    sc, subs = site.get("sitecode") or "", site.get("subs") or "-"
    who = f"{sc.upper()}({subs})"
    t = site.get("tools") or {}
    sevof = lambda tl: 1 if tl == "red" else 2
    base = dict(subs=subs, sitecode=sc, region=site.get("region"))
    d = t.get("data") or {}
    if d.get("tl") in ("red", "yellow"):
        miss, l1, pt = d.get("missing") or [], d.get("l1_fail") or [], d.get("page_type") or "PDP"
        if miss:
            text = (f"{who} {pt}의 구조화 데이터에 {_prop_ko(miss[0])}가 없음"
                    + (f" (외 {len(miss) - 1}개 필수 항목 누락)" if len(miss) > 1 else "")
                    + f" — 검색엔진·AI 답변이 이 정보를 가져가지 못함. AEO 퀄리티 {d.get('score')}%")
            act, short = f"{pt} {miss[0].split(' ')[0]} 스키마에 {miss[0].split(' ', 1)[-1]} 등록 필요", f"{miss[0].split(' ', 1)[-1]} 누락"
        elif l1:
            text = f"{who} {pt}의 기본 항목 '{l1[0]}' 기준 미충족" + (f" 외 {len(l1) - 1}개" if len(l1) > 1 else "") + f" · AEO 퀄리티 {d.get('score')}%"
            act, short = "H1·타이틀·설명문을 가이드 기준으로 수정 필요", f"{l1[0]} 미충족"
        else:
            text = f"{who} {pt}의 필수 항목은 있으나 권장 항목이 부족해 AEO 퀄리티 {d.get('score')}%"
            act, short = "권장 속성 보강 필요", f"AEO {d.get('score')}%"
        out.append(_ins("E-data", sevof(d["tl"]), text, act, tool="data", short=short, **base,
                        go={"app": "qubi", "tab": "schema", "run_id": d.get("run_id"), "region": d.get("region"), "sitecode": sc}))
    sp = t.get("spec") or {}
    if sp.get("tl") in ("red", "yellow"):
        fails = sp.get("fails") or []
        if fails:
            f0 = fails[0]
            unit = f" {f0['unit']}" if f0.get("unit") and f0["unit"] not in str(f0.get("expected")) else ""
            text = (f"{who} {f0.get('page') or 'PDP'}에 표기된 {f0.get('attribute')}가 '{f0.get('found') or '-'}' 인데 "
                    f"제품 정답은 {f0.get('expected')}{unit}" + (f" (외 {len(fails) - 1}개 스펙 오류)" if len(fails) > 1 else ""))
            act, short = f"{f0.get('page') or 'PDP'}의 {_join([x.get('attribute') for x in fails], 3)} 표기 수정 필요", f"{f0.get('attribute')} 오류"
        else:
            w = sp.get("warns") or []
            text = f"{who} 스펙 {_join(w, 3)} 표기가 정답과 형식·단위가 달라 확인 필요 ({len(w)}건)"
            act, short = "표기 단위·형식 확인 필요", f"{w[0] if w else '스펙'} 확인"
        out.append(_ins("E-spec", sevof(sp["tl"]), text, act, tool="spec", short=short, **base,
                        go={"app": "qubi", "tab": "copy", "run_id": sp.get("run_id"), "region": sp.get("region"), "sitecode": sc}))
    st = t.get("static") or {}
    if st.get("tl") in ("red", "yellow"):
        bad = sorted([pg for pg in (st.get("pages") or []) if pg.get("sev") in ("fail", "warn")],
                     key=lambda pg: _STATIC_SEV.get(pg.get("status"), 3))
        if bad:
            b0 = bad[0]
            why = f" — 원인: {_PARSE_CAT_KO.get(b0['cause'], b0['cause'])}" if b0.get("cause") else ""
            text = (f"{who} 공통페이지 '{b0.get('page')}'의 {STATIC_MEANING.get(b0.get('status'), b0.get('status'))}{why}"
                    + (f" (외 {len(bad) - 1}개 페이지)" if len(bad) > 1 else ""))
            act, short = _STATIC_ACTION.get(b0.get("status"), "JSON-LD 점검 필요"), f"{b0.get('page')} {b0.get('status')}"
        else:
            text, act, short = f"{who} 공통페이지 정상률 {st.get('score')}%", "JSON-LD 점검 필요", f"정상률 {st.get('score')}%"
        out.append(_ins("E-static", sevof(st["tl"]), text, act, tool="static", short=short, **base,
                        go={"app": "qubi", "tab": "static", "run_id": st.get("run_id"), "sitecode": sc,
                            "page": (bad[0].get("page_key") if bad else None)}))
    h = t.get("hc") or {}
    if h.get("tl") in ("red", "yellow"):
        ab, lo = h.get("absent_products") or [], h.get("low_products") or []
        prods = ab or lo
        names = _join([x["label"] for x in prods], 3)
        stores = _join(h.get("first_stores") or [], 2)
        where = "상위 8위 안에 안 보임" if ab else "8위 밖에 있음"
        text = (f"{who} Google Shopping에서 제품명({names})을 검색하면 삼성닷컴 상품이 {where}"
                + (f" — 그 자리 1위는 {stores}" if stores else ""))
        out.append(_ins("E-hc", sevof(h["tl"]), text, f"{subs} GMC 피드에서 {names} 등록·승인 상태 확인 필요",
                        tool="hc", short=f"{prods[0]['label'].replace('Galaxy ', '')}{' 외' if len(prods) > 1 else ''} {'미노출' if ab else '8위 밖'}" if prods else "노출 부족",
                        **base, go={"app": "honeycomb", "run_id": h.get("run_id"), "country": h.get("code"),
                                    "product": prods[0]["slug"] if prods else None}))
    return out


def _tile_sev(reds: int, yellows: int) -> int:
    return 1 if reds else 2 if yellows else 0


def _tool_tiles(sites: List[Dict[str, Any]], issues: List[Dict[str, Any]], apple: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Summary 타일 — 툴마다 그 툴에 맞는 대표 지표(크게) + 통일 기준(작게: 문제 사이트 수 / 검수 사이트 수)."""
    def checked(tool):
        return [s for s in sites if ((s.get("tools") or {}).get(tool) or {}).get("tl")]
    def red(tool):
        return [s for s in sites if ((s.get("tools") or {}).get(tool) or {}).get("tl") == "red"]
    def top_cause(tool):
        c = Counter(i["short"] for i in issues if i["tool"] == tool and i["sev"] == 1)
        return f"{c.most_common(1)[0][0]} {c.most_common(1)[0][1]}곳" if c else ""
    tiles = []
    if apple and apple.get("has_data"):
        tiles.append({"key": "apple", "letter": "A", "name": "appleStalker", "sub": "경쟁사 페이지 변경",
                      "metric": f"{apple.get('changes', 0)}건", "metric_label": f"이번 수집 변경 (High {apple.get('high', 0)})",
                      "note": f"변경 사이트 {len(apple.get('sites') or [])}곳 · 삼성 변경 {'있음' if 'samsung' in (apple.get('sites') or []) else '없음'}",
                      "cause": (apple.get("issues") or [{}])[0].get("short", ""), "go": {"app": "applestalker"},
                      "sev": 1 if apple.get("high") else 2 if apple.get("changes") else 0})
    dc = checked("data")
    if dc:
        sc = [((s["tools"]["data"]).get("score")) for s in dc if s["tools"]["data"].get("score") is not None]
        yel = [s for s in dc if s["tools"]["data"].get("tl") == "yellow"]
        tiles.append({"key": "data", "letter": "B", "name": "qaBee · DATA QA", "sub": "스키마·메타 데이터",
                      "metric": f"{round(sum(sc) / len(sc))}%" if sc else "—", "metric_label": "AEO 퀄리티 평균",
                      "note": f"기준 미달 사이트 {len(red('data'))} / {len(dc)}곳", "cause": top_cause("data"),
                      "go": {"app": "qubi", "tab": "schema"}, "sev": _tile_sev(len(red("data")), len(yel))})
    spc = checked("spec")
    if spc:
        crit = sum((s["tools"]["spec"].get("critical") or 0) for s in spc)
        yel = [s for s in spc if s["tools"]["spec"].get("tl") == "yellow"]
        tiles.append({"key": "spec", "letter": "B", "name": "qaBee · 스펙 QA", "sub": "PDP·Compare 스펙 표기",
                      "metric": f"{crit}건", "metric_label": "스펙 오류 항목",
                      "note": f"오류 사이트 {len(red('spec'))} / {len(spc)}곳", "cause": top_cause("spec"),
                      "go": {"app": "qubi", "tab": "copy"}, "sev": _tile_sev(len(red("spec")), len(yel))})
    stc = checked("static")
    if stc:
        sc = [s["tools"]["static"].get("score") for s in stc if s["tools"]["static"].get("score") is not None]
        yel = [s for s in stc if s["tools"]["static"].get("tl") == "yellow"]
        tiles.append({"key": "static", "letter": "B", "name": "qaBee · 공통페이지 QA", "sub": "Home·Switch to Galaxy 등",
                      "metric": f"{round(sum(sc) / len(sc))}%" if sc else "—", "metric_label": "정상 페이지 비율",
                      "note": f"오류 사이트 {len(red('static'))} / {len(stc)}곳", "cause": top_cause("static"),
                      "go": {"app": "qubi", "tab": "static"}, "sev": _tile_sev(len(red("static")), len(yel))})
    hcc = checked("hc")
    if hcc:
        t1 = sum((s["tools"]["hc"].get("top1") or 0) for s in hcc)
        tot = sum(sum((s["tools"]["hc"].get(k) or 0) for k in ("top1", "topn", "low", "absent")) for s in hcc)
        yel = [s for s in hcc if s["tools"]["hc"].get("tl") == "yellow"]
        tiles.append({"key": "hc", "letter": "C", "name": "honeyComb", "sub": "Google Shopping 노출",
                      "metric": f"{round(100 * t1 / tot)}%" if tot else "—", "metric_label": "삼성닷컴 1위 비율",
                      "note": f"미노출 있는 국가 {len(red('hc'))} / {len(hcc)}개국", "cause": top_cause("hc"),
                      "go": {"app": "honeycomb"}, "sev": _tile_sev(len(red("hc")), len(yel))})
    return tiles


def region_insights(ov: Dict[str, Any], apple: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """권역 OVERVIEW — summary(툴 타일), urgent(급한 이슈, 설명형), sites(사이트 표), by_region·by_subs(지도·법인 패널)."""
    sites = ov.get("sites") or []
    issues = [i for s in sites for i in _site_issues(s)]
    by_subs: Dict[str, List[Dict[str, Any]]] = {}
    for i in issues:
        by_subs.setdefault(i["subs"], []).append(i)
    for v in by_subs.values():
        v.sort(key=lambda x: x["sev"])
    # 사이트 표 — 빨간 도구 많은 순. 칸은 3가지 상태를 구분한다: 이슈(sev1·2) / 정상(검수했고 문제 없음) / 미검수(—).
    site_rows = []
    for s in sites:
        iss = [i for i in issues if i["sitecode"] == (s.get("sitecode") or "")]
        if not iss:
            continue
        cells: Dict[str, Any] = {}
        for tool in ("data", "spec", "static", "hc"):
            hit = next((i for i in iss if i["tool"] == tool), None)
            tl = ((s.get("tools") or {}).get(tool) or {}).get("tl")
            cells[tool] = {"sev": hit["sev"], "short": hit["short"]} if hit else {"sev": 0, "short": "정상"} if tl == "green" else None
        site_rows.append({"sitecode": s.get("sitecode"), "subs": s.get("subs"), "region": s.get("region"), "country": s.get("country"),
                          "red": sum(1 for i in iss if i["sev"] == 1), "cells": cells,
                          "details": sorted(iss, key=lambda x: x["sev"])})
    site_rows.sort(key=lambda r: (-r["red"], -len(r["details"]), r["sitecode"] or ""))
    # 급한 이슈 — 여러 권역 공통(R2) 먼저, 그다음 개별 🔴 이슈(도구가 골고루 보이게), appleStalker 변경 1건
    nreg = len({s.get("region") or "(미분류)" for s in sites})
    urgent: List[Dict[str, Any]] = []
    tool_regions = Counter()
    for tool in TOOL_KO:
        regs = {i.get("region") for i in issues if i["tool"] == tool and i["sev"] == 1}
        tool_regions[tool] = len(regs)
    for tool, k in tool_regions.most_common():
        if nreg >= 2 and k * 2 >= nreg and k >= 2:
            det = [i for i in issues if i["tool"] == tool and i["sev"] == 1]
            causes = Counter(i["short"] for i in det)
            urgent.append(_ins("R2", 1, f"{TOOL_KO[tool]}에서 같은 유형의 문제가 {k}개 권역 {len(det)}개 사이트에 퍼져 있음 — 가장 많은 것: "
                                        + ", ".join(f"{c} {n}곳" for c, n in causes.most_common(2)),
                               "개별 법인 수정보다 본사 템플릿·공통 가이드 단위로 고치는 것이 빠름", tool=tool, details=det))
    reds = [i for i in issues if i["sev"] == 1]
    picked: List[Dict[str, Any]] = []
    for tool in ("hc", "data", "spec", "static"):   # 도구별 가장 심한 1건씩 먼저
        cand = [i for i in reds if i["tool"] == tool and i not in picked]
        if cand:
            picked.append(cand[0])
    picked += [i for i in reds if i not in picked]
    urgent += picked[: max(0, 5 - len(urgent))]
    for ai in ((apple or {}).get("issues") or [])[:1]:
        urgent.append(ai)
    by_region = {}
    for reg in {s.get("region") or "(미분류)" for s in sites}:
        rr = [r for r in site_rows if (r.get("region") or "(미분류)") == reg]
        if rr:
            by_region[reg] = {"short": f"문제 사이트 {len(rr)}곳", "first": rr[0]["details"][0]["text"], "line": rr[0]["details"][0]["line"]}
    return {"summary": _tool_tiles(sites, issues, apple), "urgent": urgent, "sites": site_rows,
            "by_region": by_region, "by_subs": by_subs, "basis": BASIS_REGION,
            "top": urgent[:MAX_LINES]}
