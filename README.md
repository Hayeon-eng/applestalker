# Change Intelligence

경쟁사(애플) · 당사(삼성) 웹사이트의 변화를 매일 자동 감지하고, **변경점을 카테고리별로**
보여주며 AEO(AI 검색 노출) 관점의 시사점을 제공하는 경쟁 인텔리전스 플랫폼.

- **변경점이 메인**: 4 카테고리(데이터·스키마 / 카피 / 가격·프로모션 / 비주얼) × High·Medium·Low
- **현황 비교**: 삼성 ↔ 애플 실제 수집값 비교 (추측·환각 없음)
- 매일 09:00·14:00 KST 자동 크롤 + 이메일 리포트
- 이미지 비교샷(썸네일+변경영역), Excel/PPTX 다운로드, URL 런타임 추가

---

## 파일 구조 (단순)

```
.
├── README.md
├── requirements.txt              # 백엔드 의존성
├── render.yaml                   # 배포 참고
├── .github/workflows/scheduled-crawl.yml   # 정시 자동 크롤(GitHub Actions)
├── backend/
│   ├── main.py                   # FastAPI 엔드포인트 (전부 여기)
│   ├── config.py                 # 모니터링 대상/URL 정책 (확장 지점)
│   ├── crawler.py                # httpx + Playwright 하이브리드 크롤러
│   ├── diff_engine.py            # 변화 감지 (문자/문장/구조 + 이미지 + 중요도)
│   ├── intel_engine.py           # 근거기반 분석 (환각 차단)
│   ├── crawl_service.py          # 이벤트 파이프라인 (crawl→diff→event→분석)
│   ├── export_service.py         # Excel/PPTX
│   ├── email_service.py          # 일일 리포트 메일
│   ├── models.py                 # DB 테이블
│   ├── database.py               # DB 연결/초기화
│   └── .env.example
└── frontend/
    ├── package.json / next.config.js / tsconfig.json
    ├── .env.example
    └── src/app/
        ├── layout.tsx
        ├── globals.css
        └── page.tsx              # 대시보드 (변경점 / 현황 비교)
```

---

## 빠른 시작 (로컬)

```bash
# 1) 백엔드
cd backend
pip install -r ../requirements.txt
python -m playwright install chromium
cp .env.example .env          # DATABASE_URL, CRON_TOKEN 채우기 (DB 없으면 자동 sqlite)
uvicorn main:app --reload --port 8000

# 2) 프론트 (새 터미널)
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev                   # http://localhost:3000
```
> GEMINI_API_KEY 없어도 동작합니다(규칙기반 분석). DATABASE_URL 없으면 로컬 sqlite로 자동 동작.

---

## Render 배포 (무료 · DB 1 + 웹 2)

Dashboard 에서 직접 생성:

**① PostgreSQL** — New + → PostgreSQL → Free → Internal Database URL 복사.

**② Backend (Web Service)**
| 항목 | 값 |
|------|-----|
| Root Directory | `.` |
| Build | `pip install -r requirements.txt && python -m playwright install chromium` |
| Start | `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT` |
| 환경변수 | 아래 표 |

**③ Frontend (Web Service)**
| 항목 | 값 |
|------|-----|
| Root Directory | `frontend` |
| Build | `npm install && npm run build` |
| Start | `npm run start` |
| 환경변수 | `NEXT_PUBLIC_API_URL` = ② 백엔드 URL |

### 백엔드 환경변수
| Key | 설명 | 필수 |
|-----|------|:--:|
| `DATABASE_URL` | ① 에서 복사 (postgresql://… — 형식 자동 정규화됨) | ✅ |
| `CRON_TOKEN` | 임의의 긴 문자열, GitHub Secret 과 동일 | ✅ |
| `GEMINI_API_KEY` | 없으면 규칙기반 분석 | ▲ |
| `USE_PLAYWRIGHT` | `true` (메모리 부족 시 `false`) | |
| `ENABLE_SCREENSHOT` | `true` (이미지 비교샷) | |
| `KEEP_SNAPSHOTS` | `5` (무료 DB 용량 보호) | |
| `SENDER_EMAIL` `SENDER_PASSWORD` `RECIPIENT_EMAIL` | 메일 사용 시 | |

---

## 자동 스케줄 (Render Free sleep 회피)

무료 웹서비스는 15분 비활성 시 잠들어 내장 스케줄러가 안 돕니다.
→ **GitHub Actions** 가 정시에 깨워 크롤합니다.

1. 리포 Settings → Secrets and variables → Actions:
   - `BACKEND_URL` = 백엔드 URL
   - `CRON_TOKEN`  = 백엔드 환경변수와 동일
2. `.github/workflows/scheduled-crawl.yml` 이 매일 00:00·05:00 UTC(=09:00·14:00 KST)에
   `/api/cron/tick` 호출 → 크롤 + 스냅샷 정리 + 이메일 발송.

---

## 주요 API
| Endpoint | 설명 |
|----------|------|
| `GET /api/latest-report` | 최근 크롤 변경점(카테고리별) + 현황 분석 |
| `GET /api/compare` | 삼성↔애플 실측 비교 |
| `GET /api/timeline?level=High&category=가격·프로모션` | 변화 필터 |
| `GET /api/snapshot/screenshots?url=` | 비교샷(썸네일+변경영역) |
| `GET/POST/DELETE /api/urls` | 모니터링 URL 관리 |
| `GET /api/export/xlsx` · `/pptx` | DB 다운로드 |
| `POST /trigger-crawl/all` · `GET /api/crawl-progress` | 수동 크롤·진행률 |
| `GET/POST /api/cron/tick?token=` | 정시 트리거 |
| `POST /api/email/test` | 메일 설정 테스트 |

---

## 중요도 (High / Medium / Low)
| 등급 | 의미 | 예 |
|------|------|----|
| **High** | 즉시 대응 — 가격·구매·구조(AI 노출) | 가격/CTA/스키마 변경 |
| **Medium** | 검토 — 카피·섹션·일부 구조 | H1·본문 변경 |
| **Low** | 참고 — 단어·미세·비주얼 | 단어 수정·이미지 변화 |

> 내부 엔진은 더 정밀한 6단계(L0~L5)로 감지하지만, 화면에는 High/Medium/Low로 단순화해 표시합니다.

## 신뢰성 원칙 (환각 차단)
실제 수집된 값만 근거로 사용 · 비교는 양사 데이터가 모두 있을 때만 · 데이터에 없는 수치는 만들지 않음.
