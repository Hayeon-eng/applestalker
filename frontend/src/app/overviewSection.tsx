"use client";

import { useEffect, useState } from "react";
import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, Report, UrlRow,
  METRICS, siteName, siteShortName, siteClass, levelKo, levelClass, severityEmoji, topSeverityChanges,
  groupByUrl, shortUrl, linesFromBlock, metricOneLiner, bucketOf, actionForChange, orderedSiteKeys,
} from "./shared";
import { ChangeDrilldown, CurrentStatusDrilldown, type CurrentFindingSelection } from "./evidencePanels";
import { FindingList, sitesFromBlocks } from "./sectionCommon";
import { WatchPointPanel, InsightChat, buildDashboardDigest } from "./overviewWidgets";

/* ════════════════════════════════════════════════════
   Overview 탭 — 순서: ①변화N건+액션 ②사이트별 현황/변경 요약 ③지표별 분석 ④변경점목록
════════════════════════════════════════════════════ */
/* ── 한 메트릭(DATA/COPY/VISUAL)의 [분석기준 → 현황요약 → 변경점목록] 3장 세트.
   단일 메트릭 탭에서도, '전체요약' 탭에서 3번 반복할 때도 이 컴포넌트 하나로 재사용 ── */
function MetricSection({
  metric, changes, siteBlocks, selectedChange, setSelectedChange, showHeading, urlFilter, onClearUrlFilter,
}: {
  metric: MetricTab; changes: Change[]; siteBlocks: Record<string, AnalysisBlock>;
  selectedChange: Change | null; setSelectedChange: (c: Change | null) => void;
  showHeading?: boolean; urlFilter?: string | null; onClearUrlFilter?: () => void;
}) {
  const sites = sitesFromBlocks(siteBlocks, changes);
  const changesBySite = (site: SiteKey) => changes.filter((c) => c.site === site);
  const [selectedFinding, setSelectedFinding] = useState<CurrentFindingSelection | null>(null);
  const currentEvidenceId = `current-evidence-${metric}`;
  const openCurrentEvidence = (site: SiteKey, index: number, line: string, label: string) => {
    setSelectedFinding({ site, index, line, label });
    setTimeout(() => {
      document.getElementById(currentEvidenceId)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };
  useEffect(() => {
    setSelectedFinding(null);
  }, [metric]);
  return (
    <>
      {showHeading && (
        <p className="metricSectionHeading">
          <span className={`badge ${metric === "data" ? "c1" : metric === "copy" ? "c2" : "c4"}`}>
            {METRICS[metric].label}
          </span>
        </p>
      )}

      {/* 현황 요약 — 변경 유무 관계없는 현재 상태 (사이트별) */}
      <div className="card">
        <p className="cardTitle">현황/변경점 분석 — {METRICS[metric].label}</p>
        <div className="siteSplit">
          {sites.map((site) => (
            <div key={site}>
              <p className="siteSplitHead">
                <span className={`badge ${siteClass(site)}`}>{siteName(site)}</span>
                {siteBlocks[site]?._source === "gemini" ? (
                  <span className="badge c2" title="Gemini가 근거 기반으로 서술 — evidence 없는 내용은 생성하지 않음">🤖 AI 분석 기반</span>
                ) : siteBlocks[site]?._source === "rule_based" ? (
                  <span className="badge c6" title="현재 facts를 규칙으로 집계한 결과입니다. 외부 AI 문장 생성 없이 근거값만 사용합니다.">📐 규칙기반 분석</span>
                ) : null}
              </p>
              <FindingList
                metric={metric}
                lines={linesFromBlock(siteBlocks[site])}
                selectedIndex={selectedFinding?.site === site ? selectedFinding.index : undefined}
                onSelectLine={(index, line, label) => openCurrentEvidence(site, index, line, label)}
              />
            </div>
          ))}
        </div>
      </div>

      {selectedFinding && (
        <details className="card currentEvidenceCard" id={currentEvidenceId} open>
          <summary className="summaryEvidenceSummary">
            상세 근거 — {siteName(selectedFinding.site)} / {selectedFinding.label}
          </summary>
          <div className="summaryEvidenceBody">
            <CurrentStatusDrilldown
              metric={metric}
              site={selectedFinding.site}
              block={siteBlocks[selectedFinding.site]}
              selection={selectedFinding}
            />
          </div>
        </details>
      )}

      {/* 변경점 목록 (사이트별) */}
      <div className="card" id="change-list-section">
        <p className="cardTitle">
          변경점 목록 — {METRICS[metric].label} ({changes.length}건)
          {urlFilter && (
            <span className="urlFilterTag">
              🔎 {shortUrl(urlFilter)}만 보기
              <button onClick={onClearUrlFilter}>필터 해제 ×</button>
            </span>
          )}
        </p>
        {changes.length === 0 ? (
          <p className="muted">이 영역에서 변경된 항목이 없습니다. 현재 구성은 유지하고 다음 수집에서 변화만 확인하세요.</p>
        ) : (
          <div className="siteSplit">
            {sites.map((site) => {
              const list = changesBySite(site);
              return (
                <div key={site}>
                  <p className="siteSplitHead">
                    <span className={`badge ${siteClass(site)}`}>{siteName(site)}</span>
                    <span style={{ fontSize: 11, color: "var(--sec)", fontWeight: 400 }}>{list.length}건</span>
                  </p>
                  {list.length === 0 ? (
                    <p className="muted">변경 없음</p>
                  ) : (
                    <div className="changeGrid">
                      {groupByUrl(list).map(({ url, items }) => (
                        <div key={url} className="urlChangeGroup">
                          <p className="urlChangeGroupHead" title={url}>{shortUrl(url)} <span>· {items.length}건</span></p>
                          {items.map((c, idx) => {
                            const isOpen = idx === 0 || selectedChange?.id === c.id;
                            return (
                              <div key={c.id} id={`change-${c.id}`}>
                                <button
                                  className={`changeCard ${selectedChange?.id === c.id ? "selected" : ""}`}
                                  onClick={() => setSelectedChange(selectedChange?.id === c.id ? null : c)}
                                >
                                  <div className="changeCardTop">
                                    <span className={`badge ${levelClass(c.level)}`}>{levelKo(c.level)}</span>
                                    <span style={{ fontSize: 11, color: "var(--sec)" }}>{c.category} · {c.field}</span>
                                  </div>
                                  <p className="changeSum">{c.summary || "변경 내용"}</p>
                                </button>
                                {isOpen && <ChangeDrilldown change={c} />}
                              </div>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

export function Overview({
  report, metricTab, dcv, changes, allChanges, selectedChange, setSelectedChange,
  urls, totalUrls, urlQuery, setUrlQuery, onOpenDrawer, onJumpToMetric,
}: {
  report: Report | null; metricTab: MetricView; dcv?: Report["dcv"];
  changes: Change[]; allChanges: Change[];
  selectedChange: Change | null; setSelectedChange: (c: Change | null) => void;
  urls: UrlRow[]; totalUrls: number; urlQuery: string; setUrlQuery: (s: string) => void;
  onOpenDrawer: (id: string) => void;
  onJumpToMetric: (m: MetricTab, change?: Change) => void;
}) {
  // 통계 범위: '전체요약'이면 전체 changes, DATA/COPY/VISUAL 탭이면 그 영역 changes만 집계
  const scopedChanges = metricTab === "all" ? allChanges : changes;
  const high = scopedChanges.filter((c) => c.level === "High").length;
  const samsung = scopedChanges.filter((c) => c.site === "samsung").length;
  const competitors = scopedChanges.length - samsung;
  // High가 없으면 그 다음으로 심각한 등급을 보여줌 (범위는 위 scopedChanges와 동일)
  const topSev = topSeverityChanges(scopedChanges, 3);
  const highChanges = topSev?.changes || [];
  const [urlFilter, setUrlFilter] = useState<string | null>(null);
  const displayedChanges = urlFilter ? changes.filter((c) => c.url === urlFilter) : changes;
  const expectedSites = orderedSiteKeys(urls.map((u) => u.site_key || ""));
  const boardDigest = buildDashboardDigest({ changes: scopedChanges, dcv, metricTab, expectedSites });

  // 상세보기 클릭 → 탭 이동 후, 해당 변경점 카드로 자동 스크롤
  useEffect(() => {
    if (!selectedChange) return;
    const el = document.getElementById(`change-${selectedChange.id}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [selectedChange, metricTab]);

  // URL 목록에서 특정 URL 클릭 → 그 URL의 변경점만 필터링 + 변경점목록으로 스크롤
  const filterByUrl = (url: string) => {
    setUrlFilter((prev) => (prev === url ? null : url));
    setTimeout(() => {
      document.getElementById("change-list-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  return (
    <div className="panelStack">
      {/* ① 전체 요약 카드 — 변화 N건 + High 변화 액션 제시 (탭 범위에 맞는 건수) */}
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">{report?.timestamp || "최근 수집 없음"}</p>
            <h1 className="summaryH1">
              {report ? boardDigest.headline : "수집 데이터 없음"}
            </h1>
            <p className="summaryDesc">
              {report
                ? (metricTab === "all"
                    ? `${boardDigest.lead} · 글로벌 경쟁사 변경 ${competitors}건 · Samsung 변경 ${samsung}건`
                    : `${METRICS[metricTab].label}: ${boardDigest.lead} · ${metricOneLiner(metricTab, dcv?.[metricTab], changes, expectedSites)}`)
                : "관리 URL을 추가하거나 수집을 실행하면 현황판이 표시됩니다."}
            </p>
          </div>
        </div>

        {/* High(또는 그 다음 등급) 변화 요약 + 액션 제시 — 클릭하면 해당 영역 탭으로 이동해 상세가 열림 */}
        {highChanges.length > 0 && topSev && (
          <div className="severityLegend">
            <p className="severityLegendTitle">
              {severityEmoji(topSev.level)} {levelKo(topSev.level)}({topSev.level}) 변화 — 우선 확인 필요 (클릭하면 상세로 이동)
              {topSev.level !== "High" && (
                <span style={{ color: "var(--sec)", fontWeight: 400 }}> · 이 범위엔 High 변화가 없어 가장 심각한 등급을 보여줍니다</span>
              )}
            </p>
            {highChanges.map((c) => (
              <button key={c.id} className="sevRow sevRowClickable" onClick={() => onJumpToMetric(bucketOf(c), c)}>
                <span className={`badge ${siteClass(c.site)}`}>{siteName(c.site)}</span>
                <span className="sevDesc">
                  <b>{c.summary || c.field}</b> — {shortUrl(c.url)}
                  <br />
                  <span style={{ color: "var(--sec)" }}>액션: {actionForChange(c)}</span>
                </span>
                <span className="sevRowGo">상세보기 →</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <WatchPointPanel
        changes={scopedChanges}
        dcv={dcv}
        metricTab={metricTab}
        expectedSites={expectedSites}
        onJumpToMetric={onJumpToMetric}
      />
      <InsightChat dcv={dcv} changes={scopedChanges} expectedSites={expectedSites} />

      {/* ①.5 가장 심각한 변화의 상세 근거 — 전체요약에서는 접은 상태로 보관해 요약 흐름을 방해하지 않음 */}
      {highChanges.length > 0 && topSev && (
        <details className="card summaryEvidenceCard">
          <summary className="summaryEvidenceSummary">
            상세 근거 — {severityEmoji(topSev.level)} {levelKo(topSev.level)} 최우선 변화
          </summary>
          <div className="summaryEvidenceBody">
            <ChangeDrilldown change={highChanges[0]} />
          </div>
        </details>
      )}

      {/* ② 전체요약이 아니면(특정 지표 탭) 분석기준→현황요약→변경점목록 풀 디테일.
             전체요약은 위 WatchPointPanel의 '축별 핵심 발견' + '전체 액션'으로 충분해 별도 요약을 넣지 않음 */}
      {metricTab !== "all" && (
        <MetricSection
          metric={metricTab}
          changes={displayedChanges}
          siteBlocks={dcv?.[metricTab] || {}}
          selectedChange={selectedChange}
          setSelectedChange={setSelectedChange}
          urlFilter={urlFilter}
          onClearUrlFilter={() => setUrlFilter(null)}
        />
      )}

      {/* URL 전체 목록 — 상세보기가 있는 DATA/COPY/VISUAL 탭에만 노출 (전체요약엔 없음) */}
      {metricTab !== "all" && (
      <div className="card">
        <p className="cardTitle">모니터링 URL 목록 ({totalUrls}개) — 관리 URL/페이지 역할 기준</p>
        <div className="urlSearchRow">
          <input
            className="urlSearch"
            value={urlQuery}
            onChange={(e) => setUrlQuery(e.target.value)}
            placeholder="URL 또는 사이트 검색"
          />
        </div>
        <div className="urlTableWrap">
          <div className="urlRow head">
            <span>Site</span><span>역할</span><span>URL</span><span />
          </div>
          {urls.map((u) => (
            <button
              key={(u.site_key || "") + u.url}
              className={`urlRow ${urlFilter === u.url ? "active" : ""}`}
              onClick={() => filterByUrl(u.url)}
            >
              <span className={`badge ${siteClass(u.site_key)}`} style={{ fontSize: 10 }}>
                {siteShortName(u.site_key)}
              </span>
              <span>{u.page_role || "-"}</span>
              <span className="urlRowUrl">{u.url}</span>
              <a href={u.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} title="실제 페이지 열기">↗</a>
            </button>
          ))}
        </div>
      </div>
      )}
    </div>
  );
}
