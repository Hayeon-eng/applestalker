"""
Fixed URL Configuration for Apple Tracker
45 Hardcoded URLs - No URL Discovery
These URLs are crawled every time (Tier 0-4)
"""

# Fixed URLs - Apple.com and Samsung.com/sg
# Total: 45 URLs (21 Apple + 24 Samsung)

FIXED_URLS = {
    # ========================================
    # TIER 0: Brand Home (2 URLs)
    # ========================================
    "Tier 0": [
        "https://www.apple.com/",
        "https://www.samsung.com/sg/",
    ],
    
    # ========================================
    # TIER 1: Category Pages (6 URLs)
    # ========================================
    "Tier 1": [
        "https://www.apple.com/iphone/",
        "https://www.apple.com/watch/",
        "https://www.apple.com/airpods/",
        "https://www.samsung.com/sg/smartphones/all-smartphones/",
        "https://www.samsung.com/sg/watches/all-watches/",
        "https://www.samsung.com/sg/audio-sound/all-audio-sound/",
    ],
    
    # ========================================
    # TIER 2: Campaign Pages (8 URLs)
    # ========================================
    "Tier 2": [
        "https://www.apple.com/apple-intelligence/",
        "https://www.apple.com/iphone/compare/",
        "https://www.apple.com/watch/compare/",
        "https://www.samsung.com/sg/mobile/",
        "https://www.samsung.com/sg/galaxy-ai/",
        "https://www.samsung.com/sg/mobile/find-your-galaxy/",
        "https://www.samsung.com/sg/mobile/switch-to-galaxy/",
        "https://www.samsung.com/sg/one-ui/",
    ],
    
    # ========================================
    # TIER 3: Product Detail Pages (14 URLs)
    # ========================================
    "Tier 3": [
        "https://www.apple.com/iphone-17-pro/",
        "https://www.apple.com/iphone-air/",
        "https://www.apple.com/iphone-17/",
        "https://www.apple.com/iphone-17e/",
        "https://www.apple.com/apple-watch-series-11/",
        "https://www.apple.com/apple-watch-ultra-3/",
        "https://www.apple.com/apple-watch-se-3/",
        "https://www.apple.com/airpods-pro/",
        "https://www.samsung.com/sg/smartphones/galaxy-s26-ultra/",
        "https://www.samsung.com/sg/smartphones/galaxy-s26/",
        "https://www.samsung.com/sg/smartphones/galaxy-z-fold7/",
        "https://www.samsung.com/sg/smartphones/galaxy-z-flip7/",
        "https://www.samsung.com/sg/watches/galaxy-watch-ultra-2025/",
        "https://www.samsung.com/sg/audio-sound/galaxy-buds4-pro/",
    ],
    
    # ========================================
    # TIER 4: Commerce/Spec Pages (15 URLs)
    # ========================================
    "Tier 4": [
        "https://www.apple.com/iphone-17-pro/specs/",
        "https://www.apple.com/iphone-air/specs/",
        "https://www.apple.com/iphone-17/specs/",
        "https://www.apple.com/iphone-17e/specs/",
        "https://www.apple.com/apple-watch-series-11/specs/",
        "https://www.apple.com/apple-watch-ultra-3/specs/",
        "https://www.apple.com/apple-watch-se-3/specs/",
        "https://www.apple.com/airpods-pro/specs/",
        "https://www.apple.com/shop/buy-iphone",
        "https://www.samsung.com/sg/smartphones/galaxy-s26-ultra/buy/",
        "https://www.samsung.com/sg/smartphones/galaxy-s26/buy/",
        "https://www.samsung.com/sg/smartphones/galaxy-z-fold7/buy/",
        "https://www.samsung.com/sg/smartphones/galaxy-z-flip7/buy/",
        "https://www.samsung.com/sg/watches/galaxy-watch-ultra-2025/buy/",
        "https://www.samsung.com/sg/audio-sound/galaxy-buds4-pro/buy/",
    ],
}

# Flatten all URLs for easy iteration
ALL_URLS = []
for tier, urls in FIXED_URLS.items():
    ALL_URLS.extend(urls)

# URL to Tier mapping
URL_TO_TIER = {}
for tier, urls in FIXED_URLS.items():
    for url in urls:
        URL_TO_TIER[url] = tier


def get_all_urls() -> list:
    """Return all 45 fixed URLs"""
    return ALL_URLS.copy()


def get_urls_by_tier(tier: str) -> list:
    """Return URLs for a specific tier"""
    return FIXED_URLS.get(tier, []).copy()


def get_tier_for_url(url: str) -> str:
    """Return the tier level for a given URL"""
    return URL_TO_TIER.get(url, "Unknown")


def get_apple_urls() -> list:
    """Return all Apple URLs"""
    return [url for url in ALL_URLS if 'apple.com' in url]


def get_samsung_urls() -> list:
    """Return all Samsung URLs"""
    return [url for url in ALL_URLS if 'samsung.com' in url]
