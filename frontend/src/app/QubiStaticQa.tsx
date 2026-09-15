"use client";
/* QubiStaticQa — 🐝 큐비 · 공통페이지 QA 탭 [2026-09 · v2]
   91개 사이트 × 7종 공통 페이지(Home · All about Galaxy · Switch to Galaxy · Galaxy AI · Samsung Health · One UI · Find your Galaxy)를
   매일 한 번 "전형적 오류"만 본다. DATA QA 처럼 위에서 페이지를 고르고, 아래에서 상태별 상세를 본다. 백엔드 /api/qb/static/* */
import { useEffect, useState } from "react";
import { sel as selStyle, SEV } from "./qubiShared";

const ORDER = ["정상", "파싱 실패", "오적용", "미해결 참조", "페이지 없음", "접근 실패", "기타"];
const COLOR: Record<string, string> = { "정상": "#DCFCE7", "파싱 실패": "#FEE2E2", "오적용": "#FEF3C7", "미해결 참조": "#FEF3C7", "페이지 없음": "#E5E7EB", "접근 실패": "#F3F4F6", "기타": "#FFF7ED" };
const INK: Record<string, string> = { "정상": "#166534", "파싱 실패": "#991B1B", "오적용": "#92400E", "미해결 참조": "#92400E", "페이지 없음": "#6B7280", "접근 실패": "#9CA3AF", "기타": "#B45309" };
const HELP: Record<string, string> = {
  "정상": "스키마(JSON-LD)가 모두 읽히고 전형적 오류가 없음",
  "파싱 실패": "일부 스키마 블록이 문법 오류(escape·제어문자·괄호·쉼표)로 읽히지 않음 — 그 블록은 검색엔진이 못 봄 → HTML 수정 필요",
  "오적용": "스키마의 @id/url 에 다른 국가 사이트 주소가 섞여 있음 (예: de 페이지가 /fr/ 를 가리킴 — ca_fr↔ca 같은 언어 변형은 제외)",
  "미해결 참조": "스키마가 가리키는 @id 가 이 페이지 안에 정의되어 있지 않음",
  "페이지 없음": "404 이거나 안내 페이지로 떨어짐 — 그 국가에 이 페이지가 없거나 주소가 다름",
  "접근 실패": "403/429/네트워크 오류 — 사이트 문제보다 수집 환경(프록시·차단) 문제일 수 있음",
  "기타": "중복 @id, 리치결과 필수 속성 누락, 또는 스키마가 하나도 없음",
};
const th: React.CSSProperties = { textAlign: "left", fontSize: 11.5, color: "var(--sec)", fontWeight: 600, padding: "6px 8px", borderBottom: "1px solid var(--line)", whiteSpace: "nowrap", position: "sticky", top: 0, background: "#fff" };
const td: React.CSSProperties = { fontSize: 12, padding: "5px 8px", borderBottom: "1px solid var(--line)", verticalAlign: "top" };
const Pill = ({ s, n, on, onClick }: { s: string; n?: number; on?: boolean; onClick?: () => void }) => (
  <span title={HELP[s]} onClick={onClick} style={{ cursor: onClick ? "pointer" : "default", fontSize: 11.5, padding: "3px 9px", borderRadius: 999, background: COLOR[s], color: INK[s], fontWeight: 700, outline: on ? "2px solid var(--blue)" : "none" }}>{s}{n != null ? ` ${n}` : ""}</span>);

export function QubiStaticQa({ apiBase }: { apiBase: string }) {
  const api = (p: string) => `${apiBase}${p}`;
  const [meta, setMeta] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [run, setRun] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [page, setPage] = useState<string>("all");          // 페이지 필터(DATA QA 의 제품 칩과 같은 역할)
  const [stFilter, setStFilter] = useState<string>("all");  // 상태 필터
  const [sel, setSel] = useState<any>(null);

  const load = async () => {
    try {
      setMeta(await (await fetch(api("/api/qb/static/pages"))).json());
      const rs = (await (await fetch(api("/api/qb/static/runs"))).json()).runs || []; setRuns(rs);
      if (rs.length) setRun(await (await fetch(api(`/api/qb/static/runs/${rs[0].run_id}`))).json());
    } catch { /* */ }
  };
  useEffect(() => { load(); }, [apiBase]);
  const start = async () => {
    const body = page === "all" ? {} : { pages: [page] };
    const r = await fetch(api("/api/qb/static/run"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.status === 409) { alert("이미 검수 중입니다"); return; }
    setStatus({ done: 0, total: 0 }); const t = setInterval(async () => { const st = await (await fetch(api("/api/qb/static/status"))).json(); setStatus(st); if (!st.running) { clearInterval(t); setStatus(null); load(); } }, 1500);
  };
  const openRun = async (id: string) => { setRun(await (await fetch(api(`/api/qb/static/runs/${id}`))).json()); setSel(null); };

  if (!meta) return <div className="card">공통페이지 QA 불러오는 중…</div>;
  const pages: any[] = meta.pages;
  const results: any[] = (run?.results || []).filter((r: any) => page === "all" || r.page === page);
  const visible = results.filter((r: any) => stFilter === "all" || r.status === stFilter);
  const count = (s: string) => results.filter((r: any) => r.status === s).length;
  const pagesShown = pages.filter((p) => page === "all" || p.key === page);
  const by: Record<string, any> = {}; results.forEach((r) => { by[`${r.sitecode}|${r.page}`] = r; });
  const sites = Array.from(new Set(results.map((r) => r.sitecode))).sort().filter((sc) => stFilter === "all" || pagesShown.some((p) => by[`${sc}|${p.key}`]?.status === stFilter));
  const est = Math.max(1, Math.round((meta.auto * pagesShown.length) / 8 * 1.5 / 60));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* 페이지 선택 — DATA QA 의 제품 칩과 같은 위치·역할 */}
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "var(--sec)", marginRight: 4 }}>페이지</span>
        <span style={selStyle("all", page === "all")} onClick={() => { setPage("all"); setSel(null); }}>전체 {pages.length}종</span>
        {pages.map((p) => <span key={p.key} style={selStyle(p.key, page === p.key)} onClick={() => { setPage(p.key); setSel(null); }} >{p.label}</span>)}
        <span style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
          {runs.length > 0 && <select value={run?.run_id || ""} onChange={(e) => openRun(e.target.value)} style={{ fontSize: 12, padding: "5px 8px", border: "1px solid var(--line)", borderRadius: 6 }}>
            {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.at}</option>)}</select>}
          {!status ? <button className="btnPrimary" style={{ padding: "6px 12px", fontSize: 12 }} onClick={start}>{`▶ 지금 검수${page !== "all" ? " (선택한 페이지만)" : ""}`}</button>
            : <button style={{ padding: "6px 12px", fontSize: 12, borderRadius: 8, border: "1px solid #B42318", background: "#fff", color: "#B42318", fontWeight: 700, cursor: "pointer" }} onClick={async () => { if (window.confirm("검수를 멈출까요? 끝난 페이지까지는 저장됩니다.")) await fetch(api("/api/qb/static/cancel"), { method: "POST" }); }}>■ 멈춤</button>}
          {run && <a className="btnSecondary" style={{ padding: "6px 12px", fontSize: 12 }} href={api(`/api/qb/static/report.xlsx?run_id=${run.run_id}`)}>Excel</a>}
        </span>
      </div>

      {status && (
        <div className="card" style={{ padding: "12px 16px" }}>
          <div style={{ height: 8, background: "#F0F1F3", borderRadius: 999, overflow: "hidden" }}><div style={{ height: "100%", width: `${status.total ? (status.done / status.total) * 100 : 0}%`, background: "#1B4FD8", transition: "width .3s" }} /></div>
          <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 4 }}>🐝 공통페이지 검수 중 · {status.done}/{status.total} 페이지{status.current ? ` · 지금: ${status.current}` : ""}{status.cancel ? " · 멈추는 중…" : ""}</div>
          {status.recent?.length > 0 && <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>{status.recent.map((r: any, i: number) => <span key={i} style={{ fontSize: 11, padding: "2px 8px", borderRadius: 999, background: COLOR[r.status] || "#eee", color: INK[r.status] || "#333" }}>{r.sitecode} {r.page} · {r.status}</span>)}</div>}
        </div>
      )}
      {/* 종합 — 상태 칩(클릭하면 필터) */}
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <b style={{ fontSize: 14 }}>{page === "all" ? "공통 페이지 전체" : pages.find((p) => p.key === page)?.label}</b>
          <span style={{ fontSize: 12, color: "var(--sec)" }}>{meta.auto}개 국가 사이트{meta.manual?.length ? ` (직접 확인: ${meta.manual.join(", ")})` : ""} · {run ? `마지막 검수 ${run.at}` : "아직 검수 전"}</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
          <span style={selStyle("all", stFilter === "all")} onClick={() => setStFilter("all")}>전체 {results.length}</span>
          {ORDER.map((s) => <Pill key={s} s={s} n={count(s)} on={stFilter === s} onClick={() => setStFilter(stFilter === s ? "all" : s)} />)}
          {!run && <span style={{ fontSize: 12, color: "var(--sec)" }}>"지금 검수"를 누르면 약 {est}분 걸립니다(페이지당 1~2초).</span>}
        </div>

      </div>

      {/* [2026-09-14] 페이지·권역별 정상/오류 비율 (보고용) */}
      {run?.insight && (
        <div className="card">
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
            <b style={{ fontSize: 14 }}>페이지·권역별 비율</b>
            <span style={{ fontSize: 12, color: "var(--sec)" }}>정상 {run.insight.overall.ok_pct}% · 오류 {run.insight.overall.err_pct}% (전체 {run.insight.overall.total})</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--label2)", marginBottom: 4 }}>페이지별</div>
              {Object.entries(run.insight.by_page).map(([k, v]: any) => <Bar key={k} label={k} v={v} />)}
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--label2)", marginBottom: 4 }}>권역별 (오류 많은 순)</div>
              <div style={{ maxHeight: 220, overflow: "auto" }}>{Object.entries(run.insight.by_region).map(([k, v]: any) => <Bar key={k} label={k} v={v} />)}</div>
            </div>
          </div>
        </div>
      )}

      {/* 매트릭스 — 국가 × 페이지 */}
      {run && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ maxHeight: 420, overflow: "auto" }}>
            <table style={{ borderCollapse: "collapse", width: "100%" }}>
              <thead><tr><th style={th}>사이트</th><th style={th}>국가</th>{pagesShown.map((p) => <th key={p.key} style={{ ...th, textAlign: "center" }}>{p.label}</th>)}</tr></thead>
              <tbody>
                {sites.map((sc) => (<tr key={sc}>
                  <td style={{ ...td, fontWeight: 700 }}>{sc}</td><td style={{ ...td, color: "var(--sec)" }}>{results.find((r) => r.sitecode === sc)?.country}</td>
                  {pagesShown.map((p) => { const r = by[`${sc}|${p.key}`]; return (
                    <td key={p.key} style={{ ...td, textAlign: "center", cursor: r ? "pointer" : "default", background: r ? COLOR[r.status] : undefined, color: r ? INK[r.status] : "var(--ter)", fontWeight: 600, outline: sel && sel.sitecode === sc && sel.page === p.key ? "2px solid var(--blue)" : "none" }}
                        title={r ? `${r.url}\n${(r.reasons || []).join(" · ")}` : ""} onClick={() => r && setSel(r)}>{r ? r.status : "—"}</td>); })}
                </tr>))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 선택한 칸 상세 */}
      {sel && <Detail sel={sel} onClose={() => setSel(null)} />}

      {/* 상태별 상세 목록 — 어떤 사이트가 왜 그런지 */}
      {run && ORDER.filter((s) => s !== "정상" && (stFilter === "all" || stFilter === s)).map((s) => {
        const rows = visible.filter((r: any) => r.status === s);
        if (!rows.length) return null;
        return (
          <div key={s} className="card">
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6 }}><Pill s={s} n={rows.length} /><span style={{ fontSize: 12, color: "var(--sec)" }}>{HELP[s]}</span></div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={th}>사이트</th><th style={th}>페이지</th><th style={th}>무엇이 문제인가</th><th style={th}>주소</th></tr></thead>
              <tbody>
                {rows.sort((a: any, b: any) => a.sitecode.localeCompare(b.sitecode)).map((r: any, i: number) => (
                  <tr key={i} style={{ cursor: "pointer" }} onClick={() => setSel(r)}>
                    <td style={{ ...td, fontWeight: 700 }}>{r.sitecode} <span style={{ color: "var(--sec)", fontWeight: 400 }}>{r.country}</span></td>
                    <td style={td}>{r.page_label}</td>
                    <td style={td}>{(r.reasons || []).join(" · ")}{r.parse_errors?.filter((p: any) => p.severity !== "warn").length ? <div style={{ color: "var(--sec)" }}>{r.parse_errors.filter((p: any) => p.severity !== "warn").map((p: any) => `${p.block} · ${p.category}${p.line ? ` · ${p.line}:${p.col}` : ""}`).join(" / ")}</div> : null}</td>
                    <td style={{ ...td, wordBreak: "break-all" }}><a href={r.url} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }} onClick={(e) => e.stopPropagation()}>{r.url.replace("https://www.samsung.com", "")}</a></td>
                  </tr>))}
              </tbody>
            </table>
          </div>);
      })}
      {run && (stFilter === "all" || stFilter === "정상") && (
        <div className="card"><div style={{ display: "flex", alignItems: "baseline", gap: 10 }}><Pill s="정상" n={count("정상")} /><span style={{ fontSize: 12, color: "var(--sec)" }}>{HELP["정상"]} — 매트릭스에서 초록 칸</span></div></div>)}
    </div>
  );
}

function Bar({ label, v }: { label: string; v: any }) {
  const ok = v.ok_pct, err = v.err_pct, na = 100 - ok - err;
  return (
    <div style={{ margin: "4px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5 }}>
        <span>{label}</span><span style={{ color: "var(--sec)" }}>정상 {ok}% · 오류 {err}% <span style={{ color: "var(--ter)" }}>({v.total})</span></span>
      </div>
      <div style={{ display: "flex", height: 8, borderRadius: 999, overflow: "hidden", background: "#EEF0F3" }}>
        <div style={{ width: ok + "%", background: SEV.pass.c }} /><div style={{ width: err + "%", background: SEV.fail.c }} /><div style={{ width: na + "%", background: SEV.na.c }} />
      </div>
    </div>);
}

function Detail({ sel, onClose }: { sel: any; onClose: () => void }) {
  return (
    <div className="card qbiPopIn">
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
        <b style={{ fontSize: 14 }}>{sel.sitecode} · {sel.page_label}</b><Pill s={sel.status} />
        <a href={sel.url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: "var(--blue)", wordBreak: "break-all" }}>{sel.url}</a>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--sec)", cursor: "pointer" }} onClick={onClose}>닫기 ✕</span>
      </div>
      <div style={{ fontSize: 12, color: "var(--label2)", marginBottom: 8 }}>{HELP[sel.status]} — {(sel.reasons || []).join(" · ")}{sel.http_status ? ` · HTTP ${sel.http_status}` : ""}{sel.title ? ` · "${sel.title}"` : ""}</div>
      {sel.guide && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, margin: "0 0 12px" }}>
          <div style={{ background: "#FDECEC", borderRadius: 8, padding: "8px 10px" }}><b style={{ fontSize: 11.5, color: "#B42318" }}>지금 상태 (as-is)</b><div style={{ fontSize: 12, marginTop: 3 }}>{sel.guide.as_is}</div></div>
          <div style={{ background: "#E8F5EC", borderRadius: 8, padding: "8px 10px" }}><b style={{ fontSize: 11.5, color: "#166534" }}>이렇게 고치세요 (to-be)</b><div style={{ fontSize: 12, marginTop: 3 }}>{sel.guide.to_be}</div>{sel.guide.who !== "-" && <div style={{ fontSize: 11, color: "var(--sec)", marginTop: 4 }}>담당: {sel.guide.who}</div>}</div>
          {sel.guide.fixes?.length > 0 && (
            <div style={{ gridColumn: "1 / -1" }}>
              <b style={{ fontSize: 11.5, color: "var(--label2)" }}>블록별 조치</b>
              <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 4 }}>
                <thead><tr><th style={th}>블록</th><th style={th}>유형</th><th style={th}>위치</th><th style={th}>조치</th></tr></thead>
                <tbody>{sel.guide.fixes.map((f: any, i: number) => (<tr key={i}><td style={td}>{f.block}</td><td style={td}>{f.category}</td><td style={{ ...td, wordBreak: "break-all" }}>{f.where}</td><td style={td}>{f.to_be}</td></tr>))}</tbody>
              </table>
            </div>)}
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
        <div>
          <b>스키마 블록 {sel.blocks}개 · 읽기 실패 {(sel.parse_errors || []).filter((p: any) => p.severity !== "warn").length}</b>
          {(sel.parse_errors || []).map((p: any, i: number) => <div key={i} style={{ padding: "4px 8px", margin: "4px 0", borderRadius: 6, background: p.severity === "warn" ? "#FFFBEB" : "#FEF2F2" }}><b>{p.block}</b> · {p.category}{p.line ? ` · ${p.line}줄 ${p.col}칸` : ""}<div style={{ color: "var(--sec)" }}>{p.msg} — {p.hint}</div></div>)}
          <div style={{ marginTop: 8 }}><b>이 페이지에 있는 스키마</b><div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>{(sel.types || []).map((t: string) => <span key={t} className="badge c6">{t}</span>)}{!(sel.types || []).length && <span style={{ color: "var(--sec)" }}>없음</span>}</div></div>
        </div>
        <div>
          {!!(sel.foreign_refs || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "#92400E" }}>다른 국가 주소가 섞인 곳</b>{sel.foreign_refs.map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--sec)" }}>{u}</div>)}</div>}
          {!!(sel.unresolved_refs || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "#92400E" }}>정의되지 않은 @id 를 가리킴</b>{sel.unresolved_refs.map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--sec)" }}>{u}</div>)}</div>}
          {!!(sel.duplicate_ids || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "#B45309" }}>중복 @id</b>{sel.duplicate_ids.map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--sec)" }}>{u}</div>)}</div>}
          {!!(sel.rich_missing || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "#B45309" }}>Google 리치결과 필수 속성 누락</b>{sel.rich_missing.map((m: any, i: number) => <div key={i} style={{ color: "var(--sec)" }}>{m.type}: {m.missing.join(", ")}{m.id ? ` (${m.id})` : ""}</div>)}</div>}
          {!!(sel.external_refs || []).length && <div><b style={{ color: "var(--sec)" }}>다른 페이지에 정의된 참조(판정 안 함)</b>{sel.external_refs.slice(0, 5).map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--ter)" }}>{u}</div>)}</div>}
        </div>
      </div>
    </div>
  );
}
