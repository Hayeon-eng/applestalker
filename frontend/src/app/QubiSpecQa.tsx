"use client";
/* QubiSpecQa.tsx — Spec QA [V2] 렌더 블록 (Rule 기반 Spec Validation 결과 화면)
   QA 담당자가 30초 안에 ①어떤 Rule이 실패했는지 ②왜 ③어떻게 고치는지 이해하는 것이 목표.
   Data QA(QubiDataQa) 카드 스타일과 얼라인: 색 헤더 스트립 + 테두리 카드.

   [2026-07 리팩토링 — QA 우선순위 재정렬]
   기존에는 Dictionary Missing(미등록 표현)이 "Warning"으로 실제 Spec 오류와 같은 자리에
   노출되어, 운영자가 진짜 오류를 찾기 전에 대량의 사전 미등록 카드를 먼저 봐야 했다.
   이제 우선순위는 다음과 같이 고정된다:
     🔴 Critical Error(fail) > 🟡 Warning(warn — 추출 신뢰도 낮아 재확인 필요) >
     ✅ Pass > (완전히 분리된, 기본 접힘) Dictionary Review
   Dictionary Review는 페이지 1건이 아니라 "제품 전체 실행" 단위로 집계되어(백엔드
   spec_dict_review.py) 빈도순으로 그룹 표시된다 — QubiApp.tsx에서 1회만 렌더한다. */
import { useState } from "react";
import { TL_COLOR, TL_EMOJI, tlSpec } from "./qubiShared";

import { C, MiniDiff, Meter, RuleTrace } from "./specQaShared";
// [2026-07 분할] 46KB 제한 대응 3분할 — 기존 import 경로("./QubiSpecQa")를 깨지 않도록
// 사전·기준표 컴포넌트는 여기서 그대로 re-export한다.
export { DictionaryReviewSection, DictionaryPanel } from "./QubiSpecDict";
export { SpecV2RuleTable, SpecV2Criteria, SpecV2Score } from "./QubiSpecRules";

/* ── Error Card(Critical): 문제/현재/기준/Rule/수정 위치/권장 수정 ── */
function ErrorCard({ it }: { it: any }) {
  const foundStr = it.found ? `${it.found}` : "";
  const expStr = `${it.expected}${it.unit ? ` ${it.unit}` : ""}`;
  // 페이지에 있던 라벨(matched_alias)을 맥락으로: "Typical Capacity: 4,900 mAh"
  const label = it.matched_alias || it.attribute;
  return (
    <div style={{ background: "#FEF3F2", border: "1px solid #FECDCA", borderRadius: 10, padding: "11px 13px", marginTop: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 800, color: "#B42318" }}>🔴 {it.attribute}
        <span style={{ marginLeft: 8, fontSize: 10.5, fontWeight: 700, background: "#fff", border: "1px solid #FECDCA", borderRadius: 5, padding: "1px 6px", color: "#B42318" }}>{it.priority}</span>
      </div>
      {/* 주변 카피 맥락 + 단어 단위 diff (빨간 취소선 → 초록 밑줄) */}
      <div style={{ marginTop: 8, fontSize: 13, background: "#fff", border: "1px solid #FEE4E2", borderRadius: 8, padding: "8px 10px" }}>
        <span style={{ color: "var(--sec)", fontSize: 11.5 }}>{label}: </span>
        {foundStr
          ? <MiniDiff expected={expStr} actual={foundStr} />
          : <span><span style={{ textDecoration: "line-through", color: "#B42318", background: "#FDECEA", borderRadius: 3 }}>(페이지에 없음)</span> → <span style={{ textDecoration: "underline", color: "#067647", background: "#EAF7EE", fontWeight: 700, borderRadius: 3 }}>{expStr}</span></span>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "72px 1fr", gap: "3px 10px", fontSize: 11.5, marginTop: 8, color: "var(--sec)" }}>
        {it.fix_guide && <><span>권장 수정</span><b style={{ color: "#067647" }}>{it.fix_guide}</b></>}
        <span>수정 위치</span>
        <span>{it.section ? `${it.page} › ${it.section}` : it.page}</span>
      </div>
      <RuleTrace trace={it.trace} />
    </div>
  );
}

/* ── Warn Card(진짜 Warning): 값은 찾았지만 추출 신뢰도가 낮아 확정 오류로 단정할 수 없는 항목.
   Dictionary Missing과는 무관하다 — "찾긴 했는데 근거가 약해 재확인이 필요하다"는 뜻. ── */
function WarnCard({ it }: { it: any }) {
  const expStr = `${it.expected}${it.unit ? ` ${it.unit}` : ""}`;
  return (
    <div style={{ background: "#FFFAEB", border: "1px solid #FEDF89", borderRadius: 10, padding: "11px 13px", marginTop: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 800, color: "#93540A" }}>🟡 {it.attribute}
        <span style={{ marginLeft: 8, fontSize: 10.5, fontWeight: 700, background: "#fff", border: "1px solid #FEDF89", borderRadius: 5, padding: "1px 6px", color: "#93540A" }}>재확인 필요</span>
      </div>
      <div style={{ marginTop: 6, fontSize: 12, color: "#93540A" }}>
        기준 <b>{expStr}</b> — 페이지에서 <b>{it.found || "(불확실)"}</b> 근처를 찾았지만, 구조화된 스펙 표가 아니라 마케팅 카피 등에서
        추출한 값이라 오류로 단정하지 않았어요. 직접 페이지를 확인해주세요.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "72px 1fr", gap: "3px 10px", fontSize: 11.5, marginTop: 8, color: "var(--sec)" }}>
        <span>확인 위치</span>
        <span>{it.section ? `${it.page} › ${it.section}` : it.page}</span>
      </div>
      <RuleTrace trace={it.trace} />
    </div>
  );
}

/* ── Category Card: Validation Score → Critical → Warning → PASS 순 ── */
function CategoryCard({ cat, items }: { cat: any; items: any[] }) {
  const [open, setOpen] = useState(cat.fail > 0 || cat.warn > 0); // 오류·확인 있는 카테고리는 기본 펼침
  const fails = items.filter((i) => i.status === "fail");
  const warns = items.filter((i) => i.status === "warn");
  const passes = items.filter((i) => i.status === "pass");
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden" }}>
      <div onClick={() => setOpen(!open)} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 13px", cursor: "pointer", background: cat.fail > 0 ? "#FFF5F4" : cat.warn > 0 ? "#FFFCF5" : "#FAFBFC" }}>
        <b style={{ fontSize: 13 }}>{cat.category}</b>
        <Meter pct={cat.score} />
        <span style={{ fontSize: 11.5, color: "var(--sec)" }}>Rule Pass <b style={{ color: cat.fail ? C.crit : C.pass }}>{cat.pass} / {cat.pass + cat.fail}</b>{cat.warn ? ` · 확인 ${cat.warn}` : ""}</span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#0A66E0" }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ padding: "4px 13px 12px", borderTop: "1px solid var(--line)" }}>
          {fails.map((it, i) => <ErrorCard key={i} it={it} />)}
          {warns.map((it, i) => <WarnCard key={i} it={it} />)}
          {passes.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {passes.map((it, i) => (
                <div key={i} style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 12, padding: "3px 0", borderTop: i ? "1px solid var(--line)" : "none" }}>
                  <span style={{ color: C.pass }}>✅</span>
                  <span style={{ minWidth: 170 }}>{it.attribute}</span>
                  <b>{it.found}</b>
                  <span style={{ marginLeft: "auto", fontFamily: "monospace", fontSize: 10.5, color: "var(--sec)" }}>{it.rule_id}</span>
                </div>
              ))}
            </div>
          )}
          {passes.length > 0 && fails.length === 0 && warns.length === 0 && <RuleTrace trace={passes[0].trace} />}
        </div>
      )}
    </div>
  );
}

/* ── [V3.4] 스펙 종합 신호등 — Data QA(OverallBanner)와 얼라인 ──
   같은 TL_COLOR/TL_EMOJI·같은 레이아웃 문법(이모지 + 종합 판단 + 우측 pill 목록)을 쓰되,
   신호등 기준은 스펙 규칙(tlSpec: 오류≥1 🔴 · 확인만 🟡 · 모두 0 🟢)을 따른다.
   여러 사이트 일괄검수면 우측에 사이트별 신호등 pill(나쁜 순 정렬), 단일이면 좌측 요약만. */
export function SpecOverallBanner({ results }: { results: any[] }) {
  const rows = (results || []).filter((r: any) => r.spec_v2);
  if (!rows.length) return null;
  const agg = rows.reduce((a: any, r: any) => {
    const s = r.spec_v2.summary || {};
    a.crit += s.critical || 0; a.warn += s.warning || 0; a.pass += s.pass || 0;
    return a;
  }, { crit: 0, warn: 0, pass: 0 });
  const denom = agg.pass + agg.crit;                       // 확인은 점수 미반영(운영 결정)
  const score = denom ? Math.round((agg.pass / denom) * 1000) / 10 : null;
  const overall = tlSpec(agg.crit, agg.warn);
  const order: Record<string, number> = { red: 0, yellow: 1, green: 2 };
  const sites = rows.map((r: any) => {
    const s = r.spec_v2.summary || {};
    const d = (s.pass || 0) + (s.critical || 0);
    return { code: r.sitecode || r.country || "site", tl: tlSpec(s.critical || 0, s.warning || 0),
             pct: d ? Math.round(((s.pass || 0) / d) * 100) : null };
  }).sort((a: any, b: any) => (order[a.tl] - order[b.tl]) || ((a.pct ?? 101) - (b.pct ?? 101)));
  const MAX = 24;
  return (
    <div className="card" style={{ padding: "10px 14px", marginTop: 14, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", borderLeft: `3px solid ${TL_COLOR[overall]}` }}>
      <span style={{ fontSize: 18 }}>{TL_EMOJI[overall]}</span>
      <b style={{ fontSize: 13.5 }}>종합 판단 — 스펙</b>
      <b style={{ fontSize: 20, color: TL_COLOR[overall] }}>{score ?? "—"}{score != null ? "%" : ""}</b>
      <span style={{ fontSize: 11.5, color: "var(--sec)" }}>
        사이트 {rows.length}곳 · 🔴 오류 {agg.crit} · 🟡 확인 {agg.warn} · ✅ 정상 {agg.pass}
        <span title="점수 = 정상 ÷ (정상+오류). 확인·미노출은 점수에 반영하지 않습니다"> ⓘ</span>
      </span>
      {rows.length > 1 && (
        <span style={{ marginLeft: "auto", display: "flex", gap: 6, flexWrap: "wrap" }}>
          {sites.slice(0, MAX).map((st: any, i: number) => (
            <span key={st.code + i} style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 9px",
              background: (TL_COLOR[st.tl] || "#98A2B3") + "1A", color: TL_COLOR[st.tl] || "#98A2B3" }}>
              {TL_EMOJI[st.tl]} {st.code}{st.pct != null ? ` ${st.pct}%` : ""}
            </span>
          ))}
          {sites.length > MAX && <span style={{ fontSize: 11, color: "var(--sec)" }}>+{sites.length - MAX}</span>}
        </span>
      )}
    </div>
  );
}

/* ── 사이트 1건의 Spec QA V2 패널 ──
   Dictionary(신규 표현)는 이 패널에서 더 이상 렌더하지 않는다 — 페이지 1건이 아니라
   제품 전체 실행 단위로 집계해야 "여러 페이지 반복 발견" 조건을 검증할 수 있기 때문에,
   QubiApp.tsx에서 <DictionaryReviewSection>으로 한 번만(제품당) 렌더한다. */
export function SpecV2Panel({ row, product, api, flash }:
  { row: any; product: string; api: (p: string) => string; flash: (m: string) => void }) {
  const sv = row.spec_v2;
  if (!sv) return null;
  const s = sv.summary || {};
  const byCat: Record<string, any[]> = {};
  for (const it of sv.items || []) (byCat[it.category] ||= []).push(it);
  return (
    <div style={{ border: "1px solid #D7E3F8", borderRadius: 12, overflow: "hidden", marginTop: 14 }}>
      {/* 종합 배너 — 🔴 Critical(fail) > 🟡 Warning(재확인) > ✅ Pass. [V3] 값 없음(na)은 오류가 아니므로 표시하지 않는다 */}
      <div style={{ background: "#EEF4FE", padding: "9px 14px", borderLeft: `3px solid ${C.blue}`, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 17 }}>{TL_EMOJI[tlSpec(s.critical ?? 0, s.warning ?? 0)]}</span>
        <b style={{ fontSize: 12.5, color: C.blue }}>Spec Validation {row.sitecode ? `— ${row.sitecode}` : ""}</b>
        <Meter pct={s.score} />
        <span style={{ fontSize: 12 }}>
          <b style={{ color: C.crit }}>🔴 오류 {s.critical ?? 0}</b>
          <span style={{ margin: "0 6px", color: C.warn, fontWeight: 700 }}>🟡 확인 {s.warning ?? 0}</span>
          <span style={{ color: C.pass, fontWeight: 700 }}>✅ 정상 {s.pass ?? 0}</span>
        </span>
      </div>
      {s.diagnosis && (
        <div style={{ background: "#FFFAEB", padding: "8px 14px", fontSize: 12, color: "#93540A", borderBottom: "1px solid #FEDF89", lineHeight: 1.6 }}>
          ⚠️ <b>이 페이지에서 스펙 값을 하나도 찾지 못했어요</b> (오류 아님 — 판정할 값 자체가 없음)
          <div>추정 원인: {s.diagnosis.hint}</div>
          <div style={{ fontSize: 11, color: "#A57A2B" }}>
            수집 상태 — 렌더링: <b>{s.diagnosis.rendered_by || "?"}</b> · 텍스트 블록 {s.diagnosis.blocks}개(숫자 포함 {s.diagnosis.digit_blocks}개) · 구조 페어 {s.diagnosis.pairs}개.
            {s.diagnosis.rendered_by === "httpx" ? " → JS 렌더링 전 HTML로 보입니다. 렌더링(Playwright) 수집으로 재시도해보세요." : " 값이 스크립트/이미지로만 노출되거나, 비교 대상 미선택 상태의 빈 페이지일 수 있어요."}
          </div>
        </div>
      )}
      <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
        {(sv.categories || []).map((cat: any) => (
          <CategoryCard key={cat.category} cat={cat} items={byCat[cat.category] || []} />
        ))}
      </div>
    </div>
  );
}
