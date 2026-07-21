"use client";

import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, PageDetail,
  METRICS, orderedSiteKeys, siteName, siteShortName, siteClass,
  shortUrl, linesFromBlock, tagForLine, metricAverage, metricActionSentence, siteMetricScore,
  scoreTier, metricScoreBreakdown, ScoreTier, metricPhrase, shortActionPhrase, detailedAction, pageActionLines,
} from "./shared";


const hasActionVerb = (line: string) => /하세요|보강|확인|점검|배치|비교|유지|분리/.test(line);

const actionHintForLine = (metric: MetricTab, line: string) => {
  const raw = line.toLowerCase();
  if (hasActionVerb(line)) return "";
  if (/근거 없음|근거부족|수집 전|미수집|없습니다/.test(line)) {
    return "핵심 비교에서는 제외하고 원본 URL·렌더링·리다이렉트 상태를 확인하세요.";
  }
  if (metric === "visual" && /alt|이미지|image|visual|lifestyle/.test(raw)) {
    return metricActionSentence("visual");
  }
  if (metric === "copy" && /cta|buy|shop|copy|카피|faq|문구|구매/.test(raw)) {
    return metricActionSentence("copy");
  }
  if (metric === "data" && /schema|h-?tag|meta|html|structured|구조/.test(raw)) {
    return metricActionSentence("data");
  }
  return "";
};
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
        const actionHint = actionHintForLine(metric, line);
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
              <span className="findingText">{line}{actionHint && <small className="findingActionHint">액션: {actionHint}</small>}</span>
              <span className="findingGo">근거 ↓</span>
            </button>
          );
        }
        return (
          <div className="findingRow" key={i}>
            <span className={`badge ${tag.cls}`}>{tag.label}</span>
            <span className="findingText">{line}{actionHint && <small className="findingActionHint">액션: {actionHint}</small>}</span>
          </div>
        );
      })}
    </div>
  );
}

const SCORE_METRIC_LABEL: Record<MetricTab, string> = { data: "스키마 점수", copy: "카피 점수", visual: "이미지 점수" };
const SCORE_METRICS: MetricTab[] = ["data", "copy", "visual"];

export function SiteScoreCard({
  title, site, isOwn, blocks, onSelectScore, selectedMetric,
}: {
  title: string; site: SiteKey; isOwn?: boolean;
  blocks: Partial<Record<MetricTab, AnalysisBlock | undefined>>;
  siteAverages?: Partial<Record<MetricTab, number | null>>;
  onSelectScore?: (metric: MetricTab) => void;
  selectedMetric?: MetricTab | null;
  worstText?: string;
}) {
  const rows = SCORE_METRICS.map((m) => {
    const breakdown = metricScoreBreakdown(m, blocks[m]);
    const tier = scoreTier(breakdown.total);
    return { metric: m, total: breakdown.total, tier };
  });
  const scored = rows.filter((r) => r.total != null) as { metric: MetricTab; total: number; tier: ScoreTier }[];
  const overall = scored.length ? Math.round(scored.reduce((a, b) => a + b.total, 0) / scored.length) : null;
  const overallTier = scoreTier(overall);
  const worst = scored.length ? [...scored].sort((a, b) => a.total - b.total)[0] : null;

  // S5: 종합 인사이트 = 부족 항목(60점 미만) 나열, 없으면 '모두 양호'. 점수를 넣어 사이트마다 달라지게
  const WEAK_BELOW = 60;
  const weak = scored.filter((r) => r.total < WEAK_BELOW).sort((a, b) => a.total - b.total);
  const okList = scored.filter((r) => r.total >= WEAK_BELOW).map((r) => `${METRICS[r.metric].label} ${r.total}점`);
  const summaryLine = !scored.length
    ? "이번 수집엔 근거 없음 · 비교 대상에서 제외, URL·렌더링 확인"
    : weak.length
      ? `부족 항목 — ${weak.map((r) => `${METRICS[r.metric].label} ${r.total}점`).join(", ")}${okList.length ? ` (나머지 양호: ${okList.join(", ")})` : ""}`
      : `세 지표 모두 양호 — ${scored.map((r) => `${METRICS[r.metric].label} ${r.total}점`).join(" · ")}`;
  // S5: 우선 액션은 가장 약한 지표+점수를 앞세워 사이트마다 다르게
  const priorityAction = worst
    ? `가장 약한 ${METRICS[worst.metric].label}(${worst.total}점)부터: ${detailedAction(worst.metric, blocks[worst.metric])}`
    : "관리 URL과 수집 결과부터 확보하세요.";

  return (
    <div className="avgBox">
      <p className="avgBoxTitle">
        <span className="avgBoxSite" style={{ background: site === "samsung" ? "var(--samsung)" : site === "apple" ? "var(--apple)" : "var(--competitor)" }} />
        {title}
        {isOwn && <span className="ownTag">당사</span>}
        <span className="siteOverallScore">
          <span className={`scoreDot ${overallTier}`} />
          {overall == null ? "-" : `${overall}`}
        </span>
      </p>
      {rows.map(({ metric, total, tier }) => (
        <button
          key={metric}
          className={`scoreRow ${selectedMetric === metric ? "active" : ""}`}
          onClick={() => onSelectScore?.(metric)}
        >
          <span>{METRICS[metric].label}</span>
          <span>
            <span className={`scoreDot ${tier}`} />
            <span className="scoreNum">{total == null ? "-" : `${total}점`}</span>
            {total != null && <span className="scoreChev">›</span>}
          </span>
        </button>
      ))}
      <div className="worstBox">
        <p className="findingText" style={{ fontSize: 12 }}>종합 인사이트: {summaryLine}</p>
        <p className="findingText siteInsightAction" style={{ fontSize: 12 }}>우선 액션: {priorityAction}</p>
      </div>
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
    return `${changesText} · 이번 리포트에는 아직 ${siteName(site)}의 ${METRICS[metric].label} 근거가 없습니다. 핵심 비교에서는 제외하고 URL·차단·JS 렌더링 여부를 확인하세요.`;
  }
  const f: any = block.facts || {};
  if (metric === "data") {
    const coverage = f.schema?.coverage_pct ?? "-";
    return `${changesText} · 구조화 데이터 적용률 ${coverage}% · ${firstNarrativeLine(block)}`;
  }
  if (metric === "copy") {
    const pages = f.copy_richness?.all_pages || [];
    const avg = pages.length ? Math.round(pages.reduce((sum: number, x: any) => sum + (Number(x?.score) || 0), 0) / pages.length) : "-";
    return `${changesText} · COPY 근거 ${pages.length}페이지, 평균 구체성 ${avg}점 · ${firstNarrativeLine(block)}`;
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
      {h3.length > 0 && (
        <div className="wfMiniGrid" style={{ marginTop: 6 }}>
          {h3.slice(0, 8).map((x, i) => <div key={i} className="wfBlock"><b>{x}</b><small>H3</small></div>)}
        </div>
      )}
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

export function PageDrilldown({ page, focusMetric = "data" }: { page: PageDetail; focusMetric?: MetricView }) {
  const preferred: MetricTab = focusMetric === "all" ? "data" : focusMetric;
  const baseSections: [MetricTab, any][] = [
    ["data", page.data], ["copy", page.copy], ["visual", page.visual],
  ];
  const sections = focusMetric === "all"
    ? baseSections
    : [...baseSections].sort(([a], [b]) => (a === preferred ? -1 : b === preferred ? 1 : 0));
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
            <details key={key} style={{ marginBottom: 10 }} open={key === preferred}>
              <summary style={{ fontWeight: 700, fontSize: 13, cursor: "pointer", padding: "4px 0" }}>
                {METRICS[key].label}
              </summary>
              <div style={{ paddingTop: 8 }}>
                {linesFromBlock(block).length === 0 ? (
                  <p className="muted">근거 없음</p>
                ) : (
                  <FindingList metric={key} lines={linesFromBlock(block)} />
                )}
                <div className="pageActionBox">
                  <p className="pageActionLabel">이 페이지 액션</p>
                  {pageActionLines(key, block).map((a, i) => (
                    <p key={i} className="pageActionItem">{a}</p>
                  ))}
                </div>
              </div>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}
