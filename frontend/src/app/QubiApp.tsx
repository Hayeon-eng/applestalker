"use client";
/**
 * QubiApp.tsx — 큐비 🐝 (QA Bee) 독립 앱
 * 상단 탭: [스키마 QA] [스펙 QA]  ·  리전별 크롤+진행바 · 룰 추가 · 메일 복사 · 엑셀 URL 템플릿
 * 백엔드: /api/qb/*
 */
import { useEffect, useMemo, useRef, useState } from "react";

type Finding = { status: "pass" | "warn" | "fail"; as_is?: string; to_be?: string;
  block?: string; token?: string; kind?: string };
type PageResult = { sitecode: string; url: string; region?: string; country?: string;
  schema: { findings: Finding[] }; copy: { findings: Finding[] } };
type SiteRow = { sitecode: string; country?: string; lang?: string; url: string };

const SEV = { fail: { ko: "오류", c: "#D8362F" }, warn: { ko: "확인", c: "#E0A008" }, pass: { ko: "정상", c: "#1F9E5C" } };
const HONEY = "#E0A008";

export default function QubiApp({ apiBase = "", onHome }: { apiBase?: string; onHome?: () => void }) {
  const [tab, setTab] = useState<"schema" | "copy">("schema");
  const [product] = useState("M3");
  const [html, setHtml] = useState("");
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
  const [specs, setSpecs] = useState<any[]>([]);
  const [newUrl, setNewUrl] = useState("");
  const [newSpec, setNewSpec] = useState({ product: "galaxy-s26-ultra", category: "", value: "", unit: "" });
  const [ruleForm, setRuleForm] = useState({ block: "", property: "", kind: "spec", token: "" });
  const fileRef = useRef<HTMLInputElement>(null);

  const api = (p: string) => `${apiBase}${p}`;
  const flash = (m: string) => { setOk(m); setTimeout(() => setOk(""), 2500); };

  useEffect(() => {
    fetch(api("/api/health")).then((r) => setOnline(r.ok)).catch(() => setOnline(false));
    loadSites(); loadSpecs();
  }, []);
  useEffect(() => { if ((showRules || showRuleAdd) && !rules) loadRules(); }, [showRules, showRuleAdd]);

  async function loadSites() {
    try { const d = await (await fetch(api("/api/qb/sites"))).json(); setRegionsMap(d.regions || {}); } catch { /* */ }
  }
  async function loadSpecs() {
    try { setSpecs((await (await fetch(api(`/api/qb/specs?product=galaxy-s26-ultra`))).json()).specs || []); } catch { /* */ }
  }
  async function loadRules() {
    try { setRules(await (await fetch(api(`/api/qb/rules?product=${product}`))).json()); } catch (e: any) { setErr(String(e)); }
  }

  const allSites = useMemo(() => Object.values(regionsMap).flat(), [regionsMap]);
  const regionNames = useMemo(() => Object.keys(regionsMap), [regionsMap]);

  const checkHtml = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(api("/api/qb/check"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ html, product }) });
      if (!r.ok) throw new Error(`검수 실패 (${r.status})`);
      const d = await r.json();
      setResults([{ sitecode: "(붙여넣기)", url: "", schema: d.schema, copy: d.copy }]);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  // 리전별로 끊어서 순차 크롤 + 진행바
  const runByRegion = async () => {
    setBusy(true); setErr(""); setResults([]);
    const targetRegions = region === "전체" ? regionNames : [region];
    const total = targetRegions.reduce((n, r) => n + (regionsMap[r]?.length || 0), 0);
    setProgress({ active: true, done: 0, total, label: "" });
    const acc: PageResult[] = [];
    try {
      for (const rg of targetRegions) {
        const codes = (regionsMap[rg] || []).map((s) => s.sitecode);
        setProgress((p) => ({ ...p, label: `${rg} (${codes.length}개)` }));
        const r = await fetch(api("/api/qb/run"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product, sitecodes: codes }) });
        if (r.status === 501) throw new Error("크롤러 미연결 — HTML 붙여넣기로 검수하세요.");
        if (!r.ok) throw new Error(`실행 실패 (${r.status})`);
        const d = await r.json();
        acc.push(...(d.results || []));
        setResults([...acc]);
        setProgress((p) => ({ ...p, done: Math.min(p.done + codes.length, total) }));
      }
    } catch (e: any) { setErr(e.message); } finally {
      setBusy(false); setProgress((p) => ({ ...p, active: false }));
    }
  };

  const downloadXlsx = async () => {
    const r = await fetch(api("/api/qb/report.xlsx"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ results }) });
    const blob = await r.blob(); const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "qubi_qa_report.xlsx"; a.click();
  };
  const copyEmail = async () => {
    try {
      const r = await fetch(api("/api/qb/email-draft"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ results }) });
      const htmlBody = await r.text();
      if (navigator.clipboard && "write" in navigator.clipboard && typeof ClipboardItem !== "undefined") {
        await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([htmlBody], { type: "text/html" }), "text/plain": new Blob([htmlBody], { type: "text/plain" }) })]);
      } else {
        await navigator.clipboard.writeText(htmlBody);
      }
      flash("메일 본문을 복사했어요 🐝");
    } catch { setErr("메일 복사 실패"); }
  };

  // URL 관리
  const addUrl = async () => {
    if (!newUrl.trim()) return;
    await fetch(api("/api/qb/sites/add"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: newUrl.trim() }) });
    setNewUrl(""); loadSites(); flash("URL 추가 완료");
  };
  const removeUrl = async (sc: string) => { await fetch(api("/api/qb/sites/remove"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sitecode: sc }) }); loadSites(); };
  const downloadTemplate = () => { window.open(api("/api/qb/sites/template.xlsx"), "_blank"); };
  const uploadTemplate = async (file: File) => {
    const b64: string = await new Promise((res, rej) => { const rd = new FileReader(); rd.onload = () => res(String(rd.result)); rd.onerror = rej; rd.readAsDataURL(file); });
    const r = await fetch(api("/api/qb/sites/upload"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ b64 }) });
    const d = await r.json(); loadSites(); flash(`${d.added || 0}개 URL 일괄 추가`);
  };

  // 스펙/룰
  const addSpec = async () => {
    if (!newSpec.category || !newSpec.value) return;
    await fetch(api("/api/qb/specs/add"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newSpec) });
    setNewSpec({ ...newSpec, category: "", value: "", unit: "" }); loadSpecs(); flash("스펙 추가 완료");
  };
  const removeSpec = async (i: number) => { await fetch(api("/api/qb/specs/remove"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ index: i, product: "galaxy-s26-ultra" }) }); loadSpecs(); };
  const addRule = async () => {
    if (tab === "schema") {
      if (!ruleForm.block || !ruleForm.property) return;
      await fetch(api("/api/qb/rules/schema/add"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product, block: ruleForm.block, property: ruleForm.property }) });
    } else {
      if (!ruleForm.token) return;
      await fetch(api("/api/qb/rules/copy/add"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product, kind: ruleForm.kind, token: ruleForm.token }) });
    }
    setRuleForm({ ...ruleForm, property: "", token: "" }); setRules(null); loadRules(); flash("룰 추가 완료");
  };

  const rows = useMemo(() => {
    const out: { r: PageResult; f: Finding; item: string }[] = [];
    for (const r of results) {
      const fs = tab === "schema" ? (r.schema?.findings || []) : (r.copy?.findings || []);
      for (const f of fs) if (f.status !== "pass") out.push({ r, f, item: f.block || f.token || "" });
    }
    return out;
  }, [results, tab]);

  const inputStyle = { width: "100%", fontSize: 12, padding: "6px 8px", border: "1px solid var(--line)", borderRadius: 6 } as const;

  return (
    <div className="appShell">
      {/* ── 사이드바 ── */}
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🐝 큐비</div>
        <div className="brandSub">QA의 사촌, 큐비 — 닷컴을 붕붕 돌며 스펙을 지켜요</div>
        <div className={`connBadge ${online === true ? "ok" : "bad"}`}>
          <span className="connDot" />{online === null ? "확인 중" : online ? "백엔드 연결됨" : "연결 안 됨"}
        </div>

        <div className="sideScroll">
          {/* URL 관리 */}
          <div className="sideLabel">URL 관리</div>
          <div style={{ padding: "0 10px", marginBottom: 6 }}>
            <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="https://www.samsung.com/…/compare/" style={inputStyle} />
            <button onClick={addUrl} style={{ marginTop: 6, fontSize: 12, fontWeight: 700, color: "#0A66E0", background: "none", border: "none", cursor: "pointer" }}>＋ URL 추가</button>
          </div>
          <div style={{ padding: "0 10px 8px", display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button onClick={downloadTemplate} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }}>⬇ URL 템플릿</button>
            <button onClick={() => fileRef.current?.click()} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }}>⬆ 템플릿 업로드</button>
            <input ref={fileRef} type="file" accept=".xlsx" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadTemplate(f); e.currentTarget.value = ""; }} />
          </div>
          <div className="sideLabel" style={{ cursor: "pointer" }} onClick={() => setSitesOpen((o) => !o)}>
            {sitesOpen ? "▾" : "▸"} 모니터링 URL 목록 <span style={{ color: "var(--sec)" }}>{allSites.length}개</span>
          </div>
          {sitesOpen && allSites.map((s) => (
            <div key={s.sitecode} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 10px", fontSize: 11.5 }}>
              <span title={s.url}>{s.sitecode} <span style={{ color: "var(--sec)" }}>{s.country}</span></span>
              <span role="button" onClick={() => removeUrl(s.sitecode)} style={{ cursor: "pointer", color: "var(--high)", fontSize: 11 }}>삭제</span>
            </div>
          ))}

          {/* 스펙 관리 — 스펙 QA 탭 */}
          {tab === "copy" && (
            <>
              <div className="sideLabel" style={{ marginTop: 14 }}>스펙 기준 관리 <span style={{ color: "var(--sec)" }}>(제품·항목·값)</span></div>
              <div style={{ padding: "0 10px" }}>
                <input value={newSpec.product} onChange={(e) => setNewSpec({ ...newSpec, product: e.target.value })} placeholder="제품 (galaxy-s26-ultra)" style={{ ...inputStyle, fontSize: 11.5, marginBottom: 4 }} />
                <div style={{ display: "flex", gap: 4 }}>
                  <input value={newSpec.category} onChange={(e) => setNewSpec({ ...newSpec, category: e.target.value })} placeholder="항목(video_playback)" style={{ ...inputStyle, flex: 2, fontSize: 11.5 }} />
                  <input value={newSpec.value} onChange={(e) => setNewSpec({ ...newSpec, value: e.target.value })} placeholder="값" style={{ ...inputStyle, width: 46, fontSize: 11.5 }} />
                  <input value={newSpec.unit} onChange={(e) => setNewSpec({ ...newSpec, unit: e.target.value })} placeholder="단위" style={{ ...inputStyle, width: 44, fontSize: 11.5 }} />
                </div>
                <button onClick={addSpec} style={{ marginTop: 6, fontSize: 12, fontWeight: 700, color: "#0A66E0", background: "none", border: "none", cursor: "pointer" }}>＋ 스펙 추가</button>
              </div>
              {specs.map((sp, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "3px 10px", fontSize: 11.5 }}>
                  <span>{sp.category} = <b>{sp.value}{sp.unit ? ` ${sp.unit}` : ""}</b></span>
                  <span role="button" onClick={() => removeSpec(i)} style={{ cursor: "pointer", color: "var(--high)", fontSize: 11 }}>삭제</span>
                </div>
              ))}
            </>
          )}
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
              <button className="toolBtn" onClick={copyEmail} disabled={!results.length}>✉ 메일 복사</button>
              <button className="toolBtn" onClick={downloadXlsx} disabled={!results.length}>📊 Excel</button>
            </div>
          </div>
        </header>

        <div className="contentScroll" style={{ padding: "20px 28px" }}>
          <h2 style={{ fontSize: 18, margin: "0 0 4px" }}>
            {tab === "schema" ? "스키마 QA" : "스펙 QA"} <span style={{ fontSize: 12, fontWeight: 400, color: "var(--sec)" }}>
              {tab === "schema" ? "JSON-LD 속성·값을 스펙과 대조 (파싱 오류도 검출)" : "스펙 값·고유명사 정확성 (번역 대응)"}</span>
          </h2>

          {ok && <div style={{ background: "#ECFDF3", color: "#067647", padding: "8px 12px", borderRadius: 8, fontSize: 13, margin: "8px 0" }}>{ok}</div>}
          {err && <div style={{ background: "#FEF3F2", color: "#B42318", padding: 10, borderRadius: 8, fontSize: 13, margin: "8px 0" }}>{err}</div>}

          {/* 리전 선택 + 실행 */}
          <div style={{ display: "flex", gap: 6, alignItems: "center", margin: "12px 0 6px", flexWrap: "wrap" }}>
            <span style={{ fontSize: 12.5, color: "var(--sec)" }}>리전:</span>
            {["전체", ...regionNames].map((rg) => (
              <button key={rg} onClick={() => setRegion(rg)}
                style={{ fontSize: 12, padding: "4px 10px", borderRadius: 999, cursor: "pointer",
                  border: region === rg ? "1px solid #0A66E0" : "1px solid var(--line)",
                  background: region === rg ? "#0A66E0" : "#fff", color: region === rg ? "#fff" : "var(--label)" }}>
                {rg}{rg !== "전체" && regionsMap[rg] ? ` ${regionsMap[rg].length}` : ""}
              </button>
            ))}
          </div>
          <button onClick={runByRegion} disabled={busy} style={{ padding: "8px 14px", borderRadius: 8, border: "none", background: HONEY, color: "#fff", fontWeight: 700, cursor: "pointer" }}>
            {busy ? "붕붕 검수 중…" : `${region === "전체" ? allSites.length : (regionsMap[region]?.length || 0)}개 사이트 검수 (크롤 연동 시)`}
          </button>

          {/* 진행 상태바 */}
          {progress.active && (
            <div style={{ marginTop: 10 }}>
              <div style={{ height: 8, background: "#F0F1F3", borderRadius: 999, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${progress.total ? (progress.done / progress.total) * 100 : 0}%`, background: HONEY, transition: "width .3s" }} />
              </div>
              <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 4 }}>🐝 {progress.label} · {progress.done}/{progress.total} 사이트</div>
            </div>
          )}

          <p style={{ fontSize: 12.5, color: "var(--sec)", margin: "14px 0 6px" }}>또는 페이지 HTML을 붙여넣어 즉시 검수:</p>
          <textarea value={html} onChange={(e) => setHtml(e.target.value)} placeholder="<html>… 페이지 소스 …</html>"
            style={{ width: "100%", height: 100, fontFamily: "monospace", fontSize: 12, padding: 8, border: "1px solid var(--line)", borderRadius: 8 }} />
          <button onClick={checkHtml} disabled={busy || !html} style={{ marginTop: 8, padding: "8px 14px", borderRadius: 8, border: "1px solid #0A66E0", background: "#fff", color: "#0A66E0", fontWeight: 700, cursor: "pointer" }}>
            붙여넣은 HTML 검수
          </button>

          {/* 룰 추가 패널 */}
          {showRuleAdd && (
            <div className="card" style={{ marginTop: 16, padding: 14 }}>
              <b style={{ fontSize: 14 }}>룰 추가 — {tab === "schema" ? "스키마" : "스펙"}</b>
              {tab === "schema" ? (
                <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                  <select value={ruleForm.block} onChange={(e) => setRuleForm({ ...ruleForm, block: e.target.value })} style={{ ...inputStyle, width: 200 }}>
                    <option value="">블록 선택</option>
                    {(rules?.schema?.blocks || []).map((b: any, i: number) => <option key={i} value={b.block}>{b.block}</option>)}
                  </select>
                  <input value={ruleForm.property} onChange={(e) => setRuleForm({ ...ruleForm, property: e.target.value })} placeholder="추가할 필수 속성" style={{ ...inputStyle, width: 200 }} />
                  <button onClick={addRule} className="toolBtn">추가</button>
                </div>
              ) : (
                <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                  <select value={ruleForm.kind} onChange={(e) => setRuleForm({ ...ruleForm, kind: e.target.value })} style={{ ...inputStyle, width: 140 }}>
                    <option value="spec">스펙 토큰</option>
                    <option value="proper_noun">고유명사</option>
                  </select>
                  <input value={ruleForm.token} onChange={(e) => setRuleForm({ ...ruleForm, token: e.target.value })} placeholder={ruleForm.kind === "spec" ? "예: 2600 nits" : "예: Corning Gorilla Armor 2"} style={{ ...inputStyle, width: 240 }} />
                  <button onClick={addRule} className="toolBtn">추가</button>
                </div>
              )}
            </div>
          )}

          {/* 검수 기준 패널 */}
          {showRules && rules && (
            <div className="card" style={{ marginTop: 16, padding: 14 }}>
              <b style={{ fontSize: 14 }}>검수 기준 — {tab === "schema" ? "스키마" : "스펙"}</b>
              {tab === "schema" ? (
                <div style={{ fontSize: 12.5, marginTop: 8 }}>
                  <p style={{ color: "var(--sec)" }}>{rules.schema?.["설명"]}</p>
                  {(rules.schema?.blocks || []).map((b: any, i: number) => (
                    <div key={i} style={{ borderTop: "1px solid var(--line)", padding: "6px 0" }}>
                      <b>{b.block}</b> <span style={{ color: "var(--sec)" }}>{(b.types || []).join(", ")}</span>
                      {b.required_properties?.length > 0 && <div>필수: {b.required_properties.join(", ")}</div>}
                    </div>
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

          {/* 결과 */}
          {rows.length > 0 && (
            <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 16, fontSize: 13 }}>
              <thead><tr style={{ color: "var(--sec)", fontSize: 11, textAlign: "left" }}>
                <th style={{ padding: "6px 8px" }}>사이트</th><th style={{ padding: "6px 8px" }}>항목</th>
                <th style={{ padding: "6px 8px" }}>심각도</th><th style={{ padding: "6px 8px" }}>as-is → to-be</th></tr></thead>
              <tbody>
                {rows.map((x, i) => (
                  <tr key={i}>
                    <td style={{ padding: 8, borderTop: "1px solid var(--line)", whiteSpace: "nowrap" }}>{x.r.sitecode}</td>
                    <td style={{ padding: 8, borderTop: "1px solid var(--line)" }}>{x.item}</td>
                    <td style={{ padding: 8, borderTop: "1px solid var(--line)" }}>
                      <span style={{ background: SEV[x.f.status].c, color: "#fff", fontSize: 11, fontWeight: 700, padding: "2px 7px", borderRadius: 5 }}>{SEV[x.f.status].ko}</span>
                    </td>
                    <td style={{ padding: 8, borderTop: "1px solid var(--line)" }}>
                      <div style={{ color: "var(--sec)" }}>{x.f.as_is}</div>
                      <div style={{ fontWeight: 600 }}>→ {x.f.to_be}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {results.length > 0 && rows.length === 0 && (
            <p style={{ color: "#1F9E5C", marginTop: 16 }}>이 탭({tab === "schema" ? "스키마" : "스펙"})에서 발견된 오류가 없어요 🐝</p>
          )}
        </div>
      </div>
    </div>
  );
}
