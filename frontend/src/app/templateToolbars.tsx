"use client";
/* templateToolbars.tsx — 운영 양식(엑셀) 왕복 도구 [2026-11 신규]
   ① ProductPackToolbar : 큐비 제품 등록 워크북 — 제품정보·URL·스펙 룰·스키마 정답값 (제품 1개 = 파일 1개)
   ② TargetsToolbar     : 모니터링 대상 워크북 — appleStalker URL + honeyComb 국가·제품·경쟁사·키워드
   둘 다 "템플릿 ⬇ · 현재 값 ⬇ · 업로드 ⬆" 세 동작이 전부다. 모델이 바뀌면 코드가 아니라 이 파일을 고친다. */
import { useRef, useState } from "react";

type Api = (p: string) => string;
type Flash = (m: string) => void;

async function downloadTo(api: Api, flash: Flash, path: string, filename: string) {
  try {
    const r = await fetch(api(path));
    if (!r.ok) throw new Error(String((await r.json().catch(() => ({}))).detail || r.status));
    const blob = await r.blob();
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = href; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(href), 1500);
  } catch (e: any) { flash(`다운로드 실패 — ${e.message || e}`); }
}
const readB64 = (f: File) => new Promise<string>((res, rej) => { const rd = new FileReader(); rd.onload = () => res(String(rd.result)); rd.onerror = rej; rd.readAsDataURL(f); });
const btn: React.CSSProperties = { fontSize: 11.5, padding: "4px 9px" };
const sel: React.CSSProperties = { fontSize: 11.5, padding: "3px 6px", borderRadius: 6, border: "1px solid var(--line)" };

/* ── ① 큐비 제품 등록 워크북 ─────────────────────────────────────── */
export function ProductPackToolbar({ api, flash, product, compact }: { api: Api; flash: Flash; product?: string; compact?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"add" | "upsert" | "replace_product">("upsert");
  const [report, setReport] = useState<any>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const prod = product || "galaxy-z-fold8";
  const draft = () => {
    const to = window.prompt(`신모델 전환 초안 — '${prod}' 를 기준으로 새 제품키(URL 슬러그)를 입력하세요.\n예: galaxy-z-fold9`, "");
    if (!to) return;
    const label = window.prompt("새 제품 표시명(비우면 자동 추정)", "") || "";
    downloadTo(api, flash, `/api/qb/product-pack/draft.xlsx?from=${encodeURIComponent(prod)}&to=${encodeURIComponent(to.trim())}&label=${encodeURIComponent(label)}`, `qubi_product_pack_draft_${to.trim()}.xlsx`);
  };
  const upload = async (f?: File) => {
    if (!f) return;
    setBusy(true); setReport(null);
    try {
      const b64 = await readB64(f);
      const r = await fetch(api("/api/qb/product-pack/upload"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ b64, url_mode: mode }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(String(d.detail || r.status));
      setReport(d); flash(`제품 등록 워크북 반영 — ${d.product} 🐝`);
    } catch (e: any) { flash(`업로드 실패 — ${e.message || e}`); setReport({ error: String(e.message || e) }); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  const applied = report?.applied || {};
  return (
    <div style={{ marginTop: compact ? 6 : 10, display: "flex", flexDirection: "column", gap: 4, fontSize: 11.5 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <span style={{ color: "var(--sec)" }}><b>제품 등록 워크북</b> (제품정보·URL·스펙 룰·스키마 정답값, 제품 1개 = 파일 1개):</span>
        <button className="btnSecondary" style={btn} onClick={() => downloadTo(api, flash, `/api/qb/product-pack/template.xlsx?example=${encodeURIComponent(prod)}`, "qubi_product_pack_template.xlsx")}>⬇ 템플릿(예시 포함)</button>
        <button className="btnSecondary" style={btn} onClick={() => downloadTo(api, flash, `/api/qb/product-pack/export.xlsx?product=${encodeURIComponent(prod)}`, `qubi_product_pack_${prod}.xlsx`)}>⬇ {prod} 현재 값</button>
        <button className="btnSecondary" style={btn} onClick={draft}>✨ 신모델 초안 ({prod} → 새 제품)</button>
        <span style={{ color: "var(--sec)" }}>URL 모드</span>
        <select style={sel} value={mode} onChange={(e) => setMode(e.target.value as any)}>
          <option value="add">추가(중복 건너뜀)</option>
          <option value="upsert">갱신(같은 사이트·제품·페이지면 교체)</option>
          <option value="replace_product">제품 단위 교체</option>
        </select>
        <button className="btnSecondary" style={btn} disabled={busy} onClick={() => fileRef.current?.click()}>{busy ? "반영 중…" : "⬆ 워크북 업로드"}</button>
        <input ref={fileRef} type="file" accept=".xlsx" style={{ display: "none" }} onChange={(e) => upload(e.target.files?.[0])} />
      </div>
      {report && !report.error && (
        <div style={{ color: "var(--sec)", padding: "4px 8px", background: "var(--bg)", borderRadius: 6 }}>
          반영됨 — {Object.keys(applied).map((k) => {
            const v = applied[k];
            const txt = Array.isArray(v) ? `${v.length}건` : typeof v === "object" ? Object.entries(v).filter(([kk]) => kk !== "mode").map(([kk, vv]) => `${kk} ${typeof vv === "object" ? JSON.stringify(vv) : vv}`).join(" · ") : String(v);
            return <span key={k} style={{ marginRight: 10 }}><b>{k}</b> {txt}</span>;
          })}
          {report.warnings?.length > 0 && <div style={{ marginTop: 3 }}>참고 {report.warnings.length}건: {report.warnings.slice(0, 3).join(" / ")}{report.warnings.length > 3 ? " …" : ""}</div>}
        </div>
      )}
      {report?.error && <span style={{ color: "var(--red-ink)" }}>{report.error}</span>}
    </div>
  );
}

/* ── ② 모니터링 대상 워크북 (appleStalker URL + honeyComb) ────────── */
export function TargetsToolbar({ apiBase, flash, askPassword }: { apiBase: string; flash: Flash; askPassword: () => string | null }) {
  const api: Api = (p) => apiBase.replace(/\/+$/, "") + p;
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"upsert" | "replace">("upsert");
  const [report, setReport] = useState<any>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = async (f?: File) => {
    if (!f) return;
    const pw = askPassword(); if (pw === null) return;
    setBusy(true); setReport(null);
    try {
      const b64 = await readB64(f);
      const r = await fetch(api("/api/targets/upload"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ b64, admin_password: pw, mode }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(String(d.detail || r.status));
      setReport(d); flash("모니터링 대상 반영 완료");
    } catch (e: any) { flash(`업로드 실패 — ${e.message || e}`); setReport({ error: String(e.message || e) }); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  const a = report?.applied || {};
  return (
    <div style={{ padding: "4px 6px 8px", display: "flex", flexDirection: "column", gap: 5, fontSize: 11.5 }}>
      <div style={{ color: "var(--sec)" }}>모니터링 대상 양식 — appleStalker URL(당사·경쟁사) + honeyComb 국가·제품·경쟁사 모델·키워드를 엑셀 1개로</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <button className="btnSecondary" style={btn} onClick={() => downloadTo(api, flash, "/api/targets/template.xlsx", "monitor_targets_template.xlsx")}>⬇ 템플릿</button>
        <button className="btnSecondary" style={btn} onClick={() => downloadTo(api, flash, "/api/targets/export.xlsx", "monitor_targets_current.xlsx")}>⬇ 현재 값</button>
        <select style={sel} value={mode} onChange={(e) => setMode(e.target.value as any)}>
          <option value="upsert">갱신(파일의 Y/N만 반영)</option>
          <option value="replace">교체(파일에 없는 URL·키워드는 끔)</option>
        </select>
        <button className="btnSecondary" style={btn} disabled={busy} onClick={() => fileRef.current?.click()}>{busy ? "반영 중…" : "⬆ 업로드"}</button>
        <input ref={fileRef} type="file" accept=".xlsx" style={{ display: "none" }} onChange={(e) => upload(e.target.files?.[0])} />
      </div>
      {report && !report.error && (
        <div style={{ color: "var(--sec)" }}>
          {a.AS_URL && <span>URL 켬 {a.AS_URL.enabled} · 끔 {a.AS_URL.disabled} </span>}
          {["HC_국가", "HC_제품", "HC_경쟁사모델"].filter((k) => a[k] != null).map((k) => <span key={k}>· {k} {a[k]}건 </span>)}
          {a["HC_키워드"] && <span>· 키워드 {a["HC_키워드"].rows}건(총 {a["HC_키워드"].total})</span>}
          {report.warnings?.length > 0 && <div>참고: {report.warnings.slice(0, 3).join(" / ")}</div>}
        </div>
      )}
      {report?.error && <span style={{ color: "var(--red-ink)" }}>{report.error}</span>}
    </div>
  );
}
