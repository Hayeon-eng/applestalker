"""
qb_routes_specrules.py — Spec QA Rule DB [V2] (/spec-rules*, /spec-check) [qb_api 분할]
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

import runner
import qa_report
import schema_checker
import html_qa_scoring
from database import SessionLocal
from models import QbHistory

import qb_core
from qb_core import qb_router, _registry

# ═══════════════════════════════════════════════════════════════════
# Spec QA Rule DB [V2] — 엑셀 업로드/조회/Dictionary 승인
#   룰은 코드가 아니라 이 데이터로 확장된다 (spec_rule_db.py 참조)
# ═══════════════════════════════════════════════════════════════════
import spec_rule_db as _spec_rule_db  # noqa: E402
import spec_dict_global as _spec_dict_global  # noqa: E402


@qb_router.get("/spec-rules/products")
def qb_spec_rules_products():
    """등록된 Rule DB 제품 목록 (DB + 시드)."""
    return {"products": _spec_rule_db.list_products()}


@qb_router.get("/spec-rules")
def qb_spec_rules_get(product: str = Query(...)):
    """제품 룰셋 전체(MasterSpec/Dictionary/Exception/Interaction/Candidates).
    dictionary는 [2026-07] Global(공통) ∪ 제품별 병합 결과 — 실제 검수(spec_engine)가
    쓰는 것과 동일한 유효 사전을 그대로 보여준다. global_representatives는 그중 어떤
    대표어가 공통(Global) 출처인지 프론트가 배지로 표시할 수 있도록 별도로 내려준다."""
    rs = _spec_rule_db.load(product)
    if not rs:
        raise HTTPException(404, f"룰셋 없음: {product} — 엑셀을 업로드하세요.")
    product_dict = rs.get("dictionary", {})
    merged = _spec_dict_global.merge_for(product_dict)
    return {**rs, "dictionary": merged,
            "dictionary_product_only": product_dict,
            "global_representatives": sorted(_spec_dict_global.global_representatives())}


@qb_router.post("/spec-rules/delete")
def qb_spec_rules_delete(payload: Dict[str, Any] = Body(...)):
    """[2026-07 신규] 제품 Rule DB 삭제 — 신모델 업로드 후 구모델(Fold7/Flip7 등)을
    내릴 때 사용. 룰·예외·후보가 담긴 DB 1행을 지우고, 저장소 시드가 남아 있어도
    되살아나지 않도록 삭제 마커에 기록한다(같은 제품을 다시 엑셀 업로드하면 자동 해제).
    [2026-07 FIX] 제품 용어사전(Dictionary)은 함께 삭제되지 않는다 — 별도 보관해두었다가
    재업로드 시 자동 복원되며, 완전히 지우려면 /spec-rules/dictionary/delete를 따로 호출해야 한다.
    Global(공통) Dictionary와 다른 제품에는 영향이 없다.
    body: {product: 'galaxy-z-fold8'}"""
    product = (payload.get("product") or "").strip()
    if not product:
        raise HTTPException(400, "product가 필요합니다.")
    try:
        info = _spec_rule_db.delete_product(product)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # 구식 key_specs.json 쪽에도 같은 제품이 있으면 함께 정리(제품 칩 잔존 방지)
    try:
        import qb_routes_manage as _mg
        data = _mg._load_specs()
        if product in (data.get("products") or {}):
            del data["products"][product]
            _mg._save_specs(data)
            info["removed_key_specs"] = True
    except Exception as e:
        print(f"[spec-rules/delete] key_specs cleanup skip: {e}")
    return {"ok": True, **info, "products": _spec_rule_db.list_products()}


@qb_router.post("/spec-rules/dictionary/delete")
def qb_spec_rules_dictionary_delete(payload: Dict[str, Any] = Body(...)):
    """[2026-07 신규] 제품 용어사전(Dictionary)만 별도로 완전 삭제 — 제품(룰 DB) 삭제와는
    분리된 별도 기능이다. /spec-rules/delete는 이 사전을 건드리지 않는다.
    body: {product: 'galaxy-z-fold8'}"""
    product = (payload.get("product") or "").strip()
    if not product:
        raise HTTPException(400, "product가 필요합니다.")
    return {"ok": True, **_spec_rule_db.delete_dictionary(product)}


@qb_router.get("/spec-rules/history")
def qb_spec_rules_history(product: str = Query(...)):
    """[2026-07 신규] 이 제품에 저장된 버전 이력(최신 순) — 되돌리기 후보 목록.
    엑셀을 재업로드하거나 삭제할 때마다 그 직전 상태가 자동으로 여기 쌓인다."""
    return {"history": _spec_rule_db.list_history(product)}


@qb_router.post("/spec-rules/revert")
def qb_spec_rules_revert(payload: Dict[str, Any] = Body(...)):
    """[2026-07 신규] /spec-rules/history가 준 snapshot_key로 그 시점 상태로 되돌린다.
    되돌리기 자체도 되돌리기 전 상태를 이력에 남기므로 안전하게 여러 번 오가도 된다.
    body: {product, snapshot_key}"""
    product = (payload.get("product") or "").strip()
    snapshot_key = (payload.get("snapshot_key") or "").strip()
    if not (product and snapshot_key):
        raise HTTPException(400, "product/snapshot_key가 필요합니다.")
    try:
        info = _spec_rule_db.revert(product, snapshot_key)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, **info}


@qb_router.get("/spec-rules/template.xlsx")
def qb_spec_rules_template():
    """[2026-07 신규] 빈 Rule DB 엑셀 양식 다운로드 — 신규 제품 등록 시 이 양식에
    맞춰 채운 뒤 /spec-rules/upload로 올리면 된다. (사이트 URL 쪽 template.xlsx와 대칭)"""
    content = _spec_rule_db.build_template_xlsx()
    return StreamingResponse(iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=qubi_rule_db_template.xlsx"})


@qb_router.get("/spec-rules/export.xlsx")
def qb_spec_rules_export(product: str = Query(...)):
    """[2026-07 신규] 지금 저장된 제품 룰셋을 엑셀로 내보내기 — 수정 후 같은 파일을
    /spec-rules/upload로 재업로드하면 그대로 반영된다(수정→재업로드 왕복 지원)."""
    try:
        content = _spec_rule_db.build_export_xlsx(product)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return StreamingResponse(iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=qubi_rule_db_{product}.xlsx"})


@qb_router.post("/spec-rules/upload")
def qb_spec_rules_upload(payload: Dict[str, Any] = Body(...)):
    """Rule DB 엑셀 업로드 → 파싱 → DB 저장.
    body: {b64: dataURL|base64, product: 'galaxy-z-fold8', version?: str}"""
    import base64
    b64 = (payload.get("b64") or "")
    product = (payload.get("product") or "").strip()
    if not b64 or not product:
        raise HTTPException(400, "b64와 product가 필요합니다.")
    if "," in b64:  # dataURL
        b64 = b64.split(",", 1)[1]
    try:
        content = base64.b64decode(b64)
        ruleset = _spec_rule_db.parse_xlsx(content, product=product,
                                           version=payload.get("version", "uploaded"))
    except Exception as e:
        raise HTTPException(400, f"엑셀 파싱 실패 — {e}")
    info = _spec_rule_db.save(product, ruleset, version=payload.get("version", ""))
    return {"ok": True, **info,
            "dictionary": len(ruleset["dictionary"]), "exceptions": len(ruleset["exceptions"]),
            "interactions": len(ruleset["interactions"])}


@qb_router.post("/spec-rules/dictionary/add")
def qb_spec_rules_dict_add(payload: Dict[str, Any] = Body(...)):
    """Dictionary Alias 추가 — 반드시 사용자 승인(버튼 클릭) 후 호출된다.
    body: {product, representative, alias, scope?: 'global'|'product'}
    [2026-07] scope 기본값은 'global' — Battery Capacity/Weight/Wi-Fi 같은 표현은 세대가
    바뀌어도 번역이 거의 그대로 재사용되므로, 신모델이 나왔을 때 이 승인 이력을 다시
    쌓지 않아도 되게 하기 위함. 특정 제품에서만 쓰는 용어(예: 이 세대에만 있는 신규
    기능명)라면 화면에서 '이 제품에만 적용' 체크 후 scope='product'로 보낸다."""
    product = (payload.get("product") or "").strip()
    rep = (payload.get("representative") or "").strip()
    alias = (payload.get("alias") or "").strip()
    scope = (payload.get("scope") or "global").strip().lower()
    if not (product and rep and alias):
        raise HTTPException(400, "product/representative/alias가 필요합니다.")
    try:
        if scope == "product":
            return {"ok": True, **_spec_rule_db.add_alias(product, rep, alias)}
        return {"ok": True, **_spec_dict_global.add_alias(rep, alias)}
    except ValueError as e:
        raise HTTPException(404, str(e))


@qb_router.post("/spec-rules/dictionary/migrate")
def qb_spec_rules_dict_migrate(payload: Dict[str, Any] = Body(default={})):
    """1회성 관리 작업: 여러 제품에 동일하게 존재하는 표현을 Global Dictionary로 승격한다.
    body: {products?: string[], min_products?: int} — products 생략 시 등록된 전체 제품 대상.
    제품별 dictionary는 건드리지 않는다(합집합 조회이므로 안전) — 실수로 실행해도 데이터
    유실이 없다."""
    products = payload.get("products")
    if not products:
        products = [p["product"] for p in _spec_rule_db.list_products()]
    min_products = int(payload.get("min_products", 2))
    return {"ok": True, **_spec_dict_global.migrate_from_products(products, min_products=min_products)}


@qb_router.post("/spec-rules/dictionary/suggest")
def qb_spec_rules_dict_suggest(payload: Dict[str, Any] = Body(...)):
    """미등록 표현(alias)이 어느 canonical 항목인지 AI가 '제안'한다(판정 아님, 참고용).
    실제 반영은 사람이 dictionary/add 로 승인해야만 이뤄진다.
    GEMINI_API_KEY 미설정이면 available=False 로 폴백(프론트는 '준비 중' 표시).
    body: {product, alias, lang?}"""
    import dict_ai_suggest
    product = (payload.get("product") or "").strip()
    alias = (payload.get("alias") or "").strip()
    lang = (payload.get("lang") or "").strip()
    if not (product and alias):
        raise HTTPException(400, "product/alias가 필요합니다.")
    rs = _spec_rule_db.load(product) or {}
    attributes = sorted({r.get("attribute", "") for r in rs.get("rules", []) if r.get("attribute")})
    return dict_ai_suggest.suggest(alias, attributes, lang_hint=lang)


# ════════════════════════════════════════════════════════════════
# [2026-11 신규] 스키마 정답값(schema_values) 엑셀 템플릿 — 내려받기/내보내기/업로드/삭제
#   PPT 4번: "스키마 룰은 언팩마다 바뀌는데 매번 새롭게 업데이트할 수 있는 양식" — Spec Rule DB 와 같은 왕복 방식.
# ════════════════════════════════════════════════════════════════
import schema_values_xlsx as _sv_xlsx
import runner as _runner_mod


@qb_router.get("/schema-values/products")
def qb_schema_values_products():
    vals = _runner_mod._schema_values()
    up = _sv_xlsx.load_uploaded()
    return {"products": sorted(vals.keys()), "uploaded": sorted(up.keys())}


@qb_router.get("/schema-values/template.xlsx")
def qb_schema_values_template(example: str = Query("galaxy-z-fold8")):
    content = _sv_xlsx.build_template_xlsx(example, _runner_mod._schema_values())
    return StreamingResponse(iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=qubi_schema_values_template.xlsx"})


@qb_router.get("/schema-values/export.xlsx")
def qb_schema_values_export(product: str = Query(...)):
    try:
        content = _sv_xlsx.build_export_xlsx(product, _runner_mod._schema_values())
    except ValueError as e:
        raise HTTPException(404, str(e))
    return StreamingResponse(iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=qubi_schema_values_{product}.xlsx"})


@qb_router.post("/schema-values/upload")
def qb_schema_values_upload(payload: Dict[str, Any] = Body(...)):
    """body: {b64: dataURL|base64}. 엑셀 파싱 → 검증 → schema_values.uploaded.json 저장(제품키 단위 덮어쓰기)."""
    import base64
    b64 = (payload.get("b64") or "")
    if not b64:
        raise HTTPException(400, "b64 가 필요합니다.")
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    try:
        parsed, warnings = _sv_xlsx.parse_xlsx(base64.b64decode(b64))
    except ValueError as e:
        raise HTTPException(400, f"양식 오류 — {e}")
    except Exception as e:
        raise HTTPException(400, f"엑셀 파싱 실패 — {e}")
    info = _sv_xlsx.save_uploaded(parsed)
    _runner_mod.reset_schema_values_cache()
    # 검증: 실제 룰에 적용했을 때 블록별 id_pattern/기대값 키가 채워지는지 확인해 돌려준다
    applied = {}
    for prod in parsed:
        try:
            base = _runner_mod.load_rules("M3", page_type="PDP", market_product=prod)["schema"]
            applied[prod] = [{"block": b["name"], "id_pattern": b.get("id_pattern"), "expected_keys": list((b.get("expected_values") or {}).keys())}
                             for b in base.get("blocks", [])]
        except Exception as e:
            applied[prod] = f"적용 확인 실패: {e}"
    return {"ok": True, **info, "warnings": warnings, "applied": applied}


@qb_router.delete("/schema-values/uploaded")
def qb_schema_values_delete(product: str = Query(...)):
    ok = _sv_xlsx.delete_uploaded(product)
    _runner_mod.reset_schema_values_cache()
    if not ok:
        raise HTTPException(404, f"업로드된 값에 '{product}' 가 없습니다.")
    return {"ok": True, "product": product}


# ════════════════════════════════════════════════════════════════
# [2026-11 신규] 제품 등록 워크북(템플릿 ①) — 제품정보·URL·스펙 룰·스키마 정답값을 엑셀 1개로
# ════════════════════════════════════════════════════════════════
import product_pack_xlsx as _pack
import product_master as _pmaster
from qb_core import _registry as _pack_registry

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(content: bytes, filename: str):
    return StreamingResponse(iter([content]), media_type=_XLSX,
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@qb_router.get("/product-pack/products")
def qb_product_pack_products():
    vals = _runner_mod._schema_values()
    spec_products = [p.get("product") for p in (_spec_rule_db.list_products() or []) if isinstance(p, dict)]
    reg_products = sorted({e.get("product") for e in _pack_registry.all() if e.get("product")})
    keys = sorted({*vals.keys(), *[p for p in spec_products if p], *reg_products, *_pmaster.load().keys()})
    return {"products": [{"product": k, "master": _pmaster.get(k), "has_spec": k in spec_products,
                          "has_schema": k in vals, "url_count": sum(1 for e in _pack_registry.all() if e.get("product") == k)} for k in keys]}


@qb_router.get("/product-pack/template.xlsx")
def qb_product_pack_template(example: str = Query("galaxy-z-fold8")):
    return _xlsx_response(_pack.build_template(example, _runner_mod._schema_values(), _pack_registry), "qubi_product_pack_template.xlsx")


@qb_router.get("/product-pack/export.xlsx")
def qb_product_pack_export(product: str = Query(...)):
    return _xlsx_response(_pack.build_export(product, _runner_mod._schema_values(), _pack_registry), f"qubi_product_pack_{product}.xlsx")


@qb_router.get("/product-pack/draft.xlsx")
def qb_product_pack_draft(from_product: str = Query(..., alias="from"), to_product: str = Query(..., alias="to"), label: str = Query("")):
    """신모델 전환 초안 — 이전 제품키 → 새 제품키(슬러그). 노랑 칸만 채워 업로드."""
    if not re.match(r"^[a-z0-9\-]+$", to_product):
        raise HTTPException(400, "새 제품키는 URL 슬러그 형식(소문자·숫자·하이픈)이어야 합니다. 예: galaxy-z-fold9")
    return _xlsx_response(_pack.build_draft(from_product, to_product, label, _runner_mod._schema_values(), _pack_registry),
                          f"qubi_product_pack_draft_{to_product}.xlsx")


@qb_router.post("/product-pack/upload")
def qb_product_pack_upload(payload: Dict[str, Any] = Body(...)):
    """body: {b64, url_mode?: add|upsert|replace_product, version?}"""
    import base64
    b64 = payload.get("b64") or ""
    if not b64:
        raise HTTPException(400, "b64 가 필요합니다.")
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    mode = payload.get("url_mode") or "add"
    if mode not in ("add", "upsert", "replace_product"):
        raise HTTPException(400, "url_mode 는 add / upsert / replace_product 중 하나")
    try:
        res = _pack.parse_and_apply(base64.b64decode(b64), _pack_registry, url_mode=mode, version=payload.get("version") or "")
    except ValueError as e:
        raise HTTPException(400, f"양식 오류 — {e}")
    except Exception as e:
        raise HTTPException(400, f"반영 실패 — {e}")
    return {"ok": True, **res}
