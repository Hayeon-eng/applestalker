"use client";
/* QubiTargets — 사이드바 "대상 관리" [2026-09 · "URL 관리" 대체]
   · URL 은 사람이 등록하지 않고 삼성 검색 API(finder/spec-ia)로 자동 해석된다(backend/dotcom_qa/resolver.py).
   · 여기서는 ① 다시 해석, ② 해석 결과 보기(읽기 전용, source 별), ③ 예외 등록(cn 등 finder 미지원), ④ 크롤 제외 토글만 한다.
   · 사람이 정의하는 '대상'(제품 × 국가 × 페이지타입)은 메인 화면의 제품/사이트/페이지타입 칩이 담당한다. */
import { useEffect, useRef, useState } from "react";

const J = (b: any) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
const SRC: Record<string, { label: string; cls: string; help: string }> = {
  finder: { label: "자동 해석", cls: "good", help: "삼성 검색 API 가 돌려준 실제 URL" },
  exception: { label: "예외", cls: "c4", help: "사람이 등록(cn·캠페인 등 finder 미지원)" },
  legacy: { label: "기존 등록", cls: "c6", help: "아직 해석되지 않아 이전 레지스트리 값을 쓰는 항목 — 워치 등은 soft-404 가능" },
};

export function QubiTargets({ apiBase }: { apiBase: string }) {
  const api = (p: string) => `${apiBase}${p}`;
  const [data, setData] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<string>("all");
  const [q, setQ] = useState("");
  const [exc, setExc] = useState({ sitecode: "", url: "", product: "", page_type: "PDP", note: "" });
  const [showExc, setShowExc] = useState(false);
  const [msg, setMsg] = useState("");
  const timer = useRef<any>(null);

  const load = async () => { try { setData(await (await fetch(api("/api/qb/targets"))).json()); } catch { /* */ } };
  useEffect(() => { load(); return () => timer.current && clearInterval(timer.current); }, [apiBase]);

  const resolve = async () => {
    const r = await fetch(api("/api/qb/targets/resolve"), { method: "POST" });
    if (r.status === 409) { setMsg("이미 해석 중"); return; }
    setMsg("해석 시작 — 사이트별 finder 조회 중…");
    timer.current = setInterval(async () => {
      const st = await (await fetch(api("/api/qb/targets/status"))).json();
      setMsg(st.running ? `해석 중 ${st.done}/${st.total}` : st.error ? `실패: ${st.error}` : "해석 완료");
      if (!st.running) { clearInterval(timer.current); load(); }
    }, 1500);
  };
  const addException = async () => {
    if (!exc.url.startsWith("http")) { setMsg("절대 URL 을 입력하세요"); return; }
    const r = await (await fetch(api("/api/qb/targets/exception"), J(exc))).json();
    setMsg(r.ok ? "예외 등록됨" : "실패"); setExc({ sitecode: "", url: "", product: "", page_type: "PDP", note: "" }); load();
  };
  const removeException = async (e: any) => { await fetch(api("/api/qb/targets/exception/remove"), J({ sitecode: e.sitecode, url: e.url })); load(); };
  const toggleExclude = async (e: any) => { await fetch(api("/api/qb/targets/exclude"), J({ sitecode: e.sitecode, url: e.url, excluded: !e.excluded })); load(); };

  if (!data) return <div className="sideLabel">대상 관리 <span style={{ color: "var(--sec)" }}>불러오는 중…</span></div>;
  const entries: any[] = data.entries || [];
  const bySrc = data.stats?.by_source || {};
  const shown = entries.filter((e) => (filter === "all" || e.source === filter) && (!q || `${e.sitecode} ${e.product} ${e.url}`.toLowerCase().includes(q.toLowerCase())));

  return (
    <>
      <div className="sideLabel">대상 관리 <span style={{ color: "var(--sec)" }}>크롤 {data.stats?.active ?? 0}개</span></div>
      <div style={{ padding: "0 10px 6px", fontSize: 11, color: "var(--sec)", lineHeight: 1.45 }}>
        URL 은 삼성 검색 API 로 자동 해석됩니다{data.generated_at ? ` (마지막 해석 ${data.generated_at})` : " (아직 해석 전 — 기존 등록 값 사용 중)"}.
      </div>
      <div style={{ padding: "0 10px 8px", display: "flex", gap: 6, flexWrap: "wrap" }}>
        <button className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }} onClick={resolve} disabled={data.state?.running}>↻ URL 다시 해석</button>
        <button className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }} onClick={() => setShowExc((v) => !v)}>＋ 예외 등록</button>
        <a className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }} href={api("/api/qb/targets/export.json")}>⬇ 해석 결과 JSON</a>
      </div>
      {msg && <div style={{ padding: "0 10px 6px", fontSize: 11, color: "#8A5A00" }}>{msg}</div>}
      {showExc && (
        <div style={{ margin: "0 10px 8px", padding: 8, background: "#fff", border: "1px solid var(--line)", borderRadius: 8, display: "flex", flexDirection: "column", gap: 5 }}>
          <input className="urlInput" placeholder="URL (https://…)" value={exc.url} onChange={(e) => setExc({ ...exc, url: e.target.value })} />
          <div style={{ display: "flex", gap: 5 }}>
            <input className="urlInput" style={{ flex: "0 0 60px" }} placeholder="sitecode" value={exc.sitecode} onChange={(e) => setExc({ ...exc, sitecode: e.target.value })} />
            <input className="urlInput" placeholder="product 슬러그" value={exc.product} onChange={(e) => setExc({ ...exc, product: e.target.value })} />
            <select className="urlInput" style={{ flex: "0 0 80px" }} value={exc.page_type} onChange={(e) => setExc({ ...exc, page_type: e.target.value })}><option>PDP</option><option>Compare</option><option>Buying</option></select>
          </div>
          <input className="urlInput" placeholder="메모(선택) — 왜 예외인지" value={exc.note} onChange={(e) => setExc({ ...exc, note: e.target.value })} />
          <button className="btnAdd" style={{ padding: "5px 10px" }} onClick={addException}>등록</button>
        </div>
      )}
      <div style={{ padding: "0 10px 6px", display: "flex", gap: 4, flexWrap: "wrap" }}>
        {["all", "finder", "exception", "legacy"].map((s) => (
          <span key={s} className={`badge ${s === "all" ? "c6" : SRC[s].cls}`} style={{ cursor: "pointer", outline: filter === s ? "2px solid var(--blue)" : "none" }} onClick={() => setFilter(s)} title={s === "all" ? "" : SRC[s].help}>
            {s === "all" ? "전체" : SRC[s].label} {s === "all" ? entries.length : bySrc[s] || 0}
          </span>))}
      </div>
      {(data.unresolved || []).length > 0 && (
        <div style={{ padding: "0 10px 6px", fontSize: 11, color: "var(--med)" }}>해석 실패 {data.unresolved.length}건 — 목록 하단에 사유 표시</div>
      )}
      <div className="sideLabel" style={{ cursor: "pointer" }} onClick={() => setOpen((o) => !o)}>{open ? "▾" : "▸"} 해석 결과 보기 <span style={{ color: "var(--sec)" }}>{shown.length}개</span></div>
      {open && (<>
        <div style={{ padding: "0 10px 6px" }}><input className="urlInput" style={{ width: "100%" }} placeholder="사이트/제품/URL 검색" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div className="urlAccordionBody">
          {shown.map((e, i) => (
            <div key={`${e.sitecode}-${e.url}-${i}`} className="urlListItem" style={{ opacity: e.excluded ? 0.45 : 1 }}>
              <div className="urlListUrl">
                <b>{e.sitecode} <span className={`badge ${SRC[e.source]?.cls || "c6"}`} style={{ marginLeft: 4 }}>{SRC[e.source]?.label || e.source}</span>
                  <span className="urlAccordionTierTag" style={{ marginLeft: 4 }}>{e.product}{e.page_type ? ` · ${e.page_type}` : ""}</span></b>
                {e.url}
                {e.model_code && <small>model {e.model_code}{e.display_name ? ` · ${e.display_name}` : ""}{e.resolved_at ? ` · ${e.resolved_at}` : ""}</small>}
                {e.note && <small>메모: {e.note}</small>}
              </div>
              {e.source === "exception"
                ? <span className="urlDelBtn" title="예외 삭제" onClick={() => removeException(e)}>×</span>
                : e.source === "finder" && <span className="urlDelBtn" title={e.excluded ? "크롤에 다시 포함" : "크롤에서 제외"} onClick={() => toggleExclude(e)}>{e.excluded ? "↺" : "⊘"}</span>}
            </div>))}
          {(data.unresolved || []).map((u: any, i: number) => (
            <div key={`u-${i}`} className="urlListItem"><div className="urlListUrl"><b style={{ color: "var(--med)" }}>{u.sitecode} <span className="badge med">미해석</span> <span className="urlAccordionTierTag">{u.product}</span></b><small>{u.reason}</small></div></div>))}
        </div>
      </>)}
    </>
  );
}
