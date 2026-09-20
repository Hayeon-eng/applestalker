"""
static_qa.py — 큐비 · 스태틱(캠페인/공통) 페이지 Schema 라이트 검수 [2026-09 신규]

대상: 91개 사이트코드(sitecodes_master.json ← Sitecode_Master_91.csv) × 7종 공통 페이지
  home · all-about-galaxy(/mobile/) · switch-to-galaxy · galaxy-ai · samsung-health · one-ui · find-your-galaxy
목적: 플래그십 PDP 처럼 상세 룰(Word 세트) 대조는 하지 않고, **매일** 아래 "전형적 오류"만 본다
  (Z8_Schema_QA_Dashboard 의 상태 체계와 동일: 정상 / 파싱 실패 / 오적용 / 미해결 참조 / 페이지 없음 / 기타)
  ① 페이지 응답: HTTP 상태, soft-404(안내 페이지) → '페이지 없음'
  ② JSON-LD 블록 수 · 블록별 파싱 실패(잘못된 escape / 제어문자 / 괄호 불일치 / 쉼표 누락 / 스마트 따옴표) → '파싱 실패'
  ③ 오적용: @id / url 에 **다른 국가**의 사이트코드 경로가 섞임(예: /de/ 페이지에 samsung.com/fr/ 참조).
     단, ca_fr↔ca·ch_fr↔ch 처럼 sitecodes_master.json 의 lang_variant_of 로 묶인 "같은 국가의 언어 변형"은 제외.
  ④ 미해결 참조: hasPart / mainEntity / isPartOf / about 이 가리키는 @id 가 페이지 안에 정의되어 있지 않음
  ⑤ 중복 @id: 같은 @id 를 가진 노드가 2개 이상
  ⑥ 스키마 O/X: 어떤 @type 이 있는지(WebPage·BreadcrumbList·Organization·FAQPage·VideoObject·Product·ItemList …)
  ⑦ Google 리치결과 필수 속성(전형적): Product(name,image) · VideoObject(name,thumbnailUrl,uploadDate) ·
     FAQPage(mainEntity[].name, acceptedAnswer.text) · BreadcrumbList(itemListElement[].name,position) · Organization(name,url)
URL 은 사이트별 경로 템플릿 후보를 순서대로 시도해(200 + 리다이렉트로 슬러그 유실 없음) 처음 성공한 것을 캐시한다.
"""
from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

_HERE = os.path.dirname(__file__)
MASTER_PATH = os.path.join(_HERE, "sitecodes_master.json")
URLCACHE_PATH = os.path.join(_HERE, "static_pages.resolved.json")

# 페이지 정의 — 경로 템플릿 후보(앞이 우선). 확정된 것: home, all-about-galaxy(/mobile/, 사용자 확인), switch-to-galaxy(/mobile/switch-to-galaxy/, collector 검증).
# 나머지는 관행 기반 후보이며 첫 실행에서 200 인 것을 캐시한다(없으면 '페이지 없음').
STATIC_PAGES: List[Dict[str, Any]] = [
    {"key": "home", "label": "Home", "paths": ["{base}"], "confirmed": True},
    {"key": "all-about-galaxy", "label": "All about Galaxy", "paths": ["{base}mobile/"], "confirmed": True},
    {"key": "switch-to-galaxy", "label": "Switch to Galaxy", "paths": ["{base}mobile/switch-to-galaxy/", "{base}smartphones/switch-to-galaxy/", "{base}switch-to-galaxy/"], "confirmed": True},
    {"key": "galaxy-ai", "label": "Galaxy AI", "paths": ["{base}galaxy-ai/", "{base}mobile/galaxy-ai/", "{base}smartphones/galaxy-ai/"], "confirmed": False},
    {"key": "samsung-health", "label": "Samsung Health", "paths": ["{base}apps/samsung-health/", "{base}samsung-health/", "{base}mobile/apps/samsung-health/"], "confirmed": False},
    {"key": "one-ui", "label": "One UI", "paths": ["{base}one-ui/", "{base}apps/one-ui/", "{base}mobile/one-ui/"], "confirmed": False},
    {"key": "find-your-galaxy", "label": "Find your Galaxy", "paths": ["{base}mobile/find-your-galaxy/"], "confirmed": True},  # 사용자 확인 2026-09-11 (/sg/mobile/find-your-galaxy/)
]
REF_PROPS = ("hasPart", "mainEntity", "mainEntityOfPage", "isPartOf", "about", "publisher", "brand", "manufacturer", "subjectOf", "breadcrumb")
RICH_REQUIRED: Dict[str, List[str]] = {
    "Product": ["name", "image"], "VideoObject": ["name", "thumbnailUrl", "uploadDate"],
    "Organization": ["name"], "BreadcrumbList": ["itemListElement"], "FAQPage": ["mainEntity"], "ItemList": ["itemListElement"],
}
STATUS_ORDER = ["정상", "파싱 실패", "오적용", "미해결 참조", "페이지 없음", "접근 실패", "기타"]


def load_sites() -> List[Dict[str, Any]]:
    return json.load(open(MASTER_PATH, encoding="utf-8"))["sites"]


def load_urlcache() -> Dict[str, str]:
    try:
        return json.load(open(URLCACHE_PATH, encoding="utf-8"))
    except Exception:
        return {}


def save_urlcache(c: Dict[str, str]):
    json.dump(c, open(URLCACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def candidate_urls(site: Dict[str, Any], page: Dict[str, Any]) -> List[str]:
    return [p.format(base=site["base_url"]) for p in page["paths"]]


# ── 판정 ────────────────────────────────────────────────────────────────
def _site_seg(url: str) -> str:
    p = urlparse(url)
    if p.netloc.endswith("samsung.com.cn"):
        return "cn"
    segs = [s for s in p.path.split("/") if s]
    return segs[0].lower() if segs else ""


_SITECODE_GROUP_CACHE: Dict[str, str] = {}


def _sitecode_group(code: str) -> str:
    """sitecode(소문자) → 같은 국가의 언어 변형을 하나로 묶는 그룹 키.
    sitecodes_master.json 의 lang_variant_of 를 사용(예: ca_fr·ca → 둘 다 'CA', ch_fr·ch → 둘 다 'CH').
    lang_variant_of 가 없는 사이트(언어 변형 없음)는 자기 자신의 대문자형을 그룹 키로 쓴다."""
    if not _SITECODE_GROUP_CACHE:
        try:
            for s in load_sites():
                sc_code = str(s.get("sitecode", "")).lower()
                if sc_code:
                    _SITECODE_GROUP_CACHE[sc_code] = s.get("lang_variant_of") or sc_code.upper()
        except Exception:
            pass
    return _SITECODE_GROUP_CACHE.get(code, code.upper())


def check_static_page(html: str, url: str, sitecode: str, http_status: Optional[int] = None,
                      soft404: Optional[str] = None) -> Dict[str, Any]:
    import schema_checker as sc
    out: Dict[str, Any] = {"url": url, "sitecode": sitecode, "http_status": http_status, "status": "정상",
                           "blocks": 0, "parse_errors": [], "types": [], "foreign_refs": [], "unresolved_refs": [],
                           "duplicate_ids": [], "rich_missing": [], "reasons": []}
    if http_status is None or http_status >= 400 or not html or soft404:
        # 404/soft-404 = 페이지 없음. 403/429/5xx/네트워크 오류 = 접근 실패(사이트 문제가 아니라 수집 환경 문제일 수 있음)
        if http_status == 404 or soft404:
            out["status"] = "페이지 없음"; out["reasons"].append(soft404 or "HTTP 404")
        else:
            out["status"] = "접근 실패"; out["reasons"].append(f"HTTP {http_status}" if http_status else "네트워크 오류 — 프록시/차단 확인")
        return out
    parse_errors: List[Dict[str, Any]] = []
    nodes = sc.extract_jsonld(html, parse_errors)
    out["blocks"] = len(re.findall(r'type\s*=\s*["\']application/ld\+json["\']', html, re.I))
    hard = [pe for pe in parse_errors if pe.get("severity", "fail") == "fail"]
    out["parse_errors"] = [{"block": pe.get("block_label"), "category": pe.get("category"), "msg": pe.get("msg"),
                            "line": pe.get("lineno"), "col": pe.get("colno"), "severity": pe.get("severity", "fail"), "hint": pe.get("hint")}
                           for pe in parse_errors]
    types = set()
    ids: Dict[str, int] = {}
    refs: List[tuple] = []
    all_urls: List[str] = []
    for n in nodes:
        for t in sc._types_of(n):
            types.add(t)
        nid = n.get("@id")
        if isinstance(nid, str):
            ids[nid] = ids.get(nid, 0) + 1; all_urls.append(nid)
        for p in REF_PROPS:
            v = n.get(p)
            for rid in sc._collect_ids(v) if v is not None else []:
                if isinstance(rid, str) and rid.startswith("http") and "#" in rid:
                    refs.append((p, rid))
        u = n.get("url")
        if isinstance(u, str):
            all_urls.append(u)
    out["types"] = sorted(types)
    out["duplicate_ids"] = sorted(k for k, c in ids.items() if c > 1)
    defined = set(ids.keys())
    # 같은 페이지 앵커(…/mobile/#faq)만 '정의되어야 하는' 참조로 본다. 사이트 공통 노드(/{sc}/#org, /#brand-galaxy)는
    # 홈 등 다른 페이지에 정의되는 관행이라 여기서는 판정하지 않는다(외부 정의).
    page_base = url.split("#")[0].rstrip("/")
    out["unresolved_refs"] = sorted({f"{p} → {rid}" for p, rid in refs
                                      if rid not in defined and rid.split("#")[0].rstrip("/") == page_base})
    out["external_refs"] = sorted({rid for p, rid in refs if rid not in defined and rid.split("#")[0].rstrip("/") != page_base})[:20]
    my = sitecode.lower()
    my_group = _sitecode_group(my)
    for u in all_urls:
        seg = _site_seg(u)
        if seg and seg != my and "samsung.com" in u and seg not in ("global",):
            if _sitecode_group(seg) == my_group:
                continue  # 같은 국가의 언어 변형(예: ca_fr 페이지가 /ca/ 를 참조) — 오적용 아님
            if not (my in ("cn",) and seg == "cn"):
                out["foreign_refs"].append(u)
    out["foreign_refs"] = sorted(set(out["foreign_refs"]))[:20]
    # 리치결과 필수 속성(전형적)
    for n in nodes:
        for t in sc._types_of(n):
            req = RICH_REQUIRED.get(t)
            if not req:
                continue
            miss = [p for p in req if n.get(p) in (None, "", [], {})]
            if t == "FAQPage" and isinstance(n.get("mainEntity"), list):
                for q in n["mainEntity"]:
                    if isinstance(q, dict) and (not q.get("name") or not (q.get("acceptedAnswer") or {}).get("text")):
                        miss.append("mainEntity[].name/acceptedAnswer.text"); break
            if t == "BreadcrumbList" and isinstance(n.get("itemListElement"), list):
                for it in n["itemListElement"]:
                    if isinstance(it, dict) and (not it.get("name") or it.get("position") is None):
                        miss.append("itemListElement[].name/position"); break
            if miss:
                out["rich_missing"].append({"type": t, "id": n.get("@id"), "missing": sorted(set(miss))})
    # 상태(대시보드 체계): 파싱 실패 > 오적용 > 미해결 참조 > 기타(중복 @id·필수 누락) > 정상
    if hard:
        out["status"] = "파싱 실패"; out["reasons"].append(f"JSON-LD {out['blocks']}개 블록 중 {len(hard)}개 파싱 실패")
    elif out["foreign_refs"]:
        out["status"] = "오적용"; out["reasons"].append(f"타 사이트코드 참조 {len(out['foreign_refs'])}건")
    elif out["unresolved_refs"]:
        out["status"] = "미해결 참조"; out["reasons"].append(f"정의되지 않은 @id 참조 {len(out['unresolved_refs'])}건")
    elif out["duplicate_ids"] or out["rich_missing"]:
        out["status"] = "기타"
        if out["duplicate_ids"]:
            out["reasons"].append(f"중복 @id {len(out['duplicate_ids'])}건")
        if out["rich_missing"]:
            out["reasons"].append("리치결과 필수 속성 누락 " + ", ".join(f"{m['type']}({','.join(m['missing'])})" for m in out["rich_missing"][:3]))
    elif not nodes:
        out["status"] = "기타"; out["reasons"].append("JSON-LD 없음")
    else:
        out["reasons"].append("주요 오류 미검출")
    return out


# ── 실행(수집 포함) ──────────────────────────────────────────────────────
STATE: Dict[str, Any] = {"running": False, "done": 0, "total": 0, "run_id": None, "started": None, "cancel": False, "current": None, "recent": []}
LAST: Dict[str, Any] = {}


async def run_all(sites: Optional[List[Dict[str, Any]]] = None, pages: Optional[List[str]] = None, concurrency: int = 8) -> Dict[str, Any]:
    import asyncio, time
    from datetime import datetime
    import httpx
    sites = sites or [s for s in load_sites() if s["mode"] == "auto"]
    pdefs = [p for p in STATIC_PAGES if not pages or p["key"] in pages]
    cache = load_urlcache()
    run_id = f"static_{datetime.now():%Y%m%d_%H%M%S}"
    STATE.update(running=True, done=0, total=len(sites) * len(pdefs), run_id=run_id, started=time.time(), cancel=False, current=None, recent=[])
    sem = asyncio.Semaphore(concurrency)
    results: List[Dict[str, Any]] = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
               "Accept-Language": "en-US,en;q=0.9"}
    SOFT404 = re.compile(r"(is not available|page you requested|cannot be found|페이지를 찾을 수 없|ページが見つかりません|无法找到|nicht verf[üu]gbar|n'est pas disponible|no est[áa] disponible)", re.I)

    async def fetch(client: httpx.AsyncClient, url: str):
        try:
            r = await client.get(url, follow_redirects=True)
            return r
        except Exception as e:
            return e

    async def one(site: Dict[str, Any], page: Dict[str, Any]):
        async with sem:
            if STATE.get("cancel"):  # 멈춤 — 남은 페이지 건너뜀
                STATE["done"] += 1; return
            STATE["current"] = f"{site['sitecode']} · {page['label']}"
            key = f"{site['sitecode']}|{page['key']}"
            cands = ([cache[key]] if key in cache else []) + [u for u in candidate_urls(site, page) if u != cache.get(key)]
            row = None
            async with httpx.AsyncClient(headers=headers, timeout=25, verify=(os.getenv("QB_SSL_VERIFY", "true").lower() != "false")) as client:
                for u in cands:
                    r = await fetch(client, u)
                    if isinstance(r, Exception):
                        row = check_static_page("", u, site["sitecode"], None, str(r)); continue
                    final = str(r.url)
                    slug_lost = page["key"] != "home" and urlparse(final).path.rstrip("/") != urlparse(u).path.rstrip("/") and \
                        page["key"].replace("-", "") not in urlparse(final).path.replace("-", "")
                    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", r.text, re.I | re.S)
                    soft = SOFT404.search(re.sub(r"<[^>]+>", " ", h1.group(1))) if h1 else None
                    title = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.S)
                    # [2026-09 FIX] home 페이지는 자기 자신의 정상 title 자체가 "Samsung | Samsung {국가}"처럼
                    # 브랜드명이 반복되는 형태라, 이 휴리스틱을 그대로 적용하면 정상 홈페이지가 전부
                    # soft-404(페이지 없음)로 오판된다 — slug_lost 와 동일하게 home 은 제외한다.
                    brand_only = page["key"] != "home" and bool(title and re.match(r"^\s*samsung\s*[|｜\-–]\s*samsung\b", title.group(1).strip().lower()))
                    if r.status_code == 200 and not slug_lost and not soft and not brand_only:
                        row = check_static_page(r.text, final, site["sitecode"], 200)
                        row["title"] = title.group(1).strip()[:120] if title else ""
                        cache[key] = u
                        break
                    row = check_static_page("", u, site["sitecode"], r.status_code,
                                            "soft 404(안내 페이지)" if (soft or brand_only) else ("리다이렉트로 슬러그 유실 → " + final if slug_lost else None))
            row.update(page=page["key"], page_label=page["label"], country=site["country"], subs=site["subs"], confirmed_path=page["confirmed"])
            results.append(row); STATE["done"] += 1
            STATE["recent"] = ([{"sitecode": site["sitecode"], "page": page["label"], "status": row["status"]}] + STATE["recent"])[:8]

    await asyncio.gather(*(one(s, p) for s in sites for p in pdefs), return_exceptions=True)
    save_urlcache(cache)
    summary = {"sites": len(sites), "pages": len(pdefs), "checked": len(results),
               "by_status": {s: sum(1 for r in results if r["status"] == s) for s in STATUS_ORDER},
               "by_page": {p["key"]: {s: sum(1 for r in results if r["page"] == p["key"] and r["status"] == s) for s in STATUS_ORDER} for p in pdefs}}
    out = {"run_id": run_id, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": summary, "results": results,
           "duration_seconds": round(time.time() - STATE["started"], 1), "cancelled": bool(STATE.get("cancel"))}
    LAST.clear(); LAST.update(out)
    STATE.update(running=False)
    return out
