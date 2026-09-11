"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View, MainTab, MetricTab, MetricView, SiteKey, CrawlProgress, Change, Report, Session,
  PageLite, PageDetail, UrlRow,
  METRICS, CRITERIA, DEFAULT_SITE_ORDER, orderedSiteKeys, siteName, siteShortName, siteClass, shortUrl, bucketOf, captureScreen, productPageLabel,
} from "./shared";
import { Landing, Overview, PagesTab, ProductTab, CriteriaDrawer, InsightChat } from "./sections";
import QubiApp from "./QubiApp";
import HoneyCombApp from "./HoneyCombApp"; // [2026-09] 🐝C honeyComb (목업)

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

/* ════════════════════════════════════════════════════
   메인 컴포넌트
════════════════════════════════════════════════════ */
export default function Page() {
  const [view, setView] = useState<View>("home");
  const [appMode, setAppMode] = useState<"applestalker" | "qubi" | "honeycomb">("applestalker");
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
  const [focusSite, setFocusSite] = useState<{ site: SiteKey; n: number } | null>(null);
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

  const copyEmailBody = async () => {
    setEmailState("본문 준비 중…");
    try {
      const res = await fetch(API + "/api/export/email-html", { cache: "no-store" });
      if (!res.ok) throw new Error("fetch");
      const html = await res.text();
      // 서식(표·색·점수) 유지하며 클립보드에 복사 → 메일 작성창에 그대로 붙여넣기
      if (navigator.clipboard && "write" in navigator.clipboard && typeof ClipboardItem !== "undefined") {
        await navigator.clipboard.write([
          new ClipboardItem({
            "text/html": new Blob([html], { type: "text/html" }),
            "text/plain": new Blob([html], { type: "text/plain" }),
          }),
        ]);
        setEmailState("복사됨 — 메일 작성창에 붙여넣기(Ctrl/Cmd+V)");
      } else {
        // 클립보드 API 미지원: 새 탭에 열어 수동 복사
        const w = window.open("", "_blank");
        if (w) { w.document.write(html); w.document.close(); }
        setEmailState("새 탭에서 전체 선택 후 복사하세요");
      }
    } catch {
      setEmailState("복사 실패 — 백엔드 연결/데이터 확인");
    }
    setTimeout(() => setEmailState(""), 6000);
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

  // [2026-09] 최신 제품 URL 자동 탐색(Apple) — 사이트맵 + 세대 프로브 + 존재 확인. verified 만 등록.
  const [discover, setDiscover] = useState<{ loading: boolean; result: any | null; picked: Set<string> }>({ loading: false, result: null, picked: new Set() });
  const runDiscover = async () => {
    setDiscover({ loading: true, result: null, picked: new Set() });
    try {
      const r = await (await fetch(API + "/api/urls/discover?site_key=apple")).json();
      setDiscover({ loading: false, result: r, picked: new Set((r.verified || []).map((x: any) => x.url)) });
    } catch (e) { setDiscover({ loading: false, result: { error: String(e) }, picked: new Set() }); }
  };
  const applyDiscover = async () => {
    const urls = Array.from(discover.picked); if (!urls.length) return;
    const pw = window.prompt(`확인된 URL ${urls.length}개 등록 — 관리자 비밀번호`); if (pw === null) return;
    const r = await fetch(API + "/api/urls/discover/apply", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ urls, site_key: "apple", admin_password: pw }) });
    if (!r.ok) { alert("등록 실패: 비밀번호를 확인하세요."); return; }
    setDiscover({ loading: false, result: null, picked: new Set() }); load();
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
    return <Landing
      onEnterApple={() => { setAppMode("applestalker"); setView("dashboard"); }}
      onEnterQubi={() => { setAppMode("qubi"); setView("dashboard"); }}
      onEnterHoneyComb={() => { setAppMode("honeycomb"); setView("dashboard"); }} />;
  }

  if (appMode === "honeycomb") {
    return <HoneyCombApp apiBase={API} onHome={() => setView("home")} />;
  }

  if (appMode === "qubi") {
    return <QubiApp apiBase={API} onHome={() => setView("home")} />;
  }

  return (
    <div className="appShell">
      {/* ── 좌측 레일 */}
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={() => setView("home")} title="홈으로">
          🍎 Apple Stalker
        </div>
        <div className="brandSub">사과를 추격하며, 당사와 글로벌 경쟁사의 변화를 감지해 리포팅해요</div>
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

          <button className="runItem" onClick={runDiscover} disabled={discover.loading}>
            <span style={{ fontSize: 12, color: "var(--blue)", fontWeight: 600 }}>{discover.loading ? "찾는 중… (apple.com 에 실제로 있는 주소만)" : "🔎 Apple 신제품 페이지 찾기"}</span>
          </button>
          {discover.result && (
            <div style={{ padding: "4px 6px 8px", fontSize: 11.5 }}>
              {discover.result.error && <div style={{ color: "var(--high)" }}>{discover.result.error}</div>}
              {!discover.result.error && (<>
                <div style={{ color: "var(--sec)", marginBottom: 4 }}>apple.com 에 실제로 존재하는 새 페이지 <b style={{ color: "#166534" }}>{discover.result.verified?.length}개</b> (아래 체크된 것만 등록됩니다)</div>
                {(discover.result.candidates || []).filter((c: any) => c.verified).map((c: any) => (
                  <label key={c.url} style={{ display: "flex", gap: 6, alignItems: "flex-start", padding: "2px 0" }}>
                    <input type="checkbox" checked={discover.picked.has(c.url)} onChange={(e) => { const s2 = new Set(discover.picked); e.target.checked ? s2.add(c.url) : s2.delete(c.url); setDiscover({ ...discover, picked: s2 }); }} />
                    <span style={{ wordBreak: "break-all" }}>{c.url} <span style={{ color: "var(--sec)" }}>· {c.category}{c.generation ? ` · ${c.generation}세대` : ""} · {c.source}</span></span>
                  </label>))}
                {(discover.result.verified || []).length === 0 && <div style={{ color: "var(--sec)" }}>새로 확인된 페이지가 없습니다(이미 최신이거나 apple.com 접근 불가).</div>}
                {(discover.result.candidates || []).some((c: any) => !c.verified) && (
                  <details style={{ marginTop: 4 }}><summary style={{ cursor: "pointer", color: "var(--sec)" }}>확인해 봤지만 없는 주소 {(discover.result.candidates || []).filter((c: any) => !c.verified).length}개</summary>
                    {(discover.result.candidates || []).filter((c: any) => !c.verified).map((c: any) => <div key={c.url} style={{ color: "var(--ter)", wordBreak: "break-all" }}>{c.url} · HTTP {c.status ?? "—"}{c.note ? ` · ${c.note}` : ""}</div>)}
                  </details>)}
                {discover.picked.size > 0 && <button className="btnAdd" style={{ marginTop: 6, padding: "5px 10px" }} onClick={applyDiscover}>확인된 {discover.picked.size}개 등록</button>}
              </>)}
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
                  <span className="urlListUrl" title={u.url}>
                    <b>{productPageLabel(u, u.url)}</b>
                    <small>{u.url}</small>
                  </span>
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
              <button className={`tabBtn ${mainTab === "products" ? "on" : ""}`} onClick={() => setMainTab("products")}>
                제품별 분석
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
              <button className="toolBtn" onClick={copyEmailBody} disabled={!online}>
                📋 메일 본문 복사
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
          ) : mainTab === "pages" ? (
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
              focusSite={focusSite}
            />
          ) : (
            <ProductTab
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

      {/* Q&A는 탭과 무관하게 항상 떠 있음 */}
      <InsightChat dcv={report?.dcv} changes={allChanges} expectedSites={orderedSiteKeys(urls.map((u) => u.site_key || ""))} urls={urls}
        onNavigateSite={(site) => { setMainTab("pages"); setFocusSite((p) => ({ site, n: (p?.n ?? 0) + 1 })); }} />

      {/* ── 기준 설명 Drawer */}
      <CriteriaDrawer open={drawerOpen} section={drawerSection} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
