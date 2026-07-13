"""
spec_rule_db.py — 큐비 — Spec QA Rule DB [V2]

Rule 기반 Spec Validation 엔진의 룰 저장소.
엑셀(Rule DB 시트들) → 표준 JSON 룰셋으로 파싱하고, DB(qb_spec_rules)에
제품별 1행(JSON 문서)으로 저장한다. DB가 비어 있으면 저장소의 시드 JSON을 쓴다.

시트 → JSON 매핑
  · *MasterSpec*   → rules[]        (Rule ID/Category/Attribute/Official Value/Unit/
                                      Validation/Priority/Page/Interaction/Exception/Fix Guide)
  · Dictionary     → dictionary{}   (Representative → [aliases])
  · ExceptionRule  → exceptions[]   (rule/description)
  · InteractionRule→ interactions[] (section/action)  — Playwright 단계에서 사용
  · CountryException(선택) → country_exceptions[]
  · Candidates 는 런타임 승인 대기 목록(candidates[])로 관리

설계 원칙: 코드가 아니라 이 데이터만 갱신하면 룰이 확장된다.
"""
from __future__ import annotations
import io
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(__file__)

# Validation 타입 표준화(엑셀 표기 흔들림 흡수)
_VALIDATION_TYPES = {
    "exact": "exact",
    "numeric exact": "numeric_exact",
    "numeric": "numeric_exact",
    "prefix match": "prefix",
    "prefix": "prefix",
    "dictionary": "dictionary",
    "option match": "option_match",
    "options": "option_match",
    "exists": "exists",
    "exist": "exists",
}


def _norm_header(h) -> str:
    return re.sub(r"[^a-z]", "", str(h or "").lower())


def _cell(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s in ("-", "—") else s


def parse_xlsx(content: bytes, product: str, version: str = "") -> Dict[str, Any]:
    """Rule DB 엑셀(bytes) → 표준 룰셋 JSON.
    시트명은 부분 일치로 찾는다(MasterSpec/Dictionary/Exception/Interaction/Country)."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)

    def _find_sheet(*keywords):
        for name in wb.sheetnames:
            low = name.lower()
            if any(k in low for k in keywords):
                return wb[name]
        return None

    ruleset: Dict[str, Any] = {
        "product": product, "version": version or "uploaded",
        "rules": [], "dictionary": {}, "exceptions": [],
        "interactions": [], "country_exceptions": [], "candidates": [],
    }

    # ── MasterSpec ──
    ws = _find_sheet("masterspec", "master")
    if ws is None:
        raise ValueError("MasterSpec 시트를 찾을 수 없습니다.")
    rows = ws.iter_rows(values_only=True)
    header = [_norm_header(h) for h in next(rows)]

    def col(row, *names):
        for n in names:
            if n in header:
                return _cell(row[header.index(n)])
        return ""

    for row in rows:
        if not row or not _cell(row[0]):
            continue
        vtype_raw = col(row, "validation").lower()
        rule = {
            "rule_id": col(row, "ruleid"),
            "category": col(row, "category"),
            "attribute": col(row, "attribute"),
            "expected": col(row, "officialvaluedraft", "officialvalue", "value"),
            "unit": col(row, "unit"),
            "validation": _VALIDATION_TYPES.get(vtype_raw, vtype_raw or "exact"),
            "priority": col(row, "priority") or "Medium",
            "page": col(row, "page") or "PDP",
            "interaction": col(row, "interaction"),
            "exception": col(row, "exception"),
            "fix_guide": col(row, "fixguide"),
            "notes": col(row, "notes"),
        }
        if rule["rule_id"] and rule["attribute"]:
            ruleset["rules"].append(rule)

    # ── Dictionary ──
    ws = _find_sheet("dictionary")
    if ws is not None:
        rows = ws.iter_rows(values_only=True)
        next(rows, None)  # header
        for row in rows:
            if not row:
                continue
            rep, alias = _cell(row[0]), _cell(row[1] if len(row) > 1 else "")
            if rep and alias:
                ruleset["dictionary"].setdefault(rep, [])
                if alias not in ruleset["dictionary"][rep]:
                    ruleset["dictionary"][rep].append(alias)

    # ── ExceptionRule ──
    ws = _find_sheet("exception")
    if ws is not None and "country" not in (ws.title or "").lower():
        rows = ws.iter_rows(values_only=True)
        next(rows, None)
        for row in rows:
            if not row or not _cell(row[0]):
                continue
            ruleset["exceptions"].append({
                "rule": _cell(row[0]),
                "description": _cell(row[1] if len(row) > 1 else ""),
            })

    # ── InteractionRule ──
    ws = _find_sheet("interaction")
    if ws is not None:
        rows = ws.iter_rows(values_only=True)
        next(rows, None)
        for row in rows:
            if not row or not _cell(row[0]):
                continue
            ruleset["interactions"].append({
                "section": _cell(row[0]),
                "action": _cell(row[1] if len(row) > 1 else ""),
            })

    # ── CountryException(선택) ──
    ws = _find_sheet("countryexception", "country")
    if ws is not None:
        rows = ws.iter_rows(values_only=True)
        next(rows, None)
        for row in rows:
            if not row or not _cell(row[0]):
                continue
            ruleset["country_exceptions"].append({
                "country": _cell(row[0]),
                "rule": _cell(row[1] if len(row) > 1 else ""),
                "action": _cell(row[2] if len(row) > 2 else ""),
            })

    return ruleset


# ── DB 저장/로드 (qb_history와 동일한 SessionLocal 재사용) ──────────────
def _db():
    import sys
    sys.path.insert(0, os.path.join(_HERE, ".."))
    from database import SessionLocal
    from models import QbSpecRules
    return SessionLocal, QbSpecRules


def save(product: str, ruleset: Dict[str, Any], version: str = "", merge_dictionary: bool = True) -> Dict[str, Any]:
    """[2026-07 버그 수정] 기존엔 재업로드 시 dictionary를 통째로 덮어써서, MasterSpec(스펙
    값)만 고치려고 엑셀을 재업로드해도 그동안 운영자가 승인해둔 alias가 전부 삭제됐다.
    merge_dictionary=True(기본)면 저장 전에 '기존 DB의 dictionary ∪ 새로 넘어온 dictionary'로
    합쳐서 저장한다 — 새 alias는 추가되고, 예전에 승인된 alias는 절대 사라지지 않는다.
    (Global Dictionary 자체를 저장할 때는 spec_dict_global.save()가 merge_dictionary=False로
    호출한다 — 이미 병합이 끝난 최종본이므로 이중 병합을 피하기 위함.)"""
    SessionLocal, QbSpecRules = _db()
    db = SessionLocal()
    try:
        row = db.query(QbSpecRules).filter(QbSpecRules.product == product).first()
        if row and merge_dictionary and row.data:
            try:
                prev = json.loads(row.data)
                merged = dict(ruleset.get("dictionary", {}))
                for rep, aliases in (prev.get("dictionary") or {}).items():
                    cur = merged.setdefault(rep, [])
                    for a in aliases:
                        if a not in cur:
                            cur.append(a)
                ruleset = {**ruleset, "dictionary": merged}
            except Exception as e:
                print(f"[spec_rule_db] dictionary merge skip (falling back to overwrite): {e}")
        payload = json.dumps(ruleset, ensure_ascii=False)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if row:
            row.data = payload
            row.version = version or ruleset.get("version", "")
            row.updated_at = now
        else:
            row = QbSpecRules(product=product, data=payload,
                              version=version or ruleset.get("version", ""), updated_at=now)
            db.add(row)
        db.commit()
        return {"product": product, "version": row.version, "updated_at": now,
                "rules": len(ruleset.get("rules", []))}
    finally:
        db.close()


def load(product: str) -> Optional[Dict[str, Any]]:
    """DB → 없으면 저장소 시드(spec_rules.seed.{product}.json) → 없으면 None."""
    try:
        SessionLocal, QbSpecRules = _db()
        db = SessionLocal()
        try:
            row = db.query(QbSpecRules).filter(QbSpecRules.product == product).first()
            if row and row.data:
                return json.loads(row.data)
        finally:
            db.close()
    except Exception as e:  # DB 미설정(로컬 등)이어도 시드로 동작
        print(f"[spec_rule_db] DB load skip: {e}")
    seed = os.path.join(_HERE, f"spec_rules.seed.{product}.json")
    if os.path.exists(seed):
        return json.load(open(seed, encoding="utf-8"))
    return None


def list_products() -> List[Dict[str, Any]]:
    out, seen = [], set()
    try:
        SessionLocal, QbSpecRules = _db()
        db = SessionLocal()
        try:
            for row in db.query(QbSpecRules).all():
                if row.product == "__global__":  # Global Dictionary 저장용 가짜 제품 행 — 목록 제외
                    continue
                out.append({"product": row.product, "version": row.version,
                            "updated_at": row.updated_at, "source": "db"})
                seen.add(row.product)
        finally:
            db.close()
    except Exception:
        pass
    for fn in os.listdir(_HERE):
        m = re.match(r"spec_rules\.seed\.(.+)\.json$", fn)
        if m and m.group(1) not in seen and m.group(1) != "__global__":
            out.append({"product": m.group(1), "version": "seed", "updated_at": "", "source": "seed"})
    return out


def add_alias(product: str, representative: str, alias: str) -> Dict[str, Any]:
    """Dictionary에 Alias 추가(사용자 승인 후 호출). Candidate에 있으면 제거."""
    rs = load(product)
    if not rs:
        raise ValueError(f"룰셋 없음: {product}")
    rs["dictionary"].setdefault(representative, [])
    if alias not in rs["dictionary"][representative]:
        rs["dictionary"][representative].append(alias)
    rs["candidates"] = [c for c in rs.get("candidates", [])
                        if not (c.get("alias") == alias and c.get("representative") == representative)]
    save(product, rs, version=rs.get("version", ""))
    return {"representative": representative, "aliases": rs["dictionary"][representative]}
