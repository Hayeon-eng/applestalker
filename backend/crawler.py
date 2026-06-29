"""
Hybrid Crawler — httpx 우선 / Playwright 폴백 (Render 512MB 안전)
================================================================
요구사항 2 구현 + Render Free(512MB RAM, 디스크 휘발) 제약 반영.

핵심 설계:
  1) 기본 경로는 httpx (가볍고 빠름). JS 가 꼭 필요한 경우만 Playwright.
  2) "JS 필요" 판정:
       - registry 의 ExtractionRule.requires_js == True 이거나
       - httpx 결과가 비어있음(본문 빈약/JSON-LD 0개/타이틀 없음)일 때만 승격
  3) Playwright 는 브라우저 1개를 재사용하고, context 는 URL마다 열고 닫음.
     동시 실행을 제한(max_concurrent_browser=1)해 메모리 폭주 방지.
  4) 스크린샷은 디스크에 저장하지 않는다. 바이트만 받아 perceptual hash 만 보관.
     (요구사항: 이미지 영구저장 포기, 변화 감지용 지문만)
  5) 모든 단계 try/except — 한 URL 실패가 전체를 멈추지 않음.

반환 page dict 키:
  url, status_code, error, html_content, title, meta_description, canonical_url,
  h1, h2[], h3[], body_content, ctas[], faqs[], structured_data[], navigation{},
  internal_links[], images[], word_count, load_time_ms,
  screenshot_phash (Playwright 경로에서만 채워짐), rendered_by ('httpx'|'playwright')
"""

from __future__ import annotations
import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup


_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class HybridCrawler:
    def __init__(
        self,
        user_agent: Optional[str] = None,
        http_timeout: float = 25.0,
        js_timeout_ms: int = 30000,
        enable_playwright: Optional[bool] = None,
        enable_screenshot: Optional[bool] = None,
        max_http_concurrent: int = 4,
    ):
        self.user_agent = user_agent or _DEFAULT_UA
        self.http_timeout = http_timeout
        self.js_timeout_ms = js_timeout_ms
        # 환경변수로 제어 (Render 메모리 빠듯하면 USE_PLAYWRIGHT=false 로 끄기)
        self.enable_playwright = (
            enable_playwright
            if enable_playwright is not None
            else os.getenv("USE_PLAYWRIGHT", "true").lower() == "true"
        )
        self.enable_screenshot = (
            enable_screenshot
            if enable_screenshot is not None
            else os.getenv("ENABLE_SCREENSHOT", "true").lower() == "true"
        )
        self._client: Optional[httpx.AsyncClient] = None
        self._browser = None
        self._pw = None
        self._http_sem = asyncio.Semaphore(max_http_concurrent)
        self._browser_sem = asyncio.Semaphore(1)   # 브라우저는 직렬화 (메모리 보호)
        self._browser_lock = asyncio.Lock()

    async def start(self):
        self._client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent,
                     "Accept-Language": "en-US,en;q=0.9"},
            timeout=httpx.Timeout(self.http_timeout, connect=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
        # 브라우저는 lazy 시작 (필요할 때만) — 콜드스타트/메모리 절약

    async def _ensure_browser(self):
        if not self.enable_playwright:
            return None
        if self._browser is not None:
            return self._browser
        async with self._browser_lock:
            if self._browser is not None:
                return self._browser
            try:
                from playwright.async_api import async_playwright
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox",
                          "--disable-dev-shm-usage", "--disable-gpu",
                          "--single-process", "--no-zygote",
                          "--disable-extensions", "--disable-background-networking"],
                )
            except Exception as e:
                print(f"[crawler] Playwright launch failed → httpx-only: {e}")
                self._browser = None
        return self._browser

    async def close(self):
        try:
            if self._client:
                await self._client.aclose()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self._browser = self._pw = None

    # ── 단일 페이지 ──────────────────────────────────────────

    async def crawl(self, url: str, requires_js: bool = False) -> Dict[str, Any]:
        t0 = datetime.now()
        result: Dict[str, Any] = {
            "url": url, "status_code": 0, "error": None,
            "html_content": None, "screenshot_phash": None, "rendered_by": None,
        }

        # 1) httpx 시도 (requires_js 가 아니면)
        http_data = None
        if not requires_js:
            http_data = await self._fetch_http(url)
            if http_data and not http_data.get("error"):
                result.update(http_data)
                result["rendered_by"] = "httpx"

        # 2) 승격 판정: requires_js 이거나, httpx 결과가 빈약하면 Playwright
        need_js = requires_js or self._looks_empty(http_data)
        if need_js and self.enable_playwright:
            pw_data = await self._fetch_playwright(url)
            if pw_data and not pw_data.get("error"):
                result.update(pw_data)
                result["rendered_by"] = "playwright"
            elif http_data and not http_data.get("error"):
                # Playwright 실패했지만 httpx 결과라도 있으면 그걸 사용
                result.update(http_data)
                result["rendered_by"] = "httpx-fallback"
            else:
                result["error"] = (pw_data or {}).get("error") or "render failed"

        if result.get("html_content") is None and http_data and not http_data.get("error"):
            result.update(http_data)
            result["rendered_by"] = result.get("rendered_by") or "httpx"

        if result.get("html_content") is None and result.get("error") is None:
            result["error"] = "empty result"

        result["load_time_ms"] = int((datetime.now() - t0).total_seconds() * 1000)
        return result

    def _looks_empty(self, data: Optional[Dict]) -> bool:
        if not data or data.get("error"):
            return True
        body = data.get("body_content") or ""
        # 본문이 매우 짧고 JSON-LD 도 없으면 JS 렌더 필요로 판단
        return (len(body) < 400 and not (data.get("structured_data")) ) or not data.get("title")

    # ── httpx ────────────────────────────────────────────────

    async def _fetch_http(self, url: str) -> Dict[str, Any]:
        async with self._http_sem:
            try:
                r = await self._client.get(url)
                html = r.text
                data = self._extract(BeautifulSoup(html, "lxml"), html)
                data["html_content"] = html
                data["status_code"] = r.status_code
                data["error"] = None if r.status_code < 400 else f"HTTP {r.status_code}"
                return data
            except Exception as e:
                return {"error": str(e), "status_code": 0}

    # ── Playwright ────────────────────────────────────────────

    async def _fetch_playwright(self, url: str) -> Dict[str, Any]:
        browser = await self._ensure_browser()
        if browser is None:
            return {"error": "playwright unavailable"}
        async with self._browser_sem:               # 브라우저 직렬화
            context = page = None
            try:
                context = await browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=self.user_agent,
                )
                page = await context.new_page()
                # 메모리/속도: 이미지·폰트·미디어 차단 (스크린샷 켜면 이미지는 허용)
                if not self.enable_screenshot:
                    await page.route(
                        re.compile(r".*\.(png|jpg|jpeg|webp|gif|svg|woff2?|mp4|webm)$"),
                        lambda route: asyncio.create_task(route.abort()),
                    )
                resp = await page.goto(url, wait_until="domcontentloaded",
                                       timeout=self.js_timeout_ms)
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    await page.wait_for_timeout(2500)

                data: Dict[str, Any] = {"status_code": resp.status if resp else 200,
                                        "error": None}

                # 스크린샷 → bytes → perceptual hash (디스크 저장 안 함)
                if self.enable_screenshot:
                    try:
                        png = await page.screenshot(full_page=False, type="png")
                        from diff_engine import average_hash, thumbnail_b64
                        data["screenshot_phash"] = average_hash(png)
                        data["screenshot_thumb"] = thumbnail_b64(png)  # 비교샷용 초소형
                        data["_screenshot_bytes"] = png   # 일회성 다운로드용 (DB 저장 X)
                    except Exception as e:
                        print(f"[crawler] screenshot failed {url}: {e}")

                html = await page.content()
                data.update(self._extract(BeautifulSoup(html, "lxml"), html))
                data["html_content"] = html
                return data
            except Exception as e:
                return {"error": str(e), "status_code": 0}
            finally:
                try:
                    if context:
                        await context.close()       # context 마다 닫아 메모리 회수
                except Exception:
                    pass

    # ── 추출 (httpx/playwright 공용) ──────────────────────────

    def _extract(self, soup: BeautifulSoup, html: str) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        title = soup.find("title")
        d["title"] = title.get_text(strip=True) if title else None

        md = soup.find("meta", attrs={"name": "description"})
        d["meta_description"] = (md.get("content") or "").strip() if md else None

        canon = soup.find("link", attrs={"rel": "canonical"})
        d["canonical_url"] = canon.get("href") if canon else None

        h1 = soup.find("h1")
        d["h1"] = h1.get_text(strip=True) if h1 else None
        d["h2"] = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)][:50]
        d["h3"] = [h.get_text(strip=True) for h in soup.find_all("h3") if h.get_text(strip=True)][:80]

        # ⚠️ 본문 정리(script decompose) 보다 먼저 JSON-LD/FAQ/CTA/nav/img 를 추출한다.
        #    안 그러면 <script type=ld+json> 이 지워져서 스키마가 사라진다.
        d["ctas"] = self._ctas(soup)
        d["faqs"] = self._faqs(soup)
        d["structured_data"] = self._jsonld(soup)
        d["navigation"] = self._nav(soup)
        d["internal_links"] = self._links(soup)
        d["images"] = self._images(soup)

        body = soup.find("body")
        if body:
            for tag in body(["script", "style", "noscript"]):
                tag.decompose()
            d["body_content"] = body.get_text(separator="\n", strip=True)[:120000]
        else:
            d["body_content"] = ""
        d["word_count"] = len(d["body_content"].split())
        return d

    def _ctas(self, soup) -> List[Dict[str, str]]:
        kw = ("buy", "shop", "purchase", "order", "pre-order", "learn more",
              "explore", "get started", "구매", "사전예약", "담기")
        out, seen = [], set()
        for el in soup.find_all(["button", "a"]):
            t = el.get_text(strip=True)
            tl = t.lower()
            if t and t not in seen and any(k in tl for k in kw):
                seen.add(t)
                out.append({"text": t, "href": el.get("href", ""),
                            "type": el.name})
        return out[:30]

    def _faqs(self, soup) -> List[Dict[str, str]]:
        out = []
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(s.string or "{}")
            except Exception:
                continue
            blocks = data if isinstance(data, list) else [data]
            for blk in blocks:
                if not isinstance(blk, dict):
                    continue
                graphs = blk.get("@graph", [blk]) if isinstance(blk.get("@graph"), list) else [blk]
                for g in graphs:
                    if isinstance(g, dict) and g.get("@type") == "FAQPage":
                        for q in g.get("mainEntity", []) or []:
                            if isinstance(q, dict) and q.get("@type") == "Question":
                                out.append({
                                    "question": q.get("name", ""),
                                    "answer": (q.get("acceptedAnswer", {}) or {}).get("text", ""),
                                    "source": "schema"})
        return out[:30]

    def _jsonld(self, soup) -> List[Any]:
        out = []
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                out.append(json.loads(s.string or "null"))
            except Exception:
                continue
        return [x for x in out if x is not None]

    def _nav(self, soup) -> Dict[str, List[Dict[str, str]]]:
        nav = {"main": [], "footer": []}
        n = soup.find("nav")
        if n:
            for a in n.find_all("a", href=True):
                nav["main"].append({"text": a.get_text(strip=True), "href": a["href"]})
        f = soup.find("footer")
        if f:
            for a in f.find_all("a", href=True):
                nav["footer"].append({"text": a.get_text(strip=True), "href": a["href"]})
        return nav

    def _links(self, soup) -> List[Dict[str, str]]:
        out, seen = [], set()
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if h and h not in seen and not h.startswith(("javascript:", "mailto:", "#", "tel:")):
                seen.add(h)
                out.append({"text": a.get_text(strip=True), "href": h})
        return out[:120]

    def _images(self, soup) -> List[Dict[str, str]]:
        return [{"src": i.get("src", "") or i.get("data-src", ""),
                 "alt": i.get("alt", "")}
                for i in soup.find_all("img")[:60]]
