

"""
Hybrid Crawler — FULL RESTORED (AEO + 403 bypass + Render-safe)
================================================================
✔ AEO extraction 100% 유지 (JSON-LD / FAQ / CTA / NAV / LINKS / IMAGES)
✔ HTTPX 우선 + Playwright fallback
✔ 403 / 429 대응 headers 강화
✔ Render 512MB safe 구조 유지
[FIX] requires_js=True여도 HTTP 항상 먼저 시도 → Playwright는 선택적 업그레이드
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


# ─────────────────────────────────────────────
# 🔥 403 BYPASS HEADERS
# ─────────────────────────────────────────────
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8,en-US;q=0.7",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
}


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
        self.user_agent = user_agent or _UA
        self.http_timeout = http_timeout
        self.js_timeout_ms = js_timeout_ms

        self.enable_playwright = (
            enable_playwright
            if enable_playwright is not None
            else os.getenv("USE_PLAYWRIGHT", "false").lower() == "true"
        )

        self.enable_screenshot = (
            enable_screenshot
            if enable_screenshot is not None
            else os.getenv("ENABLE_SCREENSHOT", "false").lower() == "true"
        )

        self.browser_page_cap = int(os.getenv("BROWSER_PAGE_CAP", "8"))
        self._browser_used = 0

        self._client: Optional[httpx.AsyncClient] = None
        self._browser = None
        self._pw = None

        self._http_sem = asyncio.Semaphore(max_http_concurrent)
        self._browser_sem = asyncio.Semaphore(1)
        self._browser_lock = asyncio.Lock()

    # ─────────────────────────────────────────────
    # START
    # ─────────────────────────────────────────────
    async def start(self):
        self._client = httpx.AsyncClient(
            headers=BASE_HEADERS,
            timeout=httpx.Timeout(self.http_timeout, connect=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

    # ─────────────────────────────────────────────
    # BROWSER INIT
    # ─────────────────────────────────────────────
    async def _ensure_browser(self):
        if not self.enable_playwright:
            return None
        if self._browser:
            return self._browser

        async with self._browser_lock:
            if self._browser:
                return self._browser

            try:
                from playwright.async_api import async_playwright

                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--single-process",
                        "--no-zygote",
                    ],
                )
            except Exception as e:
                print(f"[crawler] playwright failed: {e}")
                self._browser = None

        return self._browser

    # ─────────────────────────────────────────────
    # CLOSE
    # ─────────────────────────────────────────────
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

    # ─────────────────────────────────────────────
    # MAIN CRAWL
    # ─────────────────────────────────────────────
    async def crawl(self, url: str, requires_js: bool = False) -> Dict[str, Any]:
        t0 = datetime.now()

        result: Dict[str, Any] = {
            "url": url,
            "status_code": 0,
            "error": None,
            "html_content": None,
            "rendered_by": None,
            "screenshot_phash": None,
        }

        # ✅ [FIX] HTTP는 requires_js 무관하게 항상 먼저 시도
        # 기존: if not requires_js → Samsung/Apple(requires_js=True)에서 HTTP 완전 건너뜀
        #       + USE_PLAYWRIGHT=false(기본) → Playwright도 건너뜀 → "empty result" 100%
        http_data = await self._fetch_http(url)
        if http_data and not http_data.get("error"):
            result.update(http_data)
            result["rendered_by"] = "httpx"

        # Playwright 업그레이드 조건:
        # requires_js=True 이거나 HTTP 결과가 빈 경우 AND Playwright 활성화된 경우만
        need_js = requires_js or self._looks_empty(http_data)

        if need_js and self.enable_playwright and self._browser_used < self.browser_page_cap:
            self._browser_used += 1

            pw = await self._fetch_playwright(url)

            if pw and not pw.get("error"):
                result.update(pw)
                result["rendered_by"] = "playwright"
            # playwright 실패해도 http_data 결과는 result에 이미 반영됨 (위에서 update)

        # HTTP 결과라도 있으면 최종 fallback
        if result.get("html_content") is None and http_data:
            result.update(http_data)

        if result.get("html_content") is None and not result.get("error"):
            result["error"] = "empty result"

        result["load_time_ms"] = int((datetime.now() - t0).total_seconds() * 1000)
        return result

    # ─────────────────────────────────────────────
    # EMPTY CHECK
    # ─────────────────────────────────────────────
    def _looks_empty(self, data: Optional[Dict]) -> bool:
        if not data or data.get("error"):
            return True
        return (
            len(data.get("body_content") or "") < 400
            or not data.get("title")
        )

    # ─────────────────────────────────────────────
    # HTTP FETCH (403 FIXED)
    # ─────────────────────────────────────────────
    async def _fetch_http(self, url: str) -> Dict[str, Any]:
        async with self._http_sem:
            try:
                headers = dict(BASE_HEADERS)
                headers["Referer"] = "https://www.google.com/"

                r = await self._client.get(url, headers=headers)

                if r.status_code in (403, 401, 429):
                    return {
                        "error": f"blocked {r.status_code}",
                        "status_code": r.status_code,
                        "html_content": None,
                    }

                soup = BeautifulSoup(r.text or "", "lxml")
                data = self._extract(soup)

                data["html_content"] = r.text
                data["status_code"] = r.status_code
                return data

            except Exception as e:
                return {"error": str(e), "status_code": 0}

    # ─────────────────────────────────────────────
    # PLAYWRIGHT
    # ─────────────────────────────────────────────
    async def _fetch_playwright(self, url: str) -> Dict[str, Any]:
        browser = await self._ensure_browser()
        if not browser:
            return {"error": "playwright unavailable"}

        async with self._browser_sem:
            context = page = None
            try:
                context = await browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=self.user_agent,
                    locale="ko-KR",
                )

                page = await context.new_page()

                # stealth
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                """)

                await page.goto(url, wait_until="domcontentloaded", timeout=self.js_timeout_ms)

                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    await page.wait_for_timeout(2000)

                html = await page.content()
                soup = BeautifulSoup(html, "lxml")

                data = self._extract(soup)
                data["html_content"] = html
                data["status_code"] = 200

                return data

            except Exception as e:
                return {"error": str(e), "status_code": 0}

            finally:
                if context:
                    await context.close()

    # ─────────────────────────────────────────────
    # AEO EXTRACTION (FULL RESTORED)
    # ─────────────────────────────────────────────
    def _extract(self, soup: BeautifulSoup) -> Dict[str, Any]:
        d: Dict[str, Any] = {}

        d["title"] = soup.title.get_text(strip=True) if soup.title else None

        md = soup.find("meta", attrs={"name": "description"})
        d["meta_description"] = md.get("content") if md else None

        canon = soup.find("link", rel="canonical")
        d["canonical_url"] = canon.get("href") if canon else None

        h1 = soup.find("h1")
        d["h1"] = h1.get_text(strip=True) if h1 else None

        d["h2"] = [h.get_text(strip=True) for h in soup.find_all("h2")][:50]
        d["h3"] = [h.get_text(strip=True) for h in soup.find_all("h3")][:80]

        d["ctas"] = self._ctas(soup)
        d["faqs"] = self._faqs(soup)
        d["structured_data"] = self._jsonld(soup)
        d["navigation"] = self._nav(soup)
        d["internal_links"] = self._links(soup)
        d["images"] = self._images(soup)

        body = soup.find("body")
        if body:
            for t in body(["script", "style", "noscript"]):
                t.decompose()
            d["body_content"] = body.get_text(" ", strip=True)[:120000]
        else:
            d["body_content"] = ""

        d["word_count"] = len(d["body_content"].split())
        return d

    # ─────────────────────────────────────────────
    # CTA / FAQ / JSONLD / NAV / LINKS / IMAGES
    # ─────────────────────────────────────────────
    def _ctas(self, soup):
        kw = ("buy", "shop", "purchase", "order", "learn more", "구매", "예약")
        out = []
        for a in soup.find_all(["a", "button"]):
            t = a.get_text(strip=True)
            if t and any(k in t.lower() for k in kw):
                out.append({"text": t, "href": a.get("href", "")})
        return out[:30]

    def _faqs(self, soup):
        out = []
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(s.string or "{}")
                if isinstance(data, dict) and data.get("@type") == "FAQPage":
                    out.append(data)
            except:
                pass
        return out[:30]

    def _jsonld(self, soup):
        out = []
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                out.append(json.loads(s.string or "null"))
            except:
                pass
        return out

    def _nav(self, soup):
        return {
            "main": [{"text": a.get_text(strip=True), "href": a.get("href")}
                     for a in soup.find_all("nav")[:1]],
            "footer": [],
        }

    def _links(self, soup):
        return [{"href": a.get("href"), "text": a.get_text(strip=True)}
                for a in soup.find_all("a", href=True)][:100]

    def _images(self, soup):
        return [{"src": i.get("src"), "alt": i.get("alt")}
                for i in soup.find_all("img")][:50]

