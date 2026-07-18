# Apple Stalker 🍎 & 큐비 🐝

한 저장소에 두 모듈이 함께 있습니다.

- **애플스토커 🍎 (Apple Stalker)** — 경쟁사 닷컴을 모니터링해 DATA/COPY/VISUAL 3축으로 분석하고,
  변경점·리포트(PPTX/Excel/메일)를 생성하는 기존 웹앱.
- **큐비 🐝** — 풀네임 **QA Bee**, 줄여서 **큐비**. 닷컴 페이지를 붕붕 돌며 규칙대로 검수. 삼성닷컴 제품 페이지의
  스키마·카피를 스펙(엑셀)과 대조해 오류를 잡는 **Dotcom QA** 모듈.


=============# 신모델 최종 URL/스펙 반영 요청 — 새 Claude 세션용 지시문

이 문서를 코드 파일(`backend/dotcom_qa/` 전체, 최소한 아래 "건드릴 파일" 목록)과 함께
새 대화에 첨부해서 요청하세요. 이 문서만 보고도 실수 없이 반영할 수 있게 규칙을
전부 명시해뒀습니다.

---

## 무엇을 하는 요청인가

Applestalker/Qubi 저장소의 Spec QA + Schema QA가 참조하는 **제품별 정답값 파일**
(`schema_values.part*.json`)에, 지금까지 `{PD_URL}` 같은 자리표시자로 비워뒀던 부분을
실제 제품 URL/스펙으로 채워 넣는 작업입니다. 구조(무엇을 검사할지)는 이미 확정되어
있고, **값만 채우면 됩니다** — 구조를 새로 설계하거나 바꾸지 마세요.

---

## 건드릴 파일

- `backend/dotcom_qa/schema_values.part6.json` — Watch8/WatchUltra (이번 요청 대상)
- (다른 신모델이면) `schema_values.part5.json`처럼 새 `partN.json` 파일을 추가하거나
  기존 파일에 제품 키를 추가

**건드리면 안 되는 파일**: `schema_rules.*.json`(구조 정의, 이미 확정됨), `runner.py`,
`schema_checker.py` — 이번 작업은 값(데이터)만 채우는 거라 코드/구조 파일은 손댈 필요가
없습니다. 만약 이 파일들을 고쳐야 할 것 같은 상황이 생기면, 진행하지 말고 먼저
사용자에게 물어보세요.

---

## 핵심 규칙 (반드시 지킬 것)

### 1. `{PD_URL}` 치환
`schema_values.part6.json` 안의 모든 `{PD_URL}`을 실제 제품 페이지 URL로 바꿉니다.
사용자가 국가 하나 기준 대표 URL을 줄 겁니다 (예: `https://www.samsung.com/sg/watches/
galaxy-watch/galaxy-watch8-44mm-silver-bluetooth-sm-l330nzsaasa/`).

- URL 끝의 트레일링 슬래시(`/`)는 유지하세요. `{PD_URL}#webpage` 형태로 앵커가 바로
  붙는 게 기존 컨벤션입니다 (예: `.../galaxy-watch8-.../#webpage`).
- **국가 코드(sitecode) 부분은 그대로 실제 URL의 국가 코드를 써도 되고, 별도로
  `{SITECODE}`로 만들 필요는 없습니다** — `{PD_URL}` 자체가 이미 국가별로 다른
  크롤 대상 URL에 자동으로 매핑되는 구조입니다 (`runner.py`가 크롤한 실제 페이지 URL
  로 이 패턴을 매칭). 사용자가 어느 국가 URL을 기준으로 줬는지는 몰라도 됩니다.

### 2. `{SITECODE}` 토큰은 건드리지 마세요
`{PD_URL}`과 별개로 파일 안에 이미 있는 `{SITECODE}` 토큰(예: `https://www.samsung.com/
{SITECODE}/#org`)은 **런타임에 국가 코드로 자동 치환되는 별도 메커니즘**입니다.
이 토큰은 그대로 두세요. 절대 실제 국가 코드(`sg`, `uk` 등)로 직접 바꾸지 마세요.

### 3. brand / manufacturer / publisher의 sitecode 유무 — 이미 확정된 규칙
페이지 타입(Flagship PD vs Simple PD)에 따라 이 세 값의 `{SITECODE}` 포함 여부가
다릅니다. **이미 확정되어 있으니 절대 이 규칙을 바꾸지 말고, 그대로 따르세요**:

| | brand | manufacturer | publisher (VideoObject) |
|---|---|---|---|
| Flagship PD (폰류) | `.../{SITECODE}/#brand-galaxy` (있음) | `.../#org` (없음) | `.../#org` (없음) |
| Simple PD (워치/버즈류) | `.../#brand-galaxy` (없음) | `.../#org` (없음) | `.../{SITECODE}/#org` (있음) |

Watch8/WatchUltra는 Simple PD이므로 `schema_values.part6.json`에 이미 이 규칙대로
채워져 있습니다 — **이 값들은 건드리지 마세요.**

### 4. 값을 모르면 절대 추측해서 채우지 마세요
사용자가 스펙을 안 준 항목(예: 실제 이미지 CDN 경로, 정확한 SKU 등)은 `kind: "exist"`
/ `check: "존재만_확인"`으로 이미 설정되어 있습니다. 이건 "값은 몰라도 존재만 확인"
하겠다는 의도적 설계입니다 — 여기에 임의의 값을 채워 넣지 마세요. 사용자가 실제
값을 명시적으로 줬을 때만 그 항목의 `value`를 채우고 `kind`/`check`를 그에 맞게
바꾸세요(예: 정확한 URL이면 `kind: "url"`, `check: "정확히_일치"`).

### 5. 3DModel 블록은 조건부(optional)입니다
`schema_rules.simple.PDP.json`의 3DModel 블록은 `"conditional": true`로 설정되어
있습니다 — 페이지에 3D 모델이 없어도 정상입니다. `schema_values.part6.json`의
3DModel 데크도 있으면 채우고, 해당 제품 페이지에 3D 뷰어 자체가 없다면 그 블록을
통째로 지워도 됩니다(없어도 하드 실패로 처리되지 않음).

### 6. 스펙(MasterSpec) 값은 여기가 아니라 다른 곳입니다
이 작업(`schema_values.part*.json`)은 **JSON-LD 스키마 검증용 값**입니다.
Weight/Battery/Display 같은 **Spec QA용 스펙표**는 완전히 별도 시스템
(`/api/qb/spec-rules/upload` 로 업로드하는 Rule DB 엑셀)이니 혼동하지 마세요.
사용자가 "스펙 엑셀"을 따로 준다면 그건 이 파일이 아니라 Qubi 프론트엔드의
"⬆ Rule DB 엑셀 업로드" 기능으로 안내하세요. (아래 "사용자가 실제로 줄 정보 형식"
(A)/(B) 참고 — URL만 오고 스펙이 안 왔으면 먼저 확인하세요.)

### 7. 완료 후 검증 방법
값을 다 채운 뒤, 반드시 아래처럼 실제로 돌려서 에러 없이 findings가 나오는지
확인하고 나서 결과를 알려주세요 (파일만 수정하고 끝내지 마세요):

```python
import json, runner, schema_checker as sc

base_rules = json.load(open("schema_rules.simple.PDP.json", encoding="utf-8"))
rules = runner._apply_product_values(json.loads(json.dumps(base_rules)), "galaxy-watch8", page_type="PDP")
for b in rules["blocks"]:
    print(b["name"], "| id_pattern:", b.get("id_pattern"), "| ev_keys:", list(b.get("expected_values", {}).keys()))
```

`id_pattern`에 `{PD_URL}`이 실제 URL로 잘 치환됐는지, `ev_keys`가 비어있지 않은지
확인하세요.

---

## 사용자가 실제로 줄 정보 형식 (참고용)

**이 작업은 보통 두 가지가 "같이" 옵니다 — 하나만 오면 반쪽짜리 작업이니 둘 다 챙기세요:**

### (A) URL — 이 문서가 다루는 schema_values 작업용
```
Watch8 최종 URL: https://www.samsung.com/sg/watches/galaxy-watch/galaxy-watch8-44mm-silver-bluetooth-sm-l330nzsaasa/
Watch Ultra 최종 URL: https://www.samsung.com/sg/watches/... (전체 URL)
```
여러 색상/사이즈가 있으면 "이 URL이 기준(대표) 페이지"라고 명시해줄 겁니다 — 대표
URL 하나만 있으면 충분합니다(sitecode 국가는 무엇이든 상관없음, 위 규칙 참고).

### (B) 스펙(MasterSpec) — Spec QA용, 완전히 별도 시스템
```
제품: Watch8
- Weight: 30.3g
- Battery: 435mAh
- Display: 1.34형 Super AMOLED
...
```
Weight/Battery/Display 같은 실제 스펙값은 (A)의 schema_values 작업과 **완전히 다른
파이프라인**(Rule DB 엑셀, `/api/qb/spec-rules/upload`)으로 들어갑니다. **URL만 오고
스펙 목록이 안 왔다면, 반드시 사용자에게 "MasterSpec 엑셀(또는 스펙 리스트)도
같이 주셔야 Spec QA가 신제품 기준으로 동작합니다"라고 먼저 확인하세요** — 이거
없이 URL만 반영하면 Schema QA는 신제품으로 바뀌어도 Spec QA는 여전히 구모델
기준으로 채점됩니다.

- 엑셀(MasterSpec/Dictionary/Exception/InteractionRule 시트)로 주면 가장 정확합니다.
- 텍스트 나열도 되지만, 사용자가 "이 스펙은 확정 아니니 존재만 확인해줘"라고 하는
  항목은 값으로 채우지 말고 존재-확인(exist-only)으로 남기세요(위 4번 규칙 참고).
- 스펙 엑셀은 이 문서가 다루는 `schema_values.part*.json` 파일이 아니라, Qubi
  프론트엔드의 "⬆ Rule DB 엑셀 업로드" 기능으로 넣어야 합니다 — 새 agent가 코드
  파일에서 직접 이 부분을 고치려 하지 말고, 업로드 절차를 안내하세요.

---

## 막히면 진행하지 말고 이렇게 질문하세요

- URL 구조가 기존 컨벤션(`{PD_URL}#webpage`, `{PD_URL}#faq` 등)과 명백히 다르게 생겼다
  → 임의로 앵커를 붙이지 말고 사용자에게 실제 어떤 하위 섹션(FAQ/3D/영상)이 그
  페이지에 있는지 물어보세요.
- brand/manufacturer/publisher sitecode 규칙이 이번 제품에도 똑같이 적용되는지
  불확실하다 → 위 표를 그대로 적용하고, 확신이 안 서면 반영 전에 확인 질문하세요.
- 스펙 값(Weight/Battery 등)을 URL과 같이 주려는 것 같다 → 이건 별도 시스템
  (Rule DB 엑셀)이니 헷갈리지 말고 사용자에게 "이 스펙은 schema_values가 아니라
  Rule DB 엑셀 업로드로 넣어야 한다"고 안내하세요.
