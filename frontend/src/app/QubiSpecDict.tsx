"use client";
/* QubiSpecDict.tsx — Spec QA Dictionary 화면 (제품 단위 Dictionary Review + 상시 사전 패널)
   [2026-07 분할] QubiSpecQa.tsx에서 분리 — 판정 화면과 독립적인 사전 관리 영역. */
import { useEffect, useState } from "react";

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
