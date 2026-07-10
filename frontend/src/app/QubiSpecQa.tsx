"use client";
/* QubiSpecQa.tsx — Spec QA [V2] 렌더 블록 (Rule 기반 Spec Validation 결과 화면)
   QA 담당자가 30초 안에 ①어떤 Rule이 실패했는지 ②왜 ③어떻게 고치는지 이해하는 것이 목표.
   Data QA(QubiDataQa) 카드 스타일과 얼라인: 색 헤더 스트립 + 테두리 카드. */
import { useState } from "react";

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
  return (
    <div style={{ background: "#FEF3F2", border: "1px solid #FECDCA", borderRadius: 10, padding: "10px 12px", marginTop: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 800, color: "#B42318" }}>❌ {it.attribute}
        <span style={{ marginLeft: 8, fontSize: 10.5, fontWeight: 700, background: "#fff", border: "1px solid #FECDCA", borderRadius: 5, padding: "1px 6px", color: "#B42318" }}>{it.priority}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "84px 1fr", gap: "3px 10px", fontSize: 12.5, marginTop: 6 }}>
        <span style={{ color: "var(--sec)" }}>현재</span>
        <b style={{ color: "#B42318", textDecoration: "line-through" }}>{it.found || "—"}</b>
        <span style={{ color: "var(--sec)" }}>기준</span>
        <b style={{ color: "#067647" }}>{it.expected}{it.unit ? ` ${it.unit}` : ""}</b>
        <span style={{ color: "var(--sec)" }}>Rule</span>
        <span style={{ fontFamily: "monospace", fontSize: 11.5 }}>{it.rule_id} · {it.validation}</span>
        <span style={{ color: "var(--sec)" }}>수정 위치</span>
        <span>{it.section ? `${it.page} > ${it.section}` : it.page}{it.matched_alias ? ` — "${it.matched_alias}"` : ""}</span>
        {it.fix_guide && <><span style={{ color: "var(--sec)" }}>권장 수정</span><b>{it.fix_guide}</b></>}
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
        <span style={{ color: "var(--sec)", fontSize: 11.5, marginLeft: 6 }}>딕셔너리 미등록 · 번역/표기 재확인 필요{cand.confidence != null ? ` · 신뢰도 ${cand.confidence}%` : ""}</span>
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
      {/* 종합 배너 */}
      <div style={{ background: "#EEF4FE", padding: "9px 14px", borderLeft: `3px solid ${C.blue}`, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <b style={{ fontSize: 12.5, color: C.blue }}>Spec Validation {row.sitecode ? `— ${row.sitecode}` : ""}</b>
        <Meter pct={s.score} />
        <span style={{ fontSize: 12 }}>
          <b style={{ color: C.crit }}>🔴 Critical {s.critical ?? 0}</b>
          <span style={{ margin: "0 6px", color: C.warn, fontWeight: 700 }}>🟡 Warning {s.warning ?? 0}</span>
          <span style={{ color: C.pass, fontWeight: 700 }}>✅ PASS {s.pass ?? 0}</span>
          <span style={{ marginLeft: 6, color: C.na }}>⚪ N/A {s.na ?? 0}</span>
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
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<any>(null);
  const toggle = async () => {
    const next = !open; setOpen(next);
    if (next && !data) {
      try { setData(await (await fetch(api(`/api/qb/spec-rules?product=${encodeURIComponent(product)}`))).json()); }
      catch { setData({ dictionary: {}, rules: [] }); }
    }
  };
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden", marginTop: 14 }}>
      <div onClick={toggle} style={{ display: "flex", justifyContent: "space-between", padding: "9px 14px", background: "#F9FAFB", cursor: "pointer", fontSize: 12.5, fontWeight: 700 }}>
        <span>📖 Canonical Dictionary <span style={{ fontWeight: 400, color: "var(--sec)" }}>— Rule에 연결된 다국어 표현</span></span>
        <span style={{ fontSize: 11, color: "#0A66E0" }}>{open ? "▲ 접기" : "▼ 펼치기"}</span>
      </div>
      {open && (
        <div style={{ padding: "8px 14px 12px" }}>
          {!data && <p style={{ fontSize: 12, color: "var(--sec)" }}>불러오는 중…</p>}
          {data && Object.keys(data.dictionary || {}).length === 0 && <p style={{ fontSize: 12, color: "var(--sec)" }}>등록된 Alias가 없어요 — 검수 중 발견되는 "새로운 표현"을 승인하면 여기에 쌓입니다.</p>}
          {data && Object.entries(data.dictionary || {}).map(([rep, aliases]: [string, any]) => (
            <div key={rep} style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 10, fontSize: 12, padding: "5px 0", borderTop: "1px solid var(--line)" }}>
              <b>{rep}</b>
              <span>{(aliases as string[]).map((a) => (
                <span key={a} style={{ display: "inline-block", background: "#F2F4F7", borderRadius: 5, padding: "1px 7px", margin: "1px 4px 1px 0", fontSize: 11.5 }}>{a}</span>
              ))}</span>
            </div>
          ))}
          {data && <div style={{ marginTop: 8, fontSize: 11, color: "var(--sec)" }}>룰 {data.rules?.length ?? 0}개 · 버전 {data.version || "—"} — 기준값 수정은 Rule DB 엑셀 재업로드로 반영됩니다.</div>}
        </div>
      )}
    </div>
  );
}
