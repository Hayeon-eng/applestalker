"use client";
/* specQaShared.tsx — Spec QA 공용 UI 프리미티브
   [2026-07 분할] QubiSpecQa.tsx(48KB)를 46KB 이하 3분할하면서, 결과 패널·사전·기준표가
   함께 쓰는 최소 단위(툴팁·diff·색상·게이지·판정과정)를 여기로 모았다. */
import { useState } from "react";

export function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span style={{ position: "relative", display: "inline-block", marginLeft: 6 }}>
      <span onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        style={{ cursor: "pointer", color: "#0A66E0", fontSize: 11, userSelect: "none" }}>ⓘ</span>
      {open && (
        <>
          <span onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 50 }} />
          <span style={{ position: "absolute", left: 0, top: "130%", zIndex: 51, width: 240, whiteSpace: "pre-line",
            background: "#101318", color: "#fff", fontSize: 11, lineHeight: 1.55, borderRadius: 8, padding: "8px 10px",
            boxShadow: "0 6px 18px rgba(0,0,0,.25)", fontWeight: 400 }}>{text}</span>
        </>
      )}
    </span>
  );
}

// 단어 단위 diff (Data QA MiniDiff와 동일 스타일) — 현재값(빨간 취소선) → 기준값(초록 밑줄)
export function _tok(s: string): string[] { return (s || "").match(/\s+|[^\s]+/g) || []; }
export function MiniDiff({ expected, actual }: { expected: string; actual: string }) {
  const a = _tok(actual), b = _tok(expected);
  const n = a.length, m = b.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: { t: string; s: string }[] = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { out.push({ t: "same", s: a[i] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ t: "del", s: a[i] }); i++; }
    else { out.push({ t: "ins", s: b[j] }); j++; }
  }
  while (i < n) { out.push({ t: "del", s: a[i] }); i++; }
  while (j < m) { out.push({ t: "ins", s: b[j] }); j++; }
  return (
    <span style={{ lineHeight: 1.7, wordBreak: "break-all" }}>
      {out.map((t, k) => t.t === "same"
        ? <span key={k}>{t.s}</span>
        : t.t === "del"
          ? <span key={k} style={{ textDecoration: "line-through", color: "#B42318", background: "#FDECEA", borderRadius: 3 }}>{t.s}</span>
          : <span key={k} style={{ textDecoration: "underline", color: "#067647", background: "#EAF7EE", fontWeight: 700, borderRadius: 3 }}>{t.s}</span>)}
    </span>
  );
}

export const C = { crit: "#D8362F", warn: "#E0A008", pass: "#1F9E5C", na: "#98A2B3", blue: "#1B57C4" };
export const scoreColor = (s: number | null) => (s == null ? C.na : s < 50 ? C.crit : s < 80 ? C.warn : C.pass);

export function Meter({ pct }: { pct: number | null }) {
  const v = pct == null ? 0 : pct;
  const color = scoreColor(pct);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, minWidth: 130 }}>
      <span style={{ flex: 1, height: 6, background: "#EEF1F6", borderRadius: 999, minWidth: 70 }}>
        <span style={{ display: "block", width: `${v}%`, height: "100%", background: color, borderRadius: 999 }} />
      </span>
      <b style={{ fontSize: 12.5, color }}>{pct == null ? "—" : `${pct}%`}</b>
    </span>
  );
}

/* ── Rule Trace: "판정 과정 보기" — Browser→Attribute→Dictionary→Rule→Exception→Result ── */
export function RuleTrace({ trace }: { trace: any[] }) {
  const [open, setOpen] = useState(false);
  if (!trace?.length) return null;
  return (
    <div style={{ marginTop: 6 }}>
      <button onClick={() => setOpen(!open)} style={{ background: "none", border: "none", padding: 0, fontSize: 11, color: "#0A66E0", cursor: "pointer" }}>
        {open ? "▲ 판정 과정 접기" : "▼ 판정 과정 보기"}
      </button>
      {open && (
        <div style={{ marginTop: 6, background: "#0F172A", borderRadius: 8, padding: "8px 12px" }}>
          {trace.map((t, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "104px 1fr", fontSize: 11, lineHeight: 1.8, color: "#E2E8F0" }}>
              <span style={{ color: "#7DD3FC" }}>{t.step}</span>
              <span style={{ wordBreak: "break-all" }}>{t.detail}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
