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
        <span style={{ fontSize: 11.5, color: "var(--sec)" }}>룰 {rules.length}개 · 버전 {data?.version || "—"}</span>
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
        등급: <span style={{ color: "#D8362F" }}>●</span> 필수 · <span style={{ color: "#B54708" }}>●</span> 중요 · <span style={{ color: "#0A66E0" }}>●</span> 권장 · <span style={{ color: "#667085" }}>●</span> 참고 · 각 행 ⓘ 에 마우스를 올리면 검사 방식이 나와요
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
                    <span style={{ color: pri.c, marginRight: 5 }} title={`${pri.ko} — ${pri.why}`}>●</span>
                    <b>{r.attribute}</b>
                    <span style={{ display: "block", color: "var(--sec)", fontSize: 10.5, marginLeft: 13 }}>{r.category}</span>
                  </td>
                  <td style={{ padding: "7px 10px", borderTop: "1px solid var(--line)" }}>
                    <b style={{ color: "#067647" }}>{normalText(r)}</b>
                    <InfoTip text={`검사 방식: ${valDesc}`} />
                  </td>
                  <td style={{ padding: "7px 10px", borderTop: "1px solid var(--line)", color: "var(--sec)", fontSize: 11.5 }}>
                    <b style={{ color: pri.c }}>{pri.ko}</b>
                    <span> · {(PAGE_KO[r.page]?.ko) || r.page}</span>
                    <InfoTip text={`${pri.ko} — ${pri.why}\n위치: ${(PAGE_KO[r.page]?.tip) || r.page}${r.exception ? "\n※ 특정 국가/조건 예외 규칙 있음" : ""}`} />
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
        정답지(Rule DB)의 각 항목이 페이지에 정확히 반영됐는지 규칙 기반으로 대조합니다. AI 추론이 아니라 정해진 규칙으로만 판정하므로 같은 페이지는 항상 동일한 결과가 나오며, 항목별 판정 근거를 펼쳐 확인할 수 있습니다.
      </p>
      <div style={box}>
        <div style={h}>① 검사 대상</div>
        <div style={li}>
          스펙 노출 영역(스펙표·각주·구성품)과 본문에서 <b>정답 값의 노출과 오기재 여부</b>를 확인합니다. Header/Footer/Nav/Menu/Button/Popup·프로모션은 검사 대상에서 제외합니다.
          "4,400"과 "4 400"처럼 국가별 표기 차이는 <b>동일 값으로 인정</b>하며, 칩셋명 등 현지화 표기는 사전(Dictionary)으로 매핑합니다.
        </div>
      </div>
      <div style={box}>
        <div style={h}>② 판정 등급</div>
        <div style={li}>
          <div>🔴 <b style={{ color: C.crit }}>오류</b> — <b>틀린 값이 실제로 적혀 있음</b>이 확인된 항목: 항목 라벨과 함께 표기된 오답, 한정어 오짝(예: "일반 4,272mAh"), 전작 비교 문구 속 전작 스펙 오기재, 전작 값 혼입(예: CPU에 전작 칩명). 텍스트 스펙(칩셋명 등)은 서술이 달라도 오류가 아닙니다 — 전작 값 혼입 등 적극적 증거가 있을 때만 오류. 1건이라도 있으면 해당 페이지는 오류 처리됩니다.</div>
          <div>🟡 <b style={{ color: C.warn }}>확인</b> — 오답으로 단정하기 어려운 발견: 근사 표기("약 8인치")·단위 환산 표기, 라벨 없이 단독 발견된 불일치 숫자, 배율(x)처럼 렌즈·주장에 따라 값이 달라지는 항목. <b>점수에 반영되지 않으며</b> 사람이 한번 봐주면 됩니다.</div>
          <div style={{ marginTop: 2 }}>ℹ️ <b>값이 페이지에 없는 것은 오류가 아닙니다</b> — 미노출 항목은 표시·집계하지 않습니다. 오류는 "잘못 들어간 값"에만 부여됩니다.</div>
          <div>📖 <b>Dictionary Review</b> — 오류·확인과 별개의 보조 기능. 화면 맨 아래 접힌 섹션에서, 제품 내 여러 페이지에 반복 등장한 미등록 표현만 빈도순으로 보여줍니다.</div>
        </div>
      </div>
      <div style={box}>
        <div style={h}>③ 오탐 방지 규칙</div>
        <div style={li}>
          · 판정은 <b>값 우선(value-first)</b> — 라벨 번역이 아니라 정답 값 자체(숫자+다국어 단위)를 찾으므로 언어·표기(2,600nits=2600니트=٢٦٠٠ نت)에 무관<br />
          · <b>복수 정답</b> 지원 — 일반 4,400mAh / 정격 4,272mAh처럼 어느 표기든 정답으로 인정하고, 한정어 짝만 교차검증<br />
          · <b>전작 비교 문구 인식</b> — "Galaxy Z Fold6의 …" 문장 속 숫자는 전작 정답지와 대조 (전작 값이 틀리면 그것대로 오류)<br />
          · Compare 표는 <b>컬럼→제품 귀속</b> — 이웃 제품 컬럼의 값을 검수 대상 값으로 오인하지 않음<br />
          · 프로모션 배너 수치 제외 · 국가별 예외 규칙 사전 반영
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
      <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 8 }}>📊 점수 산출 방식 — 스펙</div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>① 점수 = 통과 ÷ 판정 대상</div>
        <div style={li}><b>정답 일치 항목 ÷ (일치 + 불일치)</b> × 100. <b>확인(🟡)은 감점 사유가 아니므로 분모에서 제외</b>됩니다 — 확인만 있는 페이지는 100% + 확인 배지로 표시됩니다. 값이 페이지에 없는 항목도 오류가 아니므로 표시·집계 모두에서 제외됩니다.</div>
        <div style={{ ...li, marginTop: 4 }}>예) 일치 22 · 불일치 2 · 확인 1 → 22 ÷ 24 = <b>91.7%</b> (확인 1은 배지로만 표시)</div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>② 카테고리별 동일 산식</div>
        <div style={li}>배터리·디스플레이 등 카테고리 단위로도 같은 방식으로 계산합니다. 카드의 "Rule Pass 8/8"이 해당 카테고리의 일치/판정 대상 수이며, 불일치·확인이 있는 카테고리는 자동 전개됩니다.</div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>③ Dictionary Review는 점수에 미반영</div>
        <div style={li}>Dictionary는 <b>보조 기능</b>이라 점수·Critical/Warning 집계에서 완전히 분리됩니다. 제품 내 여러 페이지에서 반복 등장하고 Confidence가 낮지 않은 표현만 화면 맨 아래(접힘)에 모여 표시되며, 유효한 표현은 승인 시 사전에 반영되어 다음 검수부터 정식 판정됩니다.</div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>④ 커버리지 경고 시 점수 해석 주의</div>
        <div style={li}>판정 대상의 <b>절반 이상이 미검출</b>이면 상단에 경고가 표시됩니다. 사전 미등록 또는 페이지 구조 차이로 수집되지 않았을 수 있으며, 이 경우 높은 점수는 "전부 통과"가 아니라 "검출 자체가 적음"을 의미할 수 있으므로 Dictionary Review 확인이 도움이 될 수 있습니다.</div>
      </div>
      <div style={{ fontSize: 12, color: "var(--sec)", marginTop: 8, background: "#FFF5F4", border: "1px solid #FECDCA", borderRadius: 8, padding: "8px 10px" }}>
        <b>신호등 (스펙은 더 엄격한 기준)</b> — 🔴 <b>오류 1건 이상이면 빨강</b> · 🟡 오류 0, 확인만 존재 · 🟢 오류·확인 모두 0. 최상단 <b>종합 판단 — 스펙</b> 배너와 사이트별 pill도 같은 기준·같은 색(Data QA와 동일 팔레트)입니다.
        <span style={{ display: "block", marginTop: 3, fontSize: 11 }}>색·형태는 Data QA와 동일하나, 스펙 값 오류는 소비자 오인·법적 리스크로 이어지므로 Data QA(점수 %기준)와 달리 "오류 1건 = 즉시 빨강"으로 판정합니다. Dictionary Review는 이 신호등에 전혀 영향을 주지 않습니다.</span>
      </div>
    </div>
  );
}

