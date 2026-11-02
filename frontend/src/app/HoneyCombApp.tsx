"use client";
/* ════════════════════════════════════════════════════════════════════
   honeyComb 🍯 — Google Shopping 노출 순위 · GMC 보이는 속성 확인  [2026-09 · 목업 v2]
   · 🍎/🐝 와 같은 껍데기(appShell / sidebar / topbar / card / badge)와 토큰(var(--…))을 그대로 사용
   · 탭 3개: 노출 현황(벌집) / 보이는 속성 확인(표) / 키워드 관리
   · 백엔드 /api/hc/* (backend/honeycomb). provider 가 mock → 실수집으로 바뀌어도 화면은 그대로
════════════════════════════════════════════════════════════════════ */
import { Fragment, useEffect, useMemo, useState } from "react";
import { InsightBox } from "./insightUi";
import { Loading, EmptyState, toast } from "./uiShared";
// [2026-11] 용량(47KB) 제한으로 타입·상수·속성 표·Apple 비교 카드·키워드 탭은 honeyCombParts.tsx 로 분리
import {
  type Cell, type Attr, type Keyword, HONEY, HONEY_DARK, STATUS, COLOR, TXT, OBS, akey, hexPts, J, chip, th, td, inp, Badge, Mark,
  AttrTable, AttrValue, AppleCompareCard, KeywordsTab,
} from "./honeyCombParts";


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
  const [loadErr, setLoadErr] = useState("");
  const [kwForm, setKwForm] = useState<Partial<Keyword>>({ type: "brand", subtype: "A1", countries: [], enabled: true });
  const [msg, setMsg] = useState("");
  const [runState, setRunState] = useState<any>(null);
  const [withDetail, setWithDetail] = useState(true);           // [2026-11 D4] 상세 조회 기본 ON(사용자 결정)
  const [appleSel, setAppleSel] = useState<Set<string>>(new Set()); // [2026-11 D3] 비교할 Apple 모델
  const [acct, setAcct] = useState<any>(null);                     // [2026-11 B2] SerpApi 잔여 검색 수
  const loadAcct = async () => { try { setAcct(await (await fetch(api("/api/hc/serpapi/account"))).json()); } catch { /* */ } };
  useEffect(() => { loadAcct(); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);
  const [estimate, setEstimate] = useState<any>(null);
  useEffect(() => { (async () => {
    try {
      const qs = new URLSearchParams({ detail: String(withDetail) });
      Array.from(ctrys).forEach((c) => qs.append("countries", c));
      Array.from(prods).forEach((p) => qs.append("products", p));
      Array.from(appleSel).forEach((m) => qs.append("apple_models", m));
      setEstimate(await (await fetch(api(`/api/hc/run-estimate?${qs.toString()}`))).json());
    } catch { /* */ }
  })(); }, [withDetail, keywords, ctrys, prods, appleSel]);
  const STATUS_X: Record<string, string> = { ...STATUS, error: "조회 실패" };

  const loadKeywords = async () => { try { const d = await (await fetch(api("/api/hc/keywords"))).json(); setKeywords(d.keywords || []); if (d.taxonomy) setTaxonomy(d.taxonomy); } catch { /* */ } };
  useEffect(() => { (async () => {
    try {
      const rc = await fetch(api("/api/hc/config"));
      if (!rc.ok) { setLoadErr(`/api/hc/config → HTTP ${rc.status}`); setOnline(false); return; }
      const c = await rc.json(); setCfg(c); setOnline(true);
      setProds(new Set(c.products.map((p: any) => p.slug))); setCtrys(new Set(c.countries.map((x: any) => x.code))); setAttrProduct(c.products[0]?.slug || "");
      setAttrs((await (await fetch(api("/api/hc/attributes"))).json()).attributes || []);
      const rs = (await (await fetch(api("/api/hc/runs"))).json()).runs || []; setRuns(rs);
      // [2026-10] 과거 run 을 자동으로 열지 않는다 — 사용자가 주차를 고르거나 "최근 결과 열기"(큐비와 동일)
      await loadKeywords();
    } catch (e: any) { setLoadErr(String(e)); setOnline(false); }
  })(); }, [apiBase]);
  useEffect(() => { if (!runId) return; (async () => {
    setRun(await (await fetch(api(`/api/hc/runs/${runId}`))).json());
    const i = runs.findIndex((r) => r.run_id === runId);
    setPrev(i > 0 ? await (await fetch(api(`/api/hc/runs/${runs[i - 1].run_id}`))).json() : null);
  })(); }, [runId, runs]);

  // [2026-09] run 이 하나도 없어도(수집 전) 화면은 뜬다 — 빈 run 으로 렌더
  const runSafe = run || { run_id: "", week: "", at: "", source: "", cells: [] as Cell[] };
  // [2026-11 D3] Apple 비교 셀(keyword_type=competitor)은 벌집·표에서 제외 — Apple 수치는 'Apple 비교' 카드로만 본다
  const allCells: Cell[] = (runSafe.cells || []).filter((c: Cell) => (c.keyword_type || "brand") !== "competitor");
  const cells = useMemo(() => allCells.filter((c) => c.keyword_type === kwType && prods.has(c.product) && ctrys.has(c.country)), [allCells, kwType, prods, ctrys]);
  const cellOf = (country: string, product: string) => {
    if (kwFocus) return allCells.find((c) => c.country === country && c.product === product && c.keyword === kwFocus) || null;
    const r = cells.filter((c) => c.country === country && c.product === product); return r.length ? r.reduce((a, b) => ((a.position ?? 99) <= (b.position ?? 99) ? a : b)) : null;
  };
  const posBadge = (c: Cell | null) => { const st = c?.status || "unchecked"; return <span className="badge" style={{ background: COLOR[st], color: TXT[st], minWidth: 34, justifyContent: "center" }}>{c?.position != null ? `#${c.position}` : STATUS[st]}</span>; };
  const cellsOfPair = (country: string, product: string) => allCells.filter((c) => c.country === country && c.product === product);
  const prevCellOf = (country: string, product: string) => (prev?.cells || []).find((c: Cell) => c.country === country && c.product === product && c.keyword_type === kwType);
  const kwFor = (product: string, country: string) => keywords.filter((k) => k.product === product && k.enabled && (!k.countries.length || k.countries.includes(country)));

  if (online === false) return <div className="appShell"><div style={{ padding: 30, width: "100%" }}><EmptyState tone="error" title="honeyComb 백엔드(/api/hc)에 연결할 수 없습니다" desc={<span>{loadErr} — backend/honeycomb 폴더의 파일이 모두 있는지, 프로그램 로그 창에 오류가 없는지 확인하세요.</span>} action={<button className="btnSecondary" onClick={onHome}>홈으로</button>} /></div></div>;
  if (!cfg) return <div className="appShell"><div style={{ padding: 30, width: "100%" }}><Loading label="honeyComb 불러오는 중…" /></div></div>;

  const cts = cfg.countries.filter((c: any) => ctrys.has(c.code)), prs = cfg.products.filter((p: any) => prods.has(p.slug));
  const checked = cells.filter((c) => ["top1", "topn", "low", "absent"].includes(c.status));
  const top1 = cells.filter((c) => c.status === "top1").length, topn = cells.filter((c) => c.status === "topn").length;
  // [2026-11 D4] '확인 안 함'(상세 미조회)은 분모에서 제외 — 실제로 확인한 속성 중 보이는 비율
  const rates = cells.filter((c) => c.attrs && Object.keys(c.attrs).length).map((c) => { const v = Object.values(c.attrs).filter((x) => x === "entered" || x === "missed"); return v.length ? v.filter((x) => x === "entered").length / v.length : null; }).filter((x): x is number => x != null);
  const stores: Record<string, number> = {}; checked.forEach((c) => { if (c.first_store) stores[c.first_store] = (stores[c.first_store] || 0) + 1; });
  const others = Object.entries(stores).filter(([k]) => !/samsung/i.test(k)).sort((a, b) => b[1] - a[1]);
  const prevTop1 = prev ? (prev.cells || []).filter((c: Cell) => c.keyword_type === kwType && prods.has(c.product) && ctrys.has(c.country) && c.status === "top1").length : null;
  const R = 54, W = Math.sqrt(3) * R, H = 1.5 * R, padL = 160, padT = 60;
  const width = padL + W * (cts.length + 0.5) + 20, height = padT + H * prs.length + R + 10;
  const selCell = sel ? cellOf(sel.country, sel.product) : null;

  const saveKeyword = async () => {
    if (!kwForm.product || !kwForm.text) { setMsg("제품과 키워드를 입력하세요"); return; }
    // [2026-09 신규] 키워드 1개가 늘 때마다 국가 수만큼 SerpApi 호출이 곱절로 늘어나 부하가 커지므로 관리자 비밀번호로 막는다
    const pw = window.prompt("키워드 추가 — 관리자 비밀번호(SerpApi 호출량이 늘어나는 조작입니다)");
    if (pw === null) return;
    const resp = await fetch(api("/api/hc/keywords"), J({ ...kwForm, admin_password: pw }));
    const r = await resp.json().catch(() => ({}));
    if (!resp.ok) { setMsg(r.detail || "저장 실패"); return; }
    setMsg(r.ok ? `저장됨 — ${r.keyword.text}` : "저장 실패"); setKwForm({ type: "brand", subtype: "A1", countries: [], enabled: true, product: kwForm.product }); loadKeywords();
  };
  const removeKeyword = async (id: string) => { await fetch(api("/api/hc/keywords/remove"), J({ id })); loadKeywords(); };
  // [2026-09 신규] 큐비/애플스토커와 동일한 패턴 — 서버가 만든 HTML을 그대로 클립보드에 복사
  const copyEmail = async () => {
    try {
      const r = await fetch(api(`/api/hc/email-html${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`), { cache: "no-store" });
      if (!r.ok) throw new Error(`서버 오류 (${r.status})`);
      const body = await r.text();
      if (navigator.clipboard && "write" in navigator.clipboard && typeof ClipboardItem !== "undefined") {
        await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([body], { type: "text/html" }), "text/plain": new Blob([body], { type: "text/plain" }) })]);
        setMsg("메일 본문 복사됨 — 붙여넣기 🍯");
      } else if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(body); setMsg("메일 본문 복사됨 🍯"); }
      else { const w = window.open("", "_blank"); if (w) { w.document.write(body); w.document.close(); } setMsg("새 탭에서 복사하세요"); }
    } catch (e: any) { setMsg(`메일 복사 실패 — ${e.message || e}`); }
  };
  const toggleKeyword = async (k: Keyword) => { await fetch(api("/api/hc/keywords"), J({ ...k, enabled: !k.enabled })); loadKeywords(); };

  return (
    <div className="appShell">
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🍯 honey<span style={{ color: HONEY }}>C</span>omb</div>
        <div className="brandSub">Google Shopping이라는 벌집 속에서, 우리 제품은 어떤 위치에 있는지 살펴봐요</div>
        <div className={`connBadge ${cfg.provider === "serpapi" ? "ok" : "bad"}`}><span className="connDot" />{cfg.provider === "serpapi" ? "SERP API 연결됨 · 수집 가능" : "SERP API 키 없음 — 저장된 결과만 조회"}</div>
        {/* [2026-11 B2] SerpApi Account API(무료, 월 한도 차감 없음)로 남은 검색 수 표시 */}
        {cfg.provider === "serpapi" && acct && (
          <div style={{ margin: "4px 10px 0", fontSize: 11.5, color: acct.ok ? "var(--label2)" : "var(--sec)" }} title={acct.ok ? `요금제 ${acct.plan || "-"} · 이번 달 사용 ${acct.this_month_usage ?? "-"}회${acct.hourly_limit ? ` · 시간당 한도 ${acct.hourly_limit}회` : ""}` : acct.reason}>
            {acct.ok
              ? <>남은 검색 <b style={{ color: (acct.plan_searches_left ?? acct.total_searches_left ?? 0) < 100 ? "var(--red-ink)" : HONEY_DARK }}>{acct.total_searches_left ?? acct.plan_searches_left ?? "-"}회</b>{acct.searches_per_month ? ` / 월 ${acct.searches_per_month}회` : ""} <span role="button" style={{ cursor: "pointer", color: "var(--blue)" }} onClick={loadAcct}>↻</span></>
              : <>남은 검색 확인 불가 · {acct.reason}</>}
          </div>)}
        <div className="sideScroll">
          <div className="sideLabel">주차(run)</div>
          <div style={{ padding: "0 10px 8px" }}>
            <select value={runId} onChange={(e) => setRunId(e.target.value)} style={{ ...inp, width: "100%" }}>
              <option value="">{runs.length ? `이력 선택 (${runs.length})` : "저장된 이력 없음"}</option>
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
          {!!cfg.competitors?.length && (<>
            <div className="sideLabel" style={{ marginTop: 10 }}>Apple 비교 <span style={{ color: "var(--sec)", fontWeight: 400 }}>— 모델 선택 시 국가당 1회 추가 조회</span></div>
            <div style={{ padding: "0 10px 8px", display: "flex", flexWrap: "wrap", gap: 5 }}>
              {cfg.competitors.map((m: any) => (
                <span key={m.model} style={chip(appleSel.has(m.model))}
                  title={`비교 대상: ${(m.compare_to || []).map((sl: string) => cfg.products.find((p: any) => p.slug === sl)?.label || sl).join(", ")}`}
                  onClick={() => { const s2 = new Set(appleSel); s2.has(m.model) ? s2.delete(m.model) : s2.add(m.model); setAppleSel(s2); }}>{m.model}</span>))}
            </div>
          </>)}
          <div className="sideLabel" style={{ marginTop: 10 }}>노출 상태 범례</div>
          <div style={{ padding: "0 10px 8px", display: "grid", gridTemplateColumns: "14px 1fr", gap: "5px 8px", fontSize: 11.5, color: "var(--label2)", alignItems: "center" }}>
            {Object.keys(STATUS).map((s) => [<i key={s + "i"} style={{ display: "block", width: 14, height: 14, background: COLOR[s], clipPath: "polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%)" }} />, <span key={s}>{STATUS[s]} <span style={{ color: "var(--sec)" }}>— {cfg.status_legend?.[s]}</span></span>])}
          </div>
          <div className="sideLabel" style={{ marginTop: 10 }}>판정 기준</div>
          <p style={{ padding: "0 10px 8px", fontSize: 11.5, color: "var(--sec)", lineHeight: 1.5 }}>1위 = position 1 · 상단 = position ≤ {cfg.top_n}(둘째 줄까지) · gl/hl 지정 · 비로그인 데스크톱. 속성은 검색 결과 카드·제품 상세 창에서 보이는 것만 판정하고, 검색 결과에 아예 나오지 않는 속성은 '확인 불가'로 표시해요. 광고(Sponsored) 카드는 순위 계산에서 제외하고 자연 결과부터 셉니다.</p>
        </div>
        <div className="sideFoot">
          {runState && <button className="btnDanger" onClick={async () => { if (window.confirm("수집을 멈출까요? 지금까지 조회한 결과는 저장됩니다.")) await fetch(api("/api/hc/run/cancel"), J({})); }}>■ 멈춤</button>}
          <button className="btnPrimary" style={{ background: HONEY_DARK }} disabled={cfg.provider !== "serpapi" || !!runState}
            title={cfg.provider !== "serpapi" ? "설정(/desktop/settings)에 SerpApi 키를 넣으면 활성화" : "선택된 국가×제품×사용 중 키워드를 Google Shopping 에서 조회"}
            onClick={async () => {
              const left = acct?.ok ? (acct.total_searches_left ?? acct.plan_searches_left) : null;
              if (!window.confirm(`Google Shopping 조회를 시작합니다.\n예상 API 호출: 검색 ${estimate?.searches ?? "?"}회${estimate?.apple_searches ? ` (Apple ${estimate.apple_searches}회 포함)` : ""}${withDetail ? ` + 상세 최대 ${estimate?.detail_max}회` : ""} (월 한도에서 차감)${left != null ? `\n남은 검색: ${left}회` : ""}\n계속할까요?`)) return;
              const r = await fetch(api("/api/hc/run"), J({ detail: withDetail, countries: Array.from(ctrys), products: Array.from(prods), apple_models: Array.from(appleSel) }));
              if (!r.ok) { setMsg((await r.json()).detail || "실행 실패"); return; }
              setRunState({ running: true, done: 0, total: 0, cells: [] });
              const t = setInterval(async () => {
                const st = await (await fetch(api("/api/hc/run-status"))).json(); setRunState(st);
                if (!st.running) { clearInterval(t); setRunState(null); loadAcct(); if (st.error) setMsg(`수집 실패: ${st.error}`);
                  const rs = (await (await fetch(api("/api/hc/runs"))).json()).runs || []; setRuns(rs); if (rs.length) setRunId(rs[rs.length - 1].run_id); }
              }, 2000);
            }}>{runState ? `수집 중 ${runState.done}/${runState.total}` : "수집 실행"}</button>
          <label className="emailNotice" style={{ display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }} title="공식몰 카드가 잡힌 셀마다 상세 1회 추가 조회(설명·이미지·영상 등 속성 역추적). 호출 수가 최대 2배 · 끄면 상세 창 속성은 '확인 안 함'으로 표시">
            <input type="checkbox" checked={withDetail} onChange={(e) => setWithDetail(e.target.checked)} /> 상세 조회(속성 역추적) 포함
          </label>
          {estimate && <span className="emailNotice">예상 호출 {estimate.searches}회{withDetail ? ` + 상세 최대 ${estimate.detail_max}회` : ""} · 국가 {estimate.countries} × 제품 {estimate.products} × 키워드 {estimate.keywords_enabled}{estimate.apple_models ? ` · Apple ${estimate.apple_models}모델` : ""}</span>}
          <button className="toolBtn" onClick={copyEmail}>✉ 메일 복사</button>
          <a className="btnSecondary" href={api(`/api/hc/report.xlsx?run_id=${runId}`)}>📊 Excel 내려받기</a>
          {cfg.provider !== "serpapi" && <span className="emailNotice">SerpApi 키가 없어 새로 수집할 수 없습니다 — 설정(/desktop/settings)에서 키 입력</span>}
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
            <div className="toolRow"><span style={{ fontSize: 12, color: "var(--sec)" }}>{runSafe.at ? `${runSafe.week} · ${runSafe.at} · ${runSafe.source || ""}` : runs.length ? `이력 ${runs.length}건 — 주차를 선택하세요` : "아직 수집 결과가 없습니다"}</span></div>
          </div>
        </header>

        <div className="contentScroll">
          <div className="panelStack">
            {!run && !runState && (
              runs.length
                ? <EmptyState title="표시할 주차(run)를 선택하세요" desc={`저장된 수집 이력 ${runs.length}건 — 과거 결과는 자동으로 열지 않습니다.`}
                    action={<button className="btnSecondary" onClick={() => setRunId(runs[runs.length - 1].run_id)}>최근 결과 열기 ({runs[runs.length - 1].at})</button>} />
                : <EmptyState title="아직 수집 이력이 없습니다" desc={cfg.provider === "serpapi" ? "왼쪽 아래 \"수집 실행\"을 누르면 Google Shopping 노출 현황을 조회합니다." : "SerpApi 키를 설정하면 수집할 수 있습니다. 다른 PC 에서 내보낸 결과 JSON 은 %APPDATA%\\ABCTool\\hc_runs 에 넣으면 보입니다."} />
            )}
            {runState && (
              <div className="card" style={{ padding: "12px 16px" }}>
                <div style={{ height: 8, background: "var(--gray-soft)", borderRadius: 999, overflow: "hidden" }}><div style={{ height: "100%", width: `${runState.total ? (runState.done / runState.total) * 100 : 0}%`, background: HONEY, transition: "width .3s" }} /></div>
                <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 4 }}>🍯 Google Shopping 조회 중 · {runState.done}/{runState.total} 키워드×국가{runState.cancel ? " · 멈추는 중…" : ""} · SerpApi 호출이 실제로 발생하고 있습니다</div>
                {runState.cells?.length > 0 && (
                  <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
                    <thead><tr><th style={th}>국가</th><th style={th}>제품</th><th style={th}>키워드</th><th style={th}>상태</th><th style={th}>position</th><th style={th}>1위 판매처</th></tr></thead>
                    <tbody>{[...runState.cells].reverse().slice(0, 12).map((c: any, i: number) => (
                      <tr key={i}><td style={td}>{c.country}</td><td style={td}>{cfg.products.find((p: any) => p.slug === c.product)?.label || c.product}</td><td style={td}>{c.keyword}</td>
                        <td style={td}>{c.status === "조회 중" ? <span style={{ color: HONEY_DARK, fontWeight: 700 }}>조회 중…</span> : c.status === "error" ? <span style={{ color: "var(--red-ink)" }}>실패 · {c.error}</span> : <Badge st={c.status} />}</td>
                        <td style={td}>{c.position != null ? `#${c.position}` : "—"}</td><td style={td}>{c.first_store || "—"}</td></tr>))}</tbody>
                  </table>)}
              </div>
            )}
            {tab === "grid" && (<>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
                {[[checked.length ? `${Math.round((100 * top1) / checked.length)}%` : "—", `1위 비율 · ${top1}/${checked.length}칸`, prevTop1 == null ? "" : `지난주 대비 ${prevTop1 > top1 ? "▼" : prevTop1 < top1 ? "▲" : "="} ${Math.abs(top1 - prevTop1)}`],
                  [checked.length ? `${Math.round((100 * (top1 + topn)) / checked.length)}%` : "—", `상단(8위 안) 노출 비율`, ""],
                  [rates.length ? `${Math.round((100 * rates.reduce((a, b) => a + b, 0)) / rates.length)}%` : "—", "검색 결과에서 확인할 수 있는 속성 중 실제로 보이는 비율", ""],
                  // [2026-11 D2] 전체 나열 대신 상위 3곳 + 칸 수, 나머지는 '외 N곳'(마우스 오버로 전체)
                  [others.length ? others.slice(0, 3).map(([k, n]) => `${k} ${n}칸`).join(" · ") + (others.length > 3 ? ` 외 ${others.length - 3}곳` : "") : "없음", "우리 대신 1위에 오른 판매처", ""],
                ].map(([v, l, d], i) => (
                  <div key={i} className="card" style={{ padding: "12px 16px" }}>
                    <div style={{ fontSize: String(v).length > 8 ? 13.5 : 24, fontWeight: 800, lineHeight: 1.15, color: String(v).length > 8 ? HONEY_DARK : "var(--label)" }}>{v}</div>
                    <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 3 }}>{l}</div>
                    {d && <div style={{ fontSize: 11, color: HONEY_DARK, marginTop: 4 }}>{d}</div>}
                  </div>))}
              </div>
              {/* [2026-11 D1] 숫자만이 아니라 '무엇이 부족 → 무엇을 할지' (화면·메일 공통 문장) */}
              {run?.insights && <InsightBox title="이번 주 요약" items={run.insights.top} basis={run.insights.basis} empty="부족·열세 항목 없음" style={{ marginTop: 0, background: "#fff" }} />}
              {run?.insights?.apple && <AppleCompareCard ap={run.insights.apple} />}

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
                      const obs = cell?.attrs ? Object.values(cell.attrs).filter((v) => v === "entered" || v === "missed") : []; const ent = obs.filter((v) => v === "entered").length;
                      return (<g key={c.code} style={{ cursor: "pointer" }} onClick={() => setSel({ country: c.code, product: p.slug })}>
                        <polygon points={hexPts(cx, cy, R - 2)} fill={COLOR[st]} stroke={isSel ? "#111318" : "#fff"} strokeWidth={isSel ? 3 : 2} />
                        {changed && <polygon points={hexPts(cx, cy, R - 2)} fill="none" stroke="#111318" strokeWidth={2} strokeDasharray="4 3" />}
                        {cell?.position != null ? <text x={cx} y={cy - 8} textAnchor="middle" fontSize={24} fontWeight={800} fill={TXT[st]}>#{cell.position}</text>
                          : <text x={cx} y={cy - 6} textAnchor="middle" fontSize={11.5} fontWeight={700} fill={TXT[st]}>{st === "unranked" ? "순위 기록 없음" : st === "absent" ? "미노출" : "아직 조회 안 함"}</text>}
                        {cell?.first_store && <text x={cx} y={cy + 12} textAnchor="middle" fontSize={10.5} fill={TXT[st]}>{/samsung/i.test(cell.first_store) ? "1위 S.com" : `1위 ${cell.first_store.length > 14 ? cell.first_store.slice(0, 13) + "…" : cell.first_store}`}</text>}
                        {obs.length > 0 && <text x={cx} y={cy + 27} textAnchor="middle" fontSize={10} fill={TXT[st]}>속성 {ent}/{obs.length} 보임</text>}
                        <title>{`${c.label} · ${p.label}\n${cell?.keyword || ""}\n${STATUS[st]}`}</title>
                      </g>);
                    })}
                  </g>); })}
                </svg>
                </>)}
                {runSafe.source?.startsWith("mock") && <p style={{ fontSize: 11.5, color: "var(--sec)", margin: "8px 0 0" }}>목업: position은 Final Report의 S.com O/X·1위 판매처를 환산한 값(실측 아님).</p>}
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
                      {kws.map((k) => { const r = pairCells.find((x) => x.keyword === k.text); const obs = r?.attrs ? Object.values(r.attrs).filter((v) => v === "entered" || v === "missed") : [];
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
                  {selCell && selCell.attrs && Object.keys(selCell.attrs).length > 0 ? (() => { const obs = Object.entries(selCell.attrs).filter(([, v]) => v === "entered" || v === "missed"); const na = Object.values(selCell.attrs).filter((v) => v === "na").length; return (<>
                    <b style={{ fontSize: 12.5 }}>보이는 속성 확인 <span style={{ color: "var(--sec)", fontWeight: 500 }}>키워드 “{selCell.keyword}” 결과 카드·제품 상세 창에서 — 보임 <span style={{ color: "#15803D", fontWeight: 700 }}>{obs.filter(([, v]) => v === "entered").length}</span> · 안 보임 <span style={{ color: "var(--red-ink)", fontWeight: 700 }}>{obs.filter(([, v]) => v === "missed").length}</span> / 확인 가능 {obs.length}{na ? ` · 확인 불가 ${na}` : ""}{(() => { const u = Object.values(selCell.attrs).filter((v) => v === "unchecked").length; return u ? ` · 확인 안 함 ${u}(상세 미조회)` : ""; })()}</span></b>
                    <div style={{ height: 8 }} />
                    <AttrTable attrs={attrs} cell={selCell} />
                  </>); })() : selCell?.competitor_benchmark ? (() => { const cb = selCell.competitor_benchmark!; const obs = Object.entries(cb.attrs).filter(([, v]) => v === "entered" || v === "missed"); return (<>
                    <b style={{ fontSize: 12.5, color: "#93540A" }}>⚠ 우리 제품이 안 보여요 — 대신 1위 <span style={{ color: "var(--label)" }}>{cb.merchant}</span>는 이렇게 노출 중</b>
                    <div style={{ fontSize: 11.5, color: "var(--sec)", margin: "2px 0 8px" }}>{cb.title}{cb.price ? ` · ${cb.price}` : ""} — 참고용 벤치마크(추가 조회 없이 카드 정보만)</div>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead><tr><th style={th}>속성</th><th style={th}>노출 여부</th><th style={th}>노출 내용</th></tr></thead>
                      <tbody>{obs.filter(([, v]) => v === "entered").map(([code]) => { const a = attrs.find((x) => akey(x) === code); return (
                        <tr key={code}><td style={td}>{a?.name || code}</td><td style={td}><Mark v="entered" /></td><td style={{ ...td, maxWidth: 320 }}><AttrValue v={cb.attr_values?.[code]} /></td></tr>
                      ); })}</tbody>
                    </table>
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
                          return <td key={c.code} style={{ ...td, textAlign: "center", color: v === "entered" ? "#15803D" : v === "missed" ? "var(--red-ink)" : "var(--ter)", fontWeight: v ? 700 : 400 }} title={`${c.label} · ${v === "entered" ? "보임" : v === "missed" ? "안 보임" : v === "na" ? "확인 불가" : "아직 조회 안 함"}`}>{v === "entered" ? "✓" : v === "missed" ? "✗" : v === "na" ? "—" : "·"}</td>; })}
                      </tr>))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {tab === "keywords" && (<>
              <KeywordsTab cfg={cfg} taxonomy={taxonomy} showTax={showTax} setShowTax={setShowTax} keywords={keywords}
                kwForm={kwForm} setKwForm={setKwForm} msg={msg} toggleKeyword={toggleKeyword}
                saveKeyword={saveKeyword} removeKeyword={removeKeyword} />
            </>)}
          </div>
        </div>
      </div>
    </div>
  );
}

