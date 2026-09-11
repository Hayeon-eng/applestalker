"""
seo_checker.py — 큐비 🐝 SEO 요소 검수 [2026-09 신규 — D2·D3·D4·D5·D6·D7]

사람 검수 리포트(Flagship SEO QA Report)의 Issue Dictionary 를 코드로 옮긴 것.
html_qa_scoring(Level1/2 채점)과 schema_checker(JSON-LD)는 건드리지 않고, 그 둘이 보지 않던
아래 항목만 추가한다. 모든 판정은 서버 HTML(소스)만으로 가능하다 — 렌더 불필요.

  Canonical Tag      No canonical link present / Should be canonicalized
  Title Tag          Model name missing / Model name incomplete / Wrong model name in tag /
                     Country tail missing / Country tail duplicate / Samsung keyword missing /
                     Spec keyword missing(Specs 페이지만)
  Meta Description   Model name missing / Wrong model name in tag / Insufficient Description
                     (Duplicate 는 페이지 간 비교라 qb_routes_run 의 런 단위 집계에서 붙인다 → mark_duplicates)
  Google Discover    No robots meta tag (robots meta 부재) · directive 미포함은 warn
  Breadcrumb         No breadcrumb / Wrong breadcrumb structure / Wrong breadcrumb label /
                     Breadcrumb link missing / Wrong breadcrumb link inserted

결과: {"items": [ {element, issue, status(pass|warn|fail), value, fix, detail} ... ]}
      status 기준: 사람 리포트가 '오류'로 세는 항목 = fail, 판정 근거가 약한 항목 = warn.

설정(seo_rules.json): 브랜드 현지어, Spec 키워드 사전, 임계값 — 코드 수정 없이 조정.
모델명 토큰: runner._schema_values()[market_product]["name_tokens"] (model_any/tier_any) 재사용.
"""
from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

_HERE = os.path.dirname(__file__)
_CFG_CACHE: Optional[Dict[str, Any]] = None


def _cfg() -> Dict[str, Any]:
    global _CFG_CACHE
    if _CFG_CACHE is None:
        with open(os.path.join(_HERE, "seo_rules.json"), encoding="utf-8") as f:
            _CFG_CACHE = json.load(f)
    return _CFG_CACHE


# ── 사람 리포트 Dictionary 의 Fix Guideline (영문 그대로 — 엑셀 To-Be 로 사용) ──
FIX = {
    "No canonical link present": "Add a canonical tag to the page and set the canonical value to the page URL.",
    "Should be canonicalized": "The canonical URL differs from the current page URL. Update the canonical URL to match the page URL.",
    "Title tag missing": "Add a Title tag to the page. Include the model name and key keywords.",
    "Model name missing": "Add the model name for this page to the Title tag.",
    "Model name incomplete": "The model name in the Title is incomplete. Update it to the full, correct model name.",
    "Wrong model name in tag": "The tag contains an incorrect model name. Replace it with the correct model name for this page.",
    "Country tail missing": "Add the Country Tail in the format '| Samsung [Country]' at the end of the Title.",
    "Country tail duplicate": "The Title contains a duplicate Country Tail. Remove the duplicate and keep only one.",
    "Samsung keyword missing": "Add the 'Samsung' keyword to the Title.",
    "Spec keyword missing": "Add the product spec keyword to the Title.",
    "Meta description missing": "Add a Meta Description tag to the page. Include the model name and key features.",
    "Insufficient Description": "The Meta Description content is insufficient. Rewrite it to include the model name, key features, and benefits.",
    "Duplicate": "This Meta Description is identical to another page. Write a unique description specific to this page.",
    "No robots meta tag": "In PIM, enable the Maximum size image preview option under Robot Instruction.",
    "Robots directive missing": "Add 'max-image-preview:large' to the robots meta tag (Google Discover).",
    "No breadcrumb": "Add breadcrumb navigation to the page.",
    "Wrong breadcrumb structure": "The breadcrumb structure is incorrect. Update it to match the site hierarchy.",
    "Wrong breadcrumb label": "The product step of the breadcrumb shows a different model name than this page. Correct the label so it names this page's model.",
    "Breadcrumb link missing": "Add the correct link to each step in the breadcrumb.",
    "Wrong breadcrumb link inserted": "The breadcrumb contains an incorrect link. Replace it with the correct URL.",
}


def _norm_url(u: str) -> str:
    """스킴/호스트 소문자, 쿼리·프래그먼트 제거, 트레일링 슬래시 제거."""
    if not u:
        return ""
    p = urlparse(u.strip())
    host = (p.netloc or "").lower()
    path = (p.path or "/").rstrip("/") or "/"
    return f"{host}{path}".lower()


def _site_of(url: str) -> Dict[str, str]:
    """페이지 URL → {host, sitecode}. samsung.com.cn 은 경로에 사이트코드가 없다(cn)."""
    p = urlparse(url or "")
    host = (p.netloc or "").lower()
    segs = [s for s in (p.path or "").split("/") if s]
    if host.endswith("samsung.com.cn"):
        return {"host": host, "sitecode": "cn"}
    return {"host": host, "sitecode": (segs[0].lower() if segs else "")}


def _model_tokens(name_tokens: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    nt = name_tokens or {}
    return {"model": [t for t in (nt.get("model_any") or []) if t],
            "tier": [t for t in (nt.get("tier_any") or []) if t],
            "forbid": [t for t in (nt.get("forbid_any") or []) if t]}


def _has_any(text: str, tokens: List[str]) -> bool:
    low = (text or "").lower()
    return any(t.lower() in low for t in tokens if t)


def _strip_all(text: str, tokens: List[str]) -> str:
    out = text or ""
    for t in sorted([t for t in tokens if t], key=len, reverse=True):
        out = re.sub(re.escape(t), " ", out, flags=re.IGNORECASE)
    return out


def _model_name_issue(text: str, self_tokens: Dict[str, List[str]],
                      other_tokens: List[str]) -> Optional[str]:
    """Title/Meta 텍스트의 모델명 판정 → None | 'Model name missing' | 'Model name incomplete'
    | 'Wrong model name in tag'.
    · 자기 모델 토큰(Fold8/폴드8…) 없음 → missing (다른 제품 토큰이 있으면 wrong)
    · 자기 모델은 있으나 tier(Ultra 등) 누락 → incomplete
    · 자기 토큰을 지운 뒤에도 다른 제품 토큰이 남아 있으면 → wrong
      (fold8-ultra 페이지에서 'Fold8'⊂'Fold8 Ultra' 가 오검출되지 않게 자기 토큰을 먼저 제거)"""
    if not self_tokens["model"]:
        return None  # 기준 토큰 없음 → 판정하지 않음(거짓 O/X 금지)
    has_model = _has_any(text, self_tokens["model"])
    has_tier = (not self_tokens["tier"]) or _has_any(text, self_tokens["tier"])
    residual = _strip_all(text, self_tokens["model"] + self_tokens["tier"])
    has_other = _has_any(residual, other_tokens) or _has_any(text, self_tokens["forbid"])
    if not has_model:
        if has_other:
            return "Wrong model name in tag"
        # 패밀리명(Fold/Flip/Watch…)만 있고 세대 숫자가 빠진 경우 → incomplete (ch 사례 'Samsung Galaxy Z Flip')
        families = {re.sub(r"[\d\s]+.*$", "", t).strip() for t in self_tokens["model"]}
        families = {f for f in families if len(f) >= 3}
        if families and _has_any(text, sorted(families)):
            return "Model name incomplete"
        return "Model name missing"
    if has_other:
        return "Wrong model name in tag"
    if not has_tier:
        return "Model name incomplete"
    return None


# 라틴 외 문자 체계(아랍·히브리·타이·키릴·그리스·데바나가리·한자·가나·한글) — 모델명이 현지어로
# 음차될 수 있는 스크립트. 토큰 사전은 이 중 일부 언어만 등록돼 있다.
_NONLATIN_RX = re.compile(r"[\u0600-\u06FF\u0590-\u05FF\u0E00-\u0E7F\u0400-\u04FF\u0370-\u03FF"
                          r"\u0900-\u097F\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]")


def _downgrade_if_nonlatin(issue: str, text: str):
    """'missing/incomplete' 인데 텍스트에 비라틴 스크립트가 섞여 있으면 현지어 음차 모델명
    (جالاكسي زد فليب8 등)일 가능성이 커 fail 대신 warn 으로 내리고 사유를 남긴다
    (sa 사례: 사람 검수는 아랍어 모델명을 정상으로 봄 — 거짓 오류 방지).
    'Wrong model name'(다른 제품 토큰이 실제로 있음)은 그대로 fail.
    반환: (status, value, detail) — add() 의 뒤 인자로 전개."""
    if issue in ("Model name missing", "Model name incomplete") and _NONLATIN_RX.search(text or ""):
        return ("warn", text, "비라틴(현지어) 표기 — 모델명 토큰 사전(name_tokens/product_aliases) 미등록 가능, 사람 확인")
    return ("fail", text, "")


def _extract_breadcrumb(soup: BeautifulSoup, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """BreadcrumbList JSON-LD 우선, 없으면 DOM nav. → {"source": ldjson|dom|None, "items": [{name, url}]}"""
    for n in nodes:
        types = n.get("@type")
        types = types if isinstance(types, list) else [types]
        if "BreadcrumbList" in [str(t) for t in types]:
            items = []
            for el in (n.get("itemListElement") or []):
                if not isinstance(el, dict):
                    continue
                it = el.get("item")
                name = el.get("name") or (it.get("name") if isinstance(it, dict) else None)
                url = None
                if isinstance(it, dict):
                    url = it.get("@id") or it.get("url")
                elif isinstance(it, str):
                    url = it
                items.append({"name": str(name or "").strip(), "url": str(url or "").strip(),
                              "position": el.get("position")})
            items.sort(key=lambda x: (x.get("position") is None, x.get("position") or 0))
            return {"source": "ldjson", "items": items}
    for sel in _cfg().get("breadcrumb_dom_selectors", []):
        try:
            nav = soup.select_one(sel)
        except Exception:
            nav = None
        if nav is None:
            continue
        items = []
        for li in nav.find_all(["li", "a", "span"]):
            if li.name == "li":
                a = li.find("a")
                items.append({"name": li.get_text(" ", strip=True), "url": (a.get("href") if a else "") or ""})
        if not items:
            for a in nav.find_all("a"):
                items.append({"name": a.get_text(" ", strip=True), "url": a.get("href") or ""})
        if items:
            return {"source": "dom", "items": items}
    return {"source": None, "items": []}


def check_seo(html: str, page_url: str, page_type: str = "PDP",
              name_tokens: Optional[Dict[str, Any]] = None,
              other_model_tokens: Optional[List[str]] = None,
              final_url: Optional[str] = None) -> Dict[str, Any]:
    cfg = _cfg()
    soup = BeautifulSoup(html or "", "lxml")
    import schema_checker
    nodes = schema_checker.extract_jsonld(html or "")
    items: List[Dict[str, Any]] = []
    self_tok = _model_tokens(name_tokens)
    other_tok = list(other_model_tokens or [])
    site = _site_of(final_url or page_url)

    def add(element, issue, status, value="", detail=""):
        items.append({"element": element, "issue": issue, "status": status,
                      "value": (value or "")[:300], "fix": FIX.get(issue, ""), "detail": detail})

    # ── Canonical (D2) ──
    canon = soup.find("link", rel=lambda v: v and "canonical" in [x.lower() for x in (v if isinstance(v, list) else [v])])
    canon_href = (canon.get("href") or "").strip() if canon else ""
    if not canon_href:
        add("Canonical Tag", "No canonical link present", "fail", "")
    else:
        cmp_url = final_url or page_url
        if _norm_url(canon_href) != _norm_url(cmp_url):
            add("Canonical Tag", "Should be canonicalized", "fail", canon_href, f"page={cmp_url}")
        else:
            add("Canonical Tag", "OK", "pass", canon_href)

    # ── Title (D4·D5·D11) ──
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    if not title:
        add("Title Tag", "Title tag missing", "fail", "")
    else:
        mi = _model_name_issue(title, self_tok, other_tok)
        if mi:
            add("Title Tag", mi, *_downgrade_if_nonlatin(mi, title), )
        if not _has_any(title, cfg["brand_words"]):
            add("Title Tag", "Samsung keyword missing", "fail", title)
        tail_rx = re.compile(cfg["country_tail_regex"], re.IGNORECASE)
        segs = [s.strip() for s in title.split("|") if s.strip()]
        # '브랜드+국가' 꼬리 세그먼트: 브랜드어 포함, 4단어 이하, 제품/패밀리명은 없음
        # ('Samsung Galaxy Z Flip' 같은 제품 세그먼트를 꼬리로 오인하지 않게 — ch 사례)
        fam = self_tok["model"] + self_tok["tier"] + ["galaxy", "fold", "flip", "watch", "buds", "tab", "book"]
        brand_segs = [s for s in segs if _has_any(s, cfg["brand_words"]) and len(s.split()) <= 4
                      and not _has_any(s, fam)]
        # 중복: 브랜드+국가 형태의 세그먼트가 2개 이상, 또는 동일 세그먼트 반복
        dup = len(brand_segs) >= 2 or len(segs) != len({s.lower() for s in segs})
        if dup:
            add("Title Tag", "Country tail duplicate", "fail", title, " | ".join(brand_segs))
        elif not tail_rx.search(title):
            # 기대 국가명 사전이 없어 '형식 부재'만 확인 → warn (사람 검수는 오류로 셈 — 국가명 사전 연결 시 fail 로 승격)
            add("Title Tag", "Country tail missing", "warn", title)
        if page_type == "Specs" and not _has_any(title, cfg["spec_keywords"]):
            add("Title Tag", "Spec keyword missing", "warn", title, "spec_keywords 사전 기준(미등록 언어면 사전 보강)")
        # (길이 초과 warn 은 기존 html_qa 행(Meta Title Length)이 이미 내므로 여기선 중복 보고하지 않음)
        if not any(i["element"] == "Title Tag" and i["status"] != "pass" for i in items):
            add("Title Tag", "OK", "pass", title)

    # ── Meta Description (D6 — 페이지 단위) ──
    md = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    desc = (md.get("content") or "").strip() if md else ""
    if not desc:
        add("Meta Description", "Meta description missing", "fail", "")
    else:
        mi = _model_name_issue(desc, self_tok, other_tok)
        if mi == "Model name incomplete":
            mi = None  # 설명문은 tier 생략이 흔해 불완전은 잡지 않음(사람 Dictionary 에는 있으나 보수적으로)
        if mi:
            add("Meta Description", mi, *_downgrade_if_nonlatin(mi, desc))
        if len(desc) < int(cfg.get("meta_description_min_chars", 50)):
            add("Meta Description", "Insufficient Description", "warn", desc, f"{len(desc)} chars")
        if not any(i["element"] == "Meta Description" and i["status"] != "pass" for i in items):
            add("Meta Description", "OK", "pass", desc)

    # ── Google Discover / robots (D3) ──
    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    rc = (robots.get("content") or "").strip() if robots else ""
    need = cfg.get("robots_required_directive", "max-image-preview:large")
    if not robots:
        add("Google Discover Opt.", "No robots meta tag", "fail", "")
    elif need and need.replace(" ", "").lower() not in rc.replace(" ", "").lower():
        add("Google Discover Opt.", "Robots directive missing", "warn", rc, f"expected '{need}'")
    else:
        add("Google Discover Opt.", "OK", "pass", rc)

    # ── Breadcrumb (D7) ──
    bc = _extract_breadcrumb(soup, nodes)
    bitems = bc["items"]
    if not bitems:
        add("Breadcrumb", "No breadcrumb", "fail", "")
    else:
        crumb_txt = " > ".join(i["name"] for i in bitems)
        problems = 0
        if len(bitems) < int(cfg.get("breadcrumb_min_items", 3)):
            add("Breadcrumb", "Wrong breadcrumb structure", "fail", crumb_txt, f"{len(bitems)} items")
            problems += 1
        last = bitems[-1]
        # [2026-09] 단수 부족으로 이미 구조 오류를 냈으면 '마지막 단계가 제품 아님'은 같은 사실의 중복 → 1행만
        if problems == 0 and self_tok["model"] and not _has_any(last["name"], self_tok["model"]):
            # 마지막 단계가 제품이 아니면 구조 오류(kz_kz 사례 'home > mobile > smartphones'),
            # 제품인데 다른 모델명이면 라벨 오류. 현지어 음차 라벨은 사전 미등록 가능 → warn.
            if _has_any(last["name"], other_tok):
                add("Breadcrumb", "Wrong breadcrumb label", "fail", crumb_txt, last["name"])
            elif _NONLATIN_RX.search(last["name"] or ""):
                add("Breadcrumb", "Breadcrumb label unverifiable", "warn", crumb_txt,
                    f"last step '{last['name']}' — 현지어 표기, 모델 토큰 사전 미등록 가능(사람 확인)")
            else:
                add("Breadcrumb", "Wrong breadcrumb structure", "fail", crumb_txt,
                    f"last step '{last['name']}' is not the product")
            problems += 1
        missing_links = [i["name"] for i in bitems[:-1] if not i.get("url")]
        if missing_links:
            add("Breadcrumb", "Breadcrumb link missing", "fail", crumb_txt, ", ".join(missing_links))
            problems += 1
        wrong = []
        for i in bitems:
            u = i.get("url") or ""
            if not u:
                continue
            p = urlparse(u)
            host = (p.netloc or "").lower()
            segs = [s for s in (p.path or "").split("/") if s]
            if host and site["host"] and host != site["host"]:
                wrong.append(u); continue
            if site["sitecode"] == "cn":
                if segs and segs[0].lower() == "cn":   # samsung.com.cn/cn/… 은 존재하지 않는 경로
                    wrong.append(u)
            elif site["sitecode"] and segs and segs[0].lower() != site["sitecode"]:
                wrong.append(u)
        if wrong:
            add("Breadcrumb", "Wrong breadcrumb link inserted", "fail", crumb_txt, " ; ".join(wrong[:3]))
            problems += 1
        if not problems:
            add("Breadcrumb", "OK", "pass", crumb_txt)

    summary = {"fail": sum(1 for i in items if i["status"] == "fail"),
               "warn": sum(1 for i in items if i["status"] == "warn"),
               "pass": sum(1 for i in items if i["status"] == "pass")}
    return {"summary": summary, "items": items, "title": title, "meta_description": desc,
            "canonical": canon_href, "robots": rc, "breadcrumb": bc}


def mark_duplicates(page_results: List[Dict[str, Any]]) -> int:
    """[D6] 런 단위 — 같은 사이트코드 안에서 서로 다른 URL 이 동일 Meta Description 을 쓰면
    'Duplicate'(fail)를 각 페이지 seo.items 에 추가한다. 반환: 추가된 건수."""
    by_site: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for pr in page_results:
        seo = (pr or {}).get("seo") or {}
        d = (seo.get("meta_description") or "").strip().lower()
        if not d:
            continue
        by_site.setdefault(pr.get("sitecode") or "", {}).setdefault(d, []).append(pr)
    added = 0
    for _site, groups in by_site.items():
        for d, prs in groups.items():
            urls = {p.get("url") for p in prs}
            if len(urls) < 2:
                continue
            for p in prs:
                others = sorted(u for u in urls if u != p.get("url"))
                p["seo"]["items"].append({"element": "Meta Description", "issue": "Duplicate", "status": "fail",
                                          "value": p["seo"].get("meta_description", "")[:300],
                                          "fix": FIX["Duplicate"], "detail": "same as: " + " ; ".join(others[:3])})
                p["seo"]["summary"]["fail"] = p["seo"]["summary"].get("fail", 0) + 1
                added += 1
    return added


def other_model_tokens_for(market_product: Optional[str], schema_values: Dict[str, Any]) -> List[str]:
    """다른 제품들의 model_any 토큰(자기 제품 제외) — 'Wrong model name' 판정용."""
    out: List[str] = []
    for slug, sv in (schema_values or {}).items():
        if slug == market_product:
            continue
        for t in ((sv or {}).get("name_tokens") or {}).get("model_any") or []:
            if t and t not in out:
                out.append(t)
    return out
