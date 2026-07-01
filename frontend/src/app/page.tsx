"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

/* ── 타입 */
type MainTab = "overview" | "pages";
type MetricTab = "data" | "copy" | "visual";
type SiteKey = "samsung" | "apple";
type Change = {
  id: number; url: string; site?: string; level?: "High" | "Medium" | "Low";
  category?: string; field?: string; summary?: string; before?: string; after?: string;
  evidence?: Record<string, unknown>;
};
type AnalysisBlock = {
  facts?: Record<string, any>;
  insights?: { point?: string; evidence_url?: string }[];
  narrative?: string[];
};
type Report = {
  has_data?: boolean; timestamp?: string; has_changes?: boolean;
  changes?: Change[]; by_category?: Record<string, number>;
  category_summary?: Record<string, string>;
  dcv?: Record<MetricTab, Record<string, AnalysisBlock>>;
  analysis?: { summary?: string };
};
type Session = {
  session: string; run_ids: string[]; sites: string[];
  pages: number; changes: number; timestamp: string;
};
type PageLite = { url: string; title: string; word_count: number };
type PageDetail = {
  url: string; crawled_at?: string;
  data?: { facts?: any; narrative?: string[] };
  copy?: { facts?: any; narrative?: string[] };
  visual?: { facts?: any; narrative?: string[] };
};
type UrlRow = { url: string; tier_level?: number; site_key?: string };

/* ── 기준 설명 (Drawer 콘텐츠 + ⓘ 아이콘 연동) */
const CRITERIA: { id: string; title: string; items: { q: string; a: string }[] }[] = [
  {
    id: "severity",
    title: "중요도 기준 (High / Medium / Low)",
    items: [
      { q: "High — 높음", a: "Schema·DOM·여러 섹션 동시 변화, 가격·구매처럼 검색 노출이나 구매 판단에 직접 영향을 주는 변화입니다." },
      { q: "Medium — 보통", a: "문장·슬로건·메뉴·meta·FAQ 같이 의미 해석에 영향을 주는 변화입니다." },
      { q: "Low — 낮음", a: "단어 몇 개·오타·작은 이미지 변화 등 영향이 제한적인 변화입니다." },
    ],
  },
  {
    id: "data",
    title: "DATA — Schema / HTML / Meta / H-tag",
    items: [
      { q: "Schema Coverage", a: "전체 페이지 중 구조화 데이터가 적용된 비율. Product·FAQPage·Organization·BreadcrumbList 포함." },
      { q: "Schema Completeness", a: "Product 기준 필수 속성(name·image·description·brand·offers·aggregateRating·review) 충족률." },
      { q: "Schema Distribution", a: "템플릿(카테고리·PDP·홈 등) 유형별로 Schema가 고르게 적용됐는지." },
      { q: "Schema Alignment", a: "페이지 목적(PDP엔 Product, FAQ엔 FAQPage 등)과 실제 Schema 타입이 일치하는지." },
      { q: "@id 연결성(아키텍처 참고)", a: "Linked(@id 상호참조형) vs Inline(개별 페이지 임베딩형). 우열 기준이 아닌 구조적 특성입니다." },
      { q: "H-tag 구조", a: "H1 없음·H2 없이 H3만 존재(depth 불연속) 등 heading 계층 오류를 감지합니다." },
      { q: "Meta description", a: "비어있거나 누락된 페이지를 집계합니다." },
    ],
  },
  {
    id: "copy",
    title: "COPY — 카피 풍부성 / FAQ 품질",
    items: [
      { q: "카피 풍부성 점수 (0~100)", a: "정량지표(숫자+단위 밀도) 35% + 구조지표(H2·CTA·FAQ 보유) 25% + 비교·근거 키워드 20% + FAQ 보유 20%. 70+ 우수, 40~69 보통, 40 미만 미흡." },
      { q: "정량지표", a: "본문 100단어당 숫자+단위(GB·mAh·mm·% 등) 출현량. 목표 3개/100단어 기준으로 스케일." },
      { q: "빈약 콘텐츠", a: "150단어 미만은 빈약(thin) 콘텐츠로 분류합니다. 단순 수치 기준이 아닌 밀도 4단계 분포로 판단." },
      { q: "FAQ 품질 점수 (0~100)", a: "구체성(수치·스펙 포함) 40% + 질문현실성(실제 의문형) 30% + AI인용적합성(첫 문장 인용 가능) 30%." },
    ],
  },
  {
    id: "visual",
    title: "VISUAL — 이미지 분석",
    items: [
      { q: "이미지 분류", a: "alt+src 텍스트 기반 휴리스틱. lifestyle(사람이 쓰는 상황) / product(제품 자체) / unclassified 3종." },
      { q: "alt 텍스트 품질", a: "비어있음·일반적(image/photo/배너 등)·설명적(15자 이상, 제네릭 아님) 3단계. Vision AI 분석이 아닌 텍스트 기반 판정입니다." },
      { q: "이미지 고유성", a: "src/alt 중복도 기반 추정치. 같은 이미지·문구가 여러 페이지에 반복 사용되는 템플릿화 정도." },
      { q: "스토리텔링", a: "product+lifestyle 혼합이면서 설명적 alt가 2개 이상인 페이지를 스토리텔링 페이지로 분류합니다." },
    ],
  },
];

/* ── 상수 */
const METRICS: Record<MetricTab, { label: string; plain: string; criteriaId: string }> = {
  data: { label: "DATA 구조", plain: "Schema·HTML·Meta·H-tag를 분석합니다.", criteriaId: "data" },
  copy: { label: "COPY 문구", plain: "카피 풍부성·FAQ 품질·콘텐츠 밀도를 분석합니다.", criteriaId: "copy" },
  visual: { label: "VISUAL 이미지", plain: "이미지 다양성·alt 품질·스토리텔링을 분석합니다.", criteriaId: "visual" },
};
const CATEGORY_BUCKETS: Record<string, MetricTab> = {
  "데이터·스키마": "data", "데이터/스키마": "data", "DATA/Schema": "data",
  technical: "data", navigation: "data",
  카피: "copy", "가격·프로모션": "copy", "가격/프로모션": "copy",
  content: "copy", commerce: "copy",
  비주얼: "visual", visual: "visual",
};

/* ── 유틸 */
const siteName = (s?: string) =>
  s === "apple" ? "Apple 경쟁사" : s === "samsung" ? "Samsung 당사" : s || "미분류";
const siteClass = (s?: string) => (s === "apple" ? "apple" : "samsung");
const levelKo = (l?: string) => l === "High" ? "높음" : l === "Medium" ? "보통" : "낮음";
const levelClass = (l?: string) => l === "High" ? "high" : l === "Medium" ? "med" : "low";
const shortUrl = (u: string) => {
  try { const x = new URL(u); return (x.hostname + x.pathname).replace(/\/$/, ""); } catch { return u; }
};
const linesFromBlock = (b?: AnalysisBlock) => [
  ...(b?.narrative || []),
  ...((b?.insights || []).map((x) => x.point || "").filter(Boolean)),
];
const tierFromUrl = (u: string) => {
  if (/buy|shop|specs|purchase/i.test(u)) return "Tier 4";
  if (/iphone-|galaxy-|watch|buds|airpods/i.test(u)) return "Tier 3";
  if (/compare|find-your|switch|ai|one-ui/i.test(u)) return "Tier 2";
  return "Tier 1";
};
const bucketOf = (c: Change): MetricTab => {
  if (CATEGORY_BUCKETS[c.category || ""]) return CATEGORY_BUCKETS[c.category || ""];
  const raw = ((c.category || "") + " " + (c.field || "")).toLowerCase();
  if (/schema|dom|canonical|meta|html|h-tag|nav/.test(raw)) return "data";
  if (/visual|image|screenshot|alt|lifestyle/.test(raw)) return "visual";
  return "copy";
};
const metricAverage = (sitePages: PageLite[], block?: AnalysisBlock) => {
  const f = block?.facts || {};
  return {
    pages: sitePages.length,
    avgWords: sitePages.length
      ? Math.round(sitePages.reduce((a, p) => a + (p.word_count || 0), 0) / sitePages.length)
      : 0,
    schema: typeof f.schema?.coverage_pct === "number" ? f.schema.coverage_pct + "%" : "-",
    thin: typeof f.content_density?.thin_pages?.length === "number"
      ? f.content_density.thin_pages.length + "개" : "-",
    lifestyle: typeof f.image_diversity?.lifestyle_ratio_pct === "number"
      ? f.image_diversity.lifestyle_ratio_pct + "%" : "-",
  };
};

/* ── 화면 캡처 */
const captureScreen = async () => {
  const load = () =>
    new Promise<any>((res, rej) => {
      if ((window as any).html2canvas) return res((window as any).html2canvas);
      const sc = document.createElement("script");
      sc.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
      sc.onload = () => res((window as any).html2canvas);
      sc.onerror = () => rej(new Error("load fail"));
      document.body.appendChild(sc);
    });
  try {
    const h2c = await load();
    const canvas = await h2c(document.body, { backgroundColor: "#F8F9FB", scale: 2, useCORS: true });
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `apple-stalker_${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "")}.png`;
    a.click();
  } catch {
    alert("캡처에 실패했습니다.");
  }
};

/* ════════════════════════════════════════════════════
   메인 컴포넌트
════════════════════════════════════════════════════ */
export default function Page() {
  const [mainTab, setMainTab] = useState<MainTab>("overview");
  const [metricTab, setMetricTab] = useState<MetricTab>("data");
  const [online, setOnline] = useState<boolean | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [runs, setRuns] = useState<Session[]>([]);
  const [pages, setPages] = useState<Record<SiteKey, PageLite[]>>({ samsung: [], apple: [] });
  const [urls, setUrls] = useState<UrlRow[]>([]);
  const [urlQuery, setUrlQuery] = useState("");
  const [selectedChange, setSelectedChange] = useState<Change | null>(null);
  const [selectedPage, setSelectedPage] = useState<PageDetail | null>(null);
  const [selectedUrl, setSelectedUrl] = useState("");
  const [loadingPage, setLoadingPage] = useState(false);
  const [crawling, setCrawling] = useState(false);
  const [emailState, setEmailState] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerSection, setDrawerSection] = useState<string | null>(null);
  const [showUrlAdd, setShowUrlAdd] = useState(false);
  const newUrlRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const h = await fetch(API + "/api/health", { cache: "no-store" });
      if (!h.ok) throw new Error("offline");
      setOnline(true);
      const [rRep, rRuns, rSam, rApp, rUrls] = await Promise.all([
        fetch(API + "/api/latest-report", { cache: "no-store" }).catch(() => null),
        fetch(API + "/api/runs", { cache: "no-store" }).catch(() => null),
        fetch(API + "/api/pages?site=samsung", { cache: "no-store" }).catch(() => null),
        fetch(API + "/api/pages?site=apple", { cache: "no-store" }).catch(() => null),
        fetch(API + "/api/urls", { cache: "no-store" }).catch(() => null),
      ]);
      const jRep = rRep ? await rRep.json() : null;
      setReport(jRep?.has_data ? jRep : null);
      setRuns(rRuns ? (await rRuns.json()).sessions || [] : []);
      setPages({
        samsung: rSam ? (await rSam.json()).pages || [] : [],
        apple: rApp ? (await rApp.json()).pages || [] : [],
      });
      setUrls(rUrls ? (await rUrls.json()).urls || [] : []);
    } catch {
      setOnline(false);
      setReport(null);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadSession = async (runId: string) => {
    const r = await fetch(API + "/api/latest-report?run_id=" + encodeURIComponent(runId));
    const j = await r.json();
    setReport(j?.has_data ? j : null);
    setSelectedChange(null);
    setSelectedPage(null);
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
      setTimeout(load, 4000);
    } finally {
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

  const allChanges = report?.changes || [];
  const metricChanges = allChanges.filter((c) => bucketOf(c) === metricTab);
  const filteredUrls = urls.filter((u) =>
    ((u.site_key || "") + " " + u.url).toLowerCase().includes(urlQuery.toLowerCase())
  );
  const siteBlocks = report?.dcv?.[metricTab] || {};
  const avgSamsung = metricAverage(pages.samsung, siteBlocks.samsung);
  const avgApple = metricAverage(pages.apple, siteBlocks.apple);

  return (
    <div className="appShell">
      {/* ── 좌측 레일 */}
      <aside className="sidebar">
        <div className="brand">🍎 Apple Stalker</div>
        <div className="brandSub">당사 vs 경쟁사 페이지 변화 감지</div>
        <div className={`connBadge ${online === true ? "ok" : "bad"}`}>
          <span className="connDot" />
          {online === null ? "확인 중" : online ? "백엔드 연결됨" : "연결 안 됨"}
        </div>

        <div className="sideScroll">
          <div className="sideLabel">수집 이력</div>
          {runs.length === 0 && <p className="muted" style={{ padding: "4px 6px" }}>아직 이력이 없습니다</p>}
          {runs.map((run) => (
            <button key={run.session} className="runItem" onClick={() => loadSession(run.run_ids[0])}>
              <div className="runMeta">
                <span className="runTs">{run.timestamp}</span>
                <span className="runDesc">
                  {run.sites.map((s) => (s === "apple" ? "애플" : "삼성")).join("+")}
                  &nbsp;·&nbsp;변경 {run.changes}건
                </span>
              </div>
              <button className="runDel" onClick={(e) => deleteSession(run.run_ids, e)} title="삭제">×</button>
            </button>
          ))}

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
          {urls.slice(0, 12).map((u) => (
            <div key={u.url} className="urlListItem" style={{ padding: "4px 6px" }}>
              <span className="urlListUrl" title={u.url}>{shortUrl(u.url)}</span>
              <button className="urlDelBtn" onClick={() => deleteUrl(u.url)} title="삭제(관리자 비번)">×</button>
            </div>
          ))}
          {urls.length > 12 && (
            <p className="muted" style={{ padding: "2px 6px" }}>+{urls.length - 12}개 더 있음</p>
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
                현황 및 변경점
              </button>
              <button className={`tabBtn ${mainTab === "pages" ? "on" : ""}`} onClick={() => setMainTab("pages")}>
                페이지별 분석
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

          {/* 메트릭 탭 + ⓘ */}
          <div className="topbarRow2">
            <div className="metricGroup">
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
          </div>
        </header>

        {/* 탭 콘텐츠 */}
        <div className="contentScroll">
          {mainTab === "overview" ? (
            <Overview
              report={report}
              metricTab={metricTab}
              changes={metricChanges}
              allChanges={allChanges}
              selectedChange={selectedChange}
              setSelectedChange={setSelectedChange}
              urls={filteredUrls}
              totalUrls={urls.length}
              urlQuery={urlQuery}
              setUrlQuery={setUrlQuery}
              onOpenDrawer={openDrawer}
            />
          ) : (
            <PagesTab
              metricTab={metricTab}
              pages={pages}
              avgSamsung={avgSamsung}
              avgApple={avgApple}
              siteBlocks={siteBlocks}
              selectedUrl={selectedUrl}
              selectedPage={selectedPage}
              loadingPage={loadingPage}
              onPick={openPage}
            />
          )}
        </div>
      </div>

      {/* ── 기준 설명 Drawer */}
      <CriteriaDrawer open={drawerOpen} section={drawerSection} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}

/* ════════════════════════════════════════════════════
   Overview 탭
════════════════════════════════════════════════════ */
function Overview({
  report, metricTab, changes, allChanges, selectedChange, setSelectedChange,
  urls, totalUrls, urlQuery, setUrlQuery, onOpenDrawer,
}: {
  report: Report | null; metricTab: MetricTab; changes: Change[]; allChanges: Change[];
  selectedChange: Change | null; setSelectedChange: (c: Change | null) => void;
  urls: UrlRow[]; totalUrls: number; urlQuery: string; setUrlQuery: (s: string) => void;
  onOpenDrawer: (id: string) => void;
}) {
  const high = allChanges.filter((c) => c.level === "High").length;
  const apple = allChanges.filter((c) => c.site === "apple").length;
  const samsung = allChanges.filter((c) => c.site === "samsung").length;
  const catSummary = Object.entries(report?.category_summary || {}).filter(
    ([k]) => bucketOf({ id: 0, url: "", category: k }) === metricTab
  );

  return (
    <div className="panelStack">
      {/* 전체 요약 카드 (탭 첫 카드) */}
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">{report?.timestamp || "최근 수집 없음"}</p>
            <h1 className="summaryH1">
              {report ? (allChanges.length > 0 ? `변화 ${allChanges.length}건 감지` : "변화 없음 — 현행 분석") : "수집 데이터 없음"}
            </h1>
            <p className="summaryDesc">
              {report?.analysis?.summary || METRICS[metricTab].plain}
            </p>
          </div>
          <div className="statsRow">
            <Stat label="전체 변경" value={allChanges.length} />
            <Stat label="높음" value={high} tone="red" />
            <Stat label="당사" value={samsung} tone="blue" />
            <Stat label="경쟁사" value={apple} />
          </div>
        </div>

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

      {/* 영역 요약 + 기준 설명 */}
      <div className="grid2">
        <div className="card">
          <p className="cardTitle">영역 요약 — {METRICS[metricTab].label}</p>
          {catSummary.length === 0 ? (
            <p className="muted">이 영역의 요약이 없습니다. 페이지별 분석 탭에서 현재 상태를 확인하세요.</p>
          ) : (
            catSummary.map(([key, val]) => (
              <div key={key} className="catLine">
                <p className="catLineHead">
                  <span className={`badge ${key.includes("애플") || key.includes("apple") ? "apple" : "samsung"}`}>
                    {key}
                  </span>
                </p>
                <p className="catLineBody">{val}</p>
              </div>
            ))
          )}
        </div>
        <div className="card">
          <p className="cardTitle">
            분석 기준 &nbsp;
            <button style={{ fontSize: 11, color: "var(--blue)", fontWeight: 400 }} onClick={() => onOpenDrawer(METRICS[metricTab].criteriaId)}>
              전체 보기 ↗
            </button>
          </p>
          {CRITERIA.find((c) => c.id === METRICS[metricTab].criteriaId)?.items.slice(0, 4).map((item) => (
            <div key={item.q} className="catLine">
              <p className="catLineHead" style={{ fontSize: 12 }}>{item.q}</p>
              <p className="catLineBody">{item.a}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 변경점 목록 */}
      <div className="card">
        <p className="cardTitle">변경점 목록 — {METRICS[metricTab].label} ({changes.length}건)</p>
        {changes.length === 0 ? (
          <p className="muted">이 영역에서 변경된 항목이 없습니다. 페이지별 분석 탭에서 현재 상태를 확인하세요.</p>
        ) : (
          <div className="changeGrid">
            {changes.map((c, idx) => {
              const isOpen = idx === 0 || selectedChange?.id === c.id;
              return (
                <div key={c.id}>
                  <button
                    className={`changeCard ${selectedChange?.id === c.id ? "selected" : ""}`}
                    onClick={() => setSelectedChange(selectedChange?.id === c.id ? null : c)}
                  >
                    <div className="changeCardTop">
                      <span className={`badge ${levelClass(c.level)}`}>{levelKo(c.level)}</span>
                      <span className={`badge ${siteClass(c.site)}`}>{siteName(c.site)}</span>
                      <span style={{ fontSize: 11, color: "var(--sec)" }}>{c.category} · {c.field}</span>
                    </div>
                    <p className="changeSum">{c.summary || "변경 내용"}</p>
                    <p className="changeUrl">{shortUrl(c.url)}</p>
                  </button>
                  {/* 가장 최근(첫 번째) 또는 선택된 항목만 기본 펼침 */}
                  {isOpen && <ChangeDrilldown change={c} />}
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
   Pages 탭
════════════════════════════════════════════════════ */
function PagesTab({
  metricTab, pages, avgSamsung, avgApple, siteBlocks,
  selectedUrl, selectedPage, loadingPage, onPick,
}: {
  metricTab: MetricTab; pages: Record<SiteKey, PageLite[]>;
  avgSamsung: ReturnType<typeof metricAverage>; avgApple: ReturnType<typeof metricAverage>;
  siteBlocks: Record<string, AnalysisBlock>; selectedUrl: string;
  selectedPage: PageDetail | null; loadingPage: boolean; onPick: (url: string) => void;
}) {
  const pageRows = useMemo(
    () => [
      ...pages.samsung.map((p) => ({ ...p, site: "samsung" as SiteKey })),
      ...pages.apple.map((p) => ({ ...p, site: "apple" as SiteKey })),
    ],
    [pages]
  );

  return (
    <div className="panelStack">
      {/* 요약 카드 */}
      <div className="summaryCard">
        <div className="summaryTop">
          <div className="summaryText">
            <p className="summaryEyebrow">페이지별 현재 상태</p>
            <h1 className="summaryH1">{METRICS[metricTab].label} — 사이트별 비교</h1>
            <p className="summaryDesc">페이지를 선택하면 아래에 DATA/COPY/VISUAL 상세 근거가 펼쳐집니다.</p>
          </div>
        </div>
        <div className="avgGrid" style={{ marginTop: 14 }}>
          <AverageBox title="Samsung 당사" site="samsung" data={avgSamsung} metric={metricTab} />
          <AverageBox title="Apple 경쟁사" site="apple" data={avgApple} metric={metricTab} />
        </div>
      </div>

      {/* 사이트별 현행 분석 */}
      <div className="grid2">
        {(["samsung", "apple"] as SiteKey[]).map((site) => (
          <div className="card" key={site}>
            <p className="cardTitle">
              <span className={`badge ${site}`} style={{ marginRight: 6 }}>
                {site === "samsung" ? "Samsung 당사" : "Apple 경쟁사"}
              </span>
              현행 분석
            </p>
            {linesFromBlock(siteBlocks[site]).length === 0 ? (
              <p className="muted">분석 데이터가 없습니다.</p>
            ) : (
              linesFromBlock(siteBlocks[site]).map((line, i) => (
                <p className="finding" key={i}>{line}</p>
              ))
            )}
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
              <span>{tierFromUrl(p.url)}</span>
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

/* ════════════════════════════════════════════════════
   서브 컴포넌트
════════════════════════════════════════════════════ */
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
              block.narrative.map((line: string, i: number) => (
                <p className="finding" key={i}>{line}</p>
              ))
            )}
          </div>
        </details>
      ))}
    </div>
  );
}

/* ── 기준 설명 Drawer (슬라이드인, 콘텐츠 위에 겹치지 않고 레이아웃 밀어냄) */
function CriteriaDrawer({
  open, section, onClose,
}: {
  open: boolean; section: string | null; onClose: () => void;
}) {
  const target = section ? CRITERIA.find((c) => c.id === section) : null;
  const list = target ? [target] : CRITERIA;

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
              {sec.items.map((item) => (
                <div key={item.q} className="drawerItem">
                  <p className="drawerItemQ">{item.q}</p>
                  <p className="drawerItemA">{item.a}</p>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
