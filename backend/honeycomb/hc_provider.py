"""
hc_provider.py — honeyComb 수집 계층 [2026-09 · 수집 방식 확정: SERP API(SerpApi)]

엔진/화면은 provider 가 돌려주는 표준 결과만 본다.
  fetch_shopping(country, keyword) -> {"items": [...], "fetched_at", "provider", "raw_ref"}
    item: {position, title, merchant, price, extracted_price, rating, reviews, delivery, link, product_id, thumbnail,
           is_samsung_store, attrs{code: value}}
  fetch_product_detail(country, item) -> {code: value}   # 제품 상세(설명·이미지·영상·하이라이트·스펙…)

구현체
  SerpApiProvider : SerpApi google_shopping / google_product 엔진. 환경변수 SERPAPI_KEY 필요.
                    ⚠ 응답 필드 매핑은 SerpApi 문서 기준으로 작성했고 실호출로 검증하지 못했다(이 환경은 외부 접근 불가).
                    첫 실행에서 원본 응답을 runs/<run_id>/raw/ 에 저장하므로, 그 파일을 보고 매핑을 보정한다.
  MockProvider    : hc_mock_data.json(.gz) 재생(검토용). 키가 없으면 자동 선택.
"""
from __future__ import annotations
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

_HERE = os.path.dirname(__file__)


class Provider:
    name = "base"

    def fetch_shopping(self, country: Dict[str, Any], keyword: str) -> Dict[str, Any]:
        raise NotImplementedError

    def fetch_product_detail(self, country: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
        return {}


# ── 목업 ──────────────────────────────────────────────────────────────
class MockProvider(Provider):
    name = "mock"

    def __init__(self, path: Optional[str] = None):
        import gzip
        base = path or os.path.join(_HERE, "hc_mock_data.json")
        if os.path.exists(base):
            self.path = base; self.data = json.load(open(base, encoding="utf-8"))
        elif os.path.exists(base + ".gz"):
            self.path = base + ".gz"
            with gzip.open(self.path, "rt", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.path = base
            self.data = {"config": {"top_n": 8, "countries": [], "products": [], "status_legend": {}}, "attributes": [], "runs": []}

    def config(self) -> Dict[str, Any]:
        # [2026-09-11] 국가·제품 설정은 hc_config.json 이 원본(목업 파일과 무관하게 항상 존재) — 목업은 폴백
        p = os.path.join(_HERE, "hc_config.json")
        if os.path.exists(p):
            try:
                c = json.load(open(p, encoding="utf-8")); c.pop("_note", None)
                if c.get("countries") and c.get("products"):
                    return c
            except Exception:
                pass
        return self.data["config"]

    def attributes(self) -> List[Dict[str, Any]]:
        p = os.path.join(_HERE, "hc_attributes.json")
        if os.path.exists(p):
            try:
                a = json.load(open(p, encoding="utf-8")).get("attributes") or []
                if a:
                    return a
            except Exception:
                pass
        return self.data["attributes"]

    def runs(self) -> List[Dict[str, Any]]:
        return self.data["runs"]


# ── SerpApi ───────────────────────────────────────────────────────────
def _is_samsung(merchant: str, link: str) -> bool:
    m = (merchant or "").lower()
    host = (urlparse(link or "").netloc or "").lower()
    return ("samsung" in m and not any(x in m for x in ("amazon", "ebay", "shopee", "lazada", "flipkart", "check24"))) or host.endswith("samsung.com")


def _num(v) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


class SerpApiProvider(Provider):
    name = "serpapi"
    BASE = "https://serpapi.com/search.json"

    def __init__(self, api_key: Optional[str] = None, raw_dir: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY", "")
        self.raw_dir = raw_dir
        self.min_interval = float(os.getenv("SERPAPI_MIN_INTERVAL", "1.2"))  # 초 — 무료/저가 요금제 rate limit 완화
        self._last = 0.0
        self.calls = 0

    def _get(self, params: Dict[str, Any], tag: str) -> Dict[str, Any]:
        import httpx
        wait = self.min_interval - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        r = httpx.get(self.BASE, params={**params, "api_key": self.api_key, "output": "json"}, timeout=60, verify=(os.getenv("QB_SSL_VERIFY", "true").lower() != "false"))
        self._last = time.time(); self.calls += 1
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise RuntimeError(f"SerpApi: {data['error']}")
        if self.raw_dir:
            os.makedirs(self.raw_dir, exist_ok=True)
            json.dump(data, open(os.path.join(self.raw_dir, f"{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False)
        return data

    def fetch_shopping(self, country: Dict[str, Any], keyword: str) -> Dict[str, Any]:
        tag = f"shop_{country['code']}_{''.join(ch if ch.isalnum() else '_' for ch in keyword)[:40]}"
        data = self._get({"engine": "google_shopping", "q": keyword, "gl": country["gl"], "hl": country["hl"], "num": 40}, tag)
        items = []
        for i, s in enumerate(data.get("shopping_results") or [], 1):
            link = s.get("product_link") or s.get("link") or ""
            merchant = s.get("source") or s.get("seller") or ""
            item = {"position": s.get("position") or i, "title": s.get("title"), "merchant": merchant, "price": s.get("price"),
                    "extracted_price": s.get("extracted_price"), "old_price": s.get("old_price"), "rating": s.get("rating"),
                    "reviews": s.get("reviews"), "delivery": s.get("delivery"), "link": link, "product_id": s.get("product_id"),
                    "thumbnail": s.get("thumbnail"), "tag": s.get("tag") or s.get("badge"), "is_samsung_store": _is_samsung(merchant, link)}
            # 검색 결과 카드에서 바로 관측되는 GMC 속성
            attrs = {"title": s.get("title"), "price": s.get("price"), "image_link": s.get("thumbnail"),
                     "shipping": s.get("delivery"), "availability": "in stock" if s.get("price") else None}
            if s.get("old_price") or s.get("extracted_old_price"):
                attrs["sale_price"] = s.get("price")
            if s.get("second_hand_condition"):
                attrs["condition"] = s.get("second_hand_condition")
            elif s.get("title"):
                attrs["condition"] = "new(추정)"
            if s.get("title") and "samsung" in str(s.get("title")).lower():
                attrs["brand"] = "Samsung"
            item["attrs"] = {k: v for k, v in attrs.items() if v not in (None, "", [])}
            items.append(item)
        # 인라인 광고(ads)·서로 다른 블록은 위치가 별도 → 문서상 shopping_results 만 순위로 본다
        return {"items": items, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "provider": self.name,
                "raw_ref": (data.get("search_metadata") or {}).get("json_endpoint"), "total": len(items)}

    def fetch_product_detail(self, country: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
        pid = item.get("product_id")
        if not pid:
            return {}
        tag = f"prod_{country['code']}_{pid}"
        data = self._get({"engine": "google_product", "product_id": pid, "gl": country["gl"], "hl": country["hl"]}, tag)
        pr = data.get("product_results") or {}
        out: Dict[str, Any] = {}
        if pr.get("title"):
            out["title"] = pr["title"]
        if pr.get("description"):
            out["description"] = pr["description"]
        media = pr.get("media") or []
        imgs = [m for m in media if (m.get("type") or "image") == "image"]
        vids = [m for m in media if m.get("type") == "video"]
        if imgs:
            out["image_link"] = imgs[0].get("link")
        if len(imgs) >= 2:
            out["additional_image_link"] = f"{len(imgs) - 1} more"
        if vids:
            out["video_link"] = vids[0].get("link")
        if pr.get("highlights"):
            out["product_highlight"] = " | ".join(str(h) for h in pr["highlights"])[:300]
        for key in ("specs", "specs_results", "extensions"):
            if pr.get(key) or data.get(key):
                out["product_detail"] = json.dumps(pr.get(key) or data.get(key), ensure_ascii=False)[:300]; break
        if pr.get("rating") is not None:
            out["_rating"] = pr.get("rating"); out["_reviews"] = pr.get("reviews")
        sellers = ((data.get("sellers_results") or {}).get("online_sellers")) or []
        for s in sellers:
            if _is_samsung(s.get("name", ""), s.get("link", "")):
                if s.get("base_price"):
                    out["price"] = s["base_price"]
                if s.get("additional_price") is not None:
                    out["shipping"] = str(s.get("additional_price"))
                if s.get("condition"):
                    out["condition"] = s["condition"]
                out["link"] = s.get("link")
                break
        if data.get("reviews_results"):
            out["_has_reviews"] = True
        return out


def get_provider(kind: Optional[str] = None, raw_dir: Optional[str] = None) -> Provider:
    kind = (kind or os.getenv("HC_PROVIDER") or ("serpapi" if os.getenv("SERPAPI_KEY") else "mock")).lower()
    if kind == "serpapi":
        return SerpApiProvider(raw_dir=raw_dir)
    return MockProvider()
