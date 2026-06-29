"""
Target Registry — 확장 가능한 도메인/URL 레지스트리
================================================================
기존 config/urls.py 의 하드코딩 45개 URL 을 대체.

핵심 변경:
  - 각 "타겟(경쟁사 도메인)"은 자체 parsing/extraction/sensitivity 정책을 가짐
  - seed URL 은 코드(SEED_TARGETS)에 기본값으로 두되,
    런타임에 DB(MonitoredURL 테이블)에서 추가/삭제 가능 → "URL 추가 불가" 문제 해결
  - Samsung/Apple/Google/임의 사이트를 URL 만으로 등록 가능

설계 원칙: 이 파일은 '정책(스키마)'만 정의한다. 실제 활성 URL 목록은
load_active_urls(db) 가 (SEED_TARGETS + DB 등록분)을 머지해서 돌려준다.
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
    # 변화 크기(diff ratio)가 이 값 미만이면 noise 로 보고 무시 (0~1)
    min_text_diff_ratio: float = 0.002          # 0.2% 미만 텍스트 변화는 무시
    # 이 셀렉터에 매칭되는 영역의 변화는 항상 무시 (배너/시간/랜덤 광고 등)
    ignore_selectors: List[str] = field(default_factory=lambda: [
        "[data-analytics-region='cookie']", ".cookie", "#onetrust-banner-sdk",
        "time", ".timestamp", "[aria-live]",
    ])
    # 이 키워드가 필드에 들어가면 business-critical(L5) 후보로 승격
    critical_keywords: List[str] = field(default_factory=lambda: [
        "price", "$", "₩", "월", "할부", "trade-in", "보상", "sold out",
        "품절", "out of stock", "pre-order", "사전예약", "free", "무료",
    ])


@dataclass
class ExtractionRule:
    """이 도메인에서 본문/CTA/가격을 어떻게 뽑을지 (도메인 특화)."""
    # 본문으로 간주할 root 셀렉터 (없으면 <body>)
    content_root: Optional[str] = None
    # 가격 텍스트를 담는 셀렉터(있으면 commerce 변화 정밀 추적)
    price_selectors: List[str] = field(default_factory=list)
    # JS 렌더링이 꼭 필요한 도메인인지 (httpx 로 안 되면 Playwright 강제)
    requires_js: bool = False


@dataclass
class Target:
    """경쟁사/모니터링 대상 1개 (= 1 도메인 정책)."""
    key: str                       # "apple", "samsung", "google"...
    display_name: str
    domains: List[str]             # netloc 매칭용 ("apple.com")
    seed_urls: List[str]
    extraction: ExtractionRule = field(default_factory=ExtractionRule)
    sensitivity: SensitivityPolicy = field(default_factory=SensitivityPolicy)
    is_ours: bool = False          # 당사(삼성) 여부 — 분석 관점 결정에 사용


# ──────────────────────────────────────────────────────────────
# 기본 시드 (기존 45개 URL 을 타겟별로 재구성)
# tier 는 URL path 깊이/키워드로 동적 계산 (tier_for_url) → 별도 dict 불필요
# ──────────────────────────────────────────────────────────────

SEED_TARGETS: Dict[str, Target] = {
    "samsung": Target(
        key="samsung",
        display_name="Samsung Singapore",
        domains=["samsung.com"],
        is_ours=True,
        extraction=ExtractionRule(
            requires_js=True,
            price_selectors=[".price", "[class*='price']", "[data-price]"],
        ),
        seed_urls=[
            "https://www.samsung.com/sg/",
            "https://www.samsung.com/sg/smartphones/all-smartphones/",
            "https://www.samsung.com/sg/watches/all-watches/",
            "https://www.samsung.com/sg/audio-sound/all-audio-sound/",
            "https://www.samsung.com/sg/mobile/",
            "https://www.samsung.com/sg/galaxy-ai/",
            "https://www.samsung.com/sg/mobile/find-your-galaxy/",
            "https://www.samsung.com/sg/mobile/switch-to-galaxy/",
            "https://www.samsung.com/sg/one-ui/",
            "https://www.samsung.com/sg/smartphones/galaxy-s26-ultra/",
            "https://www.samsung.com/sg/smartphones/galaxy-s26/",
            "https://www.samsung.com/sg/smartphones/galaxy-z-fold7/",
            "https://www.samsung.com/sg/smartphones/galaxy-z-flip7/",
            "https://www.samsung.com/sg/watches/galaxy-watch-ultra-2025/",
            "https://www.samsung.com/sg/audio-sound/galaxy-buds4-pro/",
            "https://www.samsung.com/sg/smartphones/galaxy-s26-ultra/buy/",
            "https://www.samsung.com/sg/smartphones/galaxy-s26/buy/",
            "https://www.samsung.com/sg/smartphones/galaxy-z-fold7/buy/",
            "https://www.samsung.com/sg/smartphones/galaxy-z-flip7/buy/",
            "https://www.samsung.com/sg/watches/galaxy-watch-ultra-2025/buy/",
            "https://www.samsung.com/sg/audio-sound/galaxy-buds4-pro/buy/",
        ],
    ),
    "apple": Target(
        key="apple",
        display_name="Apple US",
        domains=["apple.com"],
        is_ours=False,
        extraction=ExtractionRule(
            requires_js=True,
            price_selectors=[".rc-prices-fullprice", "[class*='price']"],
        ),
        seed_urls=[
            "https://www.apple.com/",
            "https://www.apple.com/iphone/",
            "https://www.apple.com/watch/",
            "https://www.apple.com/airpods/",
            "https://www.apple.com/apple-intelligence/",
            "https://www.apple.com/iphone/compare/",
            "https://www.apple.com/watch/compare/",
            "https://www.apple.com/iphone-17-pro/",
            "https://www.apple.com/iphone-air/",
            "https://www.apple.com/iphone-17/",
            "https://www.apple.com/iphone-17e/",
            "https://www.apple.com/apple-watch-series-11/",
            "https://www.apple.com/apple-watch-ultra-3/",
            "https://www.apple.com/apple-watch-se-3/",
            "https://www.apple.com/airpods-pro/",
            "https://www.apple.com/iphone-17-pro/specs/",
            "https://www.apple.com/iphone-air/specs/",
            "https://www.apple.com/iphone-17/specs/",
            "https://www.apple.com/iphone-17e/specs/",
            "https://www.apple.com/apple-watch-series-11/specs/",
            "https://www.apple.com/apple-watch-ultra-3/specs/",
            "https://www.apple.com/apple-watch-se-3/specs/",
            "https://www.apple.com/airpods-pro/specs/",
            "https://www.apple.com/shop/buy-iphone",
        ],
    ),
    # 예시: 새 경쟁사는 이렇게 한 블록만 추가하면 됨 (Google)
    # "google": Target(
    #     key="google", display_name="Google Store", domains=["store.google.com"],
    #     seed_urls=["https://store.google.com/?hl=en-US"],
    #     extraction=ExtractionRule(requires_js=True),
    # ),
}


# ──────────────────────────────────────────────────────────────
# Tier 계산 (URL 만으로 동적 — 별도 매핑 dict 유지 불필요)
# ──────────────────────────────────────────────────────────────

def tier_for_url(url: str) -> int:
    """URL path 로 tier 0~4 추정. 한 곳에서만 정의해 일관성 보장."""
    try:
        path = (urlparse(url).path or "/").lower()
        segments = [s for s in path.split("/") if s and s not in ("sg", "us", "en")]
        if not segments:
            return 0                                   # 브랜드 홈
        if any(k in path for k in ("buy", "shop", "specs", "purchase")):
            return 4                                   # 구매/스펙
        if any(k in path for k in ("compare", "find-your", "switch-to",
                                   "galaxy-ai", "apple-intelligence", "mobile/", "one-ui")):
            return 2                                   # 캠페인
        if any(k in path for k in ("iphone-", "galaxy-", "apple-watch-",
                                   "buds", "watch-ultra")):
            return 3                                   # 제품 상세
        if any(k in path for k in ("all-smartphones", "all-watches",
                                   "all-audio", "iphone", "watch", "airpods")):
            return 1                                   # 카테고리
        return min(len(segments), 3)
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
    각 항목: {"url", "tier_level", "site_key"}
    db_urls: crawl_service 가 MonitoredURL 테이블에서 읽어 넘겨줌 (None 이면 시드만).
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
        out.append({"url": u, "tier_level": tier_for_url(u), "site_key": site_key})
    return out


def all_site_keys() -> List[str]:
    return list(SEED_TARGETS.keys())


# 하위호환: 기존 코드가 import 하던 함수명 유지 (점진적 마이그레이션용)
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
    """기존 코드가 'Tier N' 문자열을 기대 → 호환 래퍼."""
    return f"Tier {tier_for_url(url)}"
