"""
qb_routes_targets.py — 대상 관리 API [2026-09 신규]  (사이드바 "URL 관리" → "대상 관리")

  GET  /api/qb/targets                해석 결과 요약 + 항목(source: finder|exception|legacy, excluded 포함) + unresolved
  POST /api/qb/targets/resolve        finder/spec-ia 로 전 사이트 재해석(백그라운드) → site_registry.resolved.json
  GET  /api/qb/targets/status         진행 상태
  POST /api/qb/targets/exception      예외 등록 {sitecode,url,product,page_type,region?,country?,lang?,note?}
  POST /api/qb/targets/exception/remove {sitecode,url}
  POST /api/qb/targets/exclude        {sitecode,url,excluded:true|false} — 해석 결과를 지우지 않고 크롤에서만 제외
  GET  /api/qb/targets/export.json    resolved+exceptions 를 저장소에 커밋할 수 있게 내려준다(Render 디스크는 재배포 시 초기화)
"""
from __future__ import annotations
import json
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import Body, HTTPException
from fastapi.responses import JSONResponse

import resolver
import qb_core
from qb_core import qb_router, _registry


@qb_router.get("/targets")
def qb_targets():
    res = resolver.load_resolved() or {}
    exc = resolver.load_exceptions()
    entries = []
    exc_keys = {(e["sitecode"], e["url"]) for e in exc}
    for e in exc:
        entries.append({**e, "source": "exception"})
    for e in res.get("entries", []):
        if (e["sitecode"], e["url"]) not in exc_keys:
            entries.append(e)
    covered = {(e["sitecode"], e.get("product"), e.get("page_type") or "PDP") for e in entries}
    for b in _registry.legacy_sites:
        if (b["sitecode"], b.get("product"), b.get("page_type") or "PDP") not in covered:
            entries.append({**b, "source": "legacy"})
    active = {(e["sitecode"], e["url"]) for e in _registry.all()}
    for e in entries:
        e["active"] = (e["sitecode"], e["url"]) in active and not e.get("excluded")
    by_source: Dict[str, int] = {}
    for e in entries:
        by_source[e["source"]] = by_source.get(e["source"], 0) + 1
    return {"generated_at": res.get("generated_at"), "stats": {**res.get("stats", {}), "by_source": by_source, "active": len(_registry.all())},
            "products": res.get("products", []), "entries": entries, "unresolved": res.get("unresolved", []), "state": resolver.STATE}


@qb_router.post("/targets/resolve")
def qb_targets_resolve():
    if resolver.STATE.get("running"):
        raise HTTPException(409, "이미 해석 중입니다")
    sites = _registry.legacy_sites or _registry.all()
    ok = resolver.start_background(sites)
    return {"started": ok, "sites": len({s["sitecode"] for s in sites})}


@qb_router.get("/targets/status")
def qb_targets_status():
    st = dict(resolver.STATE)
    if not st.get("running") and st.get("finished"):
        try:
            _registry.reload()
        except Exception:
            pass
    return st


@qb_router.post("/targets/exception")
def qb_targets_exception(payload: Dict[str, Any] = Body(...)):
    sc = (payload.get("sitecode") or qb_core._sitecode_from_url(payload.get("url", "")) or "").lower()
    url = (payload.get("url") or "").strip()
    if not sc or not url.startswith("http"):
        raise HTTPException(400, "sitecode 와 절대 URL 이 필요합니다")
    exc = [e for e in resolver.load_exceptions() if not (e["sitecode"] == sc and e["url"] == url)]
    meta = _registry.get(sc) or {}
    exc.append({"sitecode": sc, "url": url, "product": payload.get("product") or "", "page_type": payload.get("page_type") or "PDP",
                "region": payload.get("region") or meta.get("region", ""), "country": payload.get("country") or meta.get("country", ""),
                "lang": payload.get("lang") or meta.get("lang", ""), "note": payload.get("note", ""), "source": "exception"})
    resolver.save_exceptions(exc); _registry.reload()
    return {"ok": True, "count": len(exc)}


@qb_router.post("/targets/exception/remove")
def qb_targets_exception_remove(payload: Dict[str, Any] = Body(...)):
    exc = resolver.load_exceptions()
    keep = [e for e in exc if not (e["sitecode"] == payload.get("sitecode") and e["url"] == payload.get("url"))]
    resolver.save_exceptions(keep); _registry.reload()
    return {"ok": True, "removed": len(exc) - len(keep)}


@qb_router.post("/targets/exclude")
def qb_targets_exclude(payload: Dict[str, Any] = Body(...)):
    """해석 결과 항목을 크롤 대상에서만 제외/복귀(파일의 excluded 플래그)."""
    res = resolver.load_resolved()
    if not res:
        raise HTTPException(404, "해석 결과가 없습니다")
    hit = 0
    for e in res.get("entries", []):
        if e["sitecode"] == payload.get("sitecode") and e["url"] == payload.get("url"):
            e["excluded"] = bool(payload.get("excluded", True)); hit += 1
    json.dump(res, open(resolver.RESOLVED_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _registry.reload()
    return {"ok": True, "updated": hit}


@qb_router.get("/targets/export.json")
def qb_targets_export():
    return JSONResponse({"resolved": resolver.load_resolved(), "exceptions": resolver.load_exceptions()},
                        headers={"Content-Disposition": "attachment; filename=site_registry.resolved.json"})
