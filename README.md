# 🍎 Apple Stalker - Competitive Intelligence Platform

**Apple Stalker**는 Apple.com 과 Samsung.com 의 콘텐츠, IA, UX, Commerce, SEO, GEO, AEO, Structured Data 전략 변화를 지속적으로 수집·저장·분석하는 Competitive Intelligence Platform 입니다.

---

## 📋 목차

1. [기능](#-기능)
2. [기술 스택](#-기술-스택)
3. [프로젝트 구조](#-프로젝트-구조)
4. [Render 배포 가이드](#-render-배포-가이드)
5. [로컬 개발 환경](#-로컬-개발-환경)
6. [이메일 설정](#-이메일-설정)
7. [API 엔드포인트](#-api-엔드포인트)
8. [트러블슈팅](#-트러블슈팅)

---

## ✨ 기능

### 핵심 기능

#### 🔒 Hallucination Prevention
- **45 개 고정 URL**: 하드코딩된 URL 만 크롤링 (자동 URL 발견 없음)
- **실제 HTML 기반**: 모든 데이터는 실제 HTML 에서 추출
- **AI 분리**: 데이터 추출과 AI 분석 완전 분리 (Gemini 는 분석만)

#### 📊 크롤링 엔진
- **고정 45 개 URL**: Apple 21 개 + Samsung 24 개 (Tier 0-4)
- **Change Detection Engine**: 콘텐츠, 내비게이션, 메타데이터 변화 감지
- **Historical Database**: PostgreSQL 기반 Append Only 영구 저장 (Render Free 10GB)

#### 🧠 AI 분석 엔진
- **Competitive Analyzer**: Apple ↔ Samsung 전략적 비교 분석
- **GEO/AEO Signal Engine**: FAQ, Schema, LLM 최적화 신호 감지
- **Samsung POV Engine**: 관찰 → 근거 → 가설 → 기회 → 액션 제안

#### ⏰ 자동화
- **Automated Scheduler**: 매일 2 회 자동 실행 (09:00, 14:00 KST)
- **Email Reports**: 자동화된 일일 리포트 이메일 발송 (09:30, 14:30 KST)

### 📊 모니터링 대상 (45 개 고정 URL)

#### Tier 0: 브랜드 홈 (2 개)
- `https://www.apple.com/`
- `https://www.samsung.com/sg/`

#### Tier 1: 카테고리 (6 개)
- `https://www.apple.com/iphone/`
- `https://www.apple.com/watch/`
- `https://www.apple.com/airpods/`
- `https://www.samsung.com/sg/smartphones/all-smartphones/`
- `https://www.samsung.com/sg/watches/all-watches/`
- `https://www.samsung.com/sg/audio-sound/all-audio-sound/`

#### Tier 2: 캠페인 (8 개)
- `https://www.apple.com/apple-intelligence/`
- `https://www.apple.com/iphone/compare/`
- `https://www.apple.com/watch/compare/`
- `https://www.samsung.com/sg/mobile/`
- `https://www.samsung.com/sg/galaxy-ai/`
- `https://www.samsung.com/sg/mobile/find-your-galaxy/`
- `https://www.samsung.com/sg/mobile/switch-to-galaxy/`
- `https://www.samsung.com/sg/one-ui/`

#### Tier 3: 제품 상세 (14 개)
- `https://www.apple.com/iphone-17-pro/`
- `https://www.apple.com/iphone-air/`
- `https://www.apple.com/iphone-17/`
- `https://www.apple.com/iphone-17e/`
- `https://www.apple.com/apple-watch-series-11/`
- `https://www.apple.com/apple-watch-ultra-3/`
- `https://www.apple.com/apple-watch-se-3/`
- `https://www.apple.com/airpods-pro/`
- `https://www.samsung.com/sg/smartphones/galaxy-s26-ultra/`
- `https://www.samsung.com/sg/smartphones/galaxy-s26/`
- `https://www.samsung.com/sg/smartphones/galaxy-z-fold7/`
- `https://www.samsung.com/sg/smartphones/galaxy-z-flip7/`
- `https://www.samsung.com/sg/watches/galaxy-watch-ultra-2025/`
- `https://www.samsung.com/sg/audio-sound/galaxy-buds4-pro/`

#### Tier 4: 구매/스펙 (15 개)
- `https://www.apple.com/iphone-17-pro/specs/`
- `https://www.apple.com/iphone-air/specs/`
- `https://www.apple.com/iphone-17/specs/`
- `https://www.apple.com/iphone-17e/specs/`
- `https://www.apple.com/apple-watch-series-11/specs/`
- `https://www.apple.com/apple-watch-ultra-3/specs/`
- `https://www.apple.com/apple-watch-se-3/specs/`
- `https://www.apple.com/airpods-pro/specs/`
- `https://www.apple.com/shop/buy-iphone`
- `https://www.samsung.com/sg/smartphones/galaxy-s26-ultra/buy/`
- `https://www.samsung.com/sg/smartphones/galaxy-s26/buy/`
- `https://www.samsung.com/sg/smartphones/galaxy-z-fold7/buy/`
- `https://www.samsung.com/sg/smartphones/galaxy-z-flip7/buy/`
- `https://www.samsung.com/sg/watches/galaxy-watch-ultra-2025/buy/`
- `https://www.samsung.com/sg/audio-sound/galaxy-buds4-pro/buy/`

### 📝 HTML 카피 변경 감지
- **헤드라인 변경**: H1, H2, H3 텍스트 변경 감지
- **메타데이터 변경**: Title, Meta Description, Open Graph 데이터
- **본문 콘텐츠**: 주요 문단 카피 변경 감지
- **Structured Data**: JSON-LD 스키마 추가/수정/제거

### 📸 Playwright 비주얼 분석
- **Desktop Screenshot**: 1920x1080 해상도 스크린샷
- **Mobile Screenshot**: 375x667 해상도 모바일 뷰
- **Full Page Screenshot**: 전체 페이지 스크린샷
- **Rendered HTML Capture**: JavaScript 실행 후 HTML 스냅샷

---

## 🔧 기술 스택

| 영역 | 기술 |
|------|------|
| **Frontend** | Next.js 14, React, TypeScript, Tailwind CSS |
| **Backend** | Python 3.11, FastAPI |
| **Crawling** | Playwright (Browser Automation) + httpx (Fallback) |
| **Database** | PostgreSQL (Render Free 10GB) |
| **AI** | Google Gemini 2.5 Flash (`gemini-2.5-flash`) |
| **Deployment** | GitHub → Render (Free Plan) |
| **Email** | Naver SMTP (smtp.naver.com:587) |

---

## 📁 프로젝트 구조

```
apple-tracker/
├── backend/
│   ├── main.py              # FastAPI 진입점
│   ├── crawler/
│   │   └── playwright_crawler.py   # Playwright 크롤러
│   ├── database/
│   │   └── database.py      # PostgreSQL 데이터베이스
│   ├── engines/
│   │   └── gemini_engine.py # Gemini AI 엔진
│   └── services/
│       ├── scheduler.py     # 크롤링 스케줄러
│       ├── email_report_service.py  # 이메일 리포트
│       └── export_service.py        # PPTX/PNG 내보내기
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router
│   │   └── components/      # React 컴포넌트
│   ├── package.json         # Node.js 의존성
│   ├── next.config.js       # Next.js 설정
│   └── tailwind.config.js   # Tailwind CSS 설정
├── render.yaml              # Render 배포 설정
├── requirements.txt         # Python 의존성
├── .env.example             # 환경 변수 템플릿
└── README.md
```

---

## 🚀 Render 배포 가이드 (수동 생성)

> **📌 중요**: Blueprint 는 사용하지 않습니다. Render Dashboard 에서 **New Service**로 직접 생성합니다.

### 전체 Render 설정 요약

| 서비스 | 타입 | 환경 | 플랜 | Region |
|--------|------|------|------|--------|
| **Backend** | Web Service | Python 3.11 | Free | Oregon West |
| **Frontend** | Web Service | Node.js 20.x | Free | Oregon West |
| **Database** | PostgreSQL | - | Free (10GB) | Oregon West |

---

### 단계별 배포 가이드

#### 1 단계: GitHub 에 코드 업로드

```bash
# 1. Git 저장소 초기화
cd c:\Users\hayeon2.kwon\Desktop\apple-tracker
git init

# 2. 모든 파일 추가
git add .

# 3. 커밋
git commit -m "Initial commit - Apple Tracker"

# 4. GitHub 원격 저장소 연결 (새 저장소 생성 후)
git remote add origin https://github.com/your-username/apple-tracker.git

# 5. main 브랜치로 푸시
git branch -M main
git push -u origin main
```

#### 2 단계: PostgreSQL 데이터베이스 생성

1. [Render Dashboard](https://dashboard.render.com/) 에서 **New +** → **PostgreSQL** 클릭
2. 설정 입력:
   - **Name**: `apple-tracker-db`
   - **Region**: `Oregon West`
   - **Plan**: `Free`
3. **Create Database** 클릭
4. 생성 후 **Internal Database URL** 복사 (형식: `postgresql://user:pass@host/dbname`)

#### 3 단계: Backend 서비스 생성

1. Render Dashboard 에서 **New +** → **Web Service** 클릭
2. GitHub 저장소 연결 → `apple-tracker` 선택
3. 설정 입력:

| 필드 | 값 |
|------|-----|
| **Name** | `apple-tracker-backend` |
| **Region** | `Oregon West` |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Environment** | `Python` |
| **Build Command** | `pip install -r ../requirements.txt && playwright install chromium --no-shell` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Plan** | `Free` |

4. **Advanced** 섹션에서 환경 변수 추가:

| Key | Value |
|-----|-------|
| `PYTHON_VERSION` | `3.11.0` |
| `DATABASE_URL` | `postgresql+asyncpg://apple_tracker_db_user:BnK68hdUtgln6OctkJMaQzX66dT8ifm1@dpg-d8pr2v8g4nts7388im7g-a/apple_tracker_db` |
| `GEMINI_API_KEY` | `AIzaSy...` (직접 입력) |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `CRAWL_SCHEDULE` | `0 0,5 * * *` |
| `SMTP_SERVER` | `smtp.naver.com` |
| `SMTP_PORT` | `587` |
| `SENDER_EMAIL` | `your-id@naver.com` (직접 입력) |
| `SENDER_PASSWORD` | `your-password` (직접 입력) |
| `RECIPIENT_EMAIL` | `your-email@company.com` (직접 입력) |
| `EMAIL_REPORT_ENABLED` | `true` |
| `USE_PLAYWRIGHT` | `true` |
| `MAX_CONCURRENT_CRAWLS` | `3` |
| `CRAWL_TIMEOUT` | `60000` |
| `ENABLE_FULL_SITE_CRAWL` | `true` |
| `NEXT_PUBLIC_API_URL` | `https://apple-tracker-backend.onrender.com` |

5. **Create Web Service** 클릭

#### 4 단계: Frontend 서비스 생성

1. Render Dashboard 에서 **New +** → **Web Service** 클릭
2. GitHub 저장소 연결 → `apple-tracker` 선택
3. 설정 입력:

| 필드 | 값 |
|------|-----|
| **Name** | `apple-tracker-frontend` |
| **Region** | `Oregon West` |
| **Branch** | `main` |
| **Root Directory** | `frontend` |
| **Environment** | `Node` |
| **Build Command** | `npm install && npm run build` |
| **Start Command** | `npm run start` |
| **Node Version** | `20.x` |
| **Plan** | `Free` |

4. **Advanced** 섹션에서 환경 변수 추가:

| Key | Value |
|-----|-------|
| `NODE_VERSION` | `20.x` |
| `NEXT_PUBLIC_API_URL` | `https://apple-tracker-backend.onrender.com` (Backend URL 입력) |

5. **Create Web Service** 클릭

---

### 배포 확인

1. **Backend Logs**: Render 대시보드 → **apple-tracker-backend** → **Logs**
2. **Frontend Logs**: Render 대시보드 → **apple-tracker-frontend** → **Logs**
3. **Database**: Render 대시보드 → **apple-tracker-db** → **Overview**

**성공 메시지:**
```
Application startup complete.
Uvicorn running on http://0.0.0.0:$PORT
```

**생성된 URL:**
- Backend: `https://apple-tracker-backend.onrender.com`
- Frontend: `https://apple-tracker-frontend.onrender.com`

---

## 🔧 로컬 개발 환경

### 1 단계: 저장소 클론

```bash
git clone https://github.com/your-username/apple-tracker.git
cd apple-tracker
```

### 2 단계: Backend 설정

```bash
# 1. backend 폴더로 이동
cd backend

# 2. 가상환경 생성
python -m venv venv

# 3. 가상환경 활성화
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. 의존성 설치
pip install -r ../requirements.txt

# 5. Playwright 브라우저 설치 (선택)
playwright install chromium
```

### 3 단계: 환경 변수 설정

**로컬 개발용** (PostgreSQL 필요):

```bash
# .env.example 복사
# Windows:
copy ..\.env.example .env
# Linux/Mac:
cp ../.env.example .env
```

`.env` 파일을 편집합니다:

```env
# Gemini API Key (필수!)
GEMINI_API_KEY=your_gemini_api_key_here

# 데이터베이스 (로컬 PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/apple_tracker

# 이메일 설정 (네이버 메일)
SMTP_SERVER=smtp.naver.com
SMTP_PORT=587
SENDER_EMAIL=your-id@naver.com
SENDER_PASSWORD=your-password
RECIPIENT_EMAIL=hayeon2.kwon@samsung.com
EMAIL_REPORT_ENABLED=true

# Playwright 사용 여부
USE_PLAYWRIGHT=true
```

> **참고**: 로컬에서 PostgreSQL 을 실행하려면 Docker 또는 로컬 PostgreSQL 설치가 필요합니다.

### 4 단계: Backend 서버 실행

```bash
cd backend
python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8002)"
```

서버가 시작되면 다음 메시지가 표시됩니다:
```
INFO:     Uvicorn running on http://0.0.0.0:8002
```

### 5 단계: Frontend 서버 실행 (Next.js)

```bash
# 1. frontend 폴더로 이동
cd frontend

# 2. 의존성 설치
npm install

# 3. 개발 서버 시작
npm run dev
```

브라우저에서 `http://localhost:3000` 을 엽니다.

---

### 6 단계: API 연동 설정

`frontend/.env.local` 파일을 생성하고 다음을 추가합니다:

```env
NEXT_PUBLIC_API_URL=http://localhost:8002
```

---

## 📧 이메일 설정

### 네이버 메일 SMTP 설정

Render 환경 변수에 다음을 추가합니다:

| 키 | 값 |
|-----|-----|
| `SMTP_SERVER` | `smtp.naver.com` |
| `SMTP_PORT` | `587` |
| `SENDER_EMAIL` | `your-id@naver.com` |
| `SENDER_PASSWORD` | `your-password` |
| `RECIPIENT_EMAIL` | `hayeon2.kwon@samsung.com` |

### Gmail 앱 비밀번호 설정 (대안)

1. [Google 계정](https://myaccount.google.com/) 에 로그인합니다.
2. **보안** → **2 단계 인증**을 활성화합니다.
3. **앱 비밀번호** 메뉴로 이동: https://myaccount.google.com/apppasswords
4. **앱**: 메일, **기기**: Windows 컴퓨터를 선택합니다.
5. 생성된 16 자리 비밀번호를 `SENDER_PASSWORD` 에 입력합니다.
   - 형식: `abcd efgh ijkl mnop` (공백 포함)
   - 실제 입력: 공백 제거 또는 포함 모두 가능

### 이메일 설정 확인

```bash
# PowerShell:
Invoke-WebRequest -Uri https://your-render-url.onrender.com/api/email/test -Method POST
```

---

## 🔌 API 엔드포인트

### 크롤링 관련
| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| GET | `/api/health` | 서버 상태 확인 |
| GET | `/api/sites` | 모니터링 사이트 목록 |
| POST | `/trigger-crawl/all` | 수동 크롤링 시작 (Tier 선택) |
| GET | `/api/crawl-status` | 크롤링 상태 확인 |
| POST | `/api/crawl-stop` | 크롤링 중지 |
| GET | `/api/crawl-progress` | 실시간 크롤링 진행 (SSE) |

### 리포트 관련
| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| GET | `/api/runs` | 크롤링 히스토리 목록 |
| GET | `/api/latest-report` | 최신 크롤링 리포트 |
| GET | `/api/run-detail/{run_id}` | 크롤링 상세 정보 (Sidebar Drawer) |
| DELETE | `/api/run/{run_id}` | 크롤링 기록 삭제 |
| POST | `/api/export/dashboard` | 대시보드 내보내기 (PPTX/PNG) |

### 변경사항 관련
| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| GET | `/api/changes` | 감지된 변경사항 목록 |
| GET | `/api/changes/summary` | 변경사항 요약 (타입/심각도별) |
| GET | `/api/crawls` | 크롤링 실행 이력 |
| GET | `/api/crawls/{crawl_run_id}` | 특정 크롤링 상세 |

### 인사이트 관련
| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| GET | `/api/povs` | Samsung POV 추천 목록 |
| GET | `/api/geo-signals` | GEO/AEO 신호 목록 |
| GET | `/api/trends` | 트렌드 데이터 |

### 설정 관련
| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| GET | `/api/settings` | 애플리케이션 설정 |
| POST | `/api/auto-crawl` | 자동 크롤링 토글 |
| GET | `/api/scheduler/jobs` | 
스케줄러 작업 목록 |
| POST | `/api/scheduler/run-now/{job_id}` | 스케줄러 즉시 실행 |

### 이메일 관련
| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| POST | `/api/email/test` | 테스트 이메일 발송 |
| GET | `/api/email/report/send?report_type=morning` | 수동 리포트 발송 |

---

## 🐛 트러블슈팅

### "Email not configured"

- `.env` 파일에 `SENDER_EMAIL`, `SENDER_PASSWORD` 가 설정되었는지 확인합니다.
- Render 환경 변수도 확인합니다.
- 백엔드를 재시작해야 환경 변수가 로드됩니다.

### "ModuleNotFoundError"

```bash
pip install -r requirements.txt
```

### "Port already in use"

```bash
# Windows: 포트 사용 중인 프로세스 확인
netstat -ano | findstr :8002

# 프로세스 종료
taskkill /F /PID <PID>
```

### "Playwright browser not found"

```bash
# Playwright 브라우저 설치
playwright install chromium
```

### Render 배포 후 API 가 응답하지 않음

1. Render Logs 를 확인합니다.
2. 환경 변수가 설정되었는지 확인합니다.
3. `GEMINI_API_KEY` 가 필수입니다.
4. 첫 요청은 Cold Start 로 30 초 정도 걸릴 수 있습니다.

---

## 📄 라이선스

MIT

---

## 👥 Author

- **Hayeon Kwon** - [hayeon2.kwon@samsung.com](mailto:hayeon2.kwon@samsung.com)

---

## ✅ Quick Deploy Checklist

### 1. GitHub 설정
- [ ] GitHub 저장소 생성
- [ ] 코드 푸시 (`git push`)

### 2. PostgreSQL 데이터베이스
- [ ] Render Dashboard → **New +** → **PostgreSQL**
- [ ] **Name**: `apple-tracker-db`
- [ ] **Region**: `Oregon West`
- [ ] **Plan**: `Free`
- [ ] **Internal Database URL** 복사

### 3. Backend 서비스
- [ ] Render Dashboard → **New +** → **Web Service**
- [ ] GitHub 저장소 연결
- [ ] **Root Directory**: `backend`
- [ ] **Region**: `Oregon West`
- [ ] **Build Command**: `pip install -r ../requirements.txt && playwright install chromium --no-shell`
- [ ] **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] 환경 변수 설정:
  - [ ] `DATABASE_URL`: `postgresql+asyncpg://...` (앞에 `+asyncpg` 추가!)
  - [ ] `GEMINI_API_KEY`: 직접 입력
  - [ ] `SENDER_EMAIL`: 직접 입력
  - [ ] `SENDER_PASSWORD`: 직접 입력
  - [ ] 나머지 변수들 입력

### 4. Frontend 서비스
- [ ] Render Dashboard → **New +** → **Web Service**
- [ ] GitHub 저장소 연결
- [ ] **Root Directory**: `frontend`
- [ ] **Region**: `Oregon West`
- [ ] **Build Command**: `npm install && npm run build`
- [ ] **Start Command**: `npm run start`
- [ ] 환경 변수 설정:
  - [ ] `NEXT_PUBLIC_API_URL`: Backend URL 입력

### 5. Verification
- [ ] 배포 완료 대기 (약 3-5 분)
- [ ] Backend Logs 확인
- [ ] Frontend Logs 확인
- [ ] Backend URL 접속 (`https://apple-tracker-backend.onrender.com/api/health`)
- [ ] Frontend URL 접속 (`https://apple-tracker-frontend.onrender.com`)
- [ ] 테스트 크롤링 실행
- [ ] 테스트 이메일 발송 확인
