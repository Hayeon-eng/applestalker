"use client";
/**
 * QubiApp.tsx — 큐비 🐝 (QA Bee) 독립 앱
 * 탭: [스키마 QA] [스펙 QA] · 제품×페이지타입 선택 · 입력 3종(붙여넣기/파일/링크)
 * 스펙 관리(메인 표) · 스키마 룰 추가(타입 드롭다운) · Quick View + 권역 신호등
 */
import { useEffect, useMemo, useRef, useState } from "react";

type Finding = { status: "pass" | "warn" | "fail" | "na"; as_is?: string; to_be?: string; block?: string; token?: string; category?: string; kind?: string };
type PageResult = { sitecode: string; url: string; region?: string; country?: string; page_type?: string;
  schema: { findings: Finding[] }; copy: { findings: Finding[] } };
type SiteRow = { sitecode: string; country?: string; lang?: string; url: string };
type CatalogItem = { category: string; label: string; ex_value: string; ex_unit: string };
type Product = { code: string; label: string };

const SEV = { fail: { ko: "오류", c: "#D8362F" }, warn: { ko: "확인", c: "#E0A008" }, pass: { ko: "정상", c: "#1F9E5C" }, na: { ko: "해당없음", c: "#98A2B3" } } as const;
const HONEY = "#E0A008";
const PAGE_TYPES = ["PDP", "Compare", "Buying"];
// 마케팅 제품 → 스키마 룰 패밀리(M3=폰 계열 / M12=버즈 계열)
const family = (code: string) => (code || "").includes("buds") ? "M12" : "M3";

export default function QubiApp({ apiBase = "", onHome }: { apiBase?: string; onHome?: () => void }) {
  const [tab, setTab] = useState<"schema" | "copy">("schema");
  const [product, setProduct] = useState("galaxy-s26-ultra");
  const [pageType, setPageType] = useState("PDP");
  const [inputMode, setInputMode] = useState<"paste" | "file" | "url">("paste");
  const [html, setHtml] = useState("");
  const [urlOne, setUrlOne] = useState("");
  const [results, setResults] = useState<PageResult[]>([]);
  const [rules, setRules] = useState<any>(null);
  const [showRules, setShowRules] = useState(false);
  const [showRuleAdd, setShowRuleAdd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [online, setOnline] = useState<boolean | null>(null);

  const [regionsMap, setRegionsMap] = useState<Record<string, SiteRow[]>>({});
  const [region, setRegion] = useState<string>("전체");
  const [progress, setProgress] = useState({ active: false, done: 0, total: 0, label: "" });

  const [sitesOpen, setSitesOpen] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const htmlFileRef = useRef<HTMLInputElement>(null);
  const xlsxFileRef = useRef<HTMLInputElement>(null);

  // 스펙 관리
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [specProduct, setSpecProduct] = useState("galaxy-s26-ultra");
  const [specs, setSpecs] = useState<any[]>([]);
  const [newProd, setNewProd] = useState("");
  const [specForm, setSpecForm] = useState({ category: "", value: "", unit: "" });
  const [schemaTypes, setSchemaTypes] = useState<string[]>([]);
  const [ruleForm, setRuleForm] = useState({ block_type: "", property: "", value: "", value_kind: "exists", nested: "", kind: "spec", token: "" });

  // Quick View
  const [quickOpen, setQuickOpen] = useState(false);
  const [qCountry, setQCountry] = useState("전체");
  const [qDetail, setQDetail] = useState<string | null>(null);

  // 검수 이력
  const [history, setHistory] = useState<any[]>([]);

  const api = (p: string) => `${apiBase}${p}`;
  const flash = (m: string) => { setOk(m); setTimeout(() => setOk(""), 2500); };
  const J = (b: any) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });

  useEffect(() => {
    fetch(api("/api/health")).then((r) => setOnline(r.ok)).catch(() => setOnline(false));
    loadSites(); loadCatalog(); loadProducts(); loadSpecs("galaxy-s26-ultra"); loadHistory();
  }, []);
  useEffect(() => { loadRules(); setSpecProduct(product); }, [product, pageType]);
  useEffect(() => { loadSpecs(specProduct); }, [specProduct]);

  async function loadSites() { try { setRegionsMap((await (await fetch(api("/api/qb/sites"))).json()).regions || {}); } catch { /* */ } }
  async function loadCatalog() { try { setCatalog((await (await fetch(api("/api/qb/spec-catalog"))).json()).catalog || []); } catch { /* */ } }
  async function loadProducts() { try { setProducts((await (await fetch(api("/api/qb/products"))).json()).products || []); } catch { /* */ } }
  async function loadSpecs(p: string) { try { setSpecs((await (await fetch(api(`/api/qb/specs?product=${encodeURIComponent(p)}`))).json()).specs || []); } catch { /* */ } }
  async function loadRules() {
    try { const d = await (await fetch(api(`/api/qb/rules?product=${family(product)}&page_type=${pageType}`))).json(); setRules(d); if (d.schema_types) setSchemaTypes(d.schema_types); } catch (e: any) { setErr(String(e)); }
  }
  async function loadHistory() { try { setHistory((await (await fetch(api("/api/qb/history"))).json()).history || []); } catch { /* */ } }
  const openHistory = async (id: string) => {
    try { const d = await (await fetch(api(`/api/qb/history/${id}`))).json(); setResults(d.results || []); flash(`이력 ${id} 불러옴`); }
    catch { setErr("이력 불러오기 실패"); }
  };
  const removeHistory = async (id: string) => { await fetch(api("/api/qb/history/remove"), J({ run_id: id })); loadHistory(); };

  const allSites = useMemo(() => Object.values(regionsMap).flat(), [regionsMap]);
  const regionNames = useMemo(() => Object.keys(regionsMap), [regionsMap]);

  // ── 검수 ──
  const doCheck = async () => {
    setBusy(true); setErr("");
    try {
      if (inputMode === "url") {
        if (!urlOne.trim()) throw new Error("검수할 링크를 입력하세요.");
        const r = await fetch(api("/api/qb/check-url"), J({ url: urlOne.trim(), product: family(product), market_product: product, page_type: pageType }));
        if (r.status === 501) throw new Error("크롤러 미연결 — 붙여넣기/파일 검수를 이용하세요.");
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `검수 실패 (${r.status})`);
        setResults([await r.json()]);
      } else {
        if (!html.trim()) throw new Error("검수할 HTML을 넣으세요.");
        const r = await fetch(api("/api/qb/check"), J({ html, product: family(product), market_product: product, page_type: pageType }));
        if (!r.ok) throw new Error(`검수 실패 (${r.status})`);
        const d = await r.json();
        setResults([{ sitecode: "(입력)", url: "", page_type: pageType, schema: d.schema, copy: d.copy }]);
      }
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const onHtmlFile = async (file: File) => { setHtml(await file.text()); setInputMode("paste"); flash(`${file.name} 불러옴 — 검수를 누르세요`); };

  // Apple Stalker의 trigger-crawl/all + crawl-progress 패턴과 동일:
  // /run 은 즉시 반환(started)되고, 실제 크롤은 서버 백그라운드에서 동시성 제한으로
  // '나눠서' 진행된다. 프론트는 SSE로 진행률만 구독하다가 done 이벤트에서 결과를 받아온다.
  // → 91개를 한 요청에 다 물지 않으므로 'Failed to fetch'(게이트웨이 타임아웃)가 사라진다.
  const runByRegion = async () => {
    if (busy) return;
    setBusy(true); setErr(""); setResults([]);
    const codes = region === "전체" ? allSites.map((s) => s.sitecode) : (regionsMap[region] || []).map((s) => s.sitecode);
    setProgress({ active: true, done: 0, total: codes.length, label: region });
    try {
      const r = await fetch(api("/api/qb/run"), J({ product: family(product), market_product: product, sitecodes: codes }));
      if (r.status === 501) throw new Error("크롤러 미연결 — 붙여넣기/파일/링크 검수를 이용하세요.");
      if (r.status === 409) throw new Error("이미 검수가 진행 중이에요. 완료 후 다시 시도하세요.");
      if (!r.ok) throw new Error(`실행 실패 (${r.status})`);
      await new Promise<void>((resolve, reject) => {
        const es = new EventSource(api("/api/qb/run-progress"));
        const timeout = setTimeout(() => { es.close(); reject(new Error("진행이 오래 걸려요 — 검수 이력에서 완료 여부를 확인해보세요.")); }, 20 * 60 * 1000);
        es.onmessage = (ev) => {
          try {
            const d = JSON.parse(ev.data);
            if (d.type === "start") setProgress((p) => ({ ...p, total: d.total || p.total, done: 0 }));
            else if (d.type === "page_done") setProgress((p) => ({ ...p, done: d.done ?? p.done + 1 }));
            else if (d.type === "done") {
              clearTimeout(timeout); es.close();
              fetch(api(`/api/qb/history/${encodeURIComponent(d.run_id)}`))
                .then((rr) => rr.ok ? rr.json() : null)
                .then((dd) => { if (dd?.results) setResults(dd.results); resolve(); })
                .catch(() => resolve());
            } else if (d.type === "status" && d.crawling === false) { clearTimeout(timeout); es.close(); resolve(); }
          } catch { /* heartbeat 무시 */ }
        };
        es.onerror = () => { clearTimeout(timeout); es.close(); reject(new Error("진행 상황 연결이 끊겼어요 — 완료 후 검수 이력에서 확인하세요.")); };
      });
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); setProgress((p) => ({ ...p, active: false })); loadHistory(); }
  };

  const downloadBlob = async (url: string, body: any, filename: string) => {
    try {
      const r = body === null
        ? await fetch(api(url))
        : await fetch(api(url), J(body));
      if (!r.ok) throw new Error(`서버 오류 (${r.status})`);
      const blob = await r.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href; a.download = filename; document.body.appendChild(a); a.click();
      a.remove(); setTimeout(() => URL.revokeObjectURL(href), 1500);
    } catch (e: any) {
      setErr(`${filename} 다운로드 실패 — ${e.message || e}`);
    }
  };
  const downloadXlsx = async () => {
    if (!results.length) { setErr("먼저 검수를 실행한 뒤 Excel을 받을 수 있어요."); return; }
    await downloadBlob("/api/qb/report.xlsx", null, "qubi_qa_report.xlsx");
  };
  const copyEmail = async () => {
    if (!results.length) { setErr("먼저 검수를 실행한 뒤 메일 본문을 복사할 수 있어요."); return; }
    try {
      // Apple Stalker와 동일: 서버가 든 마지막 결과를 GET으로 받음(본문 없음 → CORS preflight 없음)
      const r = await fetch(api("/api/qb/email-draft"), { cache: "no-store" });
      if (!r.ok) throw new Error(`서버 오류 (${r.status})`);
      const body = await r.text();
      if (navigator.clipboard && "write" in navigator.clipboard && typeof ClipboardItem !== "undefined") {
        await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([body], { type: "text/html" }), "text/plain": new Blob([body], { type: "text/plain" }) })]);
        flash("메일 본문 복사됨 — 붙여넣기 🐝");
      } else if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(body); flash("메일 본문 복사됨 🐝"); }
      else { const w = window.open("", "_blank"); if (w) { w.document.write(body); w.document.close(); } flash("새 탭에서 복사하세요"); }
    } catch (e: any) { setErr(`메일 복사 실패 — ${e.message || e}`); }
  };

  // ── URL 관리 ──
  const addUrl = async () => { if (!newUrl.trim()) return; await fetch(api("/api/qb/sites/add"), J({ url: newUrl.trim() })); setNewUrl(""); loadSites(); flash("URL 추가"); };
  const removeUrl = async (sc: string) => { await fetch(api("/api/qb/sites/remove"), J({ sitecode: sc })); loadSites(); };
  const downloadTemplate = () => downloadBlob("/api/qb/sites/template.xlsx", null, "qubi_url_template.xlsx");
  const uploadTemplate = async (file: File) => {
    const b64: string = await new Promise((res, rej) => { const rd = new FileReader(); rd.onload = () => res(String(rd.result)); rd.onerror = rej; rd.readAsDataURL(file); });
    const d = await (await fetch(api("/api/qb/sites/upload"), J({ b64 }))).json(); loadSites(); flash(`${d.added || 0}개 URL 추가`);
  };

  // ── 스펙/제품/룰 ──
  const pickCatalog = (cat: string) => { const c = catalog.find((x) => x.category === cat); setSpecForm({ category: cat, value: c?.ex_value || "", unit: c?.ex_unit || "" }); };
  const addSpec = async () => { if (!specForm.category || !specForm.value) return; await fetch(api("/api/qb/specs/add"), J({ product: specProduct, ...specForm })); setSpecForm({ category: "", value: "", unit: "" }); loadSpecs(specProduct); flash("스펙 추가"); };
  const removeSpec = async (i: number) => { await fetch(api("/api/qb/specs/remove"), J({ index: i, product: specProduct })); loadSpecs(specProduct); };
  const addProduct = async () => { if (!newProd.trim()) return; await fetch(api("/api/qb/products/add"), J({ product: newProd.trim() })); const p = newProd.trim(); setNewProd(""); await loadProducts(); setSpecProduct(p); flash("제품 추가"); };
  const addRule = async () => {
    if (tab === "schema") {
      if (!ruleForm.block_type || !ruleForm.property) return;
      await fetch(api("/api/qb/rules/schema/add"), J({
        product: family(product), page_type: pageType, block_type: ruleForm.block_type, property: ruleForm.property,
        value: ruleForm.value, value_kind: ruleForm.value_kind, nested: ruleForm.nested,
      }));
    } else {
      if (!ruleForm.token) return;
      await fetch(api("/api/qb/rules/copy/add"), J({ product, kind: ruleForm.kind, token: ruleForm.token }));
    }
    setRuleForm({ ...ruleForm, property: "", value: "", token: "" }); loadRules(); flash("룰 추가됨");
  };

  // 현재 탭 오류 행
  const rows = useMemo(() => {
    const out: { r: PageResult; f: Finding; item: string }[] = [];
    for (const r of results) {
      const fs = tab === "schema" ? (r.schema?.findings || []) : (r.copy?.findings || []);
      for (const f of fs) if (f.status !== "pass") out.push({ r, f, item: f.block || f.token || f.category || "" });
    }
    const rank: Record<string, number> = { fail: 0, warn: 1, na: 2 };
    return out.sort((a, b) => (rank[a.f.status] ?? 3) - (rank[b.f.status] ?? 3));
  }, [results, tab]);
  const failCount = rows.filter((x) => x.f.status === "fail").length;

  // 권역 신호등
  const regionTier = useMemo(() => {
    const m: Record<string, { fail: number; warn: number }> = {};
    for (const r of results) {
      const rg = r.region || "기타"; m[rg] = m[rg] || { fail: 0, warn: 0 };
      for (const f of [...(r.schema?.findings || []), ...(r.copy?.findings || [])]) {
        if (f.status === "fail") m[rg].fail++; else if (f.status === "warn") m[rg].warn++;
      }
    }
    return m;
  }, [results]);
  const tierOf = (c: { fail: number; warn: number }) => (c.fail > 0 ? "bad" : c.warn > 0 ? "mid" : "good");

  const countries = useMemo(() => Array.from(new Set(results.map((r) => r.country).filter(Boolean))) as string[], [results]);
  const quickRows = useMemo(() => rows.filter((x) => qCountry === "전체" || x.r.country === qCountry), [rows, qCountry]);

  const inputStyle = { fontSize: 12, padding: "6px 8px", border: "1px solid var(--line)", borderRadius: 6 } as const;
  const sel = (v: string, on: boolean) => ({ fontSize: 12, padding: "4px 10px", borderRadius: 999, cursor: "pointer", border: on ? "1px solid #0A66E0" : "1px solid var(--line)", background: on ? "#0A66E0" : "#fff", color: on ? "#fff" : "var(--label)" });

  return (
    <div className="appShell">
      {/* ── 사이드바 ── */}
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🐝 큐비</div>
        <div className="brandSub">QA의 사촌, 큐비 — 닷컴을 붕붕 돌며 스펙을 지켜요</div>
        <div className={`connBadge ${online === true ? "ok" : "bad"}`}><span className="connDot" />{online === null ? "확인 중" : online ? "백엔드 연결됨" : "연결 안 됨"}</div>

        <div className="sideScroll">
          <div className="sideLabel">URL 관리</div>
          <div style={{ padding: "0 10px", marginBottom: 6 }}>
            <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="https://www.samsung.com/…/compare/" style={{ ...inputStyle, width: "100%" }} />
            <button onClick={addUrl} style={{ marginTop: 6, fontSize: 12, fontWeight: 700, color: "#0A66E0", background: "none", border: "none", cursor: "pointer" }}>＋ URL 추가</button>
          </div>
          <div style={{ padding: "0 10px 8px", display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button onClick={downloadTemplate} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }}>⬇ URL 템플릿</button>
            <button onClick={() => xlsxFileRef.current?.click()} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }}>⬆ 템플릿 업로드</button>
            <input ref={xlsxFileRef} type="file" accept=".xlsx" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadTemplate(f); e.currentTarget.value = ""; }} />
          </div>
          <div className="sideLabel" style={{ cursor: "pointer" }} onClick={() => setSitesOpen((o) => !o)}>{sitesOpen ? "▾" : "▸"} 모니터링 URL 목록 <span style={{ color: "var(--sec)" }}>{allSites.length}개</span></div>
          {sitesOpen && allSites.map((s) => (
            <div key={s.sitecode} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 10px", fontSize: 11.5 }}>
              <span title={s.url}>{s.sitecode} <span style={{ color: "var(--sec)" }}>{s.country}</span></span>
              <span role="button" onClick={() => removeUrl(s.sitecode)} style={{ cursor: "pointer", color: "var(--high)", fontSize: 11 }}>삭제</span>
            </div>
          ))}

          {/* 검수 이력 */}
          <div className="sideLabel" style={{ marginTop: 14 }}>검수 이력 <span style={{ color: "var(--sec)" }}>{history.length}건</span></div>
          {history.length === 0 && <p style={{ padding: "2px 10px", fontSize: 11.5, color: "var(--sec)" }}>아직 저장된 검수가 없어요</p>}
          {history.map((h) => (
            <div key={h.run_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 10px", fontSize: 11.5, cursor: "pointer" }} onClick={() => openHistory(h.run_id)}>
              <span>
                <span style={{ fontWeight: 600 }}>{h.at?.slice(5, 16) || h.run_id}</span>
                <span style={{ color: "var(--sec)" }}> · {h.product} · {h.pages}p</span>
                {h.fail > 0 && <span style={{ color: "var(--high)" }}> · 오류 {h.fail}</span>}
              </span>
              <span role="button" onClick={(e) => { e.stopPropagation(); removeHistory(h.run_id); }} style={{ color: "var(--high)", fontSize: 11 }}>삭제</span>
            </div>
          ))}
        </div>
      </aside>

      {/* ── 메인 ── */}
      <div className="mainArea">
        <header className="topbar">
          <div className="topbarRow1">
            <div className="tabGroup">
              <button className={`tabBtn ${tab === "schema" ? "on" : ""}`} onClick={() => setTab("schema")}>스키마 QA</button>
              <button className={`tabBtn ${tab === "copy" ? "on" : ""}`} onClick={() => setTab("copy")}>스펙 QA</button>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              <button className="toolBtn" onClick={() => { setShowRuleAdd((v) => !v); setShowRules(false); }}>＋ 룰 추가</button>
              <button className="toolBtn" onClick={() => { setShowRules((v) => !v); setShowRuleAdd(false); }}>ⓘ 검수 기준</button>
              <button className="toolBtn" onClick={copyEmail}>✉ 메일 복사</button>
              <a className="toolBtn" href={api("/api/qb/report.xlsx")} onClick={(e) => { if (!results.length) { e.preventDefault(); setErr("먼저 검수를 실행한 뒤 Excel을 받을 수 있어요."); } }} download>📊 Excel</a>
            </div>
          </div>
        </header>

        <div className="contentScroll" style={{ padding: "20px 28px 80px" }}>
          <h2 style={{ fontSize: 18, margin: "0 0 4px" }}>
            {tab === "schema" ? "스키마 QA" : "스펙 QA"} <span style={{ fontSize: 12, fontWeight: 400, color: "var(--sec)" }}>
              {tab === "schema" ? "JSON-LD 속성·값을 스펙과 대조 (파싱 오류도 검출)" : "스펙 값·고유명사 정확성 (번역 대응)"}</span>
          </h2>

          {/* 제품 · 페이지타입 */}
          <div style={{ display: "flex", gap: 6, alignItems: "center", margin: "10px 0 4px", flexWrap: "wrap" }}>
            <span style={{ fontSize: 12.5, color: "var(--sec)" }}>제품:</span>
            {products.map((p) => <button key={p.code} onClick={() => setProduct(p.code)} style={sel(p.code, product === p.code)}>{p.label}</button>)}
            <span style={{ fontSize: 12.5, color: "var(--sec)", marginLeft: 10 }}>페이지타입:</span>
            {PAGE_TYPES.map((p) => <button key={p} onClick={() => setPageType(p)} style={sel(p, pageType === p)}>{p}</button>)}
          </div>

          {ok && <div style={{ background: "#ECFDF3", color: "#067647", padding: "8px 12px", borderRadius: 8, fontSize: 13, margin: "8px 0" }}>{ok}</div>}
          {err && <div style={{ background: "#FEF3F2", color: "#B42318", padding: 10, borderRadius: 8, fontSize: 13, margin: "8px 0", fontWeight: 600 }}>{err}</div>}

          {/* ① 리전별 검수 크롤 (91사이트) — 먼저 노출 */}
          <div className="card" style={{ marginTop: 12, padding: 14 }}>
            <b style={{ fontSize: 14 }}>① 리전별 검수 크롤</b>
            <span style={{ fontSize: 12, color: "var(--sec)", marginLeft: 8 }}>등록된 사이트를 권역별로 크롤해 한 번에 검수 (결과는 이력에 저장)</span>
            <div style={{ display: "flex", gap: 6, alignItems: "center", margin: "10px 0 8px", flexWrap: "wrap" }}>
              {["전체", ...regionNames].map((rg) => <button key={rg} onClick={() => setRegion(rg)} style={sel(rg, region === rg)}>{rg}{rg !== "전체" && regionsMap[rg] ? ` ${regionsMap[rg].length}` : ""}</button>)}
            </div>
            <button onClick={runByRegion} disabled={busy} style={{ padding: "8px 14px", borderRadius: 8, border: "none", background: HONEY, color: "#fff", fontWeight: 700, cursor: "pointer" }}>
              {busy ? "붕붕 검수 중…" : `${region === "전체" ? allSites.length : (regionsMap[region]?.length || 0)}개 사이트 검수`}
            </button>
            {progress.active && (
              <div style={{ marginTop: 10 }}>
                <div style={{ height: 8, background: "#F0F1F3", borderRadius: 999, overflow: "hidden" }}><div style={{ height: "100%", width: `${progress.total ? (progress.done / progress.total) * 100 : 0}%`, background: HONEY, transition: "width .3s" }} /></div>
                <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 4 }}>🐝 {progress.label} · {progress.done}/{progress.total} 사이트</div>
              </div>
            )}
          </div>

          {/* ② 단일 페이지 검수 — 붙여넣기 / 파일 / 링크 */}
          <div className="card" style={{ marginTop: 14, padding: 14 }}>
            <b style={{ fontSize: 14 }}>② 단일 페이지 검수</b>
            <span style={{ fontSize: 12, color: "var(--sec)", marginLeft: 8 }}>한 페이지만 빠르게 — HTML 붙여넣기 · 파일 업로드 · 링크 1개</span>
            <div style={{ display: "flex", gap: 6, margin: "10px 0 8px" }}>
              {([["paste", "붙여넣기"], ["file", "HTML 파일"], ["url", "링크 1개"]] as const).map(([m, l]) => (
                <button key={m} onClick={() => setInputMode(m)} style={sel(l, inputMode === m)}>{l}</button>
              ))}
            </div>
            {inputMode === "paste" && (
              <textarea value={html} onChange={(e) => setHtml(e.target.value)} placeholder="<html>… 페이지 소스 …</html>"
                style={{ width: "100%", height: 100, fontFamily: "monospace", fontSize: 12, padding: 8, border: "1px solid var(--line)", borderRadius: 8 }} />
            )}
            {inputMode === "file" && (
              <div style={{ padding: "18px", border: "1.5px dashed var(--line)", borderRadius: 8, textAlign: "center" }}>
                <button onClick={() => htmlFileRef.current?.click()} className="btnSecondary" style={{ fontSize: 13, padding: "8px 14px" }}>📄 HTML 파일 선택</button>
                <input ref={htmlFileRef} type="file" accept=".html,.htm,text/html" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onHtmlFile(f); e.currentTarget.value = ""; }} />
                {html && <span style={{ marginLeft: 10, fontSize: 12, color: "var(--sec)" }}>불러옴 ({html.length.toLocaleString()}자)</span>}
              </div>
            )}
            {inputMode === "url" && (
              <input value={urlOne} onChange={(e) => setUrlOne(e.target.value)} placeholder="https://www.samsung.com/uk/smartphones/galaxy-s26-ultra/compare/"
                style={{ ...inputStyle, width: "100%", fontSize: 13, padding: "10px 12px" }} />
            )}
            <button onClick={doCheck} disabled={busy} style={{ marginTop: 8, padding: "8px 16px", borderRadius: 8, border: "none", background: "#0A66E0", color: "#fff", fontWeight: 700, cursor: "pointer" }}>
              {busy ? "검수 중…" : "검수하기"}
            </button>
          </div>

          {/* 스펙 관리 표 (스펙 QA 탭) */}
          {tab === "copy" && (
            <div className="card" style={{ marginTop: 18, padding: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <b style={{ fontSize: 14 }}>검수 기준 스펙</b>
                <span style={{ fontSize: 12, color: "var(--sec)" }}>제품:</span>
                <select value={specProduct} onChange={(e) => setSpecProduct(e.target.value)} style={{ ...inputStyle }}>
                  {products.map((p) => <option key={p.code} value={p.code}>{p.label}</option>)}
                </select>
                <input value={newProd} onChange={(e) => setNewProd(e.target.value)} placeholder="새 제품 추가(galaxy-buds4-pro)" style={{ ...inputStyle, width: 220 }} />
                <button onClick={addProduct} className="btnSecondary" style={{ fontSize: 12, padding: "5px 10px" }}>＋ 제품</button>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 10, fontSize: 12.5 }}>
                <thead><tr style={{ color: "var(--sec)", fontSize: 11, textAlign: "left" }}>
                  <th style={{ padding: "4px 6px" }}>항목</th><th style={{ padding: "4px 6px" }}>값(여러 값=콤마)</th><th style={{ padding: "4px 6px" }}>단위</th><th style={{ padding: "4px 6px" }}>적용 페이지</th><th /></tr></thead>
                <tbody>
                  {specs.map((sp, i) => (
                    <tr key={i}>
                      <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}>{sp.category}</td>
                      <td style={{ padding: 6, borderTop: "1px solid var(--line)", fontWeight: 700 }}>{(sp.values || (sp.value != null ? [sp.value] : [])).join(" / ")}</td>
                      <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}>{sp.unit}</td>
                      <td style={{ padding: 6, borderTop: "1px solid var(--line)", color: "var(--sec)", fontSize: 11 }}>{(sp.page_types || ["PDP"]).join(", ")}</td>
                      <td style={{ padding: 6, borderTop: "1px solid var(--line)", textAlign: "right" }}><span role="button" onClick={() => removeSpec(i)} style={{ cursor: "pointer", color: "var(--high)", fontSize: 11 }}>삭제</span></td>
                    </tr>
                  ))}
                  {/* 행 추가 */}
                  <tr>
                    <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}>
                      <select value={specForm.category} onChange={(e) => pickCatalog(e.target.value)} style={{ ...inputStyle, width: "100%" }}>
                        <option value="">항목 선택…</option>
                        {catalog.map((c) => <option key={c.category} value={c.category}>{c.category} · {c.label}</option>)}
                      </select>
                    </td>
                    <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}><input value={specForm.value} onChange={(e) => setSpecForm({ ...specForm, value: e.target.value })} placeholder="예: 31  또는  7,8" style={{ ...inputStyle, width: 90 }} /></td>
                    <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}><input value={specForm.unit} onChange={(e) => setSpecForm({ ...specForm, unit: e.target.value })} placeholder="단위" style={{ ...inputStyle, width: 60 }} /></td>
                    <td style={{ padding: 6, borderTop: "1px solid var(--line)", color: "var(--sec)", fontSize: 11 }}>PDP</td>
                    <td style={{ padding: 6, borderTop: "1px solid var(--line)", textAlign: "right" }}><button onClick={addSpec} className="btnSecondary" style={{ fontSize: 12, padding: "4px 10px" }}>＋ 추가</button></td>
                  </tr>
                </tbody>
              </table>
              <p style={{ fontSize: 11, color: "var(--sec)", marginTop: 6 }}>값에 콤마를 넣으면 국별 표기 차이를 모두 인정합니다(예: 재생시간 7,8 → 7h·8h 둘 다 통과). 숫자 콤마·공백(2,600=2600)도 자동 인식.</p>
            </div>
          )}

          {/* 룰 추가 패널 */}
          {showRuleAdd && (
            <div className="card" style={{ marginTop: 16, padding: 14 }}>
              <b style={{ fontSize: 14 }}>룰 추가 — {tab === "schema" ? `스키마 (${product}·${pageType})` : "스펙"}</b>
              {tab === "schema" ? (
                <div style={{ marginTop: 10 }}>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                    <input list="qb-schema-types" value={ruleForm.block_type} onChange={(e) => setRuleForm({ ...ruleForm, block_type: e.target.value })} placeholder="① 스키마 타입 (WebPage…)" style={{ ...inputStyle, width: 180 }} />
                    <datalist id="qb-schema-types">{schemaTypes.map((t) => <option key={t} value={t} />)}</datalist>
                    <input value={ruleForm.property} onChange={(e) => setRuleForm({ ...ruleForm, property: e.target.value })} placeholder="② 속성 (name, url, @id…)" style={{ ...inputStyle, width: 170 }} />
                    <select value={ruleForm.value_kind} onChange={(e) => setRuleForm({ ...ruleForm, value_kind: e.target.value })} style={{ ...inputStyle, width: 190 }}>
                      <option value="exists">③ 존재만 (값 검사 안 함)</option>
                      <option value="url">URL/@id (SITECODE 가변·정확)</option>
                      <option value="enum">enum/타입 (정확 일치)</option>
                      <option value="text">번역 텍스트 (확인만·warn)</option>
                    </select>
                  </div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginTop: 6 }}>
                    {ruleForm.value_kind !== "exists" && ruleForm.value_kind !== "text" && (
                      <input value={ruleForm.value} onChange={(e) => setRuleForm({ ...ruleForm, value: e.target.value })}
                        placeholder={ruleForm.value_kind === "url" ? "④ 기대값 예: https://www.samsung.com/{SITECODE}/…/#webpage" : "④ 기대값 예: WebPage,ItemPage"}
                        style={{ ...inputStyle, width: 420 }} />
                    )}
                    <select value={ruleForm.nested} onChange={(e) => setRuleForm({ ...ruleForm, nested: e.target.value })} style={{ ...inputStyle, width: 150 }}>
                      <option value="">중첩 없음</option>
                      <option value="@id">중첩 @id 로 검사</option>
                      <option value="@type">중첩 @type 로 검사</option>
                    </select>
                    <button onClick={addRule} className="toolBtn">추가</button>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--sec)", marginTop: 8, lineHeight: 1.6 }}>
                    타입 블록에 속성을 등록하고, <b>값 종류</b>까지 지정하면 값 검수(#5)에 바로 반영됩니다.
                    블록이 없으면 새로 만들어 이 페이지타입에 등록해요.<br />
                    · <b>존재만</b>: 있는지만 확인 · <b>URL/@id</b>: <code>{"{SITECODE}"}</code>·<code>{"{LANG-CODE}"}</code> 자동 치환 후 정확 일치(불일치=오류)
                    · <b>enum/타입</b>: 정확 일치 · <b>번역 텍스트</b>: 번역 여부 확인(warn, 오류 아님)
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                  <select value={ruleForm.kind} onChange={(e) => setRuleForm({ ...ruleForm, kind: e.target.value })} style={{ ...inputStyle, width: 140 }}>
                    <option value="spec">스펙 토큰</option><option value="proper_noun">고유명사</option>
                  </select>
                  <input value={ruleForm.token} onChange={(e) => setRuleForm({ ...ruleForm, token: e.target.value })} placeholder={ruleForm.kind === "spec" ? "예: 2600 nits" : "예: Corning Gorilla Armor 2"} style={{ ...inputStyle, width: 260 }} />
                  <button onClick={addRule} className="toolBtn">추가</button>
                </div>
              )}
            </div>
          )}

          {/* 검수 기준 패널 */}
          {showRules && rules && (
            <div className="card" style={{ marginTop: 16, padding: 14 }}>
              <b style={{ fontSize: 14 }}>검수 기준 — {tab === "schema" ? `스키마 (${product}·${pageType})` : "스펙"}</b>
              {tab === "schema" ? (
                <div style={{ fontSize: 12.5, marginTop: 8 }}>
                  <p style={{ color: "var(--sec)" }}>{rules.schema?.["설명"]}</p>
                  {(rules.schema?.blocks || []).length === 0 && <p style={{ color: "var(--sec)" }}>이 페이지타입엔 아직 룰이 없어요. ＋룰 추가로 등록하세요.</p>}
                  {(rules.schema?.blocks || []).map((b: any, i: number) => (
                    <div key={i} style={{ borderTop: "1px solid var(--line)", padding: "6px 0" }}><b>{b.block}</b> <span style={{ color: "var(--sec)" }}>{(b.types || []).join(", ")}</span>{b.required_properties?.length > 0 && <div>필수: {b.required_properties.join(", ")}</div>}</div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12.5, marginTop: 8 }}>
                  <p style={{ color: "var(--sec)" }}>{rules.copy?.["설명"]}</p>
                  <div><b>스펙 토큰:</b> {(rules.copy?.spec_tokens || []).join(", ")}</div>
                  <div style={{ marginTop: 6 }}><b>고유명사:</b> {(rules.copy?.proper_nouns || []).join(", ")}</div>
                </div>
              )}
            </div>
          )}

          {/* 결과 — 오류 빨강 강조 */}
          {rows.length > 0 && (
            <>
              <div style={{ margin: "18px 0 8px", fontSize: 13, fontWeight: 700, color: failCount ? "#B42318" : "var(--label)" }}>
                {failCount ? `🔴 오류 ${failCount}건` : "🟡 검토"}
                {(() => { const w = rows.filter((x) => x.f.status === "warn").length; const na = rows.filter((x) => x.f.status === "na").length;
                  return <span style={{ color: "var(--sec)", fontWeight: 400 }}> · 확인 {w}건{na ? ` · 해당없음 ${na}건` : ""}</span>; })()}
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead><tr style={{ color: "var(--sec)", fontSize: 11, textAlign: "left" }}>
                  <th style={{ padding: "6px 8px" }}>사이트</th><th style={{ padding: "6px 8px" }}>항목</th><th style={{ padding: "6px 8px" }}>심각도</th><th style={{ padding: "6px 8px" }}>as-is → to-be</th></tr></thead>
                <tbody>
                  {rows.map((x, i) => (
                    <tr key={i} style={{ background: x.f.status === "fail" ? "#FEF3F2" : undefined, opacity: x.f.status === "na" ? 0.6 : 1 }}>
                      <td style={{ padding: 8, borderTop: "1px solid var(--line)", whiteSpace: "nowrap" }}>{x.r.sitecode}</td>
                      <td style={{ padding: 8, borderTop: "1px solid var(--line)" }}>{x.item}</td>
                      <td style={{ padding: 8, borderTop: "1px solid var(--line)" }}><span style={{ background: SEV[x.f.status].c, color: "#fff", fontSize: 11, fontWeight: 700, padding: "2px 7px", borderRadius: 5 }}>{SEV[x.f.status].ko}</span></td>
                      <td style={{ padding: 8, borderTop: "1px solid var(--line)" }}><div style={{ color: "var(--sec)" }}>{x.f.as_is}</div>{x.f.to_be ? <div style={{ fontWeight: 600, color: x.f.status === "fail" ? "#B42318" : "var(--label)" }}>→ {x.f.to_be}</div> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {results.length > 0 && rows.length === 0 && <p style={{ color: "#1F9E5C", marginTop: 16 }}>이 탭({tab === "schema" ? "스키마" : "스펙"})에서 발견된 오류가 없어요 🐝</p>}
        </div>
      </div>

      {/* ── Quick View (우하단) ── */}
      {!quickOpen && (
        <button onClick={() => setQuickOpen(true)} style={{ position: "fixed", right: 20, bottom: 20, zIndex: 40, background: "#101318", color: "#fff", border: "none", borderRadius: 999, padding: "12px 18px", fontWeight: 700, cursor: "pointer", boxShadow: "0 6px 20px rgba(0,0,0,.2)" }}>
          🐝 Quick View{results.length ? ` · ${results.length}` : ""}
        </button>
      )}
      {quickOpen && (
        <div style={{ position: "fixed", right: 20, bottom: 20, zIndex: 40, width: 380, maxHeight: "72vh", overflow: "auto", background: "#fff", border: "1px solid var(--line)", borderRadius: 14, boxShadow: "0 10px 30px rgba(0,0,0,.22)" }}>
          <div style={{ position: "sticky", top: 0, background: "#101318", color: "#fff", padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center", borderRadius: "14px 14px 0 0" }}>
            <b style={{ fontSize: 13 }}>🐝 Quick View — {tab === "schema" ? "스키마" : "스펙"}</b>
            <span role="button" onClick={() => setQuickOpen(false)} style={{ cursor: "pointer" }}>✕</span>
          </div>
          <div style={{ padding: 14 }}>
            {/* 권역 신호등 */}
            <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--sec)", marginBottom: 6 }}>권역 신호등</div>
            {Object.keys(regionTier).length === 0 && <p style={{ fontSize: 12, color: "var(--sec)" }}>검수를 실행하면 권역별 상태가 표시됩니다.</p>}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
              {Object.entries(regionTier).map(([rg, c]) => (
                <span key={rg} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, border: "1px solid var(--line)", borderRadius: 999, padding: "3px 9px" }}>
                  <span className={`scoreDot ${tierOf(c)}`} />{rg}<span style={{ color: "var(--sec)" }}>{c.fail ? `오류${c.fail}` : c.warn ? `확인${c.warn}` : "정상"}</span>
                </span>
              ))}
            </div>
            {/* 국가 필터 */}
            {countries.length > 0 && (
              <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 10 }}>
                <button onClick={() => setQCountry("전체")} style={sel("전체", qCountry === "전체")}>전체</button>
                {countries.map((c) => <button key={c} onClick={() => setQCountry(c)} style={sel(c, qCountry === c)}>{c}</button>)}
              </div>
            )}
            {/* 오류 목록 + 상세 */}
            {quickRows.length === 0 && <p style={{ fontSize: 12, color: "var(--sec)" }}>표시할 오류가 없어요.</p>}
            {quickRows.slice(0, 60).map((x, i) => {
              const key = `${x.r.sitecode}-${i}`;
              return (
                <div key={key} style={{ borderTop: "1px solid var(--line)", padding: "7px 0" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 6, cursor: "pointer" }} onClick={() => setQDetail(qDetail === key ? null : key)}>
                    <span style={{ fontSize: 12 }}><span style={{ background: SEV[x.f.status].c, color: "#fff", fontSize: 10, fontWeight: 700, padding: "1px 5px", borderRadius: 4, marginRight: 5 }}>{SEV[x.f.status].ko}</span><b>{x.r.sitecode}</b> · {x.item}</span>
                    <span style={{ fontSize: 11, color: "#0A66E0" }}>{qDetail === key ? "닫기" : "상세"}</span>
                  </div>
                  {qDetail === key && (
                    <div style={{ fontSize: 12, marginTop: 4, background: "#F9FAFB", borderRadius: 6, padding: 8 }}>
                      <div style={{ color: "var(--sec)" }}>as-is: {x.f.as_is}</div>
                      <div style={{ fontWeight: 600, marginTop: 2 }}>→ {x.f.to_be}</div>
                      {x.r.url && <div style={{ fontFamily: "monospace", fontSize: 10.5, color: "#98A2B3", marginTop: 4, wordBreak: "break-all" }}>{x.r.url}</div>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
