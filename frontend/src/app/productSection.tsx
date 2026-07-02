"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MetricView, SiteKey, PageLite, PageDetail, UrlRow, Report, Change,
  PRODUCT_CATEGORY_ORDER, productCategoryKo, productCategoryDesc,
  orderedSiteKeys, siteName, siteShortName, siteClass, shortUrl, bucketOf,
  productPageLabel, METRICS, MetricTab,
} from "./shared";
import { AverageBox, PageDrilldown } from "./sectionCommon";
import { buildPageRows, PageRow, roleRank, roleLabel } from "./pagesSection";

const usefulCategories = (rows: PageRow[]) => PRODUCT_CATEGORY_ORDER.filter((cat) => rows.some((r) => r.product_category === cat));

const roleCoverage = (rows: PageRow[]) => {
  const roles = ["pf", "pdp", "buying"];
  return roles.map((role) => `${roleLabel(role)} ${rows.filter((r) => r.page_role === role).length}`).join(" · ");
};

const productInsight = (category: string, rows: PageRow[]) => {
  if (!rows.length) return `${productCategoryKo(category)} 관리 URL이 없습니다.`;
  const siteKeys = orderedSiteKeys(rows.map((r) => r.site));
  const collected = rows.filter((r) => r.status === "수집됨");
  const missing = rows.filter((r) => r.status !== "수집됨");
  const bySite = siteKeys.map((site) => {
    const siteRows = rows.filter((r) => r.site === site);
    const got = siteRows.filter((r) => r.status === "수집됨").length;
    return `${siteShortName(site)} ${got}/${siteRows.length}`;
  }).join(" · ");
  const missingExamples = missing.slice(0, 3).map((r) => `${siteShortName(r.site)} ${productPageLabel(r, r.url)}`).join(", ");
  const completeSites = siteKeys.filter((site) => ["pf", "pdp", "buying"].every((role) => rows.some((r) => r.site === site && r.page_role === role)));
  return `${productCategoryKo(category)} 수집 범위: Site별 ${bySite}. 역할 구성은 ${roleCoverage(rows)}입니다. ${completeSites.length ? `PF/PDP/Buying 3종이 모두 있는 사이트: ${completeSites.map(siteShortName).join(", ")}.` : "PF/PDP/Buying 3종이 모두 갖춰진 사이트는 아직 없습니다."}${missingExamples ? ` 수집 전/근거부족: ${missingExamples}.` : " 모든 관리 URL에 수집 근거가 있습니다."}`;
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

  const metricForSite = (site: SiteKey) => {
    const sitePages = pages[site] || [];
    if (metricTab !== "all") {
      const block = dcv?.[metricTab]?.[site];
      return {
        pages: sitePages.length,
        avgWords: sitePages.length ? Math.round(sitePages.reduce((a, p) => a + (p.word_count || 0), 0) / sitePages.length) : 0,
        schema: typeof block?.facts?.schema?.coverage_pct === "number" ? block.facts.schema.coverage_pct + "%" : "-",
        thin: typeof block?.facts?.content_density?.thin_pages?.length === "number" ? block.facts.content_density.thin_pages.length + "개" : "-",
        lifestyle: typeof block?.facts?.image_diversity?.lifestyle_ratio_pct === "number" ? block.facts.image_diversity.lifestyle_ratio_pct + "%" : "-",
      };
    }
    return {
      pages: sitePages.length,
      avgWords: sitePages.length ? Math.round(sitePages.reduce((a, p) => a + (p.word_count || 0), 0) / sitePages.length) : 0,
      schema: typeof dcv?.data?.[site]?.facts?.schema?.coverage_pct === "number" ? dcv.data[site].facts.schema.coverage_pct + "%" : "-",
      thin: typeof dcv?.copy?.[site]?.facts?.content_density?.thin_pages?.length === "number" ? dcv.copy[site].facts.content_density.thin_pages.length + "개" : "-",
      lifestyle: typeof dcv?.visual?.[site]?.facts?.image_diversity?.lifestyle_ratio_pct === "number" ? dcv.visual[site].facts.image_diversity.lifestyle_ratio_pct + "%" : "-",
    };
  };

  const visibleSites = orderedSiteKeys(visibleRows.map((r) => r.site));

  return (
    <div className="panelStack">
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">제품별 분석</p>
            <h1 className="summaryH1">{productCategoryKo(selectedCategory)} — Site별 PF/PDP/Buying 비교</h1>
            <p className="summaryDesc">
              폰, 태블릿, 버즈/오디오, 워치, 노트북/PC처럼 제품군을 먼저 고른 뒤 Site별로 어떤 PF/PDP/Buying URL을 관리하고 실제 수집됐는지 확인합니다.
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
            <span className="badge c1">수집 기준</span>
            <span className="sevDesc">{productInsight(selectedCategory, visibleRows)}</span>
          </div>
          {(metricTab === "all" ? (["data", "copy", "visual"] as MetricTab[]) : [metricTab]).map((m) => (
            <div key={m} className="sevRow">
              <span className={`badge ${m === "data" ? "c1" : m === "copy" ? "c2" : "c4"}`}>{METRICS[m].label}</span>
              <span className="sevDesc">이 제품군에서 수집된 페이지를 기준으로 상세 근거를 아래에서 확인하세요. 수집 전 URL은 근거 부족으로 분리 표시합니다.</span>
            </div>
          ))}
        </div>

        <div className="avgGrid" style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
          {visibleSites.map((site) => <AverageBox key={site} title={siteName(site)} site={site} data={metricForSite(site)} metric={metricTab} />)}
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
        {loadingPage && <p className="muted">불러오는 중…</p>}
        {!loadingPage && !selectedPage && <p className="muted">아래 수집된 페이지를 선택하면 DATA/COPY/VISUAL 상세 근거가 표시됩니다.</p>}
        {!loadingPage && selectedPage && <PageDrilldown page={selectedPage} focusMetric={metricTab} />}
      </div>

      <div className="card">
        <p className="cardTitle">제품별 URL 목록 — {productCategoryKo(selectedCategory)} ({visibleRows.length}개)</p>
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
