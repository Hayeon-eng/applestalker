#!/usr/bin/env python3
"""
tools/resolve_watch_registry.py — 워치(Galaxy Watch Ultra2 · Watch9) 검수 URL 을 삼성 사이트에서 찾아
backend/dotcom_qa/site_registry.part5.json 에 **정적으로** 기록한다. [2026-09-11]

왜: 워치 PDP URL 은 국가마다 SKU 슬러그가 달라 사람이 관리하던 값이 틀렸다(soft-404). 폰(fold8/flip8)은 기존
    레지스트리를 그대로 쓰고, 워치만 이 스크립트가 finder API 로 찾아 파일로 굳힌다. 화면에는 URL 편집 UI 가 없다.
어디서: GitHub Actions(resolve-urls.yml) 가 인터넷이 되는 러너에서 실행 → 변경 시 자동 커밋. 로컬 PC 에서도 그대로 실행 가능.

  python tools/resolve_watch_registry.py            # part5 갱신 + 기존 part1~4 의 워치 행 제거
  python tools/resolve_watch_registry.py --dry-run  # 파일 쓰지 않고 결과만 출력
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DQ = os.path.join(ROOT, "backend", "dotcom_qa")
sys.path.insert(0, DQ); sys.path.insert(0, os.path.join(ROOT, "backend"))

WATCH_PRODUCTS = ("galaxy-watch-ultra2", "galaxy-watch9")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    import resolver
    from site_registry import _load_sites, _DEFAULT
    base = _load_sites(_DEFAULT)
    sites = base.get("sites", [])
    metas = {}
    for s in sites:
        metas.setdefault(s["sitecode"], {"sitecode": s["sitecode"], "region": s.get("region", ""), "country": s.get("country", ""), "lang": s.get("lang", "")})
    pdefs = [p for p in resolver.product_defs() if p["slug"] in WATCH_PRODUCTS]
    if not pdefs:
        print("워치 Rule DB(Model Code SM-L715/SM-L340)를 찾지 못했습니다"); sys.exit(2)
    print(f"sites {len(metas)} × products {[p['slug'] for p in pdefs]}")
    res = resolver.resolve_all(list(metas.values()), pdefs, workers=a.workers)
    entries = [{"sitecode": e["sitecode"], "url": e["url"], "region": e.get("region", ""), "country": e.get("country", ""), "lang": e.get("lang", ""),
                "product": e["product"], "page_type": e["page_type"], "model_code": e.get("model_code"), "display_name": e.get("display_name"),
                "resolved_at": e.get("resolved_at")} for e in res["entries"] if e["page_type"] == "PDP"]
    unresolved = res["unresolved"]
    print(f"찾음 {len(entries)}개 · 못 찾음 {len(unresolved)}개")
    for u in unresolved[:20]:
        print("  -", u["sitecode"], u["product"], u["reason"])
    if a.dry_run:
        return
    if len(entries) < 20:  # 안전장치: API 접근 실패 등으로 거의 못 찾았으면 기존 파일을 건드리지 않는다
        print(f"찾은 URL 이 {len(entries)}개뿐 — API 접근 실패로 판단, 파일을 바꾸지 않고 종료(기존 값 유지)"); sys.exit(0)
    # part5 기록
    part5 = os.path.join(DQ, "site_registry.part5.json")
    json.dump({"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "source": "tools/resolve_watch_registry.py (finder API)",
               "note": "워치 PDP URL — 국가별 SKU 슬러그. 이 파일만 스크립트가 갱신하며 part1~4 의 워치 행은 제거됨",
               "sites": entries, "unresolved": unresolved}, open(part5, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # part1~4 의 워치 행 제거(잘못된 수동 URL)
    removed = 0
    for pth in sorted(glob.glob(os.path.join(DQ, "site_registry.part[1-4].json"))):
        d = json.load(open(pth, encoding="utf-8"))
        before = len(d.get("sites", []))
        d["sites"] = [s for s in d.get("sites", []) if not str(s.get("product", "")).startswith("galaxy-watch")]
        removed += before - len(d["sites"])
        if before != len(d["sites"]):
            json.dump(d, open(pth, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if os.path.exists(resolver.RESOLVED_PATH):
        os.remove(resolver.RESOLVED_PATH)  # 동적 병합 파일은 쓰지 않는다 — part5 가 유일한 워치 소스
    print(f"part5 기록 {len(entries)} · part1~4 워치 행 제거 {removed}")


if __name__ == "__main__":
    main()
