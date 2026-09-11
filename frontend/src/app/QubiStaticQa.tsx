"use client";
/* QubiStaticQa — 🐝 큐비 · 스태틱 페이지 Schema 라이트 검수 탭 [2026-09 신규]
   91개 사이트 × 7종 공통 페이지(Home · All about Galaxy · Switch to Galaxy · Galaxy AI · Samsung Health · One UI · Find your Galaxy)를
   매일 한 번, 플래그십처럼 상세 룰이 아니라 "전형적 오류"만 본다: 페이지 없음 / JSON-LD 파싱 실패 / 타 사이트코드 참조 / 미해결 @id / 중복 @id / 리치결과 필수 속성.
   백엔드 /api/qb/static/* */
import { useEffect, useState } from "react";

const COLOR: Record<string, string> = { "정상": "#DCFCE7", "파싱 실패": "#FEE2E2", "오적용": "#FEF3C7", "미해결 참조": "#FEF3C7", "페이지 없음": "#E5E7EB", "접근 실패": "#F3F4F6", "기타": "#FFF7ED" };
const INK: Record<string, string> = { "정상": "#166534", "파싱 실패": "#991B1B", "오적용": "#92400E", "미해결 참조": "#92400E", "페이지 없음": "#6B7280", "접근 실패": "#9CA3AF", "기타": "#B45309" };
const HELP: Record<string, string> = {
  "정상": "JSON-LD 가 모두 파싱되고 전형적 오류가 없음", "파싱 실패": "일부 JSON-LD 블록이 문법 오류(escape·제어문자·괄호·쉼표)로 읽히지 않음 — 그 블록의 스키마는 검색엔진이 못 봄",
  "오적용": "@id/url 에 다른 사이트코드 경로가 섞임(예: ca_fr 페이지가 /ca/ 를 가리킴)", "미해결 참조": "hasPart/mainEntity 가 가리키는 @id 가 이 페이지에 없음",
  "페이지 없음": "404 이거나 안내 페이지(soft 404)로 떨어짐 — URL 확인", "접근 실패": "403/429/5xx 또는 네트워크 오류 — 사이트 문제보다 수집 환경(프록시·차단) 문제일 수 있음", "기타": "중복 @id 또는 리치결과 필수 속성 누락, 또는 JSON-LD 없음" };
const th: React.CSSProperties = { textAlign: "left", fontSize: 11.5, color: "var(--sec)", fontWeight: 600, padding: "6px 8px", borderBottom: "1px solid var(--line)", whiteSpace: "nowrap", position: "sticky", top: 0, background: "#fff" };
const td: React.CSSProperties = { fontSize: 12, padding: "5px 8px", borderBottom: "1px solid var(--line)", verticalAlign: "top" };

export function QubiStaticQa({ apiBase }: { apiBase: string }) {
  const api = (p: string) => `${apiBase}${p}`;
  const [meta, setMeta] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [run, setRun] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [sel, setSel] = useState<any>(null);
  const [filter, setFilter] = useState<string>("all");

  const load = async () => {
    try {
      setMeta(await (await fetch(api("/api/qb/static/pages"))).json());
      const rs = (await (await fetch(api("/api/qb/static/runs"))).json()).runs || []; setRuns(rs);
      if (rs.length) setRun((await (await fetch(api(`/api/qb/static/runs/${rs[0].run_id}`))).json()));
    } catch { /* */ }
  };
  useEffect(() => { load(); }, [apiBase]);
  const start = async () => {
    const r = await fetch(api("/api/qb/static/run"), { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (r.status === 409) { alert("이미 실행 중입니다"); return; }
    const t = setInterval(async () => { const st = await (await fetch(api("/api/qb/static/status"))).json(); setStatus(st); if (!st.running) { clearInterval(t); setStatus(null); load(); } }, 1500);
  };
  const openRun = async (id: string) => { setRun(await (await fetch(api(`/api/qb/static/runs/${id}`))).json()); setSel(null); };

  if (!meta) return <div className="card">스태틱 QA 불러오는 중…</div>;
  const pages: any[] = meta.pages;
  const results: any[] = run?.results || [];
  const by: Record<string, any> = {}; results.forEach((r) => { by[`${r.sitecode}|${r.page}`] = r; });
  const sites = Array.from(new Set(results.map((r) => r.sitecode))).sort();
  const shownSites = sites.filter((sc) => filter === "all" || pages.some((p) => by[`${sc}|${p.key}`]?.status === filter));
  const sum = run?.summary?.by_status || {};

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <b style={{ fontSize: 14 }}>스태틱 페이지 Schema 라이트 검수</b>
          <span style={{ fontSize: 12, color: "var(--sec)" }}>{meta.auto}개 사이트(자동) × {pages.length}종 페이지 · {meta.manual?.length ? `직접 확인: ${meta.manual.join(", ")}` : ""} · 매일 1회 권장(데스크톱 설정에서 자동)</span>
          <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
            <button className="btnPrimary" style={{ padding: "6px 12px", fontSize: 12 }} onClick={start} disabled={!!status}>{status ? `실행 중 ${status.done}/${status.total}` : "▶ 지금 검수"}</button>
            {run && <a className="btnSecondary" style={{ padding: "6px 12px", fontSize: 12 }} href={api(`/api/qb/static/report.xlsx?run_id=${run.run_id}`)}>Excel</a>}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
          {runs.length > 0 && <select value={run?.run_id || ""} onChange={(e) => openRun(e.target.value)} style={{ fontSize: 12, padding: "5px 8px", border: "1px solid var(--line)", borderRadius: 6 }}>
            {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.at} · 정상 {r.summary.by_status["정상"]} / 파싱 실패 {r.summary.by_status["파싱 실패"]} / 페이지 없음 {r.summary.by_status["페이지 없음"]}</option>)}
          </select>}
          {Object.keys(COLOR).map((s) => (
            <span key={s} title={HELP[s]} onClick={() => setFilter(filter === s ? "all" : s)} style={{ cursor: "pointer", fontSize: 11.5, padding: "3px 9px", borderRadius: 999, background: COLOR[s], color: INK[s], fontWeight: 700, outline: filter === s ? "2px solid var(--blue)" : "none" }}>{s} {sum[s] ?? 0}</span>))}
          {!run && <span style={{ fontSize: 12, color: "var(--sec)" }}>아직 실행 결과가 없습니다 — "지금 검수"를 누르면 약 {Math.round((meta.auto * pages.length) / 8 * 1.5 / 60)}분 소요(페이지당 1~2초, 동시 8).</span>}
        </div>
        <p style={{ fontSize: 11.5, color: "var(--sec)", margin: "8px 0 0" }}>경로가 확정된 페이지: Home · All about Galaxy(/mobile/) · Switch to Galaxy(/mobile/switch-to-galaxy/). 나머지 4종(Galaxy AI · Samsung Health · One UI · Find your Galaxy)은 관행 경로 후보를 순서대로 시도해 200 인 것을 기억합니다 — 전부 실패하면 '페이지 없음'으로 표시되니 첫 실행 후 경로를 확인해 주세요.</p>
      </div>

      {run && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ maxHeight: 560, overflow: "auto" }}>
            <table style={{ borderCollapse: "collapse", width: "100%" }}>
              <thead><tr><th style={th}>사이트</th><th style={th}>국가</th>{pages.map((p) => <th key={p.key} style={{ ...th, textAlign: "center" }}>{p.label}{!p.confirmed && <span title="경로 미확정(후보 시도)" style={{ color: "var(--ter)" }}> ?</span>}</th>)}</tr></thead>
              <tbody>
                {shownSites.map((sc) => (<tr key={sc}>
                  <td style={{ ...td, fontWeight: 700 }}>{sc}</td><td style={{ ...td, color: "var(--sec)" }}>{results.find((r) => r.sitecode === sc)?.country}</td>
                  {pages.map((p) => { const r = by[`${sc}|${p.key}`]; return (
                    <td key={p.key} style={{ ...td, textAlign: "center", cursor: r ? "pointer" : "default", background: r ? COLOR[r.status] : undefined, color: r ? INK[r.status] : "var(--ter)", fontWeight: 600, outline: sel && sel.sitecode === sc && sel.page === p.key ? "2px solid var(--blue)" : "none" }}
                        title={r ? `${r.url}\n${(r.reasons || []).join(" · ")}` : ""} onClick={() => r && setSel(r)}>{r ? r.status : "—"}</td>); })}
                </tr>))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {sel && (
        <div className="card qbiPopIn">
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
            <b style={{ fontSize: 14 }}>{sel.sitecode} · {sel.page_label}</b>
            <span style={{ fontSize: 11.5, padding: "2px 8px", borderRadius: 999, background: COLOR[sel.status], color: INK[sel.status], fontWeight: 700 }}>{sel.status}</span>
            <a href={sel.url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: "var(--blue)", wordBreak: "break-all" }}>{sel.url}</a>
            <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--sec)", cursor: "pointer" }} onClick={() => setSel(null)}>닫기 ✕</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--label2)", marginBottom: 8 }}>{HELP[sel.status]} — {(sel.reasons || []).join(" · ")}{sel.http_status ? ` · HTTP ${sel.http_status}` : ""}{sel.title ? ` · "${sel.title}"` : ""}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
            <div>
              <b>JSON-LD 블록 {sel.blocks}개 · 파싱 실패 {(sel.parse_errors || []).filter((p: any) => p.severity !== "warn").length}</b>
              {(sel.parse_errors || []).map((p: any, i: number) => <div key={i} style={{ padding: "4px 8px", margin: "4px 0", borderRadius: 6, background: p.severity === "warn" ? "#FFFBEB" : "#FEF2F2" }}><b>{p.block}</b> · {p.category} {p.line ? `· line ${p.line}, col ${p.col}` : ""}<div style={{ color: "var(--sec)" }}>{p.msg} — {p.hint}</div></div>)}
              <div style={{ marginTop: 8 }}><b>스키마 O/X</b><div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>{(sel.types || []).map((t: string) => <span key={t} className="badge c6">{t}</span>)}{!(sel.types || []).length && <span style={{ color: "var(--sec)" }}>JSON-LD 없음</span>}</div></div>
            </div>
            <div>
              {!!(sel.foreign_refs || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "#92400E" }}>타 사이트코드 참조</b>{sel.foreign_refs.map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--sec)" }}>{u}</div>)}</div>}
              {!!(sel.unresolved_refs || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "#92400E" }}>미해결 @id 참조</b>{sel.unresolved_refs.map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--sec)" }}>{u}</div>)}</div>}
              {!!(sel.duplicate_ids || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "#B45309" }}>중복 @id</b>{sel.duplicate_ids.map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--sec)" }}>{u}</div>)}</div>}
              {!!(sel.rich_missing || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "#B45309" }}>Google 리치결과 필수 속성 누락</b>{sel.rich_missing.map((m: any, i: number) => <div key={i} style={{ color: "var(--sec)" }}>{m.type}: {m.missing.join(", ")}{m.id ? ` (${m.id})` : ""}</div>)}</div>}
              {!!(sel.external_refs || []).length && <div><b style={{ color: "var(--sec)" }}>다른 페이지에 정의된 참조(판정 안 함)</b>{sel.external_refs.slice(0, 5).map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--ter)" }}>{u}</div>)}</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
