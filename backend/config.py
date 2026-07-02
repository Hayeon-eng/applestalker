"""
Target Registry — 확장 가능한 도메인/URL 레지스트리
================================================================
이번 버전의 핵심:
  - Global/US 공식 URL 기준의 최소 PF/PDP/Buying 세트만 유지
  - Smartphone / Tablet / Audio / Watch / Laptop / AI Glass 기준으로 정리
  - Buying hard URL이 없는 브랜드는 PDP/PF에서 Buy CTA를 감지하는 방식으로 보완
  - 기존 코드가 쓰던 get_apple_urls/get_samsung_urls/get_all_urls 호환 유지
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse


# ──────────────────────────────────────────────────────────────
# 도메인별 정책 (parsing / extraction / sensitivity)
# ──────────────────────────────────────────────────────────────

@dataclass
class SensitivityPolicy:
    """이 도메인에서 어떤 변화를 얼마나 민감하게 볼지."""
    min_text_diff_ratio: float = 0.002
    ignore_selectors: List[str] = field(default_factory=lambda: [
        "[data-analytics-region='cookie']", ".cookie", "#onetrust-banner-sdk",
        "time", ".timestamp", "[aria-live]",
    ])
    critical_keywords: List[str] = field(default_factory=lambda: [
        "price", "$", "₩", "월", "할부", "trade-in", "보상", "sold out",
        "품절", "out of stock", "pre-order", "사전예약", "free", "무료",
        "buy now", "buy", "shop", "shop now", "add to cart", "add to bag",
        "checkout", "where to buy", "구매", "장바구니",
    ])


@dataclass
class ExtractionRule:
    """이 도메인에서 본문/CTA/가격을 어떻게 뽑을지."""
    content_root: Optional[str] = None
    price_selectors: List[str] = field(default_factory=list)
    requires_js: bool = False


@dataclass
class Target:
    """경쟁사/모니터링 대상 1개 (= 1 도메인 정책)."""
    key: str
    display_name: str
    domains: List[str]
    seed_urls: List[str]
    extraction: ExtractionRule = field(default_factory=ExtractionRule)
    sensitivity: SensitivityPolicy = field(default_factory=SensitivityPolicy)
    is_ours: bool = False


COMMERCE_SELECTORS = [
    ".price", "[class*='price']", "[data-price]", "[class*='Price']",
    "[class*='financing']", "[class*='trade']", "[data-testid*='price']",
]


# ──────────────────────────────────────────────────────────────
# 기본 시드 URL — Global/US 공식 URL, 각 카테고리 대표 모델만
# ──────────────────────────────────────────────────────────────

SEED_TARGETS: Dict[str, Target] = {
    "samsung": Target(
        key="samsung",
        display_name="Samsung Global / US",
        domains=["samsung.com"],
        is_ours=True,
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            # Smartphone: Galaxy S Ultra — PF / PDP / Buying
            "https://www.samsung.com/us/smartphones/",
            "https://www.samsung.com/us/smartphones/galaxy-s26-ultra/",
            "https://www.samsung.com/us/smartphones/galaxy-s26-ultra/buy/galaxy-s26-ultra-256gb-unlocked-sku-sm-s948uzvaxaa/",
            # Tablet: Galaxy Tab S Ultra — PF / PDP / Buying
            "https://www.samsung.com/us/tablets/",
            "https://www.samsung.com/us/tablets/galaxy-tab-s11/",
            "https://www.samsung.com/us/tablets/galaxy-tab-s11/buy/galaxy-tab-s11-ultra-1tb-gray-wi-fi-sku-sm-x930nzaixar/",
            # Watch: Galaxy Watch Ultra — PF / PDP / Buying
            "https://www.samsung.com/us/watches/",
            "https://www.samsung.com/us/watches/galaxy-watch-ultra-2025/",
            "https://www.samsung.com/us/watches/galaxy-watch-ultra-2025/buy/galaxy-watch-ultra-47mm-titanium-gray-sku-sm-l705uza1xaa/",
            # Audio: Galaxy Buds Pro — PF / PDP / Buying
            "https://www.samsung.com/us/audio-sound/",
            "https://www.samsung.com/us/audio-sound/galaxy-buds4-pro/",
            "https://www.samsung.com/us/audio-sound/galaxy-buds4-pro/buy/galaxy-buds4-pro-white-sku-sm-r640nzwaxar/",
            # Laptop: Galaxy Book Ultra — PF / PDP / Buying
            "https://www.samsung.com/us/galaxybooks/",
            "https://www.samsung.com/us/computers/galaxy-book/galaxy-book6-ultra/",
            "https://www.samsung.com/us/computers/galaxy-book/galaxy-book6-series/buy/galaxy-book6-ultra-16-intel-core-ultra-7-1tb-gray-sku-np960ujh-xg2us/",
        ],
    ),
    "apple": Target(
        key="apple",
        display_name="Apple Global / US",
        domains=["apple.com"],
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            # Smartphone: iPhone Pro — PF / PDP / Buying
            "https://www.apple.com/iphone/",
            "https://www.apple.com/iphone-17-pro/",
            "https://www.apple.com/shop/buy-iphone/iphone-17-pro",
            # Tablet: iPad Pro — PF / PDP / Buying
            "https://www.apple.com/ipad/",
            "https://www.apple.com/ipad-pro/",
            "https://www.apple.com/shop/buy-ipad/ipad-pro",
            # Audio: AirPods Pro — PF / PDP / Buying
            "https://www.apple.com/airpods/",
            "https://www.apple.com/airpods-pro/",
            "https://www.apple.com/shop/buy-airpods/airpods-pro-3",
            # Watch: Apple Watch Ultra — PF / PDP / Buying
            "https://www.apple.com/watch/",
            "https://www.apple.com/apple-watch-ultra-3/",
            "https://www.apple.com/shop/buy-watch/apple-watch-ultra",
            # Laptop: MacBook Pro — PF / PDP / Buying
            "https://www.apple.com/mac/",
            "https://www.apple.com/macbook-pro/",
            "https://www.apple.com/shop/buy-mac/macbook-pro",
        ],
    ),
    "google_pixel": Target(
        key="google_pixel",
        display_name="Google Pixel Global / US",
        domains=["store.google.com"],
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            "https://store.google.com/category/phones?hl=en-US",
            "https://store.google.com/product/pixel_10_pro?hl=en-US",
            "https://store.google.com/config/pixel_10_pro?hl=en-US",
        ],
    ),
    "xiaomi": Target(
        key="xiaomi",
        display_name="Xiaomi Global",
        domains=["mi.com"],
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            # Smartphone + Tablet. 별도 글로벌 buying hard URL이 없으면 PDP 내 Buy CTA를 감지.
            "https://www.mi.com/global/product-list/phone/xiaomi/",
            "https://www.mi.com/global/product/xiaomi-17-ultra/",
            "https://www.mi.com/global/product-list/tablet/",
            "https://www.mi.com/global/product/xiaomi-pad-8-pro/",
        ],
    ),
    "oppo": Target(
        key="oppo",
        display_name="OPPO Global",
        domains=["oppo.com"],
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            "https://www.oppo.com/en/smartphones/",
            "https://www.oppo.com/en/smartphones/series-find-x/find-x9-ultra/",
        ],
    ),
    "vivo": Target(
        key="vivo",
        display_name="vivo Global",
        domains=["vivo.com"],
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            "https://www.vivo.com/en/products",
            "https://www.vivo.com/en/products/x300-ultra",
        ],
    ),
    "sony_audio": Target(
        key="sony_audio",
        display_name="Sony Audio Global / US",
        domains=["electronics.sony.com"],
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            "https://electronics.sony.com/audio/headphones/truly-wireless-earbuds",
            "https://electronics.sony.com/audio/headphones/truly-wireless-earbuds/p/wf1000xm6-b",
        ],
    ),
    "garmin": Target(
        key="garmin",
        display_name="Garmin Global / US",
        domains=["garmin.com"],
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            "https://www.garmin.com/en-US/c/wearables-smartwatches/",
            "https://www.garmin.com/en-US/p/1723221/",
        ],
    ),
    "dell": Target(
        key="dell",
        display_name="Dell Global / US",
        domains=["dell.com"],
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            "https://www.dell.com/en-us/shop/dell-laptops/scr/laptops/appref%3Dxps-product-line",
            "https://www.dell.com/en-us/shop/dell-laptops/new-xps-16-laptop/spd/xps-da16260-laptop",
        ],
    ),
    "meta_ai_glasses": Target(
        key="meta_ai_glasses",
        display_name="Meta AI Glasses Global / US",
        domains=["meta.com"],
        extraction=ExtractionRule(requires_js=True, price_selectors=COMMERCE_SELECTORS),
        seed_urls=[
            "https://www.meta.com/ai-glasses/",
            "https://www.meta.com/ai-glasses/ray-ban-meta/",
            "https://www.meta.com/ai-glasses/shop-all/",
        ],
    ),
}


# ──────────────────────────────────────────────────────────────
# URL 역할 / Tier 계산
# ──────────────────────────────────────────────────────────────

def page_role_for_url(url: str) -> str:
    """PF/PDP/Buying/Compare/Home 등 페이지 역할을 URL 패턴으로 추정."""
    try:
        parsed = urlparse(url)
        path = (parsed.path or "/").lower().rstrip("/")
        query = (parsed.query or "").lower()
    except Exception:
        return "unknown"

    if path in ("", "/", "/us", "/sg", "/global", "/en-us", "/en"):
        return "home"
    if any(k in path for k in (
        "/shop/buy", "/buy", "/config/", "/cty/pdp/", "/shop-all", "/cart", "/checkout"
    )):
        return "buying"
    if any(k in path for k in ("compare", "find-your", "switch-to", "apple-intelligence", "galaxy-ai")):
        return "campaign_or_compare"
    if any(k in path for k in ("specs", "specifications", "tech-specs")):
        return "specs"
    if any(k in path for k in (
        "iphone-", "pixel_", "xiaomi-", "ipad-pro", "xiaomi-pad-", "find-x", "x300",
        "wf1000", "wf-1000", "apple-watch-", "airpods-pro", "macbook-pro",
        "xps-16", "dell-da", "xps-da", "/p/1701921", "/p/1723221", "ray-ban-meta",
        "galaxy-s26-ultra", "galaxy-tab-s11", "galaxy-watch-ultra", "galaxy-buds4-pro",
        "galaxy-book6-ultra",
    )):
        return "pdp"
    if any(k in path for k in (
        "iphone", "phones", "smartphones", "product-list", "products", "ipad", "tablet", "tablets",
        "airpods", "watch", "watches", "mac", "galaxybooks", "galaxy-book", "laptops",
        "headphones", "wearables", "audio-sound", "ai-glasses", "all-smartphones", "all-watches",
        "all-audio", "computers",
    )) or "category=" in query:
        return "pf"
    return "content"


def tier_for_url(url: str) -> int:
    """URL 역할 기준 tier 0~4 추정. 한 곳에서만 정의해 일관성 보장."""
    role = page_role_for_url(url)
    if role == "home":
        return 0
    if role == "pf":
        return 1
    if role == "campaign_or_compare":
        return 2
    if role in ("pdp", "content"):
        return 3
    if role in ("buying", "specs"):
        return 4
    try:
        path = (urlparse(url).path or "/").lower()
        segments = [s for s in path.split("/") if s and s not in ("sg", "us", "en", "global")]
        return min(len(segments), 3) if segments else 0
    except Exception:
        return 3


def target_for_url(url: str) -> Optional[Target]:
    """URL → 어느 Target 정책인지."""
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return None
    for t in SEED_TARGETS.values():
        if any(d in netloc for d in t.domains):
            return t
    return None


def site_key_for_url(url: str) -> str:
    t = target_for_url(url)
    return t.key if t else "unknown"


# ──────────────────────────────────────────────────────────────
# 활성 URL 로딩 (SEED + DB 등록분 머지)
# ──────────────────────────────────────────────────────────────

def get_seed_urls(site_key: str) -> List[str]:
    t = SEED_TARGETS.get(site_key)
    return list(t.seed_urls) if t else []


def load_active_urls(site_key: str, db_urls: Optional[List[str]] = None) -> List[Dict]:
    """
    크롤 대상 URL 목록 반환. SEED + DB(MonitoredURL) 머지 후 중복 제거.
    각 항목: {"url", "tier_level", "site_key", "page_role"}

    Buying hard URL이 없는 글로벌 사이트는 URL을 억지로 만들지 않는다.
    해당 PDP/PF에서 crawler가 Buy/Shop/Add to cart CTA 텍스트와 href를 수집하고,
    COPY/Visual 분석에서 구매 CTA 보유 여부를 근거로 표시한다.
    """
    urls: List[str] = list(get_seed_urls(site_key))
    if db_urls:
        urls.extend(db_urls)
    seen, out = set(), []
    for u in urls:
        u = (u or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append({
            "url": u,
            "tier_level": tier_for_url(u),
            "site_key": site_key,
            "page_role": page_role_for_url(u),
        })
    return out


def all_site_keys() -> List[str]:
    return list(SEED_TARGETS.keys())


# 하위호환: 기존 코드가 import 하던 함수명 유지

def get_apple_urls() -> List[str]:
    return get_seed_urls("apple")


def get_samsung_urls() -> List[str]:
    return get_seed_urls("samsung")


def get_all_urls() -> List[str]:
    out = []
    for k in all_site_keys():
        out.extend(get_seed_urls(k))
    return out


def get_tier_for_url(url: str) -> str:
    return f"Tier {tier_for_url(url)}"
