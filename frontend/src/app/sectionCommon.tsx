"use client";

import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, PageDetail,
  METRICS, orderedSiteKeys, siteName, siteShortName, siteClass,
  shortUrl, linesFromBlock, tagForLine, metricAverage, metricActionSentence, siteMetricScore,
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

// 사이트 평균 대비 신호등 색: 근거 없으면 회색, 평균보다 뚜렷이 낮으면 빨강, 뚜렷이 높으면 초록, 그 외 노랑
function scoreDotClass(score: number | null, avg: number | null): string {
  if (score == null) return "none";
  if (avg == null) return "mid";
  if (score >= avg + 5) return "good";
  if (score <= avg - 10) return "bad";
  return "mid";
}

export function SiteScoreCard({
  title, site, isOwn, blocks, siteAverages, onSelectScore, selectedMetric, worstText,
}: {
  title: string; site: SiteKey; isOwn?: boolean;
  blocks: Partial<Record<MetricTab, AnalysisBlock | undefined>>;
  siteAverages: Partial<Record<MetricTab, number | null>>;
  onSelectScore?: (metric: MetricTab) => void;
  selectedMetric?: MetricTab | null;
  worstText?: string;
}) {
  const scores = SCORE_METRICS.map((m) => ({ metric: m, score: siteMetricScore(m, blocks[m]) }));
  const scored = scores.filter((s) => s.score != null) as { metric: MetricTab; score: number }[];
  const worst = scored.length
    ? scored.reduce((a, b) => {
        const gapA = a.score - (siteAverages[a.metric] ?? a.score);
        const gapB = b.score - (siteAverages[b.metric] ?? b.score);
        return gapB < gapA ? b : a;
      })
    : null;

  return (
    <div className="avgBox">
      <p className="avgBoxTitle">
        <span className="avgBoxSite" style={{ background: site === "samsung" ? "var(--samsung)" : site === "apple" ? "var(--apple)" : "var(--competitor)" }} />
        {title}
        {isOwn && <span className="ownTag">당사</span>}
      </p>
      {scores.map(({ metric, score }) => (
        <button
          key={metric}
          className={`scoreRow ${selectedMetric === metric ? "active" : ""}`}
          onClick={() => onSelectScore?.(metric)}
        >
          <span>{SCORE_METRIC_LABEL[metric]}</span>
          <span>
            <span className={`scoreDot ${scoreDotClass(score, siteAverages[metric] ?? null)}`} />
            <span className="scoreVal">{score == null ? "-" : `${score}점`}</span>
            {score != null && <span className="scoreChev">›</span>}
          </span>
        </button>
      ))}
      <div className="worstBox">
        {worst ? (
          <>
            <p className="worstLabel">가장 부족한 지표 — {SCORE_METRIC_LABEL[worst.metric]} ({worst.score}점)</p>
            {worstText && <p className="findingText" style={{ fontSize: 12 }}>{worstText}</p>}
          </>
        ) : (
          <p className="findingText" style={{ fontSize: 12, color: "var(--sec)" }}>이번 수집엔 근거 없음 · 비교 대상에서 제외, URL·렌더링 확인</p>
        )}
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
