"""
main.py — FastAPI 백엔드 (단일 파일에 엔드포인트 통합, 단순화)
프론트(Next.js)는 별도 서비스. 이 백엔드는 /api/* 만 제공.
"""
import os, json, asyncio
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from loguru import logger

load_dotenv()

from database import engine, SessionLocal, init_db, sync_engine, prune_old_snapshots
from crawl_service import CrawlServiceV2
from intel_engine import IntelEngine, aeo_facts
from email_service import EmailService
from config import SEED_TARGETS, load_active_urls, all_site_keys, site_key_for_url, tier_for_url

CRON_TOKEN = os.getenv("CRON_TOKEN", "change-me")
SITE_KEYS = ["samsung", "apple"]

# ── 카테고리/레벨 매핑 (UI 단순화: High/Med/Low, 4 카테고리) ──
CATEGORY = {  # change_type → 화면 카테고리
    "technical": "데이터·스키마", "navigation": "데이터·스키마",
    "content": "카피", "commerce": "가격·프로모션", "visual": "비주얼",
}


def display_level(change_type: str, field_name: str, severity_level: str) -> str:
    """
    화면 표시 등급(높음/보통/낮음) — 마케팅·AEO 기준.
    핵심: '무엇이(어디가)' + '얼마나(폭, L0~L5)' 를 함께 본다.
      - 구조(스키마/레이아웃) = 높음  (AI 검색 노출에 직접 영향)
      - 메뉴/메타 등 부분 구조, 문장·슬로건, 거래(가격·구매) = 보통
      - 단어·미세·작은 이미지 = 낮음
    """
    lv = severity_level or "L0"
    f = field_name or ""
    # 거래(가격·구매·프로모션)는 마케팅 관점상 '보통'
    if change_type == "commerce":
        return "Medium"
    # 구조: 스키마 추가/삭제, 레이아웃(DOM) 재편 = 높음
    if f in ("schema_type", "dom"):
        return "High"
    # 부분 구조(메뉴/정규URL/메타)는 보통
    if f in ("navigation", "canonical_url", "meta_description"):
        return "Medium"
    if change_type == "technical":
        return "High" if lv in ("L4", "L5") else "Medium"
    # 카피: 여러 섹션 동시 변화(L3+)=높음, 문장/문구=보통, 단어/미세=낮음
    if change_type == "content":
        if f == "body_content" and lv in ("L3", "L4", "L5"):
            return "High"
        return "Medium" if lv in ("L2", "L3", "L4", "L5") else "Low"
    # 비주얼: 큰 변화=보통, 작은 변화=낮음
    if change_type == "visual":
        return "Medium" if lv in ("L3", "L4", "L5") else "Low"
    return {"L5": "High", "L4": "High", "L3": "Medium",
            "L2": "Medium", "L1": "Low", "L0": "Low"}.get(lv, "Low")

crawl_state = {"crawling": False, "events": [], "run_id": None}
crawl_service = CrawlServiceV2(SessionLocal, sync_engine, crawl_state)
email_service = EmailService(sync_engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("backend up")
    yield


app = FastAPI(title="Apple Stalker API", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"], expose_headers=["*"])


from fastapi.responses import JSONResponse
from fastapi.requests import Request


@app.exception_handler(Exception)
async def all_errors(request: Request, exc: Exception):
    """어떤 에러가 나도 CORS 헤더를 붙여 JSON으로 반환.
    (이렇게 안 하면 500 응답에 CORS 헤더가 빠져 브라우저가 'CORS 차단'으로 표시함)"""
    logger.error(f"{request.url.path} 에러: {exc}")
    return JSONResponse(status_code=500,
        content={"error": str(exc), "path": request.url.path},
        headers={"Access-Control-Allow-Origin": "*"})


def q(sql, **p):
    with sync_engine.connect() as c:
        return c.execute(text(sql), p).fetchall()


# ── KST(한국시간) 변환 + 하루 2회 세션 구분 ──
from datetime import timedelta, datetime as _dt

def _to_kst(dt):
    if not dt:
        return None
    if isinstance(dt, str):
        try: dt = _dt.fromisoformat(dt.replace("Z", ""))
        except Exception: return dt
    return dt + timedelta(hours=9)

def _kst_str(dt):
    k = _to_kst(dt)
    return k.strftime("%Y-%m-%d %H:%M") if k else ""

def _session_key(dt):
    """하루 2회 슬롯: KST 날짜 + 오전/오후. (started_at 은 UTC 저장)"""
    k = _to_kst(dt)
    if not k:
        return "unknown"
    slot = "오전" if k.hour < 12 else "오후"
    return f"{k.strftime('%Y-%m-%d')} {slot}"


@app.get("/")
def root():
    """루트 접속 시 안내 (detail Not Found 방지)."""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(
        "<div style='font-family:-apple-system,sans-serif;max-width:520px;margin:60px auto;"
        "color:#1C1C1E;line-height:1.6'>"
        "<h2>🍎 Apple Stalker — Backend</h2>"
        "<p>백엔드는 정상 작동 중입니다. 이 주소는 API 전용이며, 화면은 프론트엔드에서 보세요.</p>"
        "<p style='color:#8E8E93;font-size:14px'>상태 확인: "
        "<a href='/api/health'>/api/health</a></p></div>")


# ── health / runs ──
@app.get("/api/health")
def health():
    return {"status": "healthy", "gemini": IntelEngine().is_available(), "ts": datetime.utcnow().isoformat()}


@app.get("/api/runs")
def runs():
    rows = q("SELECT crawl_run_id, site_name, started_at, total_urls_crawled, total_changes_detected "
             "FROM crawl_runs WHERE status='completed' ORDER BY started_at DESC LIMIT 60")
    # 하루 2회(오전/오후) 세션으로 묶고 삼성+애플 합산
    sessions = {}
    for r in rows:
        key = _session_key(r[2])
        s = sessions.setdefault(key, {"session": key, "run_ids": [], "sites": set(),
                                       "pages": 0, "changes": 0, "latest": r[2]})
        s["run_ids"].append(r[0]); s["sites"].add(r[1])
        s["pages"] += (r[3] or 0); s["changes"] += (r[4] or 0)
        if r[2] and (not s["latest"] or r[2] > s["latest"]): s["latest"] = r[2]
    out = [{"session": v["session"], "run_ids": v["run_ids"],
            "sites": sorted(v["sites"]), "pages": v["pages"], "changes": v["changes"],
            "timestamp": _kst_str(v["latest"])}
           for v in sessions.values()]
    out.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"sessions": out[:30]}


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str):
    """크롤 이력 1건 삭제 (관련 변화·스냅샷·분석도 함께). 어떤 단계가 실패해도 끝까지 진행."""
    with sync_engine.connect() as c:
        for sql in (
            "DELETE FROM detected_changes WHERE crawl_run_id=:r",
            "DELETE FROM page_snapshots WHERE crawl_run_id=:r",
            "DELETE FROM povs WHERE related_crawl_run_id=:r",
            "DELETE FROM crawl_runs WHERE crawl_run_id=:r",
        ):
            try:
                c.execute(text(sql), {"r": run_id}); c.commit()
            except Exception as e:
                c.rollback(); logger.warning(f"delete skip: {e}")
    return {"status": "deleted", "run_id": run_id}


@app.delete("/api/runs")
def clear_empty_runs():
    """변경 0건이거나 페이지 0개인 빈 크롤 기록 일괄 정리."""
    with sync_engine.connect() as c:
        rows = c.execute(text("SELECT crawl_run_id FROM crawl_runs "
                              "WHERE COALESCE(total_changes_detected,0)=0 "
                              "AND COALESCE(total_urls_crawled,0)=0")).fetchall()
        ids = [r[0] for r in rows]
        for rid in ids:
            c.execute(text("DELETE FROM crawl_runs WHERE crawl_run_id=:r"), {"r": rid})
        c.commit()
    return {"status": "cleared", "removed": len(ids)}


# ── 메인 데이터: 변경점(최근 1회) + 카테고리 묶음 + 현황분석 ──
@app.get("/api/latest-report")
def latest_report(run_id: Optional[str] = None):
    # 대상 run_id 목록 결정: 특정 run 지정 시 그 세션 전체, 아니면 가장 최근 세션
    allruns = q("SELECT crawl_run_id, site_name, started_at FROM crawl_runs "
                "WHERE status='completed' ORDER BY started_at DESC LIMIT 60")
    if not allruns:
        return {"has_data": False, "message": "크롤 데이터가 없습니다. 크롤을 실행하세요."}
    # 세션키별로 묶기
    by_sess = {}
    for rid, site, started in allruns:
        by_sess.setdefault(_session_key(started), []).append((rid, site, started))
    if run_id:
        target_key = next((_session_key(s) for r, _, s in allruns if r == run_id), None)
    else:
        target_key = _session_key(allruns[0][2])  # 가장 최근
    target_runs = by_sess.get(target_key, [allruns[0]])
    rids = [r[0] for r in target_runs]
    started = max(r[2] for r in target_runs)

    changes, by_cat = [], {"데이터·스키마": 0, "카피": 0, "가격·프로모션": 0, "비주얼": 0}
    for rid in rids:
        ch = q("SELECT id,url,severity_level,change_type,field_name,summary,before_value,after_value,evidence "
               "FROM detected_changes WHERE crawl_run_id=:r ORDER BY severity_level DESC, id DESC", r=rid)
        for c in ch:
            cat = CATEGORY.get(c[3], "데이터·스키마")
            by_cat[cat] = by_cat.get(cat, 0) + 1
            changes.append({
                "id": c[0], "url": c[1], "site": site_key_for_url(c[1]) or "samsung",
                "level": display_level(c[3], c[4], c[2]), "level_raw": c[2],
                "category": cat, "field": c[4], "summary": c[5],
                "before": c[6], "after": c[7],
                "evidence": json.loads(c[8]) if c[8] else {},
            })
    # 분석(POV)은 세션 내 run들 중 있는 것 모으기
    ins, act, summ, aeo = [], [], [], []
    for rid in rids:
        pov = q("SELECT observation, hypothesis, opportunity, recommended_action "
                "FROM povs WHERE related_crawl_run_id=:r LIMIT 1", r=rid)
        if pov:
            if pov[0][0]: summ.append(pov[0][0])
            if pov[0][1]: aeo.append(pov[0][1])
            ins += _loads(pov[0][2]); act += _loads(pov[0][3])
    analysis = {"summary": " ".join(summ), "aeo_implications": " ".join(aeo),
                "insights": ins, "actions": act}
    return {"has_data": True, "run_id": rids[0], "session": target_key,
            "timestamp": _kst_str(started),
            "has_changes": len(changes) > 0, "by_category": by_cat,
            "changes": changes, "analysis": analysis}


def _loads(s):
    try:
        return json.loads(s) if s else []
    except Exception:
        return []


# ── 현황 비교 (삼성 ↔ 애플) ──
@app.get("/api/compare")
def compare(ours: str = "samsung", theirs: str = "apple"):
    def latest_pages(sk):
        run = q("SELECT crawl_run_id FROM crawl_runs WHERE site_name=:s AND status='completed' "
                "ORDER BY started_at DESC LIMIT 1", s=sk)
        if not run:
            return []
        rows = q("SELECT url,title,meta_description,body_content,structural_signature,word_count "
                 "FROM page_snapshots WHERE crawl_run_id=:r", r=run[0][0])
        out = []
        for r in rows:
            sig = _loads(r[4])
            out.append({"url": r[0], "title": r[1], "meta_description": r[2],
                        "body_content": r[3] or "", "word_count": r[5] or 0,
                        "schema_types": sig.get("schema_types", []),
                        "faqs": [None] * sig.get("faq_count", 0)})
        return out
    op, tp = latest_pages(ours), latest_pages(theirs)
    if not op or not tp:
        return {"status": "insufficient_data",
                "reason": "두 사이트 모두 1회 이상 크롤이 완료되어야 비교가 가능합니다.",
                "ours_pages": len(op), "theirs_pages": len(tp)}
    intel = IntelEngine()
    res = intel.compare(
        ours={"display": SEED_TARGETS[ours].display_name, "facts": aeo_facts(op), "pages": op},
        theirs={"display": SEED_TARGETS[theirs].display_name, "facts": aeo_facts(tp), "pages": tp})
    res["status"] = res.get("status", "ok"); res["ours"] = ours; res["theirs"] = theirs
    return res


# ── 타임라인(필터) ──
@app.get("/api/timeline")
def timeline(level: Optional[str] = None, category: Optional[str] = None, limit: int = 100):
    rows = q("SELECT id,url,severity_level,change_type,field_name,summary,detected_at "
             "FROM detected_changes ORDER BY detected_at DESC LIMIT :l", l=limit)
    items = []
    for r in rows:
        lv = display_level(r[3], r[4], r[2]); cat = CATEGORY.get(r[3], "데이터·스키마")
        if level and lv != level: continue
        if category and cat != category: continue
        items.append({"id": r[0], "url": r[1], "level": lv, "category": cat,
                      "site": site_key_for_url(r[1]), "field": r[4],
                      "summary": r[5], "detected_at": str(r[6])})
    return {"items": items}


# ── 크롤 트리거 / 진행률 ──
@app.post("/trigger-crawl/all")
async def trigger_all():
    if crawl_state["crawling"]:
        raise HTTPException(409, "이미 크롤 진행 중")
    crawl_state.update(crawling=True, events=[], run_id=f"manual_{datetime.now():%Y%m%d_%H%M%S}")

    async def run():
        try:
            for sk in SITE_KEYS:
                await crawl_service.execute_crawl(sk)
        finally:
            crawl_state["crawling"] = False
    asyncio.create_task(run())
    return {"status": "started"}


@app.get("/api/crawl-status")
def crawl_status():
    return {"crawling": crawl_state["crawling"], "run_id": crawl_state["run_id"]}


@app.get("/api/crawl-progress")
async def crawl_progress():
    async def gen():
        last = 0
        while True:
            evs = crawl_state["events"]
            while last < len(evs):
                yield f"data: {json.dumps(evs[last], ensure_ascii=False)}\n\n"; last += 1
            if not crawl_state["crawling"] and last >= len(evs):
                yield f"data: {json.dumps({'type':'status','crawling':False})}\n\n"; break
            yield f"data: {json.dumps({'type':'heartbeat'})}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream")


# ── URL 관리 ──
class AddURL(BaseModel):
    url: str
    site_key: Optional[str] = None


@app.get("/api/urls")
def list_urls(site_key: Optional[str] = None):
    db = {}
    for r in q("SELECT site_key,url FROM monitored_urls WHERE enabled=true"):
        db.setdefault(r[0], []).append(r[1])
    keys = [site_key] if site_key else all_site_keys()
    out = []
    for k in keys:
        out += load_active_urls(k, db.get(k, []))
    return {"urls": out, "total": len(out)}


@app.post("/api/urls")
def add_url(req: AddURL):
    u = req.url.strip()
    if not u.startswith("http"):
        raise HTTPException(400, "유효한 URL(http...) 이어야 합니다")
    sk = req.site_key or site_key_for_url(u) or "unknown"
    with sync_engine.connect() as c:
        exists = c.execute(text("SELECT 1 FROM monitored_urls WHERE url=:u"), {"u": u}).fetchone()
        if exists:
            c.execute(text("UPDATE monitored_urls SET enabled=true WHERE url=:u"), {"u": u})
        else:
            c.execute(text("INSERT INTO monitored_urls (site_key,url,tier_level,enabled,created_at) "
                           "VALUES (:s,:u,:t,true,:c)"),
                      {"s": sk, "u": u, "t": tier_for_url(u), "c": datetime.utcnow()})
        c.commit()
    return {"status": "added", "url": u, "site_key": sk}


@app.delete("/api/urls")
def del_url(url: str = Query(...)):
    with sync_engine.connect() as c:
        c.execute(text("UPDATE monitored_urls SET enabled=false WHERE url=:u"), {"u": url}); c.commit()
    return {"status": "disabled", "url": url}


# ── 이미지 비교샷 ──
@app.get("/api/snapshot/screenshots")
def screenshots(url: str = Query(...)):
    rows = q("SELECT screenshot_thumb, screenshot_phash, crawled_at FROM page_snapshots "
             "WHERE url=:u AND screenshot_thumb IS NOT NULL ORDER BY crawled_at DESC LIMIT 2", u=url)
    if not rows:
        return {"status": "no_image"}
    after = {"thumb": rows[0][0], "phash": rows[0][1], "at": str(rows[0][2])}
    before = {"thumb": rows[1][0], "phash": rows[1][1], "at": str(rows[1][2])} if len(rows) > 1 else None
    regions = []
    if before:
        from diff_engine import diff_regions, hamming_distance
        regions = diff_regions(before["thumb"], after["thumb"])
        after["hamming"] = hamming_distance(before["phash"], after["phash"])
    return {"status": "ok", "before": before, "after": after, "regions": regions}


# ── Export (화면 변경점 그대로) ──
@app.get("/api/export/xlsx")
def export_xlsx(run_id: Optional[str] = None):
    from export_service import build_xlsx, filename
    rep = latest_report(run_id)
    data = build_xlsx(rep.get("changes", []), title="변경점", timestamp=rep.get("timestamp", ""))
    return StreamingResponse(iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename('apple_stalker','xlsx')}"})


@app.get("/api/export/pptx")
def export_pptx(run_id: Optional[str] = None):
    from export_service import build_pptx, filename
    rep = latest_report(run_id)
    data = build_pptx(rep.get("changes", []), title="변경점", timestamp=rep.get("timestamp", ""),
                      summary=(rep.get("analysis") or {}).get("summary", ""))
    return StreamingResponse(iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename={filename('apple_stalker','pptx')}"})


# ── Cron tick (GitHub Actions) ──
@app.api_route("/api/cron/tick", methods=["GET", "POST"])
async def cron_tick(token: str = Query(...), site: Optional[str] = None):
    if token != CRON_TOKEN:
        raise HTTPException(403, "invalid token")
    results = []
    for sk in ([site] if site else SITE_KEYS):
        try:
            r = await crawl_service.execute_crawl(sk)
            results.append({"site": sk, "status": r.get("status"), "changes": r.get("changes_detected")})
        except Exception as e:
            results.append({"site": sk, "status": "failed", "error": str(e)})
    prune_old_snapshots(int(os.getenv("KEEP_SNAPSHOTS", "5")))
    # 크롤 후 리포트 메일
    try:
        rt = "morning" if datetime.utcnow().hour < 3 else "afternoon"
        email_service.send(rt)
    except Exception as e:
        logger.warning(f"email skip: {e}")
    return {"ran_at": datetime.utcnow().isoformat(), "results": results}


# ── Email ──
@app.post("/api/email/test")
def email_test():
    r = email_service.send("test")
    if r["status"] == "sent":
        return r
    raise HTTPException(400 if r["status"] == "skipped" else 500, r.get("reason") or r.get("error"))


@app.get("/api/email/report/send")
def email_send(report_type: str = "morning"):
    return email_service.send(report_type)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
