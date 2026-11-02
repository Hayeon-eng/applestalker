"use client";
/* regionIssues.tsx — [2026-11 E1] 권역 OVERVIEW 이슈 목록
   · 요약 한 줄(결론 → 할 일)을 누르면 펼쳐져 사이트별 세부(무엇이 · 어디서 · 무엇을)가 나온다.
   · 세부 행의 [이동] → 해당 앱·탭을 그 검수 결과와 대상(사이트·페이지·국가·제품)이 선택된 상태로 연다.
   문장은 백엔드 insight_rules.region_insights 가 만든다(화면·메일 단일 소스). */
import { useState } from "react";
import type { NavTarget } from "./navTarget";

const TOOL_LABEL: Record<string, string> = { data: "DATA QA", spec: "스펙 QA", static: "공통페이지 QA", hc: "honeyComb" };
const GO_LABEL = (g: any) => g?.app === "honeycomb" ? "honeyComb에서 보기" : g?.tab === "static" ? "공통페이지 QA에서 보기" : g?.tab === "copy" ? "스펙 QA에서 보기" : "DATA QA에서 보기";
const DOT: Record<number, string> = { 1: "🔴", 2: "🟡", 3: "⚪" };

export function IssueDetail({ d, onGo }: { d: any; onGo: (t: NavTarget) => void }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "6px 8px", borderTop: "1px dashed var(--line)", fontSize: 12 }}>
      <span style={{ fontSize: 10, marginTop: 3 }}>{DOT[d.sev] || "⚪"}</span>
      <span style={{ flex: 1, lineHeight: 1.5 }}>
        <span style={{ fontSize: 10.5, fontWeight: 700, color: "var(--sec)", marginRight: 6 }}>{TOOL_LABEL[d.tool] || d.tool}</span>
        {d.text}
        {d.action && <><span style={{ color: "var(--sec)" }}> → </span><b style={{ color: "var(--blue)" }}>{d.action}</b></>}
      </span>
      {d.go?.app && (
        <button className="btnSecondary" style={{ fontSize: 11, padding: "3px 8px", whiteSpace: "nowrap" }}
          title={d.go.run_id ? `검수 결과 ${d.go.run_id}` : ""}
          onClick={(e) => { e.stopPropagation(); onGo({ ...d.go, n: Date.now() }); }}>{GO_LABEL(d.go)} →</button>
      )}
    </div>
  );
}

export function RegionIssueList({ ins, onGo, title = "지금 가장 급한 이슈" }: { ins: any; onGo: (t: NavTarget) => void; title?: string }) {
  const [open, setOpen] = useState<number | null>(0);   // 첫 이슈는 펼친 상태로 시작
  const top: any[] = ins?.top || [];
  return (
    <div className="insBox" style={{ marginTop: 0, background: "rgba(255,255,255,.88)" }}>
      <p className="insTitle">{title} <span style={{ fontWeight: 400, color: "var(--sec)" }}>— 누르면 사이트별 세부, [보기]로 해당 화면 이동</span></p>
      {!top.length && <p className="insLine insEmpty">오류 법인 없음</p>}
      {top.map((it, i) => (
        <div key={i} style={{ borderTop: i ? "1px solid var(--line)" : undefined, padding: "4px 0" }}>
          <div className="insLine" style={{ cursor: "pointer" }} onClick={() => setOpen(open === i ? null : i)}>
            <span className="insDot">{open === i ? "▾" : "▸"}</span>
            <span className="insText">{it.text}</span>
            {it.action && <><span className="insArrow">→</span><b className="insAct">{it.action}</b></>}
            <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--sec)" }}>{(it.details || []).length}건</span>
          </div>
          {open === i && (it.details || []).map((d: any, j: number) => <IssueDetail key={j} d={d} onGo={onGo} />)}
        </div>
      ))}
      {ins?.basis && <p className="insBasis">{ins.basis}</p>}
    </div>
  );
}
