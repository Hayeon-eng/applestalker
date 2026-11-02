# ABC 툴 업데이트 (2026-11) — 변경 내역

근거: `ABC툴_업데이트.pptx` 1~12번 + 협의 결과(인사이트 문장 형식·판단 기준·Apple 비교 범위).

## 1. 핵심 구조 — 인사이트 단일 소스

- 신규 `backend/insight_rules.py` 가 모든 인사이트 문장을 만든다. 화면·Quick View·메일·PPTX·Excel 은 이 결과를 그대로 표시만 한다 → 어디서 보든 같은 문장.
- 신규 `frontend/src/app/insightUi.tsx` (`InsightBox`) — 공통 표시 컴포넌트. 박스 하단에 판단 기준(임계값)을 항상 표시.
- 문장 형식: `[누가] [무엇이] [수치] (비교 기준) 부족/열세/우세 → [어디에] [무엇을] 필요` · 최대 3줄 · 경쟁사는 삼성보다 우세할 때만.
- 판단 기준: 70점(%) 미만 = 부족 · 비교 대상보다 10%p 이상 낮음 = 열세 / 높음 = 우세.

| 시스템 | 룰 | 사용 데이터 |
|---|---|---|
| appleStalker | D1 경쟁사 보유·삼성 미보유 스키마 타입 · D2 Product 누락 속성 · D3 페이지 유형별 누락 스키마 · D4 H1 없는 페이지 · @id 연결 | `facts.schema.*`, `html_structure.heading_issues` |
| | C1 수치 표현 밀도 · C2 전작 비교·근거 문구 · C3 FAQ · C4 구매 CTA 없는 페이지 · 본문 분량 · 중복 문구 | `facts.copy_richness.all_pages`, `commerce_cta`, `faq`, `duplication` |
| | V1 설명형 ALT · V2 사용 장면 이미지 · 이미지 보유율 | `facts.alt_text_quality`, `image_diversity` |
| | X1 경쟁사 변경 해석(가격 문구 추가·스키마 신규·본문 축소/확대·타이틀 변경 등) → 삼성 대응 페이지 비교 | `detected_changes` + evidence |
| qaBee | Q1 필수/권장 속성 누락 사이트 수 · Q2 권역 열세 · Q3 스펙 항목별 오류·정답 · Q4 공통페이지 오류 유형·주원인 | `html_qa.level2.per_type`, `spec_v2.items`, static run `results` |
| honeyComb | H1 1위 비율 · H2 국가 집중 미노출 · H3 제품 집중 미노출 · H4 속성 영역(이미지·가격·식별자·상세·배송) 부족/Apple 대비 열세 · H5 1위 판매처 가격 격차 · H6 주간 하락 | run `cells`, 직전 run |
| 권역 오버뷰 | R1 권역별 오류 법인 수·주원인 도구 · R2 여러 권역 공통 이슈 | `/api/overview/regions` 신호등 |

## 2. 요건별 처리 현황 (PPT 번호)

| # | 요건 | 처리 | 주요 파일 |
|---|---|---|---|
| 1~3 | appleStalker 문구 과다·요약 부재·로직 점검 | A1 변경 내용 기반 할 일 / A2 경쟁사 약점 행("Samsung은 유지하면 됩니다") 제거 / A3 `body_content 변경 (문장 +3/-13)` → `본문 변경: 3문장 추가, 13문장 삭제`(과거 수집분도 변환) / A4 "High 변경 13건 · 전체 58건" 기준 명시 / A5·A8 "그래서:" 고정 문장 → 인사이트 3줄 / A6 L5 본문 변경을 가격·프로모션으로 오분류하던 문제 + 배지-탭 매핑 / A7 수집 페이지 0개 사이트를 0점이 아닌 "근거 없음" / A9·A11 과밀 한 줄·사이트 카드 / A10 페이지 상세 패널(근거는 접기) | `insight_rules.py`, `main.py`, `diff_engine.py`, `sharedScoring.ts`, `overview*.tsx`, `sectionCommon.tsx`, `pagesSection.tsx`, `productSection.tsx` |
| 4 | 좌상단 타이틀 통일, SerpApi 잔여량 | `🍎 appleStalker`(S 빨강) · `🐝 qaBee`(B 노랑) · `🍯 honeyComb` / honeyComb 사이드바에 "남은 검색 N회 / 월 M회" + 실행 확인창에 예상 호출·잔여 표시 (SerpApi Account API — 무료, 월 한도 차감 없음, 60초 캐시) | `page.tsx`, `QubiSidebar.tsx`, `landing.tsx`, `hc_routes.py` `/api/hc/serpapi/account` |
| 5 | qaBee 3개 탭 100% 미만일 때 원인 표시 | DATA·스펙·공통페이지 상단 바 아래 인사이트 박스 | `qb_routes_history.py` (`/api/qb/overview` insights, `POST /api/qb/insights`), `qb_routes_static.py` |
| 6 | 비교 모듈 전작 값 오탐 | 원인: 오탐 값(239g·12.1mm·5.6mm)은 시드의 Galaxy Z Fold6 정답. 컬럼 제품명을 못 읽으면 대상 제품 오기재로 판정. 수정: 현 제품 정답이 같은 페이지에 함께 있으면 전작 컬럼으로 보고 제외. 전작 값만 있으면 기존대로 FAIL | `spec_engine.py`, `spec_value_match.py` |
| 7 | 공통페이지 QA 이력 좌우 중복 | 사이드바 이력을 탭 기준으로(공통페이지 탭 = 공통페이지 이력), 우측 드롭다운 제거. "90/91 국가" 표기를 "자동 검수 90 + 직접 확인 1 = 전체 91"로 통일 | `QubiSidebar.tsx`, `QubiStaticQa.tsx`, `QubiApp.tsx` |
| 8-1 | honeyComb 인사이트 | H1~H6 상단 요약 | `insight_rules.py`, `HoneyCombApp.tsx` |
| 8-2 | 1위 판매처 복잡 | 상위 3곳 + 칸 수 + "외 N곳", 벌집 칸 판매처명 말줄임 | `HoneyCombApp.tsx` |
| 8-3 | 경쟁사(Apple) 대비 | 사이드바에서 Apple 모델 선택(iPhone 18 Pro·iPhone Duo ↔ Fold8·Fold8 Ultra·Flip8 각각 둘 다, Watch Ultra 4↔Watch Ultra2, Series 12↔Watch9) → 전체·국가별 1위 비율, 속성 영역별 노출 비교 카드. 같은 Apple 모델은 국가당 1회만 호출 | `hc_config.json` `competitors`, `hc_engine.collect_competitors` |
| 9 | 상세 창 속성 전부 "안 보임" | 원인 3가지: ① 상세 조회 기본 OFF ② 미조회도 "안 보임" 판정 ③ 상세 파서가 일부 키만 읽음. 수정: 기본 ON / 미조회·실패는 "○ 확인 안 함"(계산 제외) / 상세 응답 JSON 전체에서 GMC 속성명 탐색(값에 출처 경로 표시) | `hc_engine.py`, `hc_provider.py`, `hc_routes.py`, `HoneyCombApp.tsx` |
| 10 | 권역 오버뷰 의미 불명 | 상단 "지금 가장 급한 이슈" 3줄, 권역 카드에 "주원인 → 할 일", KPI 라벨("C 4"→"오류 4건", "6/6"→"N개국") | `insight_rules.region_insights`, `main.py`, `RegionOverview.tsx` |
| 11 | Quick View 최신화 | appleStalker·qaBee 모두 같은 인사이트 표시, qaBee 제목 버그(공통페이지 탭에서 "스펙") 수정 | `overviewWidgets.tsx`, `QubiSections.tsx` |
| 12 | 랜딩 honeyComb 아이콘 | 부제의 "🐝C" → "🍯" | `landing.tsx` |
| 메일 | 인사이트 반영 | appleStalker·qaBee·honeyComb 메일 맨 위 요약 박스 + 판단 기준. appleStalker 는 PPTX·Excel 에도 반영(Excel "요약·할 일" 시트, 변경점 시트 "할 일" 열) | `email_service.py`, `qa_report.py`, `hc_email.py`, `export_service.py` |

## 3. 검증한 것
- 프론트엔드 `tsc --noEmit` 통과, `next build` 통과.
- 백엔드 FastAPI 앱 기동 후 변경 엔드포인트 200 응답: `/api/latest-report`, `/api/overview/regions`, `/api/qb/overview`, `POST /api/qb/insights`, `/api/qb/static/runs`, `/api/hc/config`, `/api/hc/run-estimate`, `/api/hc/serpapi/account`, `/api/export/email-html`.
- 룰 단위 테스트(합성 데이터): 실제 `intel_facts` 계산 결과로 appleStalker 문장 생성, qaBee Q1~Q4, honeyComb H1~H6(가짜 provider로 수집→인사이트 전 과정), 권역 R1·R2, 메일·PPTX·Excel 출력.
- C2 재현 테스트: 전작+현 제품 값 동시 → PASS / 전작 값만 → FAIL(기존 규칙 유지) / 무관한 틀린 값 → FAIL.

## 4. 실데이터로 확인이 필요한 것 (배포 후)
1. **honeyComb 상세 파서 확장** — SerpApi 상세 응답의 실제 구조를 샘플로 확인하지 못해, 경로를 가정하지 않고 키 이름 일치로 구현했다. 첫 실수집 후 속성 표의 `[출처: …]` 표시로 맞게 잡혔는지 확인.
2. **SerpApi 잔여량** — Account API 필드명(`total_searches_left`, `plan_searches_left`, `searches_per_month` 등)은 공식 문서 기준. 실제 키로 1회 확인. 실패하면 화면에 "확인 불가 · 사유"가 표시된다.
3. **Apple 공식몰 판정** — 판매처명에 "apple" 포함(리셀러 제외) 또는 apple.com 링크. 국가별 Apple Store 표기가 다르면 `hc_engine.is_brand_store` 의 리셀러 목록 보강.
4. **인사이트 문장 수치** — 테스트는 합성 데이터라, 실데이터에서 문장이 어색한 경우 `insight_rules.py` 의 해당 룰 텍스트만 고치면 화면·메일에 함께 반영된다.

## 5. 참고
- `backend/` 루트의 `runner.py`·`spec_engine.py` 등은 실제로 import 되지 않는 옛 사본(실행 경로는 `backend/dotcom_qa/`). 이번 수정은 `dotcom_qa/` 쪽에만 적용.
- `backend/dotcom_qa/test_spec_engine_v3.py` 는 저장소에 없는 `spec_rules.seed.galaxy-z-fold7.json` 을 참조해 이번 수정 이전부터 실행되지 않는다.
- `frontend/src/app/siteAnalysisSection.tsx` 는 어디서도 import 되지 않아 수정하지 않았다.
