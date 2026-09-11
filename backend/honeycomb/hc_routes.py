"""
hc_routes.py — honeyComb API [2026-09 · 목업]  prefix /api/hc

  GET  /api/hc/config            국가·제품·키워드·top_n·상태 범례
  GET  /api/hc/attributes        51(+8 sub) 속성 표준 + 관측 위치(card/detail/feed)
  GET  /api/hc/runs              run 목록(요약)
  GET  /api/hc/runs/{run_id}     run 상세(cells 전체 + gap)
  GET  /api/hc/diff?prev=&cur=   전주 대비 변화 셀
  POST /api/hc/run               수집 실행 — 목업 단계에서는 501(provider 미확정)
  GET  /api/hc/report.xlsx?run_id= Final Report 형식 엑셀(Summary/Shopping Check/Appendix)
  GET  /api/hc/keywords          키워드 목록(제품×유형×국가제한×활성) — hc_keywords.json
  POST /api/hc/keywords          키워드 추가/수정 {id?, product, text, type: brand|longtail, countries: [], enabled, note}
  POST /api/hc/keywords/remove   {id}

큐비 qb_api 와 같은 방식으로 main.py 에서 include_router(hc_router).
"""
from __future__ import annotations
import io
import os
import sys
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

import json
import hc_engine
from hc_provider import get_provider, MockProvider

_KW_PATH = os.path.join(os.path.dirname(__file__), "hc_keywords.json")


def _load_keywords() -> Dict[str, Any]:
    try:
        return json.load(open(_KW_PATH, encoding="utf-8"))
    except Exception:
        return {"keywords": []}


def _save_keywords(d: Dict[str, Any]):
    json.dump(d, open(_KW_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

hc_router = APIRouter(prefix="/api/hc", tags=["honeycomb"])
_provider = get_provider()


def _mock() -> MockProvider:
    if not isinstance(_provider, MockProvider):
        raise HTTPException(501, "실수집 provider 는 미구현(목업 단계). HC_PROVIDER=mock 으로 실행하세요.")
    return _provider


@hc_router.get("/config")
def hc_config():
    m = _mock()
    cfg = dict(m.config()); cfg.pop("keywords", None)  # 키워드는 hc_keywords.json(/api/hc/keywords)이 원본
    return {**cfg, "provider": _provider.name, "attribute_count": len(m.attributes()),
            "primary_attribute_count": sum(1 for a in m.attributes() if not a.get("sub"))}


@hc_router.get("/keywords")
def hc_keywords():
    return _load_keywords()


@hc_router.post("/keywords")
def hc_keyword_upsert(payload: Dict[str, Any]):
    text = (payload.get("text") or "").strip()
    product = (payload.get("product") or "").strip()
    ktype = (payload.get("type") or "longtail").strip()
    if not text or not product or ktype not in ("brand", "longtail"):
        raise HTTPException(400, "product, text, type(brand|longtail) 필요")
    d = _load_keywords()
    kid = payload.get("id") or f"{product}:{ktype}:{text}"
    sub = (payload.get("subtype") or "").strip().upper()
    if sub and sub not in ("A1", "A2", "A3", "B1", "B2", "B3", "B4"):
        raise HTTPException(400, "subtype 은 A1~A3(brand) / B1~B4(longtail)")
    if sub:  # subtype 이 type 을 결정한다(A=brand, B=longtail) — 분류 기준 일관성
        ktype = "brand" if sub.startswith("A") else "longtail"
    item = {"id": kid, "product": product, "text": text, "type": ktype, "subtype": sub or ("A1" if ktype == "brand" else "B1"),
            "countries": [c.strip().upper() for c in (payload.get("countries") or []) if c.strip()],
            "enabled": bool(payload.get("enabled", True)), "note": (payload.get("note") or "").strip()}
    d["keywords"] = [k for k in d["keywords"] if k["id"] != kid] + [item]
    _save_keywords(d)
    return {"ok": True, "keyword": item, "count": len(d["keywords"])}


@hc_router.post("/keywords/remove")
def hc_keyword_remove(payload: Dict[str, Any]):
    d = _load_keywords()
    before = len(d["keywords"])
    d["keywords"] = [k for k in d["keywords"] if k["id"] != payload.get("id")]
    _save_keywords(d)
    return {"ok": True, "removed": before - len(d["keywords"]), "count": len(d["keywords"])}


@hc_router.get("/attributes")
def hc_attributes():
    return {"attributes": _mock().attributes()}


@hc_router.get("/runs")
def hc_runs():
    m = _mock()
    return {"runs": [hc_engine.summarize(r) for r in m.runs()]}


@hc_router.get("/runs/{run_id}")
def hc_run(run_id: str, keyword_type: Optional[str] = Query(None)):
    m = _mock()
    run = next((r for r in m.runs() if r["run_id"] == run_id), None)
    if not run:
        raise HTTPException(404, f"run {run_id} 없음")
    cells = [dict(c, gaps=hc_engine.gaps(c)) for c in run["cells"]
             if not keyword_type or c["keyword_type"] == keyword_type]
    return {"run_id": run_id, "week": run["week"], "at": run["at"], "source": run.get("source"),
            "summary": hc_engine.summarize(run, keyword_type), "cells": cells}


@hc_router.get("/diff")
def hc_diff(prev: str, cur: str):
    m = _mock()
    runs = {r["run_id"]: r for r in m.runs()}
    if prev not in runs or cur not in runs:
        raise HTTPException(404, "run_id 확인")
    return {"prev": prev, "cur": cur, "changes": hc_engine.diff_runs(runs[prev], runs[cur])}


@hc_router.post("/run")
def hc_run_start(payload: Dict[str, Any] = None):
    raise HTTPException(501, "수집 방식(SERP API / Playwright / Merchant API) 미확정 — 목업 단계에서는 실행 불가")


@hc_router.get("/report.xlsx")
def hc_report(run_id: str):
    m = _mock()
    run = next((r for r in m.runs() if r["run_id"] == run_id), None)
    if not run:
        raise HTTPException(404, f"run {run_id} 없음")
    import hc_report
    buf = hc_report.build_xlsx(run, m.attributes(), m.config())
    return StreamingResponse(io.BytesIO(buf),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename=honeycomb_{run_id}.xlsx"})
