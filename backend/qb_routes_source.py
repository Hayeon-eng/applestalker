"""
qb_routes_source.py — 소스(HTML) 기반 검수 [2026-09 신규]  POST /api/qb/run-source

사용자가 제공한 페이지 소스(브라우저 '다른 이름으로 저장' HTML, 또는 collect_sources.py 가 만든
zip)를 입력으로 받아, 크롤러(httpx/Playwright) 없이 runner.run_site 만 실행한다.
결과 구조·이력 저장·엑셀 리포트는 URL 크롤 검수(/run)와 완전히 동일하다.

입력
  · files: .html 여러 개, 또는 .zip 하나(안에 .html + 선택적으로 manifest.json)
  · manifest.json (선택): [{"file": "uk_galaxy-z-fold8_pdp.html", "url": "...", "sitecode": "uk",
                             "product": "galaxy-z-fold8", "page_type": "PDP", "http_status": 200}, ...]
  · manifest 가 없으면 HTML 의 <link rel=canonical> → og:url → 파일명 순으로 URL 을 추정하고,
    URL 에서 sitecode/product/page_type 을 판별한다(runner.product_from_url / page_type_from_url).
    레지스트리에 같은 URL 이 있으면 region/country/lang 을 채운다.
  · mode: all | data | spec  (기본 all)
  · rendered_by 표기: 소스 기반은 "source(user)" — Spec QA 진단(diagnosis.rendered_by)에서
    "httpx" 로 오인해 재렌더를 시도하지 않게 한다.

한계(정직하게 표기)
  · 소스가 서버 HTML(비렌더)이면 JS 로 채워지는 스펙 값은 Spec QA 에서 na 로 남는다.
    브라우저 저장본(렌더 DOM)을 넣으면 Playwright 렌더와 동등한 입력이 된다.
  · Status Code 는 manifest 에 있을 때만 기록(브라우저 저장본은 200 으로 간주하지 않고 빈칸).
"""
from __future__ import annotations
import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import File, Form, HTTPException, UploadFile

import runner
import qa_report
import seo_checker
import qb_core
from qb_core import qb_router, _registry
from qb_routes_history import _history_save

_CANON_RE = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', re.I)
_CANON_RE2 = re.compile(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', re.I)
_OG_RE = re.compile(r'<meta[^>]+property=["\']og:url["\'][^>]*content=["\']([^"\']+)["\']', re.I)


def infer_url(html: str, filename: str = "") -> str:
    for rx in (_CANON_RE, _CANON_RE2, _OG_RE):
        m = rx.search(html[:200000])
        if m:
            return m.group(1).strip()
    # 파일명 규약(collect_sources.py / capture_pdp_samples.py): <sitecode>_<slug>_<pagetype>.html
    m = re.match(r"([a-z]{2}(?:_[a-z]{2})?|cn|sec|latin_en|africa_[a-z]{2}|levant(?:_ar)?|n_africa|iran)_(.+?)_(pdp|compare|specs|buy)\.html?$",
                 os.path.basename(filename or ""), re.I)
    if m:
        sc, slug, pt = m.group(1).lower(), m.group(2).lower(), m.group(3).lower()
        host = "www.samsung.com.cn" if sc == "cn" else "www.samsung.com"
        path = f"/smartphones/{slug}/" if sc == "cn" else f"/{sc}/smartphones/{slug}/"
        tail = {"compare": "compare/", "specs": "specs/", "buy": "buy/"}.get(pt, "")
        return f"https://{host}{path}{tail}"
    return ""


def site_from_url(url: str) -> Dict[str, Any]:
    p = urlparse(url or "")
    host = (p.netloc or "").lower()
    segs = [s for s in (p.path or "").split("/") if s]
    sitecode = "cn" if host.endswith("samsung.com.cn") else (segs[0].lower() if segs else "")
    site = {"sitecode": sitecode, "url": url, "region": None, "country": None, "lang": None,
            "product": runner.product_from_url(url), "page_type": runner.page_type_from_url(url)}
    # 레지스트리에 같은 URL/사이트가 있으면 메타 보강
    hit = next((s for s in _registry.all() if s.get("url", "").rstrip("/") == url.rstrip("/")), None) \
        or _registry.get(sitecode)
    if hit:
        for k in ("region", "country", "lang"):
            site[k] = hit.get(k)
    return site


def _read_uploads(files: List[UploadFile]) -> (List[Dict[str, Any]], Dict[str, Dict[str, Any]]):
    """업로드 파일들 → [{"name", "html"}], manifest(by file name)."""
    docs, manifest = [], {}
    for f in files:
        raw = f.file.read()
        name = f.filename or "upload.html"
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for zi in z.infolist():
                    if zi.is_dir():
                        continue
                    base = os.path.basename(zi.filename)
                    if base.lower() == "manifest.json":
                        try:
                            for row in json.loads(z.read(zi).decode("utf-8", "ignore")):
                                if isinstance(row, dict) and row.get("file"):
                                    manifest[os.path.basename(row["file"])] = row
                        except Exception as e:
                            print(f"[run-source] manifest parse skip: {e}")
                    elif base.lower().endswith((".html", ".htm")):
                        docs.append({"name": base, "html": z.read(zi).decode("utf-8", "ignore")})
        elif name.lower() == "manifest.json":
            try:
                for row in json.loads(raw.decode("utf-8", "ignore")):
                    if isinstance(row, dict) and row.get("file"):
                        manifest[os.path.basename(row["file"])] = row
            except Exception as e:
                print(f"[run-source] manifest parse skip: {e}")
        elif name.lower().endswith((".html", ".htm")):
            docs.append({"name": os.path.basename(name), "html": raw.decode("utf-8", "ignore")})
    return docs, manifest


@qb_router.post("/run-source")
def qb_run_source(files: List[UploadFile] = File(...), mode: str = Form("all"),
                  product: str = Form("M3"), save_history: bool = Form(True)):
    mode = (mode or "all").lower()
    if mode not in ("all", "data", "spec"):
        raise HTTPException(400, f"알 수 없는 mode: {mode}")
    docs, manifest = _read_uploads(files)
    if not docs:
        raise HTTPException(400, "HTML 파일(.html) 또는 .zip 이 필요합니다.")

    rules_cache: Dict[str, Any] = {}
    results: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    for d in docs:
        m = manifest.get(d["name"], {})
        url = m.get("url") or infer_url(d["html"], d["name"])
        if not url:
            skipped.append({"file": d["name"], "reason": "URL 추정 실패 — manifest.json 에 url 을 적어 주세요"})
            continue
        site = site_from_url(url)
        for k in ("sitecode", "product", "page_type", "region", "country", "lang"):
            if m.get(k):
                site[k] = m[k]
        pt, mp = site["page_type"], site["product"]
        key = f"{pt}|{mp}"
        if key not in rules_cache:
            rules_cache[key] = runner.load_rules(product, page_type=pt, market_product=mp, url=url)
        row = runner.run_site(site, d["html"], rules_cache[key], page_type=pt,
                              rendered_by=m.get("rendered_by") or "source(user)", mode=mode,
                              http_status=m.get("http_status"), final_url=m.get("final_url") or url)
        row["source_file"] = d["name"]
        results.append(row)

    try:
        seo_checker.mark_duplicates(results)
    except Exception as e:
        print(f"[run-source] duplicate check skip: {e}")

    qb_core.LAST_RESULTS = results
    summary = qa_report.summary_counts(results)
    run_id = None
    if save_history and results:
        entry = _history_save(results, summary, product=product,
                              scope=f"소스 업로드 {len(results)}건" + ({"data": " · Data QA", "spec": " · Spec QA"}.get(mode, "")),
                              duration_seconds=0)
        run_id = entry.get("run_id")
    return {"status": "done", "run_id": run_id, "pages": len(results), "skipped": skipped,
            "summary": summary, "mode": mode,
            "pages_detail": [{"file": r.get("source_file"), "url": r.get("url"), "sitecode": r.get("sitecode"),
                              "product": r.get("product"), "page_type": r.get("page_type")} for r in results]}
