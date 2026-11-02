"use client";
/* insightUi — ABC 툴 공통 인사이트 표시 [2026-11 신규]
   문장은 백엔드 insight_rules.py 가 만든다(화면·메일·Quick View 단일 소스). 여기서는 표시만 한다.
   한 줄 = "결론 → 할 일". 박스 하단에 판단 기준(임계값)을 항상 같이 보여준다. */
import { createContext, useContext } from "react";

export type Insight = {
  rule: string; sev: number; metric?: string; site?: string;
  text: string; action: string; line: string; urls?: string[];
};
export type InsightPack = {
  top: Insight[];
  by_metric: Record<string, Insight[]>;
  by_site: Record<string, Insight[]>;
  by_site_metric?: Record<string, Record<string, Insight[]>>;
  changes: Insight[];
  basis: string;
};

export const InsightCtx = createContext<InsightPack | null>(null);
export const useInsights = () => useContext(InsightCtx);

const SEV_DOT: Record<number, string> = { 1: "🔴", 2: "🟡", 3: "⚪" };

export function InsightLine({ it, dot = true }: { it: Insight; dot?: boolean }) {
  return (
    <p className="insLine">
      {dot && <span className="insDot">{SEV_DOT[it.sev] || "⚪"}</span>}
      <span className="insText">{it.text}</span>
      {it.action && <><span className="insArrow">→</span><b className="insAct">{it.action}</b></>}
    </p>
  );
}

/** 인사이트 박스 — items 가 비면 empty 문구(없으면 박스 자체를 숨김). basis = 판단 기준 문구. */
export function InsightBox({ items, basis, title, empty, max = 3, style }: {
  items?: Insight[] | null; basis?: string; title?: string; empty?: string; max?: number;
  style?: React.CSSProperties;
}) {
  const list = (items || []).slice(0, max);
  if (!list.length && !empty) return null;
  return (
    <div className="insBox" style={style}>
      {title && <p className="insTitle">{title}</p>}
      {list.length ? list.map((it, i) => <InsightLine key={`${it.rule}-${i}`} it={it} />)
        : <p className="insLine insEmpty">{empty}</p>}
      {basis && <p className="insBasis">{basis}</p>}
    </div>
  );
}

/** 메일·클립보드용 평문 (화면과 같은 문장) */
export const insightText = (items?: Insight[] | null, basis?: string) =>
  [...(items || []).map((it) => `· ${it.line}`), ...(basis ? [basis] : [])].join("\n");
