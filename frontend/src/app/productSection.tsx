"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MetricView, MetricTab, SiteKey, PageLite, PageDetail, UrlRow, Report, Change,
  PRODUCT_CATEGORY_ORDER, productCategoryKo, productCategoryDesc,
  orderedSiteKeys, siteName, siteShortName, siteClass, shortUrl, bucketOf,
  productPageLabel, METRICS, metricScoreBreakdown, scoreTier, scoreTierEmoji, scoreTierLabel, metricPhrase, shortActionPhrase, detailedAction,
} from "./shared";
import { PageDrilldown } from "./sectionCommon";
import { buildPageRows, PageRow, roleRank, roleLabel } from "./pagesSection";

const usefulCategories = (rows: PageRow[]) => PRODUCT_CATEGORY_ORDER.filter((cat) => rows.some((r) => r.product_category === cat));

const roleCoverage = (rows: PageRow[]) => {
  const roles = ["pf", "pdp", "buying"];
  return roles.map((role) => `${roleLabel(role)} ${rows.filter((r) => r.page_role === role).length}`).join(" · ");
};

const productInsight = (category: string, rows: PageRow[]) => {
  if (!rows.length) return `${productCategoryKo(category)} 관리 URL이 없습니다. PF/PDP/Buying 중 비교할 역할 URL부터 등록하세요.`;
  const siteKeys = orderedSiteKeys(rows.map((r) => r.site));
  const missing = rows.filter((r) => r.status !== "수집됨");
  const completeSites = siteKeys.filter((site) => ["pf", "pdp", "buying"].every((role) => rows.some((r) => r.site === site && r.page_role === role && r.status === "수집됨")));
  const missingExamples = missing.slice(0, 3).map((r) => `${siteShortName(r.site)} ${productPageLabel(r, r.url)}`).join(", ");
  return completeSites.length
    ? `${productCategoryKo(category)}는 ${completeSites.map(siteShortName).join(", ")}에서 PF/PDP/Buying 흐름을 비교할 수 있습니다. 역할이 비어 있는 사이트는 구매 CTA가 PDP 내부에 있는지 확인하세요.${missingExamples ? ` 근거 부족: ${missingExamples}.` : ""}`
    : `${productCategoryKo(category)}는 PF/PDP/Buying 3종이 모두 확보된 사이트가 없습니다. 제품군 비교 전에 누락 역할 URL 또는 PDP 내부 구매 CTA를 확인하세요.${missingExamples ? ` 근거 부족: ${missingExamples}.` : ""}`;
};

type RoleCell = { label: string; cls: "good" | "watch" | "unknown"; detail: string; count: number };

const roleCellFor = (rows: PageRow[], role: string): RoleCell => {
  const roleRows = rows.filter((r) => r.page_role === role);
  const collected = roleRows.filter((r) => r.status === "수집됨");
  if (collected.length) return { label: "있음", cls: "good", detail: `${collected.length}개 근거 확보`, count: collected.length };
  if (roleRows.length) return { label: "근거 부족", cls: "unknown", detail: "관리 URL은 있으나 상세 근거가 없습니다", count: roleRows.length };
  return { label: "없음", cls: "watch", detail: "역할 URL 또는 PDP 내부 CTA 확인 필요", count: 0 };
};

const productMatrixAction = (rows: PageRow[]): string | null => {
  const pf = roleCellFor(rows, "pf");
  const pdp = roleCellFor(rows, "pdp");
  const buying = roleCellFor(rows, "buying");
  if (pdp.label !== "있음") return "PDP 근거를 먼저 확보하고 제품 상세의 COPY/CTA와 Schema를 비교하세요.";
  if (buying.label !== "있음") return "Buying URL이 없으면 PDP 내부 구매 CTA와 혜택 영역을 확인하세요.";
  if (pf.label !== "있음") return "PF가 없으면 제품군 탐색에서 PDP/Buying으로 이어지는 CTA 흐름을 확인하세요.";
  return null;
};

export function ProductTab({
  metricTab, pages, urls, dcv, allChanges,
  selectedUrl, selectedPage, loadingPage, onPick, onOpenDrawer,
}: {
  metricTab: MetricView; pages: Record<SiteKey, PageLite[]>; urls: UrlRow[];
  dcv?: Report["dcv"]; allChanges: Change[];
  selectedUrl: string;
  selectedPage: PageDetail | null; loadingPage: boolean; onPick: (url: string) => void;
  onOpenDrawer: (id?: string) => void;
}) {
  const siteKeys = useMemo(
    () => orderedSiteKeys([...urls.map((u) => u.site_key || ""), ...Object.keys(pages)]),
    [pages, urls]
  );
  const allRows = useMemo(() => buildPageRows(siteKeys, urls, pages, siteKeys), [siteKeys, urls, pages]);
  const categoryKeys = useMemo(() => usefulCategories(allRows), [allRows]);
  const [selectedCategory, setSelectedCategory] = useState<string>(categoryKeys[0] || "phone");

  useEffect(() => {
    if (categoryKeys.length && !categoryKeys.includes(selectedCategory as any)) setSelectedCategory(categoryKeys[0]);
  }, [categoryKeys, selectedCategory]);

  const visibleRows = useMemo(
    () => allRows.filter((r) => r.product_category === selectedCategory),
    [allRows, selectedCategory]
  );
  const crawledRows = visibleRows.filter((r) => r.status === "수집됨");

  const representative = useMemo(() => {
    const visibleUrls = new Set(visibleRows.map((r) => r.url));
    const pool = (metricTab === "all" ? allChanges : allChanges.filter((c) => bucketOf(c) === metricTab))
      .filter((c) => visibleUrls.has(c.url));
    const high = pool.find((c) => c.level === "High");
    if (high) return { url: high.url, reason: `${productCategoryKo(selectedCategory)} 변경점 중 가장 심각한 페이지` };
    if (pool[0]) return { url: pool[0].url, reason: `${productCategoryKo(selectedCategory)}에서 변경이 감지된 페이지` };
    const firstCrawled = crawledRows[0];
    if (firstCrawled) return { url: firstCrawled.url, reason: `${productCategoryKo(selectedCategory)} 기준 수집된 첫 페이지` };
    return null;
  }, [metricTab, allChanges, visibleRows, crawledRows, selectedCategory]);

  const [autoMode, setAutoMode] = useState(true);
  const pick = (url: string) => { setAutoMode(false); onPick(url); };

  useEffect(() => {
    if (autoMode && representative && representative.url !== selectedUrl) onPick(representative.url);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [representative, autoMode]);



  const visibleSites = orderedSiteKeys(visibleRows.map((r) => r.site));

  return (
    <div className="panelStack">
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">제품별 분석</p>
            <h1 className="summaryH1">{productCategoryKo(selectedCategory)} — Site별 PF/PDP/Buying 비교</h1>
            <p className="summaryDesc">
              제품군별로 PF/PDP/Buying 흐름이 갖춰졌는지 보고, 비어 있는 역할은 액션로 바로 연결합니다.
            </p>
          </div>
        </div>

        <div className="siteFilterRow">
          {categoryKeys.map((cat) => (
            <button key={cat} className={selectedCategory === cat ? "on" : ""} onClick={() => setSelectedCategory(cat)}>
              {productCategoryKo(cat)}
            </button>
          ))}
        </div>
        <p className="muted" style={{ marginTop: 10 }}>{productCategoryDesc(selectedCategory)}</p>

        <div className="severityLegend" style={{ marginTop: 12 }}>
          <div className="sevRow">
            <span className="badge c1">제품별 요약</span>
            <span className="sevDesc">{productInsight(selectedCategory, visibleRows)}</span>
          </div>
        </div>

      </div>

      <div className="card">
        <p className="cardTitle">{productCategoryKo(selectedCategory)} — Site별 완성도</p>
        <p className="muted" style={{ marginBottom: 10 }}>점수는 사이트 전체 DATA/COPY/VISUAL 기준이고, 핵심 발견은 이 제품군의 PF/PDP/Buying 흐름 기준입니다.</p>
        <div className="siteSplit">
          {visibleSites.map((site) => {
            const rows = visibleRows.filter((r) => r.site === site);
            const roleCells = (["pf", "pdp", "buying"] as const).map((role) => ({ role, cell: roleCellFor(rows, role) }));
            const roleAction = productMatrixAction(rows);

            const axisScores = (["data", "copy", "visual"] as MetricTab[]).map((m) => {
              const total = metricScoreBreakdown(m, dcv?.[m]?.[site]).total;
              return { metric: m, total, tier: scoreTier(total) };
            });
            const scored = axisScores.filter((s) => s.total != null) as { metric: MetricTab; total: number; tier: ReturnType<typeof scoreTier> }[];
            const overall = scored.length ? Math.round(scored.reduce((a, b) => a + b.total, 0) / scored.length) : null;
            const overallTier = scoreTier(overall);
            const worstAxis = scored.length ? [...scored].sort((a, b) => a.total - b.total)[0] : null;
            // S9: 종합 인사이트 = 부족 항목(60점 미만)/모두 양호 (점수 포함 → 사이트마다 다름)
            const weakAxes = scored.filter((s) => s.total < 60).sort((a, b) => a.total - b.total);
            const okAxes = scored.filter((s) => s.total >= 60).map((s) => `${METRICS[s.metric].label} ${s.total}점`);
            const summaryLine = !scored.length
              ? "이번 수집엔 근거 없음 · 비교 대상에서 제외"
              : weakAxes.length
                ? `부족 항목 — ${weakAxes.map((s) => `${METRICS[s.metric].label} ${s.total}점`).join(", ")}${okAxes.length ? ` (나머지 양호: ${okAxes.join(", ")})` : ""}`
                : `세 지표 모두 양호 — ${scored.map((s) => `${METRICS[s.metric].label} ${s.total}점`).join(" · ")}`;
            // S9: 우선 액션은 역할 누락(roleAction) 우선, 없으면 가장 약한 지표+점수를 앞세워 사이트별 차별화
            const priorityAction = roleAction
              || (worstAxis ? `가장 약한 ${METRICS[worstAxis.metric].label}(${worstAxis.total}점)부터: ${detailedAction(worstAxis.metric, dcv?.[worstAxis.metric]?.[site])}` : "관리 URL과 수집 결과부터 확보하세요.");

            return (
              <div key={site} className="card metricSummaryCard" style={{ padding: 13, cursor: "default" }}>
                <p className="siteSplitHead" style={{ marginBottom: 6, justifyContent: "space-between" }}>
                  <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <span className={`badge ${siteClass(site)}`}>{siteName(site)}</span>
                    {site === "samsung" && <span className="ownTag">당사</span>}
                  </span>
                  <span className="siteOverallScore">
                    <span className={`scoreDot ${overallTier}`} />
                    {overall == null ? "-" : overall}
                  </span>
                </p>
                {axisScores.map(({ metric, total, tier }) => (
                  <div key={metric} className="scoreRow" style={{ cursor: "default" }}>
                    <span>{METRICS[metric].label}</span>
                    <span>
                      <span className={`scoreDot ${tier}`} />
                      <span className="scoreNum">{total == null ? "-" : `${total}점`}</span>
                    </span>
                  </div>
                ))}
                <div className="worstBox">
                  <p className="findingText" style={{ fontSize: 12 }}>종합 인사이트: {summaryLine}</p>
                  <p className="findingText" style={{ fontSize: 12 }}>
                    핵심 발견: {roleCells.map(({ role, cell }) => `${role.toUpperCase()} ${cell.label}`).join(" · ")}
                  </p>
                  <p className="findingText siteInsightAction" style={{ fontSize: 12 }}>추천 액션: {priorityAction}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="card">
        <p className="cardTitle">
          대표 페이지 상세 근거 — {selectedPage ? shortUrl(selectedPage.url) : ""} &nbsp;
          <button style={{ fontSize: 11, color: "var(--blue)", fontWeight: 400 }} onClick={() => onOpenDrawer()}>
            분석 기준 보기 ↗
          </button>
        </p>
        {representative && <p className="muted" style={{ marginTop: -6, marginBottom: 10 }}>선정 이유: {representative.reason}{!autoMode && " (수동 선택됨)"}</p>}
        {selectedPage && (() => {
          const currentRow = allRows.find((r) => r.url === selectedPage.url);
          const siblings = currentRow
            ? allRows.filter((r) => r.site === currentRow.site && r.url !== currentRow.url && r.status === "수집됨")
                .sort((a, b) => (a.product_category === b.product_category
                  ? roleRank(a.page_role) - roleRank(b.page_role)
                  : PRODUCT_CATEGORY_ORDER.indexOf(a.product_category as any) - PRODUCT_CATEGORY_ORDER.indexOf(b.product_category as any)))
            : [];
          return siblings.length > 0 ? (
            <div className="pageSwitcherRow">
              <span className="pageSwitcherLabel">{siteName(currentRow!.site)}의 다른 제품 페이지:</span>
              {siblings.slice(0, 8).map((r) => (
                <button key={r.url} className="pageSwitcherChip" onClick={() => pick(r.url)}>
                  {productCategoryKo(r.product_category)} · {r.page_label || shortUrl(r.url)}
                </button>
              ))}
            </div>
          ) : null;
        })()}
        {loadingPage && <p className="muted">불러오는 중…</p>}
        {!loadingPage && !selectedPage && <p className="muted">아래 수집된 페이지를 선택하면 DATA/COPY/VISUAL 상세 근거가 표시됩니다.</p>}
        {!loadingPage && selectedPage && <PageDrilldown page={selectedPage} focusMetric={metricTab} />}
      </div>

      <div className="card">
        <p className="cardTitle">제품별 상세 URL — {productCategoryKo(selectedCategory)} ({visibleRows.length}개)</p>
        {visibleSites.map((site) => {
          const rows = visibleRows.filter((r) => r.site === site);
          const roles = Array.from(new Set(rows.map((r) => r.page_role))).sort((a, b) => roleRank(a) - roleRank(b));
          return (
            <div key={site} style={{ marginBottom: 14 }}>
              <p className="tierRowHead" style={{ marginBottom: 6 }}>
                {siteName(site)}
                <span className="tierRowDesc">관리 {rows.filter((r) => r.managed).length}개 · 수집 {rows.filter((r) => r.status === "수집됨").length}개 · {roleCoverage(rows)}</span>
              </p>
              {roles.map((role) => {
                const roleRows = rows.filter((r) => r.page_role === role);
                return (
                  <div className="pageTable" key={`${site}-${role}`} style={{ marginBottom: 8 }}>
                    <div className="pageRow head"><span>Site</span><span>페이지</span><span>상태/단어 수</span><span>URL</span></div>
                    {roleRows.map((p) => (
                      <button
                        key={`${p.site}-${p.url}`}
                        className={`pageRow ${selectedUrl === p.url ? "selected" : ""} ${p.status !== "수집됨" ? "pending" : ""}`}
                        onClick={() => p.status === "수집됨" ? pick(p.url) : undefined}
                        title={p.status !== "수집됨" ? "아직 페이지 스냅샷이 없어 상세 근거를 열 수 없습니다." : p.url}
                      >
                        <span><span className={`badge ${siteClass(p.site)}`} style={{ fontSize: 10 }}>{siteShortName(p.site)}</span></span>
                        <span>{p.page_label}</span>
                        <span>{p.status === "수집됨" ? `${p.word_count || 0}단어` : "수집 전"}</span>
                        <span>{p.title || shortUrl(p.url)}<small>{shortUrl(p.url)}{!p.managed ? " · 관리 URL 외 수집" : ""}</small></span>
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
