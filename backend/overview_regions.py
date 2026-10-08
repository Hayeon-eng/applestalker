"""
overview_regions.py — [2026-10] 권역별 OVERVIEW 집계 (/api/overview/regions)

세 툴의 "가장 최근 결과"를 사이트코드 단위로 모은 뒤 법인(subs)·총괄(region)로 묶어 신호등을 매긴다.
  · 큐비 Data QA : QbHistory 최신순 → 사이트코드별 첫 html_qa.overall.final_pct (80↑ green / 50↑ yellow / 미만 red)
  · 큐비 Spec QA : QbHistory 최신순 → 사이트코드별 첫 spec_v2.summary(또는 Compare compare_v2) (critical≥1 red / warning≥1 yellow / green)
  · 공통페이지 QA : 최신 static run → 사이트코드별 pass/warn/fail/na → 정상률(na 제외) (80/50)
  · honeyComb   : 최신 run cells → 국가코드→sitecode(hc_config) → 셀 상태 worst (absent red / low yellow / top1·topn green)
  · Apple Stalker: 권역 개념 없음 → 상단 글로벌 카드용 요약만(main.py 가 latest_report 로 채운다)

축: 사이트코드 → 법인(subs, sitecodes_master) → 총괄(region, site_registry: EHQ/MENA/NALA/APAC/CIS/G.CN/SEC KOREA/JAPAN/SWA)
신호등 규칙은 프론트 qubiShared.tlByScore / tlSpec 과 동일. 추정 값 없음 — 데이터 없는 칸은 null(회색).
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(_HERE, "dotcom_qa"), os.path.join(_HERE, "honeycomb")):
    if p not in sys.path:
        sys.path.insert(0, p)

ORDER = {"red": 3, "yellow": 2, "green": 1, None: 0}


def worst(*tls: Optional[str]) -> Optional[str]:
    return max((t for t in tls if t), key=lambda t: ORDER[t], default=None)


def tl_score(pct: Optional[float]) -> Optional[str]:
    if pct is None:
        return None
    return "green" if pct >= 80 else "yellow" if pct >= 50 else "red"


def tl_spec(critical: int, warning: int) -> str:
    return "red" if critical > 0 else "yellow" if warning > 0 else "green"


# ── 마스터/레지스트리 ────────────────────────────────────────────────────
def _master() -> List[Dict[str, Any]]:
    import static_qa
    return static_qa.load_sites()


def _registry_region() -> Dict[str, str]:
    """sitecode → 총괄(EHQ/MENA/…) — site_registry.part*.json 에서."""
    out: Dict[str, str] = {}
    for p in sorted(glob.glob(os.path.join(_HERE, "dotcom_qa", "site_registry*.json"))):
        try:
            for s in json.load(open(p, encoding="utf-8")).get("sites", []):
                if s.get("sitecode") and s.get("region") and s["sitecode"] not in out:
                    out[s["sitecode"]] = s["region"]
        except Exception:
            continue
    # 레지스트리에 없는 사이트(큐비 검수 대상이 아닌 곳)는 지역상 명백한 총괄로 보정 — 추정이 아니라 삼성 조직 구분(MENA/SWA)
    for sc, reg in (("bd", "SWA"), ("pk", "SWA"), ("iran", "MENA"), ("levant", "MENA"), ("levant_ar", "MENA"),
                    ("iq_ar", "MENA"), ("iq_ku", "MENA"), ("lb", "MENA"), ("eg", "MENA"), ("n_africa", "MENA")):
        out.setdefault(sc, reg)
    return out


# ── 큐비(Data/Spec) ────────────────────────────────────────────────────
def _spec_summary(r: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """프론트 QubiSpecQa._specSummaryOf 와 같은 규칙."""
    if r.get("page_type") == "Compare" and (r.get("compare_v2") or {}).get("summary", {}).get("checked"):
        acc = {"critical": 0, "warning": 0, "pass": 0}
        for p in r["compare_v2"]["summary"].get("per_product") or []:
            acc["critical"] += p.get("fail") or 0; acc["warning"] += p.get("warn") or 0; acc["pass"] += p.get("pass") or 0
        return acc
    s = (r.get("spec_v2") or {}).get("summary")
    if not s:
        return None
    return {"critical": s.get("critical") or 0, "warning": s.get("warning") or 0, "pass": s.get("pass") or 0}


def _qubi_latest(session_local) -> Dict[str, Dict[str, Any]]:
    """sitecode → {data:{score, at, run_id}, spec:{critical, warning, at, run_id}} — 각각 최신 run 값."""
    import models
    out: Dict[str, Dict[str, Any]] = {}
    db = session_local()
    try:
        rows = db.query(models.QbHistory).order_by(models.QbHistory.id.desc()).limit(150).all()
    finally:
        db.close()
    for row in rows:
        try:
            results = json.loads(row.results)
        except Exception:
            continue
        for r in results:
            sc = (r.get("sitecode") or "").lower()
            if not sc:
                continue
            slot = out.setdefault(sc, {})
            hq = r.get("html_qa")
            if hq and "data" not in slot:
                fp = (hq.get("overall") or {}).get("final_pct")
                if fp is not None:
                    slot["data"] = {"score": round(fp), "at": row.at, "run_id": row.run_id,
                                    "gate_zero": bool((hq.get("overall") or {}).get("any_gate_zero"))}
            if "spec" not in slot:
                ss = _spec_summary(r)
                if ss:
                    slot["spec"] = {**ss, "at": row.at, "run_id": row.run_id}
    return out


# ── 공통페이지 QA ─────────────────────────────────────────────────────
def _static_latest() -> Dict[str, Dict[str, Any]]:
    try:
        import qb_routes_static, static_qa
    except Exception:
        return {}
    runs = qb_routes_static._list()
    if not runs:
        return {}
    run = qb_routes_static._load(runs[0]["run_id"]) or {}
    out: Dict[str, Dict[str, Any]] = {}
    for r in run.get("results", []):
        sc = (r.get("sitecode") or "").lower()
        slot = out.setdefault(sc, {"pass": 0, "warn": 0, "fail": 0, "na": 0, "at": run.get("at"), "run_id": run.get("run_id"), "pages": []})
        sev = r.get("sev") or static_qa.sev_of(r.get("status"))
        slot[sev] += 1
        slot["pages"].append({"page": r.get("page_label") or r.get("page"), "status": r.get("status"), "sev": sev})
    for sc, s in out.items():
        scored = s["pass"] + s["warn"] + s["fail"]
        s["score"] = round(100 * s["pass"] / scored) if scored else None
    return out


# ── honeyComb ────────────────────────────────────────────────────────
_HC_TL = {"absent": "red", "low": "yellow", "topn": "green", "top1": "green"}


def _hc_latest() -> Dict[str, Dict[str, Any]]:
    try:
        import hc_routes
        cfg_countries = hc_routes._mock.config().get("countries", [])
    except Exception:
        return {}
    runs = hc_routes._all_runs()
    if not runs:
        return {}
    run = runs[-1]
    code2sc = {c["code"]: (c.get("sitecode") or "").lower() for c in cfg_countries}
    out: Dict[str, Dict[str, Any]] = {}
    for cell in run.get("cells", []):
        sc = code2sc.get(cell.get("country"), (cell.get("country") or "").lower())
        slot = out.setdefault(sc, {"top1": 0, "topn": 0, "low": 0, "absent": 0, "other": 0, "at": run.get("at"), "run_id": run.get("run_id"), "week": run.get("week")})
        st = cell.get("status")
        slot[st if st in slot else "other"] += 1
    for s in out.values():
        s["tl"] = worst(*[_HC_TL[k] for k in ("absent", "low", "topn", "top1") if s[k] > 0]) or None
    return out


# ── 조립 ────────────────────────────────────────────────────────────
_cache: Dict[str, Any] = {"at": 0.0, "data": None}


def build(session_local, ttl: float = 20.0) -> Dict[str, Any]:
    now = time.time()
    if _cache["data"] is not None and now - _cache["at"] < ttl:
        return _cache["data"]

    master = _master()
    reg_region = _registry_region()
    qubi = _qubi_latest(session_local)
    static = _static_latest()
    hc = _hc_latest()

    sites: List[Dict[str, Any]] = []
    for m in master:
        sc = (m.get("sitecode") or "").lower()
        q = qubi.get(sc, {})
        d, s, st, h = q.get("data"), q.get("spec"), static.get(sc), hc.get(sc)
        tools = {
            "data": {"tl": ("red" if d and d.get("gate_zero") else tl_score(d["score"])) if d else None, **(d or {})},
            "spec": {"tl": tl_spec(s["critical"], s["warning"]) if s else None, **(s or {})},
            "static": {"tl": tl_score(st["score"]) if st else None, **(st or {})},
            "hc": {"tl": h.get("tl") if h else None, **(h or {})},
        }
        ats = [v.get("at") for v in tools.values() if v.get("at")]
        sites.append({"sitecode": sc, "country": m.get("country"), "subs": m.get("subs") or "-", "region": reg_region.get(sc, "(미분류)"),
                      "mode": m.get("mode"), "tools": tools,
                      "overall": worst(*(v["tl"] for v in tools.values())), "latest_at": max(ats) if ats else None})

    # 법인(subs) 묶음
    subs: Dict[str, Dict[str, Any]] = {}
    for s in sites:
        g = subs.setdefault(s["subs"], {"subs": s["subs"], "region": s["region"], "sitecodes": [], "countries": [],
                                       "tools": {"data": None, "spec": None, "static": None, "hc": None}, "overall": None, "latest_at": None})
        g["sitecodes"].append(s["sitecode"])
        if s["country"] not in g["countries"]:
            g["countries"].append(s["country"])
        for k in g["tools"]:
            g["tools"][k] = worst(g["tools"][k], s["tools"][k]["tl"])
        g["overall"] = worst(g["overall"], s["overall"])
        if s["latest_at"] and (not g["latest_at"] or s["latest_at"] > g["latest_at"]):
            g["latest_at"] = s["latest_at"]

    # 총괄(region) 묶음
    regions: Dict[str, Dict[str, Any]] = {}
    for g in subs.values():
        r = regions.setdefault(g["region"], {"region": g["region"], "subs": [], "overall": None, "tools": {"data": None, "spec": None, "static": None, "hc": None}})
        r["subs"].append(g["subs"])
        r["overall"] = worst(r["overall"], g["overall"])
        for k in r["tools"]:
            r["tools"][k] = worst(r["tools"][k], g["tools"][k])

    dist = {"red": 0, "yellow": 0, "green": 0, "none": 0}
    for g in subs.values():
        dist[g["overall"] or "none"] += 1

    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sites": sites,
        "subs": sorted(subs.values(), key=lambda g: (-ORDER[g["overall"]], g["subs"])),
        "regions": sorted(regions.values(), key=lambda r: (-ORDER[r["overall"]], r["region"])),
        "distribution": dist,
        "sources": {
            "static_run": next(iter(static.values()), {}).get("run_id") if static else None,
            "hc_run": next(iter(hc.values()), {}).get("run_id") if hc else None,
            "qubi_rows": len(qubi),
        },
    }
    _cache.update(at=now, data=data)
    return data
