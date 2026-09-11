#!/usr/bin/env python3
"""
registry_from_collector.py — collector(gpi-pv, Samsung finder API) 결과 → 큐비 레지스트리 [2026-09 신규]

배경
  워치/버즈(Simple PD)는 로케일별 PDP URL 이 SKU 슬러그를 포함해 일정하지 않다
  (예: /uk/watches/galaxy-watch/galaxy-watch9-44mm-graphite-bluetooth-sm-l335nzkaeua/).
  손으로 만든 레지스트리의 '/xx/watches/galaxy-watch/galaxy-watch9/' 같은 URL 은 실제 페이지가 아니어서
  삼성닷컴 soft-404 안내 페이지가 크롤됐다(2026-09 실크롤 확인). URL 은 finder API 로 받아야 한다.

사용 (사내 PC, 프록시 환경 — collector 저장소의 스크립트를 먼저 실행)
  python gpi-pv/scripts/resolve_product.py --keywords "Galaxy Watch9" --category 01030000 --out product.json
  python gpi-pv/scripts/collect_urls.py --product product.json --out candidates.json
  python gpi-pv/scripts/verify_pdp.py --candidates candidates.json --out results.json      # (권장) 실접속 검증

  python tools/registry_from_collector.py --product galaxy-watch9 \\
         --results results.json            # 또는 --candidates candidates.json (검증 전 결과)
         --registry-dir backend/dotcom_qa  # 기존 레지스트리에서 region/country/lang 을 가져옴
         --out qubi_urls_galaxy-watch9.xlsx
  → 기본: 큐비 '⬆ URL 엑셀 업로드'(/api/qb/sites/upload) 형식의 xlsx 생성 + 교체 대상(기존 URL) 목록 출력
  → --apply : site_registry.part*.json 을 직접 고쳐 저장(그 제품의 PDP 항목을 통째로 교체) — 그대로 git push

선택 규칙
  · results.json 이 있으면 status == found 만 사용(low_confidence/mismatch 는 사유와 함께 '보류' 목록으로 출력)
  · candidates.json 만 있으면 candidates[0].pdpUrl (대표 후보) 사용
  · 'cn'(samsung.com.cn)은 finder 미지원 → 기존 레지스트리 항목을 그대로 두고 경고만 출력
  · URL 은 항상 https://www.samsung.com 절대경로 + 트레일링 슬래시로 정규화
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys
from typing import Any, Dict, List
from urllib.parse import urljoin

SITE_BASE = "https://www.samsung.com"


def _abs(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if not u.startswith("http"):
        u = urljoin(SITE_BASE, u)
    u = u.split("?")[0].split("#")[0]
    return u if u.endswith("/") else u + "/"


def load_registry(reg_dir: str) -> Dict[str, Any]:
    single = os.path.join(reg_dir, "site_registry.json")
    parts = sorted(glob.glob(os.path.join(reg_dir, "site_registry.part*.json")))
    files = [single] if os.path.exists(single) else parts
    data = []
    for p in files:
        d = json.load(open(p, encoding="utf-8"))
        for e in d.get("sites", []):
            e["_file"] = p
            data.append(e)
    return {"files": files, "sites": data}


def site_meta(reg_sites: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    meta = {}
    for e in reg_sites:
        sc = e.get("sitecode")
        if sc and sc not in meta:
            meta[sc] = {"region": e.get("region", ""), "country": e.get("country", ""), "lang": e.get("lang", "")}
    return meta


def pick_urls(results_path: str, candidates_path: str):
    """→ (accepted: [{siteCode,url,note}], held: [{siteCode,status,reason}], meta_by_site)"""
    accepted, held, meta = [], [], {}
    if results_path:
        d = json.load(open(results_path, encoding="utf-8"))
        for r in d.get("results", []):
            sc = r.get("siteCode")
            meta[sc] = {"region": r.get("region", ""), "country": r.get("country_en", ""), "lang": r.get("language", "")}
            if r.get("status") == "found" and r.get("url"):
                accepted.append({"siteCode": sc, "url": _abs(r.get("final_url") or r["url"]),
                                 "note": f"verified conf={r.get('confidence')}"})
            else:
                held.append({"siteCode": sc, "status": r.get("status"), "reason": r.get("reason", ""), "url": r.get("url")})
        return accepted, held, meta
    d = json.load(open(candidates_path, encoding="utf-8"))
    for r in d.get("locale_results", []):
        sc = r.get("siteCode")
        meta[sc] = {"region": r.get("region", ""), "country": r.get("country_en", ""), "lang": r.get("language", "")}
        if r.get("status") == "candidate_found" and r.get("candidates"):
            c = r["candidates"][0]
            accepted.append({"siteCode": sc, "url": _abs(c.get("pdpUrl")), "note": f"unverified · {c.get('match_rule','')}"})
        else:
            held.append({"siteCode": sc, "status": r.get("status"), "reason": r.get("reason", ""), "url": None})
    return accepted, held, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True, help="큐비 제품 슬러그 (예: galaxy-watch9, galaxy-watch-ultra2)")
    ap.add_argument("--results", default=None, help="verify_pdp.py 산출물 (권장)")
    ap.add_argument("--candidates", default=None, help="collect_urls.py 산출물 (results 없을 때)")
    ap.add_argument("--registry-dir", default="backend/dotcom_qa")
    ap.add_argument("--page-type", default="PDP")
    ap.add_argument("--out", default=None, help="업로드용 xlsx 경로 (기본 qubi_urls_<product>.xlsx)")
    ap.add_argument("--apply", action="store_true", help="site_registry.part*.json 을 직접 교체 저장")
    args = ap.parse_args()
    if not (args.results or args.candidates):
        sys.exit("--results 또는 --candidates 중 하나는 필요합니다")

    reg = load_registry(args.registry_dir)
    reg_meta = site_meta(reg["sites"])
    accepted, held, col_meta = pick_urls(args.results, args.candidates)

    rows = []
    for a in accepted:
        sc = a["siteCode"]
        m = reg_meta.get(sc) or col_meta.get(sc) or {}
        rows.append({"sitecode": sc, "url": a["url"], "region": m.get("region", ""), "country": m.get("country", ""),
                     "lang": m.get("lang", ""), "product": args.product, "page_type": args.page_type, "note": a["note"]})
    rows.sort(key=lambda r: (r["region"], r["sitecode"]))

    # 교체 대상: 기존 레지스트리에서 같은 제품·페이지타입 항목
    old = [e for e in reg["sites"] if e.get("product") == args.product and (e.get("page_type") or "PDP") == args.page_type]
    old_by_site = {e["sitecode"]: e for e in old}
    new_sites = {r["sitecode"] for r in rows}
    unchanged = [e for e in old if e["sitecode"] in new_sites and _abs(e["url"]) == next(r["url"] for r in rows if r["sitecode"] == e["sitecode"])]
    replaced = [e for e in old if e["sitecode"] in new_sites and e not in unchanged]
    dropped = [e for e in old if e["sitecode"] not in new_sites]  # finder 에 없음(미출시/미확인) — cn 포함

    print(f"\n[{args.product}] finder 확정 {len(rows)}개 사이트 · 기존 레지스트리 {len(old)}개")
    print(f"  동일 {len(unchanged)} · URL 교체 {len(replaced)} · finder 미확인(기존 유지 여부 판단 필요) {len(dropped)}")
    for e in replaced[:200]:
        print(f"  교체 {e['sitecode']:10s} {e['url']}\n       → {next(r['url'] for r in rows if r['sitecode'] == e['sitecode'])}")
    for e in dropped:
        why = next((h for h in held if h["siteCode"] == e["sitecode"]), None)
        print(f"  미확인 {e['sitecode']:10s} {e['url']}  ({(why or {}).get('status', 'finder 목록에 없음')}"
              f"{(' — ' + why['reason']) if why and why.get('reason') else ''})")
    if held:
        print(f"\n  보류(found 아님) {len(held)}개: " + ", ".join(f"{h['siteCode']}:{h['status']}" for h in held))

    out = args.out or f"qubi_urls_{args.product}.xlsx"
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook(); ws = wb.active; ws.title = "URLs"
    cols = ["sitecode", "url", "region", "country", "lang", "product", "page_type"]
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True, name="Arial")
    for r in rows:
        ws.append([r[c] for c in cols])
    ws2 = wb.create_sheet("교체·보류 메모")
    ws2.append(["sitecode", "구분", "기존 URL", "새 URL / 사유"])
    for e in replaced:
        ws2.append([e["sitecode"], "URL 교체", e["url"], next(r["url"] for r in rows if r["sitecode"] == e["sitecode"])])
    for e in dropped:
        ws2.append([e["sitecode"], "finder 미확인(기존 유지)", e["url"], ""])
    for h in held:
        ws2.append([h["siteCode"], f"보류 {h['status']}", h.get("url") or "", h.get("reason", "")])
    for w in (ws, ws2):
        for col, width in zip("ABCDEFG", (10, 90, 14, 20, 10, 22, 10)):
            w.column_dimensions[col].width = width
    wb.save(out)
    print(f"\n업로드용 xlsx 저장: {out}  (큐비 화면 '⬆ URL 엑셀 업로드' 또는 POST /api/qb/sites/upload {{b64, replace_product: true}})")

    if args.apply:
        # 같은 제품·페이지타입 항목을 파일별로 교체: 교체/동일 사이트는 새 URL, finder 미확인 사이트는 기존 유지
        new_by_site = {r["sitecode"]: r for r in rows}
        touched = 0
        for p in reg["files"]:
            d = json.load(open(p, encoding="utf-8"))
            sites = d.get("sites", [])
            out_sites = []
            seen = set()
            for e in sites:
                if e.get("product") == args.product and (e.get("page_type") or "PDP") == args.page_type:
                    n = new_by_site.get(e["sitecode"])
                    if n:
                        if _abs(e["url"]) != n["url"]:
                            touched += 1
                        e = {**e, "url": n["url"]}
                    seen.add(e["sitecode"])
                out_sites.append(e)
            # 기존에 없던 사이트는 첫 파일에만 추가
            if p == reg["files"][0]:
                for sc, n in new_by_site.items():
                    if sc not in old_by_site:
                        out_sites.append({k: n[k] for k in cols}); touched += 1
            d["sites"] = out_sites
            d["count_in_part"] = len(out_sites)
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"--apply: 레지스트리 파일 갱신 완료 (변경 {touched}건) → git push 하세요")


if __name__ == "__main__":
    main()
