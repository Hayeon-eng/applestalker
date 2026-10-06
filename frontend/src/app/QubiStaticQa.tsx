"use client";
/* QubiStaticQa — 🐝 큐비 · 공통페이지 QA 탭 [2026-09 · v2]
   91개 사이트 × 7종 공통 페이지(Home · All about Galaxy · Switch to Galaxy · Galaxy AI · Samsung Health · One UI · Find your Galaxy)를
   매일 한 번 "전형적 오류"만 본다. DATA QA 처럼 위에서 페이지를 고르고, 아래에서 상태별 상세를 본다. 백엔드 /api/qb/static/*
   [2026-10 통일] 7단계 상태는 "사유"로 남기고, 색·신호등·점수판·칩은 큐비 공용(SEV / tlByScore / Meter / SevPill)만 쓴다.
   상태→판정 매핑은 백엔드 static_qa.SEV_OF_STATUS 가 원본(행마다 r.sev 로 내려옴). 첫 로드에 이력을 자동으로 열지 않는다(다른 탭과 동일). */
import { useEffect, useState } from "react";
import { sel as selStyle, SEV, type SevKey, TL_COLOR, tlByScore, tlEmoji } from "./qubiShared";
import { Meter, SevBar, SevPill, Loading, EmptyState, toast } from "./uiShared";

const ORDER = ["정상", "파싱 실패", "오적용", "미해결 참조", "페이지 없음", "접근 실패", "기타"];
// 상태 → 공용 판정(백엔드 SEV_OF_STATUS 와 동일 — r.sev 가 없을 때의 폴백)
const SEV_OF: Record<string, SevKey> = { "정상": "pass", "파싱 실패": "fail", "오적용": "warn", "미해결 참조": "warn", "기타": "warn", "페이지 없음": "na", "접근 실패": "na" };
const sevOf = (r: any): SevKey => (r?.sev as SevKey) || SEV_OF[r?.status] || "warn";
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
// 상태 칩 — 공용 SevPill 에 7단계 사유를 괄호로. "정상"은 사유 없이 판정만.
const Pill = ({ s, n, on, onClick }: { s: string; n?: number; on?: boolean; onClick?: () => void }) => (
  <SevPill sev={SEV_OF[s] || "warn"} label={s === "정상" ? undefined : s} n={n} on={on} onClick={onClick} title={HELP[s]} />);
// 집계 → 신호등 키(해당없음 제외 정상률 기준, Data QA 와 같은 80/50)
const tlOf = (v: any) => tlByScore(v?.score ?? null);
export function QubiStaticQa({ apiBase }: { apiBase: string }) {
  const api = (p: string) => `${apiBase}${p}`;
  const [meta, setMeta] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [run, setRun] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [page, setPage] = useState<string>("all");          // 페이지 필터(DATA QA 의 제품 칩과 같은 역할)
  const [stFilter, setStFilter] = useState<string>("all");  // 상태 필터
  const [region, setRegion] = useState<string>("all");      // [2026-09 신규] 권역(subs)별 수집
  const [sel, setSel] = useState<any>(null);

  const load = async () => {
    try {
      setMeta(await (await fetch(api("/api/qb/static/pages"))).json());
      const rs = (await (await fetch(api("/api/qb/static/runs"))).json()).runs || []; setRuns(rs);
      // 자동으로 과거 결과를 열지 않는다 — 사용자가 "최근 결과 열기"나 이력 선택으로 연다(큐비 다른 탭과 동일)
    } catch { /* */ }
  };
  const openLatest = async () => { if (runs.length) await openRun(runs[0].run_id); };
  useEffect(() => { load(); }, [apiBase]);
  const start = async () => {
    const body: any = page === "all" ? {} : { pages: [page] };
    if (region !== "all" && meta?.site_list) {
      body.sitecodes = meta.site_list.filter((s: any) => s.subs === region).map((s: any) => s.sitecode);
    }
    const r = await fetch(api("/api/qb/static/run"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.status === 409) { toast("이미 검수 중입니다", "warn"); return; }
    setStatus({ done: 0, total: 0 }); const t = setInterval(async () => { const st = await (await fetch(api("/api/qb/static/status"))).json(); setStatus(st); if (!st.running) { clearInterval(t); setStatus(null); await load(); const rs = (await (await fetch(api("/api/qb/static/runs"))).json()).runs || []; if (rs.length) openRun(rs[0].run_id); } }, 1500);
  };
  const openRun = async (id: string) => { setRun(await (await fetch(api(`/api/qb/static/runs/${id}`))).json()); setSel(null); };

  if (!meta) return <Loading label="공통페이지 QA 불러오는 중…" />;
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
          {!!meta.site_list?.length && (() => {
            const counts: Record<string, number> = {};
            meta.site_list.forEach((s: any) => { counts[s.subs] = (counts[s.subs] || 0) + 1; });
            const regions = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
            return (
              <select value={region} onChange={(e) => setRegion(e.target.value)} style={{ fontSize: 12, padding: "5px 8px", border: "1px solid var(--line)", borderRadius: 6 }} title="선택한 권역의 사이트만 검수합니다">
                <option value="all">전체 권역 ({meta.site_list.length}개국)</option>
                {regions.map((rg) => <option key={rg} value={rg}>{rg} ({counts[rg]}개국)</option>)}
              </select>
            );
          })()}
          {runs.length > 0 && <select value={run?.run_id || ""} onChange={(e) => e.target.value && openRun(e.target.value)} style={{ fontSize: 12, padding: "5px 8px", border: "1px solid var(--line)", borderRadius: 6 }} title="검수 이력">
            <option value="">이력 선택 ({runs.length})</option>
            {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.at}</option>)}</select>}
          {!status ? <button className="btnPrimary" style={{ padding: "6px 12px", fontSize: 12 }} onClick={start}>{`▶ 지금 검수${page !== "all" || region !== "all" ? " (선택 범위만)" : ""}`}</button>
            : <button className="btnDanger" style={{ padding: "6px 12px", fontSize: 12 }} onClick={async () => { if (window.confirm("검수를 멈출까요? 끝난 페이지까지는 저장됩니다.")) await fetch(api("/api/qb/static/cancel"), { method: "POST" }); }}>■ 멈춤</button>}
        </span>
      </div>

      {status && (
        <div className="card" style={{ padding: "12px 16px" }}>
          <div style={{ height: 8, background: "var(--gray-soft)", borderRadius: 999, overflow: "hidden" }}><div style={{ height: "100%", width: `${status.total ? (status.done / status.total) * 100 : 0}%`, background: "var(--blue)", transition: "width .3s" }} /></div>
          <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 4 }}>🐝 공통페이지 검수 중 · {status.done}/{status.total} 페이지{status.current ? ` · 지금: ${status.current}` : ""}{status.cancel ? " · 멈추는 중…" : ""}</div>
          {status.recent?.length > 0 && <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>{status.recent.map((r: any, i: number) => <span key={i} style={{ fontSize: 11, padding: "2px 8px", borderRadius: 999, background: SEV[sevOf(r)].soft, color: SEV[sevOf(r)].ink }}>{r.sitecode} {r.page} · {r.status}</span>)}</div>}
        </div>
      )}
      {/* 종합 — 상태 칩(클릭하면 필터) */}
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <b style={{ fontSize: 14 }}>{page === "all" ? "공통 페이지 전체" : pages.find((p) => p.key === page)?.label}</b>
          <span style={{ fontSize: 12, color: "var(--sec)" }}>{meta.auto}개 국가 사이트{meta.manual?.length ? ` (직접 확인: ${meta.manual.join(", ")})` : ""} · {run ? `검수 ${run.at}` : runs.length ? `마지막 검수 ${runs[0].at}` : "아직 검수 전"}</span>
          {run?.insight?.overall && (
            <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 18 }}>{tlEmoji(tlOf(run.insight.overall))}</span>
              <Meter pct={run.insight.overall.score} />
              <span style={{ fontSize: 11.5, color: "var(--sec)" }}>정상률 · 해당없음 {run.insight.overall.sev?.na ?? 0} 제외</span>
            </span>)}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
          <span style={selStyle("all", stFilter === "all")} onClick={() => setStFilter("all")}>전체 {results.length}</span>
          {ORDER.map((s) => <Pill key={s} s={s} n={count(s)} on={stFilter === s} onClick={() => setStFilter(stFilter === s ? "all" : s)} />)}
          {!run && <span style={{ fontSize: 12, color: "var(--sec)" }}>"지금 검수"를 누르면 약 {est}분 걸립니다(페이지당 1~2초).</span>}
        </div>
      </div>

      {!run && !status && (
        runs.length
          ? <EmptyState title="표시할 결과를 선택하세요" desc={`저장된 검수 이력 ${runs.length}건 — 과거 결과는 자동으로 열지 않습니다.`}
              action={<><button className="btnSecondary" onClick={openLatest}>최근 결과 열기 ({runs[0].at})</button><button className="btnPrimary" onClick={start}>▶ 지금 검수</button></>} />
          : <EmptyState title="아직 검수 이력이 없습니다" desc={`"지금 검수"를 누르면 ${meta.auto}개 사이트 × ${pagesShown.length}종 페이지를 확인합니다 (약 ${est}분).`}
              action={<button className="btnPrimary" onClick={start}>▶ 지금 검수</button>} />
      )}

      {/* [2026-09-14] 페이지·권역별 정상/오류 비율 (보고용) */}
      {run?.insight && (
        <div className="card">
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
            <b style={{ fontSize: 14 }}>페이지·권역별 비율</b>
            <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13 }}>
              <span>{tlEmoji(tlOf(run.insight.overall))}</span>
              <b style={{ color: TL_COLOR[tlOf(run.insight.overall)] || SEV.na.c }}>{run.insight.overall.score ?? "—"}%</b>
            </span>
            <span style={{ fontSize: 12, color: "var(--sec)" }}>정상 {run.insight.overall.sev?.pass} · 확인 {run.insight.overall.sev?.warn} · 오류 {run.insight.overall.sev?.fail} · 해당없음 {run.insight.overall.sev?.na} (전체 {run.insight.overall.total})</span>
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
              <thead><tr><th style={th}></th><th style={th}>사이트</th><th style={th}>국가 · 권역</th>{pagesShown.map((p) => <th key={p.key} style={{ ...th, textAlign: "center" }}>{p.label}</th>)}</tr></thead>
              <tbody>
                {sites.map((sc) => { const mine = results.filter((r) => r.sitecode === sc); const cnt: Record<SevKey, number> = { pass: 0, warn: 0, fail: 0, na: 0 }; mine.forEach((r) => { cnt[sevOf(r)]++; }); const scored = cnt.pass + cnt.warn + cnt.fail; const siteScore = scored ? Math.round((100 * cnt.pass) / scored) : null;
                  return (<tr key={sc}>
                  <td style={{ ...td, textAlign: "center" }} title={siteScore == null ? "판정 대상 없음" : `정상률 ${siteScore}%`}>{siteScore == null ? tlEmoji(null) : tlEmoji(tlByScore(siteScore))}</td>
                  <td style={{ ...td, fontWeight: 700 }}>{sc}</td><td style={{ ...td, color: "var(--sec)" }}>{mine[0]?.country}{mine[0]?.region && mine[0].region !== "-" ? <span style={{ color: "var(--ter)" }}> · {mine[0].region}</span> : null}</td>
                  {pagesShown.map((p) => { const r = by[`${sc}|${p.key}`]; return (
                    <td key={p.key} style={{ ...td, textAlign: "center", cursor: r ? "pointer" : "default", background: r ? SEV[sevOf(r)].soft : undefined, color: r ? SEV[sevOf(r)].ink : "var(--ter)", fontWeight: 600, outline: sel && sel.sitecode === sc && sel.page === p.key ? "2px solid var(--blue)" : "none" }}
                        title={r ? `${r.url}\n${(r.reasons || []).join(" · ")}` : ""} onClick={() => r && setSel(r)}>{r ? r.status : "—"}</td>); })}
                </tr>); })}
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
  const s = v.sev || { pass: v.ok || 0, warn: 0, fail: v.err || 0, na: v.na || 0 };
  return <SevBar label={`${tlEmoji(tlOf(v))} ${label}`} pass={s.pass} warn={s.warn} fail={s.fail} na={s.na} total={v.total} />;
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
          <div style={{ background: "var(--red-soft)", borderRadius: 8, padding: "8px 10px" }}><b style={{ fontSize: 11.5, color: "var(--red-ink)" }}>지금 상태 (as-is)</b><div style={{ fontSize: 12, marginTop: 3 }}>{sel.guide.as_is}</div></div>
          <div style={{ background: "var(--green-soft)", borderRadius: 8, padding: "8px 10px" }}><b style={{ fontSize: 11.5, color: "var(--green-ink)" }}>이렇게 고치세요 (to-be)</b><div style={{ fontSize: 12, marginTop: 3 }}>{sel.guide.to_be}</div>{sel.guide.who !== "-" && <div style={{ fontSize: 11, color: "var(--sec)", marginTop: 4 }}>담당: {sel.guide.who}</div>}</div>
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
          {(sel.parse_errors || []).map((p: any, i: number) => <div key={i} style={{ padding: "4px 8px", margin: "4px 0", borderRadius: 6, background: p.severity === "warn" ? "#FFFBEB" : "var(--red-soft)" }}><b>{p.block}</b> · {p.category}{p.line ? ` · ${p.line}줄 ${p.col}칸` : ""}<div style={{ color: "var(--sec)" }}>{p.msg} — {p.hint}</div></div>)}
          <div style={{ marginTop: 8 }}><b>이 페이지에 있는 스키마</b><div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>{(sel.types || []).map((t: string) => <span key={t} className="badge c6">{t}</span>)}{!(sel.types || []).length && <span style={{ color: "var(--sec)" }}>없음</span>}</div></div>
        </div>
        <div>
          {!!(sel.foreign_refs || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "var(--amber-ink)" }}>다른 국가 주소가 섞인 곳</b>{sel.foreign_refs.map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--sec)" }}>{u}</div>)}</div>}
          {!!(sel.unresolved_refs || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "var(--amber-ink)" }}>정의되지 않은 @id 를 가리킴</b>{sel.unresolved_refs.map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--sec)" }}>{u}</div>)}</div>}
          {!!(sel.duplicate_ids || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "var(--amber-ink)" }}>중복 @id</b>{sel.duplicate_ids.map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--sec)" }}>{u}</div>)}</div>}
          {!!(sel.rich_missing || []).length && <div style={{ marginBottom: 8 }}><b style={{ color: "var(--amber-ink)" }}>Google 리치결과 필수 속성 누락</b>{sel.rich_missing.map((m: any, i: number) => <div key={i} style={{ color: "var(--sec)" }}>{m.type}: {m.missing.join(", ")}{m.id ? ` (${m.id})` : ""}</div>)}</div>}
          {!!(sel.external_refs || []).length && <div><b style={{ color: "var(--sec)" }}>다른 페이지에 정의된 참조(판정 안 함)</b>{sel.external_refs.slice(0, 5).map((u: string) => <div key={u} style={{ wordBreak: "break-all", color: "var(--ter)" }}>{u}</div>)}</div>}
        </div>
      </div>
    </div>
  );
}

/* ── V2 검수 기준 설명 — 공통페이지(Static) QA. Spec/Data QA 패널과 톤·구조 통일 ── */
export function StaticV2Criteria({ show, panelRef }: { show: boolean; panelRef?: any }) {
  if (!show) return null;
  const box = { background: "#F7F9FC", border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px", marginTop: 8 } as const;
  const h = { fontWeight: 800, fontSize: 12.5, marginBottom: 4 } as const;
  const li = { fontSize: 12, color: "var(--sec)", lineHeight: 1.75 } as const;
  return (
    <div ref={panelRef} className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
      <b style={{ fontSize: 14 }}>검수 방식 — 공통페이지</b>
      <p style={{ fontSize: 12.5, color: "var(--sec)", margin: "6px 0 0" }}>
        91개 사이트코드 × 7종 공통 페이지(Home·All about Galaxy·Switch to Galaxy 등)에서 <b>JSON-LD 스키마</b>가 검색엔진에 제대로 읽히는지를 규칙으로만 대조해요.
      </p>
      <div style={box}>
        <div style={h}>사유는 7가지 — 판정은 다른 QA 탭과 같은 4단계(정상 · 확인 · 오류 · 해당없음)</div>
        <div style={li}>
          <div>🟢 <b style={{ color: SEV.pass.ink }}>정상</b> — {HELP["정상"]}</div>
          <div style={{ marginTop: 4 }}>🔴 <b style={{ color: SEV.fail.ink }}>오류</b>(파싱 실패) — 검색엔진이 블록을 아예 못 읽음. <b>수정 필수</b></div>
          <div style={{ marginTop: 4 }}>🟡 <b style={{ color: SEV.warn.ink }}>확인</b>(오적용 · 미해결 참조 · 기타) — 스키마는 읽히지만 참조·속성이 틀림. 점수에서 정상이 아닌 쪽으로 집계</div>
          <div style={{ marginTop: 4 }}>⚪ <b style={{ color: SEV.na.ink }}>해당없음</b>(페이지 없음 · 접근 실패) — 그 국가에 페이지가 없거나 수집 환경 문제. <b>점수 분모에서 제외</b></div>
        </div>
      </div>
      <div style={box}>
        <div style={h}>같은 국가의 언어 변형은 "다른 국가"로 안 봐요</div>
        <div style={li}>ca_fr↔ca, ch_fr↔ch 처럼 sitecodes_master.json 의 언어 변형 그룹이 같으면, 서로의 주소를 참조해도 "오적용"으로 잡지 않아요(예: ca_fr 페이지가 /ca/ 를 참조 — 정상).</div>
      </div>
      <div style={box}>
        <div style={h}>검사 대상 페이지는 계속 늘어날 수 있어요</div>
        <div style={li}>현재 확정 3종(Home·All about Galaxy·Switch to Galaxy) + 후보 4종. 후보는 첫 실행에서 200 응답인 경로를 자동으로 캐시해요 — 다음 실행부터 그 경로로 바로 확인합니다.</div>
      </div>
    </div>
  );
}

/* ── V2 점수 계산 설명 — 공통페이지(Static) QA ── */
export function StaticV2Score({ show, panelRef }: { show: boolean; panelRef?: any }) {
  if (!show) return null;
  const box = { background: "#F7F9FC", border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px", marginTop: 8 } as const;
  const li = { fontSize: 12, color: "var(--sec)", lineHeight: 1.7 } as const;
  return (
    <div ref={panelRef} className="card qbiPopIn" style={{ marginTop: 16, padding: 16 }}>
      <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 4 }}>📊 점수 계산 — 공통페이지</div>
      <div style={box}>
        <div style={{ fontSize: 15, fontWeight: 800 }}>정상률 = 정상 ÷ (정상 + 확인 + 오류) × 100 — 해당없음(페이지없음·접근실패)은 분모에서 제외</div>
        <div style={{ ...li, marginTop: 4 }}>신호등은 Data QA 와 같은 기준 — 정상률 80%↑ 🟢 · 50~79% 🟡 · 미만 🔴. 사이트별(매트릭스 첫 열)·페이지별·권역별 모두 같은 식.</div>
        <div style={{ ...li, marginTop: 6 }}>
          ⚪ 페이지 없음·접근 실패는 <b>분모에서도 빠져요</b> — 그 국가에 해당 페이지가 아예 없거나(콘텐츠 문제 아님) 수집 환경 문제라 콘텐츠 품질과 무관하기 때문이에요.
        </div>
        <div style={{ ...li, marginTop: 6, background: "#fff", border: "1px solid var(--line)", borderRadius: 6, padding: "6px 8px" }}>
          예) 91개 사이트 중 정상 80 · 확인 4 · 오류 2 · 페이지없음 3 · 접근실패 2 → 80 ÷ 86 = <b>93%</b> 정상률 🟢
        </div>
        <div style={{ ...li, marginTop: 4 }}>페이지별(Home·All about Galaxy…) 정상률도 같은 식으로 따로 계산해요 — "페이지·권역별 비율" 카드의 각 막대가 그 결과예요.</div>
      </div>
      <div style={{ fontSize: 11.5, color: "#93540A", marginTop: 8, background: "#FFFAEB", border: "1px solid #FEDF89", borderRadius: 8, padding: "8px 10px" }}>
        ⚠️ 해당없음(페이지없음·접근실패) 비중이 큰 페이지는 정상률(%)만 보면 실제보다 좋아 보일 수 있어요 — 막대의 회색(⚪) 비중도 함께 확인하세요.
      </div>
    </div>
  );
}
