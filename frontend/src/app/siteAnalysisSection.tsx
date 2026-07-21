"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MetricTab, MetricView, SiteKey, Change, Report, UrlRow, PageLite, PageDetail,
  METRICS, TIER_META,
  orderedSiteKeys, siteName, siteShortName, siteClass,
  shortUrl, linesFromBlock, tagForLine, tierForUrl, metricAverage, metricOneLiner, bucketOf,
} from "./shared";

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
        <span className="avgBoxSite" style={{ background: site === "samsung" ? "var(--samsung)" : site === "apple" ? "var(--apple)" : "var(--competitor)" }} />
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

function WireframePanel({ page }: { page: PageDetail }) {
  const wf = page.wireframe;
  if (!wf) return <p className="muted">Wireframe 데이터가 없습니다.</p>;
  const h2 = wf.h2 || [];
  const h3 = wf.h3 || [];
  const ctas = wf.ctas || [];
  return (
    <div className="wireframeCard">
      <div className="wfHeader">
        <span className="badge c1">{wf.page_role || "page"}</span>
        <span>{wf.word_count || 0} words</span>
      </div>
      <div className="wfBlock hero">
        <b>{wf.h1 || wf.title || "KV / H1 없음"}</b>
        <small>KV · Title/H1</small>
      </div>
      <div className="wfMiniGrid">
        {h2.slice(0, 5).map((x, i) => <div key={i} className="wfBlock"><b>{x}</b><small>H2 section</small></div>)}
        {h2.length === 0 && <div className="wfBlock"><b>H2 없음</b><small>section 구조 점검</small></div>}
      </div>
      {h3.length > 0 && (
        <details style={{ marginTop: 6 }}>
          <summary style={{ fontSize: 11.5, color: "var(--sec)", cursor: "pointer" }}>H3 {h3.length}개 보기</summary>
          <div className="wfMiniGrid" style={{ marginTop: 6 }}>
            {h3.map((x, i) => <div key={i} className="wfBlock"><b>{x}</b><small>H3</small></div>)}
          </div>
        </details>
      )}
      <div className="wfPills">
        {ctas.slice(0, 6).map((x, i) => <span key={i}>{x?.text || "CTA"}</span>)}
        {ctas.length === 0 && <span>CTA 없음</span>}
      </div>
      <div className="wfMetricGrid">
        <div><b>{wf.image_count || 0}</b><span>Images</span></div>
        <div><b>{wf.faq_count || 0}</b><span>FAQ</span></div>
        <div><b>{h3.length}</b><span>H3</span></div>
        <div><b>{(wf.schema_types || []).length}</b><span>Schema</span></div>
      </div>
      <p className="wfSchema">{(wf.schema_types || []).slice(0, 8).join(" · ") || "Schema 없음"}</p>
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
      <div className="pageEvidenceGrid">
        <WireframePanel page={page} />
        <div className="pageDcvStack">
          {sections.map(([key, block]) => (
            <details key={key} style={{ marginBottom: 10 }} open={key === "data"}>
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
      </div>
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
  const siteKeys = useMemo(() => orderedSiteKeys(Object.keys(pages)), [pages]);
  const [selectedSite, setSelectedSite] = useState<SiteKey | "all">("all");
  const visibleSiteKeys = useMemo(
    () => selectedSite === "all" ? siteKeys : siteKeys.filter((s) => s === selectedSite),
    [siteKeys, selectedSite]
  );
  const pageRows = useMemo(
    () => visibleSiteKeys.flatMap((site) => (pages[site] || []).map((p) => ({ ...p, site }))),
    [pages, visibleSiteKeys]
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
    (pages[site] || []).forEach((p) => {
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
      const sitePages = pages[site] || [];
      const d = metricAverage(sitePages, dcv?.data?.[site]);
      const c = metricAverage(sitePages, dcv?.copy?.[site]);
      const v = metricAverage(sitePages, dcv?.visual?.[site]);
      return { pages: d.pages, avgWords: d.avgWords, schema: d.schema, thin: c.thin, lifestyle: v.lifestyle };
    }
    return metricAverage(pages[site] || [], dcv?.[metricTab]?.[site]);
  };

  // 페이지별 분석 탭 고유의 인사이트 — Overview의 '현황요약' 문장과 겹치지 않게,
  // 이 탭에서만 볼 수 있는 '페이지 단위' 관점(분량 최다/최소, 빈약 콘텐츠 목록)으로 구성
  const pageInsights = (site: SiteKey) => {
    const list = pages[site] || [];
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
            <p className="summaryEyebrow">Site별 분석</p>
            <h1 className="summaryH1">
              {metricTab === "all" ? "전체요약" : METRICS[metricTab].label} — Site별 deep dive
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

        <div className="siteFilterRow">
          <button className={selectedSite === "all" ? "on" : ""} onClick={() => setSelectedSite("all")}>전체 Site</button>
          {siteKeys.map((site) => (
            <button key={site} className={selectedSite === site ? "on" : ""} onClick={() => setSelectedSite(site)}>
              {siteName(site)}
            </button>
          ))}
        </div>

        <div className="avgGrid" style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
          {visibleSiteKeys.map((site) => (
            <AverageBox key={site} title={siteName(site)} site={site} data={avgFor(site)} metric={metricTab} />
          ))}
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
        <p className="cardTitle">Site별 분량/콘텐츠 인사이트</p>
        <div className="siteSplit">
          {visibleSiteKeys.map((site) => {
            const ins = pageInsights(site);
            return (
              <div key={site}>
                <p className="siteSplitHead">
                  <span className={`badge ${siteClass(site)}`}>{siteName(site)}</span>
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
        <p className="cardTitle">Site별 분석 — 페이지 목록 ({pageRows.length}개) · PF/PDP/Buying 딥다이브</p>
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
                      <span className={`badge ${siteClass(p.site)}`} style={{ fontSize: 10 }}>
                        {siteShortName(p.site)}
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
