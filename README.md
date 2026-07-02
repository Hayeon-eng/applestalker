# 🍎 Apple Stalker

경쟁사(**애플**)와 당사(**삼성**) 웹사이트를 매일 자동으로 들여다보고, **무엇이 바뀌었는지**를
중요도와 카테고리로 정리해서 보여주는 도구입니다. AI 검색(AEO) 시대에 경쟁사 움직임을
놓치지 않기 위한 "웹사이트 변화 감시견" 이라고 생각하시면 됩니다.

- **변경점이 메인 화면** — 데이터·스키마 / 카피 / 가격·프로모션 / 비주얼 **4칸**으로 묶어서, **High·Medium·Low** 중요도로 표시
- **현황 비교** — 삼성 ↔ 애플 실제 수집값 비교 (지어낸 숫자 없음)
- 매일 **오전 9시·오후 2시** 자동 실행 + **이메일 리포트**
- 변화 이미지 비교샷, Excel/PPTX 다운로드, 감시 URL 추가 가능

---

## 🧩 이 프로젝트는 두 덩어리로 되어 있어요

| 폴더 | 역할 | 비유 |
|------|------|------|
| `backend/` | 크롤링·분석·데이터 저장 (FastAPI) | **두뇌** |
| `frontend/` | 화면(대시보드) (Next.js) | **얼굴** |

둘은 따로 돌아갑니다. 배포할 때 서버를 2개 만든다고 생각하시면 됩니다.

```
.
├── README.md                     ← 지금 이 문서
├── requirements.txt              ← 백엔드가 필요로 하는 부품 목록
├── render.yaml                   ← 배포 설정(참고용)
├── .github/workflows/scheduled-crawl.yml   ← 매일 자동 실행 알람
├── backend/    (두뇌)
│   ├── main.py                   ← 모든 기능 입구/API
│   ├── config.py                 ← 감시할 사이트/URL 목록
│   ├── crawler.py                ← 웹페이지 수집기
│   ├── diff_engine.py            ← 변경점 비교기 핵심
│   ├── diff_engine_helpers.py    ← 비교기 보조 로직(긴 파일 분리)
│   ├── intel_engine.py           ← AI/규칙 기반 의미 분석
│   ├── gemini_health.py          ← Gemini 실제 호출 상태 점검
│   ├── crawl_service.py          ← 전체 크롤 흐름 연결
│   ├── export_service.py         ← Excel/PPTX 만들기
│   ├── email_service.py          ← 리포트 메일 보내기
│   ├── models.py / database.py   ← 데이터 저장
│   └── .env.example              ← 설정값 예시
└── frontend/   (얼굴)
    └── src/app/
        ├── page.tsx              ← 대시보드 메인
        ├── sections.tsx          ← DATA/COPY/PRICE/VISUAL 섹션
        ├── evidencePanels.tsx    ← 변경점/현황 요약 상세 근거 패널
        └── shared.ts             ← 공통 기준 설명/유틸
```

---

## 👀 일단 화면부터 보고 싶다면 (가장 쉬움)

컴퓨터에 **Node.js**만 설치되어 있으면, 백엔드 없이도 **예시 데이터로 화면**이 뜹니다.

```bash
cd frontend
npm install
npm run dev
```
브라우저에서 **http://localhost:3000** 열기 → 끝. (노란 "예시 데이터" 배너가 보입니다)

---

## 🚀 실제로 인터넷에 올리기 (Render, 무료)

Render(render.com)는 무료로 서버를 띄울 수 있는 서비스예요. **3개를 만듭니다: 데이터베이스 1 + 서버 2.**
GitHub에 이 코드를 먼저 올린 뒤, Render에서 그 GitHub 저장소를 연결합니다.

### ① 데이터베이스 만들기
Render → **New +** → **PostgreSQL** → 이름 아무거나 → Plan **Free** → 만들기.
만든 뒤 **"Internal Database URL"** 을 복사해두세요. (나중에 ②에 붙여넣음)

### ② 두뇌(Backend) 만들기
Render → **New +** → **Web Service** → GitHub 저장소 선택. 아래처럼 입력:

| 칸 | 입력값 |
|----|--------|
| Root Directory | `.` (점 하나) |
| Build Command | `pip install -r requirements.txt && python -m playwright install chromium` |
| Start Command | `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |

그리고 **Environment(환경변수)** 에 아래 값들을 추가합니다 (표는 아래 "환경변수 쉬운 설명").

### ③ 얼굴(Frontend) 만들기
Render → **New +** → **Web Service** → 같은 GitHub 저장소.

| 칸 | 입력값 |
|----|--------|
| Root Directory | `frontend` |
| Build Command | `npm install && npm run build` |
| Start Command | `npm run start` |
| Instance Type | Free |

환경변수에 **`NEXT_PUBLIC_API_URL`** = (②에서 만든 백엔드 주소, 예: `https://apple-stalker-backend.onrender.com`)

---

## 🔑 환경변수 쉬운 설명

"환경변수"는 그냥 **설정값**이에요. Render 서비스의 Environment 탭에서 `이름 = 값` 형태로 넣습니다.

### 백엔드(②)에 넣을 값
| 이름 | 무슨 값을 넣나 | 꼭 필요? |
|------|---------------|:--:|
| `DATABASE_URL` | ①에서 복사한 데이터베이스 주소 | ✅ |
| `CRON_TOKEN` | **자동 실행용 비밀번호.** 아무 긴 글자나 정하면 됨 (예: `applestalker-9f3k2m8x7qw1zv`) | ✅ |
| `GEMINI_API_KEY` | (선택) AI 분석을 더 똑똑하게. 없어도 작동함 | ▲ |
| `USE_PLAYWRIGHT` | `true` (서버가 버거우면 `false`) | |
| `ENABLE_SCREENSHOT` | `true` (이미지 비교샷 켜기) | |
| `KEEP_SNAPSHOTS` | `5` (저장공간 아끼려고 최근 5개만 보관) | |
| `SENDER_EMAIL` / `SENDER_PASSWORD` / `RECIPIENT_EMAIL` | (선택) 리포트 메일 보낼 계정 / 받을 주소 | |

> **`DATABASE_URL` 참고:** Render가 주는 주소를 그대로 붙여넣으면 됩니다. 형식이 조금 달라도 코드가 알아서 맞춰줍니다.

### 프론트(③)에 넣을 값
| 이름 | 값 |
|------|-----|
| `NEXT_PUBLIC_API_URL` | ②에서 만든 백엔드 주소 |

---

## ⏰ 매일 자동 실행 설정 (중요)

무료 서버는 **아무도 안 쓰면 잠들어버려서**, 그냥 두면 9시·2시에 자동 크롤이 안 돕니다.
그래서 **GitHub이 정해진 시간에 서버를 깨워주는** 방식을 씁니다. (이 코드에 이미 포함되어 있어요)

설정은 딱 2단계:
1. GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret** 에서 2개 추가:
   - `BACKEND_URL` = ②에서 만든 백엔드 주소
   - `CRON_TOKEN` = **②에 넣은 것과 똑같은 비밀번호** (이게 "GitHub Secret과 동일"의 뜻)
2. 끝. 매일 한국시간 **09:00·14:00**에 자동으로 크롤하고 메일을 보냅니다.

> 💡 **`CRON_TOKEN`을 두 군데(Render·GitHub)에 똑같이 넣는 이유:** 그 "깨우는 주소"는 인터넷에 열려 있어서 아무나 누를 수 있어요. 비밀번호가 맞아야만 실행되게 막아두는 겁니다. 두 곳의 값이 같아야 "맞는 요청"으로 인정됩니다.

---

## 📊 중요도 (High / Medium / Low)
중요도는 이제 단순히 `schema_type`, `body_content` 같은 **필드명만 보고 고정하지 않습니다.**
아래 요소를 함께 봅니다.

- **변화 폭**: L0~L5 원천 변화 강도
- **AI 검색 영향**: Product/FAQ/Offer/Review schema, meta, canonical, H1 등 검색·AI 요약에 쓰이는 정보인지
- **구매전환 영향**: 가격, 프로모션, CTA, 사전예약/구매 버튼 등 매출 행동과 연결되는지
- **페이지 Tier**: 핵심 랜딩/제품 페이지인지, 하위 보조 페이지인지
- **노이즈 신호**: 렌더링 방식 차이, 반복 UI 라벨, 작은 이미지/태그 변화인지

| 등급 | 기준 | 예시 |
|------|------|------|
| 🔴 **High** | AI 검색·구매전환·핵심 페이지 영향이 큰 변화 | Product schema 변경, 핵심 CTA/가격/프로모션 변경 |
| 🟠 **Medium** | meta·H1·FAQ·CTA·주요 카피처럼 의미/클릭률에 영향 가능 | 대표 문구 변경, FAQ 추가, 주요 섹션 제목 변경 |
| 🟢 **Low** | 단어·UI 라벨·작은 이미지·렌더링 노이즈 중심 | 오타 수정, 메뉴 라벨 변화, 반복 이미지 차이 |

---

## 🛡️ 믿을 수 있는 분석 (지어내지 않음)
- 분석은 **실제로 수집한 데이터만** 근거로 사용합니다.
- 삼성 ↔ 애플 비교는 **두 사이트 데이터가 모두 있을 때만** 합니다.
- 데이터에 없는 숫자는 **만들어내지 않습니다.** (화면의 "예시 데이터" 배너는 실제 크롤 전 임시 표시이며, 크롤하면 진짜 데이터로 바뀝니다.)


### 변경점 COUNT는 이렇게 셉니다
- 같은 URL의 **직전 스냅샷과 현재 스냅샷**을 비교해서 변경 이벤트 수를 계산합니다.
- 즉, 최초 크롤은 기준선이 없어서 변경점이 많게 보일 수 있지만, 바로 다음 크롤에서 실제 내용이 같으면 원칙적으로 **0건**이어야 합니다.
- 이를 위해 저장되는 스냅샷에 안정 fingerprint를 만들고, 같은 fingerprint면 변경 이벤트를 만들지 않습니다.
- DB 저장 실패가 있으면 다음 크롤도 이전 기준선과 비교하게 되어 COUNT가 흔들릴 수 있으므로, 스냅샷/이벤트 저장 실패는 조용히 넘기지 않고 실패로 표시합니다.
- `httpx`와 `playwright`처럼 렌더링 방식이 바뀐 경우에는 body/DOM/이미지 같은 노이즈가 큰 항목은 제한하고, title/meta/H1/schema처럼 안정적인 필드 중심으로 비교합니다.

### 현황 요약도 근거를 볼 수 있습니다
- DATA/COPY/PRICE/VISUAL의 현황 요약 항목을 클릭하면, 아래의 상세 근거 패널로 이동합니다.
- 상세 근거는 기본적으로 접혀 있고, 클릭한 항목만 자동으로 펼쳐집니다.
- 예: VISUAL의 이미지 분류, alt 텍스트 품질, 이미지 고유성, 스토리텔링 항목별로 실제 집계값과 판단 기준을 확인할 수 있습니다.

---

## 🧰 자주 쓰는 주소 (개발자용 참고)
| 주소 | 설명 |
|------|------|
| `GET /api/health` | 백엔드 기본 상태 확인. `gemini: true`는 키가 설정되어 초기화됐다는 뜻입니다. |
| `GET /api/health/gemini` | Gemini에 실제 초소형 요청을 보내 인증/쿼터 상태를 확인합니다. 401이면 키/인증 문제, 429면 쿼터·rate limit 가능성이 큽니다. |
| `GET /api/latest-report` | 최근 변경점 + 현황 분석 |
| `GET /api/compare` | 삼성↔애플 비교 |
| `GET /api/export/xlsx` · `/pptx` | 다운로드 |
| `POST /trigger-crawl/all` | 지금 바로 크롤 |
| `GET /api/cron/tick?token=...` | 자동 실행용(비밀번호 필요) |
| `POST /api/email/test` | 메일 설정 테스트 |

### Gemini가 안 돌 때 빠른 확인
1. 먼저 `GET /api/health`에서 `gemini: true`인지 확인합니다.
2. 그다음 `GET /api/health/gemini`를 열어 실제 호출 결과를 확인합니다.
3. `401 invalid_authentication`이면 토큰 소진이 아니라 `GEMINI_API_KEY` 값이 잘못됐을 가능성이 큽니다. Render Environment에서 API key가 `AIza...` 형태인지 확인하세요.
4. `429 quota_or_rate_limit`이면 쿼터 소진 또는 rate limit 가능성이 큽니다.
5. Gemini가 실패해도 리포트는 멈추지 않고 **규칙기반 분석**으로 fallback됩니다.

---

## 📝 GitHub 웹 에디터로 수정할 때 참고
GitHub 웹 에디터는 큰 파일 편집이 불편할 수 있어서, 긴 로직은 일부 분리되어 있습니다.

| 큰 기능 | 주로 수정할 파일 |
|--------|----------------|
| 변경점 비교 기준 | `backend/diff_engine.py`, `backend/diff_engine_helpers.py` |
| Gemini 실제 호출 상태 확인 | `backend/gemini_health.py`, `backend/main.py` |
| 화면 섹션 UI | `frontend/src/app/sections.tsx` |
| 변경점/현황 상세 근거 패널 | `frontend/src/app/evidencePanels.tsx` |
| 중요도/기준 설명 문구 | `frontend/src/app/shared.ts`, `frontend/src/app/page.tsx` |

수정 파일만 교체해도 되도록 기존 import 경로는 최대한 유지되어 있습니다.

## 💻 내 컴퓨터에서 전체 돌려보기 (개발자용)
```bash
# 두뇌
cd backend
pip install -r ../requirements.txt
python -m playwright install chromium
uvicorn main:app --reload --port 8000      # 데이터베이스 없으면 자동으로 임시 sqlite 사용

# 얼굴 (새 터미널)
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev                                 # http://localhost:3000
```
