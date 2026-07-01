"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, Report, UrlRow, PageLite, PageDetail,
  CRITERIA, METRICS, TIER_META,
  siteName, siteClass, levelKo, levelClass, shortUrl, linesFromBlock, tierForUrl, tagForLine,
  metricAverage, metricOneLiner, bucketOf,
} from "./shared";

/* ════════════════════════════════════════════════════
   서브 컴포넌트 (이 파일 안에서만 사용)
════════════════════════════════════════════════════ */
function FindingList({ metric, lines }: { metric: MetricTab; lines: string[] }) {
  if (lines.length === 0) return <p className="muted">분석 데이터가 없습니다.</p>;
  return (
    <div>
      {lines.map((line, i) => {
        const tag = tagForLine(metric, line);
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

const EVIDENCE_LABELS: Record<string, string> = {
  kind: "종류", type: "스키마 타입", dom_hash_before: "이전 구조 해시", dom_hash_after: "이후 구조 해시",
  phash_before: "이전 이미지 해시", phash_after: "이후 이미지 해시", sentences_added: "추가된 문장",
};
const EVIDENCE_KIND_LABELS: Record<string, string> = {
  schema_added: "스키마 추가됨", schema_removed: "스키마 제거됨",
};

function ChangeDrilldown({ change: c }: { change: Change }) {
  const ev = c.evidence || {};
  const isDomHashOnly = "dom_hash_before" in ev && !("kind" in ev);
  const hasKindLabel = !!(ev.kind && EVIDENCE_KIND_LABELS[ev.kind as string]);
  return (
    <div className="drilldown">
      <h3>상세 근거</h3>
      <p>
        <b>페이지:</b>{" "}
        <a href={c.url} target="_blank" rel="noreferrer">{c.url}</a>
      </p>
      <p><b>분류:</b> {c.category || "-"} / {c.field || "-"}</p>
      {c.before && (
        <div className="diffBlock">
          <p className="diffLabel">이전</p>
          <p className="diffContent before">{c.before}</p>
        </div>
      )}
      {c.after && (
        <div className="diffBlock">
          <p className="diffLabel">현재</p>
          <p className="diffContent after">{c.after}</p>
        </div>
      )}
      {ev.kind && EVIDENCE_KIND_LABELS[ev.kind as string] && (
        <p style={{ marginTop: 8, fontSize: 12.5, fontWeight: 600 }}>
          {EVIDENCE_KIND_LABELS[ev.kind as string]}{ev.type ? ` — ${ev.type}` : ""}
        </p>
      )}
      {isDomHashOnly && (
        <p className="termDetail" style={{ marginTop: 8 }}>
          이 변화는 페이지 구조를 해시값으로만 비교해 감지했습니다. 값이 달라졌다는 것만 알 수 있고,
          구체적으로 어떤 요소가 추가·삭제·이동됐는지는 현재 저장돼 있지 않습니다.
          더 상세한 구조 diff가 필요하면 백엔드에 구조 비교 로직 보강이 필요합니다.
        </p>
      )}
      {Object.keys(ev).length > 0 && (
        <div className="evidenceGrid" style={{ marginTop: 8 }}>
          {Object.entries(ev)
            .filter(([k]) => !(hasKindLabel && (k === "kind" || k === "type")))
            .map(([k, v]) => (
              <>
                <span key={k + "_k"} className="evidenceKey">{EVIDENCE_LABELS[k] || k}</span>
                <span key={k + "_v"} className="evidenceVal">{Array.isArray(v) ? v.join(", ") : String(v)}</span>
              </>
            ))}
        </div>
      )}
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
              <FindingList metric={metric} lines={linesFromBlock(siteBlocks[site])} />
            </div>
          ))}
        </div>
      </div>

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
                      {list.map((c, idx) => {
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
                              <p className="changeUrl">{shortUrl(c.url)}</p>
                            </button>
                            {isOpen && <ChangeDrilldown change={c} />}
                          </div>
                        );
                      })}
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
  const high = allChanges.filter((c) => c.level === "High").length;
  const apple = allChanges.filter((c) => c.site === "apple").length;
  const samsung = allChanges.filter((c) => c.site === "samsung").length;
  // '전체요약' 탭이면 전체 기준 Top3, 특정 지표 탭이면 그 지표 안에서만 Top3 (탭마다 다른 항목이 보여야 함)
  const highSource = metricTab === "all" ? allChanges : changes;
  const highChanges = highSource.filter((c) => c.level === "High").slice(0, 3);
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
      {/* ① 전체 요약 카드 — 변화 N건 + High 변화 액션 제시 (항상 전체 기준, 탭과 무관) */}
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">{report?.timestamp || "최근 수집 없음"}</p>
            <h1 className="summaryH1">
              {report ? (allChanges.length > 0 ? `변화 ${allChanges.length}건 감지` : "변화 없음 — 현행 유지") : "수집 데이터 없음"}
            </h1>
            <p className="summaryDesc">
              {metricTab === "all"
                ? `Apple 변경 ${apple}건 · Samsung 변경 ${samsung}건 — 아래에서 DATA/COPY/VISUAL 영역별 요약을 확인하세요.`
                : metricOneLiner(metricTab, dcv?.[metricTab], changes)}
            </p>
          </div>
          <div className="statsRow">
            <Stat label="전체 변경" value={allChanges.length} />
            <Stat label="높음" value={high} tone="red" />
            <Stat label="Apple" value={apple} />
            <Stat label="Samsung" value={samsung} tone="blue" />
          </div>
        </div>

        {/* High 변화 요약 + 액션 제시 — 클릭하면 해당 영역 탭으로 이동해 상세가 열림 */}
        {highChanges.length > 0 && (
          <div className="severityLegend">
            <p className="severityLegendTitle">🔴 높음(High) 변화 — 우선 확인 필요 (클릭하면 상세로 이동)</p>
            {highChanges.map((c) => (
              <button key={c.id} className="sevRow sevRowClickable" onClick={() => onJumpToMetric(bucketOf(c), c)}>
                <span className={`badge ${siteClass(c.site)}`}>{siteName(c.site)}</span>
                <span className="sevDesc">
                  <b>{c.summary || c.field}</b> — {shortUrl(c.url)}
                  <br />
                  <span style={{ color: "var(--sec)" }}>액션: {c.site === "apple" ? "경쟁사 변화이므로 당사 대응 필요 여부 검토" : "당사 페이지 변경 — 의도된 변경인지 확인"}</span>
                </span>
                <span className="sevRowGo">상세보기 →</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ② '전체요약'이면 DATA/COPY/VISUAL 축약카드(클릭→해당 탭 상세로 이동, 정보 중복 없음)
             특정 지표 탭이면 분석기준→현황요약→변경점목록 풀 디테일 */}
      {metricTab === "all" ? (
        (["data", "copy", "visual"] as MetricTab[]).map((m) => {
          const mChanges = allChanges.filter((c) => bucketOf(c) === m);
          const mHigh = mChanges.filter((c) => c.level === "High").length;
          return (
            <button key={m} className="card metricSummaryCard" onClick={() => onJumpToMetric(m)}>
              <p className="cardTitle">
                <span className={`badge ${m === "data" ? "c1" : m === "copy" ? "c2" : "c4"}`}>{METRICS[m].label}</span>
                <span className="metricSummaryGo">자세히 보기 →</span>
              </p>
              <p className="metricSummaryLine">{metricOneLiner(m, dcv?.[m], mChanges)}</p>
              {mHigh > 0 && <p className="metricSummarySub">🔴 높음 변화 {mHigh}건 포함</p>}
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

  // Tier별 통계 + 간단 인사이트 (수집된 실제 값만 사용 — 지어내지 않음)
  const tierStats = (site: SiteKey) =>
    tierGroups(site).map(({ tier, pages: ps }) => {
      const avgWords = ps.length ? Math.round(ps.reduce((a, p) => a + (p.word_count || 0), 0) / ps.length) : 0;
      const thin = ps.filter((p) => (p.word_count || 0) < 150).length;
      return {
        tier, count: ps.length, avgWords, thin,
        insight: `${ps.length}개 페이지 · 평균 ${avgWords}단어${thin > 0 ? ` · 빈약 콘텐츠 ${thin}개` : ""}`,
      };
    });

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

  // 페이지 목록이 준비되면 대표 1개(첫 페이지)를 자동 선택해 상세 근거를 바로 펼쳐서 보여줌
  useEffect(() => {
    if (!selectedUrl && pageRows.length > 0) {
      onPick(pageRows[0].url);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageRows, selectedUrl]);

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

      {/* ② 분량 인사이트 — Tier별 평균 + 최다/최소/빈약 페이지 (관점이 겹쳐서 하나로 통합) */}
      <div className="card">
        <p className="cardTitle">분량 인사이트</p>
        <div className="siteSplit">
          {(["apple", "samsung"] as SiteKey[]).map((site) => (
            <div key={site}>
              <p className="siteSplitHead">
                <span className={`badge ${site}`}>{siteName(site)}</span>
              </p>
              {pageInsights(site).map((ins, i) => (
                <div className="findingRow" key={"pi" + i}>
                  <span className={`badge ${ins.cls}`}>{ins.label}</span>
                  <span className="findingText">{ins.text}</span>
                </div>
              ))}
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--line)" }}>
                {tierStats(site).map((s) => (
                  <div key={s.tier} className="tierStatRow">
                    <span className="tierStatLabel">{TIER_META[s.tier]?.label || `Tier ${s.tier}`}</span>
                    <span className="tierStatInsight">{s.insight}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ③ 페이지 목록 — Tier별로 그룹핑, 하단에 Tier 기준 설명 각주로 통합 */}
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
                    onClick={() => onPick(p.url)}
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

      {/* ④ 선택 페이지 상세 — 대표 1개가 자동 선택되어 기본적으로 펼쳐진 상태 (성격이 달라 별도 유지) */}
      <div className="card">
        <p className="cardTitle">
          선택 페이지 상세 근거 &nbsp;
          <button style={{ fontSize: 11, color: "var(--blue)", fontWeight: 400 }} onClick={() => onOpenDrawer()}>
            분석 기준 보기 ↗
          </button>
        </p>
        {loadingPage && <p className="muted">불러오는 중…</p>}
        {!loadingPage && !selectedPage && (
          <p className="muted">위 목록에서 페이지를 선택하면 DATA/COPY/VISUAL 상세 근거가 표시됩니다.</p>
        )}
        {!loadingPage && selectedPage && <PageDrilldown page={selectedPage} />}
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
