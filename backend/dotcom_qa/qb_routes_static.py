"""
qb_routes_static.py — 공통페이지 QA API [2026-09 신규]  prefix /api/qb/static

  GET  /pages            페이지 정의(7종) + 사이트 수
  POST /run              전체(90 자동 사이트 × 7 페이지) 수집·판정 시작(백그라운드) — body {pages?: [...], sitecodes?: [...]}
  GET  /status           진행 상태
  GET  /runs             저장된 실행 목록(최근 30)
  GET  /latest           최신 실행 결과
  GET  /runs/{run_id}    특정 실행 결과
  GET  /report.xlsx      엑셀(사이트 × 페이지 매트릭스 + 상세)
저장: QB_STATIC_DIR(기본 dotcom_qa/static_runs/) 에 run 별 JSON — 데스크톱은 %APPDATA%\\ABCTool\\static_runs
"""
from __future__ import annotations
import asyncio
import io
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))
from fastapi import Body, HTTPException
from fastapi.responses import StreamingResponse

import static_qa
import static_guide
from qb_core import qb_router

STORE = os.getenv("QB_STATIC_DIR") or os.path.join(os.path.dirname(__file__), "static_runs")
os.makedirs(STORE, exist_ok=True)


def _save(run: Dict[str, Any]):
    json.dump(run, open(os.path.join(STORE, run["run_id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    files = sorted(f for f in os.listdir(STORE) if f.endswith(".json"))
    for f in files[:-30]:
        os.remove(os.path.join(STORE, f))


def _list() -> List[Dict[str, Any]]:
    out = []
    for f in sorted((f for f in os.listdir(STORE) if f.endswith(".json")), reverse=True):
        try:
            d = json.load(open(os.path.join(STORE, f), encoding="utf-8"))
            out.append({"run_id": d["run_id"], "at": d["at"], "summary": d["summary"], "duration_seconds": d.get("duration_seconds")})
        except Exception:
            continue
    return out


def _load(run_id: str) -> Optional[Dict[str, Any]]:
    p = os.path.join(STORE, run_id + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


@qb_router.get("/static/pages")
def static_pages():
    sites = static_qa.load_sites()
    return {"pages": static_qa.STATIC_PAGES, "sites": len(sites), "auto": sum(1 for s in sites if s["mode"] == "auto"),
            "manual": [s["sitecode"] for s in sites if s["mode"] != "auto"], "status_order": static_qa.STATUS_ORDER}


async def _bg(pages, sitecodes):
    try:
        sites = [s for s in static_qa.load_sites() if s["mode"] == "auto" and (not sitecodes or s["sitecode"] in sitecodes)]
        run = await static_qa.run_all(sites, pages)
        _save(run)
    except Exception as e:
        static_qa.STATE.update(running=False, error=str(e))


@qb_router.post("/static/run")
async def static_run(payload: Dict[str, Any] = Body(default={})):
    if static_qa.STATE.get("running"):
        raise HTTPException(409, "이미 실행 중")
    asyncio.create_task(_bg(payload.get("pages"), [s.lower() for s in (payload.get("sitecodes") or [])]))
    return {"status": "started"}


@qb_router.get("/static/status")
def static_status():
    return static_qa.STATE


@qb_router.post("/static/cancel")
def static_cancel():
    """멈춤 — 진행 중 검수 중단(끝난 페이지는 저장, 나머지는 건너뜀)."""
    if not static_qa.STATE.get("running"):
        return {"ok": True, "running": False}
    static_qa.STATE["cancel"] = True
    return {"ok": True, "cancelling": True}


@qb_router.get("/static/runs")
def static_runs():
    return {"runs": _list()}


@qb_router.get("/static/latest")
def static_latest():
    runs = _list()
    if not runs:
        return {"run": None}
    return {"run": _load(runs[0]["run_id"])}


@qb_router.get("/static/runs/{run_id}")
def static_run_get(run_id: str):
    d = _load(run_id)
    if not d:
        raise HTTPException(404, "없음")
    for r in d.get("results", []):
        r["guide"] = static_guide.cell_guide(r)
    d["insight"] = static_guide.summarize(d.get("results", []), static_qa.load_sites())
    return d


@qb_router.get("/static/summary/{run_id}")
def static_summary(run_id: str):
    """페이지별·권역별 정상/오류 비율 + 대표 오류 사례의 as-is/to-be (보고용 요약)."""
    d = _load(run_id)
    if not d:
        raise HTTPException(404, "없음")
    insight = static_guide.summarize(d.get("results", []), static_qa.load_sites())
    # 상태별 대표 사례 1건씩(가이드 포함)
    examples = {}
    for r in d.get("results", []):
        if r["status"] not in examples and r["status"] != "정상":
            examples[r["status"]] = {"sitecode": r["sitecode"], "country": r.get("country"), "page": r.get("page_label"),
                                     "url": r["url"], "guide": static_guide.cell_guide(r)}
    return {"run_id": run_id, "at": d.get("at"), "insight": insight, "examples": examples}


@qb_router.get("/static/report.xlsx")
def static_report(run_id: Optional[str] = None):
    d = _load(run_id) if run_id else (_load(_list()[0]["run_id"]) if _list() else None)
    if not d:
        raise HTTPException(404, "실행 결과 없음")
    from openpyxl import Workbook
    wb = Workbook(); wb.remove(wb.active)
    static_guide.build_report_sheets(wb, d)
    buf = io.BytesIO(); wb.save(buf)
    return StreamingResponse(io.BytesIO(buf.getvalue()), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename=qubi_static_{d['run_id']}.xlsx"})
