"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MetricTab, MetricView, SiteKey, PageLite, PageDetail, UrlRow, Report, Change,
  METRICS, orderedSiteKeys, siteName, siteShortName, siteClass,
  metricAverage, metricOneLiner, bucketOf, shortUrl, pageRoleFromUrl,
  productCategoryFromRow, productCategoryKo, productPageLabel, roleDisplayKo,
} from "./shared";
import { AverageBox, PageDrilldown } from "./sectionCommon";

export type PageRow = PageLite & {
  site: SiteKey;
  page_role: string;
  product_category: string;
  page_label: string;
  status: "수집됨" | "수집 전";
  managed: boolean;
};

export const ROLE_ORDER = ["pf", "pdp", "buying", "specs", "campaign_or_compare", "campaign", "compare", "home", "content"];
export const roleRank = (role?: string) => {
  const idx = ROLE_ORDER.indexOf(role || "");
  return idx === -1 ? 99 : idx;
};
export const roleLabel = (role?: string) => roleDisplayKo(role);
const roleFromUrlRow = (row?: UrlRow, url?: string) => row?.page_role || pageRoleFromUrl(url || "");

export const buildPageRows = (
  visibleSiteKeys: SiteKey[],
  urls: UrlRow[],
  pages: Record<SiteKey, PageLite[]>,
  siteKeysForSort: SiteKey[] = visibleSiteKeys
): PageRow[] => {
  const out: PageRow[] = [];
  visibleSiteKeys.forEach((site) => {
    const managed = urls.filter((u) => u.site_key === site);
    const crawled = pages[site] || [];
    const crawledByUrl: Record<string, PageLite> = {};
    crawled.forEach((p) => { crawledByUrl[p.url] = p; });
    const seen = new Set<string>();

    managed.forEach((u) => {
      const p = crawledByUrl[u.url];
      const role = roleFromUrlRow(u, u.url);
      const category = productCategoryFromRow(u, u.url);
      seen.add(u.url);
      out.push({
        url: u.url,
        title: p?.title || "",
        word_count: p?.word_count || 0,
        site,
        page_role: role,
        product_category: category,
        page_label: productPageLabel(u, u.url),
        status: p ? "수집됨" : "수집 전",
        managed: true,
      });
    });
    crawled.forEach((p) => {
      if (seen.has(p.url)) return;
      const role = pageRoleFromUrl(p.url);
      const category = productCategoryFromRow(null, p.url);
      out.push({
        ...p,
        site,
        page_role: role,
        product_category: category,
        page_label: productPageLabel({ url: p.url, page_role: role, product_category: category }, p.url),
        status: "수집됨",
        managed: false,
      });
    });
  });
  return out.sort((a, b) =>
    siteKeysForSort.indexOf(a.site) - siteKeysForSort.indexOf(b.site) ||
    a.product_category.localeCompare(b.product_category) ||
    roleRank(a.page_role) - roleRank(b.page_role) ||
    a.url.localeCompare(b.url)
  );
};

const roleSummary = (rows: PageRow[]) => {
  const byRole = rows.reduce<Record<string, number>>((acc, r) => {
    acc[r.page_role] = (acc[r.page_role] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(byRole)
    .sort(([a], [b]) => roleRank(a) - roleRank(b))
    .map(([role, count]) => `${roleLabel(role)} ${count}`)
    .join(" · ");
};

/* ════════════════════════════════════════════════════
   Site별 분석 탭 — 실제 관리 URL + 제품군 + PF/PDP/Buying 역할 기준 딥다이브
════════════════════════════════════════════════════ */
export function PagesTab({
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
  const [selectedSite, setSelectedSite] = useState<SiteKey | "all">("all");
  const visibleSiteKeys = useMemo(
    () => selectedSite === "all" ? siteKeys : siteKeys.filter((s) => s === selectedSite),
    [siteKeys, selectedSite]
  );

  const pageRows = useMemo<PageRow[]>(
    () => buildPageRows(visibleSiteKeys, urls, pages, siteKeys),
    [visibleSiteKeys, urls, pages, siteKeys]
  );

  const crawledRows = pageRows.filter((p) => p.status === "수집됨");

  const avgFor = (site: SiteKey): ReturnType<typeof metricAverage> => {
    if (metricTab === "all") {
      const sitePages = pages[site] || [];
      const d = metricAverage(sitePages, dcv?.data?.[site]);
      const c = metricAverage(sitePages, dcv?.copy?.[site]);
      const v = metricAverage(sitePages, dcv?.visual?.[site]);
      return { pages: d.pages, avgWords: d.avgWords, schema: d.schema, thin: c.thin, lifestyle: v.lifestyle };
    }
    return metricAverage(pages[site] || [], dcv?.[metricTab]?.[site]);
  };

  const pageInsights = (site: SiteKey) => {
    const rows = pageRows.filter((r) => r.site === site);
    const crawled = rows.filter((r) => r.status === "수집됨");
    const categories = Array.from(new Set(rows.map((r) => r.product_category))).map(productCategoryKo).join(" · ");
    const roleText = roleSummary(rows);

    if (rows.length === 0) return "관리 URL이 없습니다. 먼저 이 사이트의 제품군별 PF/PDP/Buying URL 등록 여부를 확인하세요.";
    if (crawled.length === 0) {
      return `관리 기준 ${rows.length}개(${categories || "제품군 미분류"} / ${roleText || "역할 미분류"})가 있지만 아직 스냅샷이 없습니다. 차단, JS 렌더링, 리다이렉트, 타임아웃 여부를 먼저 확인하세요.`;
    }

    const notCrawled = rows.length - crawled.length;
    const byCategory = Array.from(new Set(rows.map((r) => r.product_category))).map((cat) => {
      const catRows = rows.filter((r) => r.product_category === cat);
      const catCrawled = catRows.filter((r) => r.status === "수집됨").length;
      return `${productCategoryKo(cat)} ${catCrawled}/${catRows.length}`;
    }).join(" · ");
    const missing = rows.filter((r) => r.status !== "수집됨").slice(0, 3).map((r) => `${r.page_label}(${shortUrl(r.url)})`);
    const missingText = missing.length ? ` 미수집 후보: ${missing.join(", ")}.` : "";
    return `관리 기준 ${rows.length}개 중 ${crawled.length}개 수집. 제품군별 수집 현황: ${byCategory}. ${notCrawled ? `근거 부족 URL ${notCrawled}개는 인사이트 산정에서 제외됩니다.` : "모든 관리 URL에 수집 근거가 있습니다."}${missingText}`;
  };

  const representative = useMemo(() => {
    const pool = metricTab === "all" ? allChanges : allChanges.filter((c) => bucketOf(c) === metricTab);
    const high = pool.find((c) => c.level === "High");
    if (high) return { url: high.url, reason: "변경점 중 가장 심각한 페이지" };
    if (pool[0]) return { url: pool[0].url, reason: "변경이 감지된 페이지" };
    const firstCrawled = crawledRows[0];
    if (firstCrawled) return { url: firstCrawled.url, reason: "변경이 없어 수집된 첫 페이지를 기준선으로 표시" };
    return null;
  }, [metricTab, allChanges, crawledRows]);

  const [autoMode, setAutoMode] = useState(true);
  const pick = (url: string) => { setAutoMode(false); onPick(url); };

  useEffect(() => {
    if (autoMode && representative && representative.url !== selectedUrl) onPick(representative.url);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [representative, autoMode]);

  return (
    <div className="panelStack">
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">Site별 분석</p>
            <h1 className="summaryH1">
              {metricTab === "all" ? "전체요약" : METRICS[metricTab].label} — 경쟁사별 페이지 딥다이브
            </h1>
            <p className="summaryDesc">
              {metricTab === "all"
                ? "경쟁사별로 어떤 제품군의 PF/PDP/Buying 페이지를 관리 대상으로 두고, 실제로 어느 페이지가 수집됐는지 먼저 보여줍니다."
                : METRICS[metricTab].plain}
            </p>
          </div>
        </div>

        <div className="severityLegend">
          {(metricTab === "all" ? (["data", "copy", "visual"] as MetricTab[]) : [metricTab]).map((m) => (
            <div key={m} className="sevRow">
              <span className={`badge ${m === "data" ? "c1" : m === "copy" ? "c2" : "c4"}`}>{METRICS[m].label}</span>
              <span className="sevDesc">
                {metricOneLiner(m, dcv?.[m], allChanges.filter((c) => bucketOf(c) === m), siteKeys)}
              </span>
            </div>
          ))}
        </div>

        <div className="siteFilterRow">
          <button className={selectedSite === "all" ? "on" : ""} onClick={() => setSelectedSite("all")}>전체 Site</button>
          {siteKeys.map((site) => (
            <button key={site} className={selectedSite === site ? "on" : ""} onClick={() => setSelectedSite(site)}>
              {siteName(site)}
            </button>
          ))}
        </div>

        <div className="avgGrid" style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
          {visibleSiteKeys.map((site) => <AverageBox key={site} title={siteName(site)} site={site} data={avgFor(site)} metric={metricTab} />)}
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
        {!loadingPage && selectedPage && <PageDrilldown page={selectedPage} />}
      </div>

      <div className="card">
        <p className="cardTitle">경쟁사별 수집 기준/인사이트</p>
        <div className="siteSplit">
          {visibleSiteKeys.map((site) => (
            <div key={site}>
              <p className="siteSplitHead"><span className={`badge ${siteClass(site)}`}>{siteName(site)}</span></p>
              <p className="findingText" style={{ fontSize: 12 }}>{pageInsights(site)}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <p className="cardTitle">Site별 분석 — 관리 URL/수집 페이지 목록 ({pageRows.length}개) · 제품군 + PF/PDP/Buying 기준</p>
        {visibleSiteKeys.map((site) => {
          const rows = pageRows.filter((p) => p.site === site);
          if (!rows.length) return null;
          const categories = Array.from(new Set(rows.map((r) => r.product_category)));
          return (
            <div key={site} style={{ marginBottom: 16 }}>
              <p className="tierRowHead" style={{ marginBottom: 6 }}>
                {siteName(site)}
                <span className="tierRowDesc">관리 {rows.filter((r) => r.managed).length}개 · 수집 {rows.filter((r) => r.status === "수집됨").length}개</span>
              </p>
              {categories.map((category) => {
                const categoryRows = rows.filter((r) => r.product_category === category);
                const roles = Array.from(new Set(categoryRows.map((r) => r.page_role))).sort((a, b) => roleRank(a) - roleRank(b));
                return (
                  <div key={`${site}-${category}`} style={{ marginBottom: 12 }}>
                    <p className="tierRowHead" style={{ marginBottom: 4, fontSize: 12 }}>
                      {productCategoryKo(category)}
                      <span className="tierRowDesc">{categoryRows.length}개 · {roleSummary(categoryRows)}</span>
                    </p>
                    {roles.map((role) => {
                      const roleRows = categoryRows.filter((r) => r.page_role === role);
                      return (
                        <div className="pageTable" key={`${site}-${category}-${role}`} style={{ marginBottom: 6 }}>
                          <div className="pageRow head">
                            <span>Site</span><span>제품/페이지</span><span>상태/단어 수</span><span>URL</span>
                          </div>
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
                              <span>
                                {p.title || shortUrl(p.url)}
                                <small>{shortUrl(p.url)}{!p.managed ? " · 관리 URL 외 수집" : ""}</small>
                              </span>
                            </button>
                          ))}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          );
        })}
        <p className="muted" style={{ marginTop: 8 }}>
          기준: 관리 URL의 제품군(폰/태블릿/버즈/워치/노트북)과 페이지 역할(PF/PDP/Buying 등)을 함께 봅니다. 수집 전 URL은 비교 근거가 아니므로 인사이트 산정에서 제외하고, 먼저 크롤 성공 여부를 확인합니다.
        </p>
      </div>
    </div>
  );
}
