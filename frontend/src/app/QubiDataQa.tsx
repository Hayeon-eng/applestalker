"use client";
/* QubiDataQa.tsx — DATA QA(스키마·HTML) 상세/종합/전사이트 렌더 블록.
   QubiSections에서 분리(파일 크기 축소). 상태는 ctx로 주입받음. */
import { useState, Fragment } from "react";
import type { ReactNode } from "react";
import { SEV, HONEY, sel, TL_COLOR, TL_EMOJI, humanizeTerm } from "./qubiShared";


// ── HTML QA 종합 패널 [신규] ──────────────────────────────────────
// 최상단 종합판단(전체 신호등 + 타입별 신호등) + 항목별 그룹핑(Meta/H태그 · 스키마 정보적합성 ·
// 파싱+리치결과 · id연결성). Level1(적용율%)+Level2(3축) 백엔드(/api/qb/check-html-qa) 결과를 그대로 렌더링.

function Accordion({ title, defaultOpen, children }: { title: ReactNode; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 10, marginTop: 10, overflow: "hidden" }}>
      <div onClick={() => setOpen((v) => !v)} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", background: "#F9FAFB", cursor: "pointer", fontSize: 13, fontWeight: 700 }}>
        <span>{title}</span><span style={{ fontSize: 11, color: "#0A66E0" }}>{open ? "▲ 접기" : "▼ 펼치기"}</span>
      </div>
      {open && <div className="qbiPopIn" style={{ padding: "10px 12px" }}>{children}</div>}
    </div>
  );
}

// 속성별 '수정 위치 + 영향' 표시용 정적 사전(로직/점수와 무관, 표현 전용)
const PROP_HELP: Record<string, { label: string; where: string; why: string }> = {
  name: { label: "제품명(name)", where: "JSON-LD → Product → name", why: "제품명 누락 시 Product 리치결과 생성 불가" },
  image: { label: "대표 이미지(image)", where: "JSON-LD → Product → image", why: "이미지 없으면 리치결과 미표기 가능" },
  brand: { label: "브랜드(brand)", where: "JSON-LD → Product → brand", why: "브랜드 정보로 신뢰도·매칭 향상" },
  manufacturer: { label: "제조사(manufacturer)", where: "JSON-LD → Product → manufacturer", why: "제조사 정보 보강" },
  potentialAction: { label: "구매 액션(potentialAction)", where: "JSON-LD → Product → potentialAction", why: "구매 액션 연결" },
  subjectOf: { label: "연결 선언(subjectOf)", where: "JSON-LD → Product → subjectOf(@id)", why: "영상·3D·FAQ 연결 선언" },
  offers: { label: "가격·재고(offers)", where: "JSON-LD → Product → offers", why: "가격·재고 정보(단독형 PDP 필수)" },
  sku: { label: "제품 식별자(sku)", where: "JSON-LD → Product → sku", why: "제품 식별자" },
  // 내부 계산 키 → 사람이 읽는 라벨
  structure_valid: { label: "FAQ 구조 유효성", where: "JSON-LD → FAQPage → mainEntity(Question/Answer)", why: "질문·답변 구조가 올바라야 FAQ로 인식" },
  screen_match: { label: "화면 노출 일치", where: "FAQPage 마크업 ↔ 화면 Q&A", why: "마크업과 실제 화면 내용이 일치해야 함" },
  type_combo: { label: "타입 선언(@type)", where: "JSON-LD → @type", why: "필수 타입 조합 선언" },
  url: { label: "URL", where: "JSON-LD → url", why: "정규 URL과 일치" },
  numberOfItems: { label: "항목 수(numberOfItems)", where: "JSON-LD → ItemList → numberOfItems", why: "선언 개수 = 실제 항목 수" },
  itemListElement: { label: "목록 항목(itemListElement)", where: "JSON-LD → ItemList → itemListElement", why: "목록 항목 완비" },
  mainEntityOfPage: { label: "페이지 연결(mainEntityOfPage)", where: "JSON-LD → mainEntityOfPage", why: "페이지와 상호 연결" },
  encoding_contentUrl: { label: "3D 파일 URL(encoding.contentUrl)", where: "JSON-LD → 3DModel → encoding.contentUrl", why: "3D 모델 파일 경로" },
  encoding_encodingFormat: { label: "3D 포맷(encoding.encodingFormat)", where: "JSON-LD → 3DModel → encoding.encodingFormat", why: "유효한 3D MIME" },
  thumbnailUrl: { label: "썸네일(thumbnailUrl)", where: "JSON-LD → VideoObject → thumbnailUrl", why: "영상 썸네일" },
  uploadDate: { label: "업로드일(uploadDate)", where: "JSON-LD → VideoObject → uploadDate", why: "ISO8601 업로드일" },
  contentUrlOrEmbedUrl: { label: "영상 URL(contentUrl/embedUrl)", where: "JSON-LD → VideoObject → contentUrl 또는 embedUrl", why: "재생 가능한 영상 경로" },
  duration: { label: "재생 길이(duration)", where: "JSON-LD → VideoObject → duration", why: "영상 길이(PT#S)" },
  description: { label: "설명(description)", where: "JSON-LD → description", why: "요약 설명" },
};
const propHelp = (p: string) => PROP_HELP[p] || { label: p, where: `JSON-LD → ${p}`, why: "" };

// PASS/부족 배지
function StatusChip({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span style={{ fontSize: 11, borderRadius: 6, padding: "3px 8px", whiteSpace: "nowrap",
      background: ok ? "#ECFDF3" : "#FEF3F2", color: ok ? "#067647" : "#D8362F" }}>
      {ok ? "✅" : "❌"} {label}
    </span>
  );
}

// 충족률 게이지(작은 막대) — KPI 유지용
function Meter({ pct, danger }: { pct: number | null; danger?: boolean }) {
  const v = pct == null ? 0 : pct;
  const color = danger || v < 50 ? "#D8362F" : v < 80 ? "#E0A008" : "#1F9E5C";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 130 }}>
      <div style={{ flex: 1, height: 6, background: "#EEF1F6", borderRadius: 999 }}>
        <div style={{ width: `${v}%`, height: "100%", background: color, borderRadius: 999 }} />
      </div>
      <b style={{ fontSize: 12.5, color }}>{pct == null ? "—" : `${pct}%`}</b>
    </div>
  );
}

// 단어 단위 diff (애플스토커 InlineDiff와 동일 스타일) — 기대값 vs 현재값 비교 표시
function _tok(s: string): string[] { return (s || "").match(/\s+|[^\s]+/g) || []; }
function MiniDiff({ expected, actual }: { expected: string; actual: string }) {
  const a = _tok(actual), b = _tok(expected);
  const n = a.length, m = b.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: { t: string; s: string }[] = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { out.push({ t: "same", s: a[i] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ t: "del", s: a[i] }); i++; }
    else { out.push({ t: "ins", s: b[j] }); j++; }
  }
  while (i < n) { out.push({ t: "del", s: a[i] }); i++; }
  while (j < m) { out.push({ t: "ins", s: b[j] }); j++; }
  return (
    <span style={{ lineHeight: 1.7, wordBreak: "break-all" }}>
      {out.map((t, k) => t.t === "same"
        ? <span key={k}>{t.s}</span>
        : t.t === "del"
          ? <span key={k} style={{ textDecoration: "line-through", color: "#B42318", background: "#FDECEA", borderRadius: 3 }}>{t.s}</span>
          : <span key={k} style={{ textDecoration: "underline", color: "#067647", background: "#EAF7EE", fontWeight: 700, borderRadius: 3 }}>{t.s}</span>)}
    </span>
  );
}

export function HtmlQaDetail({ hq, findings = [] }: { hq: any; findings?: any[] }) {
  const l1 = hq.level1_apply_rate || {};
  const axis2 = hq.level2?.axis2_parsing_rich_result || {};
  const axis3 = hq.level2?.axis3_id_linkage || {};
  const perType: Record<string, any> = hq.level2?.per_type || {};
  const sig = l1.signals || {};

  // findings를 블록별로 묶어 '수정 위치' 표시에 활용
  const findingsByBlock: Record<string, any[]> = {};
  for (const f of findings || []) (findingsByBlock[f.block || "기타"] ||= []).push(f);

  // HTML QA 항목(Meta/H태그) — PASS/FAIL 한눈에
  // [FIX] Title/Description은 백엔드(html_qa_scoring.level1_apply_rate)가 이미 버퍼(±10/±20자)를
  // 적용해 pass/warn/fail 3단계로 판정해둔 걸 그대로 쓴다. 예전엔 이 컴포넌트가 자체적으로
  // "<=60자면 OK, 아니면 ❌" 이진 체크를 따로 하고 있어서, 버퍼 안(60~70자)인 62자도 무조건
  // ❌ 오류로 보였다 — 실제로는 백엔드도 이건 "확인 권장(🟡)"이지 오류가 아니다.
  const _itemStatus = (name: string, fallbackOk: boolean): "pass" | "warn" | "fail" => {
    const found = (l1.items || []).find((it: any) => it.item === name);
    if (found?.status) return found.status;
    return fallbackOk ? "pass" : "fail";
  };
  const titleLen = (sig.title || "").length;
  const descLen = (sig.meta_description || "").length;
  const h1n = (sig.h1_list || []).length;
  const titleStatus = sig.title ? _itemStatus("Meta Title 존재·길이", titleLen <= 60) : "fail";
  const descStatus = sig.meta_description ? _itemStatus("Meta Description 존재·길이", descLen <= 160) : "fail";
  const htmlItems = [
    { key: "Meta Title", status: titleStatus, ok: titleStatus !== "fail", val: sig.title, note: sig.title ? `${titleLen}자` : "누락", where: "<head> → <title>" },
    { key: "Meta Description", status: descStatus, ok: descStatus !== "fail", val: sig.meta_description, note: sig.meta_description ? `${descLen}자` : "누락", where: "<head> → meta[name=description]" },
    { key: "H1", status: h1n === 1 ? "pass" : "fail" as const, ok: h1n === 1, val: (sig.h1_list || []).join(" / "), note: `${h1n}개`, where: "본문 <h1>" },
    { key: "H2", status: (sig.h2_list || []).length > 0 ? "pass" : "fail" as const, ok: (sig.h2_list || []).length > 0, val: `${(sig.h2_list || []).length}개`, note: `${(sig.h2_list || []).length}개`, where: "본문 <h2>" },
    // [신규] H3/H4 — H1/H2 아래 순차 노출(표시 전용, PASS/FAIL 판정 없음: H3/H4는 없어도 정상인 페이지가
    // 많아 H1/H2와 같은 기준으로 ❌ 오류 처리하면 오탐이 된다 — 개수만 참고용으로 보여준다)
    { key: "H3", status: "pass" as const, ok: true, val: `${(sig.h3_list || []).length}개`, note: `${(sig.h3_list || []).length}개`, where: "본문 <h3>" },
    { key: "H4", status: "pass" as const, ok: true, val: `${(sig.h4_list || []).length}개`, note: `${(sig.h4_list || []).length}개`, where: "본문 <h4>" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* ═══ HTML 검수 카드 (파랑 계열) ═══ */}
      <div style={{ border: "1px solid #DCE7FA", borderRadius: 12, overflow: "hidden" }}>
        <div style={{ background: "#EEF4FE", padding: "8px 14px", fontSize: 12, fontWeight: 800, color: "#1B57C4", borderLeft: "3px solid #1B57C4" }}>
          HTML 검수 <span style={{ fontWeight: 400, color: "#5B7BB4", fontSize: 10.5 }}>Meta · 제목 태그</span>
        </div>
        <div style={{ padding: "10px 14px" }}>
        {/* 문제 먼저 — 진짜 오류(fail)만 빨간 박스. 버퍼 이내 경미한 초과(warn)는 별도로 옅게 표시 */}
        {htmlItems.filter((i) => i.status === "fail").length > 0 && (
          <div style={{ background: "#FEF3F2", borderRadius: 8, padding: "7px 10px", marginBottom: 8 }}>
            {htmlItems.filter((i) => i.status === "fail").map((i) => (
              <div key={i.key} style={{ fontSize: 11.5, padding: "2px 0" }}>
                <b style={{ color: "#B42318" }}>❌ {i.key}</b> <span style={{ color: "var(--sec)" }}>{i.note}</span>
              </div>
            ))}
          </div>
        )}
        {htmlItems.filter((i) => i.status === "warn").length > 0 && (
          <div style={{ background: "#FFFAEB", borderRadius: 8, padding: "7px 10px", marginBottom: 8 }}>
            {htmlItems.filter((i) => i.status === "warn").map((i) => (
              <div key={i.key} style={{ fontSize: 11.5, padding: "2px 0" }}>
                <b style={{ color: "#93540A" }}>🟡 {i.key}</b> <span style={{ color: "var(--sec)" }}>{i.note} — 오류 아님, 확인 권장</span>
                <span style={{ color: "var(--sec)", marginLeft: 6, fontSize: 11 }}>· 수정 위치: {i.where}</span>
              </div>
            ))}
          </div>
        )}
        {/* 실제 태깅 값 + PASS (글씨 작게) */}
        <div style={{ display: "grid", gridTemplateColumns: "110px 1fr", rowGap: 6, fontSize: 11.5, alignItems: "start" }}>
          {htmlItems.map((i) => (
            <Fragment key={i.key}>
              <span style={{ color: "var(--sec)" }}>{i.status === "pass" ? "✅" : i.status === "warn" ? "🟡" : "❌"} {i.key}</span>
              <span>
                {i.key === "H2" || i.key === "H3" || i.key === "H4"
                  ? (() => {
                      const list = i.key === "H2" ? (sig.h2_list || []) : i.key === "H3" ? (sig.h3_list || []) : (sig.h4_list || []);
                      return list.length
                        ? list.map((t: string, k: number) => <span key={k} style={{ display: "inline-block", background: "#F2F4F7", padding: "1px 6px", borderRadius: 5, margin: "1px 4px 1px 0", fontSize: 10.5 }}>{t}</span>)
                        : <i style={{ color: i.key === "H2" ? "#B42318" : "var(--sec)" }}>{i.key === "H2" ? "누락" : "없음"}</i>;
                    })()
                  : (i.val ? <code style={{ background: "#F2F4F7", padding: "2px 6px", borderRadius: 5, wordBreak: "break-word", fontSize: 11 }}>{i.val}</code> : <i style={{ color: "#B42318" }}>누락</i>)}
              </span>
            </Fragment>
          ))}
        </div>
        </div>
      </div>

      {/* ═══ Schema 검수 (앰버 계열) ═══ */}
      <div style={{ border: "1px solid #F5E6C8", borderRadius: 12, overflow: "hidden" }}>
        <div style={{ background: "#FDF6E9", padding: "8px 14px", fontSize: 12, fontWeight: 800, color: "#96690B", borderLeft: "3px solid #E0A008" }}>
          Schema 검수 <span style={{ fontWeight: 400, color: "#A98A4B", fontSize: 10.5 }}>구조화 데이터(JSON-LD)</span>
        </div>
        <div style={{ padding: "10px 14px" }}>
        {Object.keys(perType).length === 0 && <p style={{ color: "var(--sec)", fontSize: 12 }}>감지된 Schema가 없어요.</p>}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {Object.entries(perType).map(([t, v]: [string, any]) => {
            const missReq: string[] = v.missing_required || [];
            const weakRec: string[] = v.weak_recommended || [];
            const blockFindings = (findingsByBlock[t] || []).filter((f) => {
              if (f.status !== "fail" && f.status !== "warn") return false;
              // '번역 확인 필요'처럼 오류가 아닌 안내성 finding(값불일치·누락 없음)은 판정근거에서 제외
              const hasReal = (f.val_mismatch || []).length || (f.missing_props || []).length ||
                              (f.name_issue || []).length || f.id_mismatch || (f.haspart_missing || []).length;
              const onlyTranslate = (f.translate_confirm || []).length && !hasReal;
              return !onlyTranslate;
            });
            // 파싱/리치결과 Critical 중, 이미 '필수 누락'으로 위에 표시한 속성과 겹치는 메시지는 제외(중복 방지)
            const parseCritical = (axis2.by_type?.[t]?.detail || []).filter((d: any) =>
              d.severity === "Critical" && !missReq.some((p) => (d.message || "").includes(p)));
            const allBlockFindings = (findingsByBlock[t] || []);
            const codeSnippet = allBlockFindings.find((f: any) => f.raw)?.raw || "";
            return (
              <details key={t} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "12px 14px" }}>
                <summary style={{ listStyle: "none", cursor: "pointer" }}>
                  {/* 헤더: 신호등 + 타입 + 최종% */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span>{TL_EMOJI[v.traffic_light] || "⚪"}</span>
                    <b style={{ fontSize: 13 }}>{t}</b>
                    {v.rich_result_status && v.rich_result_status !== "정식" && !String(v.rich_result_status).includes("폐지") &&
                      <span style={{ fontSize: 10.5, color: "var(--sec)", background: "#F2F4F7", borderRadius: 5, padding: "1px 6px" }}>리치결과 {v.rich_result_status}</span>}
                    <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
                      <Meter pct={v.final_pct} danger={v.axis1_gate_triggered || v.axis2_gate === 0} />
                      <span style={{ fontSize: 11, color: "#0A66E0" }}>펼치기 ▾</span>
                    </span>
                  </div>

                  {/* 1) 문제 먼저 (사람 라벨 + 영향 + 수정 위치) */}
                  {missReq.length > 0 && (
                    <div style={{ background: "#FEF3F2", borderRadius: 8, padding: "8px 10px", marginTop: 8 }}>
                      {missReq.map((p) => {
                        const h = propHelp(p);
                        return (
                          <div key={p} style={{ fontSize: 12.5, padding: "3px 0" }}>
                            <b style={{ color: "#B42318" }}>❌ {h.label} 누락/미흡</b>
                            {h.why && <div style={{ color: "var(--sec)", fontSize: 11.5, marginLeft: 18 }}>영향: {h.why}</div>}
                            <div style={{ color: "var(--sec)", fontSize: 11.5, marginLeft: 18 }}>수정 위치: {h.where}</div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {parseCritical.length > 0 && (
                    <div style={{ background: "#FEF3F2", borderRadius: 8, padding: "8px 10px", marginTop: 6 }}>
                      {parseCritical.map((d: any, i: number) => (
                        <div key={i} style={{ fontSize: 12.5, color: "#B42318" }}>❌ {d.message}</div>
                      ))}
                    </div>
                  )}

                  {/* 2) 충족 현황(개수) */}
                  <div style={{ display: "flex", gap: 16, fontSize: 12.5, flexWrap: "wrap", marginTop: 8 }}>
                    <span style={{ color: "var(--sec)" }}>정보 충족률 <b style={{ color: "var(--label)" }}>{v.axis1_info_adequacy_pct}%</b></span>
                    <span style={{ color: "var(--sec)" }}>필수 속성 <b style={{ color: v.required_ok < v.required_total ? "#B42318" : "#067647" }}>{v.required_ok} / {v.required_total}</b></span>
                    <span style={{ color: "var(--sec)" }}>권장 속성 <b style={{ color: v.recommended_ok < v.recommended_total ? "#E0A008" : "#067647" }}>{v.recommended_ok} / {v.recommended_total}</b></span>
                  </div>
                  {weakRec.length > 0 && (
                    <div style={{ marginTop: 6, fontSize: 11.5, color: "var(--sec)" }}>🟡 권장 보강: {weakRec.map((p) => propHelp(p).label).join(", ")}</div>
                  )}
                  {missReq.length === 0 && !v.axis1_gate_triggered && weakRec.length === 0 && parseCritical.length === 0 && (
                    <div style={{ marginTop: 6, fontSize: 12, color: "#067647" }}>✅ 모든 필수·권장 항목 충족</div>
                  )}
                </summary>

                {/* ── 펼침: 속성별 상세 + JSON-LD 코드 ── */}
                <div style={{ marginTop: 10, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
                  <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--sec)", marginBottom: 4 }}>속성별 상세</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr auto", rowGap: 4, fontSize: 12 }}>
                    {(v.prop_detail || []).length > 0 ? (v.prop_detail || []).map((pd: any, i: number) => (
                      <Fragment key={i}>
                        <span>{pd.score >= 1 ? "✅" : pd.score > 0 ? "🟡" : "❌"} {propHelp(pd.prop).label}</span>
                        <span style={{ color: "var(--sec)", textAlign: "right" }}>{pd.score >= 1 ? "충족" : pd.score > 0 ? "부분" : "누락"}</span>
                      </Fragment>
                    )) : <span style={{ color: "var(--sec)" }}>상세 정보 없음</span>}
                  </div>
                  {blockFindings.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--sec)", marginBottom: 4 }}>판정 근거
                        <span style={{ fontWeight: 400, marginLeft: 6 }}><span style={{ textDecoration: "line-through", color: "#B42318" }}>현재값</span> / <span style={{ textDecoration: "underline", color: "#067647" }}>기대값</span></span>
                      </div>
                      {blockFindings.map((f: any, i: number) => {
                        const vms = (f.val_mismatch || []).filter((v: any) => v.expected != null || v.actual != null);
                        if (vms.length > 0) {
                          return vms.map((vm: any, k: number) => (
                            <div key={`${i}-${k}`} style={{ fontSize: 11.5, padding: "3px 0", borderTop: k === 0 && i === 0 ? "none" : "1px solid var(--line)" }}>
                              <b>{propHelp(vm.prop).label}</b>{" "}
                              <MiniDiff expected={String(vm.expected ?? "")} actual={String(vm.actual ?? "(없음)")} />
                            </div>
                          ));
                        }
                        // 값 diff가 없는 근거(누락/번역확인 등)는 짧은 텍스트로
                        return <div key={i} style={{ fontSize: 11.5, color: "var(--sec)", padding: "2px 0" }}>· {humanizeTerm(f.as_is || "")}</div>;
                      })}
                    </div>
                  )}
                  {codeSnippet && (() => {
                    // 코드 라인별 diff 주석: 속성명 → {expected, actual, kind}
                    const ann: Record<string, { expected?: string; actual?: string; kind: "mismatch" | "missing" }> = {};
                    for (const f of allBlockFindings) {
                      for (const vm of (f.val_mismatch || [])) if (vm.prop) ann[vm.prop] = { expected: String(vm.expected ?? ""), actual: String(vm.actual ?? ""), kind: "mismatch" };
                      for (const mp of (f.missing_props || [])) ann[mp] = { kind: "missing" };
                    }
                    const lines = codeSnippet.split("\n");
                    return (
                      <div style={{ marginTop: 8 }}>
                        <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--sec)", marginBottom: 4 }}>
                          현재 JSON-LD (수정 대상) <span style={{ fontWeight: 400 }}>— <span style={{ textDecoration: "line-through", color: "#F98080" }}>현재</span> / <span style={{ textDecoration: "underline", color: "#84E1BC" }}>기대</span></span>
                        </div>
                        <pre style={{ margin: 0, background: "#0F172A", color: "#E2E8F0", fontSize: 11, borderRadius: 8, padding: "8px 10px", overflowX: "auto", lineHeight: 1.6 }}>
                          {lines.map((ln: string, i: number) => {
                            // 이 라인이 어떤 속성인지("prop": ...) 추출
                            const m = ln.match(/"([A-Za-z0-9_]+)"\s*:/);
                            const a = m ? ann[m[1]] : undefined;
                            return (
                              <div key={i} style={{ background: a ? (a.kind === "missing" ? "#3B1D1D" : "#3A2E12") : "transparent", borderRadius: 3 }}>
                                <span style={{ color: "#475569", userSelect: "none", display: "inline-block", width: 26, textAlign: "right", marginRight: 10 }}>{i + 1}</span>
                                <span>{ln}</span>
                                {a && a.kind === "mismatch" && (
                                  <span>{"  "}<span style={{ color: "#F98080", textDecoration: "line-through" }}>{a.actual || "(없음)"}</span>{" → "}<span style={{ color: "#84E1BC", textDecoration: "underline", fontWeight: 700 }}>{a.expected}</span></span>
                                )}
                              </div>
                            );
                          })}
                          {/* 누락 속성은 코드에 라인 자체가 없으므로 하단에 '추가 필요'로 표기 */}
                          {Object.entries(ann).filter(([, v]) => v.kind === "missing").map(([p], k) => (
                            <div key={`miss${k}`} style={{ background: "#1E3A2A", borderRadius: 3, marginTop: 2 }}>
                              <span style={{ color: "#475569", userSelect: "none", display: "inline-block", width: 26, textAlign: "right", marginRight: 10 }}>+</span>
                              <span style={{ color: "#84E1BC", textDecoration: "underline", fontWeight: 700 }}>"{p}": …</span>
                              <span style={{ color: "#84E1BC" }}>  ← 추가 필요</span>
                            </div>
                          ))}
                        </pre>
                      </div>
                    );
                  })()}
                </div>
              </details>
            );
          })}
        </div>
        </div>
      </div>

      {/* ═══ 연결성(@id) — 있을 때만, 간단히 ═══ */}
      {(axis3.checks || []).length > 0 && (
        <Accordion title={`Schema 연결성(@id) — ${axis3.id_pct ?? "—"}%${axis3.gate === 0 ? " · 🔴 연결 끊김" : ""}`}>
          {(axis3.checks || []).map((ck: any, i: number) => (
            <div key={i} style={{ borderTop: "1px solid var(--line)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 0" }}>
                <span>{ck.item.replace(" ★게이트", "")}</span>
                <span style={{ color: "var(--sec)" }}>{ck.score === null ? "해당없음" : `${Math.round(ck.score * 100)}%`} · {ck.detail}</span>
              </div>
              {/* [2026-07 과제4] @id 부여율이 100% 미만일 때, 어떤 노드(@type·이름·URL)에 @id가
                  누락됐는지 프론트 대시보드에서 바로 확인할 수 있게 목록으로 표시한다. */}
              {Array.isArray(ck.missing_ids) && ck.missing_ids.length > 0 && (
                <div style={{ margin: "2px 0 6px", padding: "6px 8px", background: "#FEF3F2", border: "1px solid #FECDCA", borderRadius: 6 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#B42318", marginBottom: 3 }}>@id 누락 노드 {ck.missing_ids.length}건</div>
                  {ck.missing_ids.map((m: any, j: number) => (
                    <div key={j} style={{ fontSize: 11, color: "#7A271A", lineHeight: 1.5 }}>
                      • <b>{m.type || "(unknown)"}</b>{m.name ? ` — ${m.name}` : ""}
                      {m.hint ? <span style={{ color: "#98A2B3", fontFamily: "monospace", marginLeft: 4, wordBreak: "break-all" }}>{m.hint}</span> : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </Accordion>
      )}
    </div>
  );
}

function OverallBanner({ hq, row }: { hq: any; row?: any }) {
  const l1 = hq.level1_apply_rate || {};
  const perType: Record<string, any> = hq.level2?.per_type || {};
  const overall = hq.overall || {};
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <span style={{ fontSize: 18 }}>{TL_EMOJI[overall.traffic_light] || "⚪"}</span>
      <b style={{ fontSize: 13.5 }}>종합 판단</b>
      {row && (row.product || row.market_product) && <span style={{ fontSize: 10.5, background: "#EEF1F6", color: "#475467", borderRadius: 4, padding: "1px 6px" }}>{row.product || row.market_product}</span>}
      {row && row.page_type && <span style={{ fontSize: 10.5, background: "#E8F0FE", color: "#1B57C4", borderRadius: 4, padding: "1px 6px" }}>{row.page_type}</span>}
      <span style={{ fontSize: 11.5, color: "var(--sec)" }}>
        데이터 유무 {overall.prop_total ? Math.round((overall.prop_ok / overall.prop_total) * 100) : "—"}% ({overall.prop_ok ?? 0}/{overall.prop_total ?? 0}) · 퀄리티 {overall.final_pct ?? "—"}%
      </span>
      <span style={{ marginLeft: "auto", display: "flex", gap: 6, flexWrap: "wrap" }}>
        {Object.entries(perType).map(([t, v]: [string, any]) => (
          <span key={t} style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 9px",
            background: (TL_COLOR[v.traffic_light] || "#98A2B3") + "1A", color: TL_COLOR[v.traffic_light] || "#98A2B3" }}>
            {TL_EMOJI[v.traffic_light]} {t} {v.final_pct ?? "—"}%
          </span>
        ))}
      </span>
    </div>
  );
}

// ctx.results 안의 각 행에 html_qa가 들어있으면(일괄검수/이력 포함 전부 공통) 그걸 그대로 씀.
// 단일검수(1건)면 상세 4개 아코디언을 바로 펼치고, 다건(일괄검수)이면 전체 집계 배너 +
// 사이트별 신호등 리스트(최악 사이트 먼저) → 클릭하면 그 사이트의 4개 아코디언이 펼쳐짐.
export function HtmlQaSummary({ ctx: c }: { ctx: any }) {
  if (c.tab !== "schema") return null;
  const rowsWithQa: any[] = (c.results || []).filter((r: any) => r.html_qa);
  if (rowsWithQa.length === 0) return null;

  if (rowsWithQa.length === 1) {
    const r0 = rowsWithQa[0];
    const hq = r0.html_qa;
    const findings = r0.schema?.findings || [];
    return (
      <div className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
        <OverallBanner hq={hq} row={r0} />
        <HtmlQaDetail hq={hq} findings={findings} />
      </div>
    );
  }

  // 일괄검수 — 집계 + 사이트별 드릴다운
  const finals = rowsWithQa.map((r) => r.html_qa.overall?.final_pct).filter((v: any) => v != null) as number[];
  const avg = finals.length ? Math.round((finals.reduce((a, b) => a + b, 0) / finals.length) * 10) / 10 : null;
  const dist = { green: 0, yellow: 0, red: 0 } as Record<string, number>;
  for (const r of rowsWithQa) dist[r.html_qa.overall?.traffic_light || "red"]++;
  const sorted = [...rowsWithQa].sort((a, b) => (a.html_qa.overall?.final_pct ?? -1) - (b.html_qa.overall?.final_pct ?? -1));
  const propOk = rowsWithQa.reduce((a, r) => a + (r.html_qa.overall?.prop_ok || 0), 0);
  const propTotal = rowsWithQa.reduce((a, r) => a + (r.html_qa.overall?.prop_total || 0), 0);
  const avgApply = propTotal ? Math.round((propOk / propTotal) * 1000) / 10 : null;
  const expanded = c.qaExpandedSite;

  // 권역 > 페이지(제품·타입) 계층으로 그룹핑
  const byRegion: Record<string, any[]> = {};
  for (const r of sorted) (byRegion[r.region || "기타"] ||= []).push(r);
  // 권역 정렬: 평균 낮은(문제 많은) 권역 먼저
  const regionAvg = (rows: any[]) => {
    const v = rows.map((x) => x.html_qa.overall?.final_pct).filter((n: any) => n != null) as number[];
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : -1;
  };
  const regionOrder = Object.keys(byRegion).sort((a, b) => regionAvg(byRegion[a]) - regionAvg(byRegion[b]));

  return (
    <div className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <b style={{ fontSize: 13.5 }}>DATA QA 종합</b>
        <span style={{ fontSize: 11.5, color: "var(--sec)" }}>{rowsWithQa.length}개 사이트 · 데이터 유무 {avgApply ?? "—"}% ({propOk}/{propTotal}) · 퀄리티 {avg ?? "—"}%</span>
        <span style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
          <span style={{ fontSize: 12 }}>🟢 {dist.green}</span>
          <span style={{ fontSize: 12 }}>🟡 {dist.yellow}</span>
          <span style={{ fontSize: 12 }}>🔴 {dist.red}</span>
        </span>
      </div>
      <div style={{ marginTop: 6 }}>
        {regionOrder.map((region) => {
          const pages = byRegion[region];
          const rAvg = regionAvg(pages);
          const rtl = rAvg < 0 ? "red" : rAvg >= 80 ? "green" : rAvg >= 50 ? "yellow" : "red";
          return (
            <div key={region} ref={(el) => { if (c.regionRefs) c.regionRefs.current[region] = el; }} style={{ marginTop: 12 }}>
              {/* 권역 헤더 */}
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 4px", borderBottom: "2px solid var(--line)" }}>
                <span>{TL_EMOJI[rtl] || "⚪"}</span>
                <b style={{ fontSize: 13 }}>{region}</b>
                <span style={{ fontSize: 11, color: "var(--sec)" }}>{pages.length}개 페이지 · 평균 {rAvg < 0 ? "—" : Math.round(rAvg * 10) / 10}%</span>
              </div>
              {/* 그 권역의 페이지들 */}
              {pages.map((r, i) => {
                const hq = r.html_qa; const tl = hq.overall?.traffic_light;
                const key = region + "|" + r.sitecode + "|" + (r.product || r.market_product || "") + "|" + (r.page_type || "") + i;
                const prod = r.product || r.market_product || "";
                return (
                  <div key={key} style={{ borderBottom: "1px solid var(--line)" }}>
                    <div onClick={() => c.setQaExpandedSite(expanded === key ? null : key)}
                      style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 4px 8px 16px", cursor: "pointer", fontSize: 12.5 }}>
                      <span>{TL_EMOJI[tl] || "⚪"}</span>
                      <b style={{ minWidth: 130 }}>{prod || r.sitecode}{r.page_type ? ` · ${r.page_type}` : ""}</b>
                      <span style={{ fontSize: 10.5, color: "var(--sec)" }}>{r.sitecode}</span>
                      <span style={{ marginLeft: "auto" }}>데이터 {hq.overall?.prop_total ? Math.round((hq.overall.prop_ok / hq.overall.prop_total) * 100) : "—"}% · AEO {hq.overall?.final_pct ?? "—"}%</span>
                      <span style={{ fontSize: 11, color: "#0A66E0" }}>{expanded === key ? "▲" : "▼"}</span>
                    </div>
                    {expanded === key && <div className="qbiPopIn" style={{ padding: "0 4px 10px 16px" }}><HtmlQaDetail hq={hq} findings={r.schema?.findings || []} /></div>}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── 전사이트 현황판 [신규] ────────────────────────────────────────
// 최상단. 이력에서 '각 권역의 가장 최근 검수'를 모아 AEO 점수를 평균낸 전사이트 스냅샷.
// 기본은 전체 점수만 한 줄로. '권역별 점수 ▸' 누르면 권역 칩이 펼쳐짐.
export function SiteOverview({ ctx: c }: { ctx: any }) {
  const [open, setOpen] = useState(false);
  if (c.tab !== "schema") return null;
  const ov = c.overview;
  if (!ov || !ov.regions || ov.regions.length === 0) return null;
  const tl = (a: number | null) => (a == null ? "red" : a >= 80 ? "green" : a >= 50 ? "yellow" : "red");
  const total = ov.total_avg_aeo;
  const dist = ov.distribution || { green: 0, yellow: 0, red: 0 };

  return (
    <div className="summaryCard" style={{ marginTop: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "var(--sec)", fontWeight: 700 }}>전사이트 현황</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 16 }}>{TL_EMOJI[tl(ov.total_apply_pct)] || "⚪"}</span>
          <span style={{ fontSize: 11.5, color: "var(--sec)" }}>데이터 유무</span>
          <b style={{ fontSize: 20, color: TL_COLOR[tl(ov.total_apply_pct)] }}>{ov.total_apply_pct ?? "—"}%</b>
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 16 }}>{TL_EMOJI[tl(total)] || "⚪"}</span>
          <span style={{ fontSize: 11.5, color: "var(--sec)" }}>AEO 퀄리티</span>
          <b style={{ fontSize: 20, color: TL_COLOR[tl(total)] }}>{total ?? "—"}%</b>
        </span>
        <span style={{ fontSize: 12, color: "var(--sec)" }}>🟢 {dist.green} · 🟡 {dist.yellow} · 🔴 {dist.red}</span>
        <button onClick={() => setOpen((v) => !v)}
          style={{ marginLeft: "auto", background: "none", border: "1px solid var(--line)", borderRadius: 8, padding: "4px 10px", fontSize: 12, cursor: "pointer", color: "var(--label)" }}>
          권역별 점수 {open ? "▾" : "▸"}
        </button>
      </div>
      {open && (
        <div className="qbiPopIn" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          {ov.regions.map((r: any) => (
            <button key={r.region} title={`${r.at} · 클릭하면 결과로 이동`}
              onClick={() => c.scrollToRegion && c.scrollToRegion(r.region)}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer",
                border: "1px solid var(--line)", borderRadius: 999, padding: "4px 11px", background: "#fff" }}>
              <span style={{ color: "var(--sec)" }}>{r.region}</span>
              <b style={{ color: TL_COLOR[tl(r.avg_aeo)] }}>{r.avg_aeo ?? "—"}</b>
              <span style={{ fontSize: 10.5, color: "#0A66E0" }}>이동 ›</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
