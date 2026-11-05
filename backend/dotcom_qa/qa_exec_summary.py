"""
qa_exec_summary.py — 큐비 · 요약판 데이터 [2026-11 신규]

화면 상단(DATA QA 종합·Spec QA 종합·공통페이지 상태)과 같은 숫자를 한 곳에서 만들어
엑셀 첫 시트 `요약판` · 메일 맨 위 블록 · PPT 2번 슬라이드가 그대로 그린다.

build(page_results, static_run) → {
  product, run_at, headline, conclusion, basis,
  kpis: [{label, value, sub, tier}],
  sites: [{site, country, region, page_type, data_pct, quality_pct, spec_pct, fail, warn, state}],
  top_issues: [{item, kind, sites, sample}],         # 가장 많은 사이트에서 나온 이슈
  url_check: [{site, url, reason}],                  # 에러 페이지로 응답한 등록 URL
  static: {sites, pages, checked, by_status} | None,
  actions: [str]                                      # 지금 할 일 Top 5
}
"""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional


def _pct(n, d):
    return round(100 * n / d, 1) if d else None


def _tier(v, good=80, mid=50):
    if v is None:
        return "none"
    return "good" if v >= good else "mid" if v >= mid else "bad"


def _site_label(pr) -> str:
    sc = pr.get("sitecode") or ""
    c = pr.get("country") or ""
    return f"{sc} {c}".strip()


def build(page_results: List[Dict[str, Any]], static_run: Optional[Dict[str, Any]] = None, run_at: str = "") -> Dict[str, Any]:
    results = page_results or []
    checked = [p for p in results if not p.get("not_checked")]
    url_check = [{"site": _site_label(p), "url": p.get("url", ""),
                  "reason": next((f.get("as_is", "") for f in (p.get("schema") or {}).get("findings", []) if f.get("as_is")), "")}
                 for p in results if p.get("url_check_needed")]
    not_collected = [p for p in results if p.get("not_checked") and not p.get("url_check_needed")]
    products = sorted({p.get("product") for p in results if p.get("product")})
    product = ", ".join(products) if products else ""

    # ── 사이트별 한 줄 ──
    sites: List[Dict[str, Any]] = []
    fail_total = warn_total = 0
    data_ok = data_tot = 0
    quality_vals: List[float] = []
    spec_pass = spec_fail = 0
    dist = Counter()
    issue_sites: Dict[str, set] = defaultdict(set)
    issue_sample: Dict[str, str] = {}
    issue_kind: Dict[str, str] = {}
    for p in checked:
        sch = p.get("schema") or {}
        f_cnt = sum(1 for f in sch.get("findings", []) if f.get("status") == "fail")
        w_cnt = sum(1 for f in sch.get("findings", []) if f.get("status") == "warn")
        for f in sch.get("findings", []):
            if f.get("status") in ("fail", "warn"):
                key = f"[스키마] {f.get('block', '')}"
                issue_sites[key].add(p.get("sitecode")); issue_kind[key] = "오류" if f.get("status") == "fail" else "확인"
                issue_sample.setdefault(key, (f.get("as_is") or "")[:90])
        for it in (p.get("seo") or {}).get("items", []) or []:
            if it.get("status") in ("fail", "warn"):
                key = f"[SEO] {it.get('element', '')} — {it.get('issue', '')}"
                issue_sites[key].add(p.get("sitecode")); issue_kind[key] = "오류" if it.get("status") == "fail" else "확인"
                issue_sample.setdefault(key, (it.get("value") or "")[:90])
                if it.get("status") == "fail":
                    f_cnt += 1
                else:
                    w_cnt += 1
        for f in (p.get("copy") or {}).get("findings", []) or []:
            if f.get("status") in ("fail", "warn"):
                key = f"[카피] {f.get('kind', '')} {f.get('token', '') or f.get('category', '')}"
                issue_sites[key].add(p.get("sitecode")); issue_kind[key] = "오류" if f.get("status") == "fail" else "확인"
                issue_sample.setdefault(key, (f.get("as_is") or "")[:90])
                if f.get("status") == "fail":
                    f_cnt += 1
                else:
                    w_cnt += 1
        sv = p.get("spec_v2") or {}
        s_fail = s_warn = s_pass = 0
        for it in sv.get("items", []) or []:
            st = it.get("status")
            if st == "fail":
                s_fail += 1
                key = f"[스펙] {it.get('attribute', '')}"
                issue_sites[key].add(p.get("sitecode")); issue_kind[key] = "오류"; issue_sample.setdefault(key, (it.get("message") or "")[:90])
            elif st == "warn":
                s_warn += 1
                key = f"[스펙] {it.get('attribute', '')}"
                issue_sites[key].add(p.get("sitecode")); issue_kind.setdefault(key, "확인"); issue_sample.setdefault(key, (it.get("message") or "")[:90])
            elif st == "pass":
                s_pass += 1
        spec_pass += s_pass; spec_fail += s_fail
        hq = (p.get("html_qa") or {}).get("overall") or {}
        d_ok, d_tot = hq.get("prop_ok") or 0, hq.get("prop_total") or 0
        data_ok += d_ok; data_tot += d_tot
        q = hq.get("final_pct")
        if q is not None:
            quality_vals.append(q); dist[hq.get("traffic_light") or _tier(q, 80, 50).replace("good", "green").replace("mid", "yellow").replace("bad", "red")] += 1
        fail_total += f_cnt + s_fail; warn_total += w_cnt + s_warn
        spec_pct = _pct(s_pass, s_pass + s_fail) if (s_pass + s_fail) else None
        state = "🔴 오류" if (f_cnt + s_fail) else ("🟡 확인" if (w_cnt + s_warn) else "🟢 정상")
        sites.append({"site": p.get("sitecode", ""), "country": p.get("country", ""), "region": p.get("region", ""), "page_type": p.get("page_type", ""),
                      "data_pct": _pct(d_ok, d_tot), "quality_pct": q, "spec_pct": spec_pct,
                      "fail": f_cnt + s_fail, "warn": w_cnt + s_warn, "state": state, "url": p.get("url", "")})
    sites.sort(key=lambda s: (-(s["fail"]), -(s["warn"]), s["site"]))

    data_pct = _pct(data_ok, data_tot)
    quality_pct = round(sum(quality_vals) / len(quality_vals), 1) if quality_vals else None
    spec_pct = _pct(spec_pass, spec_pass + spec_fail) if (spec_pass + spec_fail) else None
    clean = sum(1 for s in sites if s["fail"] == 0 and s["warn"] == 0)

    top_issues = sorted(({"item": k, "kind": issue_kind.get(k, ""), "sites": len(v), "sample": issue_sample.get(k, "")}
                         for k, v in issue_sites.items()), key=lambda x: (-x["sites"], 0 if x["kind"] == "오류" else 1, x["item"]))[:8]

    st = None
    if static_run:
        sm = static_run.get("summary") or {}
        st = {"sites": sm.get("sites"), "pages": sm.get("pages"), "checked": sm.get("checked"), "by_status": sm.get("by_status") or {},
              "at": static_run.get("at", "")}

    # ── KPI 띠 (화면 카드와 같은 숫자) ──
    kpis = [
        {"label": "검수 페이지", "value": f"{len(checked)}", "sub": (f"페이지 없음 {len(url_check)} · 수집 실패 {len(not_collected)}" if (url_check or not_collected) else "전부 검수됨"), "tier": ""},
        {"label": "오류 / 확인", "value": f"{fail_total} / {warn_total}", "sub": f"이슈 없는 페이지 {clean}/{len(checked)}", "tier": "bad" if fail_total else ("mid" if warn_total else "good")},
        {"label": "데이터 유무", "value": f"{data_pct if data_pct is not None else '-'}%", "sub": f"속성 {data_ok}/{data_tot}", "tier": _tier(data_pct)},
        {"label": "AEO 퀄리티", "value": f"{quality_pct if quality_pct is not None else '-'}%", "sub": f"🟢{dist.get('green', 0)} 🟡{dist.get('yellow', 0)} 🔴{dist.get('red', 0)}", "tier": _tier(quality_pct)},
        {"label": "스펙 일치율", "value": f"{spec_pct if spec_pct is not None else '-'}%", "sub": f"일치 {spec_pass} · 불일치 {spec_fail}", "tier": _tier(spec_pct)},
    ]
    if st:
        bs = st["by_status"]
        ok = bs.get("정상", 0); total_static = st.get("checked") or sum(bs.values()) or 0
        kpis.append({"label": "공통페이지 정상", "value": f"{_pct(ok, total_static) if total_static else '-'}%", "sub": f"{ok}/{total_static} · 파싱 실패 {bs.get('파싱 실패', 0)}", "tier": _tier(_pct(ok, total_static))})

    # ── 한 줄 결론 / 할 일 ──
    if not checked:
        headline = "검수된 페이지 없음"
        conclusion = "URL 을 점검하거나 검수를 다시 실행하세요." if url_check else "검수를 실행하면 요약이 표시됩니다."
    else:
        headline = (f"오류 {fail_total}건 · 확인 {warn_total}건 — 검수 {len(checked)}페이지" + (f" · URL 점검 {len(url_check)}건" if url_check else ""))
        worst = sites[0] if sites else None
        if fail_total == 0 and warn_total == 0:
            conclusion = "모든 검수 페이지에서 오류·확인 사항이 없습니다. 현 상태 유지."
        elif fail_total == 0:
            conclusion = f"확정 오류는 없고 확인 사항만 {warn_total}건 — 전작 값·라벨 미동반 등 사유를 보고 수정 여부를 정하세요."
        else:
            conclusion = (f"가장 많은 사이트에 나타난 오류는 '{top_issues[0]['item']}'({top_issues[0]['sites']}개 사이트)"
                          if top_issues and top_issues[0]["kind"] == "오류" else f"오류가 가장 많은 사이트는 {worst['site']}({worst['fail']}건)") + " — 여기부터 수정."
    actions: List[str] = []
    for ti in top_issues:
        if ti["kind"] == "오류":
            actions.append(f"{ti['item']} 수정 ({ti['sites']}개 사이트)" + (f" — {ti['sample']}" if ti["sample"] else ""))
        if len(actions) >= 3:
            break
    if url_check:
        actions.append(f"레지스트리 URL {len(url_check)}건 갱신 (에러 페이지로 응답: {', '.join(u['site'].split()[0] for u in url_check[:6])}{'…' if len(url_check) > 6 else ''})")
    for ti in top_issues:
        if ti["kind"] == "확인" and len(actions) < 5:
            actions.append(f"{ti['item']} 확인 ({ti['sites']}개 사이트) — {ti['sample']}")
    if st and st["by_status"].get("파싱 실패"):
        actions.append(f"공통페이지 JSON-LD 파싱 실패 {st['by_status']['파싱 실패']}건 수정 (검색엔진이 블록을 못 읽음)")
    actions = actions[:5] or ["현 상태 유지 — 다음 검수에서 변화만 확인"]

    return {"product": product, "run_at": run_at, "headline": headline, "conclusion": conclusion, "kpis": kpis, "sites": sites,
            "top_issues": top_issues, "url_check": url_check, "static": st, "actions": actions,
            "basis": ("판단 기준: 오류 = 틀린 값·누락이 확정된 항목 · 확인 = 사람이 봐야 하는 항목(전작 값·라벨 미동반 등, 점수 분모 제외) · "
                      "데이터 유무 = 충족 속성/필수+권장 속성 · AEO 퀄리티 = 타입별 정보적합성 평균(없는 필수 블록 0점 포함) · "
                      "스펙 일치율 = 일치/(일치+불일치) · 에러 페이지 URL 은 검수 제외")}
