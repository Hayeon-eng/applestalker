"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, Report, UrlRow, PageLite, PageDetail,
  CRITERIA, METRICS, TIER_META,
  siteName, siteClass, levelKo, levelClass, severityEmoji, topSeverityChanges, groupByUrl,
  shortUrl, linesFromBlock, tierForUrl, tagForLine,
  metricAverage, metricOneLiner, bucketOf, actionForChange,
} from "./shared";
import { ChangeDrilldown, CurrentStatusDrilldown, type CurrentFindingSelection } from "./evidencePanels";

/* ════════════════════════════════════════════════════
   서브 컴포넌트 (이 파일 안에서만 사용)
════════════════════════════════════════════════════ */
function FindingList({
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
              <span className="findingText">{line}</span>
              <span className="findingGo">근거 ↓</span>
            </button>
          );
        }
        return (
          <div className="findingRow" key={i}>
            <span className={`badge ${tag.cls}`}>{tag.label}</span>
            <span className="findingText">{line}</span>
          </div>
        );
      })}
    </div>
  );
}

function AverageBox({
  title, site, data, metric,
}: {
  title: string; site: SiteKey; data: ReturnType<typeof metricAverage>; metric: MetricView;
}) {
  return (
    <div className="avgBox">
      <p className="avgBoxTitle">
        <span className="avgBoxSite" style={{ background: site === "samsung" ? "var(--samsung)" : "var(--apple)" }} />
        {title}
      </p>
      <div className="avgStat"><span>{data.pages}페이지 수집</span><span className="avgStatVal">{data.pages}</span></div>
      <div className="avgStat"><span>평균 단어 수</span><span className="avgStatVal">{data.avgWords}</span></div>
      {metric === "all" ? (
        <>
          <div className="avgStat"><span>Schema 적용률</span><span className="avgStatVal">{data.schema}</span></div>
          <div className="avgStat"><span>빈약 콘텐츠</span><span className="avgStatVal">{data.thin}</span></div>
          <div className="avgStat"><span>Lifestyle 이미지</span><span className="avgStatVal">{data.lifestyle}</span></div>
        </>
      ) : (
        <div className="avgStat">
          <span>{metric === "data" ? "Schema 적용률" : metric === "copy" ? "빈약 콘텐츠" : "Lifestyle 이미지"}</span>
          <span className="avgStatVal">{metric === "data" ? data.schema : metric === "copy" ? data.thin : data.lifestyle}</span>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "red" | "blue" }) {
  return (
    <div className={`stat ${tone || ""}`}>
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}


function PageDrilldown({ page }: { page: PageDetail }) {
  const sections: [MetricTab, any][] = [
    ["data", page.data], ["copy", page.copy], ["visual", page.visual],
  ];
  return (
    <div className="pageDetail">
      <p style={{ fontSize: 12, marginBottom: 8 }}>
        <b>URL:</b>{" "}
        <a href={page.url} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }}>{page.url}</a>
      </p>
      <p style={{ fontSize: 11, color: "var(--sec)", marginBottom: 12 }}>수집: {page.crawled_at || "-"}</p>
      {sections.map(([key, block]) => (
        <details key={key} style={{ marginBottom: 10 }}>
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
  );
}

/* ════════════════════════════════════════════════════
   홈 랜딩 페이지
════════════════════════════════════════════════════ */
export function Landing({ onEnter }: { onEnter: () => void }) {
  return (
    <div className="landingShell">
      <div className="landingInner">
        <span className="landingLogo">🍎</span>
        <h1 className="landingTitle">Apple Stalker</h1>
        <p className="landingSub">Samsung(당사) · Apple(경쟁사) 웹사이트 변화 감지 도구</p>

        <div className="landingCardGrid">
          <div className="landingCard">
            <p className="landingCardTitle">무엇을</p>
            <ul className="landingFactList">
              <li><b>대상</b> — Samsung 21개 URL / Apple 24개 URL (총 45개)</li>
              <li><b>항목</b> — 데이터·스키마 / 카피 / 가격·프로모션 / 비주얼</li>
              <li><b>주기</b> — 매일 09:00, 14:00 (KST) 자동 수집</li>
            </ul>
          </div>
          <div className="landingCard">
            <p className="landingCardTitle">어떻게</p>
            <ul className="landingFactList">
              <li><b>중요도</b> — High / Medium / Low 3단계</li>
              <li><b>비교 기준</b> — 실제 수집값만 사용, 추정치 없음</li>
              <li><b>출력</b> — 변경점 목록 + 현황 비교 + 이메일 리포트</li>
            </ul>
          </div>
        </div>

        <button className="landingCTA" onClick={onEnter}>현황 보기</button>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════
   Overview 탭 — 순서: ①변화N건+액션 ②분석기준 ③현황요약(Apple좌/Samsung우) ④변경점목록(Apple좌/Samsung우)
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

      {/* 현황 요약 — 변경 유무 관계없는 현재 상태 (Apple 좌 / Samsung 우) */}
      <div className="card">
        <p className="cardTitle">현황 요약 — {METRICS[metric].label} (변경 유무 무관, 현재 상태)</p>
        <div className="siteSplit">
          {(["apple", "samsung"] as SiteKey[]).map((site) => (
            <div key={site}>
              <p className="siteSplitHead">
                <span className={`badge ${site}`}>{siteName(site)}</span>
                {siteBlocks[site]?._source === "gemini" ? (
                  <span className="badge c2" title="Gemini가 근거 기반으로 서술 — evidence 없는 내용은 생성하지 않음">🤖 AI 분석 기반</span>
                ) : siteBlocks[site]?._source === "rule_based" ? (
                  <span className="badge c6" title="AI 분석 실패 또는 미설정 — 규칙기반 집계로 대체됨">📐 규칙기반 (AI 분석 실패)</span>
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

      {/* 변경점 목록 (Apple 좌 / Samsung 우) */}
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
          <p className="muted">이 영역에서 변경된 항목이 없습니다. 위 현황 요약에서 현재 상태를 확인하세요.</p>
        ) : (
          <div className="siteSplit">
            {(["apple", "samsung"] as SiteKey[]).map((site) => {
              const list = changesBySite(site);
              return (
                <div key={site}>
                  <p className="siteSplitHead">
                    <span className={`badge ${site}`}>{siteName(site)}</span>
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
  const apple = scopedChanges.filter((c) => c.site === "apple").length;
  const samsung = scopedChanges.filter((c) => c.site === "samsung").length;
  // High가 없으면 그 다음으로 심각한 등급을 보여줌 (범위는 위 scopedChanges와 동일)
  const topSev = topSeverityChanges(scopedChanges, 3);
  const highChanges = topSev?.changes || [];
  const [urlFilter, setUrlFilter] = useState<string | null>(null);
  const displayedChanges = urlFilter ? changes.filter((c) => c.url === urlFilter) : changes;

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
              {report
                ? (scopedChanges.length > 0
                    ? `${metricTab === "all" ? "전체" : METRICS[metricTab].label} 변화 ${scopedChanges.length}건 감지`
                    : "변화 없음 — 현행 유지")
                : "수집 데이터 없음"}
            </h1>
            <p className="summaryDesc">
              {metricTab === "all"
                ? `Apple 변경 ${apple}건 · Samsung 변경 ${samsung}건 — 아래에서 DATA/COPY/VISUAL 영역별 요약을 확인하세요.`
                : metricOneLiner(metricTab, dcv?.[metricTab], changes)}
            </p>
          </div>
          <div className="statsRow">
            <Stat label={metricTab === "all" ? "전체 변경" : `${METRICS[metricTab].label} 변경`} value={scopedChanges.length} />
            <Stat label="높음" value={high} tone="red" />
            <Stat label="Apple" value={apple} />
            <Stat label="Samsung" value={samsung} tone="blue" />
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

      {/* ② '전체요약'이면 DATA/COPY/VISUAL 축약카드(클릭→해당 탭 상세로 이동, 정보 중복 없음)
             특정 지표 탭이면 분석기준→현황요약→변경점목록 풀 디테일 */}
      {metricTab === "all" ? (
        (["data", "copy", "visual"] as MetricTab[]).map((m) => {
          const mChanges = allChanges.filter((c) => bucketOf(c) === m);
          const mTopSev = topSeverityChanges(mChanges, 0);
          const mHighCount = mChanges.filter((c) => c.level === "High").length;
          return (
            <button key={m} className="card metricSummaryCard" onClick={() => onJumpToMetric(m)}>
              <p className="cardTitle">
                <span className={`badge ${m === "data" ? "c1" : m === "copy" ? "c2" : "c4"}`}>{METRICS[m].label}</span>
                <span className="metricSummaryGo">자세히 보기 →</span>
              </p>
              <p className="metricSummaryLine">{metricOneLiner(m, dcv?.[m], mChanges)}</p>
              {mTopSev && (
                <p
                  className="metricSummarySub"
                  style={{ color: mTopSev.level === "High" ? "var(--high)" : mTopSev.level === "Medium" ? "var(--med)" : "var(--tier-good)" }}
                >
                  {severityEmoji(mTopSev.level)} {levelKo(mTopSev.level)} 변화 {mChanges.filter((c) => c.level === mTopSev.level).length}건
                  {mTopSev.level !== "High" && mHighCount === 0 && " (High 없음, 최고 심각도)"}
                </p>
              )}
            </button>
          );
        })
      ) : (
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
        <p className="cardTitle">모니터링 URL 목록 ({totalUrls}개) — 행 클릭 시 그 URL의 변경점만 필터링</p>
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
            <span>구분</span><span>Tier</span><span>URL</span><span />
          </div>
          {urls.map((u) => (
            <button
              key={(u.site_key || "") + u.url}
              className={`urlRow ${urlFilter === u.url ? "active" : ""}`}
              onClick={() => filterByUrl(u.url)}
            >
              <span className={`badge ${siteClass(u.site_key)}`} style={{ fontSize: 10 }}>
                {u.site_key === "apple" ? "Apple" : "Samsung"}
              </span>
              <span>{u.tier_level ?? "-"}</span>
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

/* ════════════════════════════════════════════════════
   Pages 탭 — Apple/Samsung 전체요약 + Tier(0~4)별 요약 + Tier 기준 설명
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
  const pageRows = useMemo(
    () => [
      ...pages.apple.map((p) => ({ ...p, site: "apple" as SiteKey })),
      ...pages.samsung.map((p) => ({ ...p, site: "samsung" as SiteKey })),
    ],
    [pages]
  );

  // URL → tier 매핑: /api/urls 가 계산해둔 tier_level(0~4, 백엔드 config.py::tier_for_url) 을 1차로 사용
  const tierMap = useMemo(() => {
    const m: Record<string, number> = {};
    urls.forEach((u) => { if (u.tier_level != null) m[u.url] = u.tier_level; });
    return m;
  }, [urls]);
  const tierOf = (url: string) => tierMap[url] ?? tierForUrl(url);

  const tierGroups = (site: SiteKey) => {
    const groups: Record<number, PageLite[]> = {};
    pages[site].forEach((p) => {
      const t = tierOf(p.url);
      (groups[t] = groups[t] || []).push(p);
    });
    return Object.entries(groups)
      .map(([t, ps]) => ({ tier: Number(t), pages: ps }))
      .sort((a, b) => a.tier - b.tier);
  };

  // Apple/Samsung 요약 통계 — '전체'면 DATA·COPY·VISUAL 세 지표를 각각의 facts에서 모아 병합
  const avgFor = (site: SiteKey): ReturnType<typeof metricAverage> => {
    if (metricTab === "all") {
      const d = metricAverage(pages[site], dcv?.data?.[site]);
      const c = metricAverage(pages[site], dcv?.copy?.[site]);
      const v = metricAverage(pages[site], dcv?.visual?.[site]);
      return { pages: d.pages, avgWords: d.avgWords, schema: d.schema, thin: c.thin, lifestyle: v.lifestyle };
    }
    return metricAverage(pages[site], dcv?.[metricTab]?.[site]);
  };
  const avgApple = avgFor("apple");
  const avgSamsung = avgFor("samsung");

  // 페이지별 분석 탭 고유의 인사이트 — Overview의 '현황요약' 문장과 겹치지 않게,
  // 이 탭에서만 볼 수 있는 '페이지 단위' 관점(분량 최다/최소, 빈약 콘텐츠 목록)으로 구성
  const pageInsights = (site: SiteKey) => {
    const list = pages[site];
    if (list.length === 0) return [];
    const sorted = [...list].sort((a, b) => (b.word_count || 0) - (a.word_count || 0));
    const longest = sorted[0];
    const shortest = sorted[sorted.length - 1];
    const thin = list.filter((p) => (p.word_count || 0) < 150);
    const out = [
      { label: "최다 분량", cls: "c2", text: `${longest.title || shortUrl(longest.url)} — ${longest.word_count || 0}단어` },
      { label: "최소 분량", cls: "c5", text: `${shortest.title || shortUrl(shortest.url)} — ${shortest.word_count || 0}단어` },
    ];
    if (thin.length > 0) {
      out.push({
        label: "빈약 콘텐츠", cls: "c3",
        text: `${thin.length}개 (150단어 미만) — ${thin.slice(0, 3).map((p) => p.title || shortUrl(p.url)).join(", ")}${thin.length > 3 ? " 등" : ""}`,
      });
    }
    return out;
  };

  // 대표 페이지 선정: ①이 탭에서 High 변화가 있던 페이지 > ②변화가 있던 페이지 > ③첫 페이지(변화 자체가 없을 때)
  const representative = useMemo(() => {
    const pool = metricTab === "all" ? allChanges : allChanges.filter((c) => bucketOf(c) === metricTab);
    const high = pool.find((c) => c.level === "High");
    if (high) return { url: high.url, reason: "이 영역에서 가장 심각한(High) 변화가 있던 페이지" };
    if (pool[0]) return { url: pool[0].url, reason: "이 영역에서 변화가 감지된 페이지" };
    if (pageRows[0]) return { url: pageRows[0].url, reason: "변화가 없어 첫 페이지를 표시" };
    return null;
  }, [metricTab, allChanges, pageRows]);

  // 사용자가 직접 페이지를 클릭하면 자동 추천을 멈추고 그 선택을 존중
  const [autoMode, setAutoMode] = useState(true);
  const pick = (url: string) => { setAutoMode(false); onPick(url); };

  useEffect(() => {
    if (autoMode && representative && representative.url !== selectedUrl) {
      onPick(representative.url);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [representative, autoMode]);

  return (
    <div className="panelStack">
      {/* ① 요약 카드 — 제목 + 지표별 한줄 인사이트 + Apple/Samsung 통계 (하나로 통합) */}
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">페이지별 현재 상태</p>
            <h1 className="summaryH1">
              {metricTab === "all" ? "전체요약" : METRICS[metricTab].label} — Apple / Samsung
            </h1>
            <p className="summaryDesc">
              {metricTab === "all"
                ? "DATA·COPY·VISUAL 세 지표를 모두 모은 전체 통계입니다. 자세한 근거는 아래 지표 탭에서 확인하세요."
                : METRICS[metricTab].plain}
            </p>
          </div>
        </div>

        {/* '전체'면 DATA/COPY/VISUAL 각각의 한줄 인사이트, 특정 지표면 그 지표 한줄만 */}
        <div className="severityLegend">
          {(metricTab === "all" ? (["data", "copy", "visual"] as MetricTab[]) : [metricTab]).map((m) => (
            <div key={m} className="sevRow">
              <span className={`badge ${m === "data" ? "c1" : m === "copy" ? "c2" : "c4"}`}>{METRICS[m].label}</span>
              <span className="sevDesc">
                {metricOneLiner(m, dcv?.[m], allChanges.filter((c) => bucketOf(c) === m))}
              </span>
            </div>
          ))}
        </div>

        <div className="avgGrid" style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
          <AverageBox title="Apple 경쟁사" site="apple" data={avgApple} metric={metricTab} />
          <AverageBox title="Samsung 당사" site="samsung" data={avgSamsung} metric={metricTab} />
        </div>
      </div>

      {/* ② 대표 페이지 상세 근거 — '핵심 인사이트'(요약) + '선택 페이지 상세 근거'(전체)를 하나로 합쳐 상단에 배치 (중복 제거) */}
      <div className="card">
        <p className="cardTitle">
          대표 페이지 상세 근거 — {selectedPage ? shortUrl(selectedPage.url) : ""} &nbsp;
          <button style={{ fontSize: 11, color: "var(--blue)", fontWeight: 400 }} onClick={() => onOpenDrawer()}>
            분석 기준 보기 ↗
          </button>
        </p>
        {representative && (
          <p className="muted" style={{ marginTop: -6, marginBottom: 10 }}>
            선정 이유: {representative.reason}{!autoMode && " (수동 선택됨 — 다른 페이지를 골랐습니다)"}
          </p>
        )}
        {loadingPage && <p className="muted">불러오는 중…</p>}
        {!loadingPage && !selectedPage && (
          <p className="muted">위 목록에서 페이지를 선택하면 DATA/COPY/VISUAL 상세 근거가 표시됩니다.</p>
        )}
        {!loadingPage && selectedPage && <PageDrilldown page={selectedPage} />}
      </div>

      {/* ③ 분량 인사이트 — 사이트별 한 줄로 간략하게 */}
      <div className="card">
        <p className="cardTitle">분량 인사이트 (요약)</p>
        <div className="siteSplit">
          {(["apple", "samsung"] as SiteKey[]).map((site) => {
            const ins = pageInsights(site);
            return (
              <div key={site}>
                <p className="siteSplitHead">
                  <span className={`badge ${site}`}>{siteName(site)}</span>
                </p>
                <p className="findingText" style={{ fontSize: 12 }}>
                  {ins.map((x) => `${x.label} ${x.text}`).join(" · ")}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* ④ 페이지 목록 — Tier별로 그룹핑, 하단에 Tier 기준 설명 각주로 통합 */}
      <div className="card">
        <p className="cardTitle">페이지별 목록 ({pageRows.length}개) — Tier별 그룹</p>
        {[0, 1, 2, 3, 4].map((tier) => {
          const rows = pageRows.filter((p) => tierOf(p.url) === tier);
          if (rows.length === 0) return null;
          return (
            <div key={tier} style={{ marginBottom: 14 }}>
              <p className="tierRowHead" style={{ marginBottom: 4 }}>
                {TIER_META[tier]?.label || `Tier ${tier}`}
                <span className="tierRowDesc">{TIER_META[tier]?.desc} · {rows.length}개</span>
              </p>
              <div className="pageTable">
                <div className="pageRow head">
                  <span>구분</span><span>Tier</span><span>단어 수</span><span>페이지</span>
                </div>
                {rows.map((p) => (
                  <button
                    key={p.url}
                    className={`pageRow ${selectedUrl === p.url ? "selected" : ""}`}
                    onClick={() => pick(p.url)}
                  >
                    <span>
                      <span className={`badge ${p.site}`} style={{ fontSize: 10 }}>
                        {p.site === "samsung" ? "Samsung" : "Apple"}
                      </span>
                    </span>
                    <span>Tier {tier}</span>
                    <span>{p.word_count || 0}</span>
                    <span>
                      {p.title || shortUrl(p.url)}
                      <small>{shortUrl(p.url)}</small>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
        <details style={{ marginTop: 4 }}>
          <summary style={{ fontSize: 11.5, color: "var(--blue)", fontWeight: 600, cursor: "pointer" }}>
            Tier 기준 설명 보기
          </summary>
          <div style={{ marginTop: 8 }}>
            {Object.entries(TIER_META).map(([t, meta]) => (
              <div key={t} className="catLine">
                <p className="catLineHead" style={{ fontSize: 12 }}>{meta.label}</p>
                <p className="catLineBody">{meta.desc}</p>
              </div>
            ))}
          </div>
        </details>
      </div>
    </div>
  );
}

/* ── 기준 설명 Drawer (슬라이드인, 콘텐츠 위에 겹치지 않고 레이아웃 밀어냄) */
export function CriteriaDrawer({
  open, section, onClose,
}: {
  open: boolean; section: string | null; onClose: () => void;
}) {
  const target = section ? CRITERIA.find((c) => c.id === section) : null;
  const list = target ? [target] : CRITERIA;
  const [openTerms, setOpenTerms] = useState<Set<string>>(new Set());
  const toggleTerm = (key: string) =>
    setOpenTerms((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  return (
    <>
      {/* 오버레이 */}
      {open && (
        <div
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.18)", zIndex: 30 }}
          onClick={onClose}
        />
      )}
      {/* Drawer */}
      <div
        style={{
          position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 31,
          width: "var(--drawer-w)", background: "var(--surface)",
          boxShadow: "-4px 0 24px rgba(0,0,0,.12)",
          transform: open ? "translateX(0)" : "translateX(100%)",
          transition: "transform .25s",
          display: "flex", flexDirection: "column",
        }}
      >
        <div className="drawerHead">
          <span className="drawerTitle">분석 기준 설명</span>
          <button className="drawerClose" onClick={onClose}>×</button>
        </div>
        <div className="drawerBody" style={{ overflowY: "auto", flex: 1 }}>
          {list.map((sec) => (
            <div key={sec.id} className="drawerSection">
              <p className="drawerSectionTitle">{sec.title}</p>
              {sec.note && <p className="termDetail" style={{ marginBottom: 10 }}>{sec.note}</p>}
              {sec.items.map((item) => {
                const key = sec.id + "::" + item.q;
                const isOpen = openTerms.has(key);
                return (
                  <div key={item.q} className="drawerItem">
                    <p className="drawerItemQ">
                      {item.q}
                      {item.scoring === "weighted" && (
                        <span className="badge c2" style={{ marginLeft: 6 }}>⚖️ 가중합산</span>
                      )}
                      {item.detail && (
                        <button className="termToggle" onClick={() => toggleTerm(key)}>
                          {isOpen ? "▾ 용어 설명 접기" : "❓ 용어 설명"}
                        </button>
                      )}
                    </p>
                    <p className="drawerItemA">{item.a}</p>
                    {item.detail && isOpen && <p className="termDetail">{item.detail}</p>}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
