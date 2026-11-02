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


# [2026-09 신규] 제품명으로 검색하면 같은 브랜드의 액세서리(Trail Band, Case 등)도 결과에 섞여 들어오는데,
# 이걸 "우리 제품이 노출됨"으로 세면 실제 본품 순위가 왜곡된다(액세서리가 더 잘 팔려서 순위가 높으면
# 본품이 낮은데도 1위로 잡힘). 제목에 액세서리 키워드가 있으면 순위·속성 판정 대상에서 제외한다.
_ACCESSORY_KEYWORDS = ("band", "strap", "case", "cover", "sleeve", "pouch", "screen protector",
                       "tempered glass", "charger", "charging", "cable", "adapter", "dock",
                       "stand", "holder", "clip", "skin", "bumper", "clasp")


def _is_accessory_title(title: Optional[str]) -> bool:
    if not title:
        return False
    t = title.lower()
    return any(kw in t for kw in _ACCESSORY_KEYWORDS)


def judge_position(items: List[Dict[str, Any]], top_n: int, is_ours=None) -> Dict[str, Any]:
    """provider items → (position, first_store, status). 실수집 provider 용.
    [2026-11] is_ours: 브랜드 공식몰 판정 함수(기본=삼성). Apple 비교 셀은 Apple 공식몰 기준으로 같은 판정을 쓴다."""
    if not items:
        return {"position": None, "first_store": None, "status": "unchecked"}
    first_store = items[0]["merchant"]
    _ours = is_ours or (lambda it: it.get("is_samsung_store"))
    ours = [it for it in items if _ours(it) and not _is_accessory_title(it.get("title"))]
    if not ours:
        return {"position": None, "first_store": first_store, "status": "absent"}
    pos = min(it["position"] for it in ours)
    return {"position": pos, "first_store": first_store,
            "status": "top1" if pos == 1 else "topn" if pos <= top_n else "low"}


def trace_attributes(item: Dict[str, Any], detail: Dict[str, str], attributes: List[Dict[str, Any]],
                     detail_checked: bool = True) -> Dict[str, Any]:
    """카드(item.attrs)+상세(detail) 에서 관측된 값 → 51속성 entered/missed/na. 실수집 provider 용.
    [2026-09 신규] 그동안 entered/missed 로만 뭉개져서 "보임/안 보임"만 알 수 있었다 — 실제로 어떤
    텍스트·불릿·이미지로 노출됐는지가 안 보였다. attrs(상태 문자열, 기존 소비처 호환 그대로 유지)와
    별개로 values(실제 관측값)를 같이 반환해서, 화면에서 "어떻게" 노출됐는지도 보여줄 수 있게 한다."""
    seen = {**(item.get("attrs") or {}), **(detail or {})}
    out: Dict[str, str] = {}
    values: Dict[str, Any] = {}
    for a in attributes:
        key = a["code"] + ("" if not a.get("sub") else f"#{a['no']}")
        if a["observe"] == "feed":
            out[key] = "na"
        else:
            raw = seen.get(a["code"])
            if raw in (None, "", False) and a["observe"] == "detail" and not detail_checked:
                # [2026-11 D4] 상세 창을 열어보지 않았거나(조회 OFF·토큰 없음) 조회가 실패한 경우 —
                #   '안 보임(missed)'이 아니라 '확인 안 함(unchecked)'. 전부 빨갛게 뜨던 PPT 9번 문제.
                out[key] = "unchecked"
                continue
            out[key] = "entered" if raw not in (None, "", False) else "missed"
            if raw not in (None, "", False):
                values[key] = raw
    return {"attrs": out, "attr_values": values}


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
        obs = [v for v in (c.get("attrs") or {}).values() if v in ("entered", "missed")]   # [2026-11] 확인 안 함 제외
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
                detail_for_samsung: bool = True, progress=None, should_cancel=None) -> Dict[str, Any]:
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
                if should_cancel and should_cancel():
                    break
                if progress:
                    progress(done, total, {"country": c["code"], "product": p["slug"], "keyword": k["text"], "status": "조회 중"})
                cell = {"country": c["code"], "product": p["slug"], "keyword": k["text"], "keyword_type": k.get("type", "brand"),
                        "keyword_subtype": k.get("subtype"), "position": None, "top_n": top_n, "scom_exposed": None,
                        "first_store": None, "status": "unchecked", "attrs": {}, "attr_values": {}, "feed": {}, "evidence": None, "items_top": [], "competitor_benchmark": None}
                try:
                    res = provider.fetch_shopping(c, k["text"])
                    items = res.get("items") or []
                    j = judge_position(items, top_n)
                    cell.update(position=j["position"], first_store=j["first_store"], status=j["status"],
                                scom_exposed="O" if j["position"] is not None else "X" if items else None,
                                evidence=res.get("raw_ref"), fetched_at=res.get("fetched_at"),
                                items_top=[{k2: it.get(k2) for k2 in ("position", "title", "merchant", "price", "is_samsung_store", "link")}
                                           for it in items[:top_n]])
                    ours = [it for it in items if it.get("is_samsung_store") and not _is_accessory_title(it.get("title"))]
                    if ours:
                        best = min(ours, key=lambda it: it["position"])
                        cell["our_item"] = {k2: best.get(k2) for k2 in ("position", "title", "merchant", "price", "link", "product_id")}
                        # 카드에서 바로 보이는 속성은 항상 채운다(상세 조회 없이도)
                        _tr = trace_attributes(best, {}, attributes, detail_checked=False)
                        cell["attrs"], cell["attr_values"] = _tr["attrs"], _tr["attr_values"]
                        cell["detail_checked"] = False
                        # 상세 조회는 '있으면 더 채우는' 보강 단계 — 실패해도 순위 결과는 그대로 두고 경고만 남긴다
                        if detail_for_samsung:
                            try:
                                detail = provider.fetch_product_detail(c, best)
                                if detail:
                                    _tr = trace_attributes(best, detail, attributes, detail_checked=True)
                                    cell["attrs"], cell["attr_values"] = _tr["attrs"], _tr["attr_values"]
                                    cell["detail_checked"] = True
                            except Exception as de:
                                cell["detail_error"] = str(de)[:200]
                                errors.append({"country": c["code"], "product": p["slug"], "keyword": k["text"],
                                               "error": f"상세 조회 실패(순위는 정상): {str(de)[:160]}"})
                    elif items:
                        # [2026-09 신규] 우리 제품이 안 보일 때 "그럼 1위는 뭘 잘하고 있나"를 카드 데이터만으로
                        # 추가 호출 없이 함께 남긴다 — SerpApi 비용을 늘리지 않으면서 벤치마크로 쓸 수 있게.
                        rival = min((it for it in items if not _is_accessory_title(it.get("title"))), key=lambda it: it["position"], default=None)
                        if rival:
                            _tr = trace_attributes(rival, {}, attributes, detail_checked=False)
                            cell["competitor_benchmark"] = {
                                **{k2: rival.get(k2) for k2 in ("position", "title", "merchant", "price", "link")},
                                "attrs": _tr["attrs"], "attr_values": _tr["attr_values"],
                            }
                except Exception as e:
                    # 여기까지 오면 검색(순위) 자체가 실패한 것 — 그때만 error
                    cell["status"] = "error"; cell["error"] = str(e)[:200]
                    errors.append({"country": c["code"], "product": p["slug"], "keyword": k["text"], "error": str(e)[:200]})
                cells.append(cell); done += 1
                if progress:
                    progress(done, total, {"country": c["code"], "product": p["slug"], "keyword": k["text"], "status": cell["status"],
                                           "position": cell.get("position"), "first_store": cell.get("first_store"), "error": cell.get("error")})
    return {"run_id": run_id, "week": datetime.now().strftime("W%V"), "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": f"live:{getattr(provider, 'name', 'provider')}", "cells": cells, "errors": errors,
            "api_calls": getattr(provider, "calls", None), "cancelled": bool(should_cancel and should_cancel())}


# ── [2026-11 D3] 경쟁 브랜드(Apple) 비교 수집 ───────────────────────────────────
# 삼성 제품별로 비교할 Apple 모델(모델명 단위, hc_config.json "competitors")을 사용자가 골라 조회한다.
# · 같은 Apple 모델이 여러 삼성 제품의 비교 대상이면(예: iPhone Duo ↔ Fold8·Fold8 Ultra) 국가당 1회만 호출하고
#   결과를 각 삼성 제품 셀에 복사한다(호출 수 절감).
# · 판정 기준은 삼성과 같다 — Apple 공식몰(apple.com) 리스팅의 순위 + 속성 노출.
def is_brand_store(brand: str, item: Dict[str, Any]) -> bool:
    from urllib.parse import urlparse
    m = (item.get("merchant") or "").lower()
    host = (urlparse(item.get("link") or "").netloc or "").lower()
    resellers = ("amazon", "ebay", "best buy", "bestbuy", "walmart", "target", "flipkart", "shopee", "lazada",
                 "jb hi-fi", "argos", "currys", "mediamarkt", "fnac", "boulanger", "costco", "verizon", "at&t", "t-mobile")
    b = (brand or "").lower()
    if b == "samsung":
        return bool(item.get("is_samsung_store"))
    return (b in m and not any(r in m for r in resellers)) or host.endswith(f"{b}.com")


def collect_competitors(provider, config: Dict[str, Any], attributes: List[Dict[str, Any]], selected: List[str],
                        countries: Optional[List[str]] = None, products: Optional[List[str]] = None,
                        detail: bool = True, progress=None, should_cancel=None) -> Dict[str, Any]:
    top_n = int(config.get("top_n", 8))
    cts = [c for c in config["countries"] if not countries or c["code"] in countries]
    prs = {p["slug"] for p in config["products"] if not products or p["slug"] in products}
    models = [m for m in (config.get("competitors") or []) if m.get("model") in (selected or [])
              and any(sl in prs for sl in m.get("compare_to") or [])]
    cells: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    total = len(cts) * len(models)
    done = 0
    for c in cts:
        for m in models:
            if should_cancel and should_cancel():
                break
            brand, text = m.get("brand", "apple"), m["model"]
            if progress:
                progress(done, total, {"country": c["code"], "product": "competitor", "keyword": text, "status": "조회 중"})
            base = {"country": c["code"], "keyword": text, "keyword_type": "competitor", "brand": brand,
                    "position": None, "top_n": top_n, "first_store": None, "status": "unchecked", "attrs": {},
                    "attr_values": {}, "items_top": [], "detail_checked": False}
            try:
                res = provider.fetch_shopping(c, text)
                items = res.get("items") or []
                ours_fn = lambda it, _b=brand: is_brand_store(_b, it)
                j = judge_position(items, top_n, ours_fn)
                base.update(position=j["position"], first_store=j["first_store"], status=j["status"],
                            fetched_at=res.get("fetched_at"),
                            items_top=[{k2: it.get(k2) for k2 in ("position", "title", "merchant", "price", "link")} for it in items[:top_n]])
                ours = [it for it in items if ours_fn(it) and not _is_accessory_title(it.get("title"))]
                if ours:
                    best = min(ours, key=lambda it: it["position"])
                    base["our_item"] = {k2: best.get(k2) for k2 in ("position", "title", "merchant", "price", "link")}
                    _tr = trace_attributes(best, {}, attributes, detail_checked=False)
                    base["attrs"], base["attr_values"] = _tr["attrs"], _tr["attr_values"]
                    if detail:
                        try:
                            d = provider.fetch_product_detail(c, best, brand=brand)
                            if d:
                                _tr = trace_attributes(best, d, attributes, detail_checked=True)
                                base["attrs"], base["attr_values"] = _tr["attrs"], _tr["attr_values"]
                                base["detail_checked"] = True
                        except TypeError:   # 구 provider(mock) 호환
                            d = provider.fetch_product_detail(c, best)
                        except Exception as de:
                            base["detail_error"] = str(de)[:200]
            except Exception as e:
                base["status"] = "error"; base["error"] = str(e)[:200]
                errors.append({"country": c["code"], "product": "competitor", "keyword": text, "error": str(e)[:200]})
            for sl in m.get("compare_to") or []:
                if sl in prs:
                    cells.append({**base, "product": sl})
            done += 1
            if progress:
                progress(done, total, {"country": c["code"], "product": "competitor", "keyword": text, "status": base["status"]})
    return {"cells": cells, "errors": errors}
