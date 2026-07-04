"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MetricView, SiteKey, PageLite, PageDetail, UrlRow, Report, Change,
  PRODUCT_CATEGORY_ORDER, productCategoryKo, productCategoryDesc,
  orderedSiteKeys, siteName, siteShortName, siteClass, shortUrl, bucketOf,
  productPageLabel,
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
            <span className="badge c1">수집 기준</span>
            <span className="sevDesc">{productInsight(selectedCategory, visibleRows)}</span>
          </div>
        </div>

      </div>

      <div className="card">
        <p className="cardTitle">PF/PDP/Buying 완성도 — {productCategoryKo(selectedCategory)}</p>
        <p className="muted" style={{ marginBottom: 10 }}>역할이 다 갖춰졌으면 "특이사항 없음", 비어 있으면 무엇부터 확인할지만 보여줍니다.</p>
        <div className="siteSplit">
          {visibleSites.map((site) => {
            const rows = visibleRows.filter((r) => r.site === site);
            const roleCells = (["pf", "pdp", "buying"] as const).map((role) => ({ role, cell: roleCellFor(rows, role) }));
            const action = productMatrixAction(rows);
            return (
              <div key={site} className="card metricSummaryCard" style={{ padding: 13, cursor: "default" }}>
                <p className="siteSplitHead" style={{ marginBottom: 6 }}>
                  <span className={`badge ${siteClass(site)}`}>{siteName(site)}</span>
                  {site === "samsung" && <span className="ownTag">당사</span>}
                </p>
                {roleCells.map(({ role, cell }) => (
                  <div key={role} className="scoreRow" style={{ cursor: "default" }}>
                    <span>{role.toUpperCase()}</span>
                    <span>
                      <span className={`scoreDot ${cell.cls === "good" ? "good" : cell.cls === "unknown" ? "mid" : "bad"}`} />
                      <span className="scoreVal" style={{ fontSize: 12.5 }}>{cell.label}</span>
                    </span>
                  </div>
                ))}
                <div className="worstBox">
                  {action ? (
                    <p className="findingText siteInsightAction" style={{ fontSize: 12 }}>{action}</p>
                  ) : (
                    <p className="findingText" style={{ fontSize: 12, color: "var(--sec)" }}>PF/PDP/Buying 흐름 완비 · 특이사항 없음</p>
                  )}
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
