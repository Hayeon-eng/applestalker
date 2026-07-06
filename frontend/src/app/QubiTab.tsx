"use client";
/**
 * QubiTab.tsx — 큐비 🐝 (QB) Dotcom QA 탭
 * QA의 사촌 QB. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.
 *
 * 기존 애플스토커 프론트(frontend/src/app/)에 드롭인.
 * page.tsx 등에서 우측 진입점/탭으로 <QubiTab apiBase={API} /> 렌더.
 * 백엔드는 dotcom_qa/qb_api.py 의 /api/qb/* 를 사용.
 */
import { useEffect, useState } from "react";

type Finding = { status: "pass" | "warn" | "fail"; as_is?: string; to_be?: string;
  block?: string; token?: string; kind?: string };
type PageResult = { sitecode: string; url: string; region?: string; country?: string;
  schema: { findings: Finding[] }; copy: { findings: Finding[] } };

const SEV = { fail: { ko: "오류", c: "#D8362F" }, warn: { ko: "확인", c: "#E0A008" }, pass: { ko: "정상", c: "#1F9E5C" } };

export default function QubiTab({ apiBase = "" }: { apiBase?: string }) {
  const [tab, setTab] = useState<"run" | "rules">("run");
  const [html, setHtml] = useState("");
  const [product] = useState("M3");
  const [results, setResults] = useState<PageResult[]>([]);
  const [rules, setRules] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const api = (p: string) => `${apiBase}${p}`;

  // 단일 HTML 붙여넣기 검수(네트워크 없이 동작 확인용) — 실제 91사이트는 /run
  const checkHtml = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(api("/api/qb/check"), { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ html, product }) });
      if (!r.ok) throw new Error(`검수 실패 (${r.status})`);
      const d = await r.json();
      setResults([{ sitecode: "(붙여넣기)", url: "", schema: d.schema, copy: d.copy }]);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const runAll = async (sitecodes?: string[]) => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(api("/api/qb/run"), { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product, sitecodes }) });
      if (r.status === 501) throw new Error("크롤러가 연결되지 않았습니다(백엔드 set_fetcher 필요). 우선 HTML 붙여넣기로 검수하세요.");
      if (!r.ok) throw new Error(`실행 실패 (${r.status})`);
      const d = await r.json();
      setResults(d.results || []);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const loadRules = async () => {
    try {
      const r = await fetch(api(`/api/qb/rules?product=${product}`));
      setRules(await r.json());
    } catch (e: any) { setErr(e.message); }
  };
  useEffect(() => { if (tab === "rules" && !rules) loadRules(); }, [tab]);

  const rows: { r: PageResult; f: Finding; area: string; item: string }[] = [];
  for (const r of results) {
    for (const f of r.schema?.findings || []) if (f.status !== "pass")
      rows.push({ r, f, area: "스키마", item: f.block || "" });
    for (const f of r.copy?.findings || []) if (f.status !== "pass")
      rows.push({ r, f, area: `카피·${f.kind || ""}`, item: f.token || "" });
  }

  return (
    <div style={{ fontFamily: "-apple-system,Segoe UI,Arial,sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <h2 style={{ fontSize: 18, margin: 0 }}>큐비 🐝 <span style={{ fontSize: 12, fontWeight: 400, color: "#667085" }}>QA의 사촌 QB · 닷컴 페이지를 붕붕 돌며 규칙대로 검수</span></h2>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
        {(["run", "rules"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            style={{ padding: "6px 12px", borderRadius: 8, border: "1px solid #EAECF0", cursor: "pointer",
              background: tab === t ? "#0A66E0" : "#fff", color: tab === t ? "#fff" : "#344054", fontWeight: 700, fontSize: 13 }}>
            {t === "run" ? "검수 실행" : "검수 기준 ?"}
          </button>
        ))}
      </div>

      {err && <div style={{ background: "#FEF3F2", color: "#B42318", padding: 10, borderRadius: 8, fontSize: 13, marginBottom: 12 }}>{err}</div>}

      {tab === "run" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
            <button onClick={() => runAll()} disabled={busy}
              style={{ padding: "8px 14px", borderRadius: 8, border: "none", background: "#0A66E0", color: "#fff", fontWeight: 700, cursor: "pointer" }}>
              {busy ? "검수 중…" : "91개 사이트 검수(크롤 연동 시)"}
            </button>
          </div>
          <p style={{ fontSize: 12.5, color: "#667085", margin: "0 0 6px" }}>또는 페이지 HTML을 붙여넣어 즉시 검수:</p>
          <textarea value={html} onChange={(e) => setHtml(e.target.value)} placeholder="<html>… 페이지 소스 붙여넣기 …</html>"
            style={{ width: "100%", height: 120, fontFamily: "monospace", fontSize: 12, padding: 8, border: "1px solid #EAECF0", borderRadius: 8 }} />
          <button onClick={checkHtml} disabled={busy || !html}
            style={{ marginTop: 8, padding: "8px 14px", borderRadius: 8, border: "1px solid #0A66E0", background: "#fff", color: "#0A66E0", fontWeight: 700, cursor: "pointer" }}>
            붙여넣은 HTML 검수
          </button>

          {rows.length > 0 && (
            <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 16, fontSize: 13 }}>
              <thead><tr style={{ color: "#667085", fontSize: 11, textAlign: "left" }}>
                <th style={{ padding: "6px 8px" }}>사이트</th><th style={{ padding: "6px 8px" }}>영역</th>
                <th style={{ padding: "6px 8px" }}>항목</th><th style={{ padding: "6px 8px" }}>심각도</th>
                <th style={{ padding: "6px 8px" }}>as-is → to-be</th></tr></thead>
              <tbody>
                {rows.map((x, i) => (
                  <tr key={i}>
                    <td style={{ padding: "8px", borderTop: "1px solid #EAECF0", whiteSpace: "nowrap" }}>{x.r.sitecode}</td>
                    <td style={{ padding: "8px", borderTop: "1px solid #EAECF0" }}>{x.area}</td>
                    <td style={{ padding: "8px", borderTop: "1px solid #EAECF0" }}>{x.item}</td>
                    <td style={{ padding: "8px", borderTop: "1px solid #EAECF0" }}>
                      <span style={{ background: SEV[x.f.status].c, color: "#fff", fontSize: 11, fontWeight: 700, padding: "2px 7px", borderRadius: 5 }}>{SEV[x.f.status].ko}</span>
                    </td>
                    <td style={{ padding: "8px", borderTop: "1px solid #EAECF0" }}>
                      <div style={{ color: "#667085" }}>{x.f.as_is}</div>
                      <div style={{ color: "#101318", fontWeight: 600 }}>→ {x.f.to_be}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "rules" && rules && (
        <div style={{ fontSize: 13, color: "#344054" }}>
          <p style={{ color: "#667085", fontSize: 12.5 }}>큐비가 이 기준으로 검수합니다. 왜 오류로 잡혔는지 여기서 확인하세요.</p>
          <h3 style={{ fontSize: 14, margin: "12px 0 6px" }}>스키마 규칙</h3>
          <p style={{ fontSize: 12, color: "#667085", margin: "0 0 8px" }}>{rules.schema?.설명}</p>
          {(rules.schema?.blocks || []).map((b: any, i: number) => (
            <div key={i} style={{ border: "1px solid #EAECF0", borderRadius: 8, padding: 10, marginBottom: 8 }}>
              <b>{b.block}</b> <span style={{ color: "#98A2B3", fontSize: 11 }}>{(b.types || []).join(", ")} · {b.id}</span>
              {b.required_properties?.length > 0 && <div style={{ fontSize: 12, marginTop: 4 }}>필수 속성: {b.required_properties.join(", ")}</div>}
              {b.haspart_ids?.length > 0 && <div style={{ fontSize: 12, marginTop: 2 }}>hasPart @id: {b.haspart_ids.join(", ")}</div>}
              {b.conditional && <div style={{ fontSize: 11.5, color: "#E0A008", marginTop: 2 }}>조건부(없으면 확인): {b.conditional}</div>}
            </div>
          ))}
          <h3 style={{ fontSize: 14, margin: "16px 0 6px" }}>카피 규칙</h3>
          <p style={{ fontSize: 12, color: "#667085", margin: "0 0 8px" }}>{rules.copy?.설명}</p>
          <div style={{ fontSize: 12.5 }}><b>스펙 토큰(정확 일치):</b> {(rules.copy?.spec_tokens || []).join(", ")}</div>
          <div style={{ fontSize: 12.5, marginTop: 6 }}><b>고유명사(존재 확인):</b> {(rules.copy?.proper_nouns || []).join(", ")}</div>
        </div>
      )}
    </div>
  );
}
