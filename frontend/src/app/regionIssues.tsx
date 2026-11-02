"use client";
/* regionIssues.tsx — [2026-11 E1 v2] 권역 OVERVIEW 본문
   ① Summary  : A/B/C 툴마다 그 툴에 맞는 대표 지표(크게) + 통일 기준(작은 주석: 문제 사이트 수 / 검수 수)
   ② 급한 이슈 : 길어도 '무엇을 검사했고 · 어디가 · 왜 문제인지'가 읽히는 문장 + [보기]로 해당 화면 이동
   ③ 사이트별 현황 : 사이트 행 × 툴 열(짧은 원인). 행을 누르면 설명형 세부 + 이동
   문장·지표는 백엔드 insight_rules.region_insights 가 만든다(단일 소스). */
import { useState } from "react";
import type { NavTarget } from "./navTarget";

const LETTER: Record<string, { c: string; soft: string }> = {
  A: { c: "#C62828", soft: "#FDECEC" }, B: { c: "#8A5A00", soft: "#FFF4D6" }, C: { c: "#7A4E00", soft: "#FBEFD9" },
};
const TOOL_OF: Record<string, { letter: string; label: string }> = {
  apple: { letter: "A", label: "appleStalker" }, data: { letter: "B", label: "DATA QA" }, spec: { letter: "B", label: "스펙 QA" },
  static: { letter: "B", label: "공통페이지 QA" }, hc: { letter: "C", label: "honeyComb" },
};
const SEV_C: Record<number, string> = { 1: "#D8362F", 2: "#E0A008", 3: "#98A2B3" };
const GO_LABEL = (g: any) => g?.app === "applestalker" ? "appleStalker에서 보기" : g?.app === "honeycomb" ? "honeyComb에서 보기"
  : g?.tab === "static" ? "공통페이지 QA에서 보기" : g?.tab === "copy" ? "스펙 QA에서 보기" : "DATA QA에서 보기";

const Letter = ({ l }: { l: string }) => (
  <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 18, height: 18, borderRadius: 5,
    fontSize: 11, fontWeight: 800, color: LETTER[l]?.c, background: LETTER[l]?.soft, flex: "none" }}>{l}</span>);
const Dot = ({ sev }: { sev: number }) => <span style={{ width: 8, height: 8, borderRadius: 999, background: SEV_C[sev] || SEV_C[3], flex: "none", display: "inline-block" }} />;
const goBtn = (g: any, onGo: (t: NavTarget) => void) => g?.app ? (
  <button className="btnSecondary" style={{ fontSize: 11, padding: "3px 9px", whiteSpace: "nowrap", flex: "none" }}
    onClick={(e) => { e.stopPropagation(); onGo({ ...g, n: Date.now() }); }}>{GO_LABEL(g)} →</button>) : null;

/** 설명형 이슈 한 줄 (법인 패널·사이트 표 세부에서도 사용) */
export function IssueDetail({ d, onGo }: { d: any; onGo: (t: NavTarget) => void }) {
  const t = TOOL_OF[d.tool] || { letter: "", label: d.tool };
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "7px 8px", borderTop: "1px dashed var(--line)", fontSize: 12.5 }}>
      <span style={{ marginTop: 5 }}><Dot sev={d.sev} /></span>
      <span style={{ flex: 1, lineHeight: 1.55 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: "var(--sec)", marginRight: 6 }}>{t.label}</span>{d.text}
        {d.action && <div style={{ color: "var(--blue)", fontWeight: 700, marginTop: 2 }}>→ {d.action}</div>}
      </span>
      {goBtn(d.go, onGo)}
    </div>);
}

export function RegionSummary({ ins, onGo }: { ins: any; onGo: (t: NavTarget) => void }) {
  const [tool, setTool] = useState<string | null>(null);
  const [region, setRegion] = useState("all");
  const [open, setOpen] = useState<string | null>(null);
  const [more, setMore] = useState(false);
  const [openU, setOpenU] = useState<number | null>(null);
  const tiles: any[] = ins?.summary || [];
  const rows: any[] = (ins?.sites || []).filter((r: any) => (!tool || r.cells[tool]) && (region === "all" || r.region === region));
  const regions = [...new Set((ins?.sites || []).map((r: any) => r.region).filter(Boolean))] as string[];
  const shown = more ? rows : rows.slice(0, 10);
  const COLS = [["data", "DATA"], ["spec", "스펙"], ["static", "공통페이지"], ["hc", "노출"]];
  const grid = "minmax(150px,1.1fr) repeat(4, minmax(0,1fr))";
  return (
    <div style={{ padding: "12px 16px 0", display: "grid", gap: 12 }}>
      {/* ① Summary */}
      <div className="rgGlass" style={{ padding: "12px 14px" }}>
        <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 8 }}>Summary</div>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.max(tiles.length, 1)}, minmax(0,1fr))`, gap: 10 }}>
          {tiles.map((t) => {
            const on = tool === t.key;
            return (
              <div key={t.key} onClick={() => t.key !== "apple" && setTool(on ? null : t.key)}
                style={{ background: on ? "#fff" : "rgba(255,255,255,.6)", border: `1px solid ${on ? "var(--label)" : "var(--line)"}`, borderRadius: 10, padding: "10px 12px", cursor: t.key === "apple" ? "default" : "pointer" }}
                title={t.key === "apple" ? "" : "누르면 아래 사이트 표를 이 툴 기준으로 거릅니다"}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}><Letter l={t.letter} /><b style={{ fontSize: 12.5 }}>{t.name}</b></div>
                <div style={{ fontSize: 11, color: "var(--sec)", marginTop: 2 }}>{t.sub}</div>
                <div style={{ fontSize: 24, fontWeight: 800, marginTop: 6, lineHeight: 1.1 }}>{t.metric}</div>
                <div style={{ fontSize: 11.5, color: "var(--label2)" }}>{t.metric_label}</div>
                {t.cause && <div style={{ fontSize: 11.5, marginTop: 6, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={t.cause}>가장 많은 문제 · {t.cause}</div>}
                <div style={{ fontSize: 10.5, color: "var(--gray)", marginTop: 6, borderTop: "1px dashed var(--line)", paddingTop: 5, display: "flex", alignItems: "center" }}>
                  <span>{t.note}</span>
                  <span role="button" style={{ marginLeft: "auto", color: "var(--blue)", cursor: "pointer" }} onClick={(e) => { e.stopPropagation(); onGo({ ...t.go, n: Date.now() }); }}>열기 →</span>
                </div>
              </div>);
          })}
        </div>
        <div style={{ fontSize: 10.5, color: "var(--gray)", marginTop: 8 }}>{ins?.basis}</div>
      </div>

      {/* ② 급한 이슈 */}
      <div className="rgGlass" style={{ padding: "12px 14px" }}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>급한 이슈 <span style={{ fontWeight: 400, fontSize: 11.5, color: "var(--sec)" }}>— 🔴 판정만 · 툴마다 가장 심한 것부터</span></div>
        {!(ins?.urgent || []).length && <div style={{ fontSize: 12.5, color: "var(--sec)", marginTop: 6 }}>지금 고쳐야 할 이슈 없음</div>}
        {(ins?.urgent || []).map((u: any, i: number) => {
          const t = TOOL_OF[u.tool] || { letter: "", label: "" };
          return (
            <div key={i} style={{ borderTop: i ? "1px solid var(--line)" : undefined, padding: "8px 0" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 8, cursor: u.details ? "pointer" : "default" }} onClick={() => u.details && setOpenU(openU === i ? null : i)}>
                <Letter l={t.letter} />
                <div style={{ flex: 1, fontSize: 13, lineHeight: 1.55 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "var(--sec)", marginRight: 6 }}>{t.label}{u.rule === "R2" ? " · 여러 권역 공통" : ""}</span>{u.text}
                  {u.action && <div style={{ color: "var(--blue)", fontWeight: 700, marginTop: 2 }}>→ {u.action}</div>}
                  {u.details && <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 2 }}>{openU === i ? "▾ 접기" : `▸ 해당 사이트 ${u.details.length}곳 보기`}</div>}
                </div>
                {goBtn(u.go, onGo)}
              </div>
              {openU === i && u.details?.map((d: any, j: number) => <IssueDetail key={j} d={d} onGo={onGo} />)}
            </div>);
        })}
      </div>

      {/* ③ 사이트별 현황 */}
      <div className="rgGlass" style={{ padding: "12px 14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <b style={{ fontSize: 13 }}>사이트별 현황</b>
          <span style={{ fontSize: 11.5, color: "var(--sec)" }}>{tool ? `${(tiles.find((t) => t.key === tool) || {}).name} 문제 사이트` : "문제가 있는 사이트"} {rows.length}곳 · 🔴 많은 순 · 행을 누르면 내용과 이동 버튼</span>
          {tool && <span role="button" style={{ fontSize: 11.5, color: "var(--blue)", cursor: "pointer" }} onClick={() => setTool(null)}>툴 필터 해제</span>}
          <select value={region} onChange={(e) => setRegion(e.target.value)} style={{ marginLeft: "auto", fontSize: 12, padding: "3px 6px", borderRadius: 6, border: "1px solid var(--line)" }}>
            <option value="all">전체 권역</option>{regions.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: grid, gap: 8, fontSize: 11, color: "var(--sec)", padding: "8px 6px 4px", borderBottom: "1px solid var(--line)" }}>
          <span>사이트 · 법인 · 권역</span>
          {COLS.map(([k, l]) => <span key={k} style={{ display: "flex", alignItems: "center", gap: 4 }}><Letter l={k === "hc" ? "C" : "B"} />{l}</span>)}
        </div>
        {shown.map((r: any) => (
          <div key={r.sitecode}>
            <div onClick={() => setOpen(open === r.sitecode ? null : r.sitecode)}
              style={{ display: "grid", gridTemplateColumns: grid, gap: 8, padding: "8px 6px", borderBottom: "1px solid var(--line)", cursor: "pointer", fontSize: 12.5, alignItems: "center",
                background: open === r.sitecode ? "rgba(255,255,255,.75)" : undefined }}>
              <span><b>{(r.sitecode || "").toUpperCase()}</b> <span style={{ fontSize: 11, color: "var(--sec)" }}>{r.subs} · {r.region}</span></span>
              {COLS.map(([k]) => { const c = r.cells[k];
                return <span key={k} style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }} title={c?.short || "문제 없음 또는 미검수"}>
                  {c ? <><Dot sev={c.sev} /><span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.short}</span></> : <span style={{ color: "var(--ter)" }}>—</span>}</span>; })}
            </div>
            {open === r.sitecode && <div style={{ background: "rgba(255,255,255,.75)", paddingBottom: 4 }}>{r.details.map((d: any, j: number) => <IssueDetail key={j} d={d} onGo={onGo} />)}</div>}
          </div>))}
        {rows.length > 10 && <div role="button" onClick={() => setMore(!more)} style={{ fontSize: 12, color: "var(--blue)", padding: "8px 6px", cursor: "pointer" }}>{more ? "접기" : `${rows.length}곳 모두 보기`}</div>}
        <div style={{ fontSize: 10.5, color: "var(--gray)", marginTop: 6 }}>— = 문제 없음 또는 아직 검수 전 · 🔴 지금 고쳐야 함 · 🟡 확인 필요 · A(appleStalker)는 경쟁사 사이트 기준이라 이 표에는 없고 Summary·급한 이슈에 표시</div>
      </div>
    </div>);
}
