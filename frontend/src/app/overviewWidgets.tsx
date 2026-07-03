"use client";

import { useState } from "react";
import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, Report,
  METRICS, orderedSiteKeys, siteName, siteShortName, siteClass, levelKo, levelClass,
  shortUrl, bucketOf, actionForChange, pageRoleFromUrl, pageRoleKo, pageRoleFromText,
  metricActionSentence, metricIssueSentence, metricAreaLabel,
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
  source: "change" | "insight" | "evidence";
};

export type BoardDigest = {
  scopedMetrics: MetricTab[];
  allSites: SiteKey[];
  siteRows: SiteDashboardRow[];
  priorityRows: PriorityIssue[];
  samsungActions: string[];
  competitorBenchmarks: string[];
  evidenceWarnings: string[];
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
  good: { label: "우수", cls: "good" },
  watch: { label: "확인 필요", cls: "watch" },
  risk: { label: "개선 필요", cls: "risk" },
  unknown: { label: "근거 부족", cls: "unknown" },
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
  if (!block) return { state: "unknown", label: "근거 부족", summary: `${metricAreaLabel(metric)} 근거가 부족합니다` };

  if (metric === "data") {
    const totalPages = pageCountFromBlock(metric, block);
    const coverage = schemaCoverage(block);
    const h1Pct = asNumber((block.facts as any)?.html_structure?.h_tag_coverage?.h1_coverage_pct, 0);
    if (!totalPages) return { state: "unknown", label: "근거 부족", summary: "DATA / Schema 페이지 근거가 부족합니다" };
    if (high) return { state: "risk", label: "변화 있음", summary: "Schema/H-tag 변경이 검색·AI 해석에 영향을 줄 수 있습니다" };
    if (coverage === 0 && h1Pct === 0) return { state: "risk", label: "개선 필요", summary: "Schema와 H-tag 역할 신호가 약합니다" };
    if ((coverage ?? 0) < 40) return { state: "watch", label: "확인 필요", summary: `Schema 적용 범위가 낮습니다 (${coverage ?? "-"}%)` };
    return { state: changed ? "watch" : "good", label: changed ? "변화 있음" : "우수", summary: `Schema ${coverage ?? "-"}% · 역할 신호를 유지하세요` };
  }

  if (metric === "copy") {
    const totalPages = pageCountFromBlock(metric, block);
    const words = avgCopyWords(block);
    const score = avgCopyScore(block);
    const cta = asNumber((block.facts as any)?.commerce_cta?.pages_with_buy_cta, 0);
    const roles = (block.facts as any)?.page_inventory?.by_page_role || {};
    const conversionRoles = asNumber(roles.pf, 0) + asNumber(roles.pdp, 0) + asNumber(roles.buying, 0);
    if (!totalPages) return { state: "unknown", label: "근거 부족", summary: "COPY / CTA 페이지 근거가 부족합니다" };
    if (words !== null && words < 30) return { state: "unknown", label: "근거 부족", summary: "카피 본문 근거가 부족합니다" };
    if (high) return { state: "risk", label: "변화 있음", summary: "핵심 카피/CTA 변경을 확인해야 합니다" };
    if ((score !== null && score < 40) || (conversionRoles > 0 && cta === 0)) {
      return { state: "risk", label: "개선 필요", summary: "구매 CTA와 카피 연결이 약합니다" };
    }
    return { state: changed ? "watch" : "good", label: changed ? "변화 있음" : "우수", summary: `카피 ${score ?? "-"}점 · CTA ${cta}p` };
  }

  const totalPages = pageCountFromBlock(metric, block);
  const imageCount = visualImageCount(block);
  const altPct = visualAltPct(block);
  if (!totalPages) return { state: "unknown", label: "근거 부족", summary: "VISUAL / ALT COPY 페이지 근거가 부족합니다" };
  if (imageCount === 0) return { state: "unknown", label: "근거 부족", summary: "이미지/ALT COPY 근거가 부족합니다" };
  if (high) return { state: "risk", label: "변화 있음", summary: "핵심 이미지/ALT COPY 변경을 확인해야 합니다" };
  if ((altPct ?? 0) < 40) return { state: "risk", label: "개선 필요", summary: "ALT COPY의 구체성이 부족합니다" };
  return { state: changed ? "watch" : "good", label: changed ? "변화 있음" : "우수", summary: `이미지 ${imageCount ?? "-"}개 · ALT COPY ${altPct ?? "-"}%` };
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

  if (!totalPages) return { state: "unknown", label: "근거 부족", summary: "핵심 비교에 넣기 전 원본 페이지 확인이 필요합니다" };
  if (words !== null && words < 30 && (images === 0 || images === null)) {
    return { state: "unknown", label: "근거 부족", summary: "본문/이미지 근거가 부족해 보조 확인으로 분리합니다" };
  }
  if (high) return { state: "watch", label: "변화 있음", summary: "High 변경 포함" };
  if (missingScoped.length > 0) {
    return { state: "watch", label: "확인 필요", summary: `${missingScoped.map(metricShortLabel).join("/")} 근거를 보강하세요` };
  }
  if (words !== null && words < 80) return { state: "watch", label: "확인 필요", summary: "카피 근거가 짧아 핵심 문구를 확인하세요" };
  if (scopedMetrics.includes("visual") && images === 0) return { state: "watch", label: "확인 필요", summary: "이미지/ALT COPY 근거를 확인하세요" };
  return { state: "good", label: "우수", summary: `${totalPages}p 근거 확보` };
}

function issueFromRow(row: SiteDashboardRow): string {
  if (row.changes.length) return compactSummary(row.changes[0].summary || row.changes[0].field || "변경 상세 확인 필요", 90);
  if (row.collection.state === "risk" || row.collection.state === "unknown") return row.collection.summary;
  const weakMetric = (Object.entries(row.metrics) as [MetricTab, MetricHealth][]).find(([, h]) => h.state === "risk" || h.state === "unknown" || h.state === "watch");
  if (weakMetric) return `${metricShortLabel(weakMetric[0])}: ${weakMetric[1].summary}`;
  return "중요 변경 없음 · 현재 구성을 유지";
}

function actionFromRow(row: SiteDashboardRow): string {
  if (row.changes.length) return actionForChange(row.changes[0]);
  const weakMetric = (Object.entries(row.metrics) as [MetricTab, MetricHealth][]).find(([, h]) => h.state === "risk" || h.state === "watch" || h.state === "unknown");
  if (weakMetric) return metricActionSentence(weakMetric[0]);
  if (row.collection.state === "risk" || row.collection.state === "unknown") return "핵심 비교에서는 제외하고 URL·리다이렉트·렌더링 상태를 확인하세요.";
  return "현재 구성을 유지하고 다음 수집에서 변화만 확인하세요.";
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

  const insightRows = rows
    .filter((row) => row.priority !== "Low" && !changeRows.some((x) => x.site === row.site))
    .sort((a, b) => priorityRank[a.priority] - priorityRank[b.priority])
    .slice(0, 6)
    .map((row) => {
      const weakMetric = scopedMetrics.find((m) => row.metrics[m].state === "risk" || row.metrics[m].state === "unknown" || row.metrics[m].state === "watch");
      return {
        id: `insight-${row.site}`,
        priority: row.priority,
        site: row.site,
        area: weakMetric ? METRICS[weakMetric].label : "근거 상태",
        issue: weakMetric ? metricIssueSentence(weakMetric) : row.issue,
        action: row.action,
        source: row.collection.state === "unknown" ? "evidence" as const : "insight" as const,
      };
    });

  return [...changeRows, ...insightRows]
    .sort((a, b) => priorityRank[a.priority] - priorityRank[b.priority])
    .slice(0, 8);
}

function actionLinesForRow(row: SiteDashboardRow, scopedMetrics: MetricTab[]): string[] {
  const lines: string[] = [];
  const changed = row.changes.slice(0, 2).map((c) => actionForChange(c));
  lines.push(...changed);
  scopedMetrics.forEach((m) => {
    const health = row.metrics[m];
    if (health.state === "risk" || health.state === "watch") {
      lines.push(`${metricIssueSentence(m)} ${metricActionSentence(m)}`);
    }
  });
  if (!lines.length && (row.collection.state === "risk" || row.collection.state === "unknown")) {
    lines.push(`${siteShortName(row.site)}는 근거가 부족해 핵심 비교에서 제외하고 원본 URL·렌더링을 확인하세요.`);
  }
  if (!lines.length) lines.push(`${siteShortName(row.site)}는 중요 변경이 없어 현재 구성을 유지하세요.`);
  return Array.from(new Set(lines));
}

function benchmarkLineForRow(row: SiteDashboardRow, scopedMetrics: MetricTab[]): string {
  const bestMetric = scopedMetrics.find((m) => row.metrics[m].state === "good") || scopedMetrics.find((m) => row.metrics[m].state === "watch") || scopedMetrics[0];
  if (bestMetric === "data") return `${siteShortName(row.site)}는 DATA / Schema 구조를 참고할 수 있습니다. Samsung의 PF/PDP/Buying 역할별 Schema와 비교하세요.`;
  if (bestMetric === "visual") return `${siteShortName(row.site)}는 VISUAL / ALT COPY 흐름을 참고할 수 있습니다. 제품명·기능·사용 장면 설명 방식을 비교하세요.`;
  return `${siteShortName(row.site)}는 COPY / CTA 흐름을 참고할 수 있습니다. PDP에서 구매/혜택 CTA가 어떻게 이어지는지 비교하세요.`;
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

  const samsungRow = siteRows.find((row) => row.site === "samsung");
  const samsungActions = samsungRow
    ? actionLinesForRow(samsungRow, scopedMetrics).slice(0, 4)
    : ["Samsung 관리 URL과 수집 결과가 없어 개선 포인트를 만들 수 없습니다."];
  const competitorBenchmarks = siteRows
    .filter((row) => row.site !== "samsung" && row.collection.state !== "unknown")
    .sort((a, b) => priorityRank[a.priority] - priorityRank[b.priority])
    .slice(0, 4)
    .map((row) => benchmarkLineForRow(row, scopedMetrics));
  const evidenceWarnings = siteRows
    .filter((row) => row.collection.state === "unknown" || row.metrics && scopedMetrics.some((m) => row.metrics[m].state === "unknown"))
    .slice(0, 4)
    .map((row) => `${siteShortName(row.site)}는 근거가 부족해 핵심 인사이트가 아니라 보조 확인으로 보세요.`);

  const headline = !allSites.length
    ? "분석 데이터 없음"
    : highChangeCount > 0
    ? `오늘 확인할 변화 ${highChangeCount}건`
    : changes.length > 0
    ? `경쟁사 변화 ${changes.length}건 확인`
    : "오늘의 경쟁사 인사이트";
  const lead = !allSites.length
    ? "관리 URL을 추가하거나 수집을 실행하면 인사이트와 오늘 할 일이 표시됩니다."
    : `${metricTab === "all" ? "전체 분석" : METRICS[metricTab as MetricTab].label} 기준으로 Samsung 개선 포인트, 경쟁사 벤치마크, 근거 부족 항목을 분리했습니다.`;
  const overallLabel = !allSites.length
    ? "데이터 없음"
    : highChangeCount > 0 || samsungActions.some((x) => !/유지/.test(x))
    ? "오늘 확인"
    : changes.length > 0
    ? "변화 확인"
    : "유지";
  const confidenceLabel = evidenceWarnings.length ? "근거 보강 필요" : "근거 확보";

  const changedSites = orderedSiteKeys(changes.map((c) => c.site || "")).slice(0, 4).map(siteShortName);
  const executiveBullets = [
    samsungActions[0] || "Samsung 개선 포인트가 없습니다.",
    competitorBenchmarks[0] || "현재 비교 가능한 경쟁사 벤치마크가 없습니다.",
    changes.length
      ? `변화 감지: ${changedSites.join(", ") || "상세 목록"} 중심으로 확인하세요.`
      : "큰 변경은 없으므로 오늘 할 일과 벤치마크 포인트만 확인하세요.",
  ];

  return {
    scopedMetrics, allSites, siteRows, priorityRows, samsungActions, competitorBenchmarks, evidenceWarnings,
    headline, lead, overallLabel, confidenceLabel, executiveBullets,
    comparableCount, watchCount, riskCount, unknownCount, highChangeCount, actionCount,
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
          <p className="summaryEyebrow">Insight Board</p>
          <h2>{digest.headline}</h2>
          <p className="execLead">{digest.lead}</p>
          <div className="execBullets">
            <span>핵심 결론</span>
            {digest.executiveBullets.map((item) => <b key={item}>{item}</b>)}
          </div>
        </div>
        <div className="execKpiGrid" aria-label="Executive KPI">
          <div><b>{digest.samsungActions.length}</b><span>Samsung 개선</span></div>
          <div><b>{digest.competitorBenchmarks.length}</b><span>벤치마크</span></div>
          <div><b>{digest.highChangeCount || changes.length}</b><span>변화 감지</span></div>
          <div><b>{digest.evidenceWarnings.length}</b><span>근거 부족</span></div>
        </div>
      </div>

      <div className="decisionStrip insightStrip">
        <div>
          <span>Samsung 개선 포인트</span>
          <b>{digest.samsungActions.length}개</b>
          <p>{digest.samsungActions[0] || "현재 즉시 수정할 항목은 없습니다."}</p>
        </div>
        <div>
          <span>경쟁사 벤치마크</span>
          <b>{digest.competitorBenchmarks.length}개</b>
          <p>{digest.competitorBenchmarks[0] || "비교 가능한 경쟁사 포인트가 없습니다."}</p>
        </div>
        <div>
          <span>근거 상태</span>
          <b>{digest.confidenceLabel}</b>
          <p>{digest.evidenceWarnings[0] || "핵심 인사이트에 사용할 근거가 확보되어 있습니다."}</p>
        </div>
      </div>

      <div className="execSectionHead">
        <div>
          <p className="summaryEyebrow">오늘 할 일</p>
          <h3>오늘 할 일</h3>
        </div>
        <small>모든 탭 공통 규칙: 판단 + 오늘 할 일로 표시</small>
      </div>
      <div className="priorityTableWrap">
        <div className="priorityRow head">
          <span>우선순위</span><span>Site</span><span>영역</span><span>판단</span><span>오늘 할 일</span>
        </div>
        {digest.priorityRows.length === 0 ? (
          <div className="priorityEmpty">오늘 할 일 없음 · 현재 구성을 유지</div>
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
          <p className="summaryEyebrow">Status Matrix</p>
          <h3>사이트 × 분석축 요약</h3>
        </div>
        <small>우수 / 확인 필요 / 개선 필요 / 근거 부족으로 통일</small>
      </div>
      <div className={`matrixGrid cols-${displayMetrics.length}`}>
        <div className="matrixRow matrixHeader">
          <span>Site</span>
          {displayMetrics.map((m) => <span key={m}>{metricShortLabel(m)}</span>)}
          <span>근거 상태</span>
          <span>우선순위</span>
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
                <p className="scorecardAction">오늘 할 일: {row.action}</p>
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
        setAnswer("조건에 맞는 변경점은 없습니다. 다만 변경 없음으로 보기 전 아래 근거 부족 항목을 보조 확인하세요.\n" + qualityWarnings.map((row) => `- ${siteName(row.site)}: ${row.issue} → ${row.action}`).join("\n"));
        return;
      }
      setAnswer("조건에 맞는 변경점은 없습니다. 큰 근거 공백이 없으면 현재 구성을 유지하고, 다음 수집에서 Schema/CTA/카피/ALT COPY 변화만 비교하면 됩니다.");
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
        return `- ${siteName(s)} ${roleText}${METRICS[metric].label}: 근거 부족. ${health.summary} → 핵심 비교에서는 제외하고 URL·렌더링을 확인하세요.`;
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
          <p className="muted">현재 수집된 facts/changes 안에서만 판단과 오늘 할 일을 rule-based로 답합니다.</p>
        </div>
      )}
    </div>
  );
}
