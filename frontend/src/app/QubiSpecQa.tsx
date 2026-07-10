"use client";
/* QubiSpecQa.tsx — Spec QA [V2] 렌더 블록 (Rule 기반 Spec Validation 결과 화면)
   QA 담당자가 30초 안에 ①어떤 Rule이 실패했는지 ②왜 ③어떻게 고치는지 이해하는 것이 목표.
   Data QA(QubiDataQa) 카드 스타일과 얼라인: 색 헤더 스트립 + 테두리 카드. */
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

/* ── Error Card: 문제/현재/기준/Rule/수정 위치/권장 수정 ── */
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

/* ── Category Card: Validation Score → Critical → PASS 순 ── */
function CategoryCard({ cat, items }: { cat: any; items: any[] }) {
  const [open, setOpen] = useState(cat.fail > 0); // 오류 있는 카테고리는 기본 펼침
  const fails = items.filter((i) => i.status === "fail");
  const passes = items.filter((i) => i.status === "pass");
  const nas = items.filter((i) => i.status === "na");
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden" }}>
      <div onClick={() => setOpen(!open)} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 13px", cursor: "pointer", background: cat.fail > 0 ? "#FFF5F4" : "#FAFBFC" }}>
        <b style={{ fontSize: 13 }}>{cat.category}</b>
        <Meter pct={cat.score} />
        <span style={{ fontSize: 11.5, color: "var(--sec)" }}>Rule Pass <b style={{ color: cat.fail ? C.crit : C.pass }}>{cat.pass} / {cat.pass + cat.fail}</b>{cat.na ? ` · N/A ${cat.na}` : ""}</span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#0A66E0" }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ padding: "4px 13px 12px", borderTop: "1px solid var(--line)" }}>
          {fails.map((it, i) => <ErrorCard key={i} it={it} />)}
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
          {nas.length > 0 && (
            <div style={{ marginTop: 6, fontSize: 11.5, color: C.na }}>
              ⚪ N/A: {nas.map((i) => i.attribute).join(", ")}
            </div>
          )}
          {passes.length > 0 && fails.length === 0 && <RuleTrace trace={passes[0].trace} />}
        </div>
      )}
    </div>
  );
}

/* ── Candidate: 새로운 표현 발견 → 사용자 승인으로만 Dictionary 반영 ── */
function CandidateCard({ cand, attributes, product, api, flash, onDone }:
  { cand: any; attributes: string[]; product: string; api: (p: string) => string; flash: (m: string) => void; onDone: () => void }) {
  const [rep, setRep] = useState(cand.representative || "");
  const [busy, setBusy] = useState(false);
  const [ai, setAi] = useState<any>(null);  // AI 제안 결과 {available, attribute, confidence, reason}
  useEffect(() => {  // 후보가 뜨면 AI 제안 자동 조회 (키 없으면 available:false로 폴백)
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
  }, [cand.alias, product]);
  const add = async () => {
    if (!rep) { flash("어느 항목의 표현인지 선택하세요"); return; }
    setBusy(true);
    try {
      const r = await fetch(api("/api/qb/spec-rules/dictionary/add"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product, representative: rep, alias: cand.alias }) });
      if (!r.ok) throw new Error(String(r.status));
      flash(`Dictionary 추가됨: ${cand.alias} → ${rep}`); onDone();
    } catch { flash("추가 실패 — 서버 확인"); } finally { setBusy(false); }
  };
  return (
    <div style={{ background: "#FFFAEB", border: "1px solid #FEDF89", borderRadius: 10, padding: "9px 12px", marginTop: 8 }}>
      <div style={{ fontSize: 12.5 }}>🟡 <b>새로운 표현 발견</b> — <span style={{ fontFamily: "monospace", background: "#fff", padding: "1px 6px", borderRadius: 5 }}>{cand.alias}</span>
        <span style={{ color: "var(--sec)", fontSize: 11.5, marginLeft: 6 }}>딕셔너리 미등록 · 번역/표기 재확인 필요</span>
      </div>
      {/* AI 제안 줄 — 판정이 아니라 참고용 제안. 최종 승인은 사람이 아래 버튼으로. */}
      <div style={{ marginTop: 6, fontSize: 11.5, background: "#fff", border: "1px dashed #D6BB6A", borderRadius: 7, padding: "5px 9px" }}>
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
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 7 }}>
        <span style={{ fontSize: 11.5, color: "var(--sec)" }}>예상 Canonical</span>
        <select value={rep} onChange={(e) => setRep(e.target.value)} style={{ fontSize: 12, padding: "4px 8px", borderRadius: 7, border: "1px solid var(--line)" }}>
          <option value="">— 항목 선택 —</option>
          {attributes.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <button onClick={add} disabled={busy} style={{ fontSize: 11.5, fontWeight: 700, padding: "5px 10px", borderRadius: 7, border: "none", background: "#0A66E0", color: "#fff", cursor: "pointer" }}>Dictionary 추가</button>
        <button onClick={onDone} style={{ fontSize: 11.5, padding: "5px 10px", borderRadius: 7, border: "1px solid var(--line)", background: "#fff", cursor: "pointer" }}>무시</button>
      </div>
    </div>
  );
}

/* ── 사이트 1건의 Spec QA V2 패널 ── */
export function SpecV2Panel({ row, product, api, flash }:
  { row: any; product: string; api: (p: string) => string; flash: (m: string) => void }) {
  const [dismissed, setDismissed] = useState<string[]>([]);
  const sv = row.spec_v2;
  if (!sv) return null;
  const s = sv.summary || {};
  const attributes: string[] = Array.from(new Set((sv.items || []).map((i: any) => i.attribute)));
  const cands = (sv.candidates || []).filter((c: any) => !dismissed.includes(c.alias));
  const byCat: Record<string, any[]> = {};
  for (const it of sv.items || []) (byCat[it.category] ||= []).push(it);
  return (
    <div style={{ border: "1px solid #D7E3F8", borderRadius: 12, overflow: "hidden", marginTop: 14 }}>
      {/* 종합 배너 — 신호등은 Data QA와 동일 이모지, 판정은 스펙 규칙(오류 1건이라도 🔴) */}
      <div style={{ background: "#EEF4FE", padding: "9px 14px", borderLeft: `3px solid ${C.blue}`, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 17 }}>{TL_EMOJI[tlSpec(s.critical ?? 0, s.warning ?? 0)]}</span>
        <b style={{ fontSize: 12.5, color: C.blue }}>Spec Validation {row.sitecode ? `— ${row.sitecode}` : ""}</b>
        <Meter pct={s.score} />
        <span style={{ fontSize: 12 }}>
          <b style={{ color: C.crit }}>🔴 오류 {s.critical ?? 0}</b>
          <span style={{ margin: "0 6px", color: C.warn, fontWeight: 700 }}>🟡 확인 {s.warning ?? 0}</span>
          <span style={{ color: C.pass, fontWeight: 700 }}>✅ 정상 {s.pass ?? 0}</span>
          <span style={{ marginLeft: 6, color: C.na }}>⚪ 해당없음 {s.na ?? 0}</span>
        </span>
      </div>
      {s.coverage_low && (
        <div style={{ background: "#FFFAEB", padding: "7px 14px", fontSize: 12, color: "#93540A", borderBottom: "1px solid #FEDF89" }}>
          ⚠️ 적용 대상 룰의 절반 이상을 페이지에서 찾지 못했어요 — 이 언어의 표현이 Dictionary에 없거나 페이지 구조가 달라 수집이 안 됐을 수 있습니다. 아래 "새로운 표현"을 승인해 Dictionary를 보강하세요.
        </div>
      )}
      <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
        {/* 새로운 표현(Warning) — 승인 흐름 */}
        {cands.map((c: any, i: number) => (
          <CandidateCard key={c.alias + i} cand={c} attributes={attributes} product={product} api={api} flash={flash}
            onDone={() => setDismissed((d) => [...d, c.alias])} />
        ))}
        {/* Category Cards */}
        {(sv.categories || []).map((cat: any) => (
          <CategoryCard key={cat.category} cat={cat} items={byCat[cat.category] || []} />
        ))}
      </div>
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
  exact: { label: "완전일치", desc: "정규화 후 문자열이 같아야 함 (해상도·IP48·카메라 조합)" },
  numeric_exact: { label: "숫자일치", desc: "표기가 달라도 숫자만 비교 — 4,400 = 4.400 = 4 400 (배터리·무게·크기)" },
  prefix: { label: "접두일치", desc: "앞부분만 일치하면 통과 — SM-F966B/DS의 지역 서픽스 허용" },
  dictionary: { label: "사전", desc: "표기 변형 허용 — Wi-Fi 7 = WiFi 7, 칩셋명 현지화 접미사 허용" },
  option_match: { label: "옵션전부", desc: "나열된 옵션이 모두 있어야 함 — 256/512/1TB 중 하나라도 빠지면 오류" },
  exists: { label: "존재확인", desc: "언급 자체가 검수 대상 — Galaxy AI·구성품·disclaimer 문구" },
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
  const normalText = (r: any) => {
    const v = `${r.expected}${r.unit ? ` ${r.unit}` : ""}`;
    if (r.validation === "option_match") return `${v} (이 값들이 옵션으로 노출)`;
    if (r.validation === "exists") return `"${v}" 언급이 있어야`;
    if (r.validation === "numeric_exact") return `${v} (표기 달라도 숫자 일치면 OK)`;
    if (r.validation === "dictionary") return `${v} (표기 변형·현지화 허용)`;
    return `정확히 "${v}"`;
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
          스펙 노출 영역(스펙표·각주·구성품 등)에서 <b>정답지 항목의 존재 여부와 값 일치</b>를 확인합니다.
          "4,400"과 "4 400"처럼 국가별 표기 차이는 <b>동일 값으로 인정</b>하며, 칩셋명 등 현지화 표기는 사전(Dictionary)으로 매핑합니다.
        </div>
      </div>
      <div style={box}>
        <div style={h}>② 판정 등급</div>
        <div style={li}>
          <div>🔴 <b style={{ color: C.crit }}>오류</b> — 값이 정답과 불일치 (예: 무게 216g / 정답 215g). 1건이라도 있으면 해당 페이지는 오류 처리됩니다.</div>
          <div>🟡 <b style={{ color: C.warn }}>확인</b> — 사전 미등록 표현 발견. 오류가 아니라 "미학습 표현"이며, 유효한 표현이면 [Dictionary 추가]로 승인 시 다음 검수부터 정식 판정됩니다.</div>
          <div>⚪ <b style={{ color: C.na }}>해당없음</b> — 해당 페이지타입에 없는 항목이거나 미검출 (미검출 과다 시 커버리지 경고 표시).</div>
        </div>
      </div>
      <div style={box}>
        <div style={h}>③ 오탐 방지 규칙</div>
        <div style={li}>
          · 일반 용량(4400)과 각주 정격 용량(4272)은 <b>별개 항목</b>으로 분리 판정<br />
          · 프로모션 배너의 마케팅 수치는 <b>검사 대상에서 제외</b><br />
          · 국가별 예외 규칙(특정 항목 생략 허용 등)을 사전 반영
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
        <div style={li}><b>정답 일치 항목 ÷ (일치 + 불일치)</b> × 100. <b>"해당없음(⚪)"은 분모에서 제외</b>합니다 — 해당 페이지에 존재하지 않는 항목이 점수를 왜곡하지 않도록 하기 위함입니다.</div>
        <div style={{ ...li, marginTop: 4 }}>예) 31개 중 해당없음 6 · 일치 23 · 불일치 2 → 23 ÷ 25 = <b>92%</b></div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>② 카테고리별 동일 산식</div>
        <div style={li}>배터리·디스플레이 등 카테고리 단위로도 같은 방식으로 계산합니다. 카드의 "Rule Pass 8/8"이 해당 카테고리의 일치/판정 대상 수이며, 불일치가 있는 카테고리는 자동 전개됩니다.</div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>③ "확인(🟡)"은 점수에 미반영</div>
        <div style={li}>🟡은 페이지 오류가 아니라 <b>검수기의 사전 미등록 표현</b>을 의미하므로 점수와 분리해 집계합니다. 유효한 표현은 승인 시 사전에 반영되어 다음 검수부터 정식 판정됩니다.</div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>④ 커버리지 경고 시 점수 해석 주의</div>
        <div style={li}>판정 대상의 <b>절반 이상이 미검출</b>이면 상단에 경고가 표시됩니다. 사전 미등록 또는 페이지 구조 차이로 수집되지 않았을 수 있으며, 이 경우 높은 점수는 "전부 통과"가 아니라 "검출 자체가 적음"을 의미할 수 있으므로 미등록 표현 승인이 선행되어야 합니다.</div>
      </div>
      <div style={{ fontSize: 12, color: "var(--sec)", marginTop: 8, background: "#FFF5F4", border: "1px solid #FECDCA", borderRadius: 8, padding: "8px 10px" }}>
        <b>신호등 (스펙은 더 엄격한 기준)</b> — 🔴 <b>오류 1건 이상이면 빨강</b> · 🟡 오류 0, 확인만 존재 · 🟢 오류·확인 모두 0.
        <span style={{ display: "block", marginTop: 3, fontSize: 11 }}>색·형태는 Data QA와 동일하나, 스펙 값 오류는 소비자 오인·법적 리스크로 이어지므로 Data QA(점수 %기준)와 달리 "오류 1건 = 즉시 빨강"으로 판정합니다.</span>
      </div>
    </div>
  );
}
