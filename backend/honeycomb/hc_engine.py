"""
hc_engine.py — honeyComb 판정 엔진 [2026-09]

입력: provider 표준 결과(items) 또는 목업 cells · 출력: cell 판정 + 집계.

판정(사용자 확정 2026-09-11)
  · top1     : samsung.com 스토어 리스팅 position == 1
  · topn     : position ≤ top_n(기본 8 — 데스크톱 2줄)
  · low      : 노출되나 top_n 밖
  · absent   : 결과 안에 samsung.com 스토어 없음
  · unranked : 속성 역추적은 됐으나 위치 기록 없음(수동 리포트 공란 이관분)
  · unchecked: 미검사(long-tail 키워드 등 수집 전)

속성 역추적(attrs): entered | missed | na(관측 불가 — 피드 전용)
피드 대조(feed):    fed | empty | na   → gap = 피드에 있는데 화면에 없음(fed&missed) / 피드에 없는데 보임(empty&entered)
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

STATUS_ORDER = ["top1", "topn", "low", "absent", "unranked", "unchecked", "error"]


def judge_position(items: List[Dict[str, Any]], top_n: int) -> Dict[str, Any]:
    """provider items → (position, first_store, status). 실수집 provider 용."""
    first_store = items[0]["merchant"] if items else None
    ours = [it for it in items if it.get("is_samsung_store")]
    if not items:
        return {"position": None, "first_store": None, "status": "unchecked"}
    if not ours:
        return {"position": None, "first_store": first_store, "status": "absent"}
    pos = min(it["position"] for it in ours)
    return {"position": pos, "first_store": first_store,
            "status": "top1" if pos == 1 else "topn" if pos <= top_n else "low"}


def trace_attributes(item: Dict[str, Any], detail: Dict[str, str], attributes: List[Dict[str, Any]]) -> Dict[str, str]:
    """카드(item.attrs)+상세(detail) 에서 관측된 값 → 51속성 entered/missed/na. 실수집 provider 용."""
    seen = {**(item.get("attrs") or {}), **(detail or {})}
    out = {}
    for a in attributes:
        key = a["code"] + ("" if not a.get("sub") else f"#{a['no']}")
        if a["observe"] == "feed":
            out[key] = "na"
        else:
            out[key] = "entered" if seen.get(a["code"]) not in (None, "", False) else "missed"
    return out


def gaps(cell: Dict[str, Any]) -> Dict[str, List[str]]:
    a, f = cell.get("attrs") or {}, cell.get("feed") or {}
    return {
        "fed_but_missed": sorted(k for k, v in a.items() if v == "missed" and f.get(k) == "fed"),
        "empty_but_entered": sorted(k for k, v in a.items() if v == "entered" and f.get(k) == "empty"),
    }


def summarize(run: Dict[str, Any], keyword_type: Optional[str] = "brand") -> Dict[str, Any]:
    cells = [c for c in run["cells"] if not keyword_type or c["keyword_type"] == keyword_type]
    by_status = {s: sum(1 for c in cells if c["status"] == s) for s in STATUS_ORDER}
    checked = [c for c in cells if c["status"] in ("top1", "topn", "low", "absent")]
    per_country: Dict[str, Dict[str, int]] = {}
    per_product: Dict[str, Dict[str, int]] = {}
    for c in cells:
        per_country.setdefault(c["country"], {s: 0 for s in STATUS_ORDER})[c["status"]] += 1
        per_product.setdefault(c["product"], {s: 0 for s in STATUS_ORDER})[c["status"]] += 1
    entered_rates = []
    for c in checked + [x for x in cells if x["status"] == "unranked"]:
        obs = [v for v in (c.get("attrs") or {}).values() if v != "na"]
        if obs:
            entered_rates.append(sum(1 for v in obs if v == "entered") / len(obs))
    stores: Dict[str, int] = {}
    for c in checked:
        if c.get("first_store"):
            stores[c["first_store"]] = stores.get(c["first_store"], 0) + 1
    return {
        "run_id": run["run_id"], "week": run["week"], "at": run["at"], "cells": len(cells),
        "by_status": by_status,
        "top1_rate": round(100 * by_status["top1"] / len(checked), 1) if checked else None,
        "topn_rate": round(100 * (by_status["top1"] + by_status["topn"]) / len(checked), 1) if checked else None,
        "attr_entered_rate": round(100 * sum(entered_rates) / len(entered_rates), 1) if entered_rates else None,
        "first_stores": dict(sorted(stores.items(), key=lambda kv: -kv[1])),
        "per_country": per_country, "per_product": per_product,
    }


def diff_runs(prev: Dict[str, Any], cur: Dict[str, Any]) -> List[Dict[str, Any]]:
    """전주 대비 변화 셀 — 순위 상태 변화 / 속성 entered 변화."""
    key = lambda c: (c["country"], c["product"], c["keyword"])
    p = {key(c): c for c in prev["cells"]}
    out = []
    for c in cur["cells"]:
        o = p.get(key(c))
        if not o:
            continue
        ch = {}
        if o["status"] != c["status"]:
            ch["status"] = [o["status"], c["status"]]
        if o.get("position") != c.get("position"):
            ch["position"] = [o.get("position"), c.get("position")]
        gained = sorted(k for k, v in (c.get("attrs") or {}).items() if v == "entered" and (o.get("attrs") or {}).get(k) == "missed")
        lost = sorted(k for k, v in (c.get("attrs") or {}).items() if v == "missed" and (o.get("attrs") or {}).get(k) == "entered")
        if gained or lost:
            ch["attrs"] = {"gained": gained, "lost": lost}
        if ch:
            out.append({"country": c["country"], "product": c["product"], "keyword": c["keyword"], "changes": ch})
    return out


# ── [2026-09 수집 확정] SERP API 실수집 실행 ────────────────────────────────
def collect_run(provider, config: Dict[str, Any], attributes: List[Dict[str, Any]], keywords: List[Dict[str, Any]],
                countries: Optional[List[str]] = None, products: Optional[List[str]] = None,
                detail_for_samsung: bool = True, progress=None) -> Dict[str, Any]:
    """국가 × 제품 × 활성 키워드마다 provider 로 Google Shopping 을 조회해 cell 을 만든다.
    · 우리 리스팅이 있으면(가장 높은 position) 그 카드의 product_id 로 상세를 1회 더 조회해 속성을 역추적한다.
    · 실패한 조회는 status='error' 로 남기고 계속 진행(한 키워드 실패가 전체를 죽이지 않게)."""
    from datetime import datetime
    top_n = int(config.get("top_n", 8))
    cts = [c for c in config["countries"] if not countries or c["code"] in countries]
    prs = [p for p in config["products"] if not products or p["slug"] in products]
    run_id = f"hc_{datetime.now():%Y%m%d_%H%M%S}"
    cells: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    total = sum(1 for c in cts for p in prs for k in keywords if k.get("enabled", True) and k["product"] == p["slug"]
                and (not k.get("countries") or c["code"] in k["countries"]))
    done = 0
    for c in cts:
        for p in prs:
            for k in keywords:
                if not k.get("enabled", True) or k["product"] != p["slug"] or (k.get("countries") and c["code"] not in k["countries"]):
                    continue
                cell = {"country": c["code"], "product": p["slug"], "keyword": k["text"], "keyword_type": k.get("type", "brand"),
                        "keyword_subtype": k.get("subtype"), "position": None, "top_n": top_n, "scom_exposed": None,
                        "first_store": None, "status": "unchecked", "attrs": {}, "feed": {}, "evidence": None, "items_top": []}
                try:
                    res = provider.fetch_shopping(c, k["text"])
                    items = res.get("items") or []
                    j = judge_position(items, top_n)
                    cell.update(position=j["position"], first_store=j["first_store"], status=j["status"],
                                scom_exposed="O" if j["position"] is not None else "X" if items else None,
                                evidence=res.get("raw_ref"), fetched_at=res.get("fetched_at"),
                                items_top=[{k2: it.get(k2) for k2 in ("position", "title", "merchant", "price", "is_samsung_store", "link")}
                                           for it in items[:top_n]])
                    ours = [it for it in items if it.get("is_samsung_store")]
                    if ours:
                        best = min(ours, key=lambda it: it["position"])
                        detail = provider.fetch_product_detail(c, best) if detail_for_samsung else {}
                        cell["attrs"] = trace_attributes(best, detail, attributes)
                        cell["our_item"] = {k2: best.get(k2) for k2 in ("position", "title", "merchant", "price", "link", "product_id")}
                except Exception as e:
                    cell["status"] = "error"; cell["error"] = str(e)[:200]
                    errors.append({"country": c["code"], "product": p["slug"], "keyword": k["text"], "error": str(e)[:200]})
                cells.append(cell); done += 1
                if progress:
                    progress(done, total)
    return {"run_id": run_id, "week": datetime.now().strftime("W%V"), "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": f"live:{getattr(provider, 'name', 'provider')}", "cells": cells, "errors": errors,
            "api_calls": getattr(provider, "calls", None)}
