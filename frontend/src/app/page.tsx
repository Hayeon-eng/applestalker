"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View, MainTab, MetricTab, MetricView, SiteKey, CrawlProgress, Change, Report, Session,
  PageLite, PageDetail, UrlRow,
  METRICS, CRITERIA, DEFAULT_SITE_ORDER, orderedSiteKeys, siteName, siteShortName, siteClass, shortUrl, bucketOf, captureScreen,
} from "./shared";
import { Landing, Overview, PagesTab, CriteriaDrawer } from "./sections";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

/* ════════════════════════════════════════════════════
   메인 컴포넌트
════════════════════════════════════════════════════ */
export default function Page() {
  const [view, setView] = useState<View>("home");
  const [mainTab, setMainTab] = useState<MainTab>("overview");
  const [metricTab, setMetricTab] = useState<MetricView>("all");
  const [online, setOnline] = useState<boolean | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [runs, setRuns] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [pages, setPages] = useState<Record<SiteKey, PageLite[]>>({});
  const [urls, setUrls] = useState<UrlRow[]>([]);
  const [urlQuery, setUrlQuery] = useState("");
  const [urlAccordionOpen, setUrlAccordionOpen] = useState(false);
  const [selectedChange, setSelectedChange] = useState<Change | null>(null);
  const [selectedPage, setSelectedPage] = useState<PageDetail | null>(null);
  const [selectedUrl, setSelectedUrl] = useState("");
  const [loadingPage, setLoadingPage] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [crawling, setCrawling] = useState(false);
  const [progress, setProgress] = useState<CrawlProgress>({ active: false, total: 0, done: 0 });
  const [emailState, setEmailState] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerSection, setDrawerSection] = useState<string | null>(null);
  const [showUrlAdd, setShowUrlAdd] = useState(false);
  const newUrlRef = useRef<HTMLInputElement>(null);
  const esRef = useRef<EventSource | null>(null);

  const load = useCallback(async () => {
    try {
      const h = await fetch(API + "/api/health", { cache: "no-store" });
      if (!h.ok) throw new Error("offline");
      setOnline(true);
      const [rRep, rRuns, rUrls, rStatus] = await Promise.all([
        fetch(API + "/api/latest-report", { cache: "no-store" }).catch(() => null),
        fetch(API + "/api/runs", { cache: "no-store" }).catch(() => null),
        fetch(API + "/api/urls", { cache: "no-store" }).catch(() => null),
        fetch(API + "/api/crawl-status", { cache: "no-store" }).catch(() => null),
      ]);
      const jRep = rRep ? await rRep.json() : null;
      const jUrls = rUrls ? await rUrls.json() : null;
      setReport(jRep?.has_data ? jRep : null);
      setActiveSessionId(jRep?.run_id || null);
      setRuns(rRuns ? (await rRuns.json()).sessions || [] : []);
      const nextUrls = jUrls?.urls || [];
      setUrls(nextUrls);
      const dcvSites = Object.values((jRep?.dcv || {}) as Record<string, Record<string, unknown>>)
        .flatMap((block) => Object.keys(block || {}));
      const urlSites = nextUrls.map((u: UrlRow) => u.site_key).filter(Boolean) as string[];
      const siteKeys = orderedSiteKeys([...DEFAULT_SITE_ORDER, ...urlSites, ...dcvSites]);
      const pagePairs = await Promise.all(siteKeys.map(async (site) => {
        const res = await fetch(API + "/api/pages?site=" + encodeURIComponent(site), { cache: "no-store" }).catch(() => null);
        return [site, res ? ((await res.json()).pages || []) : []] as [SiteKey, PageLite[]];
      }));
      setPages(Object.fromEntries(pagePairs));
      const jStatus = rStatus ? await rStatus.json() : null;
      if (jStatus?.crawling) {
        setCrawling(true);
        connectProgress();
      }
    } catch {
      setOnline(false);
      setReport(null);
    }
  }, []);

  // ── 크롤 진행률 SSE 연결 (수집 실행 버튼 눌렀을 때 + 이미 다른 곳에서 크롤 중일 때 둘 다 사용) ──
  const connectProgress = useCallback(() => {
    if (esRef.current) return; // 이미 연결됨
    setProgress({ active: true, total: 0, done: 0 });
    const es = new EventSource(API + "/api/crawl-progress");
    esRef.current = es;
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d.type === "start") {
          setProgress((p) => ({ ...p, active: true, site: d.site, total: d.total || 0, done: 0 }));
        } else if (d.type === "page_done") {
          setProgress((p) => ({ ...p, active: true, done: p.done + 1, currentUrl: d.url,
            error: d.status === "error" ? d.error : undefined }));
        } else if (d.type === "done") {
          setProgress((p) => ({ ...p, currentUrl: undefined }));
        } else if (d.type === "status" && d.crawling === false) {
          es.close(); esRef.current = null;
          setProgress((p) => ({ ...p, active: false }));
          setCrawling(false);
          load();
        }
      } catch { /* heartbeat 등 무시 */ }
    };
    es.onerror = () => { es.close(); esRef.current = null; setProgress((p) => ({ ...p, active: false })); };
  }, [load]);

  useEffect(() => () => { esRef.current?.close(); }, []);

  useEffect(() => { load(); }, [load]);

  const loadSession = async (runId: string) => {
    setLoadingSession(true);
    setActiveSessionId(runId);
    try {
      const r = await fetch(API + "/api/latest-report?run_id=" + encodeURIComponent(runId), { cache: "no-store" });
      const j = await r.json();
      setReport(j?.has_data ? j : null);
      setSelectedChange(null);
      setSelectedPage(null);
      setMainTab("overview"); // 이력 데이터는 '현황/변경점 분석' 탭에 표시되므로 그쪽으로 전환
    } catch {
      alert("수집 이력을 불러오지 못했습니다. 네트워크 상태를 확인해주세요.");
    } finally {
      setLoadingSession(false);
    }
  };

  const deleteSession = async (runIds: string[], e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("이 수집 기록을 삭제할까요?")) return;
    setRuns((prev) => prev.filter((s) => !s.run_ids.some((r) => runIds.includes(r))));
    for (const id of runIds) {
      await fetch(API + "/api/runs/" + encodeURIComponent(id), { method: "DELETE" }).catch(() => {});
    }
    load();
  };

  const startCrawl = async () => {
    if (!online) return;
    setCrawling(true);
    try {
      await fetch(API + "/trigger-crawl/all", { method: "POST" });
      connectProgress();
    } catch {
      setCrawling(false);
    }
  };

  const sendEmail = async () => {
    setEmailState("발송 중…");
    try {
      const r = await fetch(API + "/api/email/test", { method: "POST" });
      const j = await r.json();
      setEmailState(r.ok ? "발송 완료: " + (j.recipient || "수신자") : "실패: " + (j.detail || j.error || "설정 확인"));
    } catch {
      setEmailState("실패: 백엔드 연결 확인");
    }
    setTimeout(() => setEmailState(""), 5000);
  };

  const openPage = async (url: string) => {
    setSelectedUrl(url);
    setSelectedPage(null);
    setSelectedChange(null);
    setLoadingPage(true);
    try {
      const r = await fetch(API + "/api/page-detail?url=" + encodeURIComponent(url));
      if (r.ok) setSelectedPage(await r.json());
    } finally {
      setLoadingPage(false);
    }
  };

  const addUrl = async () => {
    const u = newUrlRef.current?.value.trim();
    if (!u) return;
    const pw = window.prompt("관리자 비밀번호를 입력하세요");
    if (pw === null) return;
    const r = await fetch(API + "/api/urls", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: u, admin_password: pw }),
    });
    if (!r.ok) { alert("추가 실패: 비밀번호를 확인하세요."); return; }
    if (newUrlRef.current) newUrlRef.current.value = "";
    setShowUrlAdd(false);
    load();
  };

  const deleteUrl = async (u: string) => {
    const pw = window.prompt(`"${shortUrl(u)}" 삭제 — 관리자 비밀번호 입력`);
    if (pw === null) return;
    const r = await fetch(
      API + "/api/urls?url=" + encodeURIComponent(u) + "&admin_password=" + encodeURIComponent(pw),
      { method: "DELETE" }
    );
    if (!r.ok) { alert("삭제 실패: 비밀번호를 확인하세요."); return; }
    load();
  };

  const openDrawer = (sectionId?: string) => {
    setDrawerSection(sectionId || null);
    setDrawerOpen(true);
  };

  // 요약(High 변화 목록 / 전체요약 축약카드)에서 클릭하면 해당 지표 탭으로 이동 + 필요시 그 변경점을 펼침
  const jumpToMetric = (m: MetricTab, change?: Change) => {
    setMetricTab(m);
    setSelectedChange(change || null);
  };

  const allChanges = report?.changes || [];
  const effectiveMetric: MetricTab = metricTab === "all" ? "data" : metricTab;
  const metricChanges = allChanges.filter((c) => bucketOf(c) === effectiveMetric);
  const filteredUrls = urls.filter((u) =>
    ((u.site_key || "") + " " + u.url).toLowerCase().includes(urlQuery.toLowerCase())
  );

  if (view === "home") {
    return <Landing onEnter={() => setView("dashboard")} />;
  }

  return (
    <div className="appShell">
      {/* ── 좌측 레일 */}
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={() => setView("home")} title="홈으로">
          🍎 Apple Stalker
        </div>
        <div className="brandSub">Samsung + Global competitors 변화 감지</div>
        <div className={`connBadge ${online === true ? "ok" : "bad"}`}>
          <span className="connDot" />
          {online === null ? "확인 중" : online ? "백엔드 연결됨" : "연결 안 됨"}
        </div>

        <div className="sideScroll">
          <div className="sideLabel">수집 이력{loadingSession && " · 불러오는 중…"}</div>
          {runs.length === 0 && <p className="muted" style={{ padding: "4px 6px" }}>아직 이력이 없습니다</p>}
          {runs.map((run) => {
            const isActive = run.run_ids.includes(activeSessionId || "");
            return (
              <div
                key={run.session}
                className={`runItem ${isActive ? "active" : ""}`}
                role="button"
                tabIndex={0}
                onClick={() => loadSession(run.run_ids[0])}
                onKeyDown={(e) => { if (e.key === "Enter") loadSession(run.run_ids[0]); }}
              >
                <div className="runMeta">
                  <span className="runTs">{run.timestamp}</span>
                  <span className="runDesc">
                    {run.sites.map((s) => siteShortName(s)).join("+")}
                    &nbsp;·&nbsp;변경 {run.changes}건
                  </span>
                </div>
                <span className="runDel" role="button" tabIndex={0}
                  onClick={(e) => deleteSession(run.run_ids, e)}
                  onKeyDown={(e) => { e.stopPropagation(); if (e.key === "Enter") deleteSession(run.run_ids, e as any); }}
                  title="삭제">×</span>
              </div>
            );
          })}

          <div className="sideLabel" style={{ marginTop: 8 }}>중요도 기준</div>
          <div className="sideSeverity">
            {[
              ["high", "높음", "AI 검색·구매전환·핵심 페이지 영향 큰 변화"],
              ["med", "보통", "meta·H1·FAQ·CTA·주요 카피 변화"],
              ["low", "낮음", "단어·UI 라벨·작은 이미지·렌더링 노이즈"],
            ].map(([cls, label, desc]) => (
              <div key={cls} className="sideSevRow">
                <span className={`sevBadge ${cls}`}>{label}</span>
                <span className="sideSevDesc">{desc}</span>
              </div>
            ))}
            <button className="sideSevMore" onClick={() => openDrawer("severity")}>자세히 ↗</button>
          </div>

          {metricTab !== "all" && (
            <>
              <div className="sideLabel" style={{ marginTop: 8 }}>분석 기준 — {METRICS[effectiveMetric].label}</div>
              <div className="sideSeverity">
                {CRITERIA.find((c) => c.id === METRICS[effectiveMetric].criteriaId)?.items.slice(0, 4).map((item) => (
                  <div key={item.q} className="sideCriteriaRow">
                    <p className="sideCriteriaQ">{item.q}</p>
                    <p className="sideSevDesc">{item.a}</p>
                  </div>
                ))}
                <button className="sideSevMore" onClick={() => openDrawer(METRICS[effectiveMetric].criteriaId)}>
                  전체 보기(용어 설명 포함) ↗
                </button>
              </div>
            </>
          )}

          <div className="sideLabel" style={{ marginTop: 8 }}>URL 관리</div>
          <button className="runItem" onClick={() => setShowUrlAdd((v) => !v)}>
            <span style={{ fontSize: 12, color: "var(--blue)", fontWeight: 600 }}>
              {showUrlAdd ? "▾" : "▸"} URL 추가
            </span>
          </button>
          {showUrlAdd && (
            <div style={{ padding: "4px 6px 8px" }}>
              <div className="urlAddRow">
                <input ref={newUrlRef} className="urlInput" placeholder="https://…" />
                <button className="btnAdd" onClick={addUrl}>추가</button>
              </div>
            </div>
          )}

          <button className="urlAccordionToggle" onClick={() => setUrlAccordionOpen((v) => !v)}>
            <span>{urlAccordionOpen ? "▾" : "▸"} 모니터링 URL 목록</span>
            <span className="urlAccordionCount">{urls.length}개</span>
          </button>
          {urlAccordionOpen && (
            <div className="urlAccordionBody">
              {urls.map((u) => (
                <div key={u.url} className="urlListItem">
                  <span className={`badge ${siteClass(u.site_key)}`} style={{ fontSize: 9, flexShrink: 0 }}>
                    {siteShortName(u.site_key)}
                  </span>
                  <span className="urlListUrl" title={u.url}>{u.url}</span>
                  <button className="urlDelBtn" onClick={() => deleteUrl(u.url)} title="삭제(관리자 비번)">×</button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="sideFoot">
          <button className="btnPrimary" disabled={!online || crawling} onClick={startCrawl}>
            {crawling ? "수집 중…" : "수집 실행"}
          </button>
          {emailState && <p className="emailNotice">{emailState}</p>}
        </div>
      </aside>

      {/* ── 메인 */}
      <div className="mainArea">
        {/* 헤더 */}
        <header className="topbar">
          <div className="topbarRow1">
            <div className="tabGroup">
              <button className={`tabBtn ${mainTab === "overview" ? "on" : ""}`} onClick={() => setMainTab("overview")}>
                현황/변경점 분석
              </button>
              <button className={`tabBtn ${mainTab === "pages" ? "on" : ""}`} onClick={() => setMainTab("pages")}>
                Site별 분석
              </button>
            </div>

            {/* 도구 버튼 — 항상 헤더에 고정 */}
            <div className="toolRow">
              <button className="toolBtn" onClick={() => openDrawer("severity")}>
                📋 기준 설명
              </button>
              <button className="toolBtn" onClick={captureScreen}>📸 캡처</button>
              {online && (
                <a className="toolBtn" href={API + "/api/export/xlsx"} download>
                  📊 Excel
                </a>
              )}
              {online && (
                <a className="toolBtn" href={API + "/api/export/pptx"} download>
                  🎞 PPTX
                </a>
              )}
              <button className="toolBtn" onClick={sendEmail} disabled={!online}>
                📧 메일 테스트
              </button>
            </div>
          </div>

          {progress.active && (
            <div className="progressWrap">
              <div className="progressTopRow">
                <span className="progressTitle">
                  🔄 수집 중{progress.site ? ` — ${siteName(progress.site)}` : ""}
                </span>
                <span className="progressCount">{progress.done}{progress.total ? ` / ${progress.total}` : ""}</span>
              </div>
              <div className="progressBar">
                <div
                  className="progressFill"
                  style={{ width: progress.total ? `${Math.min(100, (progress.done / progress.total) * 100)}%` : "8%" }}
                />
              </div>
              {progress.currentUrl && <p className="progressLabel">{shortUrl(progress.currentUrl)}</p>}
            </div>
          )}

          {/* 메트릭 탭 + ⓘ — 전체요약 > DATA > COPY > VISUAL 순서, 두 메인탭 공통 */}
          <div className="topbarRow2">
            <div className="metricGroup">
              <button
                className={`metricBtn ${metricTab === "all" ? "on" : ""}`}
                onClick={() => setMetricTab("all")}
              >
                전체요약
              </button>
              {(Object.keys(METRICS) as MetricTab[]).map((key) => (
                <button
                  key={key}
                  className={`metricBtn ${metricTab === key ? "on" : ""}`}
                  onClick={() => setMetricTab(key)}
                >
                  {METRICS[key].label}
                </button>
              ))}
            </div>
            {metricTab === "all" ? (
              <>
                <button className="metricInfo" title="전체 기준 보기" onClick={() => openDrawer()}>
                  ⓘ 전체 기준
                </button>
                <span style={{ fontSize: 12, color: "var(--sec)", marginLeft: 6 }}>
                  DATA·COPY·VISUAL 세 영역을 요약해서 한 화면에 모아 보여줍니다. 자세히 보려면 각 탭을 선택하세요.
                </span>
              </>
            ) : (
              <>
                <button
                  className="metricInfo"
                  title="이 영역의 분석 기준 보기"
                  onClick={() => openDrawer(METRICS[metricTab].criteriaId)}
                >
                  ⓘ 이 영역 기준
                </button>
                <span style={{ fontSize: 12, color: "var(--sec)", marginLeft: 6 }}>
                  {METRICS[metricTab].plain}
                </span>
              </>
            )}
          </div>
        </header>

        {/* 탭 콘텐츠 */}
        <div className="contentScroll">
          {mainTab === "overview" ? (
            <Overview
              report={report}
              metricTab={metricTab}
              dcv={report?.dcv}
              changes={metricChanges}
              allChanges={allChanges}
              selectedChange={selectedChange}
              setSelectedChange={setSelectedChange}
              urls={filteredUrls}
              totalUrls={urls.length}
              urlQuery={urlQuery}
              setUrlQuery={setUrlQuery}
              onOpenDrawer={openDrawer}
              onJumpToMetric={jumpToMetric}
            />
          ) : (
            <PagesTab
              metricTab={metricTab}
              pages={pages}
              urls={urls}
              dcv={report?.dcv}
              allChanges={allChanges}
              selectedUrl={selectedUrl}
              selectedPage={selectedPage}
              loadingPage={loadingPage}
              onPick={openPage}
              onOpenDrawer={openDrawer}
            />
          )}
        </div>
      </div>

      {/* ── 기준 설명 Drawer */}
      <CriteriaDrawer open={drawerOpen} section={drawerSection} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
