"""
qb_routes_history.py — 검수 이력·리포트 (/history, /overview, /report.xlsx, /email-draft) [qb_api 분할]
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

import runner
import qa_report
import schema_checker
import html_qa_scoring
from database import SessionLocal
from models import QbHistory

import qb_core
from qb_core import qb_router, _registry
from qb_routes_static import _list as _static_runs, _load as _static_run

# ── 검수 이력 (DB 저장) ──
# [FIX] 기존엔 dotcom_qa/qb_history/*.json 로컬 파일에 저장했으나, Render 무료 플랜은
# idle 슬립 후 재시작(또는 재배포) 시 로컬 디스크가 초기화되어 사이트를 나갔다 오면
# 이력이 전부 유실됐음. 이미 붙어있는 Postgres DB(QbHistory 테이블)에 저장하도록 변경.

def _history_index() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(QbHistory).order_by(QbHistory.id.desc()).limit(100).all()
        return [{"run_id": r.run_id, "at": r.at, "product": r.product, "scope": r.scope,
                  "pages": r.pages, "fail": r.fail, "warn": r.warn,
                  "duration_seconds": r.duration_seconds} for r in rows]
    finally:
        db.close()


def _history_save(results, summary, product="M3", scope="", duration_seconds: Optional[float] = None) -> Dict[str, Any]:
    now = datetime.now()
    run_id = now.strftime("%Y%m%d-%H%M%S")
    entry = {"run_id": run_id, "at": now.strftime("%Y-%m-%d %H:%M:%S"),
             "product": product, "scope": scope, "pages": summary.get("pages", len(results)),
             "fail": summary.get("fail", 0), "warn": summary.get("warn", 0),
             "duration_seconds": duration_seconds}
    db = SessionLocal()
    try:
        db.add(QbHistory(run_id=run_id, at=entry["at"], product=product, scope=scope,
                          pages=entry["pages"], fail=entry["fail"], warn=entry["warn"],
                          duration_seconds=duration_seconds,
                          results=json.dumps(results, ensure_ascii=False, separators=(",", ":"))))
        db.commit()
        # 최근 100건만 유지 — 초과분 삭제
        old_ids = [r.id for r in db.query(QbHistory.id).order_by(QbHistory.id.desc()).offset(100).all()]
        if old_ids:
            db.query(QbHistory).filter(QbHistory.id.in_(old_ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()
    return entry


# ── [2026-09] 이력 내보내기/가져오기 — 사내망에서 공용 DB 포트가 막혀 이력 공유가 안 되므로,
#    각자 PC(sqlite)에 저장한 이력을 JSON 파일로 내보내고 상대가 가져와 같은 화면으로 볼 수 있게 한다.
@qb_router.get("/history/export")
def qb_history_export(run_id: Optional[str] = Query(None)):
    from fastapi.responses import JSONResponse
    db = SessionLocal()
    try:
        qs = db.query(QbHistory).order_by(QbHistory.id.desc())
        rows = [qs.filter(QbHistory.run_id == run_id).first()] if run_id else qs.limit(50).all()
        rows = [r for r in rows if r]
        payload = {"tool": "qubi", "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   "entries": [{"run_id": r.run_id, "at": r.at, "product": r.product, "scope": r.scope, "pages": r.pages,
                                "fail": r.fail, "warn": r.warn, "duration_seconds": r.duration_seconds,
                                "results": json.loads(r.results or "[]")} for r in rows]}
    finally:
        db.close()
    name = f"qubi_history_{run_id or 'all'}_{datetime.now():%Y%m%d}.json"
    return JSONResponse(payload, headers={"Content-Disposition": f"attachment; filename={name}"})


@qb_router.post("/history/import")
def qb_history_import(payload: Dict[str, Any] = Body(...)):
    """내보낸 JSON 을 그대로 올리면 run_id 기준으로 없는 것만 추가한다(덮어쓰지 않음)."""
    entries = payload.get("entries") or []
    if payload.get("tool") not in (None, "qubi") or not isinstance(entries, list):
        raise HTTPException(400, "큐비 이력 JSON 이 아닙니다")
    db = SessionLocal(); added = skipped = 0
    try:
        for e in entries:
            rid = str(e.get("run_id") or "")
            if not rid or db.query(QbHistory).filter(QbHistory.run_id == rid).first():
                skipped += 1; continue
            db.add(QbHistory(run_id=rid, at=e.get("at"), product=e.get("product"), scope=(e.get("scope") or "") + " · 가져옴",
                             pages=e.get("pages", 0), fail=e.get("fail", 0), warn=e.get("warn", 0),
                             duration_seconds=e.get("duration_seconds"),
                             results=json.dumps(e.get("results") or [], ensure_ascii=False, separators=(",", ":"))))
            added += 1
        db.commit()
    finally:
        db.close()
    return {"ok": True, "added": added, "skipped": skipped}


@qb_router.get("/history")
def qb_history():
    return {"history": _history_index()}


@qb_router.get("/overview")
def qb_overview():
    """전사이트 현황(A안) — 이력을 최신순으로 훑어 '각 권역의 가장 최근 검수'를 하나씩 뽑고,
    그 권역들의 AEO 퀄리티 점수를 평균낸 전사이트 점수판을 만든다.
    권역별로 나눠 검수하더라도 각 권역의 최신값을 모아 전체 현황을 보여준다."""
    db = SessionLocal()
    try:
        rows = db.query(QbHistory).order_by(QbHistory.id.desc()).limit(100).all()
    finally:
        db.close()

    # region -> {최신 검수에서 집계한 값}. 이력은 최신순이라, 어떤 region을 이미 봤으면 그게 최신.
    region_latest: Dict[str, Dict[str, Any]] = {}
    seen_regions: set = set()
    for r in rows:
        try:
            results = json.loads(r.results)
        except Exception:
            continue
        # 이 run에 포함된 region별로, 아직 확정 안 된 region만 이 run 값으로 채운다.
        by_region_here: Dict[str, List[float]] = {}
        applyacc_here: Dict[str, List[int]] = {}  # region -> [prop_ok합, prop_total합]
        run_at = r.at
        for row in results:
            region = row.get("region") or "기타"
            hq = row.get("html_qa")
            if not hq:
                continue
            fp = (hq.get("overall") or {}).get("final_pct")
            if fp is None:
                continue
            by_region_here.setdefault(region, []).append(fp)
            ov = hq.get("overall") or {}
            acc = applyacc_here.setdefault(region, [0, 0])
            acc[0] += ov.get("prop_ok") or 0
            acc[1] += ov.get("prop_total") or 0
        for region, scores in by_region_here.items():
            if region in seen_regions:
                continue  # 더 최신 run에서 이미 확정됨
            seen_regions.add(region)
            avg = round(sum(scores) / len(scores), 1) if scores else None
            acc = applyacc_here.get(region, [0, 0])
            apply_pct = round(100 * acc[0] / acc[1], 1) if acc[1] else None
            region_latest[region] = {"region": region, "avg_aeo": avg, "apply_pct": apply_pct,
                                     "prop_ok": acc[0], "prop_total": acc[1],
                                     "sites": len(scores), "at": run_at}

    regions = sorted(region_latest.values(), key=lambda x: (x["avg_aeo"] if x["avg_aeo"] is not None else -1))
    vals = [x["avg_aeo"] for x in regions if x["avg_aeo"] is not None]
    total_avg = round(sum(vals) / len(vals), 1) if vals else None
    tot_ok = sum(x.get("prop_ok") or 0 for x in regions)
    tot_all = sum(x.get("prop_total") or 0 for x in regions)
    total_apply = round(100 * tot_ok / tot_all, 1) if tot_all else None
    dist = {"green": 0, "yellow": 0, "red": 0}
    for x in regions:
        a = x["avg_aeo"]
        if a is None:
            dist["red"] += 1
        elif a >= 80:
            dist["green"] += 1
        elif a >= 50:
            dist["yellow"] += 1
        else:
            dist["red"] += 1
    return {"total_avg_aeo": total_avg, "total_apply_pct": total_apply, "region_count": len(regions),
            "regions": regions, "distribution": dist}


@qb_router.get("/history/{run_id}")
def qb_history_one(run_id: str):
    db = SessionLocal()
    try:
        row = db.query(QbHistory).filter(QbHistory.run_id == run_id).first()
        if not row:
            raise HTTPException(404, "해당 이력이 없습니다.")
        results = json.loads(row.results)
        return {"run_id": run_id, "results": results, "summary": qa_report.summary_counts(results)}
    finally:
        db.close()


@qb_router.post("/history/remove")
def qb_history_remove(payload: Dict[str, Any] = Body(...)):
    run_id = payload.get("run_id", "")
    db = SessionLocal()
    try:
        db.query(QbHistory).filter(QbHistory.run_id == run_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    return {"ok": True, "history": _history_index()}



def _latest_static_run() -> Optional[Dict[str, Any]]:
    """공통페이지 QA 최신 실행 결과 — 있으면 통합 리포트에 시트로 추가한다.
    공통페이지 QA는 Data/Spec QA 와 별도 주기로 돌기 때문에 run_id 매칭 없이 항상 최신 것을 붙인다."""
    try:
        runs = _static_runs()
        return _static_run(runs[0]["run_id"]) if runs else None
    except Exception:
        return None


@qb_router.get("/report.xlsx")
def qb_report_xlsx_get(run_id: str = Query(None)):
    try:
        data = qa_report.build_xlsx(qb_core._resolve_results(run_id=run_id), static_run=_latest_static_run())
    except Exception as e:
        # [2026-07 FIX] 원인 불명 500 리포트 대응 — 어떤 페이지의 어떤 값 때문에 실패했는지
        # 서버 로그에 전체 traceback을 남기고, 사용자에게는 원인 파악 가능한 메시지를 준다.
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Excel 리포트 생성 실패: {type(e).__name__}: {e}")
    return StreamingResponse(iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=qubi_qa_report.xlsx"})


@qb_router.post("/report.xlsx")
def qb_report_xlsx(payload: Dict[str, Any] = Body(default={})):
    try:
        data = qa_report.build_xlsx(qb_core._resolve_results(payload), static_run=_latest_static_run())
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Excel 리포트 생성 실패: {type(e).__name__}: {e}")
    return StreamingResponse(iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=qubi_qa_report.xlsx"})


@qb_router.get("/email-draft")
def qb_email_draft_get(run_id: str = Query(None), tab: str = Query(None), sections: Optional[List[str]] = Query(None)):
    # [2026-09 FIX] sections(다중 선택) 우선, 없으면 예전 단일 tab 파라미터로 하위호환
    secs = sections or ([tab] if tab else None)
    static_run = _latest_static_run() if (secs and "static" in secs) else None
    return HTMLResponse(content=qa_report.build_email_draft(qb_core._resolve_results(run_id=run_id), sections=secs, static_run=static_run))


@qb_router.post("/email-draft")
def qb_email_draft(payload: Dict[str, Any] = Body(default={})):
    secs = payload.get("sections") or ([payload.get("tab")] if payload.get("tab") else None)
    static_run = _latest_static_run() if (secs and "static" in secs) else None
    return HTMLResponse(content=qa_report.build_email_draft(qb_core._resolve_results(payload), sections=secs, static_run=static_run))


