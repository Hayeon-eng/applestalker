"use client";
/* regionIssues.tsx — [2026-11 E1 v2] 권역 OVERVIEW 본문
   ① Summary  : A/B/C 툴마다 그 툴에 맞는 대표 지표(크게) + 통일 기준(작은 주석: 문제 사이트 수 / 검수 수)
   ② 급한 이슈 : 길어도 '무엇을 검사했고 · 어디가 · 왜 문제인지'가 읽히는 문장 + [보기]로 해당 화면 이동
   ③ 사이트별 현황 : 사이트 행 × 툴 열(짧은 원인). 행을 누르면 설명형 세부 + 이동
   문장·지표는 백엔드 insight_rules.region_insights 가 만든다(단일 소스). */
import { useState } from "react";
import type { NavTarget } from "./navTarget";
import { TOOL_THEME, letterOf, SUBTOOL, sevTheme, type ToolLetter } from "./toolTheme";

const TOOL_OF: Record<string, { letter: ToolLetter; label: string }> = Object.fromEntries(
  Object.entries(SUBTOOL).map(([k, v]) => [k, { letter: letterOf(k), label: v }])) as any;
const SEV_C: Record<number, string> = { 1: "#D8362F", 2: "#E0A008", 3: "#98A2B3" };
const GO_LABEL = (g: any) => g?.app === "applestalker" ? "appleStalker에서 보기" : g?.app === "honeycomb" ? "honeyComb에서 보기"
  : g?.tab === "static" ? "공통페이지 QA에서 보기" : g?.tab === "copy" ? "스펙 QA에서 보기" : "DATA QA에서 보기";

/** 툴 배지 — 아이콘 + 툴 색. sub 를 주면 'qaBee · 스펙 QA'처럼 세부 검수까지 */
export const ToolBadge = ({ l, sub, size = "sm" }: { l: ToolLetter; sub?: string; size?: "sm" | "lg" }) => {
  const t = TOOL_THEME[l];
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, flex: "none", fontSize: size === "lg" ? 12.5 : 11, fontWeight: 700,
      color: t.ink, background: t.soft, border: `1px solid ${t.color}33`, borderRadius: 999, padding: size === "lg" ? "3px 10px 3px 4px" : "1px 8px 1px 3px" }}>
      <span style={{ width: size === "lg" ? 22 : 16, height: size === "lg" ? 22 : 16, borderRadius: 999, background: "#fff", display: "inline-flex",
        alignItems: "center", justifyContent: "center", fontSize: size === "lg" ? 13 : 10.5, boxShadow: `0 0 0 1.5px ${t.color}` }}>{t.icon}</span>
      {t.name}{sub ? <span style={{ fontWeight: 500, opacity: .85 }}>· {sub}</span> : null}
    </span>);
};
const Dot = ({ sev }: { sev: number }) => <span style={{ width: 8, height: 8, borderRadius: 999, background: SEV_C[sev] || SEV_C[3], flex: "none", display: "inline-block" }} />;
const goBtn = (g: any, onGo: (t: NavTarget) => void) => g?.app ? (
  <button className="btnSecondary" style={{ fontSize: 11, padding: "3px 9px", whiteSpace: "nowrap", flex: "none" }}
    onClick={(e) => { e.stopPropagation(); onGo({ ...g, n: Date.now() }); }}>{GO_LABEL(g)} →</button>) : null;

/** 설명형 이슈 한 줄 (법인 패널·사이트 표 세부에서도 사용) */
export function IssueDetail({ d, onGo }: { d: any; onGo: (t: NavTarget) => void }) {
  const t = TOOL_OF[d.tool] || { letter: "B" as ToolLetter, label: d.tool };
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "7px 8px", borderTop: "1px dashed var(--line)", fontSize: 12.5,
      boxShadow: `inset 3px 0 0 ${TOOL_THEME[t.letter]?.color || "transparent"}` }}>
      <span style={{ marginTop: 5 }}><Dot sev={d.sev} /></span>
      <span style={{ flex: 1, lineHeight: 1.55 }}>
        <ToolBadge l={t.letter} sub={t.label} /> {d.text}
        {d.action && <div style={{ color: "var(--blue)", fontWeight: 700, marginTop: 2 }}>→ {d.action}</div>}
      </span>
      {goBtn(d.go, onGo)}
    </div>);
}

/* ① Summary — 툴 타일. 선택 시 지도·아래 표가 그 툴 기준으로 바뀐다(상태는 RegionOverview 가 가짐) */
export function SummaryTiles({ ins, tool, setTool, onGo }: { ins: any; tool: string | null; setTool: (t: string | null) => void; onGo: (t: NavTarget) => void }) {
  const tiles: any[] = ins?.summary || [];
  return (
    <div style={{ padding: "12px 16px 0" }}>
      <div className="rgGlass" style={{ padding: "12px 14px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 800 }}>Summary</span>
          <span style={{ fontSize: 11.5, color: "var(--sec)" }}>{tool ? "선택한 툴 기준으로 지도와 아래 표를 보여주는 중 · 다시 누르면 해제" : "타일을 누르면 지도와 아래 표가 그 툴 기준으로 바뀝니다"}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.max(tiles.length, 1)}, minmax(0,1fr))`, gap: 10 }}>
          {tiles.map((t) => {
            const th = TOOL_THEME[t.letter as ToolLetter] || TOOL_THEME.B;
            const sv = sevTheme(t.sev);                 // [2026-11] 테두리·강조는 상태색(정상=초록 등), 브랜드색과 분리
            const on = tool === t.key, off = !!tool && !on;
            return (
              <div key={t.key} className="rgTile" onClick={() => setTool(on ? null : t.key)}
                style={{ background: on ? sv.soft : "rgba(255,255,255,.72)", border: `1px solid ${on ? sv.color : "var(--line)"}`, borderTop: `4px solid ${sv.color}`,
                  borderRadius: 12, padding: "10px 12px", cursor: "pointer", opacity: off ? .55 : 1, boxShadow: on ? `0 6px 18px ${sv.color}33` : undefined,
                  display: "flex", flexDirection: "column", minHeight: 158 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 30, height: 30, borderRadius: 10, background: th.soft, display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 17, flex: "none" }}>{th.icon}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 800, color: th.ink }}>{th.name}</div>
                    <div style={{ fontSize: 11, color: "var(--sec)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.key === "apple" ? "경쟁사 페이지 변경" : t.name.split("· ")[1] || t.sub}</div>
                  </div>
                  {t.sev === 0 && <span title="정상" style={{ marginLeft: "auto", fontSize: 11, color: sv.ink }}>●</span>}
                </div>
                <div style={{ fontSize: 26, fontWeight: 800, marginTop: 8, lineHeight: 1.1, color: "var(--label)" }}>{t.metric}</div>
                <div style={{ fontSize: 11.5, color: "var(--label2)" }}>{t.metric_label}</div>
                {/* [2026-11] 중간 줄을 항상 확보(비어도 자리 유지) — 타일 높이가 들쭉날쭉하지 않게. 2줄까지 접힘(말 중간에서 안 끊기게) */}
                <div style={{ fontSize: 11.5, marginTop: 6, color: sv.ink, flex: 1, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", lineHeight: 1.4 }}>
                  {t.cause ? <>가장 많은 문제 · {t.cause}</> : " "}
                </div>
                <div style={{ fontSize: 10.5, color: "var(--gray)", marginTop: 6, borderTop: "1px dashed var(--line)", paddingTop: 5, display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.note}</span>
                  <span role="button" style={{ marginLeft: "auto", color: th.ink, fontWeight: 700, cursor: "pointer", flex: "none" }} onClick={(e) => { e.stopPropagation(); onGo({ ...t.go, n: Date.now() }); }}>열기 →</span>
                </div>
              </div>);
          })}
        </div>
        <div style={{ fontSize: 10.5, color: "var(--gray)", marginTop: 8 }}>{ins?.basis}</div>
      </div>
    </div>);
}

/* ② 급한 이슈 + ③ 사이트별 현황. 행·이슈에 마우스를 올리면 지도에서 그 나라가 툴 색으로 맥동, '지도'를 누르면 지도로 이동해 확대 */
export function IssuesAndSites({ ins, tool, setTool, onGo, onHoverSite, onShowOnMap }: {
  ins: any; tool: string | null; setTool: (t: string | null) => void; onGo: (t: NavTarget) => void;
  onHoverSite: (h: { sitecode: string; tool: string } | null) => void; onShowOnMap: (sitecode: string) => void;
}) {
  const [region, setRegion] = useState("all");
  const [open, setOpen] = useState<string | null>(null);
  const [more, setMore] = useState(false);
  const [openU, setOpenU] = useState<number | null>(null);
  const tiles: any[] = ins?.summary || [];
  const rows: any[] = (ins?.sites || []).filter((r: any) => (!tool || tool === "apple" || r.cells[tool]) && (region === "all" || r.region === region));
  const urgent: any[] = (ins?.urgent || []).filter((u: any) => !tool || u.tool === tool);
  const regions = [...new Set((ins?.sites || []).map((r: any) => r.region).filter(Boolean))] as string[];
  const shown = more ? rows : rows.slice(0, 10);
  const COLS: [string, string][] = [["data", "DATA"], ["spec", "스펙"], ["static", "공통페이지"], ["hc", "노출"]];
  const grid = "minmax(160px,1.1fr) repeat(4, minmax(0,1fr)) 44px";
  const mapBtn = (sc: string) => (
    <button className="btnSecondary" title="지도에서 이 사이트 위치로 확대" style={{ fontSize: 11, padding: "2px 6px" }}
      onClick={(e) => { e.stopPropagation(); onShowOnMap(sc); }}>지도</button>);
  return (
    <div style={{ padding: "12px 16px 0", display: "grid", gap: 12 }}>
      <div className="rgGlass" style={{ padding: "12px 14px" }}>
        <div style={{ fontSize: 13, fontWeight: 800 }}>급한 이슈 <span style={{ fontWeight: 400, fontSize: 11.5, color: "var(--sec)" }}>— 🔴 판정만 · 툴마다 가장 심한 것부터{tool ? " · 선택한 툴만" : ""}</span></div>
        {!urgent.length && <div style={{ fontSize: 12.5, color: "var(--sec)", marginTop: 6 }}>지금 고쳐야 할 이슈 없음</div>}
        {urgent.map((u: any, i: number) => {
          const t = TOOL_OF[u.tool] || { letter: "B" as ToolLetter, label: "" };
          const th = TOOL_THEME[t.letter];
          return (
            <div key={i} className="rgRow" onMouseEnter={() => u.sitecode && onHoverSite({ sitecode: u.sitecode, tool: u.tool })} onMouseLeave={() => onHoverSite(null)}
              style={{ borderTop: i ? "1px solid var(--line)" : undefined, padding: "9px 8px", boxShadow: `inset 3px 0 0 ${th.color}`, background: `linear-gradient(90deg, ${th.soft} 0, transparent 220px)` }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 8, cursor: u.details ? "pointer" : "default" }} onClick={() => u.details && setOpenU(openU === i ? null : i)}>
                <div style={{ flex: 1, fontSize: 13, lineHeight: 1.55 }}>
                  <div style={{ marginBottom: 3 }}><ToolBadge l={t.letter} sub={`${t.label}${u.rule === "R2" ? " · 여러 권역 공통" : ""}`} /></div>
                  {u.text}
                  {u.action && <div style={{ color: "var(--blue)", fontWeight: 700, marginTop: 2 }}>→ {u.action}</div>}
                  {u.details && <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 2 }}>{openU === i ? "▾ 접기" : `▸ 해당 사이트 ${u.details.length}곳 보기`}</div>}
                </div>
                {u.sitecode && mapBtn(u.sitecode)}
                {goBtn(u.go, onGo)}
              </div>
              {openU === i && u.details?.map((d: any, j: number) => (
                <div key={j} onMouseEnter={() => onHoverSite({ sitecode: d.sitecode, tool: d.tool })}><IssueDetail d={d} onGo={onGo} /></div>))}
            </div>);
        })}
      </div>

      <div className="rgGlass" style={{ padding: "12px 14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <b style={{ fontSize: 13 }}>사이트별 현황</b>
          <span style={{ fontSize: 11.5, color: "var(--sec)" }}>{tool && tool !== "apple" ? `${(tiles.find((t) => t.key === tool) || {}).name} 문제 사이트` : "문제가 있는 사이트"} {rows.length}곳 · 🔴 많은 순 · 행을 누르면 내용과 이동 버튼</span>
          {tool && <span role="button" style={{ fontSize: 11.5, color: "var(--blue)", cursor: "pointer" }} onClick={() => setTool(null)}>툴 선택 해제</span>}
          <select value={region} onChange={(e) => setRegion(e.target.value)} style={{ marginLeft: "auto", fontSize: 12, padding: "3px 6px", borderRadius: 6, border: "1px solid var(--line)" }}>
            <option value="all">전체 권역</option>{regions.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        {/* 툴 그룹 머리글 — 🐝 qaBee(3열) · 🍯 honeyComb(1열) */}
        <div style={{ display: "grid", gridTemplateColumns: grid, gap: 8, padding: "10px 6px 0" }}>
          <span />
          <span style={{ gridColumn: "span 3", borderBottom: `2px solid ${TOOL_THEME.B.color}`, paddingBottom: 3 }}><ToolBadge l="B" /></span>
          <span style={{ borderBottom: `2px solid ${TOOL_THEME.C.color}`, paddingBottom: 3 }}><ToolBadge l="C" /></span>
          <span />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: grid, gap: 8, fontSize: 11, color: "var(--sec)", padding: "5px 6px 4px", borderBottom: "1px solid var(--line)" }}>
          <span>사이트 · 법인 · 권역</span>
          {COLS.map(([k, l]) => <span key={k} style={{ fontWeight: tool === k ? 800 : 500, color: tool === k ? TOOL_THEME[letterOf(k)].ink : undefined }}>{l}</span>)}
          <span />
        </div>
        {shown.map((r: any) => (
          <div key={r.sitecode} onMouseEnter={() => onHoverSite({ sitecode: r.sitecode, tool: tool || Object.keys(r.cells)[0] })} onMouseLeave={() => onHoverSite(null)}>
            <div className="rgRow" onClick={() => setOpen(open === r.sitecode ? null : r.sitecode)}
              style={{ display: "grid", gridTemplateColumns: grid, gap: 8, padding: "8px 6px", borderBottom: "1px solid var(--line)", cursor: "pointer", fontSize: 12.5, alignItems: "center",
                background: open === r.sitecode ? "rgba(255,255,255,.8)" : undefined }}>
              <span><b>{(r.sitecode || "").toUpperCase()}</b> <span style={{ fontSize: 11, color: "var(--sec)" }}>{r.subs} · {r.region}</span></span>
              {COLS.map(([k]) => { const c = r.cells[k];
                // [2026-11] 3가지 상태를 구분: 이슈(색+짧은 원인) / 정상(옅은 초록 '정상') / 미검수(연회색 '—', 구분되게)
                const dim = tool && tool !== k;
                if (!c) return <span key={k} style={{ color: "var(--ter)", opacity: dim ? .4 : .7, fontSize: 12 }} title="이 툴로 아직 검수하지 않음">—</span>;
                const sv = sevTheme(c.sev);
                return <span key={k} style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, opacity: dim ? .4 : 1,
                    background: sv.soft, borderRadius: 6, padding: "2px 6px" }} title={c.short}>
                  <Dot sev={c.sev} /><span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: sv.ink, fontWeight: c.sev === 0 ? 500 : 700 }}>{c.short}</span></span>; })}
              {mapBtn(r.sitecode)}
            </div>
            {open === r.sitecode && <div style={{ background: "rgba(255,255,255,.8)", paddingBottom: 4 }}>{r.details.map((d: any, j: number) => <IssueDetail key={j} d={d} onGo={onGo} />)}</div>}
          </div>))}
        {rows.length > 10 && <div role="button" onClick={() => setMore(!more)} style={{ fontSize: 12, color: "var(--blue)", padding: "8px 6px", cursor: "pointer" }}>{more ? "접기" : `${rows.length}곳 모두 보기`}</div>}
        <div style={{ fontSize: 11, color: "var(--label2)", marginTop: 8, padding: "6px 8px", background: "var(--rail)", borderRadius: 8, display: "flex", gap: 14, flexWrap: "wrap" }}>
          <span><Dot sev={1} /> 지금 고쳐야 함</span><span><Dot sev={2} /> 확인 필요</span><span><Dot sev={0} /> 정상(검수 완료)</span>
          <span style={{ color: "var(--ter)" }}>— 아직 검수 안 함</span>
          <span style={{ marginLeft: "auto", color: "var(--sec)" }}>🍎 appleStalker 는 경쟁사 사이트 기준이라 이 표에 없음 — Summary·급한 이슈에서 확인</span>
        </div>
      </div>
    </div>);
}
