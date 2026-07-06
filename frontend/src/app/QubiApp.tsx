"use client";
/**
 * QubiApp.tsx — 큐비 🐝 (QA Bee) 독립 앱
 * 애플스토커와 별개의 풀 화면 도구. 상단 탭: [스키마 QA] [카피 QA]
 * 사이드바: 큐비 URL 관리 / (카피) 스펙 관리
 * 백엔드: /api/qb/*
 */
import { useEffect, useMemo, useState } from "react";

type Finding = { status: "pass" | "warn" | "fail"; as_is?: string; to_be?: string;
  block?: string; token?: string; kind?: string };
type PageResult = { sitecode: string; url: string; region?: string; country?: string;
  schema: { findings: Finding[] }; copy: { findings: Finding[] } };
type SiteRow = { sitecode: string; country?: string; lang?: string; url: string };

const SEV = { fail: { ko: "오류", c: "#D8362F" }, warn: { ko: "확인", c: "#E0A008" }, pass: { ko: "정상", c: "#1F9E5C" } };

export default function QubiApp({ apiBase = "", onHome }: { apiBase?: string; onHome?: () => void }) {
  const [tab, setTab] = useState<"schema" | "copy">("schema");
  const [product] = useState("M3");
  const [html, setHtml] = useState("");
  const [results, setResults] = useState<PageResult[]>([]);
  const [rules, setRules] = useState<any>(null);
  const [showRules, setShowRules] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [online, setOnline] = useState<boolean | null>(null);

  // 사이드바 데이터
  const [sites, setSites] = useState<SiteRow[]>([]);
  const [sitesOpen, setSitesOpen] = useState(false);
  const [specs, setSpecs] = useState<any[]>([]);
  const [newUrl, setNewUrl] = useState("");
  const [newSpec, setNewSpec] = useState({ product: "galaxy-s26-ultra", category: "", value: "", unit: "" });

  const api = (p: string) => `${apiBase}${p}`;

  useEffect(() => {
    fetch(api("/api/health")).then((r) => setOnline(r.ok)).catch(() => setOnline(false));
    loadSites(); loadSpecs();
  }, []);
  useEffect(() => { if (showRules && !rules) loadRules(); }, [showRules]);

  async function loadSites() {
    try {
      const r = await fetch(api("/api/qb/sites")); const d = await r.json();
      const flat: SiteRow[] = [];
      Object.values(d.regions || {}).forEach((arr: any) => arr.forEach((s: SiteRow) => flat.push(s)));
      setSites(flat);
    } catch { /* noop */ }
  }
  async function loadSpecs() {
    try { const r = await fetch(api(`/api/qb/specs?product=galaxy-s26-ultra`)); setSpecs((await r.json()).specs || []); } catch { /* */ }
  }
  async function loadRules() {
    try { const r = await fetch(api(`/api/qb/rules?product=${product}`)); setRules(await r.json()); } catch (e: any) { setErr(String(e)); }
  }

  const checkHtml = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(api("/api/qb/check"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ html, product }) });
      if (!r.ok) throw new Error(`검수 실패 (${r.status})`);
      const d = await r.json();
      setResults([{ sitecode: "(붙여넣기)", url: "", schema: d.schema, copy: d.copy }]);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const runAll = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(api("/api/qb/run"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product }) });
      if (r.status === 501) throw new Error("크롤러 미연결(백엔드 enable_default_crawler 필요). HTML 붙여넣기로 검수하세요.");
      if (!r.ok) throw new Error(`실행 실패 (${r.status})`);
      setResults((await r.json()).results || []);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const downloadXlsx = async () => {
    const r = await fetch(api("/api/qb/report.xlsx"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ results }) });
    const blob = await r.blob(); const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "qubi_qa_report.xlsx"; a.click();
  };

  const addUrl = async () => {
    if (!newUrl.trim()) return;
    await fetch(api("/api/qb/sites/add"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: newUrl.trim() }) });
    setNewUrl(""); loadSites();
  };
  const removeUrl = async (sc: string) => { await fetch(api("/api/qb/sites/remove"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sitecode: sc }) }); loadSites(); };
  const addSpec = async () => {
    if (!newSpec.category || !newSpec.value) return;
    await fetch(api("/api/qb/specs/add"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newSpec) });
    setNewSpec({ ...newSpec, category: "", value: "", unit: "" }); loadSpecs();
  };
  const removeSpec = async (i: number) => { await fetch(api("/api/qb/specs/remove"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ index: i, product: "galaxy-s26-ultra" }) }); loadSpecs(); };

  // 현재 탭에 맞는 결과 행
  const rows = useMemo(() => {
    const out: { r: PageResult; f: Finding; item: string }[] = [];
    for (const r of results) {
      const fs = tab === "schema" ? (r.schema?.findings || []) : (r.copy?.findings || []);
      for (const f of fs) if (f.status !== "pass") out.push({ r, f, item: f.block || f.token || "" });
    }
    return out;
  }, [results, tab]);

  return (
    <div className="appShell">
      {/* ── 사이드바 ── */}
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🐝 큐비 <span style={{ fontSize: 12, fontWeight: 400 }}>QA Bee</span></div>
        <div className="brandSub">삼성닷컴 스키마·카피 QA 검수</div>
        <div className={`connBadge ${online === true ? "ok" : "bad"}`}>
          <span className="connDot" />{online === null ? "확인 중" : online ? "백엔드 연결됨" : "연결 안 됨"}
        </div>

        <div className="sideScroll">
          {/* URL 관리 */}
          <div className="sideLabel">URL 관리</div>
          <div style={{ padding: "0 6px", marginBottom: 8 }}>
            <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="https://www.samsung.com/…/compare/"
              style={{ width: "100%", fontSize: 12, padding: "6px 8px", border: "1px solid var(--line)", borderRadius: 6 }} />
            <button onClick={addUrl} style={{ marginTop: 6, fontSize: 12, fontWeight: 700, color: "#0A66E0", background: "none", border: "none", cursor: "pointer" }}>＋ URL 추가</button>
          </div>
          <div className="sideLabel" style={{ cursor: "pointer" }} onClick={() => setSitesOpen((o) => !o)}>
            {sitesOpen ? "▾" : "▸"} 모니터링 URL 목록 <span className="muted">{sites.length}개</span>
          </div>
          {sitesOpen && sites.map((s) => (
            <div key={s.sitecode} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 6px", fontSize: 11.5 }}>
              <span title={s.url}>{s.sitecode} <span className="muted">{s.country}</span></span>
              <span role="button" onClick={() => removeUrl(s.sitecode)} style={{ cursor: "pointer", color: "var(--high)", fontSize: 11 }}>삭제</span>
            </div>
          ))}

          {/* 스펙 관리 — 카피 탭에서 사용 */}
          {tab === "copy" && (
            <>
              <div className="sideLabel" style={{ marginTop: 12 }}>스펙 기준 관리 <span className="muted">(제품·항목·값)</span></div>
              <div style={{ padding: "0 6px" }}>
                <input value={newSpec.product} onChange={(e) => setNewSpec({ ...newSpec, product: e.target.value })} placeholder="제품 (galaxy-s26-ultra)"
                  style={{ width: "100%", fontSize: 11.5, padding: "5px 7px", border: "1px solid var(--line)", borderRadius: 6, marginBottom: 4 }} />
                <div style={{ display: "flex", gap: 4 }}>
                  <input value={newSpec.category} onChange={(e) => setNewSpec({ ...newSpec, category: e.target.value })} placeholder="항목(video_playback)"
                    style={{ flex: 2, fontSize: 11.5, padding: "5px 7px", border: "1px solid var(--line)", borderRadius: 6 }} />
                  <input value={newSpec.value} onChange={(e) => setNewSpec({ ...newSpec, value: e.target.value })} placeholder="값(31)"
                    style={{ width: 52, fontSize: 11.5, padding: "5px 7px", border: "1px solid var(--line)", borderRadius: 6 }} />
                  <input value={newSpec.unit} onChange={(e) => setNewSpec({ ...newSpec, unit: e.target.value })} placeholder="단위"
                    style={{ width: 48, fontSize: 11.5, padding: "5px 7px", border: "1px solid var(--line)", borderRadius: 6 }} />
                </div>
                <button onClick={addSpec} style={{ marginTop: 6, fontSize: 12, fontWeight: 700, color: "#0A66E0", background: "none", border: "none", cursor: "pointer" }}>＋ 스펙 추가</button>
              </div>
              {specs.map((sp, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "3px 6px", fontSize: 11.5 }}>
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
              <button className={`tabBtn ${tab === "copy" ? "on" : ""}`} onClick={() => setTab("copy")}>카피 QA</button>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              <button className="toolBtn" onClick={() => setShowRules((v) => !v)}>ⓘ 검수 기준</button>
              <button className="toolBtn" onClick={downloadXlsx} disabled={!results.length}>📊 Excel</button>
            </div>
          </div>
        </header>

        <div className="contentScroll">
          <h2 style={{ fontSize: 18, margin: "0 0 4px" }}>
            {tab === "schema" ? "스키마 QA" : "카피 QA"} <span style={{ fontSize: 12, fontWeight: 400, color: "var(--sec)" }}>
              {tab === "schema" ? "JSON-LD를 스펙과 대조" : "스펙 값·고유명사 정확성(번역 대응)"}</span>
          </h2>

          {err && <div style={{ background: "#FEF3F2", color: "#B42318", padding: 10, borderRadius: 8, fontSize: 13, margin: "8px 0" }}>{err}</div>}

          <div style={{ display: "flex", gap: 8, margin: "10px 0", flexWrap: "wrap" }}>
            <button onClick={runAll} disabled={busy} style={{ padding: "8px 14px", borderRadius: 8, border: "none", background: "#0A66E0", color: "#fff", fontWeight: 700, cursor: "pointer" }}>
              {busy ? "검수 중…" : "91개 사이트 검수(크롤 연동 시)"}
            </button>
          </div>
          <p style={{ fontSize: 12.5, color: "var(--sec)", margin: "0 0 6px" }}>또는 페이지 HTML을 붙여넣어 즉시 검수:</p>
          <textarea value={html} onChange={(e) => setHtml(e.target.value)} placeholder="<html>… 페이지 소스 …</html>"
            style={{ width: "100%", height: 110, fontFamily: "monospace", fontSize: 12, padding: 8, border: "1px solid var(--line)", borderRadius: 8 }} />
          <button onClick={checkHtml} disabled={busy || !html} style={{ marginTop: 8, padding: "8px 14px", borderRadius: 8, border: "1px solid #0A66E0", background: "#fff", color: "#0A66E0", fontWeight: 700, cursor: "pointer" }}>
            붙여넣은 HTML 검수
          </button>

          {showRules && rules && (
            <div className="card" style={{ marginTop: 16, padding: 14 }}>
              <b style={{ fontSize: 14 }}>검수 기준 — {tab === "schema" ? "스키마" : "카피"}</b>
              {tab === "schema" ? (
                <div style={{ fontSize: 12.5, marginTop: 8 }}>
                  <p style={{ color: "var(--sec)" }}>{rules.schema?.설명}</p>
                  {(rules.schema?.blocks || []).map((b: any, i: number) => (
                    <div key={i} style={{ borderTop: "1px solid var(--line)", padding: "6px 0" }}>
                      <b>{b.block}</b> <span className="muted">{(b.types || []).join(", ")}</span>
                      {b.required_properties?.length > 0 && <div>필수: {b.required_properties.join(", ")}</div>}
                      {b.haspart_ids?.length > 0 && <div>hasPart: {b.haspart_ids.join(", ")}</div>}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12.5, marginTop: 8 }}>
                  <p style={{ color: "var(--sec)" }}>{rules.copy?.설명}</p>
                  <div><b>스펙 토큰:</b> {(rules.copy?.spec_tokens || []).join(", ")}</div>
                  <div style={{ marginTop: 6 }}><b>고유명사:</b> {(rules.copy?.proper_nouns || []).join(", ")}</div>
                </div>
              )}
            </div>
          )}

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
            <p style={{ color: "#1F9E5C", marginTop: 16 }}>이 탭({tab === "schema" ? "스키마" : "카피"})에서 발견된 오류가 없습니다.</p>
          )}
        </div>
      </div>
    </div>
  );
}
