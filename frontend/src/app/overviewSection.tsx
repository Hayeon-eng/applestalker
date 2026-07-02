"use client";

import { useEffect, useState } from "react";
import {
  MetricTab, MetricView, SiteKey, Change, AnalysisBlock, Report, UrlRow,
  METRICS,
  orderedSiteKeys, siteName, siteShortName, siteClass, levelKo, levelClass, severityEmoji, topSeverityChanges, groupByUrl,
  shortUrl, linesFromBlock, tagForLine,
  metricOneLiner, bucketOf, actionForChange, pageRoleFromUrl, pageRoleKo, pageRoleFromText,
} from "./shared";
import { ChangeDrilldown, CurrentStatusDrilldown, type CurrentFindingSelection } from "./evidencePanels";

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

function Stat({ label, value, tone }: { label: string; value: number; tone?: "red" | "blue" }) {
  return (
    <div className={`stat ${tone || ""}`}>
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}


const firstNarrativeLine = (block?: AnalysisBlock) => linesFromBlock(block).find(Boolean) || "수집 근거 부족";
const siteMetricSummary = (site: SiteKey, metric: MetricTab, block?: AnalysisBlock, siteChanges: Change[] = []) => {
  const changesText = siteChanges.length ? `변경 ${siteChanges.length}건` : "변경 없음";
  if (!block) return `${changesText} · 아직 수집된 ${METRICS[metric].label} 근거가 부족합니다.`;
  const f: any = block.facts || {};
  if (metric === "data") {
    return `${changesText} · Schema 적용률 ${f.schema?.coverage_pct ?? "-"}% · ${firstNarrativeLine(block)}`;
  }
  if (metric === "copy") {
    const pages = f.copy_richness?.all_pages || [];
    const avg = pages.length ? Math.round(pages.reduce((sum: number, x: any) => sum + (Number(x?.score) || 0), 0) / pages.length) : "-";
    return `${changesText} · 카피 구체성 평균 ${avg}점 · ${firstNarrativeLine(block)}`;
  }
  return `${changesText} · Lifestyle 이미지 신호 ${f.image_diversity?.lifestyle_ratio_pct ?? "-"}% · ${firstNarrativeLine(block)}`;
};
const compactSummary = (text: string, max = 190) => text.length > max ? text.slice(0, max - 1) + "…" : text;
const siteMatchesQuery = (site: SiteKey, raw: string) => {
  const hay = [site, siteName(site), siteShortName(site)].join(" ").toLowerCase();
  return hay.split(/\s+/).some((x) => x && raw.includes(x)) || raw.includes(site.replace(/_/g, " "));
};

const sitesFromBlocks = (siteBlocks?: Record<string, AnalysisBlock>, changes: Change[] = []) =>
  orderedSiteKeys([...(siteBlocks ? Object.keys(siteBlocks) : []), ...changes.map((c) => c.site || "")]);

function WatchPointPanel({ changes, dcv, metricTab }: { changes: Change[]; dcv?: Report["dcv"]; metricTab: MetricView }) {
  const scopedMetrics = metricTab === "all" ? (["data", "copy", "visual"] as MetricTab[]) : [metricTab];
  const allSites = orderedSiteKeys([
    ...scopedMetrics.flatMap((m) => Object.keys(dcv?.[m] || {})),
    ...changes.map((c) => c.site || ""),
  ]);
  const changedSites = new Set(changes.map((c) => c.site).filter(Boolean));
  const topChanges = changes.slice(0, 5);
  return (
    <div className="card watchPointCard">
      <p className="cardTitle">Overview</p>
      <p className="overviewLead">
        {changes.length > 0
          ? `이번 수집에서 ${changes.length}건의 변경이 잡혔습니다. 아래는 사이트별로 무엇이 바뀌었고, 삼성 입장에서 왜 봐야 하는지 정리한 요약입니다.`
          : "이번 수집에서는 변경점이 없습니다. 대신 현재 각 사이트가 어떤 구조·카피·비주얼 전략을 쓰는지 기준선을 요약합니다."}
      </p>
      {topChanges.length > 0 && (
        <div className="overviewChangeList">
          {topChanges.map((c) => (
            <div key={c.id} className="overviewChangeItem">
              <span className={`badge ${siteClass(c.site)}`}>{siteName(c.site)}</span>
              <span className={`sevBadge ${levelClass(c.level)}`}>{levelKo(c.level)}</span>
              <p>{c.summary || c.field}<small>{shortUrl(c.url)} · 삼성 액션: {actionForChange(c)}</small></p>
            </div>
          ))}
        </div>
      )}
      <div className="overviewSiteGrid">
        {allSites.length === 0 ? <p className="muted">수집 데이터가 쌓이면 사이트별 Overview가 표시됩니다.</p> : allSites.map((site) => {
          const siteChanges = changes.filter((c) => c.site === site);
          const summary = scopedMetrics.map((m) => siteMetricSummary(site, m, dcv?.[m]?.[site], siteChanges.filter((c) => bucketOf(c) === m)));
          return (
            <div key={site} className="overviewSiteCard">
              <div className="overviewSiteHead">
                <span className={`badge ${siteClass(site)}`}>{siteName(site)}</span>
                <span className={siteChanges.length ? "changeState changed" : "changeState stable"}>{siteChanges.length ? `변경 ${siteChanges.length}건` : "변경 없음"}</span>
              </div>
              <ul>
                {summary.map((x, i) => <li key={i}>{compactSummary(x)}</li>)}
              </ul>
              <p className="overviewAction">
                {siteChanges.length
                  ? `예의주시: ${compactSummary(actionForChange(siteChanges[0]), 100)}`
                  : "예의주시: 변경은 없지만 현재 구조가 기준선입니다. 다음 수집에서 카피/CTA/Schema가 이탈하는지 확인하세요."}
              </p>
            </div>
          );
        })}
      </div>
      {changedSites.size === 0 && (
        <p className="overviewFootnote">변경이 없을 때도 이 Overview는 무의미하지 않습니다. 각 사이트의 현재 Schema 적용률, 카피 구체성, alt/src 기반 visual tactic이 다음 주 변화 감지의 baseline으로 쓰입니다.</p>
      )}
    </div>
  );
}

function InsightChat({ dcv, changes }: { dcv?: Report["dcv"]; changes: Change[] }) {
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
    const allMetricSites = orderedSiteKeys(Object.keys(dcv?.[metric] || {}));
    const site = allMetricSites.find((s) => siteMatchesQuery(s, raw)) || orderedSiteKeys(changes.map((c) => c.site || "")).find((s) => siteMatchesQuery(s, raw));
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
      setAnswer("조건에 맞는 변경점은 없습니다. 변경이 없는 사이트는 현재 상태를 baseline으로 두고, 다음 수집에서 Schema/CTA/카피/alt.copy가 달라지는지 확인하면 됩니다.");
      return;
    }

    if (/삼성|samsung|예의주시|watch|action/.test(raw)) {
      if (changes.length) {
        setAnswer(changes.slice(0, 5).map((c) => `- ${siteName(c.site)} ${levelKo(c.level)}: ${c.summary || c.field}\n  → 삼성 액션: ${actionForChange(c)}`).join("\n"));
        return;
      }
      setAnswer("이번 수집에서는 변경점이 없습니다. 예의주시 포인트는 ① 경쟁사의 Product/FAQ schema 변화 ② PF/PDP/Buying CTA 위치 변화 ③ hero copy의 톤 변화 ④ alt.copy 보강 여부입니다.");
      return;
    }

    if (/pf|pdp|buying|구매|약해/.test(raw)) {
      const blocks = dcv?.copy || {};
      const lines = orderedSiteKeys(Object.keys(blocks)).map((s) => {
        const f: any = blocks[s]?.facts || {};
        const roleLen = f.role_copy_length?.summary || f.content_density?.density_buckets || {};
        const line = firstNarrativeLine(blocks[s]);
        return `- ${siteName(s)}: ${compactSummary(JSON.stringify(roleLen), 90)} · ${compactSummary(line, 120)}`;
      });
      setAnswer(lines.length ? lines.join("\n") : "PF/PDP/Buying 역할별 copy 근거가 아직 부족합니다.");
      return;
    }

    const targetSites = site ? [site] : allMetricSites;
    const answers = targetSites.slice(0, 5).map((s) => {
      const block = dcv?.[metric]?.[s];
      const siteChanges = changes.filter((c) => bucketOf(c) === metric && c.site === s && (!role || pageRoleFromUrl(c.url) === role));
      const roleText = role ? `${pageRoleKo(role)} ` : "";
      if (siteChanges.length) {
        return `- ${siteName(s)} ${roleText}${METRICS[metric].label} 변경: ${siteChanges.slice(0, 2).map((c) => `${c.summary || c.field} (${shortUrl(c.url)})`).join(" / ")}`;
      }
      return `- ${siteName(s)} ${roleText}${METRICS[metric].label}: 변경점 없음. 현재 근거: ${compactSummary(firstNarrativeLine(block), 180)}`;
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
          <p className="muted">현재 수집된 facts/changes 안에서만 rule-based로 답합니다.</p>
        </div>
      )}
    </div>
  );
}

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
          <p className="muted">이 영역에서 변경된 항목이 없습니다. 위 현재 상태 요약을 baseline으로 확인하세요.</p>
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
                ? `글로벌 경쟁사 변경 ${competitors}건 · Samsung 변경 ${samsung}건 — 아래에서 DATA/COPY/VISUAL 영역별 요약을 확인하세요.`
                : metricOneLiner(metricTab, dcv?.[metricTab], changes)}
            </p>
          </div>
          <div className="statsRow">
            <Stat label={metricTab === "all" ? "전체 변경" : `${METRICS[metricTab].label} 변경`} value={scopedChanges.length} />
            <Stat label="높음" value={high} tone="red" />
            <Stat label="경쟁사" value={competitors} />
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

      <WatchPointPanel changes={scopedChanges} dcv={dcv} metricTab={metricTab} />
      <InsightChat dcv={dcv} changes={scopedChanges} />

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
                {siteShortName(u.site_key)}
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
