"use client";
/* QubiSpecQa.tsx — Spec QA [V2] 렌더 블록 (Rule 기반 Spec Validation 결과 화면)
   QA 담당자가 30초 안에 ①어떤 Rule이 실패했는지 ②왜 ③어떻게 고치는지 이해하는 것이 목표.
   Data QA(QubiDataQa) 카드 스타일과 얼라인: 색 헤더 스트립 + 테두리 카드. */
import { useEffect, useRef, useState } from "react";

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
      <p style={{ fontSize: 11.5, color: "var(--sec)", margin: "6px 0 8px" }}>
        기준값은 이 Rule DB(엑셀)가 원본입니다 — 값 수정은 엑셀 편집 → 업로드로 반영하세요. 화면에서 직접 편집하지 않습니다(변경 이력·검토를 엑셀로 일원화).
      </p>
      <div style={{ maxHeight: 340, overflow: "auto", border: "1px solid var(--line)", borderRadius: 10 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead><tr style={{ color: "var(--sec)", fontSize: 11, textAlign: "left", position: "sticky", top: 0, background: "#F9FAFB" }}>
            <th style={{ padding: "6px 8px" }}>분류</th><th style={{ padding: "6px 8px" }}>항목</th>
            <th style={{ padding: "6px 8px" }}>기준값</th><th style={{ padding: "6px 8px" }}>검사</th>
            <th style={{ padding: "6px 8px" }}>등급</th><th style={{ padding: "6px 8px" }}>위치</th></tr></thead>
          <tbody>
            {rules.map((r: any) => (
              <tr key={r.rule_id}>
                <td style={{ padding: "5px 8px", borderTop: "1px solid var(--line)", color: "var(--sec)" }}>{r.category}</td>
                <td style={{ padding: "5px 8px", borderTop: "1px solid var(--line)" }}>{r.attribute}</td>
                <td style={{ padding: "5px 8px", borderTop: "1px solid var(--line)", fontWeight: 700 }}>{r.expected}{r.unit ? ` ${r.unit}` : ""}</td>
                <td style={{ padding: "5px 8px", borderTop: "1px solid var(--line)" }} title={VAL_KO[r.validation]?.desc || r.validation}>
                  <span style={{ background: "#F2F4F7", borderRadius: 5, padding: "1px 6px", fontSize: 11 }}>{VAL_KO[r.validation]?.label || r.validation}</span></td>
                <td style={{ padding: "5px 8px", borderTop: "1px solid var(--line)" }}>
                  <b style={{ color: PRI_COLOR[r.priority] || "var(--sec)", fontSize: 11 }}>{r.priority}</b></td>
                <td style={{ padding: "5px 8px", borderTop: "1px solid var(--line)", color: "var(--sec)", fontSize: 11 }}>{r.page}{r.exception ? " ⓘ" : ""}</td>
              </tr>
            ))}
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
  return (
    <div ref={panelRef} className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
      <b style={{ fontSize: 14 }}>검수 기준 — 스펙 (Rule 기반 V2)</b>
      <p style={{ fontSize: 12.5, color: "var(--sec)", margin: "6px 0 0" }}>
        AI 추론이 아니라 <b>Rule DB 기준값과의 결정적(deterministic) 대조</b>입니다. 같은 페이지는 항상 같은 결과가 나오고, 모든 판정에 "판정 과정 보기"가 남습니다.
      </p>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>판정 순서 (항상 이 순서)</div>
        <div style={{ fontSize: 12, color: "var(--sec)", lineHeight: 1.7 }}>
          페이지 수집 → 스펙 영역 추출 → <b>섹션 판정</b>(본문/각주/구매박스/구성품…) → <b>항목 판정</b>(라벨이 어느 속성인지) → <b>사전 매핑</b>(23개 대표항목 × 637개 다국어 표현) → <b>정규화</b>(4,400=4.400=4 400) → <b>검사</b> → <b>예외 적용</b> → 결과
        </div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>검사 방식 6종 — 항목마다 "틀리는 방식"에 맞춰 배정</div>
        {Object.entries(VAL_KO).map(([k, v]) => (
          <div key={k} style={{ fontSize: 12, color: "var(--sec)", lineHeight: 1.7 }}>
            · <b style={{ color: "var(--label)" }}>{v.label}</b> — {v.desc}
          </div>
        ))}
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>판정 등급</div>
        <div style={{ fontSize: 12, color: "var(--sec)", lineHeight: 1.8 }}>
          <div>🔴 <b style={{ color: C.crit }}>Critical</b> — 값이 기준과 <b>다름</b> (예: 무게 216g ↔ 기준 215g)</div>
          <div>🟡 <b style={{ color: C.warn }}>Warning</b> — 페이지에서 <b>사전에 없는 새 표현</b> 발견 → 번역/표기 재확인 후 [Dictionary 추가]로 승인</div>
          <div>⚪ <b style={{ color: C.na }}>N/A</b> — 항목을 페이지에서 못 찾았거나 이 페이지타입에 해당 없음 (N/A가 절반 넘으면 커버리지 경고가 뜹니다)</div>
        </div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>오탐(False Positive) 방지 장치</div>
        <div style={{ fontSize: 12, color: "var(--sec)", lineHeight: 1.7 }}>
          · <b>Typical ↔ Rated 상호 비교 금지</b> — 일반 4400과 각주의 정격 4272는 서로 다른 항목으로 취급<br />
          · <b>프로모션 영역 제외</b> — 배너의 마케팅 숫자는 검사하지 않음<br />
          · <b>적응형 주사율(1–120Hz)</b> — 최대값만 검증 · <b>국가 예외</b> — CountryException 시트로 국가별 스킵/허용
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
      <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 8 }}>📊 스펙 점수는 이렇게 계산돼요 (V2)</div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>① Validation Score</div>
        <div style={li}><b>통과한 룰 ÷ 판정한 룰</b> × 100. "판정한 룰" = PASS + Critical만이에요 — <b>N/A는 분모에서 제외</b>합니다(페이지에 원래 없는 항목 때문에 점수가 깎이지 않게).</div>
        <div style={{ ...li, marginTop: 4 }}>예) 룰 31개 중 N/A 6개 · PASS 23개 · Critical 2개 → 23 ÷ 25 = <b>92%</b></div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>② 카테고리 점수</div>
        <div style={li}>같은 방식을 카테고리(Battery·Display…) 단위로 계산합니다. 카드에 보이는 "Rule Pass 8/8"이 그 분자/분모예요. 오류가 있는 카테고리는 자동으로 펼쳐집니다.</div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>③ Warning은 점수에 안 들어가요</div>
        <div style={li}>🟡 Warning(사전 미등록 표현)은 "페이지가 틀렸다"가 아니라 <b>"검수 시스템이 이 표현을 아직 모른다"</b>는 뜻이라 점수와 분리해서 셉니다. 승인해서 사전에 추가하면 다음 검수부터 그 항목이 정식 판정됩니다.</div>
      </div>
      <div style={box}>
        <div style={{ fontWeight: 800, fontSize: 12.5, marginBottom: 4 }}>④ 커버리지 경고 — 점수가 좋아 보여도 믿지 마세요</div>
        <div style={li}>적용 대상 룰의 <b>절반 이상이 N/A</b>면 상단에 ⚠️ 경고가 뜹니다. 이 언어 표현이 사전에 없거나 페이지 구조가 달라 수집이 안 된 것일 수 있어요 — 이때의 높은 점수는 "다 통과"가 아니라 "거의 못 봤다"일 수 있으니, 새 표현 승인부터 해주세요.</div>
      </div>
      <div style={{ fontSize: 12, color: "var(--sec)", marginTop: 8 }}>
        신호등: 🟢 80%↑ · 🟡 50–79% · 🔴 50% 미만 — Data QA와 동일 기준
      </div>
    </div>
  );
}
