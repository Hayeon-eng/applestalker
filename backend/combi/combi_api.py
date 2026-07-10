"""
combi_api.py — Combi(🍯) API 라우터 스켈레톤

엔드포인트:
  GET  /api/combi/prompts        — 승인된 Prompt Library 조회
  POST /api/combi/runs           — Prompt×Country 실행 (지금은 rule_engine STUB 결과 저장)
  GET  /api/combi/runs           — 최근 실행 이력
  GET  /api/combi/runs/{run_id}  — 실행 1건 상세(Shelf/Coverage/Gap)
  GET  /api/combi/kpi            — Landing 카드용 요약 KPI

[SKELETON] 실제 크롤러(Google Search → Shopping Shelf 파싱)는 아직 없음.
rule_engine.py가 결정적 mock을 반환하고, 이 라우터는 그 결과를 실제 저장/조회 파이프라인에
그대로 흘려보낸다 — 나중에 rule_engine 내부만 실데이터로 교체하면 API/DB/Frontend는 안 바뀜.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import SessionLocal
from models import CombiRun
from combi.prompt_library import load_prompts, get_prompt
from combi.rule_engine import compute_shelf, compute_coverage, find_gaps

combi_router = APIRouter(prefix="/api/combi", tags=["combi"])


class RunRequest(BaseModel):
    prompt_ids: List[str]
    countries: List[str] = ["US"]


@combi_router.get("/health")
def combi_health():
    return {"ok": True, "service": "combi", "status": "skeleton"}


@combi_router.get("/prompts")
def list_prompts():
    return {"prompts": load_prompts(active_only=True)}


@combi_router.post("/runs")
def create_runs(req: RunRequest):
    if not req.prompt_ids:
        raise HTTPException(400, "prompt_ids가 비어있음")

    created = []
    db = SessionLocal()
    try:
        for pid in req.prompt_ids:
            prompt = get_prompt(pid)
            if not prompt:
                continue
            for country in req.countries:
                shelf = compute_shelf(prompt["text"], country)
                coverage = compute_coverage(prompt["text"], country, "Samsung.com")
                gaps = find_gaps(prompt["text"], country)

                samsung_rows = [r for r in shelf if r["is_samsung"]]
                samsung_rank = samsung_rows[0]["rank"] if samsung_rows else None
                samsung_above_fold = bool(samsung_rows and samsung_rows[0]["above_fold"])

                row = CombiRun(
                    combi_run_id=f"combi_{uuid.uuid4().hex[:12]}",
                    prompt_id=prompt["id"],
                    prompt_text=prompt["text"],
                    category=prompt["category"],
                    country=country,
                    shelf_json=json.dumps(shelf, ensure_ascii=False),
                    coverage_json=json.dumps(coverage, ensure_ascii=False),
                    gaps_json=json.dumps(gaps, ensure_ascii=False),
                    samsung_rank=samsung_rank,
                    samsung_above_fold=samsung_above_fold,
                    gap_count=len(gaps),
                )
                db.add(row)
                db.flush()
                created.append(row.combi_run_id)
        db.commit()
    finally:
        db.close()

    return {"created": created, "count": len(created)}


@combi_router.get("/runs")
def list_runs(limit: int = 50):
    db = SessionLocal()
    try:
        rows = (
            db.query(CombiRun)
            .order_by(CombiRun.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "runs": [
                {
                    "combi_run_id": r.combi_run_id,
                    "prompt_id": r.prompt_id,
                    "prompt_text": r.prompt_text,
                    "category": r.category,
                    "country": r.country,
                    "samsung_rank": r.samsung_rank,
                    "samsung_above_fold": r.samsung_above_fold,
                    "gap_count": r.gap_count,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        }
    finally:
        db.close()


@combi_router.get("/runs/{combi_run_id}")
def get_run(combi_run_id: str):
    db = SessionLocal()
    try:
        r: Optional[CombiRun] = (
            db.query(CombiRun).filter(CombiRun.combi_run_id == combi_run_id).first()
        )
        if not r:
            raise HTTPException(404, "run을 찾을 수 없음")
        return {
            "combi_run_id": r.combi_run_id,
            "prompt_id": r.prompt_id,
            "prompt_text": r.prompt_text,
            "category": r.category,
            "country": r.country,
            "shelf": json.loads(r.shelf_json or "[]"),
            "coverage": json.loads(r.coverage_json or "{}"),
            "gaps": json.loads(r.gaps_json or "[]"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
    finally:
        db.close()


@combi_router.get("/kpi")
def kpi():
    """Landing 카드에 뿌릴 요약 지표."""
    db = SessionLocal()
    try:
        total = db.query(CombiRun).count()
        latest = db.query(CombiRun).order_by(CombiRun.created_at.desc()).first()
        above_fold_count = db.query(CombiRun).filter(CombiRun.samsung_above_fold == True).count()  # noqa: E712
        return {
            "total_runs": total,
            "above_fold_runs": above_fold_count,
            "latest_run_at": latest.created_at.isoformat() if latest and latest.created_at else None,
        }
    finally:
        db.close()
