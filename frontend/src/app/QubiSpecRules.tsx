"use client";
/* QubiSpecRules.tsx — Spec QA 기준표(Rule DB 뷰어·엑셀 업로드) + 검수 기준/점수 설명 패널
   [2026-07 분할] QubiSpecQa.tsx에서 분리. */
import { useEffect, useRef, useState } from "react";

import { C } from "./specQaShared";

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
        <span style={{ marginLeft: "auto", display: "inline-flex", gap: 6 }}>
          <button onClick={() => fileRef.current?.click()} disabled={busy} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 10px" }}>
            {busy ? "업로드 중…" : "⬆ Rule DB 엑셀 업로드"}
          </button>
          {/* [2026-07] 모델 DB 삭제 — 신모델 엑셀 업로드 후 구모델(예: Fold7)을 목록에서 내릴 때.
              룰·제품 사전·예외가 전부 삭제되며, 검수 이력·모니터링 URL·Global 사전은 유지된다. */}
          <button disabled={busy} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 10px", color: "#B42318", borderColor: "#FECDCA" }}
            onClick={async () => {
              if (!window.confirm(`'${product}'의 Rule DB 전체(룰 ${rules.length}개 + 제품 사전)를 삭제할까요?\n\n검수 이력·모니터링 URL·공통(Global) 사전은 그대로 유지됩니다.\n같은 제품 엑셀을 다시 업로드하면 언제든 복구돼요.`)) return;
              setBusy(true);
              try {
                const r = await fetch(api("/api/qb/spec-rules/delete"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product }) });
                if (!r.ok) throw new Error(String((await r.json().catch(() => ({}))).detail || r.status));
                flash(`'${product}' Rule DB 삭제됨 — 제품 목록은 새로고침 후 반영 🐝`); load();
              } catch (e: any) { flash(`삭제 실패 — ${e.message || e}`); } finally { setBusy(false); }
            }}>
            🗑 모델 삭제
          </button>
          <input ref={fileRef} type="file" accept=".xlsx" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.currentTarget.value = ""; }} />
        </span>
      </div>
      <p style={{ fontSize: 11.5, color: "var(--sec)", margin: "6px 0 4px" }}>
        이 표가 "정답지"예요. 각 항목이 페이지에 <b>이래야 정상</b>이라는 기준입니다. 값 수정은 엑셀을 고쳐 업로드하세요(화면 직접 편집 안 함 — 이력 관리를 엑셀로 일원화).
      </p>
      <div style={{ fontSize: 10.5, color: "var(--sec)", marginBottom: 8 }}>
        등급: <span style={{ color: "#D8362F" }}>●</span> 필수(틀리면 즉시 오류) · <span style={{ color: "#B54708" }}>●</span> 중요 · <span style={{ color: "#0A66E0" }}>●</span> 권장 · <span style={{ color: "#667085" }}>●</span> 참고 — 검사 방식·노출 위치는 각 행 아래 작은 글씨로 표시돼요
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
                  {/* [2026-07] 기준표 ⓘ 툴팁 전면 삭제 — 클릭 없이 읽히도록 서브텍스트로 상시 노출 */}
                  <td style={{ padding: "7px 10px", borderTop: "1px solid var(--line)" }}>
                    <span style={{ color: pri.c, marginRight: 5 }}>●</span>
                    <b>{r.attribute}</b>
                    <span style={{ display: "block", color: "var(--sec)", fontSize: 10.5, marginLeft: 13 }}>{r.category}</span>
                  </td>
                  <td style={{ padding: "7px 10px", borderTop: "1px solid var(--line)" }}>
                    <b style={{ color: "#067647" }}>{normalText(r)}</b>
                    <span style={{ display: "block", color: "var(--sec)", fontSize: 10.5, marginTop: 2, lineHeight: 1.5 }}>{VAL_KO[r.validation]?.label || r.validation} — {valDesc}</span>
                  </td>
                  <td style={{ padding: "7px 10px", borderTop: "1px solid var(--line)", color: "var(--sec)", fontSize: 11.5 }}>
                    <b style={{ color: pri.c }}>{pri.ko}</b>
                    <span> · {(PAGE_KO[r.page]?.ko) || r.page}</span>
                    <span style={{ display: "block", fontSize: 10.5, color: "#98A2B3", marginTop: 2 }}>
                      {(PAGE_KO[r.page]?.tip) || r.page}{r.exception ? " · ※ 국가/조건 예외 있음" : ""}
                    </span>
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

/* ── V2 검수 기준 설명 — [2026-07] 사람 친화적으로 재작성: 3가지 결과 중심, 짧은 문장 ── */
export function SpecV2Criteria({ show, panelRef }: { show: boolean; panelRef?: any }) {
  if (!show) return null;
  const box = { background: "#F7F9FC", border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px", marginTop: 8 } as const;
  const h = { fontWeight: 800, fontSize: 12.5, marginBottom: 4 } as const;
  const li = { fontSize: 12, color: "var(--sec)", lineHeight: 1.75 } as const;
  return (
    <div ref={panelRef} className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
      <b style={{ fontSize: 14 }}>검수 방식 — 스펙</b>
      <p style={{ fontSize: 12.5, color: "var(--sec)", margin: "6px 0 0" }}>
        위 Rule DB 표의 <b>정답 값</b>이 페이지에 <b>제대로 적혀 있는지</b>를 규칙으로만 대조해요. AI 추측이 없어서 같은 페이지는 언제나 같은 결과가 나옵니다.
      </p>
      <div style={box}>
        <div style={h}>결과는 딱 3가지</div>
        <div style={li}>
          <div>🔴 <b style={{ color: C.crit }}>오류</b> — 틀린 값이 <b>실제로 적혀 있음</b>. 예: 항목 이름 옆에 다른 숫자, 전작 스펙이 잘못 섞임. 1건만 있어도 페이지는 빨간불.</div>
          <div style={{ marginTop: 4 }}>🟡 <b style={{ color: C.warn }}>확인</b> — 틀렸다고 단정하긴 애매한 것. 사람이 한 번 봐주면 되고, <b>점수는 깎이지 않아요</b>.</div>
          <div style={{ marginTop: 4 }}>⚪ <b>값 없음</b> — 페이지에 아예 안 보이면 <b>오류가 아니에요</b>. 표시도 집계도 하지 않습니다.</div>
        </div>
      </div>
      <div style={box}>
        <div style={h}>언어·표기가 달라도 알아봐요</div>
        <div style={li}>
          4,400 mAh = 4.400 mAh = 4400mAh, 24 hours = 24時間 = 24시간 = 24 hrs처럼 <b>나라별 숫자·단위 표기를 같은 값으로 인정</b>해요.
          칩셋명처럼 나라마다 이름이 다른 항목은 사전(Dictionary)에 등록된 표기면 정상. "Fold6보다 …" 같은 전작 비교 문구는 전작 정답지와 따로 대조합니다.
        </div>
      </div>
      <div style={box}>
        <div style={h}>검사하지 않는 곳</div>
        <div style={li}>Header · Footer · 메뉴 · 팝업/프로모션 배너는 애초에 보지 않아요. Compare 표는 컬럼(제품)별로 구분해서 옆 제품 값을 오인하지 않습니다.</div>
      </div>
      <div style={box}>
        <div style={h}>Dictionary Review는 별개</div>
        <div style={li}>화면 맨 아래의 미등록 표현 목록은 <b>점수·신호등과 무관한</b> 번역 관리 기능이에요. 승인하면 다음 검수부터 반영됩니다.</div>
      </div>
    </div>
  );
}

/* ── V2 점수 계산 설명 — [2026-07] 계산식 한 줄 + 예시 한 줄 중심으로 간결화 ── */
export function SpecV2Score({ show, panelRef }: { show: boolean; panelRef?: any }) {
  if (!show) return null;
  const box = { background: "#F7F9FC", border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px", marginTop: 8 } as const;
  const li = { fontSize: 12, color: "var(--sec)", lineHeight: 1.7 } as const;
  return (
    <div ref={panelRef} className="card qbiPopIn" style={{ marginTop: 16, padding: 16 }}>
      <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 4 }}>📊 점수 계산 — 스펙</div>
      <div style={box}>
        <div style={{ fontSize: 15, fontWeight: 800 }}>점수 = 정상 ÷ (정상 + 오류) × 100</div>
        <div style={{ ...li, marginTop: 6 }}>
          🟡 확인과 ⚪ 값 없음은 <b>계산에 넣지 않아요</b> — 오답이라는 증거가 아니기 때문이에요.
          확인만 있는 페이지는 <b>100% + 🟡 배지</b>로 표시됩니다.
        </div>
        <div style={{ ...li, marginTop: 6, background: "#fff", border: "1px solid var(--line)", borderRadius: 6, padding: "6px 8px" }}>
          예) 정상 22 · 오류 2 · 확인 1 → 22 ÷ 24 = <b>91.7%</b> (확인 1건은 배지로만)
        </div>
        <div style={{ ...li, marginTop: 4 }}>카테고리(배터리·디스플레이…) 점수도 같은 식이에요.</div>
      </div>
      <div style={{ fontSize: 12, color: "var(--sec)", marginTop: 8, background: "#FFF5F4", border: "1px solid #FECDCA", borderRadius: 8, padding: "8px 10px" }}>
        <b>신호등 (스펙은 %가 아니라 건수 기준 — Data QA보다 엄격)</b>
        <div style={{ marginTop: 3 }}>🔴 오류 1건 이상 · 🟡 오류 0 + 확인 있음 · 🟢 둘 다 0</div>
        <div style={{ marginTop: 3, fontSize: 11.5 }}>스펙 오기재는 소비자 오인·법적 리스크로 이어질 수 있어 "오류 1건 = 즉시 빨강"으로 봅니다.</div>
      </div>
      <div style={{ fontSize: 11.5, color: "#93540A", marginTop: 8, background: "#FFFAEB", border: "1px solid #FEDF89", borderRadius: 8, padding: "8px 10px" }}>
        ⚠️ 상단에 <b>커버리지 경고</b>가 뜨면 점수를 그대로 믿지 마세요 — "다 맞았다"가 아니라 "검출된 게 적다"는 뜻일 수 있어요.
      </div>
    </div>
  );
}
