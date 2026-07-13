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
import { useEffect, useRef, useState } from "react";
import { TL_COLOR, TL_EMOJI, tlSpec } from "./qubiShared";

// 클릭하면 뜨는 툴팁 — 브라우저 기본 title은 안 뜨거나 느려서 직접 구현
function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span style={{ position: "relative", display: "inline-block", marginLeft: 6 }}>
      <span onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        style={{ cursor: "pointer", color: "#0A66E0", fontSize: 11, userSelect: "none" }}>ⓘ</span>
      {open && (
        <>
          <span onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 50 }} />
          <span style={{ position: "absolute", left: 0, top: "130%", zIndex: 51, width: 240, whiteSpace: "pre-line",
            background: "#101318", color: "#fff", fontSize: 11, lineHeight: 1.55, borderRadius: 8, padding: "8px 10px",
            boxShadow: "0 6px 18px rgba(0,0,0,.25)", fontWeight: 400 }}>{text}</span>
        </>
      )}
    </span>
  );
}

// 단어 단위 diff (Data QA MiniDiff와 동일 스타일) — 현재값(빨간 취소선) → 기준값(초록 밑줄)
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

const C = { crit: "#D8362F", warn: "#E0A008", pass: "#1F9E5C", na: "#98A2B3", blue: "#1B57C4" };
const scoreColor = (s: number | null) => (s == null ? C.na : s < 50 ? C.crit : s < 80 ? C.warn : C.pass);

function Meter({ pct }: { pct: number | null }) {
  const v = pct == null ? 0 : pct;
  const color = scoreColor(pct);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, minWidth: 130 }}>
      <span style={{ flex: 1, height: 6, background: "#EEF1F6", borderRadius: 999, minWidth: 70 }}>
        <span style={{ display: "block", width: `${v}%`, height: "100%", background: color, borderRadius: 999 }} />
      </span>
      <b style={{ fontSize: 12.5, color }}>{pct == null ? "—" : `${pct}%`}</b>
    </span>
  );
}

/* ── Rule Trace: "판정 과정 보기" — Browser→Attribute→Dictionary→Rule→Exception→Result ── */
function RuleTrace({ trace }: { trace: any[] }) {
  const [open, setOpen] = useState(false);
  if (!trace?.length) return null;
  return (
    <div style={{ marginTop: 6 }}>
      <button onClick={() => setOpen(!open)} style={{ background: "none", border: "none", padding: 0, fontSize: 11, color: "#0A66E0", cursor: "pointer" }}>
        {open ? "▲ 판정 과정 접기" : "▼ 판정 과정 보기"}
      </button>
      {open && (
        <div style={{ marginTop: 6, background: "#0F172A", borderRadius: 8, padding: "8px 12px" }}>
          {trace.map((t, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "104px 1fr", fontSize: 11, lineHeight: 1.8, color: "#E2E8F0" }}>
              <span style={{ color: "#7DD3FC" }}>{t.step}</span>
              <span style={{ wordBreak: "break-all" }}>{t.detail}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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

/* ── Dictionary Review 승인 행: 제품 단위로 집계된 그룹(빈도순) 1건 ──
   기존 CandidateCard(페이지별·1건씩)를 대체 — "GPU (15)"처럼 이미 여러 페이지에서
   반복 발견되고 Confidence 기준을 통과한 것만 여기 도달한다(백엔드 spec_dict_review.py). */
function GroupedCandidateRow({ cand, attributes, product, api, flash, onDone }:
  { cand: any; attributes: string[]; product: string; api: (p: string) => string; flash: (m: string) => void; onDone: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [rep, setRep] = useState("");
  const [productOnly, setProductOnly] = useState(false); // [2026-07] 기본은 전체 공통(Global) — 체크하면 이 제품에만 적용
  const [busy, setBusy] = useState(false);
  const [ai, setAi] = useState<any>(null);
  useEffect(() => {  // 펼쳤을 때만 AI 제안 조회(그룹이 많을 수 있어 지연 로드)
    if (!expanded || ai !== null) return;
    let alive = true;
    (async () => {
      try {
        const r = await fetch(api("/api/qb/spec-rules/dictionary/suggest"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product, alias: cand.alias }),
        });
        if (alive && r.ok) setAi(await r.json());
      } catch { /* 조용히 무시 */ }
    })();
    return () => { alive = false; };
  }, [expanded, cand.alias, product]);
  useEffect(() => {  // High confidence는 펼치기 전에도 추천값을 미리 채워둔다(요구사항 4)
    if (cand.recommend_canonical && attributes.includes(cand.alias)) setRep(cand.alias);
  }, [cand.alias, cand.recommend_canonical]);
  const add = async () => {
    if (!rep) { flash("어느 항목의 표현인지 선택하세요"); return; }
    setBusy(true);
    try {
      const r = await fetch(api("/api/qb/spec-rules/dictionary/add"), { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product, representative: rep, alias: cand.alias, scope: productOnly ? "product" : "global" }) });
      if (!r.ok) throw new Error(String(r.status));
      flash(`Dictionary 추가됨(${productOnly ? "이 제품 전용" : "전체 공통"}): ${cand.alias} → ${rep}`); onDone();
    } catch { flash("추가 실패 — 서버 확인"); } finally { setBusy(false); }
  };
  const confBadge = cand.confidence === "high"
    ? { bg: "#EAF7EE", fg: "#067647", label: "High" }
    : { bg: "#FFFAEB", fg: "#93540A", label: "Medium" };
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 10, marginTop: 6, overflow: "hidden" }}>
      <div onClick={() => setExpanded((v) => !v)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 11px", cursor: "pointer", background: "#FAFBFC" }}>
        <span style={{ fontFamily: "monospace", background: "#F2F4F7", padding: "1px 7px", borderRadius: 5, fontSize: 12.5, fontWeight: 700 }}>{cand.alias}</span>
        <span style={{ fontSize: 11.5, color: "var(--sec)" }}>({cand.count}개 페이지 반복)</span>
        <span style={{ fontSize: 10.5, fontWeight: 700, background: confBadge.bg, color: confBadge.fg, borderRadius: 5, padding: "1px 6px" }}>{confBadge.label}</span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#0A66E0" }}>{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && (
        <div style={{ padding: "9px 11px", borderTop: "1px solid var(--line)" }}>
          <div style={{ fontSize: 11, color: "var(--sec)", marginBottom: 6 }}>발견 위치: {cand.sections?.join(", ") || "spec"}</div>
          {/* AI 제안 줄 — 판정이 아니라 참고용 제안. 최종 승인은 사람이 아래 버튼으로.
              Confidence: High만 자동 추천 채움, Medium은 선택 가능하되 자동 채우지 않음, Low는 애초에 여기 도달하지 않음(요구사항 4). */}
          <div style={{ fontSize: 11.5, background: "#fff", border: "1px dashed #D6BB6A", borderRadius: 7, padding: "5px 9px" }}>
            {ai == null && <span style={{ color: "var(--sec)" }}>✨ AI 제안 확인 중…</span>}
            {ai && ai.available && ai.attribute && (
              <span>✨ <b>AI 제안</b>: 이 표현은 <b style={{ color: "#0A66E0" }}>{ai.attribute}</b>{ai.confidence != null ? ` (신뢰도 ${ai.confidence}%)` : ""}
                <button onClick={() => setRep(ai.attribute)} style={{ marginLeft: 8, fontSize: 11, padding: "2px 8px", borderRadius: 6, border: "1px solid #0A66E0", background: "#fff", color: "#0A66E0", cursor: "pointer" }}>제안 적용</button>
                {ai.reason && <span style={{ display: "block", color: "var(--sec)", fontSize: 10.5, marginTop: 2 }}>{ai.reason}</span>}
              </span>
            )}
            {ai && ai.available && !ai.attribute && <span style={{ color: "var(--sec)" }}>✨ AI가 마땅한 항목을 못 찾았어요 — 직접 선택해주세요.</span>}
            {ai && !ai.available && <span style={{ color: "#98A2B3", fontStyle: "italic" }}>✨ AI 번역 제안 — 준비 중 (API 키 연결 시 활성화)</span>}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 7, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11.5, color: "var(--sec)" }}>예상 Canonical</span>
            <select value={rep} onChange={(e) => setRep(e.target.value)} style={{ fontSize: 12, padding: "4px 8px", borderRadius: 7, border: "1px solid var(--line)" }}>
              <option value="">— 항목 선택 —</option>
              {attributes.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            <button onClick={add} disabled={busy} style={{ fontSize: 11.5, fontWeight: 700, padding: "5px 10px", borderRadius: 7, border: "none", background: "#0A66E0", color: "#fff", cursor: "pointer" }}>Dictionary 추가</button>
            <button onClick={onDone} style={{ fontSize: 11.5, padding: "5px 10px", borderRadius: 7, border: "1px solid var(--line)", background: "#fff", cursor: "pointer" }}>무시</button>
            <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10.5, color: "var(--sec)", marginLeft: "auto", cursor: "pointer" }}>
              <input type="checkbox" checked={productOnly} onChange={(e) => setProductOnly(e.target.checked)} />
              이 제품({product})에만 적용
            </label>
          </div>
          <div style={{ fontSize: 10, color: "#98A2B3", marginTop: 4 }}>
            기본은 <b>전체 제품 공통</b>으로 저장돼요 — Weight·Storage처럼 신모델이 나와도 번역이 재사용되는 표현이 대부분이라서요.
            이번 세대에만 있는 고유 기능명 등은 위 체크박스로 이 제품에만 한정할 수 있어요.
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Dictionary Review 섹션 — 제품당 1회, 기본 접힘.
   요구사항 5: 동일 표현을 카드 여러 개로 흩뿌리지 않고 빈도순 그룹으로 표시.
   요구사항 1: Critical/Warning/Pass 아래, 항상 맨 마지막에만 노출(보조 기능). ──*/
export function DictionaryReviewSection({ results, product, api, flash }:
  { results: any[]; product: string; api: (p: string) => string; flash: (m: string) => void }) {
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState<string[]>([]);
  const [attributes, setAttributes] = useState<string[]>([]);

  useEffect(() => {  // 항목 선택 드롭다운용 — Rule DB의 attribute 목록만 가볍게 조회
    let alive = true;
    (async () => {
      try {
        const d = await (await fetch(api(`/api/qb/spec-rules?product=${encodeURIComponent(product)}`))).json();
        if (alive) setAttributes((d.rules || []).map((r: any) => r.attribute));
      } catch { if (alive) setAttributes([]); }
    })();
    return () => { alive = false; };
  }, [product]);

  // 이번 실행 결과 중 이 product의 spec_v2.dictionary_review는 어느 페이지나 동일(제품 단위
  // 집계 결과가 그대로 복사되어 있음) — 첫 번째 것만 사용
  const withSv = results.find((r: any) => r.spec_v2?.dictionary_review);
  const all: any[] = withSv?.spec_v2?.dictionary_review || [];
  const cands = all.filter((c) => !dismissed.includes(c.alias));
  if (!all.length) return null;

  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden", marginTop: 16 }}>
      <div onClick={() => setOpen(!open)} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", cursor: "pointer", background: "#FAFBFC" }}>
        <span style={{ fontSize: 15 }}>📖</span>
        <b style={{ fontSize: 13 }}>Dictionary Review</b>
        <span style={{ fontSize: 11.5, color: "var(--sec)" }}>사전 미등록 표현 {cands.length}건 — 보조 기능, Spec 오류가 아닙니다</span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#0A66E0" }}>{open ? "▲ 접기" : "▼ 펼치기"}</span>
      </div>
      {open && (
        <div style={{ padding: "4px 14px 12px", borderTop: "1px solid var(--line)" }}>
          <div style={{ fontSize: 11, color: "var(--sec)", margin: "8px 0" }}>
            이번 실행에서 <b>{product}</b>의 여러 페이지에 반복 등장했고 신뢰도(Confidence)가 낮지 않은 표현만 모았습니다.
            1회성으로만 발견됐거나 신뢰도가 낮은 표현은 자동으로 제외되었습니다.
          </div>
          {cands.map((c, i) => (
            <GroupedCandidateRow key={c.alias + i} cand={c} attributes={attributes} product={product} api={api} flash={flash}
              onDone={() => setDismissed((d) => [...d, c.alias])} />
          ))}
          {cands.length === 0 && <div style={{ fontSize: 12, color: "var(--sec)" }}>처리할 항목이 없어요.</div>}
        </div>
      )}
    </div>
  );
}

/* ── Canonical Dictionary 관리 (기본 접힘) ── */
export function DictionaryPanel({ product, api }: { product: string; api: (p: string) => string }) {
  const [openPanel, setOpenPanel] = useState(false);   // 패널 자체 열림
  const [data, setData] = useState<any>(null);
  const [q, setQ] = useState("");                       // 검색어
  const [openRows, setOpenRows] = useState<Set<string>>(new Set()); // 항목별 펼침

  useEffect(() => {  // 제품 바뀌면 다시 로드(패널 닫혀 있어도 미리 준비)
    let alive = true;
    (async () => {
      try { const d = await (await fetch(api(`/api/qb/spec-rules?product=${encodeURIComponent(product)}`))).json(); if (alive) setData(d); }
      catch { if (alive) setData({ dictionary: {}, rules: [] }); }
    })();
    return () => { alive = false; };
  }, [product]);

  const dict: Record<string, string[]> = data?.dictionary || {};
  const entries = Object.entries(dict);
  const ql = q.trim().toLowerCase();
  const filtered = ql
    ? entries.filter(([rep, al]) => rep.toLowerCase().includes(ql) || (al as string[]).some((a) => a.toLowerCase().includes(ql)))
    : entries;
  const totalAlias = entries.reduce((n, [, al]) => n + (al as string[]).length, 0);

  const toggleRow = (rep: string) => setOpenRows((s) => { const n = new Set(s); n.has(rep) ? n.delete(rep) : n.add(rep); return n; });

  if (!openPanel) {
    return (
      <button onClick={() => setOpenPanel(true)}
        style={{ position: "fixed", left: 20, bottom: 20, zIndex: 40, background: "#fff", color: "#101318",
          border: "1px solid var(--line)", borderRadius: 999, padding: "10px 16px", fontWeight: 700, fontSize: 12.5,
          cursor: "pointer", boxShadow: "0 6px 20px rgba(0,0,0,.14)" }}>
        📖 Dictionary{entries.length ? ` · ${entries.length}` : ""}
      </button>
    );
  }
  return (
    <div style={{ position: "fixed", left: 20, bottom: 20, zIndex: 40, width: 380, maxHeight: "72vh", display: "flex", flexDirection: "column",
      background: "#fff", border: "1px solid var(--line)", borderRadius: 14, boxShadow: "0 10px 30px rgba(0,0,0,.22)" }}>
      <div style={{ background: "#101318", color: "#fff", padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center", borderRadius: "14px 14px 0 0" }}>
        <b style={{ fontSize: 13 }}>📖 Canonical Dictionary <span style={{ fontWeight: 400, opacity: .75 }}>— {product}</span></b>
        <span role="button" onClick={() => setOpenPanel(false)} style={{ cursor: "pointer" }}>✕</span>
      </div>
      <div style={{ padding: "10px 14px 4px" }}>
        <div style={{ fontSize: 11, color: "var(--sec)", marginBottom: 6 }}>항목 {entries.length}개 · 표현 {totalAlias}개 — 검수기가 이 표현들을 만나면 해당 항목으로 인식합니다. 값 수정은 Rule DB 엑셀로.</div>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="항목·표현 검색 (예: Battery, 무게, 배터리)"
          style={{ width: "100%", fontSize: 12.5, padding: "7px 10px", border: "1px solid var(--line)", borderRadius: 8, boxSizing: "border-box" }} />
      </div>
      <div style={{ overflow: "auto", padding: "6px 14px 12px" }}>
        {!data && <p style={{ fontSize: 12, color: "var(--sec)" }}>불러오는 중…</p>}
        {data && entries.length === 0 && <p style={{ fontSize: 12, color: "var(--sec)" }}>등록된 표현이 없어요.</p>}
        {filtered.map(([rep, aliases]) => {
          const al = aliases as string[];
          const on = openRows.has(rep) || !!ql;  // 검색 중이면 자동 펼침
          return (
            <div key={rep} style={{ borderTop: "1px solid var(--line)", padding: "6px 0" }}>
              <div onClick={() => toggleRow(rep)} style={{ display: "flex", justifyContent: "space-between", cursor: "pointer", alignItems: "center" }}>
                <b style={{ fontSize: 12.5 }}>{rep}</b>
                <span style={{ fontSize: 11, color: "var(--sec)" }}>{al.length}개 {on ? "▲" : "▼"}</span>
              </div>
              {on && (
                <div style={{ marginTop: 5 }}>
                  {al.map((a) => (
                    <span key={a} style={{ display: "inline-block", background: "#F2F4F7", borderRadius: 5, padding: "1px 7px", margin: "1px 4px 1px 0", fontSize: 11.5 }}>{a}</span>
                  ))}
                  {/* AI 제안 자리 — 키 연결 후 활성화. 지금은 안내만. */}
                  <div style={{ marginTop: 6, fontSize: 10.5, color: "#98A2B3", fontStyle: "italic" }}>
                    ✨ AI 번역 제안 — 준비 중 (연결 시 이 항목의 새 언어 표현을 자동 추천)
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {data && filtered.length === 0 && ql && <p style={{ fontSize: 12, color: "var(--sec)", marginTop: 8 }}>"{q}" 검색 결과 없음</p>}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   V2 기준/점수 패널 — 기존 SpecTable/CriteriaPanel/ScorePanel의 V2 대체판.
   V2 룰셋이 있는 제품(fold7/flip7 등)에서만 렌더되고, 없는 제품은 기존 패널 유지.
   ═══════════════════════════════════════════════════════════════════ */

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
        <b>신호등 (스펙은 더 엄격한 기준)</b> — 🔴 <b>오류 1건 이상이면 빨강</b> · 🟡 오류 0, 확인만 존재 · 🟢 오류·확인 모두 0.
        <span style={{ display: "block", marginTop: 3, fontSize: 11 }}>색·형태는 Data QA와 동일하나, 스펙 값 오류는 소비자 오인·법적 리스크로 이어지므로 Data QA(점수 %기준)와 달리 "오류 1건 = 즉시 빨강"으로 판정합니다. Dictionary Review는 이 신호등에 전혀 영향을 주지 않습니다.</span>
      </div>
    </div>
  );
}
