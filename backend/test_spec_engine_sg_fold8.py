"""
test_spec_engine_sg_fold8.py — 큐비 Spec QA 회귀 테스트 [2026-09 S1~S5]

고정하는 것 (근거: 2026-09-11 SG Galaxy Z Fold8 PDP 저장본 — 렌더된 DOM):
  F. 픽스처 전체: 실제 스펙 오류가 없는 페이지에서 FAIL 0건, 정답 노출 17항목 PASS.
     (수정 전 결과: FAIL 7건 — 모두 오탐)
  S1. 고객 리뷰(UGC) 문장의 숫자는 판정 근거가 아니다.
  S2. 현 제품의 다른 스펙 정답(Wide 50MP)이 Front Camera 룰에서 전작 혼입 FAIL로 잡히지 않는다.
  S3. 한 블록에 형제 모델(Fold8 Ultra) 값과 대상 값이 함께 있을 때 숫자별로 귀속한다.
  S4. 옵션 '1 TB'(숫자-단위 공백) 인식.
  X1. 'PDP/Compare' 룰은 PDP 안의 Compare 위젯(section=compare)도 검사한다.
  X2. '7.6-inch'(하이픈) · '5.5”'(둥근 따옴표) 표기 인식.
실행: python3 test_spec_engine_sg_fold8.py
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import spec_engine  # noqa: E402
import spec_dict_global  # noqa: E402

HERE = os.path.dirname(__file__)
SEED = json.load(open(os.path.join(HERE, "spec_rules.seed.galaxy-z-fold8.json"), encoding="utf-8"))
RS = {**SEED, "dictionary": spec_dict_global.merge_for(SEED.get("dictionary", {}))}
FIXTURE = os.path.join(HERE, "fixtures", "sg_galaxy-z-fold8_pdp_2026-09-11.html.gz")

FAILED = []


def check(name, cond, info=""):
    tag = "PASS" if cond else "FAIL"
    if not cond:
        FAILED.append(name)
    print(f"[{tag}] {name}" + (f" — {info}" if info and not cond else ""))


def run(html, page_type="PDP"):
    return spec_engine.run(html, RS, page_type=page_type, sitecode="sg", rendered_by="test")


def item(res, attribute):
    return next(i for i in res["items"] if i["attribute"] == attribute)


P = lambda *body: "<html><body>" + "".join(f"<p>{b}</p>" for b in body) + "</body></html>"

# ── F. 실제 픽스처 ─────────────────────────────────────────────────────
html_f = gzip.open(FIXTURE, "rt", encoding="utf-8", errors="ignore").read()
res_f = run(html_f)
check("F1 SG Fold8 — FAIL 0건", res_f["summary"]["critical"] == 0,
      json.dumps([(i["attribute"], i["message"][:60]) for i in res_f["items"] if i["status"] == "fail"], ensure_ascii=False))
for attr in ["Product Name", "Main Display Size", "Cover Display Size", "Peak Brightness", "Processor",
             "RAM", "Storage Option", "Wide Camera", "Ultra Wide Camera", "Front Camera", "Cover Camera",
             "Battery Capacity", "Video Playback", "Weight", "Thickness (Folded)", "Thickness (Unfolded)",
             "Water Resistance"]:
    check(f"F2 {attr} PASS", item(res_f, attr)["status"] == "pass", item(res_f, attr)["message"])
check("F3 Storage 1TB 인식(S4)", "1TB" in item(res_f, "Storage Option")["found"], item(res_f, "Storage Option")["found"])
check("F4 화면 미노출 항목은 na(오류 아님)", all(item(res_f, a)["status"] == "na"
      for a in ["Model Code", "Main Resolution", "Cover Resolution"]))

# ── S1. 리뷰(UGC) 제외 ─────────────────────────────────────────────────
html_s1 = ('<html><body><div class="pd-g-product-bv-review"><p>This new fold 8 is amazing.. '
           'from the 8.0 inch screen display, plus 5000 mah battery</p></div>'
           '<p>Galaxy Z Fold8 main screen 7.6-inch, 4800 mAh battery</p></body></html>')
res = run(html_s1)
check("S1 리뷰의 8.0 inch 는 Main Display Size FAIL 근거 아님", item(res, "Main Display Size")["status"] == "pass",
      item(res, "Main Display Size")["message"])
check("S1 리뷰의 5000 mAh 는 Battery FAIL 근거 아님", item(res, "Battery Capacity")["status"] == "pass",
      item(res, "Battery Capacity")["message"])

# ── S2. 현 제품 다른 스펙 정답 > 전작 혼입 검사 ─────────────────────────
res = run(P("Camera: capture with the 50 MP wide camera and the 10 MP front camera"))
check("S2 Front Camera 룰이 자기 Wide 50MP 를 전작 혼입으로 잡지 않음", item(res, "Front Camera")["status"] == "pass",
      item(res, "Front Camera")["message"])
check("S2 Wide Camera PASS", item(res, "Wide Camera")["status"] == "pass")

# ── S3. 형제 모델 숫자별 귀속 ──────────────────────────────────────────
res = run(P("Power built for your experience. Galaxy Z Fold8 Ultra features a 5000 mAh battery, "
            "while Galaxy Z Fold8 comes with a 4800 mAh battery."))
check("S3 형제(Ultra) 5000mAh 와 대상 4800mAh 공존 → PASS", item(res, "Battery Capacity")["status"] == "pass",
      item(res, "Battery Capacity")["message"])
res = run(P("Both feature a 50 MP Ultra Wide camera, while Galaxy Z Fold8 Ultra adds a 200 MP Wide camera."))
check("S3 형제(Ultra) 200MP Wide 는 대상 Wide Camera FAIL 근거 아님", item(res, "Wide Camera")["status"] != "fail",
      item(res, "Wide Camera")["message"])
res = run(P("Galaxy Z Fold8 Ultra pairs a 6.5-inch cover screen with an expansive 8-inch main screen."))
check("S3 형제 전용 문장만 있으면 대상 Display Size 는 na(오류 아님)",
      item(res, "Main Display Size")["status"] in ("na", "warn"), item(res, "Main Display Size")["message"])
# 대상 제품 라벨과 함께 진짜 오답이 있으면 여전히 FAIL 이어야 한다(수정으로 탐지력이 죽지 않았는지)
res = run(P("Galaxy Z Fold8 battery capacity: 5000 mAh"))
check("S3 대상 제품 자체의 오답(5000mAh)은 FAIL 유지", item(res, "Battery Capacity")["status"] == "fail",
      item(res, "Battery Capacity")["message"])

# ── S4. 옵션 공백 ──────────────────────────────────────────────────────
res = run(P("Storage options: 256 GB, 512 GB and 1 TB"))
check("S4 '1 TB' 인식", "1TB" in item(res, "Storage Option")["found"], item(res, "Storage Option")["found"])

# ── X1. Compare 위젯 섹션 ───────────────────────────────────────────────
html_x1 = ('<html><body><div class="compare-key-specs"><span>5.5"</span><span>7.6"</span></div></body></html>')
res = run(html_x1)
check("X1 PDP 내 compare 섹션의 7.6\" 인식", item(res, "Main Display Size")["status"] == "pass",
      item(res, "Main Display Size")["message"])

# ── X2. 하이픈 · 둥근 따옴표 ────────────────────────────────────────────
res = run(P("Galaxy Z Fold8 features a 5.5-inch cover screen and 7.6-inch main screen."))
check("X2 '7.6-inch' 인식", item(res, "Main Display Size")["status"] == "pass", item(res, "Main Display Size")["message"])
res = run(P("Measured diagonally, Galaxy Z Fold8's Cover Screen size is 5.5” in the full rectangle."))
check("X2 '5.5”' 인식", item(res, "Cover Display Size")["status"] == "pass", item(res, "Cover Display Size")["message"])

print("\n" + ("ALL PASS" if not FAILED else f"{len(FAILED)} FAILED: {FAILED}"))
sys.exit(1 if FAILED else 0)
