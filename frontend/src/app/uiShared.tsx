"use client";
/* uiShared.tsx — [2026-10 통일] 세 툴(A·B·C) 공용 UI 프리미티브
   Meter(점수 게이지) · SevPill(판정 칩) · Loading · EmptyState · toast(alert 대체)
   색은 qubiShared.SEV / globals.css 토큰만 쓴다. 각 탭이 자체 Meter/Bar/COLOR 를 만들지 말고 여기서 import. */
import type { ReactNode } from "react";
import { SEV, type SevKey, TL_COLOR } from "./qubiShared";

/** 점수 → 색. Data QA 기준(80↑ 초록 / 50~79 노랑 / 미만 빨강). danger=true 면 점수와 무관하게 빨강(게이트 발동). */
export const scoreColor = (pct: number | null | undefined, danger = false) =>
  danger ? TL_COLOR.red : pct == null ? SEV.na.c : pct < 50 ? TL_COLOR.red : pct < 80 ? TL_COLOR.yellow : TL_COLOR.green;

/** 점수 게이지(막대 + %). Data QA·Spec QA·공통페이지 QA 모두 이것 하나. */
export function Meter({ pct, danger, minWidth = 130 }: { pct: number | null | undefined; danger?: boolean; minWidth?: number }) {
  const v = pct == null ? 0 : Math.max(0, Math.min(100, pct));
  const color = scoreColor(pct, danger);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, minWidth }}>
      <span style={{ flex: 1, height: 6, background: "var(--gray-soft)", borderRadius: 999, minWidth: 70, overflow: "hidden" }}>
        <span style={{ display: "block", width: `${v}%`, height: "100%", background: color, borderRadius: 999, transition: "width .3s" }} />
      </span>
      <b style={{ fontSize: 12.5, color }}>{pct == null ? "—" : `${pct}%`}</b>
    </span>
  );
}

/** 정상/확인/오류/해당없음 분포 막대(한 줄). 공통페이지 QA 페이지별·권역별 비율 등. */
export function SevBar({ pass, warn, fail, na, label, total }: { pass: number; warn: number; fail: number; na: number; label?: string; total?: number }) {
  const sum = Math.max(1, pass + warn + fail + na);
  const w = (n: number) => `${(100 * n) / sum}%`;
  const scored = pass + warn + fail;
  const pct = scored ? Math.round((100 * pass) / scored) : null;
  return (
    <div style={{ margin: "4px 0" }}>
      {label != null && (
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5 }}>
          <span>{label}</span>
          <span style={{ color: "var(--sec)" }}>
            <b style={{ color: scoreColor(pct) }}>{pct == null ? "—" : `${pct}%`}</b> · 정상 {pass} · 확인 {warn} · 오류 {fail}{na ? ` · 해당없음 ${na}` : ""}
            {total != null && <span style={{ color: "var(--ter)" }}> ({total})</span>}
          </span>
        </div>
      )}
      <div style={{ display: "flex", height: 8, borderRadius: 999, overflow: "hidden", background: "var(--gray-soft)" }}>
        <div style={{ width: w(pass), background: SEV.pass.c }} /><div style={{ width: w(warn), background: SEV.warn.c }} />
        <div style={{ width: w(fail), background: SEV.fail.c }} /><div style={{ width: w(na), background: SEV.na.c }} />
      </div>
    </div>
  );
}

/** 판정 칩. sev 로 색이 정해지고, label 을 주면 "오류 (파싱 실패)" 처럼 사유를 괄호로 덧붙인다. */
export function SevPill({ sev, label, n, on, onClick, title, size = 11.5 }:
  { sev: SevKey; label?: string; n?: number; on?: boolean; onClick?: () => void; title?: string; size?: number }) {
  const s = SEV[sev];
  return (
    <span title={title} onClick={onClick}
      style={{ cursor: onClick ? "pointer" : "default", fontSize: size, padding: "3px 9px", borderRadius: 999, background: s.soft, color: s.ink, fontWeight: 700,
        outline: on ? "2px solid var(--blue)" : "none", whiteSpace: "nowrap", display: "inline-flex", gap: 4, alignItems: "center" }}>
      {s.ko}{label ? <span style={{ fontWeight: 500, opacity: .85 }}>({label})</span> : null}{n != null ? <span style={{ fontWeight: 500 }}>{n}</span> : null}
    </span>
  );
}

/** 로딩 표시 — 카드 안에서든 사이드바에서든 이 한 가지. */
export function Loading({ label = "불러오는 중…", inline }: { label?: string; inline?: boolean }) {
  return inline
    ? <span className="abcLoading" style={{ padding: 0, display: "inline-flex" }}>{label}</span>
    : <div className="card"><div className="abcLoading">{label}</div></div>;
}

/** 빈 상태 — 이력 없음 / 아직 실행 전 / 연결 실패. action 에 버튼을 넣는다. */
export function EmptyState({ title, desc, action, tone = "neutral" }: { title: string; desc?: ReactNode; action?: ReactNode; tone?: "neutral" | "error" }) {
  return (
    <div className="card">
      <div className="abcEmpty">
        <b style={{ color: tone === "error" ? SEV.fail.ink : undefined }}>{tone === "error" ? "⚠ " : ""}{title}</b>
        {desc && <div>{desc}</div>}
        {action && <div style={{ marginTop: 12, display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>{action}</div>}
      </div>
    </div>
  );
}

/** alert() 대체 토스트. React 밖(.ts 유틸)에서도 호출 가능하도록 DOM 에 직접 붙인다. */
export type ToastKind = "info" | "ok" | "warn" | "err";
export function toast(message: string, kind: ToastKind = "info", ms = 3200) {
  if (typeof document === "undefined") return;
  let wrap = document.querySelector<HTMLDivElement>(".abcToastWrap");
  if (!wrap) { wrap = document.createElement("div"); wrap.className = "abcToastWrap"; document.body.appendChild(wrap); }
  const el = document.createElement("div");
  el.className = `abcToast ${kind === "info" ? "" : kind}`.trim();
  el.textContent = message;
  el.onclick = () => el.remove();
  wrap.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .25s"; setTimeout(() => el.remove(), 260); }, ms);
}
