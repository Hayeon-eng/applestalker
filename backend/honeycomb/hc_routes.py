"""
hc_routes.py — honeyComb API [2026-09 · 수집 확정: SERP API]  prefix /api/hc

  GET  /api/hc/config            국가·제품·top_n·범례 + provider(serpapi|mock) + 키 설정 여부
  GET  /api/hc/attributes        속성 표준(51+8) + 관측 위치
  GET  /api/hc/keywords · POST /api/hc/keywords · POST /api/hc/keywords/remove
  GET  /api/hc/runs              저장된 실행(실수집) + 목업 run 요약
  GET  /api/hc/runs/{run_id}     run 상세
  POST /api/hc/run               실수집 시작(백그라운드, SERPAPI_KEY 필요) — body {countries?, products?, detail?: true}
  GET  /api/hc/run-status        진행 상태
  GET  /api/hc/diff?prev=&cur=
  GET  /api/hc/report.xlsx?run_id=
저장: HC_RUNS_DIR(기본 backend/honeycomb/runs) — run JSON + raw/ (SerpApi 원본 응답, 매핑 보정용)
"""
from __future__ import annotations
import io
import json
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse, HTMLResponse

import hc_engine
from hc_provider import get_provider, MockProvider

hc_router = APIRouter(prefix="/api/hc", tags=["honeycomb"])
_mock = MockProvider()  # config/attributes 의 원본(국가·제품·속성 표준)
# [2026-09 신규] 키워드 추가는 SerpApi 호출량이 크게 늘어나는 부하 유발 조작이라 관리자 비밀번호로 막는다
# (main.py 의 URL 추가/삭제 게이트와 동일한 이름의 환경변수를 그대로 사용 — PC 한 대에서 값 하나만 관리).
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "0108")
RUNS_DIR = os.getenv("HC_RUNS_DIR") or os.path.join(os.path.dirname(__file__), "runs")
os.makedirs(RUNS_DIR, exist_ok=True)
_KW_PATH = os.path.join(os.path.dirname(__file__), "hc_keywords.json")
STATE: Dict[str, Any] = {"running": False, "done": 0, "total": 0, "run_id": None, "error": None, "cancel": False, "cells": []}


def _provider_kind() -> str:
    return "serpapi" if os.getenv("SERPAPI_KEY") else "mock"


def _load_keywords() -> Dict[str, Any]:
    try:
        return json.load(open(_KW_PATH, encoding="utf-8"))
    except Exception:
        return {"keywords": []}


def _save_keywords(d: Dict[str, Any]):
    json.dump(d, open(_KW_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _saved_runs() -> list:
    out = []
    for f in sorted((f for f in os.listdir(RUNS_DIR) if f.endswith(".json")), reverse=True):
        try:
            out.append(json.load(open(os.path.join(RUNS_DIR, f), encoding="utf-8")))
        except Exception:
            continue
    return out


def _all_runs() -> list:
    """목업 run(있으면) + 실수집 run — 오래된 것부터."""
    return list(_mock.runs()) + sorted(_saved_runs(), key=lambda r: r.get("at", ""))


def _find_run(run_id: str) -> Optional[Dict[str, Any]]:
    return next((r for r in _all_runs() if r["run_id"] == run_id), None)


@hc_router.get("/config")
def hc_config():
    cfg = dict(_mock.config()); cfg.pop("keywords", None)
    return {**cfg, "provider": _provider_kind(), "serpapi_key_set": bool(os.getenv("SERPAPI_KEY")),
            "attribute_count": len(_mock.attributes()), "primary_attribute_count": sum(1 for a in _mock.attributes() if not a.get("sub")),
            "status_legend": {**cfg.get("status_legend", {}), "error": "조회 실패(API 오류·한도 초과)"}}


@hc_router.get("/attributes")
def hc_attributes():
    return {"attributes": _mock.attributes()}


@hc_router.get("/keywords")
def hc_keywords():
    return _load_keywords()


@hc_router.post("/keywords")
def hc_keyword_upsert(payload: Dict[str, Any]):
    text = (payload.get("text") or "").strip(); product = (payload.get("product") or "").strip()
    ktype = (payload.get("type") or "brand").strip()
    if not text or not product:
        raise HTTPException(400, "product, text 필요")
    # [2026-09 신규] 키워드 하나 늘 때마다 국가 수만큼 SerpApi 호출이 곱절로 늘어나는 부하 유발 조작이라
    # (기존에도 제품당 2개 제한이 있던 이유와 같음) 관리자 비밀번호 없이는 추가할 수 없게 막는다.
    if (payload.get("admin_password") or "") != ADMIN_PASSWORD:
        raise HTTPException(403, "관리자 비밀번호가 올바르지 않습니다")
    sub = (payload.get("subtype") or "").strip().upper()
    # [2026-09-11 운영 결정] 제품명 키워드(A1~A3)만 허용 — 자연어(B) 키워드는 사용하지 않는다(호출 수 절감)
    if sub not in ("", "A1", "A2", "A3") or ktype != "brand":
        raise HTTPException(400, "제품명 키워드(A1~A3)만 등록할 수 있습니다 — 자연어 키워드는 사용하지 않습니다")
    ktype = "brand"
    d = _load_keywords(); kid = payload.get("id") or f"{product}:{ktype}:{text}"
    item = {"id": kid, "product": product, "text": text, "type": ktype, "subtype": sub or "A1",
            "countries": [c.strip().upper() for c in (payload.get("countries") or []) if c.strip()],
            "enabled": bool(payload.get("enabled", True)), "note": (payload.get("note") or "").strip()}
    d["keywords"] = [k for k in d["keywords"] if k["id"] != kid] + [item]
    if sum(1 for k in d["keywords"] if k["product"] == product and k["enabled"]) > 2:
        raise HTTPException(400, "제품당 사용 중 키워드는 2개까지입니다(호출 수 절감) — 기존 키워드를 끄거나 삭제하세요")
    _save_keywords(d)
    return {"ok": True, "keyword": item, "count": len(d["keywords"])}


@hc_router.post("/keywords/remove")
def hc_keyword_remove(payload: Dict[str, Any]):
    d = _load_keywords(); before = len(d["keywords"])
    d["keywords"] = [k for k in d["keywords"] if k["id"] != payload.get("id")]
    _save_keywords(d)
    return {"ok": True, "removed": before - len(d["keywords"]), "count": len(d["keywords"])}


@hc_router.get("/runs")
def hc_runs():
    return {"runs": [hc_engine.summarize(r) for r in _all_runs()], "provider": _provider_kind()}


@hc_router.get("/runs/{run_id}")
def hc_run(run_id: str, keyword_type: Optional[str] = Query(None)):
    run = _find_run(run_id)
    if not run:
        raise HTTPException(404, f"run {run_id} 없음")
    cells = [dict(c, gaps=hc_engine.gaps(c)) for c in run["cells"] if not keyword_type or c["keyword_type"] == keyword_type]
    return {"run_id": run_id, "week": run.get("week"), "at": run["at"], "source": run.get("source"), "errors": run.get("errors", []),
            "api_calls": run.get("api_calls"), "summary": hc_engine.summarize(run, keyword_type), "cells": cells}


@hc_router.get("/diff")
def hc_diff(prev: str, cur: str):
    a, b = _find_run(prev), _find_run(cur)
    if not a or not b:
        raise HTTPException(404, "run_id 확인")
    return {"prev": prev, "cur": cur, "changes": hc_engine.diff_runs(a, b)}


def _bg(countries, products, detail):
    try:
        run_id_tmp = STATE["run_id"]
        provider = get_provider("serpapi", raw_dir=os.path.join(RUNS_DIR, run_id_tmp, "raw"))
        kws = _load_keywords().get("keywords", [])

        def prog(d, t, info=None):
            STATE.update(done=d, total=t)
            if info:
                cells = [x for x in STATE["cells"] if not (x["country"] == info["country"] and x["product"] == info["product"] and x["keyword"] == info["keyword"])]
                STATE["cells"] = cells + [info]
        run = hc_engine.collect_run(provider, _mock.config(), _mock.attributes(), kws, countries, products, detail, prog,
                                    should_cancel=lambda: STATE.get("cancel"))
        run["run_id"] = run_id_tmp
        json.dump(run, open(os.path.join(RUNS_DIR, run_id_tmp + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        files = sorted(f for f in os.listdir(RUNS_DIR) if f.endswith(".json"))
        for f in files[:-52]:  # 1년치(주 1회) 보관
            os.remove(os.path.join(RUNS_DIR, f))
    except Exception as e:
        STATE["error"] = str(e)[:300]
    finally:
        STATE["running"] = False


def _estimate(countries=None, products=None, detail=False) -> Dict[str, Any]:
    cfg = _mock.config(); kws = [k for k in _load_keywords().get("keywords", []) if k.get("enabled", True)]
    cts = [c for c in cfg["countries"] if not countries or c["code"] in countries]
    prs = [p for p in cfg["products"] if not products or p["slug"] in products]
    n = sum(1 for c in cts for p in prs for k in kws if k["product"] == p["slug"] and (not k.get("countries") or c["code"] in k["countries"]))
    return {"searches": n, "detail_max": n if detail else 0, "total_max": n + (n if detail else 0),
            "countries": len(cts), "products": len(prs), "keywords_enabled": len(kws),
            "note": "상세 조회(속성 역추적)는 우리 카드가 잡힌 셀마다 1회 추가 — 최대치로 계산"}


@hc_router.get("/run-estimate")
def hc_run_estimate(detail: bool = Query(False), countries: Optional[List[str]] = Query(None), products: Optional[List[str]] = Query(None)):
    return _estimate(countries=countries, products=products, detail=detail)


@hc_router.post("/run")
def hc_run_start(payload: Dict[str, Any] = Body(default={})):
    if _provider_kind() != "serpapi":
        raise HTTPException(501, "SERPAPI_KEY 가 설정되지 않았습니다 — 데스크톱 설정(/desktop/settings) 또는 환경변수에 키를 넣으세요")
    if STATE.get("running"):
        raise HTTPException(409, "이미 수집 중")
    from datetime import datetime
    STATE.update(running=True, done=0, total=0, run_id=f"hc_{datetime.now():%Y%m%d_%H%M%S}", error=None, cancel=False, cells=[])
    detail = bool(payload.get("detail", False))  # 기본 OFF — 호출 수 절감(운영 결정 2026-09)
    threading.Thread(target=_bg, args=(payload.get("countries"), payload.get("products"), detail), daemon=True).start()
    return {"status": "started", "run_id": STATE["run_id"], "estimate": _estimate(payload.get("countries"), payload.get("products"), detail)}


@hc_router.get("/run-status")
def hc_run_status():
    return STATE


@hc_router.post("/run/cancel")
def hc_run_cancel():
    """멈춤 — 다음 키워드부터 중단하고 지금까지 결과를 저장한다(API 호출도 그 시점에서 멈춤)."""
    if not STATE.get("running"):
        return {"ok": True, "running": False}
    STATE["cancel"] = True
    return {"ok": True, "cancelling": True}


@hc_router.get("/report.xlsx")
def hc_report(run_id: str):
    run = _find_run(run_id)
    if not run:
        raise HTTPException(404, f"run {run_id} 없음")
    import hc_report
    buf = hc_report.build_xlsx(run, _mock.attributes(), _mock.config())
    return StreamingResponse(io.BytesIO(buf), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename=honeycomb_{run_id}.xlsx"})


# ── 이메일(2026-09 신규): 본문 복사 / 발송 / 자동발송(cron) ─────────────────
def _latest_two_runs():
    """[가장 최근, 그 이전] — diff_runs 로 지난주 대비 변화를 보여주기 위함(둘 다 있을 때만)."""
    runs = _all_runs()  # 오래된 것부터
    if not runs:
        return None, None
    return runs[-1], (runs[-2] if len(runs) > 1 else None)


@hc_router.get("/email-html")
def hc_email_html(run_id: Optional[str] = None):
    """SMTP 발송 대신, 메일에 붙여넣을 수 있는 리포트 HTML 본문만 반환 — 큐비/애플스토커의
    '메일 본문 복사'와 동일한 역할. run_id 없으면 최신 실행."""
    import hc_email
    if run_id:
        run = _find_run(run_id)
        if not run:
            raise HTTPException(404, f"run {run_id} 없음")
        _, prev = _latest_two_runs()
        prev = prev if prev and prev["run_id"] != run_id else None
    else:
        run, prev = _latest_two_runs()
        if not run:
            raise HTTPException(404, "실행 결과 없음")
    return HTMLResponse(content=hc_email.build_html(run, prev, _mock.config()))


@hc_router.get("/email/send")
def hc_email_send(run_id: Optional[str] = None):
    import hc_email
    if run_id:
        run = _find_run(run_id)
        if not run:
            raise HTTPException(404, f"run {run_id} 없음")
        _, prev = _latest_two_runs()
        prev = prev if prev and prev["run_id"] != run_id else None
    else:
        run, prev = _latest_two_runs()
        if not run:
            raise HTTPException(404, "실행 결과 없음")
    r = hc_email.send_email(run, prev, _mock.config())
    if r["status"] == "sent":
        return r
    raise HTTPException(400 if r["status"] == "skipped" else 500, r.get("reason") or r.get("error"))


@hc_router.api_route("/cron/tick", methods=["GET", "POST"])
def hc_cron_tick(token: str = Query(...)):
    """[2026-09 신규] 자동 발송 — 애플스토커의 /api/cron/tick 과 동일하게 GitHub Actions 스케줄에서
    호출한다. CRON_TOKEN 은 main.py 와 같은 환경변수를 그대로 써서 시크릿을 하나만 관리하면 된다.
    수집은 여기서 동기로 끝까지 기다린 뒤(운영 결정: 활성 키워드 전체·전 국가·전 제품) 메일을 보낸다 —
    호출 수가 크므로 워크플로 스케줄 자체를 자주 돌리지 않는 것으로 부하를 관리한다."""
    import hc_email
    cron_token = os.getenv("CRON_TOKEN", "change-me")
    if token != cron_token:
        raise HTTPException(403, "invalid token")
    kws = [k for k in _load_keywords().get("keywords", []) if k.get("enabled", True)]
    run_id_tmp = f"cron_{time.strftime('%Y%m%d_%H%M%S')}"
    provider = get_provider(_provider_kind(), raw_dir=os.path.join(RUNS_DIR, run_id_tmp, "raw"))
    prev, _ = _latest_two_runs()
    try:
        run = hc_engine.collect_run(provider, _mock.config(), _mock.attributes(), kws, None, None, True, None)
        run["run_id"] = run_id_tmp
        os.makedirs(RUNS_DIR, exist_ok=True)
        json.dump(run, open(os.path.join(RUNS_DIR, run_id_tmp + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        files = sorted(f for f in os.listdir(RUNS_DIR) if f.endswith(".json"))
        for f in files[:-52]:  # 1년치(주 1회) 보관 — /run 백그라운드 정리와 동일 기준
            os.remove(os.path.join(RUNS_DIR, f))
    except Exception as e:
        return {"ran_at": datetime.utcnow().isoformat(), "status": "collect_failed", "error": str(e)[:300]}
    mail = hc_email.send_email(run, prev, _mock.config())
    return {"ran_at": datetime.utcnow().isoformat(), "run_id": run_id_tmp, "cells": len(run.get("cells", [])), "email": mail}
