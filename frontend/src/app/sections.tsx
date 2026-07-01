"use client";

import { useMemo, useState } from "react";
import {
  MetricTab, SiteKey, Change, AnalysisBlock, Report, UrlRow, PageLite, PageDetail,
  CRITERIA, METRICS, TIER_META,
  siteName, siteClass, levelKo, levelClass, shortUrl, linesFromBlock, tierForUrl, tagForLine, metricAverage,
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
  title: string; site: SiteKey; data: ReturnType<typeof metricAverage>; metric: MetricTab;
}) {
  const mv = metric === "data" ? data.schema : metric === "copy" ? data.thin : data.lifestyle;
  const ml = metric === "data" ? "Schema 적용률" : metric === "copy" ? "빈약 콘텐츠" : "Lifestyle 이미지";
  return (
    <div className="avgBox">
      <p className="avgBoxTitle">
        <span className="avgBoxSite" style={{ background: site === "samsung" ? "var(--samsung)" : "var(--apple)" }} />
        {title}
      </p>
      <div className="avgStat"><span>{data.pages}페이지 수집</span><span className="avgStatVal">{data.pages}</span></div>
      <div className="avgStat"><span>평균 단어 수</span><span className="avgStatVal">{data.avgWords}</span></div>
      <div className="avgStat"><span>{ml}</span><span className="avgStatVal">{mv}</span></div>
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

function ChangeDrilldown({ change: c }: { change: Change }) {
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
      {c.evidence && Object.keys(c.evidence).length > 0 && (
        <div className="evidenceGrid" style={{ marginTop: 8 }}>
          {Object.entries(c.evidence).map(([k, v]) => (
            <>
              <span key={k + "_k"} className="evidenceKey">{k}</span>
              <span key={k + "_v"} className="evidenceVal">{String(v)}</span>
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
export function Overview({
  report, metricTab, changes, allChanges, selectedChange, setSelectedChange,
  siteBlocks, urls, totalUrls, urlQuery, setUrlQuery, onOpenDrawer,
}: {
  report: Report | null; metricTab: MetricTab; changes: Change[]; allChanges: Change[];
  selectedChange: Change | null; setSelectedChange: (c: Change | null) => void;
  siteBlocks: Record<string, AnalysisBlock>;
  urls: UrlRow[]; totalUrls: number; urlQuery: string; setUrlQuery: (s: string) => void;
  onOpenDrawer: (id: string) => void;
}) {
  const high = allChanges.filter((c) => c.level === "High").length;
  const apple = allChanges.filter((c) => c.site === "apple").length;
  const samsung = allChanges.filter((c) => c.site === "samsung").length;
  const highChanges = allChanges.filter((c) => c.level === "High").slice(0, 3);
  const changesBySite = (site: SiteKey) => changes.filter((c) => c.site === site);

  return (
    <div className="panelStack">
      {/* ① 전체 요약 카드 — 변화 N건 + High 변화 액션 제시 */}
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">{report?.timestamp || "최근 수집 없음"}</p>
            <h1 className="summaryH1">
              {report ? (allChanges.length > 0 ? `변화 ${allChanges.length}건 감지` : "변화 없음 — 현행 유지") : "수집 데이터 없음"}
            </h1>
            <p className="summaryDesc">
              {report?.analysis?.summary || METRICS[metricTab].plain}
            </p>
          </div>
          <div className="statsRow">
            <Stat label="전체 변경" value={allChanges.length} />
            <Stat label="높음" value={high} tone="red" />
            <Stat label="Apple" value={apple} />
            <Stat label="Samsung" value={samsung} tone="blue" />
          </div>
        </div>

        {/* High 변화 요약 + 액션 제시 */}
        {highChanges.length > 0 && (
          <div className="severityLegend">
            <p className="severityLegendTitle">🔴 높음(High) 변화 — 우선 확인 필요</p>
            {highChanges.map((c) => (
              <div key={c.id} className="sevRow">
                <span className={`badge ${siteClass(c.site)}`}>{siteName(c.site)}</span>
                <span className="sevDesc">
                  <b>{c.summary || c.field}</b> — {shortUrl(c.url)}
                  <br />
                  <span style={{ color: "var(--sec)" }}>액션: {c.site === "apple" ? "경쟁사 변화이므로 당사 대응 필요 여부 검토" : "당사 페이지 변경 — 의도된 변경인지 확인"}</span>
                </span>
              </div>
            ))}
          </div>
        )}

        {/* SEVERITY 범례 */}
        <div className="severityLegend">
          <p className="severityLegendTitle">
            중요도 기준 &nbsp;
            <button style={{ fontSize: 11, color: "var(--blue)" }} onClick={() => onOpenDrawer("severity")}>
              자세히 ↗
            </button>
          </p>
          {[
            ["high", "높음", "Schema·DOM·가격·여러 섹션 동시 변화. AI 검색 노출에 직접 영향"],
            ["med", "보통", "문장·슬로건·메뉴·meta·FAQ 변화. 의미 해석에 영향"],
            ["low", "낮음", "단어 몇 개·오타·작은 이미지 변화. 영향 제한적"],
          ].map(([cls, label, desc]) => (
            <div key={cls} className="sevRow">
              <span className={`sevBadge ${cls}`}>{label}</span>
              <span className="sevDesc">{desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ② 분석 기준 */}
      <div className="card">
        <p className="cardTitle">
          분석 기준 — {METRICS[metricTab].label} &nbsp;
          <button style={{ fontSize: 11, color: "var(--blue)", fontWeight: 400 }} onClick={() => onOpenDrawer(METRICS[metricTab].criteriaId)}>
            전체 보기(용어 설명 포함) ↗
          </button>
        </p>
        <div className="grid2">
          {CRITERIA.find((c) => c.id === METRICS[metricTab].criteriaId)?.items.slice(0, 4).map((item) => (
            <div key={item.q} className="catLine">
              <p className="catLineHead" style={{ fontSize: 12 }}>
                {item.q}
                {item.scoring === "weighted" && <span className="badge c2" style={{ marginLeft: 6 }}>⚖️ 가중합산</span>}
              </p>
              <p className="catLineBody">{item.a}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ③ 현황 요약 — 변경 유무 관계없는 현재 상태 (Apple 좌 / Samsung 우) */}
      <div className="card">
        <p className="cardTitle">현황 요약 — {METRICS[metricTab].label} (변경 유무 무관, 현재 상태)</p>
        <div className="siteSplit">
          {(["apple", "samsung"] as SiteKey[]).map((site) => (
            <div key={site}>
              <p className="siteSplitHead">
                <span className={`badge ${site}`}>{siteName(site)}</span>
              </p>
              <FindingList metric={metricTab} lines={linesFromBlock(siteBlocks[site])} />
            </div>
          ))}
        </div>
      </div>

      {/* ④ 변경점 목록 (Apple 좌 / Samsung 우) */}
      <div className="card">
        <p className="cardTitle">변경점 목록 — {METRICS[metricTab].label} ({changes.length}건)</p>
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
                          <div key={c.id}>
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

      {/* URL 전체 목록 */}
      <div className="card">
        <p className="cardTitle">모니터링 URL 목록 ({totalUrls}개)</p>
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
            <div className="urlRow" key={(u.site_key || "") + u.url}>
              <span className={`badge ${siteClass(u.site_key)}`} style={{ fontSize: 10 }}>
                {u.site_key === "apple" ? "Apple" : "Samsung"}
              </span>
              <span>{u.tier_level ?? "-"}</span>
              <a href={u.url} target="_blank" rel="noreferrer">{u.url}</a>
              <span />
            </div>
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
  metricTab, pages, urls, avgSamsung, avgApple,
  selectedUrl, selectedPage, loadingPage, onPick,
}: {
  metricTab: MetricTab; pages: Record<SiteKey, PageLite[]>; urls: UrlRow[];
  avgSamsung: ReturnType<typeof metricAverage>; avgApple: ReturnType<typeof metricAverage>;
  selectedUrl: string;
  selectedPage: PageDetail | null; loadingPage: boolean; onPick: (url: string) => void;
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

  return (
    <div className="panelStack">
      {/* 요약 카드 — Apple / Samsung 전체 요약 */}
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">페이지별 현재 상태</p>
            <h1 className="summaryH1">{METRICS[metricTab].label} — Apple / Samsung 전체 요약</h1>
            <p className="summaryDesc">페이지를 선택하면 아래에 DATA/COPY/VISUAL 상세 근거가 펼쳐집니다.</p>
          </div>
        </div>
        <div className="avgGrid" style={{ marginTop: 14 }}>
          <AverageBox title="Apple 경쟁사" site="apple" data={avgApple} metric={metricTab} />
          <AverageBox title="Samsung 당사" site="samsung" data={avgSamsung} metric={metricTab} />
        </div>
      </div>

      {/* Tier(0~4) 별 요약 — 어떤 페이지가 어느 Tier에 포함되는지 위주 */}
      <div className="card">
        <p className="cardTitle">Tier별 요약 — 이 Tier에 포함된 페이지</p>
        <div className="siteSplit">
          {(["apple", "samsung"] as SiteKey[]).map((site) => (
            <div key={site}>
              <p className="siteSplitHead">
                <span className={`badge ${site}`}>{siteName(site)}</span>
              </p>
              {tierGroups(site).map(({ tier, pages: ps }) => (
                <div key={tier} className="tierRow">
                  <p className="tierRowHead">
                    {TIER_META[tier]?.label || `Tier ${tier}`}
                    <span className="tierRowDesc">{TIER_META[tier]?.desc} · {ps.length}개</span>
                  </p>
                  <p className="tierPageList">
                    {ps.map((p) => (
                      <span key={p.url} className="tierPageChip" title={p.url}>
                        {p.title || shortUrl(p.url)}
                      </span>
                    ))}
                  </p>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Tier 기준 설명 */}
      <div className="card">
        <p className="cardTitle">Tier 기준 설명</p>
        {Object.entries(TIER_META).map(([t, meta]) => (
          <div key={t} className="catLine">
            <p className="catLineHead" style={{ fontSize: 12 }}>{meta.label}</p>
            <p className="catLineBody">{meta.desc}</p>
          </div>
        ))}
      </div>

      {/* 페이지 목록 */}
      <div className="card">
        <p className="cardTitle">페이지별 목록 ({pageRows.length}개)</p>
        <div className="pageTable">
          <div className="pageRow head">
            <span>구분</span><span>Tier</span><span>단어 수</span><span>페이지</span>
          </div>
          {pageRows.map((p) => (
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
              <span>Tier {tierOf(p.url)}</span>
              <span>{p.word_count || 0}</span>
              <span>
                {p.title || shortUrl(p.url)}
                <small>{shortUrl(p.url)}</small>
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* 선택 페이지 상세 */}
      <div className="card">
        <p className="cardTitle">선택 페이지 상세 근거</p>
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
