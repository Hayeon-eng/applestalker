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

    def fetch_product_detail(self, country: Dict[str, Any], item: Dict[str, Any], brand: str = "samsung") -> Dict[str, Any]:
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
        # [2026-09-14] 광고(Sponsored) 제외 후 오가닉(자연 결과)만으로 position 재부여.
        #   판정 기준: SerpApi 는 광고를 별도 배열(shopping_ads/ads)로 주거나, 항목의 tag/extensions 에 'Sponsored' 표시.
        #   ads 배열의 항목은 순위 계산에서 제외하고, shopping_results 안에 섞인 sponsored 표시 항목도 제외한다.
        raw = data.get("shopping_results") or []

        def _is_ad(x: Dict[str, Any]) -> bool:
            tag = str(x.get("tag") or x.get("badge") or "").lower()
            exts = " ".join(str(e) for e in (x.get("extensions") or [])).lower()
            if "sponsor" in tag or "sponsor" in exts or "ad" == tag or "광고" in tag:
                return True
            if x.get("sponsored") is True or x.get("ad") is True:
                return True
            # aclk 리다이렉트 링크(광고 클릭 추적)면 광고로 본다
            lk = str(x.get("product_link") or x.get("link") or "")
            return "aclk" in lk or "/aclk?" in lk
        organic = [x for x in raw if not _is_ad(x)]
        ad_count = len(raw) - len(organic)
        items = []
        for i, s in enumerate(organic, 1):   # position 을 오가닉 기준으로 1부터 다시 매김
            link = s.get("product_link") or s.get("link") or ""
            merchant = s.get("source") or s.get("seller") or ""
            item = {"position": i, "title": s.get("title"), "merchant": merchant, "price": s.get("price"),  # position=오가닉 재부여(광고 제외)
                    "extracted_price": s.get("extracted_price"), "old_price": s.get("old_price"), "rating": s.get("rating"),
                    "reviews": s.get("reviews"), "delivery": s.get("delivery"), "link": link, "product_id": s.get("product_id"),
                    # [2026-09-14] 상세는 이제 immersive product 방식 — shopping 결과의 토큰/링크를 그대로 넘겨 상세를 받는다
                    "immersive_token": s.get("immersive_product_page_token"),
                    "serpapi_immersive": s.get("serpapi_immersive_product_api"),
                    "serpapi_product_link": s.get("serpapi_product_api") or s.get("serpapi_product_link"),
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
                "raw_ref": (data.get("search_metadata") or {}).get("json_endpoint"), "total": len(items),
                "ads_excluded": ad_count + len(data.get("shopping_ads") or data.get("ads") or [])}

    def fetch_product_detail(self, country: Dict[str, Any], item: Dict[str, Any], brand: str = "samsung") -> Dict[str, Any]:
        # [2026-09-14] Google 이 상세를 immersive product 로 바꾸면서 옛 product_id → google_product 방식은
        # 대부분 실패한다. 우선순위: ① immersive_product_page_token → google_immersive_product
        #                          ② product_id → google_product(폴백, 구형 항목용)
        # 어느 쪽도 없거나 실패하면 {} 반환(호출측이 카드 속성만으로 진행하고 순위는 보존).
        cc = country["code"]
        token = item.get("immersive_token")
        data = None
        if token:
            tag = f"prod_{cc}_immersive_{abs(hash(token)) % 10**8}"
            data = self._get({"engine": "google_immersive_product", "page_token": token,
                              "gl": country["gl"], "hl": country["hl"]}, tag)
        elif item.get("product_id"):
            pid = str(item["product_id"])
            tag = f"prod_{cc}_{pid}"
            data = self._get({"engine": "google_product", "product_id": pid, "gl": country["gl"], "hl": country["hl"]}, tag)
        else:
            return {}
        # 두 엔진 모두 product_results 로 반환(immersive 는 필드 일부만 채워질 수 있음)
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
        def _brand_seller(sd):
            if brand == "samsung":
                return _is_samsung(sd.get("name", ""), sd.get("link", ""))
            nm = (sd.get("name") or "").lower(); host = (urlparse(sd.get("link") or "").netloc or "").lower()
            return (brand in nm and "amazon" not in nm and "ebay" not in nm) or host.endswith(f"{brand}.com")
        for s in sellers:
            if _brand_seller(s):
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
        # [2026-11 D4③] 위에서 명시적으로 읽는 키 외에, 상세 응답 JSON 전체에서 GMC 속성명을 찾아 보강한다.
        #   SerpApi 상세 응답 구조가 엔진·국가별로 달라 특정 경로를 가정하지 않고, 키 이름(또는 스펙 표의 항목명)이
        #   속성 동의어와 일치하면 '보임'으로 기록한다. 값에는 출처 경로를 붙여 화면에서 검증할 수 있게 한다.
        for code, val in _deep_attr_scan(data).items():
            out.setdefault(code, val)
        return out


# ── [2026-11 D4③] 상세 응답 전체 탐색 ─────────────────────────────────────────
# 토큰 단위로 일치하는 경우만 인정(부분 문자열 금지) — 'type' 같은 범용 키로 생기는 오탐을 막는다.
_ATTR_SYNONYMS = {
    "gtin": ["gtin", "ean", "upc", "isbn", "jan"],
    "mpn": ["mpn", "model number", "model no", "part number", "manufacturer part number", "modellnummer", "référence"],
    "color": ["color", "colour", "colors", "colours", "farbe", "couleur", "colore"],
    "size": ["size", "sizes", "storage", "capacity", "speicher", "stockage", "memory"],
    "material": ["material", "materials", "matériau"],
    "product_weight": ["weight", "gewicht", "poids", "peso"],
    "product_length": ["length", "länge", "longueur"],
    "product_width": ["width", "breite", "largeur"],
    "product_height": ["height", "höhe", "hauteur", "dimensions", "abmessungen"],
    "certification": ["certification", "certifications"],
    "energy_efficiency_class": ["energy efficiency", "energy class", "energieeffizienzklasse"],
    "question_and_answer": ["questions", "questions and answers", "q and a"],
    "related_product": ["related products", "related", "similar products", "similar"],
    "variant_option": ["variants", "variant", "configurations"],
    "availability_date": ["availability date", "release date", "pre order", "preorder"],
    "promotion_id": ["promotion", "promotions", "deals", "offer details"],
    "virtual_model_link": ["3d model", "view in 3d", "ar model"],
    "document_link": ["manual", "manuals", "documents", "user guide"],
    "popularity_rank": ["rank", "best seller", "bestseller", "popularity"],
    "google_product_category": ["category", "categories", "breadcrumbs", "breadcrumb"],
    "installment": ["installment", "installments", "financing", "monthly payment"],
    "free_shipping_threshold": ["free shipping", "free delivery"],
}


def _norm_tok(s: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9äöüéèàç ]+", " ", (s or "").lower()).strip()


def _deep_attr_scan(data: Any) -> Dict[str, str]:
    found: Dict[str, str] = {}
    syn = {code: {_norm_tok(x) for x in xs} for code, xs in _ATTR_SYNONYMS.items()}

    def hit(name: str, value: Any, path: str):
        n = _norm_tok(name.replace("_", " "))
        if not n or value in (None, "", [], {}):
            return
        for code, names in syn.items():
            if code in found:
                continue
            if n in names:
                v = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                found[code] = f"{str(v)[:120]}  [출처: {path}]"

    def walk(o: Any, path: str, depth: int = 0):
        if depth > 6:
            return
        if isinstance(o, dict):
            # 스펙 표 형태 {name/title/key: ..., value: ...}
            label = o.get("name") or o.get("title") or o.get("key") or o.get("label")
            if isinstance(label, str) and ("value" in o or "values" in o):
                hit(label, o.get("value") or o.get("values"), f"{path}.{label}")
            for k, v in o.items():
                if isinstance(k, str):
                    hit(k, v, f"{path}.{k}")
                walk(v, f"{path}.{k}", depth + 1)
        elif isinstance(o, list):
            for i, v in enumerate(o[:60]):
                walk(v, f"{path}[{i}]", depth + 1)

    walk(data, "detail")
    return found


def get_provider(kind: Optional[str] = None, raw_dir: Optional[str] = None) -> Provider:
    kind = (kind or os.getenv("HC_PROVIDER") or ("serpapi" if os.getenv("SERPAPI_KEY") else "mock")).lower()
    if kind == "serpapi":
        return SerpApiProvider(raw_dir=raw_dir)
    return MockProvider()
