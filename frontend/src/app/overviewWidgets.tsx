"use client";

import { useState } from "react";
import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, Report,
  METRICS, orderedSiteKeys, siteName, siteShortName, siteClass, levelKo, levelClass,
  shortUrl, bucketOf, actionForChange, metricActionSentence, metricIssueSentence, metricAreaLabel, siteMetricScore,
  PRODUCT_CATEGORY_ORDER, productCategoryKo, productCategoryFromRow,
  metricScoreBreakdown, scoreTier, ScoreTier, scoreTierEmoji, scoreTierLabel, shortActionPhrase, detailedAction,
} from "./shared";
import {
  compactSummary,
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
  blocks: Partial<Record<MetricTab, AnalysisBlock | undefined>>;
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
  metric: MetricTab;
  change?: Change;
};

type AxisHighlight = {
  metric: MetricTab;
  score: number | null;
  tier: ScoreTier;
  competitorAvg: number | null;
  delta: number | null; // Samsung score - 경쟁사 평균
  keyStatLabel: string;
  keyStatValue: number | null;
  insight: string;
  action: string;
  change?: Change;
};

export type BoardDigest = {
  scopedMetrics: MetricTab[];
  allSites: SiteKey[];
  siteRows: SiteDashboardRow[];
  priorityRows: PriorityIssue[];
  axisHighlights: AxisHighlight[];
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
    if (coverage === 0 && h1Pct === 0) return { state: "risk", label: "주의 필요", summary: "Schema와 H-tag 역할 신호 적용 범위가 제한적입니다" };
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
      return { state: "risk", label: "주의 필요", summary: "구매 CTA와 카피 연결 범위가 제한적입니다" };
    }
    return { state: changed ? "watch" : "good", label: changed ? "변화 있음" : "우수", summary: `카피 ${score ?? "-"}점 · CTA ${cta}p` };
  }

  const totalPages = pageCountFromBlock(metric, block);
  const imageCount = visualImageCount(block);
  const altPct = visualAltPct(block);
  if (!totalPages) return { state: "unknown", label: "근거 부족", summary: "VISUAL / ALT COPY 페이지 근거가 부족합니다" };
  if (imageCount === 0) return { state: "unknown", label: "근거 부족", summary: "이미지/ALT COPY 근거가 부족합니다" };
  if (high) return { state: "risk", label: "변화 있음", summary: "핵심 이미지/ALT COPY 변경을 확인해야 합니다" };
  if ((altPct ?? 0) < 40) return { state: "risk", label: "주의 필요", summary: "ALT COPY의 구체성이 상대적으로 낮습니다" };
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
  if (weakMetric) return detailedAction(weakMetric[0], row.blocks[weakMetric[0]]);
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
    const blocks: Partial<Record<MetricTab, AnalysisBlock | undefined>> = {
      data: dcv?.data?.[site], copy: dcv?.copy?.[site], visual: dcv?.visual?.[site],
    };
    const row: SiteDashboardRow = {
      site, metrics, blocks, collection, priority, changes: siteChanges,
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
      metric: bucketOf(c),
      change: c,
    }));

  const samsungRowForCompare = rows.find((r) => r.site === "samsung");
  const insightRows = rows
    .filter((row) => row.priority !== "Low" && !changeRows.some((x) => x.site === row.site))
    .sort((a, b) => priorityRank[a.priority] - priorityRank[b.priority])
    .slice(0, 6)
    .map((row) => {
      const weakMetric = scopedMetrics.find((m) => row.metrics[m].state === "risk" || row.metrics[m].state === "unknown" || row.metrics[m].state === "watch");
      const samsungMetric = weakMetric ? samsungRowForCompare?.metrics[weakMetric] : undefined;
      const action = !weakMetric
        ? row.action
        : row.site === "samsung"
          ? detailedAction(weakMetric, row.blocks[weakMetric])
          : samsungMetric && samsungMetric.state === "good"
            ? `Samsung은 지금 ${samsungMetric.summary} 수준을 유지하세요.`
            : samsungMetric && samsungMetric.state === "watch"
              ? `Samsung도 ${METRICS[weakMetric].label}이 완전하지 않으니, 함께 점검하세요: ${detailedAction(weakMetric, samsungRowForCompare?.blocks[weakMetric])}`
              : detailedAction(weakMetric, row.blocks[weakMetric]);
      return {
        id: `insight-${row.site}`,
        priority: row.priority,
        site: row.site,
        area: weakMetric ? METRICS[weakMetric].label : "근거 상태",
        issue: weakMetric ? row.metrics[weakMetric].summary : row.issue,
        action,
        source: row.collection.state === "unknown" ? "evidence" as const : "insight" as const,
        metric: weakMetric || scopedMetrics[0] || "copy",
        change: row.changes[0],
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
      lines.push(`${metricIssueSentence(m)} ${detailedAction(m, row.blocks[m])}`);
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

const AXIS_INSIGHT_OBSERVATION: Record<MetricTab, string> = {
  data: "페이지 구조 데이터는 존재하지만",
  copy: "구매 관련 페이지는 존재하지만",
  visual: "이미지는 확보되어 있지만",
};
const AXIS_INSIGHT_MEANING: Record<MetricTab, string> = {
  data: "검색 엔진이 페이지 역할을 해석하는 신호 범위가 제한될 수 있습니다.",
  copy: "페이지 수보다 행동 연결 밀도 차이가 더 크게 나타납니다.",
  visual: "이미지 의미 전달 범위가 제한될 수 있습니다.",
};

function buildAxisInsight(metric: MetricTab, weakestLabel: string | undefined, delta: number | null, tier: ScoreTier): string {
  const compareText = delta == null
    ? "경쟁사 비교 근거가 아직 부족합니다"
    : delta < 0
      ? `${weakestLabel || METRICS[metric].label} 적용 범위가 경쟁사보다 ${Math.abs(delta)}%p 좁습니다`
      : delta > 0
        ? `${weakestLabel || METRICS[metric].label} 적용 범위가 경쟁사보다 ${delta}%p 넓습니다`
        : `${weakestLabel || METRICS[metric].label} 적용 범위가 경쟁사와 비슷한 수준입니다`;
  const nuance = (delta != null && delta > 0 && tier !== "good")
    ? ` 경쟁사보다는 앞서 있지만, 절대 점수 기준으로는 아직 ${scoreTierLabel(tier)} 구간입니다.`
    : "";
  return `${AXIS_INSIGHT_OBSERVATION[metric]} ${compareText}.${nuance} ${AXIS_INSIGHT_MEANING[metric]}`;
}

function buildAxisHighlights(
  dcv: Report["dcv"] | undefined, allSites: SiteKey[], scopedMetrics: MetricTab[], changes: Change[],
): AxisHighlight[] {
  return scopedMetrics.map((metric): AxisHighlight => {
    const samsungBlock = dcv?.[metric]?.["samsung"];
    const samsungBreak = metricScoreBreakdown(metric, samsungBlock);
    const score = samsungBreak.total;
    const tier = scoreTier(score);

    const competitorScores = allSites
      .filter((s) => s !== "samsung")
      .map((s) => metricScoreBreakdown(metric, dcv?.[metric]?.[s]).total)
      .filter((v): v is number => v != null);
    const competitorAvg = competitorScores.length
      ? Math.round(competitorScores.reduce((a, b) => a + b, 0) / competitorScores.length) : null;
    const delta = score != null && competitorAvg != null ? score - competitorAvg : null;

    const weakestComponent = [...samsungBreak.components]
      .filter((c) => c.value != null)
      .sort((a, b) => (a.value as number) - (b.value as number))[0];

    const samsungChange = changes
      .filter((c) => c.site === "samsung" && bucketOf(c) === metric)
      .sort((a, b) => priorityRank[(a.level || "Low") as PriorityLevel] - priorityRank[(b.level || "Low") as PriorityLevel])[0];

    const aheadButModerate = delta != null && delta > 0 && tier !== "good";
    const action = samsungChange
      ? actionForChange(samsungChange)
      : aheadButModerate
        ? `경쟁 우위는 유지하면서 ${detailedAction(metric, samsungBlock)}`
        : detailedAction(metric, samsungBlock);

    return {
      metric, score, tier, competitorAvg, delta,
      keyStatLabel: weakestComponent?.label || METRICS[metric].label,
      keyStatValue: weakestComponent?.value ?? score,
      insight: buildAxisInsight(metric, weakestComponent?.label, delta, tier),
      action,
      change: samsungChange,
    };
  });
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
  const axisHighlights = buildAxisHighlights(dcv, allSites, scopedMetrics, changes);
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
    ? "관리 URL을 추가하거나 수집을 실행하면 인사이트와 액션이 표시됩니다."
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
      : "큰 변경은 없으므로 액션과 벤치마크 포인트만 확인하세요.",
  ];

  return {
    scopedMetrics, allSites, siteRows, priorityRows, axisHighlights, samsungActions, competitorBenchmarks, evidenceWarnings,
    headline, lead, overallLabel, confidenceLabel, executiveBullets,
    comparableCount, watchCount, riskCount, unknownCount, highChangeCount, actionCount,
  };
}

/* WatchPointPanel — Site별 분석(pagesSection) 탭과 같은 "카드 여러 개를 쌓는" 톤으로 통일.
   ① 요약 3줄 스트립 ② Site별 인사이트(클릭 → 상세로 이동) ③ 액션 표(클릭 → 상세로 이동)
   ④ 매트릭스는 접어서 보관(원하는 사람만 펼쳐봄). 헤드라인/KPI는 상위 summaryCard와 중복이라 제거. */
export function WatchPointPanel({
  changes, dcv, metricTab, expectedSites = [], onJumpToMetric,
}: {
  changes: Change[]; dcv?: Report["dcv"]; metricTab: MetricView; expectedSites?: SiteKey[];
  onJumpToMetric?: (m: MetricTab, change?: Change) => void;
}) {
  const digest = buildDashboardDigest({ changes, dcv, metricTab, expectedSites });
  const jump = (metric: MetricTab, change?: Change) => onJumpToMetric?.(metric, change);

  return (
    <>
      {/* ① 축별 핵심 발견 — DATA/COPY/VISUAL 3장 고정, 항상 Samsung 자체 점수 기준.
         제목 → 점수+신호등 → 핵심 수치(경쟁사 평균 대비) → 인사이트(관찰→비교→의미) → 우선 액션 */}
      <div className="card">
        <p className="cardTitle">축별 핵심 발견 <span className="cardTitleHint">— 누르면 해당 탭·상세로 이동</span></p>
        <div className="axisGrid">
          {digest.axisHighlights.map((h) => (
            <button key={h.metric} className="axisCard" onClick={() => jump(h.metric, h.change)}>
              <p className="axisCardLabel">{metricShortLabel(h.metric)}</p>
              <p className="axisCardScore">
                <span>{scoreTierEmoji(h.tier)}</span>
                <span className="axisCardScoreNum">{h.score == null ? "-" : h.score}</span>
                <span className="axisCardTier">{scoreTierLabel(h.tier)}</span>
              </p>
              <p className="axisCardStat">
                {h.keyStatLabel} {h.keyStatValue == null ? "근거 없음" : `${h.keyStatValue}%`}
                {h.delta != null && (
                  <span className={h.delta < 0 ? "axisCardDeltaBad" : "axisCardDeltaGood"}>
                    {" "}({h.delta > 0 ? "+" : ""}{h.delta}%p vs 경쟁사)
                  </span>
                )}
              </p>
              <p className="axisCardInsight">{h.insight}</p>
              <hr className="axisCardHr" />
              <p className="axisCardAct">우선 액션: {h.action}</p>
            </button>
          ))}
        </div>
      </div>

      {/* ② 전체 액션 — 위 축 카드는 하이라이트 3건, 여기는 전체 목록 (용도가 다름) */}
      <div className="card">
        <p className="cardTitle">전체 액션 ({digest.priorityRows.length}건)</p>
        <div className="priorityTableWrap">
          <div className="priorityRow head">
            <span>우선순위</span><span>Site</span><span>영역</span><span>판단</span><span>액션</span>
          </div>
          {digest.priorityRows.length === 0 ? (
            <div className="priorityEmpty">액션 없음 · 현재 구성을 유지</div>
          ) : digest.priorityRows.map((row) => (
            <button key={row.id} className="priorityRow" onClick={() => jump(row.metric, row.change)}>
              <span><span className={`sevBadge ${levelClass(row.priority)}`}>{levelKo(row.priority)}</span></span>
              <span><span className={`badge ${siteClass(row.site)}`}>{siteName(row.site)}</span></span>
              <span>{row.area}</span>
              <span>{row.issue}</span>
              <span>{row.action}</span>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

type QaResultRow = {
  site: SiteKey; metric: MetricTab; score: number | null; tier: ScoreTier;
  components: { label: string; value: number | null }[];
  health: MetricHealth; evidenceItems: { url: string; text: string }[];
};

export function InsightChat({ dcv, changes, expectedSites = [] }: { dcv?: Report["dcv"]; changes: Change[]; expectedSites?: SiteKey[] }) {
  const [open, setOpen] = useState(false);
  const [qaSite, setQaSite] = useState<string>("all");
  const [qaMetric, setQaMetric] = useState<string>("all");
  const [qaCategory, setQaCategory] = useState<string>("all");
  const [results, setResults] = useState<QaResultRow[] | null>(null);
  const [resultLabel, setResultLabel] = useState<string>("");

  const allQaSites = orderedSiteKeys([...expectedSites, ...Object.keys(dcv?.data || {}), ...Object.keys(dcv?.copy || {}), ...Object.keys(dcv?.visual || {}), ...changes.map((c) => c.site || "")]);

  const askStructured = () => {
    const metricsToShow = qaMetric === "all" ? (["data", "copy", "visual"] as MetricTab[]) : [qaMetric as MetricTab];
    const sitesToShow = qaSite === "all" ? allQaSites : [qaSite as SiteKey];
    if (!sitesToShow.length) {
      setResults([]);
      setResultLabel("표시할 사이트가 없습니다. 관리 URL을 추가하고 수집을 실행하세요.");
      return;
    }
    const rows: QaResultRow[] = sitesToShow.flatMap((s) =>
      metricsToShow.map((m) => {
        const block = dcv?.[m]?.[s];
        const breakdown = metricScoreBreakdown(m, block);
        const sChanges = changes.filter((c) => bucketOf(c) === m && c.site === s
          && (qaCategory === "all" || productCategoryFromRow(undefined, c.url) === qaCategory))
          .sort((a, b) => priorityRank[(a.level || "Low") as PriorityLevel] - priorityRank[(b.level || "Low") as PriorityLevel]);
        const health = metricHealth(m, block, sChanges);
        const evidenceItems = sChanges.length
          ? sChanges.slice(0, 5).map((c) => ({ url: c.url || "", text: `${levelKo((c.level || "Low") as PriorityLevel)} · ${c.summary || c.field || "변경 감지"}` }))
          : [];
        return { site: s, metric: m, score: breakdown.total, tier: scoreTier(breakdown.total), components: breakdown.components, health, evidenceItems };
      })
    );
    setResultLabel(`${qaSite === "all" ? "브랜드 전체" : siteName(qaSite as SiteKey)} · ${qaCategory === "all" ? "제품 전체" : productCategoryKo(qaCategory)} · ${qaMetric === "all" ? "지표 전체" : METRICS[qaMetric as MetricTab].label}`);
    setResults(rows);
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
          <div className="qaPickRow">
            <select value={qaSite} onChange={(e) => setQaSite(e.target.value)}>
              <option value="all">브랜드 전체</option>
              {allQaSites.map((s) => <option key={s} value={s}>{siteName(s)}</option>)}
            </select>
            <select value={qaCategory} onChange={(e) => setQaCategory(e.target.value)}>
              <option value="all">제품 전체</option>
              {PRODUCT_CATEGORY_ORDER.map((c) => <option key={c} value={c}>{productCategoryKo(c)}</option>)}
            </select>
            <select value={qaMetric} onChange={(e) => setQaMetric(e.target.value)}>
              <option value="all">지표 전체</option>
              <option value="data">DATA / Schema</option>
              <option value="copy">COPY / CTA</option>
              <option value="visual">VISUAL / ALT COPY</option>
            </select>
          </div>
          <button className="qaPickGo qaPickGoFull" onClick={askStructured}>점수·신호등·근거 보기</button>

          {results && (
            <div className="qaResultWrap">
              <p className="qaResultLabel">{resultLabel}</p>
              {results.length === 0 ? (
                <p className="muted">{resultLabel}</p>
              ) : results.map((r, i) => (
                <div key={`${r.site}-${r.metric}-${i}`} className="qaResultRow">
                  <p className="qaResultHead">
                    <span className={`badge ${siteClass(r.site)}`}>{siteName(r.site)}</span>
                    <span className="qaResultMetric">{METRICS[r.metric].label}</span>
                    <span className={`scoreDot ${r.tier}`} />
                    <span className="scoreVal">{r.score == null ? "근거 없음" : `${r.score}점 · ${scoreTierLabel(r.tier)}`}</span>
                  </p>
                  <p className="qaResultComponents">
                    {r.components.map((c) => `${c.label} ${c.value == null ? "-" : c.value + "%"}`).join(" · ")}
                  </p>
                  <p className="qaResultSummary">{r.health.summary}</p>
                  {r.evidenceItems.length > 0 && (
                    <ul className="qaResultEvidence">
                      {r.evidenceItems.map((item, j) => (
                        <li key={j}>
                          {item.text}
                          {item.url && (
                            <a href={item.url} target="_blank" rel="noreferrer" className="qaResultUrl">{shortUrl(item.url)}</a>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
          <p className="muted" style={{ marginTop: 8 }}>현재 수집된 facts/changes 안에서만 점수와 근거를 rule-based로 보여줍니다.</p>
        </div>
      )}
    </div>
  );
}
