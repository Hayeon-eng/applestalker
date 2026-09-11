"use client";
/* QubiUrlList — 검수할 페이지 URL 목록(읽기 전용) [2026-09-11]
   URL 은 저장소의 backend/dotcom_qa/site_registry.part*.json 에 정적으로 들어 있다. 여기서는 개수와 목록만 보여준다. */
import { useEffect, useState } from "react";

export function QubiUrlList({ apiBase }: { apiBase: string }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  useEffect(() => { (async () => { try { const d = await (await fetch(`${apiBase}/api/qb/sites`)).json(); setEntries(d.sites || d.entries || []); } catch { /* */ } })(); }, [apiBase]);
  const shown = entries.filter((e) => !q || `${e.sitecode} ${e.product} ${e.page_type} ${e.url}`.toLowerCase().includes(q.toLowerCase()));
  const byProduct: Record<string, number> = {}; entries.forEach((e) => { byProduct[e.product || "?"] = (byProduct[e.product || "?"] || 0) + 1; });
  return (
    <>
      <div className="sideLabel">검수할 페이지 URL <span style={{ color: "var(--sec)" }}>{entries.length}개</span></div>
      <div style={{ padding: "0 10px 6px", fontSize: 11, color: "var(--sec)", lineHeight: 1.5 }}>
        {Object.entries(byProduct).map(([p, n]) => `${p} ${n}`).join(" · ")}
        <div style={{ marginTop: 2 }}>URL 목록은 저장소 파일로 관리됩니다(변경은 개발 담당에게).</div>
      </div>
      <div className="sideLabel" style={{ cursor: "pointer" }} onClick={() => setOpen((o) => !o)}>{open ? "▾" : "▸"} 목록 보기</div>
      {open && (<>
        <div style={{ padding: "0 10px 6px" }}><input className="urlInput" style={{ width: "100%" }} placeholder="국가/제품/URL 검색" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div className="urlAccordionBody">
          {shown.slice(0, 400).map((e, i) => (
            <div key={`${e.sitecode}-${i}`} className="urlListItem"><div className="urlListUrl"><b>{e.sitecode} <span className="urlAccordionTierTag">{e.product}{e.page_type ? ` · ${e.page_type}` : ""}</span></b>{e.url}</div></div>))}
          {shown.length > 400 && <div style={{ fontSize: 11, color: "var(--sec)", padding: 6 }}>… {shown.length - 400}개 더 — 검색으로 좁혀 보세요</div>}
        </div>
      </>)}
    </>
  );
}
