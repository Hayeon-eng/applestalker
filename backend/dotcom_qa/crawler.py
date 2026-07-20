

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
import sys
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
    # Global/US 경쟁사 페이지 기준선 안정성을 위해 영어 우선.
    # ko-KR 우선 사용 시 Meta처럼 국가/언어 리다이렉트가 강한 사이트가
    # 에러/unsupported 페이지로 떨어질 수 있다.
    "Accept-Language": "en-US,en;q=0.9,ko-KR;q=0.8,ko;q=0.7",
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

        # [JS_RESCUE] 전면 렌더(USE_PLAYWRIGHT)는 그대로 꺼둔 채, httpx가 '빈/차단'
        # 페이지를 받은 경우에 한해서만 Playwright로 그 페이지만 구제한다.
        # → 정상 페이지는 렌더하지 않아 전체 크롤 속도는 유지, Meta 같은 소수만 추가 비용.
        self.js_rescue = os.getenv("JS_RESCUE", "true").lower() == "true"
        self.js_rescue_cap = int(os.getenv("JS_RESCUE_CAP", "8"))
        self._rescue_used = 0
        # 렌더가 실제로 가능한지(전면 렌더 or 구제 중 하나라도 켜짐)
        self._pw_available = self.enable_playwright or self.js_rescue

        self.enable_screenshot = (
            enable_screenshot
            if enable_screenshot is not None
            else os.getenv("ENABLE_SCREENSHOT", "false").lower() == "true"
        )

        self.browser_page_cap = int(os.getenv("BROWSER_PAGE_CAP", "24"))
        self._browser_used = 0

        # [2026-07 속도 개선] 렌더 1건당 고정으로 붙던 두 대기가 병목의 절반 이상이었다.
        #   · networkidle 8초: 트래커/분석 스크립트가 있는 페이지는 거의 항상 8초를 꽉 채우고
        #     타임아웃 → "기다렸다는 사실"만 남고 대부분 실효가 없었다. 이미 domcontentloaded +
        #     동의창 클릭 뒤 대기 + 스크롤 단계가 이어지므로 3.5초로 줄여도 실수집 품질엔
        #     영향이 없었다(콘텐츠는 스크롤 단계에서 강제로 그려짐).
        #   · 스크롤 루프 최대 10초(40회×250ms): "추천상품" 캐러셀처럼 스크롤할 때마다 높이가
        #     계속 늘어나는 페이지는 조기 종료 조건에 절대 안 걸려 매번 10초를 다 썼다.
        #     반복 횟수 대신 총 시간 예산으로 바꿔 상한을 明확히 걸었다.
        # 필요하면 환경변수로 조정 가능 — 기본값은 속도만 개선하고 렌더 품질엔 영향 없도록 보수적으로 잡음.
        self.js_networkidle_ms = int(os.getenv("JS_NETWORKIDLE_MS", "3500"))
        self.js_scroll_budget_ms = int(os.getenv("JS_SCROLL_BUDGET_MS", "3000"))
        # [2026-07 속도 개선] Playwright 동시 렌더 수 — 기본 1은 Render 512MB 환경 안전을 위해
        # 그대로 유지(바꾸지 않음). 메모리 여유가 있는 환경에서만 BROWSER_CONCURRENCY로 올려서
        # 여러 페이지를 동시에 렌더하면 Compare처럼 항상 렌더가 필요한 배치가 크게 빨라진다 —
        # 다만 Chromium 컨텍스트 하나당 메모리를 꽤 쓰므로, 512MB 이하 환경에서는 절대 올리지 말 것.
        self._browser_concurrency = max(1, int(os.getenv("BROWSER_CONCURRENCY", "1")))
        # [2026-07-4 FIX] force_render()(Compare)는 browser_page_cap 대상이 아니므로,
        # 렌더가 많이 몰리는 실행에서 Chromium 메모리가 계속 누적되는 걸 막기 위해
        # 이 횟수마다 브라우저를 예방적으로 재기동한다. Render 512MB 기준 보수적으로 20.
        self._recycle_after_renders = max(1, int(os.getenv("BROWSER_RECYCLE_AFTER", "20")))
        # [2026-07-4 FIX] 브라우저가 "죽지는 않았지만(is_connected=true) 응답이 없는" 경우
        # (Render 512MB 스와핑 등)를 대비한 렌더 1건당 하드 데드라인. 개별 내부 timeout들의
        # 합보다 넉넉히 잡되(js_timeout_ms + networkidle + scroll + 여유), 무한 대기는 절대
        # 허용하지 않는다.
        self._render_hard_timeout_s = int(os.getenv("BROWSER_RENDER_HARD_TIMEOUT_S", "45"))

        self._client: Optional[httpx.AsyncClient] = None
        self._browser = None
        self._pw = None
        self._install_attempted = False  # [2026-07 신규] 런타임 자동설치 재시도 1회 제한용

        self._http_sem = asyncio.Semaphore(max_http_concurrent)
        self._browser_sem = asyncio.Semaphore(self._browser_concurrency)
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
    # [2026-07-4 FIX] 근본 원인: Render 512MB에서 Chromium(--single-process)이
    # 메모리 압박으로 죽어도(OOM) 이 함수는 "self._browser가 set돼 있으니 캐시된 걸
    # 재사용"이라고 판단해 이미 죽은 브라우저 참조를 그대로 반환해왔다. 그 뒤로는
    # new_context() 등 모든 호출이 "has been closed" 예외를 내거나 응답 없이 걸려
    # js_timeout_ms(30초)를 매 페이지마다 다 채우고 실패 — 배치 전체가 "로딩만 느려지다
    # 뻗는" 것처럼 보이던 현상의 핵심 원인이었다. is_connected()로 죽은 브라우저를
    # 감지해 재기동한다.
    async def _launch_chromium(self):
        from playwright.async_api import async_playwright
        if not self._pw:
            self._pw = await async_playwright().start()
        return await self._pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--single-process",
                "--no-zygote",
            ],
        )

    async def _ensure_browser(self):
        if not self._pw_available:
            return None
        if self._browser:
            if self._browser.is_connected():
                return self._browser
            # 죽은 브라우저 — 참조를 버리고 아래에서 재기동
            print("[crawler] chromium found disconnected (probably OOM-killed) — relaunching")
            try:
                if self._pw:
                    await self._pw.stop()
            except Exception:
                pass
            self._browser = None
            self._pw = None

        async with self._browser_lock:
            if self._browser and self._browser.is_connected():
                return self._browser

            try:
                self._browser = await self._launch_chromium()
            except Exception as e:
                msg = str(e)
                # [2026-07 FIX] "Executable doesn't exist" — 빌드 때 playwright install이
                # 안 됐거나 빌드/런타임 캐시 경로가 어긋난 경우. 배포 파이프라인을 다시
                # 만지지 않아도 되게, 런타임에서 딱 한 번만 자동 설치를 시도하고 재시도한다.
                if "Executable doesn't exist" in msg and not self._install_attempted:
                    self._install_attempted = True
                    print("[crawler] chromium missing — attempting runtime `playwright install chromium`")
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            sys.executable, "-m", "playwright", "install", "chromium",
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
                        out, _ = await proc.communicate()
                        print(f"[crawler] runtime playwright install exit={proc.returncode}: "
                              f"{out.decode(errors='ignore')[-800:]}")
                        if proc.returncode == 0:
                            self._browser = await self._launch_chromium()
                    except Exception as e2:
                        print(f"[crawler] runtime playwright install failed: {e2}")
                if not self._browser:
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
            "final_url": url,
            "status_code": 0,
            "error": None,
            "html_content": None,
            "rendered_by": None,
            "screenshot_phash": None,
            "page_height_px": None,
            "collection_issues": [],
        }

        # ✅ [FIX] HTTP는 requires_js 무관하게 항상 먼저 시도
        # 기존: if not requires_js → Samsung/Apple(requires_js=True)에서 HTTP 완전 건너뜀
        #       + USE_PLAYWRIGHT=false(기본) → Playwright도 건너뜀 → "empty result" 100%
        http_data = await self._fetch_http(url)
        http_bad = (not http_data) or bool(http_data.get("error"))
        if http_data and not http_data.get("error"):
            result.update(http_data)
            result["rendered_by"] = "httpx"

        # JS 렌더링을 태울지 결정 — 두 경로 분리:
        #  1) 전면 렌더(USE_PLAYWRIGHT=true): 기존처럼 '얼마나 비었나' 기준으로 업그레이드
        #  2) 구제(JS_RESCUE): 평소엔 안 태우고, httpx가 '빈/차단' 페이지를 받은 경우에만
        #     그 페이지만 별도 예산으로 재렌더 → 정상 페이지는 손대지 않아 속도 유지
        use_full = self.enable_playwright and self._looks_empty(http_data, strict=requires_js) \
            and self._browser_used < self.browser_page_cap
        use_rescue = (not self.enable_playwright) and self.js_rescue and http_bad \
            and self._rescue_used < self.js_rescue_cap

        if use_full or use_rescue:
            if use_full:
                self._browser_used += 1
            else:
                self._rescue_used += 1
                result.setdefault("collection_issues", []).append(
                    f"js_rescue: httpx 결과 부실({http_data.get('error') or 'near-empty'}) → JS 재렌더 시도")
            pw = await self._fetch_playwright(url)
            if pw and not pw.get("error"):
                result.update(pw)
                result["rendered_by"] = "playwright" + ("" if use_full else "(rescue)")
            elif pw and pw.get("error"):
                # 렌더까지 했는데도 실패 → 정확한 사유를 남긴다(차단/빈페이지/타임아웃 구분)
                result["error"] = pw.get("error")
                result.setdefault("collection_issues", []).extend(pw.get("collection_issues") or [])

        # HTTP 결과라도 있으면 최종 fallback
        if result.get("html_content") is None and http_data:
            result.update(http_data)

        if result.get("html_content") is None and not result.get("error"):
            result["error"] = "empty result"

        result["load_time_ms"] = int((datetime.now() - t0).total_seconds() * 1000)
        return result

    # ─────────────────────────────────────────────
    # FORCE RENDER (선택적 단건 재렌더)
    # ─────────────────────────────────────────────
    async def force_render(self, url: str) -> Dict[str, Any]:
        """[2026-07 신규] httpx 결과의 '비어있음' 판정과 무관하게 이 URL 하나만 강제로
        Playwright 렌더링한다. 스펙 값이 0개 감지된('JS 미렌더 추정') 페이지를 상위 레이어
        (qb_routes_run)가 선별적으로 재수집할 때 사용 — crawl()의 기존 판단/속도에는
        영향을 주지 않는다."""
        return await self._fetch_playwright(url)

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
        min_words = 120 if strict else 60
        return (
            len(data.get("body_content") or "") < min_len
            or int(data.get("word_count") or 0) < min_words
            or not data.get("title")
        )

    # ─────────────────────────────────────────────
    # BAD PAGE / ERROR PAGE DETECTION
    # ─────────────────────────────────────────────
    def _detect_bad_page(self, data: Optional[Dict[str, Any]], url: str = "") -> Optional[str]:
        """정상 HTML처럼 보이지만 실제로는 Error/차단/빈 페이지인 경우를 실패로 분류한다.

        Meta의 'Error | Meta'처럼 status=200 + title 존재 조합은 기존 _looks_empty에서
        정상 수집으로 통과했다. 이 함수는 title/body/근거 필드를 같이 보고 비교 불가
        페이지를 명시적으로 막는다.
        """
        if not data:
            return "empty result"
        if data.get("error"):
            return str(data.get("error"))

        title = str(data.get("title") or "").strip()
        h1 = str(data.get("h1") or "").strip()
        body = str(data.get("body_content") or "").strip()
        word_count = int(data.get("word_count") or 0)
        image_count = len(data.get("images") or [])
        cta_count = len(data.get("ctas") or [])
        schema_count = len(data.get("structured_data") or [])
        combined = " ".join([title, h1, body[:500]]).lower()

        hard_error_patterns = (
            "error | meta", "access denied", "permission denied", "not found", "page not found",
            "404", "403", "429", "captcha", "verify you are human", "just a moment",
            "temporarily unavailable", "something went wrong", "unsupported browser",
        )
        if any(p in combined for p in hard_error_patterns):
            return f"error page detected: {title or 'unknown title'}"

        # title/h1은 있으나 실제 분석 근거가 거의 없는 케이스. Meta 에러 페이지처럼
        # nav나 빈 컨테이너만 남는 경우 변경 없음으로 오판하지 않도록 차단한다.
        if word_count < 15 and image_count == 0 and cta_count == 0 and schema_count == 0:
            return "insufficient crawl evidence: near-empty page"

        return None

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
                        "final_url": str(r.url),
                        "collection_issues": [f"blocked {r.status_code}"],
                    }

                soup = BeautifulSoup(r.text or "", "lxml")
                final_url = str(r.url)
                data = self._extract(soup, final_url)

                data["html_content"] = r.text
                data["status_code"] = r.status_code
                data["final_url"] = final_url
                data["collection_issues"] = []

                bad_reason = self._detect_bad_page(data, final_url)
                if bad_reason:
                    data["error"] = bad_reason
                    data["collection_issues"].append(bad_reason)
                return data

            except Exception as e:
                return {"error": str(e), "status_code": 0, "collection_issues": [str(e)]}

    # ─────────────────────────────────────────────
    # PLAYWRIGHT
    # ─────────────────────────────────────────────
    # ─────────────────────────────────────────────
    # PLAYWRIGHT (하드 타임아웃 래퍼)
    # ─────────────────────────────────────────────
    # [2026-07-4 FIX] 진짜 근본 원인: is_connected()는 브라우저가 "죽었는지"만 감지한다.
    # 하지만 Render 512MB에서 메모리를 다 써서 스와핑이 시작되면, Chromium은 죽지 않은 채로
    # (is_connected()=true) 그냥 응답이 몇 분씩 안 오는 상태가 된다. 이 안에서 걸리는 모든
    # await(new_context/goto/evaluate 등)에 개별 timeout이 있어도, self._browser_sem(=1)을
    # 쥔 채로 멈춰 있으면 배치의 남은 모든 렌더·다음 배치 실행이 전부 그 세마포어를 기다리며
    # 무한정 걸린다 — "예전엔 잘 됐는데 크롤러 바꾸고 나서 갑자기(크롤을 안 돌려도) 계속
    # 느려진다"던 현상의 핵심. 전체 렌더 1건에 하드 데드라인을 걸어, 넘으면 무조건 브라우저를
    # 통째로 버리고 재기동해 세마포어를 풀어준다.
    async def _fetch_playwright(self, url: str) -> Dict[str, Any]:
        try:
            return await asyncio.wait_for(
                self._fetch_playwright_inner(url), timeout=self._render_hard_timeout_s)
        except asyncio.TimeoutError:
            print(f"[crawler] HARD TIMEOUT({self._render_hard_timeout_s}s) — chromium wedged "
                  f"(alive but unresponsive, likely OOM/swap) — force-killing & relaunching: {url}")
            async with self._browser_lock:
                try:
                    if self._browser:
                        await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            msg = f"하드 타임아웃({self._render_hard_timeout_s}s) — 브라우저가 응답 없어 강제 재기동함"
            return {"error": msg, "status_code": 0, "collection_issues": [msg]}

    async def _fetch_playwright_inner(self, url: str) -> Dict[str, Any]:
        # [2026-07-4 FIX] force_render()(Compare 페이지는 항상 이 경로)는 browser_page_cap을
        # 타지 않아 한 번의 배치 실행 안에서 렌더 횟수 제한이 없었다. Chromium은 context를
        # 매번 close()해도 프로세스 메모리가 서서히 늘어나는 경향이 있어(특히 --single-process),
        # 렌더가 많이 몰리는 실행(Compare 사이트가 많은 배치)에서는 시간이 지날수록 Render
        # 512MB를 넘겨 OOM으로 죽을 위험이 커진다. N회(RECYCLE_AFTER_RENDERS)마다 브라우저를
        # 통째로 재기동해 누적 메모리를 강제로 반납한다 — 캐시 실패가 아니라 예방적 재기동.
        self._render_count = getattr(self, "_render_count", 0) + 1
        if self._render_count % self._recycle_after_renders == 0:
            print(f"[crawler] recycling chromium after {self._render_count} renders "
                  f"(preventive — avoids Render 512MB OOM creep)")
            async with self._browser_lock:
                try:
                    if self._browser:
                        await self._browser.close()
                except Exception:
                    pass
                self._browser = None

        browser = await self._ensure_browser()
        if not browser:
            return {"error": "playwright unavailable", "collection_issues": ["playwright unavailable"]}

        async with self._browser_sem:
            context = page = None
            try:
                context = await browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=self.user_agent,
                    locale="en-US",
                    timezone_id="America/Los_Angeles",
                )
                # [consent] 동의/지역 게이트가 강한 사이트(Meta 등)에 미리 동의 쿠키를 심어
                # 쿠키월/리다이렉트로 'Error | Meta' 껍데기가 오는 것을 줄인다.
                try:
                    host = re.sub(r"^https?://", "", url).split("/")[0]
                    root = "." + ".".join(host.split(".")[-2:])
                    await context.add_cookies([
                        {"name": "dcookie", "value": "1", "domain": root, "path": "/"},
                        {"name": "cookie_consent", "value": "accepted", "domain": root, "path": "/"},
                        {"name": "OptanonAlertBoxClosed", "value": "2026-01-01T00:00:00.000Z", "domain": root, "path": "/"},
                    ])
                except Exception:
                    pass

                page = await context.new_page()
                await page.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")

                await page.goto(url, wait_until="domcontentloaded", timeout=self.js_timeout_ms)

                # [2026-07 FIX] Samsung.com 2단계 게이트(①지역/언어 선택 → ②개인정보 동의)를
                # 먼저 닫는다. 안 닫으면 Compare/Specs 표의 실제 스펙 값(JS로 채워짐)이 영원히
                # 비어있는 채로 캡처됨 — 아이콘/열 구조만 있고 숫자는 없는 현상의 유력 원인.
                # 다른 사이트의 무관한 버튼을 잘못 누르지 않도록, 반드시 해당 모달의 랜드마크
                # 문구가 같이 있는 컨테이너 안에서만 클릭한다(전역 'Continue' 클릭 금지).
                try:
                    loc_btn = await page.query_selector(
                        "xpath=//*[contains(text(),'Choose your location and language')]"
                        "/ancestor::*[self::div or self::section or self::form][1]"
                        "//button[contains(., 'Continue')]")
                    if loc_btn:
                        await loc_btn.click(timeout=1500); await page.wait_for_timeout(400)
                except Exception:
                    pass
                try:
                    proceed_btn = await page.query_selector(
                        "button:has-text('PROCEED TO SAMSUNG.COM')")
                    if proceed_btn:
                        cb = await page.query_selector(
                            "xpath=//button[contains(., 'PROCEED TO SAMSUNG.COM')]"
                            "/ancestor::*[self::div or self::form][1]//input[@type='checkbox']")
                        if cb:
                            await cb.click(timeout=1500); await page.wait_for_timeout(200)
                        await proceed_btn.click(timeout=1500); await page.wait_for_timeout(400)
                except Exception:
                    pass

                # [consent] 흔한 쿠키 동의 버튼 자동 클릭(있으면). 없으면 조용히 넘어감.
                for sel in ("button[data-cookiebanner='accept_button']",
                            "button[data-testid='cookie-policy-manage-dialog-accept-button']",
                            "[aria-label*='Allow all']", "[title*='Accept']",
                            "button:has-text('Accept All')", "button:has-text('Accept all')",
                            "button:has-text('동의')", "button:has-text('모두 허용')"):
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            await el.click(timeout=1500); await page.wait_for_timeout(400); break
                    except Exception:
                        pass

                try:
                    await page.wait_for_load_state("networkidle", timeout=self.js_networkidle_ms)
                except Exception:
                    await page.wait_for_timeout(1200)

                # [2026-07 FIX] 스펙/Compare 섹션이 스크롤 진입 시에만 그려지는(지연로딩)
                # 페이지가 많다 — 캡처 전 페이지 끝까지 단계적으로 스크롤해 지연로딩 콘텐츠를
                # 강제로 화면에 그려지게 한다. 실패해도 기존 캡처 흐름엔 영향 없음.
                # [2026-07 속도 개선] 반복 횟수(40회) 대신 총 시간 예산(js_scroll_budget_ms)으로
                # 상한을 건다 — "스크롤할 때마다 높이가 계속 늘어나는" 캐러셀형 페이지는 기존
                # 조기 종료 조건에 걸리지 않아 매번 최대치(10초)를 다 썼는데, 이제는 예산을
                # 넘기면 무조건 멈추고 다음 단계로 넘어간다.
                try:
                    await page.evaluate(
                        """
                        async (budgetMs) => {
                            const step = Math.max(400, window.innerHeight);
                            const t0 = Date.now();
                            let last = -1;
                            while (Date.now() - t0 < budgetMs) {
                                window.scrollBy(0, step);
                                await new Promise(r => setTimeout(r, 180));
                                const h = document.body ? document.body.scrollHeight : 0;
                                if (window.scrollY + window.innerHeight >= h) {
                                    if (h === last) break;
                                    last = h;
                                }
                            }
                            window.scrollTo(0, 0);
                        }
                        """,
                        self.js_scroll_budget_ms,
                    )
                    await page.wait_for_timeout(350)
                except Exception:
                    pass

                html = await page.content()
                final_url = page.url
                soup = BeautifulSoup(html, "lxml")

                data = self._extract(soup, final_url)
                data["html_content"] = html
                data["status_code"] = 200
                data["final_url"] = final_url
                data["collection_issues"] = []

                try:
                    height = await page.evaluate(
                        "() => Math.max("
                        "document.documentElement ? document.documentElement.scrollHeight : 0,"
                        "document.body ? document.body.scrollHeight : 0)"
                    )
                    data["page_height_px"] = int(height) if height else None
                except Exception:
                    data["page_height_px"] = None

                bad_reason = self._detect_bad_page(data, final_url)
                if bad_reason:
                    # 렌더까지 했는데도 실패 → 사유를 사람이 알아보게 분류
                    redirected = final_url.rstrip("/") != url.rstrip("/")
                    if "error page" in bad_reason or "blocked" in bad_reason:
                        why = f"사이트 차단/에러 페이지(렌더 후에도 '{data.get('title') or '?'}')"
                    elif "near-empty" in bad_reason:
                        why = "JS 렌더 후에도 본문 없음 — 동의벽/지역 게이트 추정"
                    else:
                        why = bad_reason
                    if redirected:
                        why += f" · 리다이렉트: {final_url}"
                    data["error"] = why
                    data["collection_issues"].append(why)
                return data

            except Exception as e:
                msg = str(e)
                # [2026-07-4 FIX] 브라우저가 렌더 도중 죽은 경우(OOM 등) — "has been closed"류
                # 예외를 그냥 실패로 남기면, 배치의 남은 모든 페이지가 죽은 브라우저를 향해
                # 매번 타임아웃까지 기다리다 실패하는 연쇄가 발생한다. 여기서 딱 1회만 브라우저를
                # 강제로 재기동하고 같은 URL을 재시도해 배치가 계속 진행되게 한다.
                closed = ("has been closed" in msg or "Target page" in msg
                          or "Connection closed" in msg or "Browser closed" in msg)
                if closed and not getattr(self, "_retrying_after_crash", False):
                    print(f"[crawler] browser died mid-render ({msg[:120]}) — relaunch + retry once: {url}")
                    self._retrying_after_crash = True
                    try:
                        async with self._browser_lock:
                            try:
                                if self._browser:
                                    await self._browser.close()
                            except Exception:
                                pass
                            self._browser = None
                        return await self._fetch_playwright(url)
                    finally:
                        self._retrying_after_crash = False
                if "Timeout" in msg or "timeout" in msg:
                    msg = f"타임아웃({self.js_timeout_ms}ms 초과) — 페이지가 안 뜨거나 차단 추정"
                return {"error": msg, "status_code": 0, "collection_issues": [msg]}

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

        d["body_content"] = self._body_copy_text(soup, page_url)
        d["word_count"] = len(d["body_content"].split())
        return d

    def _body_copy_text(self, soup: BeautifulSoup, page_url: str = "") -> str:
        """반복 크롤 안정화를 위한 본문 카피 추출.

        기존 body 전체 텍스트는 헤더/푸터/메뉴/쿠키/추천 영역까지 포함해
        같은 페이지를 바로 다시 크롤해도 텍스트 순서와 항목 수가 흔들릴 수 있었다.
        CTA/내비/이미지/FAQ는 별도 필드로 이미 수집하므로, body_content는
        핵심 랜딩 카피 중심으로 정리해 저장한다.
        """
        root = soup.find("main") or soup.find("body")
        if not root:
            return ""

        # [FIX 2026-07] "compare"는 원래 PDP 등 다른 페이지에 뜨는 '비교하기' 업셀
        # 위젯(cross-sell)을 걸러내려던 키워드였는데, 정작 Compare 페이지 자신은
        # 최상위 컨테이너부터 "compare-..." 클래스/id를 쓰는 경우가 많아, 이 하나의
        # 키워드가 Compare 페이지의 스펙 그리드 전체를 통째로 지워버리고 있었다
        # (그래서 Compare 페이지에서 스펙이 "아예" 안 잡히는 현상 발생).
        # → 지금 크롤 중인 URL 자체가 Compare 페이지면 "compare/비교" 키워드는
        #   노이즈 필터에서 빼고, 대신 업셀 위젯에만 쓰이는 더 구체적인 패턴으로 대체.
        is_compare_page = bool(re.search(r"/compare(/|$)", page_url or "", re.IGNORECASE))

        # 원본 soup를 훼손하지 않도록 복제한 뒤 노이즈 영역 제거
        clean = BeautifulSoup(str(root), "lxml")
        noisy_tags = [
            "script", "style", "noscript", "svg", "path", "template", "iframe",
            "header", "footer", "nav", "form", "select", "option",
        ]
        for t in clean.find_all(noisy_tags):
            t.decompose()

        compare_token = (
            # Compare 페이지 자신을 크롤할 때: 업셀 위젯만 좁게 매칭(자기 자신의
            # compare-key-specs / compare-table 같은 본문 컨테이너는 건드리지 않음)
            r"compare[-_]?(cta|widget|upsell|promo|banner|module)|"
            r"(you[-_ ]?may|related|recommend)[-_ ]?compare"
            if is_compare_page
            # 그 외 페이지(PDP 등)에서는 기존처럼 "compare" 전체를 노이즈로 간주
            else r"compare"
        )
        noisy_re = re.compile(
            r"(cookie|consent|privacy|legal|footer|header|nav|menu|gnb|breadcrumb|"
            r"modal|popup|overlay|drawer|tooltip|pagination|carousel-control|"
            rf"recommend|related|recently|{compare_token}|support|search|login|account|"
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

