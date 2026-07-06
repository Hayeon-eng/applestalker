# Apple Stalker 🍎 & 큐비 🐝

한 저장소에 두 모듈이 함께 있습니다.

- **애플스토커 🍎 (Apple Stalker)** — 경쟁사 닷컴을 모니터링해 DATA/COPY/VISUAL 3축으로 분석하고,
  변경점·리포트(PPTX/Excel/메일)를 생성하는 기존 웹앱.
- **큐비 🐝** — 풀네임 **QA Bee**, 줄여서 **큐비**. 닷컴 페이지를 붕붕 돌며 규칙대로 검수. 삼성닷컴 제품 페이지의
  스키마·카피를 스펙(엑셀)과 대조해 오류를 잡는 **Dotcom QA** 모듈. (본 저장소의 신규 파트)

---

## 큐비 🐝 — Dotcom QA

### 무엇을 하나
| 단계 | 기능 | 파일 |
|---|---|---|
| A | **스키마 QA** — 페이지 JSON-LD ↔ 스펙 대조 (@type/@id/속성, Product.hasPart) | `schema_rule_parser.py`, `schema_checker.py`, `schema_rules.json` |
| C | **카피 QA** — 번역 불변 값만 검사(스펙 토큰 정확 일치 + 고유명사 존재) | `copy_rule_parser.py`, `copy_checker.py`, `copy_rules.json` |
| D | **사이트 레지스트리** — 91개(지역/국가/사이트코드/언어/URL) | `site_registry.py`, `site_registry.json` |
| G | **리포트** — 오류 Excel(as-is/to-be) + 메일 초안 | `qa_report.py` |
| E | **오케스트레이터** — 레지스트리 순회 검수(크롤러 주입) | `runner.py` |
| H | **API + 화면** — FastAPI 라우터 + React 탭 + `?` 검수기준 패널 | `qb_api.py`, `QubiTab.tsx` |

> B(Meta QA)는 이번 범위에서 제외. F(룰 업로드: xlsx/ppt/html/zip)는 후속.

### 카피 QA 설계 (번역 사이트 대응)
- **스펙 토큰**(숫자+하드웨어 단위: 200 MP, 1 TB, 512 GB, 5000 mAh, 2600 nits, 100x …) — 번역돼도
  동일하므로 페이지에 **정확히 있는지** 검사. 없으면 **오류(FAIL)**.
- **고유명사**(Snapdragon 8 Elite Gen 5, Vapor Chamber, Galaxy AI …) — 현지어 대체 가능성 있어
  **존재만 확인**, 없으면 **확인(WARN)**.
- 서술형 문장은 `=` 검사하지 않음.

### 설치 / 실행
```bash
pip install openpyxl fastapi        # (레포 requirements 에 이미 있으면 생략)

# 1) 스펙 엑셀 → 규칙 JSON (스펙덱 갱신 시 재실행)
python3 schema_rule_parser.py <schema_deck.xlsx> schema_rules.json
python3 copy_rule_parser.py   <copydeck.xlsx>    copy_rules.json

# 2) 단일 페이지 검수 (CLI)
python3 schema_checker.py schema_rules.json <page.html> M3
python3 copy_checker.py   copy_rules.json   <page.html> M3

# 3) 91개 순회 검수 + 리포트는 앱에서 (아래 API)
```

### 앱에 붙이기 (기존 애플스토커 FastAPI)
`backend/main.py` 의 `app = FastAPI(...)` 아래에 **이 2줄만** 추가하면 끝 (기존 HybridCrawler 자동 연결):
```python
from dotcom_qa.qb_api import qb_router, enable_default_crawler
app.include_router(qb_router)
enable_default_crawler()      # 91개 자동 순회 검수(/api/qb/run) 활성화
```
- `enable_default_crawler()` 는 기존 `crawler.HybridCrawler().crawl(url)` 로 HTML을 받아 큐비에 넘깁니다(async→sync 브리지 내장).
- 크롤 연결 없이 써도 됩니다 — 화면의 **HTML 붙여넣기 검수**나 `POST /api/qb/check` 는 크롤러 없이 동작.
- 커스텀 크롤러를 쓰려면 대신 `set_fetcher(내함수)` — `내함수(url) -> html`.

프론트에서 우측 진입점/탭으로:
```tsx
import QubiTab from "./QubiTab";
<QubiTab apiBase={API} />
```

### API
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/qb/sites` | 91개 사이트(지역별) |
| GET | `/api/qb/rules?product=M3` | 검수 기준(화면 `?` 패널용) |
| POST | `/api/qb/check` | `{html, product}` 단일 HTML 검수(네트워크 불필요) |
| POST | `/api/qb/run` | `{sitecodes?, product}` 크롤 후 순회 검수(fetcher 필요) |
| POST | `/api/qb/report.xlsx` | `{results}` → Excel |
| POST | `/api/qb/email-draft` | `{results}` → 메일 초안 HTML |

### 검증 상태
- 레퍼런스 `index.html`(S26 Ultra, M3): 스키마 PASS 12/WARN 1/FAIL 0, 카피 스펙 20/20 정상.
- 오류 주입 테스트(스키마 @type/속성/hasPart, 배터리 스펙 제거): 모두 정확히 검출.
- 레지스트리: 91개, 지역/국가 91/91, 언어 90/91(`ps` 미지정 → 사람이 채움).

---

## 저장소에 올리기 (병합 파일트리)

큐비는 **기존 애플스토커 파일을 건드리지 않고** 대부분 새 폴더로 들어갑니다.
아래에서 `★ NEW` 가 이번에 추가/수정할 파일입니다.

```
applestalker-main/
├─ backend/
│  ├─ main.py                     ← (수정) qb_router 3줄 mount   ★ NEW(3줄)
│  ├─ crawler.py, crawl_service.py, intel_engine.py, …  (기존 그대로)
│  └─ dotcom_qa/                                          ★ NEW 폴더
│     ├─ __init__.py              (빈 파일; 패키지 인식)   ★ NEW
│     ├─ schema_rule_parser.py                            ★ NEW
│     ├─ schema_checker.py                                ★ NEW
│     ├─ schema_rules.json                                ★ NEW
│     ├─ copy_rule_parser.py                              ★ NEW
│     ├─ copy_checker.py                                  ★ NEW
│     ├─ copy_rules.json                                  ★ NEW
│     ├─ site_registry.py                                 ★ NEW
│     ├─ site_registry.json                               ★ NEW
│     ├─ qa_report.py                                     ★ NEW
│     ├─ runner.py                                        ★ NEW
│     └─ qb_api.py                                        ★ NEW
├─ frontend/src/app/
│  ├─ QubiTab.tsx                 ← 큐비 탭 컴포넌트         ★ NEW
│  └─ page.tsx                    ← (선택) 탭/진입점에 <QubiTab/> 추가
├─ requirements.txt               ← openpyxl 없으면 추가
└─ README.md                      ← 본 문서
```

### git 업로드 절차
```bash
# 1) 위 트리대로 파일 배치 (dotcom_qa 폴더 통째 복사 + QubiTab.tsx)
mkdir -p backend/dotcom_qa
cp <이 zip의 dotcom_qa>/* backend/dotcom_qa/
touch backend/dotcom_qa/__init__.py
cp <이 zip의>/QubiTab.tsx frontend/src/app/

# 2) main.py 의 app=FastAPI(...) 아래에 2줄 추가:
#      from dotcom_qa.qb_api import qb_router, enable_default_crawler
#      app.include_router(qb_router); enable_default_crawler()

# 3) 문법/타입 확인
cd backend && python3 -m py_compile dotcom_qa/*.py
cd ../frontend && npx tsc --noEmit

# 4) 커밋 & 푸시 (배포형이면 자동 재빌드)
git add backend/dotcom_qa frontend/src/app/QubiTab.tsx backend/main.py README.md
git commit -m "feat: 큐비 Dotcom QA 모듈 추가 (스키마/카피 QA, 91사이트 레지스트리, 리포트, API, 탭)"
git push
```

> `__init__.py` 는 빈 파일로 만들면 됩니다(패키지 인식용). 규칙 JSON(`*_rules.json`)은
> 스펙덱이 바뀔 때 파서를 다시 돌려 갱신하세요.
