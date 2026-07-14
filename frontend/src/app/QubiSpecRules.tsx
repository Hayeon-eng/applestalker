"use client";
/* QubiSpecRules.tsx — Spec QA 기준표(Rule DB 뷰어·엑셀 업로드) + 검수 기준/점수 설명 패널
   [2026-07 분할] QubiSpecQa.tsx에서 분리. */
import { useEffect, useRef, useState } from "react";

import { C, InfoTip } from "./specQaShared";

const VAL_KO: Record<string, { label: string; desc: string }> = {
  // [V3] 공통 원칙: 값이 페이지에 없는 건 오류가 아니고, "틀린 값이 항목과 함께
  // 적혀 있을 때"만 오류. 아래 설명은 그 원칙을 유형별 예시로 풀어쓴 것.
  exact: { label: "값 그대로", desc: "이 값이 페이지에 보이면 정상. 콤마·공백·× 같은 표기 차이는 같은 값으로 인정 (2184 x 1968 = 2184×1968). 다른 값이 이 항목 이름과 함께 적혀 있을 때만 오류" },
  numeric_exact: { label: "숫자 일치", desc: "숫자만 맞으면 정상 — 4,400mAh = 4.400mAh = 4400mAh, 니트·ニト 같은 현지어 단위도 인정. 다른 숫자가 이 항목 이름과 함께 적혀 있을 때만 오류" },
  prefix: { label: "앞부분 일치", desc: "이 값으로 시작하면 정상 — 예: SM-F966B, SM-F966N/DS처럼 뒤에 지역 코드가 붙어도 통과" },
  dictionary: { label: "표기 자유", desc: "나라마다 표기가 다른 항목(칩셋명 등) — 정답 표기나 등록된 현지 표기가 보이면 정상. 다르게 서술돼 있어도 오류 아님(전작 칩명이 잘못 들어간 경우만 오류)" },
  option_match: { label: "옵션 노출", desc: "나열된 옵션 중 페이지에 보이는 것을 확인 — 일부가 안 보여도 오류 아님(국가별 미출시 가능). 목록에 없는 엉뚱한 옵션 값이 이 항목과 함께 적혀 있을 때만 오류" },
};
const PRI_COLOR: Record<string, string> = { Critical: "#D8362F", High: "#B54708", Medium: "#0A66E0", Low: "#667085" };

/* ── V2 검수 기준 스펙표 — Rule DB 뷰어 + 엑셀 업로드 (구 SpecTable 대체) ── */
export function SpecV2RuleTable({ product, api, flash }:
  { product: string; api: (p: string) => string; flash: (m: string) => void }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const load = async () => {
    try { setData(await (await fetch(api(`/api/qb/spec-rules?product=${encodeURIComponent(product)}`))).json()); }
    catch { setData(null); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [product]);
  const upload = async (f: File) => {
    setBusy(true);
    try {
      const b64: string = await new Promise((res, rej) => { const rd = new FileReader(); rd.onload = () => res(String(rd.result)); rd.onerror = rej; rd.readAsDataURL(f); });
      const r = await fetch(api("/api/qb/spec-rules/upload"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ b64, product, version: f.name }) });
      if (!r.ok) throw new Error(String((await r.json().catch(() => ({}))).detail || r.status));
      flash("Rule DB 갱신됨 — 다음 검수부터 적용 🐝"); load();
    } catch (e: any) { flash(`업로드 실패 — ${e.message || e}`); } finally { setBusy(false); }
  };
  const rules = data?.rules || [];
  // [FIX] Rule DB 병합 이력에 따라 버전이 "V3+V3"처럼 같은 값이 겹쳐 저장되는 경우가 있어(구분자 '+'),
  // 화면에는 중복 제거된 값만 보여준다. 원본 문자열 자체는 건드리지 않음(엑셀 이력 그대로 유지).
  const versionDisplay = (v: string) => {
    if (!v) return v;
    const parts = Array.from(new Set(v.split("+").map((x) => x.trim()).filter(Boolean)));
    return parts.join("+");
  };
  // 등급 → 색점 + 사람 설명 (개발자용 'Critical/High' 대신)
  const PRI_DOT: Record<string, { c: string; ko: string; why: string }> = {
    Critical: { c: "#D8362F", ko: "필수", why: "틀리면 바로 오류 — 반드시 정확해야 하는 핵심 스펙" },
    High: { c: "#B54708", ko: "중요", why: "제품 대표 스펙 — 노출 위치에서 꼭 맞아야 함" },
    Medium: { c: "#0A66E0", ko: "권장", why: "있으면 좋은 상세 스펙" },
    Low: { c: "#667085", ko: "참고", why: "부가 정보 — 없어도 큰 문제 아님" },
  };
  // 기준값을 자연어 '이래야 정상'으로
  // [V3] 기준값만 깔끔하게 — 검사 방식 설명은 옆의 ⓘ 툴팁이 담당한다(괄호 사족 제거).
  //      복수 정답 '4400|4272'는 사람이 읽기 좋게 '4400 또는 4272'로 표기.
  const normalText = (r: any) => {
    const exp = String(r.expected || "").split("|").map((x: string) => x.trim()).join(" 또는 ");
    return `${exp}${r.unit ? ` ${r.unit}` : ""}`;
  };
  // page(노출 영역) 라벨을 사람이 아는 말로
  const PAGE_KO: Record<string, { ko: string; tip: string }> = {
    "PDP": { ko: "제품 상세", tip: "제품 상세 페이지(PDP) 본문" },
    "PDP/Compare": { ko: "상세·비교", tip: "제품 상세와 비교 페이지 양쪽" },
    "Buy Box": { ko: "구매 영역", tip: "가격·구매 버튼이 있는 구매 박스 영역 (옵션 선택지가 여기 노출)" },
    "Disclaimer": { ko: "각주", tip: "페이지 하단 법적 고지·각주 영역" },
    "What's in the box": { ko: "구성품", tip: "박스 구성품 안내 영역" },
  };
  return (
    <div className="card" style={{ marginTop: 18, padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <b style={{ fontSize: 14 }}>검수 기준 스펙 — Rule DB</b>
        <span style={{ fontSize: 11, background: "#EEF4FE", color: C.blue, borderRadius: 5, padding: "2px 7px", fontWeight: 700 }}>{product}</span>
        <span style={{ fontSize: 11.5, color: "var(--sec)" }}>룰 {rules.length}개 · 버전 {versionDisplay(data?.version) || "—"}</span>
        <span style={{ marginLeft: "auto" }}>
          <button onClick={() => fileRef.current?.click()} disabled={busy} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 10px" }}>
            {busy ? "업로드 중…" : "⬆ Rule DB 엑셀 업로드"}
          </button>
          <input ref={fileRef} type="file" accept=".xlsx" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.currentTarget.value = ""; }} />
        </span>
      </div>
      <p style={{ fontSize: 11.5, color: "var(--sec)", margin: "6px 0 4px" }}>
        이 표가 "정답지"예요. 각 항목이 페이지에 <b>이래야 정상</b>이라는 기준입니다. 값 수정은 엑셀을 고쳐 업로드하세요(화면 직접 편집 안 함 — 이력 관리를 엑셀로 일원화).
      </p>
      <div style={{ fontSize: 10.5, color: "var(--sec)", marginBottom: 8 }}>
        등급: <span style={{ color: "#D8362F" }}>●</span> 필수 · <span style={{ color: "#B54708" }}>●</span> 중요 · <span style={{ color: "#0A66E0" }}>●</span> 권장 · <span style={{ color: "#667085" }}>●</span> 참고 · 각 행의 <b style={{ color: C.blue }}>ⓘ</b>를 누르면 검사 방식이 나와요
      </div>
      <div style={{ maxHeight: 340, overflow: "auto", border: "1px solid var(--line)", borderRadius: 10 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead><tr style={{ color: "var(--sec)", fontSize: 11, textAlign: "left", position: "sticky", top: 0, background: "#F9FAFB" }}>
            <th style={{ padding: "7px 10px", width: "28%" }}>항목</th>
            <th style={{ padding: "7px 10px", width: "44%" }}>이래야 정상</th>
            <th style={{ padding: "7px 10px" }}>왜 중요 · 어디에</th></tr></thead>
          <tbody>
            {rules.map((r: any) => {
              const pri = PRI_DOT[r.priority] || PRI_DOT.Low;
              const valDesc = VAL_KO[r.validation]?.desc || r.validation;
              return (
                <tr key={r.rule_id}>
                  <td style={{ padding: "7px 10px", borderTop: "1px solid var(--line)" }}>
                    <span style={{ color: pri.c, marginRight: 5 }}>●</span>
                    <b>{r.attribute}</b>
                    <InfoTip text={`${pri.ko} — ${pri.why}`} />
                    <span style={{ display: "block", color: "var(--sec)", fontSize: 10.5, marginLeft: 13 }}>{r.category}</span>
                  </td>
                  <td style={{ padding: "7px 10px", borderTop: "1px solid var(--line)" }}>
                    <b style={{ color: "#067647" }}>{normalText(r)}</b>
                    <InfoTip text={`검사 방식: ${valDesc}`} />
                  </td>
                  <td style={{ padding: "7px 10px", borderTop: "1px solid var(--line)", color: "var(--sec)", fontSize: 11.5 }}>
                    <b style={{ color: pri.c }}>{pri.ko}</b>
                    <span> · {(PAGE_KO[r.page]?.ko) || r.page}</span>
                    <InfoTip text={`위치: ${(PAGE_KO[r.page]?.tip) || r.page}${r.exception ? "\n※ 특정 국가/조건 예외 규칙 있음" : ""}`} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── V2 검수 기준 설명 (구 CriteriaPanel 스펙 브랜치 대체) ── */
export function SpecV2Criteria({ show, panelRef }: { show: boolean; panelRef?: any }) {
  if (!show) return null;
  const box = { background: "#F7F9FC", border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px", marginTop: 8 } as const;
  const h = { fontWeight: 800, fontSize: 12.5, marginBottom: 4 } as const;
  const li = { fontSize: 12, color: "var(--sec)", lineHeight: 1.75 } as const;
  return (
    <div ref={panelRef} className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
      <b style={{ fontSize: 14 }}>검수 방식 — 스펙</b>
      <p style={{ fontSize: 12.5, color: "var(--sec)", margin: "6px 0 0" }}>
        한 줄 요약: 위 Rule DB 표에 적힌 <b>정답 값</b>이 실제 페이지에 <b>그대로 있는지</b>를 규칙으로 대조합니다. AI가 추측하지 않고 정해진 규칙만 쓰기 때문에 같은 페이지는 항상 같은 결과가 나옵니다.
      </p>
      <div style={box}>
        <div style={h}>① 어디를 검사하나요</div>
        <div style={li}>
          스펙표·각주·구성품 영역과 본문에서 <b>정답 값이 올바르게 노출됐는지 / 틀린 값이 적혀 있는지</b>만 봅니다. Header·Footer·Nav·메뉴·버튼·팝업/프로모션은 애초에 검사하지 않습니다.<br />
          "4,400"과 "4 400"처럼 나라별 표기 차이는 <b>같은 값으로 인정</b>하고, 칩셋명처럼 나라마다 부르는 이름이 다른 항목은 사전(Dictionary)에 등록된 표기면 정상으로 봅니다.
        </div>
      </div>
      <div style={box}>
        <div style={h}>② 세 가지 판정 결과</div>
        <div style={li}>
          <div>🔴 <b style={{ color: C.crit }}>오류</b> — <b>틀린 값이 실제로 적혀 있음</b>을 확인한 경우. 예: 항목 라벨과 함께 적힌 오답, "일반 4,272mAh"처럼 한정어가 바뀐 값, 전작 스펙이 잘못 섞여 들어간 경우. 1건만 있어도 그 페이지는 오류로 처리됩니다.</div>
          <div style={{ marginTop: 4 }}>🟡 <b style={{ color: C.warn }}>확인</b> — 오답이라 단정하기엔 근거가 약한 경우. 예: "약 8인치" 같은 근사 표기, 라벨 없이 혼자 발견된 다른 숫자. <b>점수에는 영향 없고</b> 사람이 한 번 눈으로 봐주면 됩니다.</div>
          <div style={{ marginTop: 4 }}>⚪ <b>값 없음 = 오류 아님</b> — 페이지에 아예 안 보이는 항목은 표시도, 집계도 하지 않습니다. 오류는 "틀린 값이 적혀 있을 때"만 발생합니다.</div>
        </div>
      </div>
      <div style={box}>
        <div style={h}>③ 잘못 잡아내지 않기 위한 안전장치</div>
        <div style={li}>
          · 정답 값 자체(숫자+다국어 단위)로 찾기 때문에 언어가 달라도(2,600nits = 2600니트) 문제 없음<br />
          · 정답이 여러 개 허용되는 항목(일반 4,400mAh / 정격 4,272mAh)은 어느 쪽이든 정상 처리<br />
          · "Galaxy Z Fold6의 …"처럼 전작을 언급하는 문장은 전작 정답지와 따로 대조<br />
          · Compare 표는 컬럼 단위로 제품을 구분해서, 옆 제품 컬럼 값을 오인하지 않음<br />
          · 프로모션 배너 숫자·국가별 예외 규칙은 미리 반영
        </div>
      </div>
      <div style={box}>
        <div style={h}>④ Dictionary Review는 별개 기능</div>
        <div style={li}>
          화면 맨 아래 접힌 섹션에 나오는 <b>Dictionary Review</b>는 오류·확인과 무관한 보조 기능입니다. 제품 내 여러 페이지에 반복 등장한 <b>미등록 표현</b>만 빈도순으로 모아 보여줄 뿐, 점수나 신호등에는 전혀 영향을 주지 않습니다.
        </div>
      </div>
    </div>
  );
}

/* ── V2 점수 계산 설명 (구 ScorePanel의 스펙 탭 대응) ── */
export function SpecV2Score({ show, panelRef }: { show: boolean; panelRef?: any }) {
  if (!show) return null;
  const box = { background: "#F7F9FC", border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px", marginTop: 8 } as const;
  const li = { fontSize: 12, color: "var(--sec)", lineHeight: 1.7 } as const;
  return (
    <div ref={panelRef} className="card qbiPopIn" style={{ marginTop: 16, padding: 16 }}>
      <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 4 }}>📊 점수 산출 방식 — 스펙</div>
      <p style={{ fontSize: 12.5, color: "var(--sec)", margin: "0 0 8px" }}>
        한 줄 요약: <b>정답과 일치한 항목의 비율</b>입니다. "확인"과 "값 없음"은 감점하지 않습니다.
      </p>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>① 계산식</div>
        <div style={li}>정상(일치) ÷ (정상 + 오류) × 100</div>
        <div style={{ ...li, marginTop: 4 }}>
          🟡 확인은 감점 사유가 아니라서 분모에서 빠집니다 — 확인만 있는 페이지는 <b>100%</b> + 확인 배지로 표시됩니다.<br />
          값이 페이지에 없는 항목도 오류가 아니므로 애초에 집계 대상이 아닙니다.
        </div>
        <div style={{ ...li, marginTop: 6, background: "#fff", border: "1px solid var(--line)", borderRadius: 6, padding: "6px 8px" }}>
          예시: 정상 22 · 오류 2 · 확인 1 → 22 ÷ (22+2) = <b>91.7%</b> (확인 1건은 배지로만 별도 표시, 계산에서 제외)
        </div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>② 카테고리 점수도 같은 방식</div>
        <div style={li}>배터리·디스플레이 등 카테고리별 점수도 위와 똑같은 식으로 계산합니다. 카드에 보이는 "Rule Pass 8/8"이 그 카테고리의 (정상 / 정상+오류) 값이고, 오류·확인이 하나라도 있으면 해당 카테고리는 자동으로 펼쳐집니다.</div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>③ Dictionary Review는 점수와 무관</div>
        <div style={li}>화면 맨 아래 Dictionary Review는 점수·신호등 계산에서 완전히 분리된 보조 기능입니다. 여러 페이지에서 반복 등장한 미등록 표현만 모아 보여주고, 담당자가 승인하면 다음 검수부터 정식 사전에 반영됩니다.</div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>④ "커버리지 경고"가 뜨면 점수를 곧이곧대로 보지 마세요</div>
        <div style={li}>판정 대상의 절반 이상이 아예 검출되지 않으면 상단에 경고가 뜹니다. 이때 높은 점수는 "다 통과했다"가 아니라 "애초에 검출된 게 적다"는 뜻일 수 있으니, Dictionary Review를 먼저 확인해보세요.</div>
      </div>
      <div style={{ fontSize: 12, color: "var(--sec)", marginTop: 8, background: "#FFF5F4", border: "1px solid #FECDCA", borderRadius: 8, padding: "8px 10px" }}>
        <b>신호등 기준 (스펙은 Data QA보다 엄격)</b>
        <div style={{ marginTop: 3 }}>🔴 오류 1건 이상 · 🟡 오류 0 + 확인 있음 · 🟢 오류·확인 모두 0</div>
        <div style={{ marginTop: 3 }}>최상단 종합 판단 배너와 사이트별 신호등도 전부 같은 기준입니다. Data QA와 색·이모지는 같지만, 스펙 값 오류는 소비자 오인·법적 리스크로 이어질 수 있어 "%기준"이 아니라 <b>"오류 1건 = 즉시 빨강"</b>으로 판정합니다.</div>
      </div>
    </div>
  );
}

