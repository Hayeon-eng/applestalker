

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
from urllib.parse import urljoin

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

        self.browser_page_cap = int(os.getenv("BROWSER_PAGE_CAP", "12"))
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
        # [FIX] requires_js=True라고 무조건 JS를 태우지 않는다. 대신 requires_js는
        # '얼마나 엄격하게 비었다고 볼지'의 기준(strict)으로만 쓴다.
        # → httpx로 이미 충분한 페이지는 JS 예산을 아끼고, 실제로 빈약한 페이지에
        #   BROWSER_PAGE_CAP을 우선 배정한다 (URL 등장 순서에 좌우되지 않음).
        need_js = self._looks_empty(http_data, strict=requires_js)

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
    def _looks_empty(self, data: Optional[Dict], strict: bool = False) -> bool:
        """
        [FIX] strict=True(=사이트가 requires_js)일 때는 '비어있다'의 기준을 높여
        httpx만으로 이미 충분한 페이지까지 무조건 Playwright로 재렌더링하지 않게 한다.
        기존엔 requires_js=True인 사이트(Samsung/Apple)는 이 함수 결과와 무관하게
        crawl()에서 항상 need_js=True로 강제해, 페이지 내용과 상관없이
        BROWSER_PAGE_CAP를 URL 등장 순서대로 소모해버렸다.
        """
        if not data or data.get("error"):
            return True
        min_len = 900 if strict else 400
        return (
            len(data.get("body_content") or "") < min_len
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
                data = self._extract(soup, url)

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

                data = self._extract(soup, url)
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
    def _extract(self, soup: BeautifulSoup, page_url: str = "") -> Dict[str, Any]:
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
        d["images"] = self._images(soup, page_url)

        d["body_content"] = self._body_copy_text(soup)
        d["word_count"] = len(d["body_content"].split())
        return d

    def _body_copy_text(self, soup: BeautifulSoup) -> str:
        """반복 크롤 안정화를 위한 본문 카피 추출.

        기존 body 전체 텍스트는 헤더/푸터/메뉴/쿠키/추천 영역까지 포함해
        같은 페이지를 바로 다시 크롤해도 텍스트 순서와 항목 수가 흔들릴 수 있었다.
        CTA/내비/이미지/FAQ는 별도 필드로 이미 수집하므로, body_content는
        핵심 랜딩 카피 중심으로 정리해 저장한다.
        """
        root = soup.find("main") or soup.find("body")
        if not root:
            return ""

        # 원본 soup를 훼손하지 않도록 복제한 뒤 노이즈 영역 제거
        clean = BeautifulSoup(str(root), "lxml")
        noisy_tags = [
            "script", "style", "noscript", "svg", "path", "template", "iframe",
            "header", "footer", "nav", "form", "select", "option",
        ]
        for t in clean.find_all(noisy_tags):
            t.decompose()

        noisy_re = re.compile(
            r"(cookie|consent|privacy|legal|footer|header|nav|menu|gnb|breadcrumb|"
            r"modal|popup|overlay|drawer|tooltip|pagination|carousel-control|"
            r"recommend|related|recently|compare|support|search|login|account|"
            r"쿠키|동의|개인정보|약관|푸터|헤더|메뉴|내비|모달|팝업|추천|관련|검색|로그인)",
            re.IGNORECASE,
        )
        for el in list(clean.find_all(True)):
            # [FIX] 이 루프는 find_all(True)로 전체 태그를 미리 리스트로 뽑아둔 뒤
            # 돌면서 중간중간 decompose()를 호출한다. bs4는 부모를 decompose()하면
            # 그 자식들의 .attrs를 전부 None으로 만들어버리는데, 자식이 이미 이 리스트에
            # 담겨 있으면 뒤늦게 처리되면서 el.get(...) 호출 시
            # "AttributeError: 'NoneType' object has no attribute 'get'"로 죽는다.
            # → 상위 요소가 먼저 decompose되어 이미 죽은(고아가 된) 요소는 건너뛴다.
            if el.attrs is None:
                continue
            cls = el.get("class") or []
            cls_txt = " ".join(str(x) for x in cls) if isinstance(cls, list) else str(cls or "")
            attrs = " ".join([
                str(el.get("id") or ""),
                cls_txt,
                str(el.get("role") or ""),
                str(el.get("aria-label") or ""),
            ])
            style = str(el.get("style") or "").replace(" ", "").lower()
            if el.get("aria-hidden") == "true" or "display:none" in style or noisy_re.search(attrs):
                el.decompose()

        pieces: List[str] = []
        campaign_re = re.compile(
            r"(sale|offer|deal|save|new|launch|pre[- ]?order|buy|shop|promo|"
            r"할인|혜택|출시|사전예약|구매|프로모션|신제품|이벤트)",
            re.IGNORECASE,
        )
        for el in clean.find_all(["h1", "h2", "h3", "h4", "p", "li", "figcaption", "blockquote"]):
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
            if not txt:
                continue
            if len(txt) < 18 and not campaign_re.search(txt):
                continue
            pieces.append(txt)

        if not pieces:
            text = clean.get_text(" ", strip=True)
            return re.sub(r"\s+", " ", text).strip()[:120000]

        seen = set()
        out: List[str] = []
        for txt in pieces:
            key = txt.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(txt)
            if len(out) >= 260:
                break
        return " ".join(out)[:120000]

    # ─────────────────────────────────────────────
    # CTA / FAQ / JSONLD / NAV / LINKS / IMAGES
    # ─────────────────────────────────────────────
    def _ctas(self, soup):
        # Buying hard URL이 없는 글로벌 사이트도 있으므로, PDP/PF 내부의 구매 CTA를 근거로 남긴다.
        # 버튼 텍스트뿐 아니라 aria-label/title도 같이 보며, 이후 COPY 분석에서 Buy CTA 보유 여부를 판단한다.
        kw = (
            "buy", "shop", "purchase", "order", "add to cart", "add to bag",
            "checkout", "where to buy", "pre-order", "preorder", "learn more",
            "구매", "예약", "장바구니",
        )
        out = []
        seen = set()
        for a in soup.find_all(["a", "button"]):
            txt_bits = [a.get_text(" ", strip=True), a.get("aria-label", ""), a.get("title", "")]
            t = re.sub(r"\s+", " ", " ".join(str(x or "") for x in txt_bits)).strip()
            low = t.lower()
            href = a.get("href", "") or a.get("data-href", "") or ""
            if t and any(k in low for k in kw):
                key = (t.lower(), href)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"text": t[:160], "href": href})
        return out[:40]

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

    def _img_attr(self, tag, *names):
        for name in names:
            v = tag.get(name)
            if isinstance(v, list):
                v = " ".join(str(x) for x in v)
            if v:
                v = str(v).strip()
                if v:
                    return v
        return ""

    def _src_from_srcset(self, srcset: str) -> str:
        if not srcset:
            return ""
        candidates = []
        for part in str(srcset).split(","):
            chunk = part.strip()
            if not chunk:
                continue
            bits = chunk.split()
            url = bits[0].strip() if bits else ""
            if not url:
                continue
            score = 1.0
            if len(bits) > 1:
                m = re.search(r"([0-9.]+)(x|w)$", bits[1])
                if m:
                    try:
                        score = float(m.group(1))
                    except Exception:
                        score = 1.0
            candidates.append((score, url))
        if not candidates:
            return ""
        return sorted(candidates, key=lambda x: x[0], reverse=True)[0][1]

    def _normalize_img_url(self, src: str, page_url: str = "") -> str:
        src = (src or "").strip()
        if not src:
            return ""
        if src.startswith("data:"):
            return ""
        if src.startswith("//"):
            return "https:" + src
        if page_url and not re.match(r"^[a-z]+://", src, re.I):
            try:
                return urljoin(page_url, src)
            except Exception:
                return src
        return src

    def _image_context(self, tag) -> Dict[str, str]:
        parent = tag.find_parent(["picture", "figure", "section", "article", "a", "div"])
        context_text = ""
        parent_class = ""
        parent_id = ""
        if parent:
            context_text = parent.get_text(" ", strip=True)[:240]
            pc = parent.get("class") or []
            parent_class = " ".join(str(x) for x in pc) if isinstance(pc, list) else str(pc or "")
            parent_id = str(parent.get("id") or "")
        cls = tag.get("class") or []
        tag_class = " ".join(str(x) for x in cls) if isinstance(cls, list) else str(cls or "")
        return {
            "title": self._img_attr(tag, "title", "aria-label"),
            "class": tag_class,
            "id": str(tag.get("id") or ""),
            "parent_class": parent_class,
            "parent_id": parent_id,
            "context": context_text,
        }

    def _images(self, soup, page_url: str = ""):
        """이미지 추출. 기존 src/alt는 유지하면서 Samsung lazy-load/srcset/picture 구조를 보강한다."""
        out = []
        seen = set()

        def add_image(tag, source_type: str = "img"):
            raw_src = self._img_attr(
                tag,
                "src", "data-src", "data-original", "data-lazy", "data-url", "data-image",
                "data-desktop-src", "data-mobile-src", "data-src-desktop", "data-src-mobile",
                "data-img-src", "data-media-desktop", "data-media-mobile", "data-lazy-src",
            )
            srcset = self._img_attr(tag, "srcset", "data-srcset", "data-desktop-srcset", "data-mobile-srcset")
            if not raw_src and srcset:
                raw_src = self._src_from_srcset(srcset)

            src = self._normalize_img_url(raw_src, page_url)
            alt = self._img_attr(tag, "alt", "title", "aria-label")
            if not src and not alt and not srcset:
                return

            ctx = self._image_context(tag)
            key = src or f"{alt}|{ctx.get('context','')[:60]}|{source_type}"
            if key in seen:
                return
            seen.add(key)

            item = {"src": src, "alt": alt}
            if srcset:
                item["srcset"] = srcset[:1000]
            for k, v in ctx.items():
                if v:
                    item[k] = v
            item["source_type"] = source_type
            out.append(item)

        for i in soup.find_all("img"):
            add_image(i, "img")
            if len(out) >= 50:
                return out[:50]

        # Samsung/Apple 모두 <picture><source srcset=...>에 실제 이미지가 있는 경우가 있어 보조 추출
        for source in soup.find_all("source"):
            add_image(source, "source")
            if len(out) >= 50:
                break

        return out[:50]

