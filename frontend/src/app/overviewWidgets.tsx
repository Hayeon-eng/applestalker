"use client";

import { useState } from "react";
import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, Report,
  METRICS, orderedSiteKeys, siteName, siteShortName, siteClass, levelKo, levelClass,
  shortUrl, bucketOf, actionForChange, pageRoleFromUrl, pageRoleKo, pageRoleFromText,
} from "./shared";
import {
  firstNarrativeLine, siteMetricSummary, compactSummary, siteMatchesQuery,
} from "./sectionCommon";

type HealthState = "good" | "watch" | "risk" | "unknown";
type PriorityLevel = "High" | "Medium" | "Low";

type MetricHealth = {
  state: HealthState;
  label: string;
  summary: string;
};

type SiteDashboardRow = {
  site: SiteKey;
  collection: MetricHealth;
  metrics: Record<MetricTab, MetricHealth>;
  priority: PriorityLevel;
  issue: string;
  action: string;
  changes: Change[];
};

type PriorityIssue = {
  id: string;
  priority: PriorityLevel;
  site: SiteKey;
  area: string;
  issue: string;
  action: string;
  source: "change" | "quality";
};

export type BoardDigest = {
  scopedMetrics: MetricTab[];
  allSites: SiteKey[];
  siteRows: SiteDashboardRow[];
  priorityRows: PriorityIssue[];
  headline: string;
  lead: string;
  overallLabel: string;
  confidenceLabel: string;
  executiveBullets: string[];
  comparableCount: number;
  watchCount: number;
  riskCount: number;
  unknownCount: number;
  highChangeCount: number;
  actionCount: number;
};

const HEALTH_META: Record<HealthState, { label: string; cls: string }> = {
  good: { label: "Good", cls: "good" },
  watch: { label: "Watch", cls: "watch" },
  risk: { label: "Risk", cls: "risk" },
  unknown: { label: "Unknown", cls: "unknown" },
};

const priorityRank: Record<PriorityLevel, number> = { High: 0, Medium: 1, Low: 2 };
const healthPriorityRank: Record<HealthState, number> = { risk: 0, unknown: 1, watch: 2, good: 3 };

const metricShortLabel = (metric: MetricTab) => metric === "data" ? "DATA" : metric === "copy" ? "COPY" : "VISUAL";

const asNumber = (v: unknown, fallback = 0) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

const pageCountFromBlock = (metric: MetricTab, block?: AnalysisBlock): number => {
  const f: any = block?.facts || {};
  if (metric === "data") return asNumber(f.schema?.total_pages, 0);
  if (metric === "copy") {
    const inv = asNumber(f.page_inventory?.total_pages, 0);
    const pages = Array.isArray(f.copy_richness?.all_pages) ? f.copy_richness.all_pages.length : 0;
    return inv || pages;
  }
  const roleSummary = f.visual_tactics?.role_summary || {};
  const rolePages = Object.values(roleSummary).reduce((sum: number, x: any) => sum + asNumber(x?.pages, 0), 0);
  const tacticPages = Array.isArray(f.visual_tactics?.pages) ? f.visual_tactics.pages.length : 0;
  return rolePages || tacticPages;
};

const avgCopyWords = (block?: AnalysisBlock): number | null => {
  const pages = (block?.facts as any)?.copy_richness?.all_pages;
  if (!Array.isArray(pages) || pages.length === 0) return null;
  const total = pages.reduce((sum: number, p: any) => sum + asNumber(p?.word_count, 0), 0);
  return Math.round(total / pages.length);
};

const avgCopyScore = (block?: AnalysisBlock): number | null => {
  const pages = (block?.facts as any)?.copy_richness?.all_pages;
  if (!Array.isArray(pages) || pages.length === 0) return null;
  const total = pages.reduce((sum: number, p: any) => sum + asNumber(p?.score, 0), 0);
  return Math.round((total / pages.length) * 10) / 10;
};

const visualImageCount = (block?: AnalysisBlock): number | null => {
  const v = (block?.facts as any)?.image_diversity?.total_images;
  return typeof v === "number" ? v : null;
};

const visualAltPct = (block?: AnalysisBlock): number | null => {
  const v = (block?.facts as any)?.alt_text_quality?.descriptive_ratio_pct;
  return typeof v === "number" ? v : null;
};

const schemaCoverage = (block?: AnalysisBlock): number | null => {
  const v = (block?.facts as any)?.schema?.coverage_pct;
  return typeof v === "number" ? v : null;
};

const worstHealth = (states: HealthState[]): HealthState => {
  if (!states.length) return "unknown";
  return [...states].sort((a, b) => healthPriorityRank[a] - healthPriorityRank[b])[0];
};

function metricHealth(metric: MetricTab, block: AnalysisBlock | undefined, metricChanges: Change[]): MetricHealth {
  const high = metricChanges.some((c) => c.level === "High");
  const changed = metricChanges.length > 0;
  if (!block) return { state: "unknown", label: "근거 없음", summary: "이번 리포트에 수집 근거 없음" };

  if (metric === "data") {
    const totalPages = pageCountFromBlock(metric, block);
    const coverage = schemaCoverage(block);
    const h1Pct = asNumber((block.facts as any)?.html_structure?.h_tag_coverage?.h1_coverage_pct, 0);
    if (!totalPages) return { state: "unknown", label: "판단 보류", summary: "DATA 페이지 근거 없음" };
    if (high) return { state: "risk", label: "High 변경", summary: "검색·AI 구조 영향 가능성 있는 변경" };
    if (coverage === 0 && h1Pct === 0) return { state: "risk", label: "구조 근거 낮음", summary: `Schema 0% · H1 ${h1Pct}%` };
    if ((coverage ?? 0) < 40) return { state: "watch", label: "보강 후보", summary: `Schema ${coverage ?? "-"}%` };
    return { state: changed ? "watch" : "good", label: changed ? "변경 확인" : "정상", summary: `Schema ${coverage ?? "-"}%` };
  }

  if (metric === "copy") {
    const totalPages = pageCountFromBlock(metric, block);
    const words = avgCopyWords(block);
    const score = avgCopyScore(block);
    const cta = asNumber((block.facts as any)?.commerce_cta?.pages_with_buy_cta, 0);
    const roles = (block.facts as any)?.page_inventory?.by_page_role || {};
    const conversionRoles = asNumber(roles.pf, 0) + asNumber(roles.pdp, 0) + asNumber(roles.buying, 0);
    if (!totalPages) return { state: "unknown", label: "판단 보류", summary: "COPY 페이지 근거 없음" };
    if (words !== null && words < 30) return { state: "risk", label: "수집 의심", summary: `평균 ${words} words` };
    if (high) return { state: "risk", label: "High 변경", summary: "핵심 카피/CTA 변경 확인 필요" };
    if ((score !== null && score < 40) || (conversionRoles > 0 && cta === 0)) {
      return { state: "watch", label: "보강 후보", summary: `카피 ${score ?? "-"}점 · CTA ${cta}p` };
    }
    return { state: changed ? "watch" : "good", label: changed ? "변경 확인" : "정상", summary: `카피 ${score ?? "-"}점 · CTA ${cta}p` };
  }

  const totalPages = pageCountFromBlock(metric, block);
  const imageCount = visualImageCount(block);
  const altPct = visualAltPct(block);
  if (!totalPages) return { state: "unknown", label: "판단 보류", summary: "VISUAL 페이지 근거 없음" };
  if (imageCount === 0) return { state: "risk", label: "이미지 근거 없음", summary: "수집 이미지 0개" };
  if (high) return { state: "risk", label: "High 변경", summary: "핵심 이미지/alt 변경 확인 필요" };
  if ((altPct ?? 0) < 40) return { state: "watch", label: "alt 보강", summary: `이미지 ${imageCount ?? "-"}개 · alt ${altPct ?? "-"}%` };
  return { state: changed ? "watch" : "good", label: changed ? "변경 확인" : "정상", summary: `이미지 ${imageCount ?? "-"}개 · alt ${altPct ?? "-"}%` };
}

function collectionHealth(site: SiteKey, scopedMetrics: MetricTab[], dcv: Report["dcv"] | undefined, siteChanges: Change[]): MetricHealth {
  const allBlocks = (['data', 'copy', 'visual'] as MetricTab[]).map((m) => dcv?.[m]?.[site]).filter(Boolean);
  if (allBlocks.length === 0) return { state: "unknown", label: "근거 없음", summary: "수집 근거 없음" };

  const copyBlock = dcv?.copy?.[site];
  const visualBlock = dcv?.visual?.[site];
  const dataBlock = dcv?.data?.[site];
  const words = avgCopyWords(copyBlock);
  const images = visualImageCount(visualBlock);
  const totalPages = Math.max(
    pageCountFromBlock("data", dataBlock),
    pageCountFromBlock("copy", copyBlock),
    pageCountFromBlock("visual", visualBlock),
  );
  const missingScoped = scopedMetrics.filter((m) => !dcv?.[m]?.[site]);
  const high = siteChanges.some((c) => c.level === "High");

  if (!totalPages) return { state: "risk", label: "수집 실패 의심", summary: "페이지 카운트 0" };
  if (words !== null && words < 30 && (images === 0 || images === null)) {
    return { state: "risk", label: "수집 실패 의심", summary: `평균 ${words} words · 이미지 ${images ?? 0}개` };
  }
  if (high) return { state: "watch", label: "변경 우선 확인", summary: "High 변경 포함" };
  if (missingScoped.length > 0) {
    return { state: "watch", label: "부분 수집", summary: `${missingScoped.map(metricShortLabel).join("/")} 근거 부족` };
  }
  if (words !== null && words < 80) return { state: "watch", label: "텍스트 근거 낮음", summary: `평균 ${words} words` };
  if (scopedMetrics.includes("visual") && images === 0) return { state: "watch", label: "이미지 근거 낮음", summary: "이미지 0개" };
  return { state: "good", label: "정상 비교 가능", summary: `${totalPages}p 수집 근거` };
}

function issueFromRow(row: SiteDashboardRow): string {
  if (row.changes.length) return compactSummary(row.changes[0].summary || row.changes[0].field || "변경 상세 확인 필요", 90);
  if (row.collection.state === "risk" || row.collection.state === "unknown") return row.collection.summary;
  const weakMetric = (Object.entries(row.metrics) as [MetricTab, MetricHealth][]).find(([, h]) => h.state === "risk" || h.state === "unknown" || h.state === "watch");
  if (weakMetric) return `${metricShortLabel(weakMetric[0])}: ${weakMetric[1].summary}`;
  return "큰 변화 없음 · 기준선 유지";
}

function actionFromRow(row: SiteDashboardRow): string {
  if (row.changes.length) return actionForChange(row.changes[0]);
  if (row.collection.state === "risk" || row.collection.state === "unknown") return "URL·차단·JS 렌더링·에러 페이지 여부 우선 확인";
  if (row.collection.state === "watch") return "근거가 낮은 지표만 재수집 후 리포트 반영";
  return "다음 수집까지 모니터링 유지";
}

function buildSiteRows(changes: Change[], dcv: Report["dcv"] | undefined, scopedMetrics: MetricTab[], expectedSites: SiteKey[]) {
  const allSites = orderedSiteKeys([
    ...expectedSites,
    ...scopedMetrics.flatMap((m) => Object.keys(dcv?.[m] || {})),
    ...changes.map((c) => c.site || ""),
  ]);

  return allSites.map((site) => {
    const siteChanges = changes.filter((c) => c.site === site);
    const metrics = {
      data: metricHealth("data", dcv?.data?.[site], siteChanges.filter((c) => bucketOf(c) === "data")),
      copy: metricHealth("copy", dcv?.copy?.[site], siteChanges.filter((c) => bucketOf(c) === "copy")),
      visual: metricHealth("visual", dcv?.visual?.[site], siteChanges.filter((c) => bucketOf(c) === "visual")),
    };
    const collection = collectionHealth(site, scopedMetrics, dcv, siteChanges);
    const worstScoped = worstHealth(scopedMetrics.map((m) => metrics[m].state));
    const maxChangeLevel = siteChanges.some((c) => c.level === "High") ? "High" : siteChanges.some((c) => c.level === "Medium") ? "Medium" : undefined;
    const priority: PriorityLevel = maxChangeLevel === "High" || collection.state === "risk" || collection.state === "unknown" || worstScoped === "risk" || worstScoped === "unknown"
      ? "High"
      : maxChangeLevel === "Medium" || collection.state === "watch" || worstScoped === "watch"
      ? "Medium"
      : "Low";
    const row: SiteDashboardRow = {
      site, metrics, collection, priority, changes: siteChanges,
      issue: "", action: "",
    };
    row.issue = issueFromRow(row);
    row.action = actionFromRow(row);
    return row;
  });
}

function buildPriorityRows(rows: SiteDashboardRow[], changes: Change[], scopedMetrics: MetricTab[]): PriorityIssue[] {
  const changeRows = [...changes]
    .sort((a, b) => priorityRank[(a.level || "Low") as PriorityLevel] - priorityRank[(b.level || "Low") as PriorityLevel])
    .slice(0, 6)
    .map((c) => ({
      id: `change-${c.id}`,
      priority: (c.level || "Low") as PriorityLevel,
      site: c.site || "",
      area: METRICS[bucketOf(c)].label,
      issue: compactSummary(c.summary || c.field || "변경 상세 확인 필요", 90),
      action: actionForChange(c),
      source: "change" as const,
    }));

  const qualityRows = rows
    .filter((row) => row.priority !== "Low" && !changeRows.some((x) => x.site === row.site))
    .sort((a, b) => priorityRank[a.priority] - priorityRank[b.priority])
    .slice(0, 6)
    .map((row) => {
      const weakMetric = scopedMetrics.find((m) => row.metrics[m].state === "risk" || row.metrics[m].state === "unknown" || row.metrics[m].state === "watch");
      return {
        id: `quality-${row.site}`,
        priority: row.priority,
        site: row.site,
        area: weakMetric ? METRICS[weakMetric].label : "Collection",
        issue: row.issue,
        action: row.action,
        source: "quality" as const,
      };
    });

  return [...changeRows, ...qualityRows]
    .sort((a, b) => priorityRank[a.priority] - priorityRank[b.priority])
    .slice(0, 8);
}

export function buildDashboardDigest({
  changes, dcv, metricTab, expectedSites = [],
}: {
  changes: Change[]; dcv?: Report["dcv"]; metricTab: MetricView; expectedSites?: SiteKey[];
}): BoardDigest {
  const scopedMetrics = metricTab === "all" ? (["data", "copy", "visual"] as MetricTab[]) : [metricTab];
  const siteRows = buildSiteRows(changes, dcv, scopedMetrics, expectedSites);
  const allSites = siteRows.map((row) => row.site);
  const highChangeCount = changes.filter((c) => c.level === "High").length;
  const comparableCount = siteRows.filter((row) => row.collection.state === "good" || row.collection.state === "watch").length;
  const watchCount = siteRows.filter((row) => row.collection.state === "watch").length;
  const riskCount = siteRows.filter((row) => row.collection.state === "risk").length;
  const unknownCount = siteRows.filter((row) => row.collection.state === "unknown").length;
  const priorityRows = buildPriorityRows(siteRows, changes, scopedMetrics);
  const actionCount = priorityRows.filter((row) => row.priority !== "Low").length;

  const confidenceRatio = allSites.length ? comparableCount / allSites.length : 0;
  const confidenceLabel = !allSites.length
    ? "No Data"
    : riskCount + unknownCount > 0
    ? "Medium-Low"
    : confidenceRatio >= 0.8
    ? "High"
    : confidenceRatio >= 0.5
    ? "Medium"
    : "Low";
  const overallLabel = !allSites.length
    ? "No Data"
    : highChangeCount > 0 || riskCount + unknownCount > 0
    ? "Watch"
    : changes.length > 0 || watchCount > 0
    ? "Monitor"
    : "Stable";
  const headline = !allSites.length
    ? "수집 데이터 없음"
    : highChangeCount > 0
    ? `즉시 확인 필요 · High ${highChangeCount}건`
    : riskCount + unknownCount > 0
    ? "변경 판단 보류 · 수집 품질 확인 필요"
    : changes.length > 0
    ? `변경 감지 · ${changes.length}건 우선순위 확인`
    : watchCount > 0
    ? "대체로 안정 · 일부 지표 재확인"
    : "안정 · 정상 비교 가능";
  const lead = !allSites.length
    ? "관리 URL을 추가하거나 수집을 실행하면 리더십용 현황판이 표시됩니다."
    : `관리 대상 ${allSites.length}개 중 비교 가능 ${comparableCount}개, 확인 필요 ${riskCount + unknownCount}개, 우선 액션 ${actionCount}개.`;

  const issueSites = siteRows.filter((row) => row.priority !== "Low").slice(0, 4).map((row) => siteShortName(row.site));
  const changedSites = orderedSiteKeys(changes.map((c) => c.site || "")).slice(0, 4).map(siteShortName);
  const executiveBullets = [
    changes.length
      ? `변경 ${changes.length}건 감지: ${changedSites.join(", ") || "상세 목록"} 중심으로 확인 필요`
      : "신규 변경점은 없으며, 현재 수집분은 다음 비교 기준선으로 활용 가능",
    riskCount + unknownCount
      ? `수집 품질 확인 필요: ${issueSites.join(", ") || "일부 사이트"}의 빈 데이터/근거 부족 여부 점검`
      : "수집 품질상 치명적 공백은 보이지 않음",
    actionCount
      ? `오늘 확인할 액션 ${actionCount}개: 아래 Priority Issues부터 처리`
      : "즉시 처리할 액션 없음 · 정기 모니터링 유지",
  ];

  return {
    scopedMetrics, allSites, siteRows, priorityRows, headline, lead, overallLabel, confidenceLabel,
    executiveBullets, comparableCount, watchCount, riskCount, unknownCount, highChangeCount, actionCount,
  };
}

function HealthPill({ health }: { health: MetricHealth }) {
  return <span className={`healthPill ${HEALTH_META[health.state].cls}`}>{health.label}</span>;
}

function StatusCell({ health }: { health: MetricHealth }) {
  return (
    <div className={`matrixCell ${HEALTH_META[health.state].cls}`} title={health.summary}>
      <b>{HEALTH_META[health.state].label}</b>
      <span>{compactSummary(health.summary, 36)}</span>
    </div>
  );
}

export function WatchPointPanel({ changes, dcv, metricTab, expectedSites = [] }: { changes: Change[]; dcv?: Report["dcv"]; metricTab: MetricView; expectedSites?: SiteKey[] }) {
  const digest = buildDashboardDigest({ changes, dcv, metricTab, expectedSites });
  const displayMetrics = digest.scopedMetrics;

  return (
    <div className="card watchPointCard execBoard">
      <div className="execHero">
        <div className="execHeroText">
          <p className="summaryEyebrow">Executive Overview</p>
          <h2>{digest.headline}</h2>
          <p className="execLead">{digest.lead}</p>
          <div className="execBullets">
            <span>핵심 결론</span>
            {digest.executiveBullets.map((item) => <b key={item}>{item}</b>)}
          </div>
        </div>
        <div className="execKpiGrid" aria-label="Executive KPI">
          <div><b>{digest.allSites.length}</b><span>관리 Site</span></div>
          <div><b>{digest.comparableCount}</b><span>비교 가능</span></div>
          <div><b>{digest.riskCount + digest.unknownCount}</b><span>확인 필요</span></div>
          <div><b>{digest.actionCount}</b><span>Action</span></div>
        </div>
      </div>

      <div className="decisionStrip">
        <div>
          <span>Overall Status</span>
          <b>{digest.overallLabel}</b>
          <p>{digest.headline}</p>
        </div>
        <div>
          <span>Data Confidence</span>
          <b>{digest.confidenceLabel}</b>
          <p>비교 가능 {digest.comparableCount}/{digest.allSites.length || 0} · Watch {digest.watchCount}</p>
        </div>
        <div>
          <span>Action Required</span>
          <b>{digest.actionCount} items</b>
          <p>{digest.priorityRows[0]?.action || "즉시 처리할 이슈 없음"}</p>
        </div>
      </div>

      <div className="execSectionHead">
        <div>
          <p className="summaryEyebrow">Priority Issues</p>
          <h3>오늘 먼저 볼 항목</h3>
        </div>
        <small>변경점과 수집 품질 이슈를 같은 우선순위로 정렬</small>
      </div>
      <div className="priorityTableWrap">
        <div className="priorityRow head">
          <span>Priority</span><span>Site</span><span>Area</span><span>Issue</span><span>Action</span>
        </div>
        {digest.priorityRows.length === 0 ? (
          <div className="priorityEmpty">우선 확인할 항목 없음 · 다음 수집까지 기준선 유지</div>
        ) : digest.priorityRows.map((row) => (
          <div key={row.id} className="priorityRow">
            <span><span className={`sevBadge ${levelClass(row.priority)}`}>{levelKo(row.priority)}</span></span>
            <span><span className={`badge ${siteClass(row.site)}`}>{siteName(row.site)}</span></span>
            <span>{row.area}</span>
            <span>{row.issue}</span>
            <span>{row.action}</span>
          </div>
        ))}
      </div>

      <div className="execSectionHead matrixHead">
        <div>
          <p className="summaryEyebrow">Competitor Matrix</p>
          <h3>사이트 × 분석축 현황</h3>
        </div>
        <small>Good / Watch / Risk / Unknown으로 압축</small>
      </div>
      <div className={`matrixGrid cols-${displayMetrics.length}`}>
        <div className="matrixRow matrixHeader">
          <span>Site</span>
          {displayMetrics.map((m) => <span key={m}>{metricShortLabel(m)}</span>)}
          <span>Collection</span>
          <span>Priority</span>
        </div>
        {digest.siteRows.map((row) => (
          <div key={row.site} className="matrixRow">
            <span><span className={`badge ${siteClass(row.site)}`}>{siteName(row.site)}</span></span>
            {displayMetrics.map((m) => <div key={m} className="matrixCellSlot"><StatusCell health={row.metrics[m]} /></div>)}
            <StatusCell health={row.collection} />
            <span><span className={`priorityPill ${levelClass(row.priority)}`}>{levelKo(row.priority)}</span></span>
          </div>
        ))}
      </div>

      <details className="siteScoreDetails">
        <summary>사이트별 Scorecard 보기</summary>
        <div className="scorecardGrid">
          {digest.siteRows.map((row) => {
            const scopedSummary = displayMetrics.map((m) => ({
              metric: m,
              health: row.metrics[m],
              text: siteMetricSummary(row.site, m, dcv?.[m]?.[row.site], row.changes.filter((c) => bucketOf(c) === m)),
            }));
            return (
              <div key={row.site} className={`scorecard ${levelClass(row.priority)}`}>
                <div className="scorecardHead">
                  <span className={`badge ${siteClass(row.site)}`}>{siteName(row.site)}</span>
                  <span className={`priorityPill ${levelClass(row.priority)}`}>{levelKo(row.priority)}</span>
                </div>
                <p className="scorecardIssue">{row.issue}</p>
                <div className="scoreRows">
                  {scopedSummary.map((x) => (
                    <div key={x.metric}>
                      <b>{metricShortLabel(x.metric)}</b>
                      <HealthPill health={x.health} />
                      <span>{compactSummary(x.text, 82)}</span>
                    </div>
                  ))}
                </div>
                <p className="scorecardAction">Action: {row.action}</p>
              </div>
            );
          })}
        </div>
      </details>
    </div>
  );
}

export function InsightChat({ dcv, changes, expectedSites = [] }: { dcv?: Report["dcv"]; changes: Change[]; expectedSites?: SiteKey[] }) {
  const presets = [
    "이번 주 변경된 페이지는?",
    "삼성은 뭘 예의주시해야 해?",
    "Apple PDP에서 copy 의미있는 차이는?",
    "Xiaomi tablet PDP에서 image 인사이트는?",
    "스키마에서 의미 있는 차이는?",
    "PF/PDP/Buying 중 어디가 약해?",
  ];
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState("preset을 누르거나, ‘Apple PDP copy’, ‘Xiaomi tablet image’처럼 사이트·페이지·지표를 넣어 물어보세요.");

  const answerFor = (query: string) => {
    const raw = query.trim().toLowerCase();
    if (!raw) return;
    const metricExplicit: MetricTab | undefined = /schema|data|html|h-?tag|스키마|데이터/.test(raw)
      ? "data" : /visual|image|alt|비주얼|이미지/.test(raw)
      ? "visual" : /copy|카피|문구|tone|faq|cta/.test(raw)
      ? "copy" : undefined;
    const metric: MetricTab = metricExplicit || "copy";
    const role = pageRoleFromText(raw);
    const digest = buildDashboardDigest({ changes, dcv, metricTab: metricExplicit || "all", expectedSites });
    const allMetricSites = orderedSiteKeys([...expectedSites, ...Object.keys(dcv?.[metric] || {}), ...changes.map((c) => c.site || "")]);
    const site = allMetricSites.find((s) => siteMatchesQuery(s, raw));
    const filteredChanges = changes.filter((c) => {
      if (bucketOf(c) !== metric) return false;
      if (site && c.site !== site) return false;
      if (role && pageRoleFromUrl(c.url) !== role) return false;
      return true;
    });

    if (/이번|변경|바뀐|changed|change/.test(raw) && !/의미|insight|인사이트/.test(raw)) {
      if (filteredChanges.length) {
        setAnswer(filteredChanges.slice(0, 5).map((c) => `- ${siteName(c.site)} ${pageRoleKo(pageRoleFromUrl(c.url))} ${METRICS[bucketOf(c)].label}: ${c.summary || c.field} (${shortUrl(c.url)})`).join("\n"));
        return;
      }
      const qualityWarnings = digest.siteRows.filter((row) => row.priority !== "Low").slice(0, 4);
      if (qualityWarnings.length) {
        setAnswer("조건에 맞는 변경점은 없습니다. 다만 변경 없음으로 단정하기 전 아래 수집 품질을 먼저 확인해야 합니다.\n" + qualityWarnings.map((row) => `- ${siteName(row.site)}: ${row.issue} → ${row.action}`).join("\n"));
        return;
      }
      setAnswer("조건에 맞는 변경점은 없습니다. 수집 품질상 큰 공백이 없으면 현재 상태를 baseline으로 두고, 다음 수집에서 Schema/CTA/카피/alt.copy 변화를 비교하면 됩니다.");
      return;
    }

    if (/삼성|samsung|예의주시|watch|action/.test(raw)) {
      if (digest.priorityRows.length) {
        setAnswer(digest.priorityRows.slice(0, 5).map((row) => `- ${siteName(row.site)} ${levelKo(row.priority)}: ${row.issue}\n  → 삼성 액션: ${row.action}`).join("\n"));
        return;
      }
      setAnswer("이번 수집에서는 즉시 처리할 이슈가 없습니다. 예의주시 포인트는 ① 경쟁사의 Product/FAQ schema 변화 ② PF/PDP/Buying CTA 위치 변화 ③ hero copy의 톤 변화 ④ alt.copy 보강 여부입니다.");
      return;
    }

    if (/pf|pdp|buying|구매|약해/.test(raw)) {
      const blocks = dcv?.copy || {};
      const lines = orderedSiteKeys([...expectedSites, ...Object.keys(blocks)]).map((s) => {
        const block = blocks[s];
        const row = digest.siteRows.find((x) => x.site === s);
        const f: any = block?.facts || {};
        if (!block || row?.collection.state === "risk" || row?.collection.state === "unknown") return `- ${siteName(s)}: ${row?.issue || "아직 COPY 근거가 없습니다."} 수집 성공 후 PF/PDP/Buying별로 판단할 수 있습니다.`;
        const roles = f.page_inventory?.by_page_role || {};
        const roleText = Object.entries(roles).map(([k, v]) => `${pageRoleKo(k)} ${v}p`).join(", ") || "역할 정보 없음";
        const line = firstNarrativeLine(block);
        return `- ${siteName(s)}: 수집 기준 ${roleText}. ${compactSummary(line, 160)}`;
      });
      setAnswer(lines.length ? lines.join("\n") : "PF/PDP/Buying 역할별 COPY 근거가 아직 부족합니다.");
      return;
    }

    const targetSites = site ? [site] : allMetricSites;
    const answers = targetSites.slice(0, 5).map((s) => {
      const block = dcv?.[metric]?.[s];
      const siteChanges = changes.filter((c) => bucketOf(c) === metric && c.site === s && (!role || pageRoleFromUrl(c.url) === role));
      const roleText = role ? `${pageRoleKo(role)} ` : "";
      const health = metricHealth(metric, block, siteChanges);
      if (siteChanges.length) {
        return `- ${siteName(s)} ${roleText}${METRICS[metric].label} 변경: ${siteChanges.slice(0, 2).map((c) => `${c.summary || c.field} (${shortUrl(c.url)})`).join(" / ")}`;
      }
      if (!block || health.state === "risk" || health.state === "unknown") {
        return `- ${siteName(s)} ${roleText}${METRICS[metric].label}: 변경 판단 보류. ${health.summary} → 수집 실패/차단/JS 렌더링 여부 확인 필요.`;
      }
      return `- ${siteName(s)} ${roleText}${METRICS[metric].label}: ${health.label}. 현재 근거: ${compactSummary(firstNarrativeLine(block), 180)}`;
    });
    setAnswer(answers.length ? answers.join("\n") : "현재 리포트에서 해당 사이트/페이지/지표 조합에 대한 근거가 없습니다.");
  };

  return (
    <div className={`floatingChat ${open ? "open" : ""}`}>
      {!open && <button className="chatToggle" onClick={() => setOpen(true)}>Q&A</button>}
      {open && (
        <div className="chatPanel">
          <div className="chatPanelHead">
            <b>간단 Q&A</b>
            <button onClick={() => setOpen(false)} title="닫기">×</button>
          </div>
          <div className="presetGrid">
            {presets.map((p) => <button key={p} onClick={() => { setQ(p); answerFor(p); }}>{p}</button>)}
          </div>
          <div className="chatInputRow">
            <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") answerFor(q); }} placeholder="예: OPPO PDP copy 차이는?" />
            <button onClick={() => answerFor(q)}>질문</button>
          </div>
          <pre>{answer}</pre>
          <p className="muted">현재 수집된 facts/changes와 수집 품질 상태 안에서만 rule-based로 답합니다.</p>
        </div>
      )}
    </div>
  );
}
