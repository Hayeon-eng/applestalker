"""
runner.py — 큐비 — Dotcom QA 체커 [오케스트레이터 / Phase E 어댑터]

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

레지스트리의 URL들에 대해:
  fetch_html(url) → HTML 수집  (기존 백엔드 크롤러를 여기에 주입)
  → schema_checker + copy_checker 검수
  → page_results 리스트로 집계 (qa_report 로 Excel/메일 생성 가능)

* 이 샌드박스는 samsung.com 에 접근할 수 없으므로 실제 수집은 기존 크롤러가 담당한다.
  fetch_html 을 주입만 하면 91개 사이트를 순회 검수할 수 있다(네트워크는 호출측 책임).
"""
from __future__ import annotations
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

import schema_checker
import copy_checker
import html_qa_scoring
from site_registry import SiteRegistry

_HERE = os.path.dirname(__file__)


def page_type_from_url(url: str) -> str:
    """URL 경로 → 페이지타입. [2026-09 D1] /specs/ 를 'Specs'로 분리한다 — 기존엔 PDP로
    오분류되어 flagship 스키마 세트가 적용됐다(사람 검수는 PDP·compare·specs·buy 4종)."""
    u = (url or "").lower()
    if re.search(r"/compare(/|$|\?)", u):
        return "Compare"
    if re.search(r"/buy(/|$|\?)", u):
        return "Buying"
    if re.search(r"/specs?(/|$|\?)", u):
        return "Specs"
    return "PDP"


# [2026-09] 크롤 대상에서 Specs 제외(사용자 결정). URL 이 /specs/ 면 분류만 하고 파생 생성은 Buying 만.
DERIVED_PAGE_TYPES = ("Buying",)


def derive_page_url(pdp_url: str, page_type: str) -> str:
    """PDP URL → 파생 페이지 URL(specs/buy). 레지스트리에 없는 페이지타입을 요청받았을 때
    PDP 엔트리에서 생성한다(존재 여부는 크롤 결과 status로 확인 — 404면 Not Checked)."""
    base = (pdp_url or "").split("?")[0].rstrip("/") + "/"
    seg = {"Specs": "specs/", "Buying": "buy/"}.get(page_type)
    return base + seg if seg else pdp_url


def product_from_url(url: str) -> Optional[str]:
    """URL 경로에서 마케팅 제품 판별.
    [2026-07 Phase2] 신모델(Z8/Watch) 추가. 더 구체적인 슬러그(Ultra/Ultra2)를 먼저 검사한다
    (예: galaxy-z-fold8-ultra 는 galaxy-z-fold8 를 부분문자열로 포함하므로 순서가 중요).
    URL 변형(galaxy-fold8=z 생략, -samsung-com-only/-exclusive/-enterprise 접미사)도
    base 슬러그가 부분문자열로 포함되므로 그대로 매칭된다."""
    u = (url or "").lower()
    # ── 신모델 폴더블(Z8) — Ultra 먼저 ──
    if "galaxy-z-fold8-ultra" in u or "galaxy-fold8-ultra" in u:
        return "galaxy-z-fold8-ultra"
    if "galaxy-z-fold8" in u or "galaxy-fold8" in u:
        return "galaxy-z-fold8"
    if "galaxy-z-flip8" in u or "galaxy-flip8" in u:
        return "galaxy-z-flip8"
    # ── 신모델 워치 — Ultra2 먼저(galaxy-watch-ultra2 ⊃ galaxy-watch-ultra) ──
    if "galaxy-watch-ultra2" in u:
        return "galaxy-watch-ultra2"
    if "galaxy-watch9" in u:
        return "galaxy-watch9"
    # ── 구모델(레지스트리에서 미출시국은 크롤하지 않지만, 잔존 URL 안전 검출용으로 유지) ──
    # 폴더블 — 더 구체적인 슬러그를 먼저(fold7/flip7).
    if "galaxy-z-fold7" in u:
        return "galaxy-z-fold7"
    if "galaxy-z-flip7" in u:
        return "galaxy-z-flip7"
    if "galaxy-s26-ultra" in u:
        return "galaxy-s26-ultra"
    if "galaxy-s26-plus" in u or "galaxy-s26+" in u:
        return "galaxy-s26-plus"
    if "galaxy-s26" in u:
        return "galaxy-s26"
    # 워치 — Ultra를 먼저(워치8보다 구체적인 슬러그).
    if "galaxy-watch-ultra" in u:
        return "galaxy-watch-ultra"
    if "galaxy-watch8" in u:
        return "galaxy-watch8"
    # [2026-07] galaxy-buds4/-pro는 운영 대상에서 제외됨(요청) — Rule DB 시드도 함께 삭제됨.
    return None


def is_smartphone(market_product: Optional[str], url: str = "") -> bool:
    """스마트폰(=Flagship PD 세트) 여부. galaxy-s26*/galaxy-z*(폴더블) 계열이면 True.
    판별 불가한 신규/공통 페이지는 안전하게 False(→ Simple 세트)로 폴백."""
    mp = (market_product or "").lower()
    u = (url or "").lower()
    if mp.startswith(("galaxy-s", "galaxy-z")) and "buds" not in mp:
        return True
    if "/smartphones/" in u and "buds" not in u:
        return True
    return False


def schema_set_for(page_type: str, market_product: Optional[str], url: str = "") -> Optional[str]:
    """페이지타입+제품군 → Word 스키마 세트 파일 접두어.
    - PDP + 스마트폰  → flagship
    - PDP + 그 외     → simple  (버즈·노트북·태블릿, 판별불가 공통페이지 포함)
    - Compare         → compare
    - Buying          → None (스키마 검사 제외)
    """
    if page_type in ("Buying", "Specs"):
        return None  # [D1] Specs 는 별도 Word 세트가 없어 스키마 검사 제외(HTML/SEO 검사만)
    if page_type == "Compare":
        return "compare"
    return "flagship" if is_smartphone(market_product, url) else "simple"


_SCHEMA_VALUES_CACHE = None


def _schema_values():
    global _SCHEMA_VALUES_CACHE
    if _SCHEMA_VALUES_CACHE is None:
        single = os.path.join(_HERE, "schema_values.json")
        if os.path.exists(single):
            _SCHEMA_VALUES_CACHE = json.load(open(single, encoding="utf-8"))
        else:
            # 대용량이라 분할 배포하는 경우: schema_values.part*.json 을 병합
            import glob
            merged = {}
            for p in sorted(glob.glob(os.path.join(_HERE, "schema_values.part*.json"))):
                merged.update(json.load(open(p, encoding="utf-8")))
            _SCHEMA_VALUES_CACHE = merged
    return _SCHEMA_VALUES_CACHE


def _apply_product_values(schema_rules: Dict[str, Any], market_product: str,
                          page_type: str = "PDP") -> Dict[str, Any]:
    """Word 세트(구조) 위에 제품별 정답값(카피덱)을 덮어씌운다.
    - 카피덱에 값이 있는 블록: expected_values/haspart_ids 를 제품 값으로 교체
    - 카피덱에 없는 블록(예: 버즈의 Product/WebPage): 폰 값이 잘못 남지 않도록 비움(구조만 검사)
    - WebPage/ItemPage: 카피덱엔 없지만 기존 세트값을 제품 슬러그로 치환해 유지(폰만)."""
    sv = _schema_values().get(market_product)
    if not sv:
        return schema_rules
    is_compare = (page_type == "Compare")
    # [2026-07 신규] Compare 페이지는 WebPage.mainEntity가 제품 자신이 아니라 ItemList(#list)를,
    # hasPart는 FAQ 하나만 가리키는 등 PDP와 참조 대상 자체가 다르다. 기존의 "PDP 값 재활용 +
    # URL에 /compare/ 접미사만 붙이기(_to_compare)" 방식으로는 이 구조를 표현할 수 없어,
    # 제품별로 별도의 compare_blocks 덱이 있으면 그걸 우선 사용한다(없으면 기존 방식으로 폴백).
    by_type = (sv.get("compare_blocks") if is_compare and sv.get("compare_blocks") else None) or sv.get("blocks", {})
    name_tokens = dict(sv.get("name_tokens", {}) or {})
    # [2026-09 FIX] 제품명 식별 토큰이 영문(Fold8/Fold 8)만 있어 현지어 제품명("Samsung 갤럭시 Z 폴드8",
    # "Galaxy Z フォールド8")이 '제품명 오기'로 오탐됐다(sec 실크롤 확인). Spec Rule DB 시드의
    # product_aliases(다국어 제품명)를 model_any 에 합쳐 현지어 표기도 정상으로 인정한다.
    try:
        _seed = os.path.join(_HERE, f"spec_rules.seed.{market_product}.json")
        if os.path.exists(_seed):
            _al = json.load(open(_seed, encoding="utf-8")).get("product_aliases") or []
            if _al and name_tokens:
                name_tokens["model_any"] = list(dict.fromkeys(list(name_tokens.get("model_any") or []) + _al))
    except Exception:
        pass
    slug = market_product  # 예: galaxy-s26 / galaxy-z-fold7 / galaxy-buds4-pro
    is_phone = slug.startswith(("galaxy-s", "galaxy-z"))

    _PAGE_SELF_PROPS = {"about", "url", "mainEntity", "mainEntityOfPage", "isPartOf"}

    def _to_compare(url: str) -> str:
        if not isinstance(url, str) or "/compare" in url:
            return url
        return url.rstrip("/") + "/compare/"

    for b in schema_rules.get("blocks", []):
        types = b.get("types", [])
        # 폰 계열: 세트에 하드코딩된 S26 슬러그(@id 패턴·hasPart)를 제품 슬러그로 치환.
        # 기존엔 id_pattern이 어느 경로에서도 치환되지 않아 fold7 등에서 @id 오탐 발생.
        if is_phone:
            if b.get("id_pattern"):
                b["id_pattern"] = b["id_pattern"].replace("galaxy-s26-ultra", slug)
            if b.get("id_slug"):
                b["id_slug"] = b["id_slug"].replace("galaxy-s26-ultra", slug)
            if b.get("haspart_ids"):
                b["haspart_ids"] = [h.replace("galaxy-s26-ultra", slug) if isinstance(h, str) else h
                                    for h in b["haspart_ids"]]
        # 카피덱의 대표(첫) 블록 찾기
        deck = None
        deck_is_compare_native = by_type is sv.get("compare_blocks")
        for t in types:
            if t in by_type and by_type[t]:
                deck = by_type[t][0]; break
        if deck:
            import copy as _c
            ev = _c.deepcopy(deck.get("expected_values", {}))
            if is_compare and not deck_is_compare_native:
                for prop, spec in ev.items():
                    # @id(페이지 자기참조 URL)일 때만 compare 경로로. @type 값(예: mainEntity=Question)엔 적용 금지
                    if prop in _PAGE_SELF_PROPS and isinstance(spec, dict) and spec.get("kind") == "url" and spec.get("nested") == "@id":
                        spec["value"] = _to_compare(spec.get("value", ""))
            b["expected_values"] = ev
            if "haspart_ids" in deck:  # 빈 배열 명시 포함 — 페이지 구성 미확정 제품은 []로 구조검사만
                b["haspart_ids"] = deck["haspart_ids"]
            if deck.get("id_pattern"):  # [2026-07 FIX] 제품별 @id 패턴도 함께 덮어써야
                # 블록이 @type만으로 후보를 잡지 않고 실제 이 제품 페이지의 @id로 정확히 매칭된다.
                # 기존엔 이 줄이 없어 카피덱에 id_pattern을 채워도 조용히 무시되고 있었다.
                pat = deck["id_pattern"]
                if is_compare and not deck_is_compare_native:
                    pat = _to_compare(pat)
                b["id_pattern"] = pat
        elif ("WebPage" in types or "ItemPage" in types) and is_phone:
            # 카피덱엔 WebPage가 없음 → 기존 세트값의 슬러그를 제품에 맞게 치환(폰만)
            ev = b.get("expected_values", {})
            for prop, spec in ev.items():
                v = spec.get("value", "")
                if isinstance(v, str):
                    spec["value"] = v.replace("galaxy-s26-ultra", slug)
                    if is_compare and prop in _PAGE_SELF_PROPS and spec.get("kind") == "url":
                        spec["value"] = _to_compare(spec["value"])
                # name 기대값("Samsung Galaxy S26 Ultra")은 슬러그 문자열이 없어 치환 불가 →
                # 제품 식별토큰(name_token) 검사로 교체 (S26 잔존 방지)
                if prop == "name" and name_tokens:
                    ev[prop] = {"value": "", "kind": "name_token", "check": "제품명_올바른지", "nested": None}
        else:
            # 카피덱에 값 없음(예: 버즈 Product/WebPage) → 폰 값 잔재 제거, 구조만 검사
            b["expected_values"] = {}
            b["haspart_ids"] = []
            b["id_pattern"] = ""   # 폰 @id 패턴 잔재 제거(오탐 방지)
            # 단, 제품명은 확인할 수 있게 name 식별토큰 검사만 주입(name이 이 블록 속성일 때)
            props = set(b.get("required_properties", [])) | set(b.get("optional_properties", []))
            if name_tokens and "name" in props:
                b["expected_values"] = {"name": {"value": "", "kind": "name_token", "check": "제품명_올바른지", "nested": None}}
        # 제품명 식별토큰(name 검사용)을 블록에 부착
        if name_tokens:
            b["name_tokens"] = name_tokens
    return schema_rules


def load_rules(product: str = "M3", page_type: str = "PDP", market_product: str = None,
               url: str = "", schema_path: str = None, copy_path: str = None, spec_path: str = None) -> Dict[str, Any]:
    copy_path = copy_path or os.path.join(_HERE, "copy_rules.json")
    spec_path = spec_path or os.path.join(_HERE, "key_specs.json")

    # ── 스키마 규칙: Word(PTK) 세트로 재구성 — flagship/simple/compare, Buying 제외 ──
    schema_set = schema_set_for(page_type, market_product, url)
    if schema_set is None:
        sr = {"page_type": page_type, "set": None, "blocks": [], "skip": True}  # Buying: 스키마 검사 제외
    else:
        # 세트 파일: schema_rules.{set}.{PDP|Compare}.json
        set_page = "Compare" if schema_set == "compare" else "PDP"
        set_file = os.path.join(_HERE, f"schema_rules.{schema_set}.{set_page}.json")
        if os.path.exists(set_file):
            sr = json.load(open(set_file, encoding="utf-8"))
        else:
            # 폴백: 구 파일(있으면) → 빈 룰
            legacy = os.path.join(_HERE, f"schema_rules.{product}.{page_type}.json")
            sr = json.load(open(legacy, encoding="utf-8")) if os.path.exists(legacy) else {"page_type": page_type, "blocks": []}
        # 제품별 정답값(카피덱) 오버레이 — 세트=구조, 값=제품별
        if market_product and not sr.get("skip"):
            sr = _apply_product_values(sr, market_product, page_type=page_type)

    # 카피(스펙) 규칙: 마케팅 제품별 토큰 우선, 없으면 패밀리 폴백
    cdata = json.load(open(copy_path, encoding="utf-8"))["products"]
    cr = cdata.get(market_product) if market_product else None
    if not cr:
        # [2026-09 FIX] 제품별 카피 룰이 없을 때 패밀리(M3=S26 Ultra 폰 토큰)로 폴백하면 워치/Fold8 Ultra 등에
        # 200MP·5000mAh 같은 남의 스펙 '누락' 오탐이 생긴다(sec/sg 실크롤 Proper Noun 노이즈). 폰 계열(S/Z)이
        # 아니면 빈 룰로 두어 copy 검사를 건너뛴다 — Spec QA(Rule DB)가 제품별로 별도 판정한다.
        cr = cdata.get(product, {}) if str(market_product or "").startswith(("galaxy-s", "galaxy-z")) or not market_product else {}
    try:
        specs_all = json.load(open(spec_path, encoding="utf-8")).get("products", {})
    except Exception:
        specs_all = {}
    mp = market_product or ("galaxy-s26-ultra" if product == "M3" else product)
    # [2026-09 FIX] 해당 제품 항목이 없을 때 S26 Ultra 스펙으로 폴백하면 워치/버즈 페이지에
    # 200MP·5000mAh 같은 폰 스펙 '누락' 오탐이 대량 발생한다 → 폰 계열이 아니면 빈 값.
    entry = specs_all.get(mp) or (specs_all.get("galaxy-s26-ultra") if str(mp).startswith(("galaxy-s", "galaxy-z")) else None) or {}
    ks = entry.get("specs", []) if isinstance(entry, dict) else (entry or [])
    label = entry.get("label", mp) if isinstance(entry, dict) else mp
    return {"schema": sr, "copy": cr, "key_specs": ks, "product_label": label,
            "market_product": mp, "page_type": page_type, "schema_set": schema_set}


# [2026-07 과제3] 크롤 시간 최소화 — Data QA / Spec QA 독립 실행.
#   mode="data" : schema + copy + html_qa 만 (Data QA 탭). 무거운 Spec 추출/재렌더를 건너뛴다.
#   mode="spec" : spec_v2 (+ Compare 페이지의 compare_v2) 만 (Spec QA 탭).
#   mode="all"  : 종전과 동일(둘 다) — 하위호환 기본값.
DATA_MODES = ("all", "data")
SPEC_MODES = ("all", "spec")


def check_html(html: str, rules: Dict[str, Any],
               sitecode: str = None, site_lang: str = None, rendered_by: str = None,
               mode: str = "all", page_url: str = "", final_url: str = None) -> Dict[str, Any]:
    """단일 페이지 HTML 검수 → {schema, copy, html_qa, spec_v2, compare_v2}.
    mode 로 Data QA(schema/copy/html_qa)와 Spec QA(spec_v2/compare_v2)를 분리 실행한다.
    실행하지 않은 축은 None 으로 남겨 다운스트림(summary/report/프론트)이 '미실행'으로
    인식하게 한다(qa_report._flatten 은 None 을 빈 결과로 안전 처리)."""
    pt = rules.get("page_type", "PDP")
    mp = rules.get("market_product")
    mode = (mode or "all").lower()

    # ── Data QA 축 ──
    schema_result = None
    copy_result = None
    html_qa_result = None
    seo_result = None
    if mode in DATA_MODES:
        schema_result = schema_checker.check_page(html, rules["schema"],
                                                  sitecode=sitecode, site_lang=site_lang,
                                                  market_product=mp,
                                                  page_url=(final_url or page_url or None))  # [2026-09] {PD_URL} 치환
        copy_result = copy_checker.check_copy(html, rules["copy"], key_specs=rules.get("key_specs"), page_type=pt)
        html_qa_result = html_qa_scoring.score_html_qa(html, rules["schema"], schema_result, rendered_by=rendered_by)
        # [2026-09 D2~D7] 사람 검수 항목(Canonical/robots/Title 구성/Meta/Breadcrumb) — 소스 HTML 기준
        try:
            import seo_checker
            sv = _schema_values()
            nt = dict((sv.get(mp) or {}).get("name_tokens") or {}) if mp else {}
            # Spec Rule DB 시드의 다국어 제품명(product_aliases: '갤럭시 Z 폴드8' 등)을 모델 토큰에 합쳐
            # 현지어 Title/Meta 에서 '모델명 누락' 오탐을 줄인다.
            try:
                seed_p = os.path.join(_HERE, f"spec_rules.seed.{mp}.json")
                if mp and os.path.exists(seed_p):
                    aliases = json.load(open(seed_p, encoding="utf-8")).get("product_aliases") or []
                    nt["model_any"] = list(dict.fromkeys(list(nt.get("model_any") or []) + aliases))
            except Exception:
                pass
            seo_result = seo_checker.check_seo(html, page_url or "", page_type=pt, name_tokens=nt,
                                               other_model_tokens=seo_checker.other_model_tokens_for(mp, sv),
                                               final_url=final_url)
        except Exception as e:  # SEO 검사 실패가 기존 검수를 죽이지 않게
            print(f"[runner] seo skip: {e}")
            seo_result = None

    # ── Spec QA 축 ──
    spec_v2 = None
    compare_v2 = None
    if mode in SPEC_MODES:
        try:
            import spec_rule_db, spec_engine, spec_dict_global
            ruleset = spec_rule_db.load(mp) if mp else None
            if ruleset:
                # [2026-07] Global Dictionary(제품 공통 번역) ∪ 제품별 dictionary — 신모델이
                # 나와도 세대 간 재사용 가능한 번역(Weight/Storage/Water Resistance 등)을
                # 다시 쌓지 않도록 여기서 병합한다. spec_engine 자체는 여전히 결정론적으로,
                # 병합된 최종 dictionary만 넘겨받아 그대로 사용한다.
                ruleset = {**ruleset, "dictionary": spec_dict_global.merge_for(ruleset.get("dictionary", {}))}
                spec_v2 = spec_engine.run(html, ruleset, page_type=pt, sitecode=sitecode or "",
                                          rendered_by=rendered_by or "source")
        except Exception as e:  # V2 실패가 기존 검수를 죽이지 않게
            print(f"[runner] spec_v2 skip: {e}")

        # [Compare Pipeline] Compare 페이지 전용 Matrix QA — Spec 축에 속한다.
        if pt == "Compare":
            compare_v2 = None
            # [2026-09] ① 삼성 검색 API(spec/compare)에서 비교표 데이터를 직접 받아 판정(렌더 불필요).
            #   sg Compare HAR 로 확인된 구조. QB_SPEC_API=false 로 끄면 ② HTML 경로만 사용.
            if os.getenv("QB_SPEC_API", "true").lower() == "true" and mp and sitecode:
                try:
                    import spec_api, spec_rule_db
                    from compare_qa import CompareQA
                    rs_api = spec_rule_db.load(mp)
                    if rs_api:
                        matrix = spec_api.compare_matrix_from_api(sitecode, mp, rs_api)
                        compare_v2 = CompareQA().evaluate(matrix, mp)
                        compare_v2["summary"]["source"] = "api:spec/compare"
                        compare_v2["summary"]["category_code"] = matrix.get("category_code")
                except Exception as e:
                    print(f"[runner] compare api skip → HTML 경로: {e}")
                    compare_v2 = None
            # ② HTML 경로(렌더된 DOM 이 있을 때만 의미 있음 — httpx HTML 은 비교표 값이 비어 있음)
            if compare_v2 is None:
                try:
                    import compare_pipeline
                    compare_v2 = compare_pipeline.run_compare_pipeline(html, mp)
                    compare_v2.setdefault("summary", {})["source"] = "html"
                except Exception as e:  # Compare Pipeline 실패가 기존 검수를 죽이지 않게
                    print(f"[runner] compare_v2 skip: {e}")

    return {
        "schema": schema_result,
        "copy": copy_result,
        "html_qa": html_qa_result,
        "seo": seo_result,
        "spec_v2": spec_v2,
        "compare_v2": compare_v2,
    }


def run_site(site: Dict[str, Any], html: str, rules: Dict[str, Any], page_type: str = "PDP",
             rendered_by: str = None, mode: str = "all",
             http_status: int = None, final_url: str = None) -> Dict[str, Any]:
    res = check_html(html, rules, sitecode=site.get("sitecode"), site_lang=site.get("lang"),
                     rendered_by=rendered_by, mode=mode, page_url=site.get("url", ""), final_url=final_url)
    return {"sitecode": site.get("sitecode"), "url": site.get("url"),
            "region": site.get("region"), "country": site.get("country"),
            "product": site.get("product", "galaxy-s26-ultra"), "lang": site.get("lang"),
            "page_type": page_type, "qa_mode": (mode or "all").lower(),
            # [2026-09 D8] 상태코드/최종 URL 기록(리포트 Status Code 열·Not Checked 시트용)
            "http_status": http_status, "final_url": final_url, "rendered_by": rendered_by,
            "schema": res["schema"], "copy": res["copy"], "html_qa": res["html_qa"],
            "seo": res.get("seo"),
            "spec_v2": res.get("spec_v2"), "compare_v2": res.get("compare_v2")}


def run_all(fetch_html: Callable[[str], Optional[str]],
            product: str = "M3",
            sitecodes: Optional[List[str]] = None,
            registry: Optional[SiteRegistry] = None) -> List[Dict[str, Any]]:
    """레지스트리 순회 검수. fetch_html(url)->html|None 을 주입.
    sitecodes 를 주면 해당 사이트만 검수. 페이지타입은 URL 로 자동판별해 해당 룰 적용."""
    registry = registry or SiteRegistry()
    rules_cache: Dict[str, Dict[str, Any]] = {}

    def rules_for(pt: str, mp: str, url: str = "") -> Dict[str, Any]:
        sset = schema_set_for(pt, mp, url)
        key = f"{pt}|{mp}|{sset}"
        if key not in rules_cache:
            rules_cache[key] = load_rules(product, page_type=pt, market_product=mp, url=url)
        return rules_cache[key]

    targets = registry.all()
    if sitecodes:
        want = {s.lower() for s in sitecodes}
        targets = [t for t in targets if t["sitecode"] in want]
    results = []
    for site in targets:
        url = site.get("url", "")
        pt = site.get("page_type") or page_type_from_url(url)
        mp = product_from_url(url)
        try:
            html = fetch_html(site["url"])
        except Exception:
            html = None
        if not html:
            results.append({"sitecode": site["sitecode"], "url": site["url"],
                            "region": site.get("region"), "country": site.get("country"),
                            "page_type": pt,
                            "schema": {"summary": {}, "findings": [
                                {"block": "(수집 실패)", "status": "fail",
                                 "as_is": "HTML 수집 실패", "to_be": "URL 접근/렌더링 확인"}]},
                            "copy": {"summary": {}, "findings": []}, "html_qa": None})
            continue
        results.append(run_site(site, html, rules_for(pt, mp, url), page_type=pt))
    return results


if __name__ == "__main__":
    # 데모: 로컬 index.html 을 fetch_html 로 반환하도록 주입 (네트워크 없이 검증)
    local = open("/mnt/user-data/uploads/index.html", encoding="utf-8", errors="ignore").read()

    def fake_fetch(url):
        return local if url.endswith("/uk/smartphones/galaxy-s26-ultra/") else None

    res = run_all(fake_fetch, sitecodes=["uk", "de"])
    for r in res:
        sf = r["schema"]["summary"]; cf = r["copy"]["summary"]
        print(f"{r['sitecode']:4s} schema {sf.get('fail','?')}fail/{sf.get('warn','?')}warn · "
              f"copy {cf.get('fail','?')}fail/{cf.get('warn','?')}warn")
