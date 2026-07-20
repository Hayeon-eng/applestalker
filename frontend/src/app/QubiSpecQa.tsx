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
import { CompareMatrixPanel } from "./CompareMatrixPanel";

/* Compare 페이지는 PDP 전용 spec_v2가 아니라 compare_v2(제품별 매트릭스 QA)가 실제 판정을
   갖고 있다 — 배너·리스트 신호등이 항상 spec_v2만 보면 Compare 행은 "값 0개"로 잘못 보인다.
   이 헬퍼 하나로 페이지 타입에 맞는 요약을 통일해서 돌려준다(모든 집계 지점이 이걸 공유). */
function _specSummaryOf(r: any): { critical: number; warning: number; pass: number } {
  if (r?.page_type === "Compare" && r?.compare_v2?.summary?.checked) {
    const per = r.compare_v2.summary.per_product || [];
    return per.reduce((a: any, p: any) => {
      a.critical += p.fail || 0; a.warning += p.warn || 0; a.pass += p.pass || 0; return a;
    }, { critical: 0, warning: 0, pass: 0 });
  }
  return r?.spec_v2?.summary || {};
}

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
    const s = _specSummaryOf(r);
    a.crit += s.critical || 0; a.warn += s.warning || 0; a.pass += s.pass || 0;
    return a;
  }, { crit: 0, warn: 0, pass: 0 });
  const denom = agg.pass + agg.crit;                       // 확인은 점수 미반영(운영 결정)
  const score = denom ? Math.round((agg.pass / denom) * 1000) / 10 : null;
  const overall = tlSpec(agg.crit, agg.warn);
  const order: Record<string, number> = { red: 0, yellow: 1, green: 2 };
  const sites = rows.map((r: any) => {
    const s = _specSummaryOf(r);
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
        사이트 {rows.length}곳{rows.length === 1 ? ` (${rows[0].sitecode || rows[0].country || rows[0].url || "미상"}${rows[0].market_product || rows[0].product ? " · " + (rows[0].market_product || rows[0].product) : ""})` : ""} · 🔴 오류 {agg.crit} · 🟡 확인 {agg.warn} · ✅ 정상 {agg.pass}
        <span style={{ display: "block", fontSize: 10.5, color: "#98A2B3" }}>점수 = 정상 ÷ (정상+오류) — 확인·미노출은 반영하지 않아요</span>
      </span>
      {rows.length >= 1 && (
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

/* ── [2026-07 재배치 — DATA QA와 순서·양식 얼라인] ──
   · SpecSiteOverview: 화면 맨 위 — DATA QA의 '전사이트 현황'(SiteOverview)과 같은 문법.
     현재 검수 결과의 종합 점수 + '권역별 점수 ▸' 토글만 보여준다.
   · SpecQaDetails: 화면 아래쪽(HtmlQaSummary 옆) — PDP/Compare → 권역 → 사이트 드릴다운 상세.
   두 컴포넌트는 QubiApp.tsx에서 각각 상단/하단에 렌더된다. */
const PAGE_TYPE_LABEL: Record<string, string> = { PDP: "제품 상세 (PDP)", Compare: "비교 (Compare)" };

const _specScoreOf = (r: any) => {
  const s = _specSummaryOf(r);
  const d = (s.pass || 0) + (s.critical || 0);
  return d ? Math.round(((s.pass || 0) / d) * 100) : null;
};
const _specAggOf = (rs: any[]) => rs.reduce((a, r) => {
  const s = _specSummaryOf(r);
  a.crit += s.critical || 0; a.warn += s.warning || 0; a.pass += s.pass || 0; return a;
}, { crit: 0, warn: 0, pass: 0 });

/* 맨 위 — 스펙 현황(종합 + 권역별 보기). DATA QA SiteOverview와 동일한 summaryCard 스타일. */
export function SpecSiteOverview({ ctx: c }: { ctx: any }) {
  const [open, setOpen] = useState(false);
  if (c.tab !== "copy") return null;
  const rows: any[] = (c.results || []).filter((r: any) => r.spec_v2);
  if (!rows.length) return null;
  const agg = _specAggOf(rows);
  const denom = agg.pass + agg.crit;
  const score = denom ? Math.round((agg.pass / denom) * 1000) / 10 : null;
  const overall = tlSpec(agg.crit, agg.warn);
  // 권역별 집계
  const byRegion: Record<string, any[]> = {};
  for (const r of rows) (byRegion[r.region || "기타"] ||= []).push(r);
  const regions = Object.keys(byRegion).map((rg) => {
    const a = _specAggOf(byRegion[rg]);
    const d = a.pass + a.crit;
    return { region: rg, tl: tlSpec(a.crit, a.warn), score: d ? Math.round((a.pass / d) * 100) : null, crit: a.crit, warn: a.warn };
  }).sort((x, y) => (x.score ?? 101) - (y.score ?? 101));
  return (
    <div className="summaryCard" style={{ marginTop: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "var(--sec)", fontWeight: 700 }}>스펙 현황</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 16 }}>{TL_EMOJI[overall]}</span>
          <span style={{ fontSize: 11.5, color: "var(--sec)" }}>스펙 정확도</span>
          <b style={{ fontSize: 20, color: TL_COLOR[overall] }}>{score ?? "—"}{score != null ? "%" : ""}</b>
        </span>
        <span style={{ fontSize: 12, color: "var(--sec)" }}>사이트 {rows.length}곳 · 🔴 오류 {agg.crit} · 🟡 확인 {agg.warn} · ✅ 정상 {agg.pass}</span>
        <button onClick={() => setOpen((v) => !v)}
          style={{ marginLeft: "auto", background: "none", border: "1px solid var(--line)", borderRadius: 8, padding: "4px 10px", fontSize: 12, cursor: "pointer", color: "var(--label)" }}>
          권역별 점수 {open ? "▾" : "▸"}
        </button>
      </div>
      <div style={{ fontSize: 10.5, color: "#98A2B3", marginTop: 4 }}>점수 = 정상 ÷ (정상+오류) — 확인·미노출은 반영하지 않아요 · 상세 오류·확인 현황은 화면 아래 "스펙 QA 상세"에서</div>
      {open && (
        <div className="qbiPopIn" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          {regions.map((r) => (
            <span key={r.region} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
              border: "1px solid var(--line)", borderRadius: 999, padding: "4px 11px", background: "#fff" }}>
              <span>{TL_EMOJI[r.tl]}</span>
              <span style={{ color: "var(--sec)" }}>{r.region}</span>
              <b style={{ color: TL_COLOR[r.tl] }}>{r.score ?? "—"}{r.score != null ? "%" : ""}</b>
              <span style={{ fontSize: 10.5, color: "var(--sec)" }}>🔴{r.crit}·🟡{r.warn}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* 아래쪽 — 스펙 QA 상세 (PDP/Compare → 권역 → 사이트 드릴다운) */
export function SpecQaDetails({ ctx: c }: { ctx: any }) {
  if (c.tab !== "copy") return null;
  const rows: any[] = (c.results || []).filter((r: any) => r.spec_v2);
  if (!rows.length) return null;

  // 단일 사이트 검수 — 바로 상세만
  if (rows.length === 1) {
    const r0 = rows[0];
    return (
      <div className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
        <SpecOverallBanner results={rows} />
        {r0.page_type !== "Compare" && (
          <SpecV2Panel row={r0} product={r0.market_product || c.product} api={c.api} flash={c.flash} />
        )}
        <CompareMatrixPanel row={r0} />
      </div>
    );
  }

  const scoreOf = (r: any) => {
    const s = _specSummaryOf(r);
    const d = (s.pass || 0) + (s.critical || 0);
    return d ? Math.round(((s.pass || 0) / d) * 100) : null;
  };
  const critWarnOf = (rs: any[]) => rs.reduce((a, r) => {
    const s = _specSummaryOf(r);
    a.crit += s.critical || 0; a.warn += s.warning || 0; return a;
  }, { crit: 0, warn: 0 });

  // ① PDP/Compare 분리 (요청 1) — 등장 순서 고정, 그 외 타입은 뒤에
  const PT_ORDER = ["PDP", "Compare"];
  const byType: Record<string, any[]> = {};
  for (const r of rows) (byType[r.page_type || "기타"] ||= []).push(r);
  const typeKeys = Object.keys(byType).sort((a, b) => {
    const ia = PT_ORDER.indexOf(a), ib = PT_ORDER.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  const expanded = c.qaExpandedSite;

  return (
    <div className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
      <b style={{ fontSize: 13.5 }}>스펙 QA 상세</b>
      <span style={{ fontSize: 11.5, color: "var(--sec)", marginLeft: 8 }}>페이지타입(PDP/Compare) → 권역 → 사이트 순 — 문제 많은 곳부터</span>
      <SpecOverallBanner results={rows} />
      {typeKeys.map((pt) => {
        const ptRows = byType[pt];
        const ptAgg = critWarnOf(ptRows);
        const ptTl = tlSpec(ptAgg.crit, ptAgg.warn);
        // 권역별 그룹 (문제 많은 권역 먼저)
        const byRegion: Record<string, any[]> = {};
        for (const r of ptRows) (byRegion[r.region || "기타"] ||= []).push(r);
        const regionScore = (rs: any[]) => { const v = rs.map(scoreOf).filter((x) => x != null) as number[]; return v.length ? v.reduce((a, b) => a + b, 0) / v.length : -1; };
        const regionOrder = Object.keys(byRegion).sort((a, b) => regionScore(byRegion[a]) - regionScore(byRegion[b]));
        return (
          <div key={pt} style={{ marginTop: 16 }}>
            {/* 페이지 타입 헤더 — 요청1: PDP/Compare를 별개 블록으로 */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 4px", borderBottom: "2px solid var(--line)" }}>
              <span>{TL_EMOJI[ptTl]}</span>
              <b style={{ fontSize: 13, background: "#E8F0FE", color: "#1B57C4", borderRadius: 6, padding: "2px 9px" }}>{PAGE_TYPE_LABEL[pt] || pt}</b>
              <span style={{ fontSize: 11.5, color: "var(--sec)" }}>{ptRows.length}개 페이지 · 🔴 {ptAgg.crit} · 🟡 {ptAgg.warn}</span>
            </div>
            {regionOrder.map((region) => {
              const pages = byRegion[region];
              const rAgg = critWarnOf(pages);
              const rTl = tlSpec(rAgg.crit, rAgg.warn);
              const rScore = regionScore(pages);
              return (
                <div key={region} style={{ marginTop: 10 }}>
                  {/* 권역 헤더 — 요청2: 권역별 점수·신호 노출 */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 4px" }}>
                    <span>{TL_EMOJI[rTl]}</span>
                    <b style={{ fontSize: 12.5 }}>{region}</b>
                    <span style={{ fontSize: 11, color: "var(--sec)" }}>
                      {pages.length}개 · 평균 {rScore < 0 ? "—" : `${Math.round(rScore)}%`} · 🔴 {rAgg.crit} · 🟡 {rAgg.warn}
                    </span>
                  </div>
                  {pages.map((r: any, i: number) => {
                    const s = _specSummaryOf(r);
                    const noRuleset = !!r?.spec_v2?.no_ruleset;
                    const tl = tlSpec(s.critical || 0, s.warning || 0);
                    const key = `spec:${pt}|${region}|${r.sitecode}|${i}`;
                    const prod = r.market_product || r.product || "";
                    return (
                      <div key={key} style={{ borderBottom: "1px solid var(--line)" }}>
                        <div onClick={() => c.setQaExpandedSite(expanded === key ? null : key)}
                          style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 4px 8px 16px", cursor: "pointer", fontSize: 12.5 }}>
                          <span>{noRuleset ? "⚪️" : TL_EMOJI[tl]}</span>
                          <b style={{ minWidth: 130 }}>{prod || r.sitecode}</b>
                          <span style={{ fontSize: 10.5, color: "var(--sec)" }}>{r.sitecode}</span>
                          {noRuleset
                            ? <span style={{ marginLeft: "auto", color: "var(--sec)" }}>기준 없음 — 현재값 참고용</span>
                            : <span style={{ marginLeft: "auto" }}>🔴 오류 {s.critical ?? 0} · 🟡 확인 {s.warning ?? 0} · ✅ 정상 {s.pass ?? 0}</span>}
                          <span style={{ fontSize: 11, color: "#0A66E0" }}>{expanded === key ? "▲" : "▼"}</span>
                        </div>
                        {expanded === key && (
                          <div className="qbiPopIn" style={{ padding: "0 4px 10px 16px" }}>
                            {pt !== "Compare" && (
                              <SpecV2Panel row={r} product={prod || c.product} api={c.api} flash={c.flash} />
                            )}
                            <CompareMatrixPanel row={r} />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        );
      })}
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

  // [2026-07 신규] Rule DB(검수 기준)가 아직 없는 제품 — 판정 대신 실제로 읽힌
  // 라벨:값 쌍만 참고용으로 보여준다. sv.raw_pairs는 runner.check_html()의
  // no_ruleset 폴백에서 온다(백엔드 출력 형태는 spec_engine.run()과 다름).
  if (sv.no_ruleset) {
    const pairs: any[] = sv.raw_pairs || [];
    return (
      <div style={{ border: "1px solid #E4E7EC", borderRadius: 12, overflow: "hidden", marginTop: 14 }}>
        <div style={{ background: "#F9FAFB", padding: "9px 14px", borderLeft: "3px solid #98A2B3" }}>
          <b style={{ fontSize: 12.5, color: "var(--label)" }}>현재값 {row.sitecode ? `— ${row.sitecode}` : ""}</b>
          <span style={{ fontSize: 11.5, color: "var(--sec)", marginLeft: 8 }}>
            검수 기준(Rule DB) 없음 — 판정 없이 페이지에서 읽힌 값만 참고용으로 표시 ({s.raw_count ?? pairs.length}개)
          </span>
        </div>
        {pairs.length === 0 ? (
          <div style={{ padding: "10px 14px", fontSize: 12, color: "var(--sec)" }}>이 페이지에서 라벨:값 형태의 스펙을 찾지 못했어요.</div>
        ) : (
          <div style={{ padding: "8px 14px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 14px" }}>
            {pairs.map((p: any, i: number) => (
              <div key={i} style={{ fontSize: 12, display: "contents" }}>
                <span style={{ color: "var(--sec)" }}>{p.label}</span>
                <span style={{ fontWeight: 600 }}>{p.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

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
