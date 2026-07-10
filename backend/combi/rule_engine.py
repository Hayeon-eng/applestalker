"""
rule_engine.py — Combi Rule Engine 스켈레톤

[STUB] 아직 실제 크롤러(Google Search → Shopping Shelf → Organic 파싱)가 붙지 않았다.
지금은 Frontend/Backend 스켈레톤 검증용으로 결정적(deterministic) mock 데이터를 반환한다.
실제 구현 시 이 파일의 3개 함수 내부만 크롤 결과 기반 계산으로 교체하면 되도록
반환 스키마(dict 형태)는 이미 최종 형태로 맞춰뒀다.

AI 추론 금지 원칙(PRD 4장) — 여기 로직은 전부 규칙 기반이어야 하며, LLM 호출이 들어가면 안 된다.
"""
import hashlib
from typing import Any, Dict, List

# Coverage Analyzer가 판정하는 Feed Attribute 목록 (PRD 9장)
FEED_ATTRIBUTES = [
    "title", "description", "brand", "gtin", "mpn", "price", "sale_price",
    "availability", "shipping", "return_policy", "product_highlight",
    "lifestyle_image", "additional_image", "video", "3D", "rating",
    "review", "pickup", "color", "size", "material", "pattern",
]

MERCHANTS = ["Samsung.com", "Apple", "Best Buy", "Amazon", "Walmart", "Target"]


def _seed(*parts: str) -> int:
    """prompt/country 조합마다 같은 mock 결과가 나오도록 결정적 시드 생성."""
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:8], 16)


def compute_shelf(prompt_text: str, country: str) -> List[Dict[str, Any]]:
    """[STUB] Shelf Tracker — Organic Shelf 내 제품 위치.

    실제 구현 시: Sponsored 제거 → Organic Shelf만 파싱 → Row/Column/Rank 계산 (PRD 8장)
    """
    seed = _seed(prompt_text, country, "shelf")
    rows = []
    for i in range(6):
        merchant = MERCHANTS[(seed + i) % len(MERCHANTS)]
        rank = i + 1
        rows.append({
            "rank": rank,
            "row": (rank - 1) // 3 + 1,
            "column": (rank - 1) % 3 + 1,
            "above_fold": rank <= 3,
            "merchant": merchant,
            "is_samsung": merchant == "Samsung.com",
            "price": round(199 + ((seed >> i) % 800), 2),
            "rating": round(3.8 + ((seed >> i) % 12) / 10, 1),
            "review_count": (seed >> (i + 3)) % 5000,
        })
    return rows


def compute_coverage(prompt_text: str, country: str, merchant: str = "Samsung.com") -> Dict[str, str]:
    """[STUB] Coverage Analyzer — Feed Attribute Present/Missing/Unknown 판정.

    실제 구현 시: Merchant Feed vs Shopping Card 실 데이터 대조 (PRD 9장)
    """
    seed = _seed(prompt_text, country, merchant)
    result = {}
    for i, attr in enumerate(FEED_ATTRIBUTES):
        bucket = (seed >> i) % 10
        if bucket < 7:
            result[attr] = "present"
        elif bucket < 9:
            result[attr] = "missing"
        else:
            result[attr] = "unknown"
    return result


def find_gaps(prompt_text: str, country: str) -> List[Dict[str, Any]]:
    """[STUB] Commerce Gap Finder — 경쟁사 대비 부족한 Feed/노출 기회 계산.

    실제 구현 시: Competitor Coverage > Samsung Coverage 규칙 + Country별 차이 규칙 (PRD 10장)
    """
    samsung_cov = compute_coverage(prompt_text, country, "Samsung.com")
    gaps = []
    for competitor in ["Apple", "Best Buy"]:
        comp_cov = compute_coverage(prompt_text, country, competitor)
        for attr in FEED_ATTRIBUTES:
            if comp_cov[attr] == "present" and samsung_cov[attr] != "present":
                gaps.append({
                    "attribute": attr,
                    "competitor": competitor,
                    "samsung_status": samsung_cov[attr],
                    "opportunity": f"{competitor}는 '{attr}' 노출 중, Samsung은 미노출 → Feed 보강 기회",
                })
    return gaps
