"""
test_spec_engine_v3.py — 큐비 Spec QA V3 회귀 테스트

고정하는 것:
  A. [스크린샷 오탐 재현 케이스] KR Fold7 마케팅형 PDP — V2가 Critical 4건을 냈던
     문장들에서 V3는 오탐을 내지 않는다 (Resolution/Refresh/Brightness).
  B. 다국어 값 인정: 2600 nits = 2,600 nits = 2600nits = 2600니트 = 2,600니트
     = 2600ニト = ٢٦٠٠ نت 모두 PASS.
  C. 소수점 콤마(6,5 Zoll)·천단위(4.400 mAh, 2 600 nits) 로케일 표기 PASS.
  D. 복수 정답: Typical 4,400 또는 Rated 4,272 어느 표기든 PASS.
  E. 한정어 오짝: '일반(typical) 4,272mAh' → FAIL.
  F. 라벨 동반 오답: '최대 밝기 1,750니트' → FAIL.
  G. 전작 귀속: 'Galaxy Z Fold6의 2,600니트' → 정상(무시), 'Fold6 …1,750니트' → 전작 오기재 FAIL.
  H. 값 없음 = na (오류 아님) · exists 룰 미존재.
  I. 근사 표기('약 8인치') → warn / 라벨 없는 단독 불일치 → warn.
  J. 단위 합집합: 12GB(RAM 정답)가 Storage 룰에서 오답으로 잡히지 않음.
  K. Compare 컬럼 귀속: 이웃 전작 컬럼의 값은 무관, 대상 컬럼 오답은 FAIL.
실행: python3 test_spec_engine_v3.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import spec_engine

RS = json.load(open(os.path.join(os.path.dirname(__file__),
                                 "spec_rules.seed.galaxy-z-fold7.json"), encoding="utf-8"))

FAILED = []
def check(name, cond, info=""):
    tag = "PASS" if cond else "FAIL"
    if not cond:
        FAILED.append(name)
    print(f"[{tag}] {name}" + (f" — {info}" if info and not cond else ""))

def run(html, page_type="PDP"):
    return spec_engine.run(html, RS, page_type=page_type, sitecode="sec")

def item(res, rule_id):
    return next(i for i in res["items"] if i["rule_id"] == rule_id)

P = lambda *body: "<html><body>" + "".join(f"<p>{b}</p>" for b in body) + "</body></html>"

# ── A. 스크린샷 오탐 재현 (V2 Critical 4건 → V3 오탐 없음) ─────────────
html_a = P(
    "고해상도의 동영상 촬영을 자주 하는 경우라면 최대 1TB의 넉넉한 저장 공간을 선택하여 "
    "용량 부족이나 속도 저하 없이 소중한 순간을 기록해보세요",
    "최대 2,600니트 밝기와 최대 120Hz 주사율을 지원하는 고해상도 화면을 즐겨보세요",
)
res = run(html_a)
check("A1 Main Resolution — 저장공간 문장 오탐 없음(FAIL 아님)",
      item(res, "DISPLAY_002")["status"] != "fail", item(res, "DISPLAY_002")["message"])
check("A2 Cover Resolution — 오탐 없음", item(res, "DISPLAY_004")["status"] != "fail")
check("A3 Refresh Rate — 같은 문장의 2600을 오답으로 안 잡음(PASS)",
      item(res, "DISPLAY_005")["status"] == "pass", item(res, "DISPLAY_005")["message"])
check("A4 Peak Brightness — 값이 라벨 앞에 있어도 PASS",
      item(res, "DISPLAY_006")["status"] == "pass", item(res, "DISPLAY_006")["message"])

# ── B. 다국어 표기 변형 전부 PASS ─────────────────────────────────────
for i, txt in enumerate(["최대 2600 nits 밝기", "peak brightness of 2,600 nits",
                         "2600nits까지", "최대 2600니트", "무려 2,600니트!",
                         "最大2600ニトの輝度", "سطوع يصل إلى ٢٦٠٠ نت"]):
    r = run(P(txt))
    check(f"B{i+1} '{txt}' → Brightness PASS",
          item(r, "DISPLAY_006")["status"] == "pass", item(r, "DISPLAY_006")["message"])

# ── C. 로케일 숫자 표기 ───────────────────────────────────────────────
r = run(P("Hauptdisplay: 8,0 Zoll"))
check("C1 독일어 소수점 콤마 '8,0 Zoll' → Main Display Size PASS",
      item(r, "DISPLAY_001")["status"] == "pass", item(r, "DISPLAY_001")["message"])
r = run(P("Akku: 4.400 mAh (typisch)"))
check("C2 독일어 천단위 '4.400 mAh' → Battery PASS",
      item(r, "BATTERY_001")["status"] == "pass", item(r, "BATTERY_001")["message"])
r = run(P("luminosité maximale de 2 600 nits"))
check("C3 프랑스어 공백 천단위 '2 600 nits' → PASS",
      item(r, "DISPLAY_006")["status"] == "pass")

# ── D. 복수 정답 ─────────────────────────────────────────────────────
r = run(P("배터리 용량(정격) 4,272mAh"))
check("D1 Rated 4,272mAh만 있어도 Battery PASS",
      item(r, "BATTERY_001")["status"] == "pass", item(r, "BATTERY_001")["message"])
r = run(P("4,400mAh(일반) 대용량 배터리"))
check("D2 Typical 4,400mAh 표기 PASS", item(r, "BATTERY_001")["status"] == "pass")

# ── E. 한정어 오짝 → FAIL ────────────────────────────────────────────
r = run(P("배터리 용량: 4,272mAh (일반)"))
check("E1 '일반 4,272mAh' 한정어 오짝 → FAIL",
      item(r, "BATTERY_001")["status"] == "fail", item(r, "BATTERY_001")["message"])
r = run(P("일반 용량 4,400mAh · 정격 용량 4,272mAh"))
check("E2 두 값이 올바른 짝으로 병기되면 PASS",
      item(r, "BATTERY_001")["status"] == "pass", item(r, "BATTERY_001")["message"])

# ── F. 라벨 동반 오답 → FAIL ─────────────────────────────────────────
r = run(P("최대 밝기 1,750니트의 화면"))
check("F1 '최대 밝기 1,750니트' → Brightness FAIL",
      item(r, "DISPLAY_006")["status"] == "fail", item(r, "DISPLAY_006")["message"])
r = run(P("주사율: 최대 90Hz"))
check("F2 '주사율 90Hz' → Refresh FAIL",
      item(r, "DISPLAY_005")["status"] == "fail", item(r, "DISPLAY_005")["message"])

# ── G. 전작 귀속 ─────────────────────────────────────────────────────
r = run(P("Galaxy Z Fold6의 2,600니트와 동일한 밝기에, 더 얇아진 두께",
          "밝기 최대 2,600니트"))
check("G1 전작 정답값 언급은 정상(현재 제품 PASS 유지)",
      item(r, "DISPLAY_006")["status"] == "pass", item(r, "DISPLAY_006")["message"])
r = run(P("최대 2,600니트 밝기", "Galaxy Z Fold6의 1,750니트보다 한층 밝아진 화면"))
check("G2 전작 값 오기재(Fold6=2600인데 1750으로 표기) → FAIL",
      item(r, "DISPLAY_006")["status"] == "fail", item(r, "DISPLAY_006")["message"])

# ── H. 값 없음 = 오류 아님 · exists 룰 부재 ──────────────────────────
r = run(P("혁신적인 폴더블의 새 기준"))
check("H1 아무 값 없음 → critical 0", r["summary"]["critical"] == 0,
      str(r["summary"]))
check("H2 값 없음 항목은 na(집계 제외)", item(r, "DISPLAY_006")["status"] == "na")
check("H3 exists 룰이 결과에 없음",
      not any(i["validation"] == "exists" for i in r["items"]))

# ── I. 근사·단독 불일치 ─────────────────────────────────────────────
# [2026-07 운영 결정 변경] 근사 마커('약/約')가 있어도 값이 정답 집합 안이면 PASS.
# 'Up to 24 hours'의 현지화('約24時間'/'약 24시간')가 확인으로 내려가던 오탐 수정.
r = run(P("약 8인치의 대화면"))
check("I1 '약 8인치'(정답값 8.0) → PASS(근사 마커는 감점/확인 사유 아님)",
      item(r, "DISPLAY_001")["status"] == "pass", item(r, "DISPLAY_001")["message"])
r = run(P("約24 時間のビデオ再生"))
check("I1b '約24 時間'(정답 24 hours) → PASS(다국어 단위+근사 마커)",
      item(r, "BATTERY_004")["status"] == "pass", item(r, "BATTERY_004")["message"])
r = run(P("1,750니트로 촬영된 콘텐츠도 생생하게"))
check("I2 라벨·모델명 없는 단독 불일치 → warn(Critical 아님)",
      item(r, "DISPLAY_006")["status"] == "warn", item(r, "DISPLAY_006")["message"])

# ── I3. [2026-07] 델타 표기·타모델 비교 블록 오탐 방지 ──────────────
r = run(P("Galaxy Z Fold3 Folded 14.4 mm  Thickness (Folded) -5.5 mm  Weight -56 g"))
check("I3 전작 비교 델타(-5.5mm/-56g) → critical 0 (스펙 주장 아님)",
      r["summary"]["critical"] == 0, str(r["summary"]))
r = run(P("Galaxy S25 Ultra 8.2 mm  Thickness (Folded) +0.7 mm"))
check("I4 등록된 참조 모델(S25 Ultra) 두께 8.2mm + 델타 +0.7mm → critical 0",
      r["summary"]["critical"] == 0, str(r["summary"]))

# ── J. 단위 합집합 ───────────────────────────────────────────────────
r = run(P("12GB RAM과 256GB 저장 공간"))
sto = item(r, "MEMORY_002")
check("J1 RAM 12GB가 Storage 룰 오답으로 안 잡힘(FAIL 아님)",
      sto["status"] != "fail", sto["message"])
check("J2 RAM 룰은 PASS", item(r, "MEMORY_001")["status"] == "pass")

# ── K. Compare 컬럼 귀속 ─────────────────────────────────────────────
tbl = """<html><body><table>
<tr><th>Spec</th><th>Galaxy Z Fold7</th><th>Galaxy Z Fold6</th></tr>
<tr><td>Peak Brightness</td><td>2,600 nits</td><td>2,600 nits</td></tr>
<tr><td>Main Resolution</td><td>2184 x 1968</td><td>2160 x 1856</td></tr>
</table></body></html>"""
r = run(tbl, page_type="Compare")
check("K1 전작 컬럼(2160 x 1856)은 오답 아님 — Main Resolution PASS",
      item(r, "DISPLAY_002")["status"] == "pass", item(r, "DISPLAY_002")["message"])
tbl_bad = tbl.replace("<td>2184 x 1968</td><td>2160 x 1856</td>",
                      "<td>2208 x 1840</td><td>2160 x 1856</td>")
r = run(tbl_bad, page_type="Compare")
check("K2 대상(Fold7) 컬럼 오답 2208 x 1840 → Main Resolution FAIL",
      item(r, "DISPLAY_002")["status"] == "fail", item(r, "DISPLAY_002")["message"])

# ── L. 범용 단위 'x' — 해상도 NxM을 줌 배율로 오인하지 않음 ──────────
r = run(P("8.0인치 메인 디스플레이 · 2184 x 1968 (QXGA+)", "3배 광학 줌"))
check("L1 해상도 x가 Optical Zoom 오답/확인으로 안 잡힘",
      item(r, "CAM_004")["status"] in ("pass", "na"), item(r, "CAM_004")["message"])
check("L2 Main Resolution PASS 유지", item(r, "DISPLAY_002")["status"] == "pass")
r = run(P("100x 줌"))
check("L3 라벨 없는 100x는 warn(단독 불일치)로만",
      item(r, "CAM_004")["status"] == "warn", item(r, "CAM_004")["message"])

# ── M. 텍스트 룰(Processor) — 다른 서술은 오류 아님, 전작 칩명 혼입만 FAIL ──
r = run('<html><body><table><tr><td>CPU</td><td>3나노 프로세서</td></tr></table></body></html>')
check("M1 'CPU: 3나노 프로세서' — Snapdragon 미포함이어도 FAIL 아님(na)",
      item(r, "CPU_001")["status"] == "na", item(r, "CPU_001")["message"])
r = run('<html><body><table><tr><td>CPU</td><td>Snapdragon 8 Elite for Galaxy</td></tr></table></body></html>')
check("M2 정답 칩명 표기 → PASS", item(r, "CPU_001")["status"] == "pass")
r = run('<html><body><table><tr><td>CPU</td><td>Snapdragon 8 Gen 3</td></tr></table></body></html>')
check("M3 전작 칩명(8 Gen 3) 혼입 → FAIL",
      item(r, "CPU_001")["status"] == "fail", item(r, "CPU_001")["message"])

# ── N. 범용 단위 'x' — 라벨 동반 다른 배율도 FAIL 아닌 확인 ──────────
r = run(P("200MP 광각 카메라 광학 줌 수준의 2배 줌"))
check("N1 '광학 줌 수준의 2배' → Optical Zoom warn(확인), FAIL 아님",
      item(r, "CAM_004")["status"] == "warn", item(r, "CAM_004")["message"])

# ── O. 점수 — 확인은 분모 제외 (100% + 확인 배지) ────────────────────
r = run(P("무게 215g", "1,750니트로 촬영된 콘텐츠도 생생하게"))
dim = next(c for c in r["categories"] if c["category"] == "Dimension")
disp = next(c for c in r["categories"] if c["category"] == "Display")
check("O1 확인만 있는 카테고리 점수는 감점 없음(100 또는 None)",
      disp["score"] in (100.0, None) and disp["warn"] >= 1, str(disp))
check("O2 pass만 있는 카테고리 100%", dim["score"] == 100.0, str(dim))
check("O3 전체 점수도 확인 미반영", r["summary"]["score"] in (100.0, None), str(r["summary"]))

# ── P. [Compare 스크린샷 오탐] 숫자 없는 페어·행 배치·전작 혼입 구분 ──
def TBL(rows_):
    return "<html><body><table>" + "".join(
        f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in rows_) + "</table></body></html>"

r = run(TBL([("Cover Display Size", "Cover Display Size"), ("Weight", "무게")]), page_type="Compare")
check("P1 라벨성 텍스트(숫자 없음)가 값으로 잡혀도 FAIL 아님 — Cover Display Size na",
      item(r, "DISPLAY_003")["status"] == "na", item(r, "DISPLAY_003")["message"])
check("P2 Weight도 na(오류 0)", item(r, "DIM_001")["status"] == "na"
      and r["summary"]["critical"] == 0, str(r["summary"]))

r = run(TBL([("Cover Display Size", "8.0 inch")]), page_type="Compare")
check("P3 같은 단위 다른 스펙 정답값(메인 8.0이 커버 행에) → warn",
      item(r, "DISPLAY_003")["status"] == "warn", item(r, "DISPLAY_003")["message"])

r = run(TBL([("Weight", "239 g")]), page_type="Compare")
check("P4 전작 정답값(Fold6 239g)이 현 제품 행에 → FAIL(전작 값 혼입)",
      item(r, "DIM_001")["status"] == "fail", item(r, "DIM_001")["message"])

r = run(P("무게(Weight) 239 g의 가벼운 바디"))
check("P5 본문에서도 모델명 없이 전작 값+라벨 → FAIL",
      item(r, "DIM_001")["status"] == "fail", item(r, "DIM_001")["message"])
r = run(P("무게(Weight) 215 g의 가벼운 바디"))
check("P6 정답 무게는 PASS 유지", item(r, "DIM_001")["status"] == "pass")

# ── Q. Compare 한국어 헤더 귀속 · 일반 헤더 미skip · 감지0 진단 ─────
kr_tbl = """<html><body><table>
<tr><th>사양</th><th>갤럭시 Z 폴드7</th><th>갤럭시 Z 폴드6</th></tr>
<tr><td>Cover Display Size</td><td>6.5 인치</td><td>6.3 인치</td></tr>
<tr><td>Weight</td><td>215 g</td><td>239 g</td></tr>
</table></body></html>"""
r = run(kr_tbl, page_type="Compare")
check("Q1 한국어 헤더 '갤럭시 Z 폴드7' 컬럼 정상 귀속 → Cover Size PASS",
      item(r, "DISPLAY_003")["status"] == "pass", item(r, "DISPLAY_003")["message"])
check("Q2 전작(폴드6) 컬럼 6.3/239는 오류 아님 → critical 0",
      r["summary"]["critical"] == 0, str(r["summary"]))

gen_tbl = """<html><body><table>
<tr><th>구분</th><th>상세</th><th>비고</th></tr>
<tr><td>Weight</td><td>215 g</td><td>-</td></tr>
</table></body></html>"""
r = run(gen_tbl, page_type="Compare")
check("Q3 일반 헤더('상세') 컬럼이 skip되지 않음 → Weight PASS",
      item(r, "DIM_001")["status"] == "pass", item(r, "DIM_001")["message"])

r = run("<html><body><p>지금 구매하세요</p></body></html>", page_type="Compare")
check("Q4 감지 0이면 summary.diagnosis 제공(원인 힌트 포함)",
      r["summary"].get("detected") == 0 and bool(r["summary"].get("diagnosis", {}).get("hint")),
      str(r["summary"].get("diagnosis")))

print()
if FAILED:
    print(f"❌ {len(FAILED)} failed: {FAILED}"); sys.exit(1)
print("✅ all V3 regression tests passed (incl. L~Q)")
