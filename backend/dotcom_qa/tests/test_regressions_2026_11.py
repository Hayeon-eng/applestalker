"""
2026-11 판정 로직 개선 회귀 테스트 — PPT(oc.pptx) 지적사항 + 정상 페이지로 재현한 추가 오탐.
실행:  cd backend/dotcom_qa && python -m pytest tests/ -q      (또는 python tests/test_regressions_2026_11.py)

각 테스트는 "무엇이 오탐이었고(before) 어떻게 판정해야 하는지(after)"를 하나씩 고정한다.
여기 케이스가 깨지면 그 오탐이 되살아난 것이다.
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
QA = os.path.dirname(HERE)
sys.path.insert(0, QA)
sys.path.insert(0, os.path.dirname(QA))

import spec_engine                    # noqa: E402
import spec_value_match as svm        # noqa: E402
import static_qa                      # noqa: E402
import schema_checker                 # noqa: E402
import runner                         # noqa: E402
import copy_checker                   # noqa: E402

RS = json.load(open(os.path.join(QA, "spec_rules.seed.galaxy-z-fold8.json"), encoding="utf-8"))


def _spec(html: str):
    r = spec_engine.run(html, RS, "PDP", "fr")
    return {it["attribute"]: it for it in r["items"]}, r["summary"]


# ── Spec QA ───────────────────────────────────────────────────────────
def test_S1_dimension_triplet_not_judged_by_first_number():
    """'153,5 × 68,1 × 12,1 mm' 의 153.5 를 두께로 판정해 FAIL 내던 오탐(PPT 2번)."""
    items, _ = _spec('<html><body><h1>Galaxy Z Fold8</h1><div class="body"><dl>'
                     '<dt>Dimensions (plié/déplié)</dt><dd>158,4 × 72,8 × 9,7 mm / 158,4 × 143,2 × 4,5 mm</dd></dl></div></body></html>')
    assert items["Thickness (Folded)"]["status"] == "pass"
    assert items["Thickness (Unfolded)"]["status"] == "pass"


def test_S2_predecessor_only_value_is_warn_with_reason():
    """전작(Fold6) 정답값만 있고 현 제품 값이 없으면 FAIL 이 아니라 '확인 필요' + 사유(운영 결정)."""
    items, s = _spec('<html><body><h1>Galaxy Z Fold8</h1><div class="body"><dl><dt>Poids</dt><dd>239 g</dd>'
                     '<dt>Dimensions (plié/déplié)</dt><dd>153,5 × 68,1 × 12,1 mm / 153,5 × 132,6 × 5,6 mm</dd></dl></div></body></html>')
    for a in ("Weight", "Thickness (Folded)", "Thickness (Unfolded)"):
        assert items[a]["status"] == "warn", (a, items[a]["message"])
        assert "Fold6" in items[a]["message"] and "현 제품 정답" in items[a]["message"]
    assert s["critical"] == 0 and s["score"] == 100.0


def test_S2b_true_misprint_still_fails():
    items, _ = _spec('<html><body><h1>Galaxy Z Fold8</h1><div class="body"><dl><dt>Poids</dt><dd>211 g</dd>'
                     '<dt>Dimensions (plié/déplié)</dt><dd>158,4 × 72,8 × 9,9 mm / 158,4 × 143,2 × 4,5 mm</dd></dl></div></body></html>')
    assert items["Weight"]["status"] == "fail" and "211" in items["Weight"]["message"]
    assert items["Thickness (Folded)"]["status"] == "fail" and "9.9" in items["Thickness (Folded)"]["message"]
    assert any(t["step"] == "pair" for t in items["Weight"]["trace"]), "판정 과정에 구조 페어 단계가 기록돼야 한다"


def test_S3_5G_is_not_grams():
    items, _ = _spec('<html><body><h1>Galaxy Z Fold8</h1><div class="body"><p>Galaxy Z Fold8 5G. Poids 201 g.</p></div></body></html>')
    assert items["Weight"]["status"] == "pass", items["Weight"]["message"]


def test_S4_delta_values_in_comparison_are_not_errors():
    """'Plus fin de 0,8 mm' / '14 g de moins' — 현 제품·전작 정답의 차이값은 스펙 주장이 아님."""
    items, s = _spec('<html><body><h1>Galaxy Z Fold8</h1><div class="body">'
                     '<p>Poids 201 g. Plié 9,7 mm, déplié 4,5 mm.</p>'
                     '<p>Comparé au Galaxy Z Fold7 : 215 g, 8,9 mm, 4,2 mm. Plus fin de 0,8 mm. Pèse 14 g de moins.</p>'
                     '<p>Plus léger de 14 g et plus fin de 0,8 mm que la génération précédente.</p></div></body></html>')
    assert s["critical"] == 0, [(k, v["message"]) for k, v in items.items() if v["status"] == "fail"]


def test_S4b_delta_is_same_attribute_only():
    """|4.5 − 14.4| = 9.9 처럼 속성이 다른 조합을 차이값으로 보면 진짜 오기재(9.9mm)가 묻힌다."""
    items, _ = _spec('<html><body><h1>Galaxy Z Fold8</h1><div class="body"><p>Épaisseur 9,9 mm plié.</p></div></body></html>')
    assert items["Thickness (Folded)"]["status"] == "fail"


def test_S5_same_evidence_counted_once():
    items, s = _spec('<html><body><h1>Galaxy Z Fold8</h1><div class="body"><p>Résolution principale 2184 x 1968 pixels.</p></div></body></html>')
    assert items["Main Resolution"]["status"] == "fail"
    assert items["Cover Resolution"]["status"] == "na" and items["Cover Resolution"].get("dup_of")
    assert s["critical"] == 1


def test_S6_fully_correct_page_scores_100():
    items, s = _spec('<html><body><h1>Galaxy Z Fold8</h1><div class="body">'
                     '<p>Galaxy Z Fold8 5G. Poids 201 g. Écran principal 7,6 pouces, écran externe 5,5 pouces, 3 000 nits, 1~120 Hz.</p>'
                     '<p>Caméra grand angle 50 MP, ultra grand angle 50 MP, frontale 10 MP. Zoom optique 3x, Space Zoom 30x.</p>'
                     '<p>Batterie 4 800 mAh (typique) / 4 660 mAh (nominale). Lecture vidéo jusqu\'à 26 heures. Charge 25 W.</p>'
                     '<p>12 Go RAM, 256 Go / 512 Go / 1 To. Plié 9,7 mm, déplié 4,5 mm. IP48. Snapdragon 8 Elite Gen 5 for Galaxy.</p>'
                     '<p>Résolution 1848 x 2448 (QXGA+). Externe 1972 x 1248.</p>'
                     '<p>Comparé au Galaxy Z Fold7 : 215 g, 8,9 mm, 4,2 mm. Plus fin de 0,8 mm. Pèse 14 g de moins.</p></div></body></html>')
    assert s["critical"] == 0 and s["warning"] == 0 and s["score"] == 100.0


# ── 공통페이지 QA ─────────────────────────────────────────────────────
def _ld(o):
    return '<script type="application/ld+json">' + json.dumps(o) + "</script>"


U = "https://www.samsung.com/uk/"
ORG_DEF = {"@context": "https://schema.org", "@type": "Organization", "@id": U + "#org", "name": "Samsung UK", "url": U}
ORG_REF = {"@type": "Organization", "@id": U + "#org"}
WEB = {"@context": "https://schema.org", "@type": "WebSite", "@id": U + "#website", "name": "Samsung UK", "url": U, "publisher": ORG_REF}
PAGE = {"@context": "https://schema.org", "@type": "WebPage", "@id": U + "#webpage", "url": U,
        "isPartOf": {"@type": "WebSite", "@id": U + "#website"}, "publisher": ORG_REF}


def test_T1_reference_nodes_are_not_duplicates_or_missing_props():
    r = static_qa.check_static_page("<html><head>" + _ld(ORG_DEF) + _ld(WEB) + _ld(PAGE) + "</head></html>", U, "uk", 200)
    assert r["status"] == "정상" and r["duplicate_ids"] == [] and r["rich_missing"] == []


def test_T2_identical_duplicate_definition_hidden_differing_flagged():
    r = static_qa.check_static_page("<html><head>" + _ld(ORG_DEF) + _ld(ORG_DEF) + _ld(WEB) + _ld(PAGE) + "</head></html>", U, "uk", 200)
    assert r["status"] == "정상" and r["duplicate_ids"] == [] and r["identical_duplicate_ids"] == [U + "#org"]
    org2 = dict(ORG_DEF, name="Samsung Electronics UK")
    r = static_qa.check_static_page("<html><head>" + _ld(ORG_DEF) + _ld(org2) + _ld(WEB) + _ld(PAGE) + "</head></html>", U, "uk", 200)
    assert r["status"] == "기타" and r["duplicate_ids"] == [U + "#org"]


# ── DATA QA ───────────────────────────────────────────────────────────
PD = "https://www.samsung.com/uk/smartphones/galaxy-z-fold8/"


def _fold8_page(video_frags=("video-form-factor", "video-galaxy-ai"), with_quote=False,
                desc="The thinnest Fold yet — it’s light, and the display is brighter for your everyday use."):
    org = {"@type": "Organization", "@id": "https://www.samsung.com/#org"}
    web = {"@context": "https://schema.org", "@type": ["WebPage", "ItemPage"], "@id": PD + "#webpage", "url": PD, "inLanguage": "en-GB",
           "name": "Galaxy Z Fold8 | Samsung UK", "description": desc,
           "primaryImageOfPage": {"@type": "ImageObject", "url": "https://images.samsung.com/uk/smartphones/galaxy-z-fold8/images/hero.jpg"},
           "mainEntity": {"@id": PD}, "about": {"@id": PD}, "breadcrumb": {"@id": PD + "#breadcrumb"},
           "hasPart": [{"@id": PD + "#faq"}, {"@id": PD + "#model3d"}] + [{"@id": PD + "#" + f} for f in video_frags], "publisher": org}
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "@id": PD + "#breadcrumb", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.samsung.com/uk/"},
        {"@type": "ListItem", "position": 2, "name": "Smartphones", "item": "https://www.samsung.com/uk/smartphones/"},
        {"@type": "ListItem", "position": 3, "name": "Galaxy Z Fold8", "item": PD}]}
    prod = {"@context": "https://schema.org", "@type": "Product", "@id": PD, "name": "Samsung Galaxy Z Fold8", "description": desc,
            "brand": {"@type": "Brand", "@id": "https://www.samsung.com/uk/#brand-galaxy"}, "manufacturer": org,
            "image": ["https://images.samsung.com/uk/smartphones/galaxy-z-fold8/images/kv.jpg"],
            "potentialAction": {"@type": "BuyAction", "target": PD + "buy/"}, "mainEntityOfPage": {"@id": PD + "#webpage"},
            "subjectOf": [{"@id": PD + "#model3d"}], "hasPart": [{"@id": PD + "#faq"}, {"@id": PD + "#model3d"}] + [{"@id": PD + "#" + f} for f in video_frags]}
    m3 = {"@context": "https://schema.org", "@type": "3DModel", "@id": PD + "#model3d", "name": "3D", "isPartOf": {"@id": PD + "#webpage"},
          "about": {"@id": PD}, "encoding": [{"@type": "MediaObject", "contentUrl": "https://images.samsung.com/uk/x.glb", "encodingFormat": "model/gltf-binary"}]}
    vids = [{"@context": "https://schema.org", "@type": "VideoObject", "@id": PD + "#" + f, "name": f, "description": desc,
             "uploadDate": "2026-07-22", "duration": "PT6S", "thumbnailUrl": "https://images.samsung.com/uk/" + f + ".jpg",
             "publisher": org, "isPartOf": {"@id": PD + "#webpage"}, "about": {"@id": PD}, "inLanguage": "en-GB"} for f in video_frags]
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "@id": PD + "#faq", "inLanguage": "en-GB", "isPartOf": {"@id": PD + "#webpage"},
           "about": {"@id": PD}, "mainEntity": [{"@type": "Question", "name": "Weight?", "acceptedAnswer": {"@type": "Answer", "text": "201 g."}}]}
    blocks = [web, bc, prod, m3, faq] + vids
    if with_quote:
        blocks.append({"@context": "https://schema.org", "@type": "Quotation", "@id": PD + "#mediaquote-techradar", "text": "Great",
                       "author": {"@type": "Organization", "name": "TechRadar"}, "citation": "https://techradar.com/x", "about": {"@id": PD}, "inLanguage": "en-GB"})
    head = ('<title>Galaxy Z Fold8 | Samsung UK</title><meta name="description" content="Discover Galaxy Z Fold8 — the thinnest Galaxy Fold with Galaxy AI. Buy now at Samsung UK.">'
            f'<meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="{PD}">')
    return f"<!doctype html><html lang='en-GB'><head>{head}{''.join(_ld(b) for b in blocks)}</head><body><h1>Galaxy Z Fold8</h1><h2>Galaxy AI</h2><p>201 g</p></body></html>"


def _data_qa(html, sitecode="uk", lang="en"):
    rules = runner.load_rules("M3", page_type="PDP", market_product="galaxy-z-fold8", url=PD)
    site = {"sitecode": sitecode, "lang": lang, "url": PD, "product": "galaxy-z-fold8"}
    return runner.run_site(site, html, rules, page_type="PDP", rendered_by="httpx", mode="data", http_status=200, final_url=PD)


def test_D2_D3_D4_D5_compliant_page_has_no_findings():
    """정답대로 만든 페이지: 스마트 따옴표·#video-1 고정 id·번역확인·조건부 없음 이 더 이상 오류/확인을 만들지 않는다."""
    res = _data_qa(_fold8_page())
    sch = res["schema"]["summary"]
    assert sch["fail"] == 0 and sch["warn"] == 0, [(f["block"], f.get("as_is")) for f in res["schema"]["findings"] if f["status"] in ("fail", "warn")]
    assert all(it["status"] == "pass" for it in res["seo"]["items"]), [i for i in res["seo"]["items"] if i["status"] != "pass"]
    assert res["html_qa"]["level2"]["axis2_parsing_rich_result"]["syntax_errors"] == []
    q = next(f for f in res["schema"]["findings"] if f["block"] == "Quotation")
    assert q["status"] == "na"


def test_D3_multi_instance_all_nodes_checked_and_haspart_mutual():
    """세 번째 영상이 hasPart 에 빠지면 잡아야 하고(상호 연결), 영상 노드의 누락 속성도 첫 노드가 아닌 전부에서 잡는다."""
    html = _fold8_page(video_frags=("video-a", "video-b"))
    # video-c 노드를 추가하되 hasPart 에는 넣지 않는다
    extra = {"@context": "https://schema.org", "@type": "VideoObject", "@id": PD + "#video-c", "name": "c",
             "uploadDate": "2026-07-22", "duration": "PT6S", "thumbnailUrl": "https://images.samsung.com/uk/c.jpg",
             "publisher": {"@id": "https://www.samsung.com/#org"}, "isPartOf": {"@id": PD + "#webpage"}}   # description 누락
    html = html.replace("</head>", _ld(extra) + "</head>")
    res = _data_qa(html)
    f = {x["block"]: x for x in res["schema"]["findings"]}
    assert f["VideoObject"]["status"] == "fail"
    assert any("video-c" in m and "description" in m for m in f["VideoObject"]["missing_props"])
    assert any("video-c" in m for m in f["WebPage, ItemPage"]["haspart_missing"])


def test_D4_english_text_on_nonenglish_site_is_info_only():
    res = _data_qa(_fold8_page(), sitecode="fr", lang="fr")
    prod = next(x for x in res["schema"]["findings"] if x["block"] == "Product")
    # (픽스처가 uk URL 이라 fr 기대값과의 URL 불일치는 정상적인 오류 — 여기선 '번역 확인'이 오류·확인이 아닌 참고로만 남는지 본다)
    assert prod.get("info_notes") and prod["info_notes"][0]["prop"] == "description"
    assert not any(v["prop"] == "description" for v in prod.get("val_mismatch", []))
    assert not any(t["prop"] == "description" for t in prod.get("translate_confirm", []))
    res_uk = _data_qa(_fold8_page())
    prod_uk = next(x for x in res_uk["schema"]["findings"] if x["block"] == "Product")
    assert prod_uk["status"] == "pass" and not prod_uk.get("info_notes"), "영어 사이트의 영어 문장엔 참고조차 붙지 않는다"


def test_G6_missing_required_block_lowers_score():
    html = _fold8_page()
    import re
    html_no_faq = re.sub(r'<script type="application/ld\+json">\{[^<]*"FAQPage"[^<]*</script>', "", html)
    full = _data_qa(html)["html_qa"]["overall"]["final_pct"]
    less = _data_qa(html_no_faq)["html_qa"]["overall"]["final_pct"]
    assert less < full, (full, less)


def test_D7_copy_checker_no_spec_value_judgement():
    rules = {"spec_tokens": [], "proper_nouns": ["Galaxy AI"]}
    body = "<p>Galaxy AI est là. Batterie 4 400 mAh pour toute la journée. " + "Texte de présentation du produit. " * 60 + "</p>"
    res = copy_checker.check_copy("<html><body>" + body + "</body></html>", rules,
                                  key_specs=[{"category": "Battery", "unit": "mAh", "values": ["4800"], "page_types": ["PDP"]}],
                                  page_type="PDP")
    # 예전 로직: 4800 기대인데 4400 이 있으니 '값 불일치 FAIL' — 이제 Spec QA 전담이라 판정하지 않는다
    assert res["summary"]["fail"] == 0 and res["summary"]["value_mismatch"] == 0
    assert any(f["kind"] == "spec_value" and f["status"] == "na" for f in res["findings"])


# ── 크롤러 — 에러 페이지 ──────────────────────────────────────────────
def test_D1_error_page_detected_regardless_of_language():
    import inspect
    import importlib.util
    spec = importlib.util.spec_from_file_location("qa_crawler", os.path.join(QA, "crawler.py"))   # 루트 crawler.py 와 구분
    crawler = importlib.util.module_from_spec(spec); spec.loader.exec_module(crawler)
    cls = [v for v in vars(crawler).values() if inspect.isclass(v) and hasattr(v, "_detect_bad_page")][0]
    obj = cls.__new__(cls)
    base = {"body_content": "x " * 200, "word_count": 200, "images": [1], "ctas": [1], "structured_data": [1]}
    lv = dict(base, title="SAMSUNG | Samsung LV", h1="Pieprasītā lapa nav pieejama", canonical_url="https://www.samsung.com/lv/common/error/")
    assert obj._detect_bad_page(lv, "https://www.samsung.com/lv/smartphones/galaxy-z-fold8/")
    lv2 = dict(lv, canonical_url=None)
    assert obj._detect_bad_page(lv2, "https://www.samsung.com/lv/smartphones/galaxy-z-fold8/")
    ok = dict(base, title="Galaxy Z Fold8 | Samsung UK", h1="Galaxy Z Fold8", canonical_url=PD)
    assert obj._detect_bad_page(ok, PD) is None


# ── appleStalker 인사이트 ──────────────────────────────────────────────
def test_I1_relative_metric_not_judged_weak_and_ahead_noted():
    sys.path.insert(0, os.path.dirname(QA))
    import insight_rules
    import insight_rules_base as b

    def blk(lifestyle, alt):
        return {"facts": {"schema": {"total_pages": 10, "coverage_pct": 90}, "image_diversity": {"total_images": 100, "lifestyle_ratio_pct": lifestyle,
                          "pages_with_images": 10, "total_pages": 10}, "alt_text_quality": {"descriptive_ratio_pct": alt, "gap_pages": []},
                          "page_inventory": {"total_pages": 10}}}
    ins = insight_rules.apple_stalker_insights({"data": {}, "copy": {}, "visual": {"samsung": blk(34, 54), "apple": blk(9, 30)}}, [])
    lines = [i["line"] for i in ins["by_metric"].get("visual", [])]
    assert not any("사용 장면" in l and "필요" in l for l in lines), lines
    assert any("설명형 ALT" in l and "경쟁사보다는 우세" in l for l in lines), lines
    sc = b.score_block("visual", blk(34, 54))
    assert [c["label"] for c in sc["components"]] == ["ALT ratio", "Image pages"] and sc["total"] == 77


# ── 운영 양식(템플릿 ①·②) ────────────────────────────────────────────
def test_P1_product_pack_roundtrip_and_draft(tmp_path=None):
    """제품 등록 워크북: 내보내기 → 재업로드(값 보존), 신모델 초안(전작 시트 자동·기대값 공란·슬러그 치환)."""
    import io
    os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/qubi_test_pack.db")
    sys.path.insert(0, os.path.dirname(QA))
    import database; database.init_db()
    import site_registry, spec_rule_db, product_master, product_pack_xlsx as pack, schema_values_xlsx as sx
    from openpyxl import load_workbook
    reg = site_registry.SiteRegistry(); reg.save = lambda *a, **k: None   # 디스크 저장 금지
    spec_rule_db.save("galaxy-z-fold8", RS, version="test")
    vals = runner._schema_values()
    try:
        exp = pack.build_export("galaxy-z-fold8", vals, reg)
        res = pack.parse_and_apply(exp, reg, url_mode="upsert")
        assert res["applied"]["URL"]["added"] == 0 and res["applied"]["URL"]["updated"] == 0
        assert res["applied"]["스펙 룰"]["rules"] == len(RS["rules"])
        assert res["applied"]["스키마 정답값"]["blocks"]["galaxy-z-fold8"] == 7
        drf = pack.build_draft("galaxy-z-fold8", "galaxy-z-fold9", "", vals, reg)
        wb = load_workbook(io.BytesIO(drf))
        ms = list(wb["스펙_MasterSpec"].iter_rows(min_row=2, values_only=True))
        assert ms and all(not r[3] for r in ms), "초안의 기대값(Official Value)은 비어 있어야 한다"
        pm = list(wb["스펙_PreviousModel"].iter_rows(min_row=2, values_only=True))
        assert any(r[0] == "Galaxy Z Fold8" and r[2] == "Weight" and "201" in str(r[3]) for r in pm), "이전 제품이 전작 시트로 들어가야 한다"
        blk = list(wb["스키마_블록"].iter_rows(min_row=2, values_only=True))
        assert all("galaxy-z-fold9" in str(r[3]) for r in blk if r[3])
        assert wb["제품정보"].cell(2, 5).value == "galaxy-z-fold8" and wb["제품정보"].cell(2, 4).value == "flagship"
        res2 = pack.parse_and_apply(drf, reg, url_mode="add")
        assert any("기대값" in w for w in res2["warnings"]), "빈 기대값은 경고로 알려야 한다"
        assert runner.schema_set_for("PDP", "galaxy-z-fold9") == "flagship"
    finally:
        for p in ("galaxy-z-fold8", "galaxy-z-fold9"):
            product_master.delete(p); sx.delete_uploaded(p)
        try:
            spec_rule_db.delete_product("galaxy-z-fold9")
        except Exception:
            pass
        runner.reset_schema_values_cache()


def test_P2_monitor_targets_parse_and_hc_validation():
    """모니터링 대상 워크북: 파싱·HC 검증(compare_to 가 없는 slug 면 거부)·AS_URL 계획(replace 모드는 미기재 URL 끔)."""
    import io
    sys.path.insert(0, os.path.dirname(QA))
    import monitor_targets_xlsx as mt
    from openpyxl import load_workbook
    cur = [{"site_key": "apple", "url": "https://www.apple.com/iphone/", "enabled": True, "tier_level": 1, "page_role": "pf", "source": "seed"},
           {"site_key": "apple", "url": "https://www.apple.com/ipad/", "enabled": True, "tier_level": 1, "page_role": "pf", "source": "seed"}]
    content = mt.build_export(cur)
    wb = load_workbook(io.BytesIO(content))
    assert set(mt.SHEETS) <= set(wb.sheetnames)
    parsed = mt.parse(content)
    assert len(parsed["AS_URL"]) == 2
    plan, warns = mt.as_url_plan([{"site_key": "apple", "url": "https://www.apple.com/iphone/", "enabled": "Y"}], lambda u: "apple", "replace", cur)
    assert ("apple", "https://www.apple.com/ipad/", False) in plan and not warns
    try:
        mt.apply_hc({"HC_경쟁사모델": [{"brand": "apple", "model": "iPhone X", "compare_to": "no-such-slug"}]}, "upsert")
        assert False, "없는 slug 는 거부해야 한다"
    except ValueError:
        pass
    import shutil
    shutil.rmtree(mt.HC_HISTORY, ignore_errors=True)


if __name__ == "__main__":
    import traceback
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("PASS", name)
            except Exception:
                fails += 1; print("FAIL", name); traceback.print_exc()
    print("\n", "ALL PASS" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)


