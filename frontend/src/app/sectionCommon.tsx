"use client";

import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, PageDetail,
  METRICS, orderedSiteKeys, siteName, siteShortName, siteClass,
  shortUrl, linesFromBlock, tagForLine, metricAverage,
} from "./shared";

export function FindingList({
  metric, lines, selectedIndex, onSelectLine,
}: {
  metric: MetricTab; lines: string[]; selectedIndex?: number;
  onSelectLine?: (index: number, line: string, label: string) => void;
}) {
  if (lines.length === 0) return <p className="muted">분석 데이터가 없습니다.</p>;
  const interactive = !!onSelectLine;
  return (
    <div>
      {lines.map((line, i) => {
        const tag = tagForLine(metric, line);
        if (interactive) {
          return (
            <button
              type="button"
              className={`findingRow findingRowButton ${selectedIndex === i ? "selected" : ""}`}
              key={i}
              onClick={() => onSelectLine?.(i, line, tag.label)}
              title="상세 근거 보기"
            >
              <span className={`badge ${tag.cls}`}>{tag.label}</span>
              <span className="findingText">{line}</span>
              <span className="findingGo">근거 ↓</span>
            </button>
          );
        }
        return (
          <div className="findingRow" key={i}>
            <span className={`badge ${tag.cls}`}>{tag.label}</span>
            <span className="findingText">{line}</span>
          </div>
        );
      })}
    </div>
  );
}

export function AverageBox({
  title, site, data, metric,
}: {
  title: string; site: SiteKey; data: ReturnType<typeof metricAverage>; metric: MetricView;
}) {
  return (
    <div className="avgBox">
      <p className="avgBoxTitle">
        <span className="avgBoxSite" style={{ background: site === "samsung" ? "var(--samsung)" : site === "apple" ? "var(--apple)" : "var(--competitor)" }} />
        {title}
      </p>
      <div className="avgStat"><span>{data.pages}페이지 수집</span><span className="avgStatVal">{data.pages}</span></div>
      <div className="avgStat"><span>평균 단어 수</span><span className="avgStatVal">{data.avgWords}</span></div>
      {metric === "all" ? (
        <>
          <div className="avgStat"><span>Schema 적용률</span><span className="avgStatVal">{data.schema}</span></div>
          <div className="avgStat"><span>짧은 텍스트 페이지</span><span className="avgStatVal">{data.thin}</span></div>
          <div className="avgStat"><span>Lifestyle 이미지</span><span className="avgStatVal">{data.lifestyle}</span></div>
        </>
      ) : (
        <div className="avgStat">
          <span>{metric === "data" ? "Schema 적용률" : metric === "copy" ? "짧은 텍스트 페이지" : "Lifestyle 이미지"}</span>
          <span className="avgStatVal">{metric === "data" ? data.schema : metric === "copy" ? data.thin : data.lifestyle}</span>
        </div>
      )}
    </div>
  );
}

export function Stat({ label, value, tone }: { label: string; value: number; tone?: "red" | "blue" }) {
  return (
    <div className={`stat ${tone || ""}`}>
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}


export const firstNarrativeLine = (block?: AnalysisBlock) => linesFromBlock(block).find(Boolean) || "수집 근거 부족";
export const siteMetricSummary = (site: SiteKey, metric: MetricTab, block?: AnalysisBlock, siteChanges: Change[] = []) => {
  const changesText = siteChanges.length ? `변경 ${siteChanges.length}건` : "변경 없음";
  if (!block) {
    return `${changesText} · 이번 리포트에는 아직 ${siteName(site)}의 ${METRICS[metric].label} 근거가 없습니다. 관리 URL은 있으므로 수집 실패/차단/JS 렌더링 여부를 먼저 확인하세요.`;
  }
  const f: any = block.facts || {};
  if (metric === "data") {
    const coverage = f.schema?.coverage_pct ?? "-";
    return `${changesText} · 구조화 데이터 적용률 ${coverage}% · ${firstNarrativeLine(block)}`;
  }
  if (metric === "copy") {
    const pages = f.copy_richness?.all_pages || [];
    const avg = pages.length ? Math.round(pages.reduce((sum: number, x: any) => sum + (Number(x?.score) || 0), 0) / pages.length) : "-";
    return `${changesText} · COPY 기준선 ${pages.length}페이지, 평균 구체성 ${avg}점 · ${firstNarrativeLine(block)}`;
  }
  return `${changesText} · alt/src 기반 lifestyle 이미지 신호 ${f.image_diversity?.lifestyle_ratio_pct ?? "-"}% · ${firstNarrativeLine(block)}`;
};
export const compactSummary = (text: string, max = 190) => text.length > max ? text.slice(0, max - 1) + "…" : text;
export const siteMatchesQuery = (site: SiteKey, raw: string) => {
  const hay = [site, siteName(site), siteShortName(site)].join(" ").toLowerCase();
  return hay.split(/\s+/).some((x) => x && raw.includes(x)) || raw.includes(site.replace(/_/g, " "));
};

export const sitesFromBlocks = (siteBlocks?: Record<string, AnalysisBlock>, changes: Change[] = []) =>
  orderedSiteKeys([...(siteBlocks ? Object.keys(siteBlocks) : []), ...changes.map((c) => c.site || "")]);

export function WireframePanel({ page }: { page: PageDetail }) {
  const wf = page.wireframe;
  if (!wf) return <p className="muted">Wireframe 데이터가 없습니다.</p>;
  const h2 = wf.h2 || [];
  const h3 = wf.h3 || [];
  const ctas = wf.ctas || [];
  return (
    <div className="wireframeCard">
      <div className="wfHeader">
        <span className="badge c1">{wf.page_role || "page"}</span>
        <span>{wf.word_count || 0} words</span>
      </div>
      <div className="wfBlock hero">
        <b>{wf.h1 || wf.title || "KV / H1 없음"}</b>
        <small>KV · Title/H1</small>
      </div>
      <div className="wfMiniGrid">
        {h2.slice(0, 5).map((x, i) => <div key={i} className="wfBlock"><b>{x}</b><small>H2 section</small></div>)}
        {h2.length === 0 && <div className="wfBlock"><b>H2 없음</b><small>section 구조 점검</small></div>}
      </div>
      <div className="wfPills">
        {ctas.slice(0, 6).map((x, i) => <span key={i}>{x?.text || "CTA"}</span>)}
        {ctas.length === 0 && <span>CTA 없음</span>}
      </div>
      <div className="wfMetricGrid">
        <div><b>{wf.image_count || 0}</b><span>Images</span></div>
        <div><b>{wf.faq_count || 0}</b><span>FAQ</span></div>
        <div><b>{h3.length}</b><span>H3</span></div>
        <div><b>{(wf.schema_types || []).length}</b><span>Schema</span></div>
      </div>
      <p className="wfSchema">{(wf.schema_types || []).slice(0, 8).join(" · ") || "Schema 없음"}</p>
    </div>
  );
}

export function PageDrilldown({ page }: { page: PageDetail }) {
  const sections: [MetricTab, any][] = [
    ["data", page.data], ["copy", page.copy], ["visual", page.visual],
  ];
  return (
    <div className="pageDetail">
      <p style={{ fontSize: 12, marginBottom: 8 }}>
        <b>URL:</b>{" "}
        <a href={page.url} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }}>{page.url}</a>
      </p>
      <p style={{ fontSize: 11, color: "var(--sec)", marginBottom: 12 }}>수집: {page.crawled_at || "-"}</p>
      <div className="pageEvidenceGrid">
        <WireframePanel page={page} />
        <div className="pageDcvStack">
          {sections.map(([key, block]) => (
            <details key={key} style={{ marginBottom: 10 }} open={key === "data"}>
              <summary style={{ fontWeight: 700, fontSize: 13, cursor: "pointer", padding: "4px 0" }}>
                {METRICS[key].label}
              </summary>
              <div style={{ paddingTop: 8 }}>
                {(block?.narrative || []).length === 0 ? (
                  <p className="muted">근거 없음</p>
                ) : (
                  <FindingList metric={key} lines={block.narrative} />
                )}
              </div>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}
