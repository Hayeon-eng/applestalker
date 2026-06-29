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
│   ├── main.py                   ← 모든 기능 입구
│   ├── config.py                 ← 감시할 사이트/URL 목록
│   ├── crawler.py                ← 웹페이지 수집기
│   ├── diff_engine.py            ← "무엇이 바뀌었나" 비교기
│   ├── intel_engine.py           ← 의미 분석 (지어내지 않음)
│   ├── crawl_service.py          ← 전체 흐름 연결
│   ├── export_service.py         ← Excel/PPTX 만들기
│   ├── email_service.py          ← 리포트 메일 보내기
│   ├── models.py / database.py   ← 데이터 저장
│   └── .env.example              ← 설정값 예시
└── frontend/   (얼굴)
    └── src/app/page.tsx          ← 대시보드 화면
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
| 등급 | 의미 | 예시 |
|------|------|------|
| 🔴 **High** | 즉시 봐야 함 — 가격·구매 버튼·구조(AI 노출) 변화 | 사전예약 버튼 신설, 가격 변경 |
| 🟠 **Medium** | 검토 — 카피·섹션·일부 구조 변화 | 대표 제목/본문 변경 |
| 🟢 **Low** | 참고 — 단어·미세·이미지 변화 | 단어 수정, 이미지 교체 |

---

## 🛡️ 믿을 수 있는 분석 (지어내지 않음)
- 분석은 **실제로 수집한 데이터만** 근거로 사용합니다.
- 삼성 ↔ 애플 비교는 **두 사이트 데이터가 모두 있을 때만** 합니다.
- 데이터에 없는 숫자는 **만들어내지 않습니다.** (화면의 "예시 데이터" 배너는 실제 크롤 전 임시 표시이며, 크롤하면 진짜 데이터로 바뀝니다.)

---

## 🧰 자주 쓰는 주소 (개발자용 참고)
| 주소 | 설명 |
|------|------|
| `GET /api/latest-report` | 최근 변경점 + 현황 분석 |
| `GET /api/compare` | 삼성↔애플 비교 |
| `GET /api/export/xlsx` · `/pptx` | 다운로드 |
| `POST /trigger-crawl/all` | 지금 바로 크롤 |
| `GET /api/cron/tick?token=...` | 자동 실행용(비밀번호 필요) |
| `POST /api/email/test` | 메일 설정 테스트 |

---

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
