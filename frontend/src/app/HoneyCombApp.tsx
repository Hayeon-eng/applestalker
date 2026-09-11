"use client";
/* ════════════════════════════════════════════════════════════════════
   honeyComb 🍯 — Google Shopping 노출 순위 · GMC 보이는 속성 확인  [2026-09 · 목업 v2]
   · 🍎/🐝 와 같은 껍데기(appShell / sidebar / topbar / card / badge)와 토큰(var(--…))을 그대로 사용
   · 탭 3개: 노출 현황(벌집) / 보이는 속성 확인(표) / 키워드 관리
   · 백엔드 /api/hc/* (backend/honeycomb). provider 가 mock → 실수집으로 바뀌어도 화면은 그대로
════════════════════════════════════════════════════════════════════ */
import { Fragment, useEffect, useMemo, useState } from "react";

type Cell = { country: string; product: string; keyword: string; keyword_type: string; position: number | null; status: string;
  first_store?: string | null; scom_exposed?: string | null; attrs: Record<string, string>; feed: Record<string, string> };
type Attr = { no: number; sub?: boolean; category: string; name: string; code: string; observe: string };
type Keyword = { id: string; product: string; text: string; type: string; subtype?: string; countries: string[]; enabled: boolean; note?: string };

const HONEY = "#E0A008", HONEY_DARK = "#8A5A00";
const STATUS: Record<string, string> = { top1: "1순위", topn: "상단 노출", low: "8위 밖 노출", absent: "미노출", unranked: "순위 기록 없음", unchecked: "아직 조회 안 함" };
const COLOR: Record<string, string> = { top1: "#2F8F5B", topn: "#E8C547", low: "#E07A1F", absent: "#C0392B", unranked: "#9DB0C4", unchecked: "#E5E7EB", error: "#F3F4F6" };
const TXT: Record<string, string> = { top1: "#fff", topn: "#3A2A0F", low: "#fff", absent: "#fff", unranked: "#fff", unchecked: "#6B7280", error: "#9CA3AF" };
const OBS: Record<string, string> = { card: "검색 결과 카드", detail: "제품 상세 창", feed: "검색 결과에 안 나옴" };
const akey = (a: Attr) => a.code + (a.sub ? `#${a.no}` : "");
const hexPts = (cx: number, cy: number, r: number) =>
  [0, 1, 2, 3, 4, 5].map((i) => { const a = (Math.PI / 180) * (60 * i - 30); return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`; }).join(" ");
const J = (b: any) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
const chip = (on: boolean): React.CSSProperties => ({ fontSize: 12, padding: "4px 10px", borderRadius: 999, cursor: "pointer", border: on ? `1px solid ${HONEY}` : "1px solid var(--line)", background: on ? HONEY : "#fff", color: on ? "#fff" : "var(--label)", fontWeight: on ? 700 : 500 });
const th: React.CSSProperties = { textAlign: "left", fontSize: 11.5, color: "var(--sec)", fontWeight: 600, padding: "6px 8px", borderBottom: "1px solid var(--line)", whiteSpace: "nowrap" };
const td: React.CSSProperties = { fontSize: 12, padding: "6px 8px", borderBottom: "1px solid var(--line)", verticalAlign: "top" };
const inp: React.CSSProperties = { fontSize: 12, padding: "6px 8px", border: "1px solid var(--line)", borderRadius: 6 };
const Badge = ({ st }: { st: string }) => <span className="badge" style={{ background: COLOR[st], color: TXT[st] }}>{STATUS[st] || st}</span>;
const Mark = ({ v }: { v: string }) => v === "entered" ? <span style={{ color: "#15803D", fontWeight: 700 }}>✓ 보임</span> : v === "missed" ? <span style={{ color: "#B42318", fontWeight: 700 }}>✗ 안 보임</span> : <span style={{ color: "var(--ter)" }}>· 확인 불가</span>;

export default function HoneyCombApp({ apiBase, onHome }: { apiBase: string; onHome: () => void }) {
  const api = (p: string) => `${apiBase}${p}`;
  const [cfg, setCfg] = useState<any>(null);
  const [attrs, setAttrs] = useState<Attr[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState<any>(null);
  const [prev, setPrev] = useState<any>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [taxonomy, setTaxonomy] = useState<any>(null);
  const [showTax, setShowTax] = useState(true);
  const [tab, setTab] = useState<"grid" | "attrs" | "keywords">("grid");
  const kwType = "brand"; // [2026-09-11] 제품명 키워드만 사용 — 자연어 키워드 제거
  const [prods, setProds] = useState<Set<string>>(new Set());
  const [ctrys, setCtrys] = useState<Set<string>>(new Set());
  const [sel, setSel] = useState<{ country: string; product: string } | null>(null);
  const [view, setView] = useState<"hex" | "kw">("hex");           // 노출 현황: 제품 벌집 / 키워드별 순위
  const [kwFocus, setKwFocus] = useState<string | null>(null);        // 특정 키워드로 벌집 보기
  const [attrProduct, setAttrProduct] = useState("");
  const [online, setOnline] = useState<boolean | null>(null);
  const [kwForm, setKwForm] = useState<Partial<Keyword>>({ type: "brand", subtype: "A1", countries: [], enabled: true });
  const [msg, setMsg] = useState("");
  const [runState, setRunState] = useState<any>(null);
  const [withDetail, setWithDetail] = useState(false);
  const [estimate, setEstimate] = useState<any>(null);
  useEffect(() => { (async () => { try { setEstimate(await (await fetch(api(`/api/hc/run-estimate?detail=${withDetail}`))).json()); } catch { /* */ } })(); }, [withDetail, keywords]);
  const STATUS_X: Record<string, string> = { ...STATUS, error: "조회 실패" };

  const loadKeywords = async () => { try { const d = await (await fetch(api("/api/hc/keywords"))).json(); setKeywords(d.keywords || []); if (d.taxonomy) setTaxonomy(d.taxonomy); } catch { /* */ } };
  useEffect(() => { (async () => {
    try {
      const c = await (await fetch(api("/api/hc/config"))).json(); setCfg(c); setOnline(true);
      setProds(new Set(c.products.map((p: any) => p.slug))); setCtrys(new Set(c.countries.map((x: any) => x.code))); setAttrProduct(c.products[0]?.slug || "");
      setAttrs((await (await fetch(api("/api/hc/attributes"))).json()).attributes || []);
      const rs = (await (await fetch(api("/api/hc/runs"))).json()).runs || []; setRuns(rs); if (rs.length) setRunId(rs[rs.length - 1].run_id);
      await loadKeywords();
    } catch { setOnline(false); }
  })(); }, [apiBase]);
  useEffect(() => { if (!runId) return; (async () => {
    setRun(await (await fetch(api(`/api/hc/runs/${runId}`))).json());
    const i = runs.findIndex((r) => r.run_id === runId);
    setPrev(i > 0 ? await (await fetch(api(`/api/hc/runs/${runs[i - 1].run_id}`))).json() : null);
  })(); }, [runId, runs]);

  const allCells: Cell[] = run?.cells || [];
  const cells = useMemo(() => allCells.filter((c) => c.keyword_type === kwType && prods.has(c.product) && ctrys.has(c.country)), [allCells, kwType, prods, ctrys]);
  const cellOf = (country: string, product: string) => {
    if (kwFocus) return allCells.find((c) => c.country === country && c.product === product && c.keyword === kwFocus) || null;
    const r = cells.filter((c) => c.country === country && c.product === product); return r.length ? r.reduce((a, b) => ((a.position ?? 99) <= (b.position ?? 99) ? a : b)) : null;
  };
  const posBadge = (c: Cell | null) => { const st = c?.status || "unchecked"; return <span className="badge" style={{ background: COLOR[st], color: TXT[st], minWidth: 34, justifyContent: "center" }}>{c?.position != null ? `#${c.position}` : STATUS[st]}</span>; };
  const cellsOfPair = (country: string, product: string) => allCells.filter((c) => c.country === country && c.product === product);
  const prevCellOf = (country: string, product: string) => (prev?.cells || []).find((c: Cell) => c.country === country && c.product === product && c.keyword_type === kwType);
  const kwFor = (product: string, country: string) => keywords.filter((k) => k.product === product && k.enabled && (!k.countries.length || k.countries.includes(country)));

  if (online === false) return <div className="appShell"><div style={{ padding: 30 }}>honeyComb 백엔드(/api/hc)에 연결할 수 없습니다. <button className="btnSecondary" onClick={onHome}>홈</button></div></div>;
  if (!cfg || !run) return <div className="appShell"><div style={{ padding: 30, color: "var(--sec)" }}>honeyComb 불러오는 중…</div></div>;

  const cts = cfg.countries.filter((c: any) => ctrys.has(c.code)), prs = cfg.products.filter((p: any) => prods.has(p.slug));
  const checked = cells.filter((c) => ["top1", "topn", "low", "absent"].includes(c.status));
  const top1 = cells.filter((c) => c.status === "top1").length, topn = cells.filter((c) => c.status === "topn").length;
  const rates = cells.filter((c) => c.attrs && Object.keys(c.attrs).length).map((c) => { const v = Object.values(c.attrs).filter((x) => x !== "na"); return v.filter((x) => x === "entered").length / v.length; });
  const stores: Record<string, number> = {}; checked.forEach((c) => { if (c.first_store) stores[c.first_store] = (stores[c.first_store] || 0) + 1; });
  const others = Object.entries(stores).filter(([k]) => !/samsung/i.test(k)).sort((a, b) => b[1] - a[1]);
  const prevTop1 = prev ? (prev.cells || []).filter((c: Cell) => c.keyword_type === kwType && prods.has(c.product) && ctrys.has(c.country) && c.status === "top1").length : null;
  const R = 54, W = Math.sqrt(3) * R, H = 1.5 * R, padL = 160, padT = 60;
  const width = padL + W * (cts.length + 0.5) + 20, height = padT + H * prs.length + R + 10;
  const selCell = sel ? cellOf(sel.country, sel.product) : null;

  const saveKeyword = async () => {
    if (!kwForm.product || !kwForm.text) { setMsg("제품과 키워드를 입력하세요"); return; }
    const r = await (await fetch(api("/api/hc/keywords"), J(kwForm))).json();
    setMsg(r.ok ? `저장됨 — ${r.keyword.text}` : "저장 실패"); setKwForm({ type: "brand", subtype: "A1", countries: [], enabled: true, product: kwForm.product }); loadKeywords();
  };
  const removeKeyword = async (id: string) => { await fetch(api("/api/hc/keywords/remove"), J({ id })); loadKeywords(); };
  const toggleKeyword = async (k: Keyword) => { await fetch(api("/api/hc/keywords"), J({ ...k, enabled: !k.enabled })); loadKeywords(); };

  return (
    <div className="appShell">
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🍯 honey<span style={{ color: HONEY }}>C</span>omb</div>
        <div className="brandSub">Google Shopping이라는 벌집 속에서, 우리 제품은 어떤 위치에 있는지 살펴봐요</div>
        <div className={`connBadge ${cfg.provider === "serpapi" ? "ok" : "bad"}`}><span className="connDot" />{cfg.provider === "serpapi" ? "SERP API 연결됨 · 실수집 가능" : "SERP API 키 없음 — 목업만 표시"}</div>
        <div className="sideScroll">
          <div className="sideLabel">주차(run)</div>
          <div style={{ padding: "0 10px 8px" }}>
            <select value={runId} onChange={(e) => setRunId(e.target.value)} style={{ ...inp, width: "100%" }}>
              {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.week} · {r.at}</option>)}
            </select>
          </div>
          <div className="sideLabel">제품</div>
          <div style={{ padding: "0 10px 8px", display: "flex", flexWrap: "wrap", gap: 5 }}>
            {cfg.products.map((p: any) => <span key={p.slug} style={chip(prods.has(p.slug))} onClick={() => { const s = new Set(prods); s.has(p.slug) ? s.delete(p.slug) : s.add(p.slug); setProds(s); }}>{p.label.replace("Galaxy ", "")}</span>)}
          </div>
          <div className="sideLabel">국가</div>
          <div style={{ padding: "0 10px 8px", display: "flex", flexWrap: "wrap", gap: 5 }}>
            {cfg.countries.map((c: any) => <span key={c.code} style={chip(ctrys.has(c.code))} onClick={() => { const s = new Set(ctrys); s.has(c.code) ? s.delete(c.code) : s.add(c.code); setCtrys(s); }}>{c.code}</span>)}
          </div>
          <div className="sideLabel" style={{ marginTop: 10 }}>노출 상태 범례</div>
          <div style={{ padding: "0 10px 8px", display: "grid", gridTemplateColumns: "14px 1fr", gap: "5px 8px", fontSize: 11.5, color: "var(--label2)", alignItems: "center" }}>
            {Object.keys(STATUS).map((s) => [<i key={s + "i"} style={{ display: "block", width: 14, height: 14, background: COLOR[s], clipPath: "polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%)" }} />, <span key={s}>{STATUS[s]} <span style={{ color: "var(--sec)" }}>— {cfg.status_legend?.[s]}</span></span>])}
          </div>
          <div className="sideLabel" style={{ marginTop: 10 }}>판정 기준</div>
          <p style={{ padding: "0 10px 8px", fontSize: 11.5, color: "var(--sec)", lineHeight: 1.5 }}>1위 = position 1 · 상단 = position ≤ {cfg.top_n}(둘째 줄까지) · gl/hl 지정 · 비로그인 데스크톱. 속성은 검색 결과 카드·제품 상세 창에서 보이는 것만 판정하고, 검색 결과에 아예 나오지 않는 속성은 '확인 불가'로 표시해요.</p>
        </div>
        <div className="sideFoot">
          <button className="btnPrimary" style={{ background: HONEY_DARK }} disabled={cfg.provider !== "serpapi" || !!runState}
            title={cfg.provider !== "serpapi" ? "설정(/desktop/settings)에 SerpApi 키를 넣으면 활성화" : "국가×제품×사용 중 키워드 전체를 Google Shopping 에서 조회"}
            onClick={async () => {
              if (!window.confirm(`Google Shopping 조회를 시작합니다.\n예상 API 호출: 검색 ${estimate?.searches ?? "?"}회${withDetail ? ` + 상세 최대 ${estimate?.detail_max}회` : ""} (월 한도에서 차감)\n계속할까요?`)) return;
              const r = await fetch(api("/api/hc/run"), J({ detail: withDetail }));
              if (!r.ok) { setMsg((await r.json()).detail || "실행 실패"); return; }
              const t = setInterval(async () => {
                const st = await (await fetch(api("/api/hc/run-status"))).json(); setRunState(st);
                if (!st.running) { clearInterval(t); setRunState(null); if (st.error) setMsg(`수집 실패: ${st.error}`);
                  const rs = (await (await fetch(api("/api/hc/runs"))).json()).runs || []; setRuns(rs); if (rs.length) setRunId(rs[rs.length - 1].run_id); }
              }, 2000);
            }}>{runState ? `수집 중 ${runState.done}/${runState.total}` : "수집 실행"}</button>
          <label className="emailNotice" style={{ display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }} title="우리 카드가 잡힌 셀마다 상세 1회 추가 조회(설명·이미지·영상 등 속성 역추적). 호출 수가 최대 2배">
            <input type="checkbox" checked={withDetail} onChange={(e) => setWithDetail(e.target.checked)} /> 상세 조회(속성 역추적) 포함
          </label>
          {estimate && <span className="emailNotice">예상 호출 {estimate.searches}회{withDetail ? ` + 상세 최대 ${estimate.detail_max}회` : ""} · 국가 {estimate.countries} × 제품 {estimate.products} × 키워드 {estimate.keywords_enabled}</span>}
          <a className="btnSecondary" href={api(`/api/hc/report.xlsx?run_id=${runId}`)}>Excel 내려받기</a>
          {cfg.provider !== "serpapi" && <span className="emailNotice">SerpApi 키가 없어 목업 데이터만 보입니다 — 설정에서 키 입력</span>}
          {msg && <span className="emailNotice" style={{ color: HONEY_DARK }}>{msg}</span>}
        </div>
      </aside>

      <div className="mainArea">
        <header className="topbar">
          <div className="topbarRow1">
            <div className="tabGroup">
              <button className={`tabBtn ${tab === "grid" ? "on" : ""}`} onClick={() => setTab("grid")}>노출 현황</button>
              <button className={`tabBtn ${tab === "attrs" ? "on" : ""}`} onClick={() => setTab("attrs")}>보이는 속성 확인</button>
              <button className={`tabBtn ${tab === "keywords" ? "on" : ""}`} onClick={() => setTab("keywords")}>키워드 관리 <span style={{ color: "var(--sec)", fontWeight: 500 }}>{keywords.length}</span></button>
            </div>
            <div className="toolRow"><span style={{ fontSize: 12, color: "var(--sec)" }}>{run.week} · {run.at} · {run.source?.startsWith("mock") ? "목업 데이터(Final Report 7/23·7/27 이관)" : run.source}</span></div>
          </div>
        </header>

        <div className="contentScroll">
          <div className="panelStack">
            {tab === "grid" && (<>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
                {[[checked.length ? `${Math.round((100 * top1) / checked.length)}%` : "—", `1위 비율 · ${top1}/${checked.length}칸`, prevTop1 == null ? "" : `지난주 대비 ${prevTop1 > top1 ? "▼" : prevTop1 < top1 ? "▲" : "="} ${Math.abs(top1 - prevTop1)}`],
                  [checked.length ? `${Math.round((100 * (top1 + topn)) / checked.length)}%` : "—", `상단(8위 안) 노출 비율`, ""],
                  [rates.length ? `${Math.round((100 * rates.reduce((a, b) => a + b, 0)) / rates.length)}%` : "—", "검색 결과에서 확인할 수 있는 속성 중 실제로 보이는 비율", ""],
                  [others.length ? others.map(([k]) => k).join(" · ") : "없음", "우리 대신 1위에 오른 판매처", ""],
                ].map(([v, l, d], i) => (
                  <div key={i} className="card" style={{ padding: "12px 16px" }}>
                    <div style={{ fontSize: String(v).length > 8 ? 13.5 : 24, fontWeight: 800, lineHeight: 1.15, color: String(v).length > 8 ? HONEY_DARK : "var(--label)" }}>{v}</div>
                    <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 3 }}>{l}</div>
                    {d && <div style={{ fontSize: 11, color: HONEY_DARK, marginTop: 4 }}>{d}</div>}
                  </div>))}
              </div>

              <div className="card">
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                  <div className="tabGroup"><button className={`tabBtn ${view === "hex" ? "on" : ""}`} onClick={() => setView("hex")}>제품 벌집</button><button className={`tabBtn ${view === "kw" ? "on" : ""}`} onClick={() => setView("kw")}>키워드별 순위</button></div>
                  {view === "hex" && (<>
                    <select value={kwFocus || ""} onChange={(e) => setKwFocus(e.target.value || null)} style={inp} title="특정 키워드 하나로 벌집을 봅니다. 비우면 유형 안에서 가장 좋은 결과">
                      <option value="">키워드: 제품별 가장 잘 나온 결과</option>
                      {keywords.filter((k) => k.enabled && prods.has(k.product)).map((k) => <option key={k.id} value={k.text}>{k.subtype} · {k.text}</option>)}
                    </select>
                    <span style={{ fontSize: 12, color: "var(--sec)" }}>큰 숫자 = 우리 리스팅 position · 아랫줄 = 1위 판매처 · 셀을 누르면 상세</span>
                  </>)}
                  {view === "kw" && <span style={{ fontSize: 12, color: "var(--sec)" }}>키워드 한 줄 = 국가별 position. #1 = 1순위, #2~{cfg.top_n} = 상단, 미노출/아직 조회 안 함는 글자로</span>}
                </div>
                {view === "kw" && (
                  <div style={{ overflowX: "auto", marginBottom: 6 }}>
                    <table style={{ borderCollapse: "collapse", minWidth: 760 }}>
                      <thead><tr><th style={th}>제품</th><th style={th}>키워드</th><th style={th}>유형</th>{cts.map((c: any) => <th key={c.code} style={{ ...th, textAlign: "center" }}>{c.code}</th>)}<th style={th}></th></tr></thead>
                      <tbody>
                        {prs.map((p: any) => keywords.filter((k) => k.product === p.slug && k.enabled).sort((a, b) => (a.subtype || "").localeCompare(b.subtype || "")).map((k) => (
                          <tr key={k.id}>
                            <td style={td}>{p.label}</td><td style={td}>{k.text}</td>
                            <td style={td}><span className="badge samsung">{k.subtype}</span></td>
                            {cts.map((c: any) => { const cell = allCells.find((x) => x.country === c.code && x.product === p.slug && x.keyword === k.text) || null; const applicable = !k.countries.length || k.countries.includes(c.code);
                              return <td key={c.code} style={{ ...td, textAlign: "center" }} title={cell ? `${STATUS[cell.status]}${cell.first_store ? ` · 1위 ${cell.first_store}` : ""}` : "아직 조회 안 함"}>{applicable ? posBadge(cell) : <span style={{ color: "var(--ter)" }}>—</span>}</td>; })}
                            <td style={td}><span role="button" style={{ cursor: "pointer", color: "var(--blue)", fontSize: 11.5 }} onClick={() => { setKwFocus(k.text); setView("hex"); }}>벌집으로</span></td>
                          </tr>)))}
                      </tbody>
                    </table>
                  </div>
                )}
                {view === "hex" && (<>
                <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ maxHeight: 600, display: "block" }}>
                  {cts.map((c: any, i: number) => { const x = padL + W * (i + 0.5) + W / 4; return (<g key={c.code}>
                    <text x={x} y={22} textAnchor="middle" fontSize={14} fontWeight={800} fill="#111318">{c.code}</text>
                    <text x={x} y={38} textAnchor="middle" fontSize={10.5} fill="#6B7280">{c.label}</text></g>); })}
                  {prs.map((p: any, ri: number) => { const cy = padT + H * ri + R, off = ri % 2 ? W / 2 : 0; return (<g key={p.slug}>
                    <text x={padL - 12} y={cy + 4} textAnchor="end" fontSize={12} fontWeight={700} fill="#374151">{p.label}</text>
                    {cts.map((c: any, ci: number) => {
                      const cx = padL + W * (ci + 0.5) + off; const cell = cellOf(c.code, p.slug); const st = cell?.status || "unchecked";
                      const pc = prevCellOf(c.code, p.slug); const changed = cell && pc && pc.status !== cell.status; const isSel = sel?.country === c.code && sel?.product === p.slug;
                      const obs = cell?.attrs ? Object.values(cell.attrs).filter((v) => v !== "na") : []; const ent = obs.filter((v) => v === "entered").length;
                      return (<g key={c.code} style={{ cursor: "pointer" }} onClick={() => setSel({ country: c.code, product: p.slug })}>
                        <polygon points={hexPts(cx, cy, R - 2)} fill={COLOR[st]} stroke={isSel ? "#111318" : "#fff"} strokeWidth={isSel ? 3 : 2} />
                        {changed && <polygon points={hexPts(cx, cy, R - 2)} fill="none" stroke="#111318" strokeWidth={2} strokeDasharray="4 3" />}
                        {cell?.position != null ? <text x={cx} y={cy - 8} textAnchor="middle" fontSize={24} fontWeight={800} fill={TXT[st]}>#{cell.position}</text>
                          : <text x={cx} y={cy - 6} textAnchor="middle" fontSize={11.5} fontWeight={700} fill={TXT[st]}>{st === "unranked" ? "순위 기록 없음" : st === "absent" ? "미노출" : "아직 조회 안 함"}</text>}
                        {cell?.first_store && <text x={cx} y={cy + 12} textAnchor="middle" fontSize={10.5} fill={TXT[st]}>{/samsung/i.test(cell.first_store) ? "1위 S.com" : `1위 ${cell.first_store}`}</text>}
                        {obs.length > 0 && <text x={cx} y={cy + 27} textAnchor="middle" fontSize={10} fill={TXT[st]}>속성 {ent}/{obs.length} 보임</text>}
                        <title>{`${c.label} · ${p.label}\n${cell?.keyword || ""}\n${STATUS[st]}`}</title>
                      </g>);
                    })}
                  </g>); })}
                </svg>
                </>)}
                {run.source?.startsWith("mock") && <p style={{ fontSize: 11.5, color: "var(--sec)", margin: "8px 0 0" }}>목업: position은 Final Report의 S.com O/X·1위 판매처를 환산한 값(실측 아님). </p>}
              </div>

              {sel && (() => {
                const c = cfg.countries.find((x: any) => x.code === sel.country), p = cfg.products.find((x: any) => x.slug === sel.product);
                const pairCells = cellsOfPair(sel.country, sel.product); const kws = kwFor(sel.product, sel.country);
                return (<div className="card qbiPopIn">
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
                    <b style={{ fontSize: 14 }}>{p.label} · {c.label}</b><span style={{ fontSize: 12, color: "var(--sec)" }}>gl={c.gl} hl={c.hl}</span>
                    <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--sec)", cursor: "pointer" }} onClick={() => setSel(null)}>닫기 ✕</span>
                  </div>
                  <b style={{ fontSize: 12.5 }}>키워드별 결과 <span style={{ color: "var(--sec)", fontWeight: 500 }}>{kws.length}개 등록</span></b>
                  <table style={{ width: "100%", borderCollapse: "collapse", margin: "6px 0 14px" }}>
                    <thead><tr><th style={th}>키워드</th><th style={th}>유형</th><th style={th}>상태</th><th style={th}>position</th><th style={th}>1위 판매처</th><th style={th}>S.com</th><th style={th}>보이는 속성(보임/확인 가능)</th></tr></thead>
                    <tbody>
                      {kws.map((k) => { const r = pairCells.find((x) => x.keyword === k.text); const obs = r?.attrs ? Object.values(r.attrs).filter((v) => v !== "na") : [];
                        return (<tr key={k.id}><td style={td}>{k.text}</td><td style={td}>{k.subtype || "A1"}</td><td style={td}><Badge st={r?.status || "unchecked"} /></td>
                          <td style={td}>{r?.position != null ? `#${r.position}` : "—"}</td><td style={td}>{r?.first_store || "—"}</td><td style={td}>{r?.scom_exposed || "—"}</td>
                          <td style={td}>{obs.length ? `${obs.filter((v) => v === "entered").length}/${obs.length}` : "—"}</td></tr>); })}
                    </tbody>
                  </table>
                  {selCell && (selCell as any).items_top?.length > 0 && (<>
                    <b style={{ fontSize: 12.5 }}>검색 결과 상위 {(selCell as any).items_top.length}개 <span style={{ color: "var(--sec)", fontWeight: 500 }}>키워드 “{selCell.keyword}” · 실제 Google Shopping 카드 순서</span></b>
                    <table style={{ width: "100%", borderCollapse: "collapse", margin: "6px 0 14px" }}>
                      <thead><tr><th style={th}>#</th><th style={th}>제품명(카드 제목)</th><th style={th}>판매처</th><th style={th}>가격</th><th style={th}></th></tr></thead>
                      <tbody>{(selCell as any).items_top.map((it: any) => (<tr key={it.position} style={{ background: it.is_samsung_store ? "var(--low-soft)" : undefined }}>
                        <td style={td}>#{it.position}</td><td style={td}>{it.title}</td><td style={td}>{it.merchant}</td><td style={td}>{it.price || "—"}</td>
                        <td style={td}>{it.is_samsung_store ? <span className="badge samsung">우리 스토어</span> : ""}</td></tr>))}</tbody>
                    </table>
                  </>)}
                  {selCell && selCell.attrs && Object.keys(selCell.attrs).length > 0 ? (() => { const obs = Object.entries(selCell.attrs).filter(([, v]) => v !== "na"); const na = Object.values(selCell.attrs).filter((v) => v === "na").length; return (<>
                    <b style={{ fontSize: 12.5 }}>보이는 속성 확인 <span style={{ color: "var(--sec)", fontWeight: 500 }}>키워드 “{selCell.keyword}” 결과 카드·제품 상세 창에서 — 보임 <span style={{ color: "#15803D", fontWeight: 700 }}>{obs.filter(([, v]) => v === "entered").length}</span> · 안 보임 <span style={{ color: "#B42318", fontWeight: 700 }}>{obs.filter(([, v]) => v === "missed").length}</span> / 확인 가능 {obs.length}{na ? ` · 확인 불가 ${na}` : ""}</span></b>
                    <div style={{ height: 8 }} />
                    <AttrTable attrs={attrs} cell={selCell} />
                  </>); })() : <p style={{ fontSize: 12, color: "var(--sec)" }}>보이는 속성 확인 결과가 없습니다(수집 시 채워집니다).</p>}
                </div>);
              })()}
            </>)}

            {tab === "attrs" && (
              <div className="card">
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
                  <b style={{ fontSize: 14 }}>보이는 속성 확인 — 국가 비교</b>
                  <div style={{ display: "flex", gap: 5 }}>{cfg.products.map((p: any) => <span key={p.slug} style={chip(attrProduct === p.slug)} onClick={() => setAttrProduct(p.slug)}>{p.label.replace("Galaxy ", "")}</span>)}</div>
                  <span style={{ fontSize: 11.5, color: "var(--sec)", marginLeft: "auto" }}>✓ 화면에 보임 · ✗ 안 보임 · — 검색 결과에서는 볼 수 없는 속성 · 기준 키워드: {kwFocus || "제품별 가장 잘 나온 결과"}</span>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ borderCollapse: "collapse", minWidth: 760 }}>
                    <thead><tr><th style={th}>#</th><th style={th}>카테고리</th><th style={th}>속성</th><th style={th}>보이는 곳</th>{cts.map((c: any) => <th key={c.code} style={{ ...th, textAlign: "center" }}>{c.code}</th>)}</tr></thead>
                    <tbody>
                      {attrs.map((a) => (<tr key={akey(a)}>
                        <td style={{ ...td, color: "var(--sec)" }}>{a.no}{a.sub ? "·" : ""}</td><td style={{ ...td, color: "var(--sec)" }}>{a.category}</td><td style={td}>{a.name}</td><td style={{ ...td, color: "var(--sec)" }}>{OBS[a.observe]}</td>
                        {cts.map((c: any) => { const cell = cellOf(c.code, attrProduct); const v = cell?.attrs?.[akey(a)] || (a.observe === "feed" ? "na" : "");
                          return <td key={c.code} style={{ ...td, textAlign: "center", color: v === "entered" ? "#15803D" : v === "missed" ? "#B42318" : "var(--ter)", fontWeight: v ? 700 : 400 }} title={`${c.label} · ${v === "entered" ? "보임" : v === "missed" ? "안 보임" : v === "na" ? "확인 불가" : "아직 조회 안 함"}`}>{v === "entered" ? "✓" : v === "missed" ? "✗" : v === "na" ? "—" : "·"}</td>; })}
                      </tr>))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {tab === "keywords" && (<>
              {taxonomy && (
                <div className="card" style={{ padding: "14px 20px" }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                    <b style={{ fontSize: 14 }}>키워드 분류 기준</b>
                    <span style={{ fontSize: 12, color: "var(--sec)" }}>제품명 키워드만 사용합니다 — "우리 제품이 1위여야 하는 검색어". 제품당 1~2개(1개 추가 = 국가 수만큼 API 호출 증가)</span>
                    <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--blue)", cursor: "pointer" }} onClick={() => setShowTax((v) => !v)}>{showTax ? "접기" : "펼치기"}</span>
                  </div>
                  {showTax && (<>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 14, marginTop: 10 }}>
                      {(["brand"] as const).filter((k) => taxonomy[k]).map((k) => { const t = taxonomy[k]; return (
                        <div key={k} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "10px 14px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}><span className="badge samsung">A</span><b style={{ fontSize: 13 }}>{t.label}</b></div>
                          <div style={{ fontSize: 12, color: "var(--label2)", margin: "6px 0 2px" }}><b>목적·KPI</b> — {t.goal}</div>
                          <div style={{ fontSize: 12, color: "var(--label2)", marginBottom: 8 }}><b>분류 규칙</b> — {t.rule}</div>
                          <table style={{ width: "100%", borderCollapse: "collapse" }}><tbody>
                            {Object.entries(t.subtypes || {}).map(([code, st]: any) => (
                              <tr key={code}><td style={{ ...td, whiteSpace: "nowrap", fontWeight: 700, color: "var(--label2)" }}>{code} {st.label}</td><td style={{ ...td, color: "var(--sec)" }}>{st.desc}</td><td style={{ ...td, fontStyle: "italic" }}>{st.ex}</td></tr>))}
                          </tbody></table>
                        </div>); })}
                    </div>
                    <div style={{ marginTop: 10, fontSize: 12, color: "var(--label2)" }}><b>작성 규칙</b>
                      <ul style={{ margin: "4px 0 0 16px", padding: 0, lineHeight: 1.6 }}>{(taxonomy.writing_rules || []).map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
                    </div>
                  </>)}
                </div>
              )}
              <div className="card">
                <b style={{ fontSize: 14 }}>키워드 추가 · 수정</b>
                <p style={{ fontSize: 12, color: "var(--sec)", margin: "4px 0 10px" }}>제품별 Google Shopping 검색어(제품명 키워드)를 관리합니다. 제품당 사용 중 키워드는 2개까지 — 키워드 1개가 늘면 국가 수(6)만큼 API 호출이 늘어납니다. 국가를 비우면 전 국가에 적용됩니다.</p>
                <div style={{ display: "grid", gridTemplateColumns: "150px 1fr 190px 200px 1fr auto", gap: 8, alignItems: "center" }}>
                  <select value={kwForm.product || ""} onChange={(e) => setKwForm({ ...kwForm, product: e.target.value })} style={inp}>
                    <option value="">제품 선택</option>{cfg.products.map((p: any) => <option key={p.slug} value={p.slug}>{p.label}</option>)}
                  </select>
                  <input value={kwForm.text || ""} onChange={(e) => setKwForm({ ...kwForm, text: e.target.value })} placeholder='검색어 (예: "best foldable phone for multitasking")' style={inp} />
                  <select value={kwForm.subtype || "A1"} onChange={(e) => setKwForm({ ...kwForm, subtype: e.target.value, type: "brand" })} style={inp} title="제품명 키워드만 등록할 수 있습니다">
                    {taxonomy?.brand ? Object.entries(taxonomy.brand.subtypes || {}).map(([code, st]: any) => <option key={code} value={code}>{code} {st.label}</option>)
                      : <><option value="A1">A1 정식 제품명</option><option value="A2">A2 제품명 + 사양/변형</option><option value="A3">A3 제품명 + 구매 의도</option></>}
                  </select>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>{cfg.countries.map((c: any) => { const on = (kwForm.countries || []).includes(c.code); return <span key={c.code} style={{ ...chip(on), fontSize: 11, padding: "2px 7px" }} onClick={() => setKwForm({ ...kwForm, countries: on ? (kwForm.countries || []).filter((x) => x !== c.code) : [...(kwForm.countries || []), c.code] })}>{c.code}</span>; })}</div>
                  <input value={kwForm.note || ""} onChange={(e) => setKwForm({ ...kwForm, note: e.target.value })} placeholder="메모(선택)" style={inp} />
                  <button className="btnPrimary" style={{ background: HONEY_DARK, padding: "7px 14px" }} onClick={saveKeyword}>저장</button>
                </div>
                {msg && <p style={{ fontSize: 12, color: HONEY_DARK, marginTop: 8 }}>{msg}</p>}
              </div>
              <div className="card">
                <b style={{ fontSize: 14 }}>등록된 키워드 <span style={{ color: "var(--sec)", fontWeight: 500 }}>{keywords.length}개 · 사용 중 {keywords.filter((k) => k.enabled).length}</span></b>
                <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
                  <thead><tr><th style={th}>제품</th><th style={th}>키워드</th><th style={th}>유형</th><th style={th}>국가</th><th style={th}>상태</th><th style={th}>메모</th><th style={th}></th></tr></thead>
                  <tbody>
                    {[...keywords].sort((a, b) => a.product.localeCompare(b.product) || a.type.localeCompare(b.type)).map((k) => (<tr key={k.id} style={{ opacity: k.enabled ? 1 : 0.5 }}>
                      <td style={td}>{cfg.products.find((p: any) => p.slug === k.product)?.label || k.product}</td><td style={td}>{k.text}</td>
                      <td style={td}><span className="badge samsung" title={taxonomy?.brand?.subtypes?.[k.subtype || ""]?.desc || ""}>{k.subtype || "A"} · {taxonomy?.brand?.subtypes?.[k.subtype || ""]?.label || "제품명"}</span></td>
                      <td style={td}>{k.countries?.length ? k.countries.join(", ") : "전 국가"}</td>
                      <td style={td}><span role="button" style={{ cursor: "pointer", color: k.enabled ? "#15803D" : "var(--sec)", fontWeight: 600 }} onClick={() => toggleKeyword(k)}>{k.enabled ? "사용 중" : "꺼짐"}</span></td>
                      <td style={{ ...td, color: "var(--sec)" }}>{k.note || ""}</td>
                      <td style={td}><span role="button" style={{ cursor: "pointer", color: "var(--sec)", marginRight: 10 }} onClick={() => setKwForm({ ...k })}>수정</span><span role="button" style={{ cursor: "pointer", color: "var(--high)" }} onClick={() => removeKeyword(k.id)}>삭제</span></td>
                    </tr>))}
                  </tbody>
                </table>
              </div>
            </>)}
          </div>
        </div>
      </div>
    </div>
  );
}

function AttrTable({ attrs, cell }: { attrs: Attr[]; cell: Cell }) {
  const cats = [...new Set(attrs.map((a) => a.category))];
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead><tr><th style={th}>#</th><th style={th}>속성</th><th style={th}>보이는 곳</th><th style={th}>화면</th></tr></thead>
      <tbody>
        {cats.map((cat) => (<Fragment key={cat}>
          <tr><td colSpan={4} style={{ ...td, background: "var(--rail)", fontWeight: 700, fontSize: 11.5, color: "var(--label2)" }}>{cat}</td></tr>
          {attrs.filter((a) => a.category === cat).map((a) => { const v = cell.attrs[akey(a)] || "na";
            return (<tr key={akey(a)} style={{ background: v === "missed" ? "var(--high-soft)" : undefined }}>
              <td style={{ ...td, color: "var(--sec)" }}>{a.no}{a.sub ? "·" : ""}</td><td style={td}>{a.name}</td><td style={{ ...td, color: "var(--sec)" }}>{OBS[a.observe]}</td>
              <td style={td}><Mark v={v} /></td>
            </tr>); })}
        </Fragment>))}
      </tbody>
    </table>
  );
}
