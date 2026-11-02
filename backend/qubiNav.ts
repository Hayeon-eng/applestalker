/* qubiNav.ts — [2026-11] QubiApp 보조 훅 (QubiApp.tsx 용량 47KB 제한으로 분리)
   · useSpecInsights: 스펙 QA 상단 인사이트 — 현재 결과를 백엔드 insight_rules 로 보내 같은 문장을 받는다
   · useQubiNav: 권역 OVERVIEW 에서 넘어온 이동 대상(NavTarget)대로 탭·검수 이력·권역/사이트를 연다 */
import { useEffect, useState } from "react";
import type { NavTarget } from "./navTarget";

export function useSpecInsights(tab: string, results: any[], api: (p: string) => string) {
  const [specInsights, setSpecInsights] = useState<any>(null);
  useEffect(() => {
    if (tab !== "copy") return;
    const rows = (results || []).filter((r: any) => r.spec_v2 || r.compare_v2);
    if (!rows.length) { setSpecInsights(null); return; }
    const slim = (v: any) => v ? { summary: { score: v.summary?.score }, items: (v.items || []).filter((i: any) => i.status === "fail" || i.status === "warn")
      .map((i: any) => ({ attribute: i.attribute || i.label || i.rule_id, status: i.status, expected: i.expected, unit: i.unit, page: i.page })) } : null;
    const body = rows.map((r: any) => ({ sitecode: r.sitecode, region: r.region, page_type: r.page_type, spec_v2: slim(r.spec_v2), compare_v2: slim(r.compare_v2) }));
    let alive = true;
    fetch(api("/api/qb/insights"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tab: "spec", results: body }) })
      .then((x) => (x.ok ? x.json() : null)).then((j) => { if (alive) setSpecInsights(j); }).catch(() => { if (alive) setSpecInsights(null); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, results]);
  return specInsights;
}

// 이동해 온 사이트 행 강조(노란 배경 + 왼쪽 띠). 배지 문구는 globals CSS .qbFocusRow
export const FOCUS_ROW = { background: "#FFF8E1", boxShadow: "inset 3px 0 0 #E0A008" } as const;

/** 결과가 그려질 때까지 최대 timeoutMs 동안 사이트 행을 찾는다 */
function waitForRows(sitecode: string, timeoutMs = 4000): Promise<HTMLElement[]> {
  const sel = `[data-qb-site="${sitecode.replace(/"/g, "")}"]`;
  return new Promise((resolve) => {
    const t0 = Date.now();
    const tick = () => {
      const els = Array.from(document.querySelectorAll<HTMLElement>(sel));
      if (els.length || Date.now() - t0 > timeoutMs) return resolve(els);
      setTimeout(tick, 200);
    };
    tick();
  });
}

export function useQubiNav(nav: NavTarget | null | undefined, h: {
  setTab: (t: "schema" | "copy" | "static") => void;
  openHistory: (id: string) => Promise<void> | void;
  openStatic: (req: { id: string; n: number; sitecode?: string | null; page?: string | null }) => void;
  scrollToRegion: (region: string) => void;
  flash: (msg: string) => void;
  setFocusSite: (sc: string | null) => void;          // 사이트 행 강조
  setExpanded: (key: string | null) => void;          // 사이트 행 펼침(qaExpandedSite)
}) {
  useEffect(() => {
    if (!nav || nav.app !== "qubi" || !nav.tab) return;
    h.setTab(nav.tab);
    if (nav.tab === "static") {
      if (nav.run_id) h.openStatic({ id: nav.run_id, n: nav.n || Date.now(), sitecode: nav.sitecode, page: nav.page });
      return;
    }
    (async () => {
      h.setFocusSite(nav.sitecode || null);
      if (nav.run_id) await h.openHistory(nav.run_id);
      if (!nav.sitecode) { if (nav.region) setTimeout(() => h.scrollToRegion(nav.region as string), 400); return; }
      // [사이트 단위] 그 사이트 행을 찾아 → 첫 행 펼침 → 화면 가운데로 스크롤 (같은 사이트의 다른 제품·페이지 행도 강조)
      const rows = await waitForRows(nav.sitecode);
      if (!rows.length) {
        if (nav.region) h.scrollToRegion(nav.region);
        h.flash(`이 검수 결과에는 ${nav.sitecode.toUpperCase()} 행이 없어요${nav.region ? ` — ${nav.region} 권역으로 이동` : ""}`);
        return;
      }
      h.setExpanded(rows[0].getAttribute("data-qb-key"));
      setTimeout(() => rows[0].scrollIntoView({ behavior: "smooth", block: "center" }), 150);
      h.flash(`${nav.sitecode.toUpperCase()} 결과로 이동했어요${rows.length > 1 ? ` (같은 사이트 ${rows.length}개 행 강조)` : ""}`);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nav?.n]);
}
