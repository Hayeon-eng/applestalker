"use client";
/* RegionOverview.tsx — [2026-10] 🌍 권역별 OVERVIEW  (2026-10-08 커맨드센터형으로 단순화)
   구성: ① 위 KPI 5장(툴별 숫자 하나 + 신호등) ② 가운데 지도 + 총괄 9개 말풍선 카드(🔴🟡🟢 법인 수 + 가장 급한 법인 한 줄, 지시선)
         ③ 아래 "지금 봐야 할 것" 한 줄(🔴 법인만) ④ 카드/국가 클릭 → 그 범위로 줌인(CSS transition) + 오른쪽 상세 패널, Esc/빈 곳 → 뒤로
   세계지도는 world-atlas 50m + d3-geo. 국가 색 = 담당 사이트코드들의 worst 신호등.
   데이터: GET /api/overview/regions (backend/overview_regions.py). 신호등·색은 qubiShared 공용. 추정값 없음 — 없으면 회색.
   지도: public/world/head.json + arcs-N.json + geom-N.json (world-atlas countries-50m 을 40KB 이하로 분할 — 원본 740KB 가 업로드 제한 47KB 에 걸려서). */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { geoNaturalEarth1, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { FeatureCollection, Feature, Geometry } from "geojson";
import { SEV, TL_COLOR, TL_EMOJI, TL_NONE, BLUE } from "./qubiShared";
import { Loading, EmptyState, toast } from "./uiShared";
import { SITE_GEO, countryIndex, ANTARCTICA } from "./regionGeo";

type TL = "red" | "yellow" | "green" | null;
type Tool = { tl: TL; [k: string]: any };
type Site = { sitecode: string; country: string; subs: string; region: string; tools: Record<"data" | "spec" | "static" | "hc", Tool>; overall: TL; latest_at: string | null };
type Subs = { subs: string; region: string; sitecodes: string[]; countries: string[]; tools: Record<string, TL>; overall: TL; latest_at: string | null };
type Region = { region: string; subs: string[]; overall: TL; tools: Record<string, TL> };
type Data = { generated_at: string; sites: Site[]; subs: Subs[]; regions: Region[]; distribution: Record<string, number>; apple: any };

const W = 960, H = 480;
const TOOLS: { key: "data" | "spec" | "static" | "hc"; label: string; app: "qubi" | "honeycomb" }[] = [
  { key: "data", label: "Data QA", app: "qubi" }, { key: "spec", label: "Spec QA", app: "qubi" },
  { key: "static", label: "공통페이지", app: "qubi" }, { key: "hc", label: "honeyComb", app: "honeycomb" },
];
const fill = (tl: TL) => tl ? TL_COLOR[tl] : "var(--gray-soft)";
const emoji = (tl: TL) => tl ? TL_EMOJI[tl] : TL_NONE;
const ORDER: Record<string, number> = { red: 3, yellow: 2, green: 1 };
const worst = (...tls: TL[]): TL => tls.filter(Boolean).sort((a, b) => ORDER[b!] - ORDER[a!])[0] || null;

function toolText(t: Tool, key: string): string {
  if (!t || !t.tl) return "—";
  if (key === "data") return `${t.score}%${t.gate_zero ? " · 게이트" : ""}`;
  if (key === "spec") return `C${t.critical} · W${t.warning}`;
  if (key === "static") return `${t.score ?? "—"}%`;
  if (key === "hc") return t.absent ? `미노출 ${t.absent}` : t.low ? `하단 ${t.low}` : `상단 ${(t.top1 || 0) + (t.topn || 0)}`;
  return "";
}

export default function RegionOverview({ apiBase, onHome, onGo }: { apiBase: string; onHome: () => void; onGo: (app: "applestalker" | "qubi" | "honeycomb") => void }) {
  const api = (p: string) => (apiBase === "/" ? "" : apiBase.replace(/\/$/, "")) + p;
  const [data, setData] = useState<Data | null>(null);
  const [geo, setGeo] = useState<FeatureCollection | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [level, setLevel] = useState<{ kind: "all" } | { kind: "region"; region: string } | { kind: "subs"; subs: string }>({ kind: "all" });
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const [onlyRed, setOnlyRed] = useState(false);
  const [showList, setShowList] = useState(false);
  const [hoverRegion, setHoverRegion] = useState<string | null>(null);   // 절충안: 평소 단색, 호버/줌인한 권역만 색칠
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    (async () => {
      try {
        // 지도 데이터(world-atlas 50m, 740KB)는 업로드 제한(47KB) 때문에 public/world/ 에 40KB 이하 조각(head + arcs-N + geom-N)으로 나눠 두었다 — 여기서 재조립
        // 런처는 없는 경로에 index.html 을 돌려주므로(SPA 폴백) JSON 대신 HTML 이 오면 "어느 파일이 없는지"를 바로 알려준다
        const getJson = async (url: string, cache: RequestCache) => {
          const r = await fetch(url, { cache });
          const ct = r.headers.get("content-type") || "";
          if (!r.ok || !ct.includes("json")) {
            const hint = url.startsWith("/world/") ? "프론트 빌드가 오래됐습니다 — frontend 에서 npm run build 후 desktop/frontend_out 갱신(또는 build.ps1)"
              : "백엔드가 옛 코드입니다 — backend/main.py·overview_regions.py 반영 후 프로그램 재시작";
            throw new Error(`${url} → ${r.status} ${ct.split(";")[0] || "응답 없음"}\n${hint}`);
          }
          return r.json();
        };
        const d = await getJson(api("/api/overview/regions"), "no-store");
        // 지도 데이터: ① 빌드에 포함된 public/world/ 조각 → ② 없으면 CDN(world-atlas 원본) — 저장소에 조각 파일을 안 올렸을 때의 예비 경로(인터넷 필요)
        let w: any;
        try {
          const head = await getJson("/world/head.json", "force-cache");
          const get = (name: string) => getJson(`/world/${name}.json`, "force-cache");
          const [arcParts, geomParts] = await Promise.all([
            Promise.all(Array.from({ length: head.arcs_parts || 0 }, (_, i) => get(`arcs-${i + 1}`))),
            Promise.all(Array.from({ length: head.geom_parts || 0 }, (_, i) => get(`geom-${i + 1}`))),
          ]);
          w = { ...head, arcs: arcParts.flat(), objects: { countries: { ...head.objects.countries, geometries: geomParts.flat() } } };
        } catch (localErr: any) {
          try {
            w = await getJson("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json", "force-cache");
            toast("지도 파일이 빌드에 없어 인터넷(CDN)에서 받았습니다 — frontend/public/world 폴더를 저장소에 올리면 오프라인에서도 뜹니다", "warn", 6000);
          } catch {
            throw new Error(`${String(localErr?.message || localErr).split("\n")[0]}\n빌드에 지도 파일(frontend/public/world/ 22개)이 없고, 인터넷(cdn.jsdelivr.net)도 닫혀 있습니다.\n→ GitHub 의 frontend/public/world 폴더에 head.json·arcs-1~20.json·geom-1.json 이 있는지 확인하고 Actions 를 다시 돌리세요.`);
          }
        }
        setData(d);
        const fc = feature(w, w.objects.countries) as unknown as FeatureCollection;
        fc.features = fc.features.filter((f) => String(f.id) !== ANTARCTICA && (f.properties as any)?.name !== "Ashmore and Cartier Is.");   // 호주와 같은 id(036)를 가진 무인도 제외
        setGeo(fc);
      } catch (e: any) {
        // 진단: 런처가 지금 어느 프론트 폴더를 서빙 중인지(exe 내장인지, 지도 파일이 있는지) 함께 보여준다
        let diag = "";
        try {
          const fi = await fetch(api("/api/front-info"), { cache: "no-store" });
          if (fi.ok && (fi.headers.get("content-type") || "").includes("json")) {
            const j = await fi.json();
            diag = `\n\n[서버 진단] ${j.frozen ? "exe 내장 프론트(빌드 시점에 묶임 → exe 재빌드 필요)" : "폴더 서빙"}: ${j.front_dir}\nindex.html 빌드 ${j.index_mtime || "없음"} · world/head.json ${j.world_head ? "있음" : "없음"} (조각 ${j.world_parts}개)`;
          } else diag = "\n\n[서버 진단] /api/front-info 없음 → launcher.py 도 옛 버전";
        } catch { /* 진단 실패는 무시 */ }
        setErr(String(e?.message || e) + diag);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const projection = useMemo(() => geoNaturalEarth1().fitExtent([[8, 8], [W - 8, H - 8]], { type: "Sphere" } as any), []);
  const path = useMemo(() => geoPath(projection), [projection]);
  const idx = useMemo(() => countryIndex(), []);
  const siteBy = useMemo(() => Object.fromEntries((data?.sites || []).map((s) => [s.sitecode, s])), [data]);
  const subsBy = useMemo(() => Object.fromEntries((data?.subs || []).map((s) => [s.subs, s])), [data]);

  // 국가 id → 색(그 나라를 담당하는 사이트코드들의 worst) · 법인
  const countryInfo = useCallback((id: string) => {
    const scs = idx[id] || [];
    const sites = scs.map((sc) => siteBy[sc]).filter(Boolean) as Site[];
    const tl = worst(...sites.map((s) => s.overall));
    return { scs, sites, tl, subs: sites[0]?.subs || null, region: sites[0]?.region || null };
  }, [idx, siteBy]);

  // 현재 레벨에 속한 국가 id 집합
  const focusIds = useMemo(() => {
    if (!data) return new Set<string>();
    const scs = level.kind === "all" ? Object.keys(SITE_GEO)
      : level.kind === "region" ? data.sites.filter((s) => s.region === level.region).map((s) => s.sitecode)
      : (subsBy[level.subs]?.sitecodes || []);
    return new Set(scs.flatMap((sc) => SITE_GEO[sc] || []));
  }, [data, level, subsBy]);

  // 줌 변환 — 선택된 국가들의 bbox 에 맞춘다(CSS transition 으로 "샥")
  const transform = useMemo(() => {
    if (!geo || level.kind === "all") return { k: 1, tx: 0, ty: 0 };
    const feats = geo.features.filter((f) => focusIds.has(String(f.id)));
    if (!feats.length) return { k: 1, tx: 0, ty: 0 };
    const [[x0, y0], [x1, y1]] = path.bounds({ type: "FeatureCollection", features: feats } as any);
    const dx = Math.max(x1 - x0, 40), dy = Math.max(y1 - y0, 40);
    const k = Math.min(8, 0.85 / Math.max(dx / W, dy / H));
    return { k, tx: W / 2 - k * (x0 + x1) / 2, ty: H / 2 - k * (y0 + y1) / 2 };
  }, [geo, level, focusIds, path]);

  const pick = (id: string) => {
    const ci = countryInfo(id);
    if (!ci.subs) return;
    if (level.kind === "subs" && level.subs === ci.subs) { setLevel({ kind: "region", region: ci.region! }); return; }
    setLevel({ kind: "subs", subs: ci.subs });
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setLevel((l) => l.kind === "subs" ? { kind: "region", region: subsBy[l.subs]?.region || "" } : { kind: "all" }); };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [subsBy]);

  if (err) return <div className="appShell"><div style={{ padding: 30, width: "100%" }}><EmptyState tone="error" title="권역 OVERVIEW 를 불러오지 못했습니다" desc={<span style={{ whiteSpace: "pre-line" }}>{err}</span>} action={<button className="btnSecondary" onClick={onHome}>홈으로</button>} /></div></div>;
  if (!data || !geo) return <div className="appShell"><div style={{ padding: 30, width: "100%" }}><Loading label="세계지도와 세 툴의 최신 결과를 모으는 중…" /></div></div>;

  const selSubs = level.kind === "subs" ? subsBy[level.subs] : null;
  const selRegion = level.kind === "region" ? data.regions.find((r) => r.region === level.region) : level.kind === "subs" ? data.regions.find((r) => r.region === selSubs?.region) : null;
  const hov = hover ? countryInfo(hover.id) : null;
  const hovFeat = hover ? geo.features.find((f) => String(f.id) === hover.id) : null;
  const zoomed = level.kind !== "all";
  const hovRegionName = hoverRegion || (hover ? countryInfo(hover.id).region : null);
  const MONO_MINE = "#C9CFDA", MONO_OTHER = "#E4E8EF";   // 단색 지도: 우리 사이트 있는 나라 / 없는 나라
  const sevKey = (tl: TL) => tl === "red" ? "fail" : tl === "yellow" ? "warn" : tl === "green" ? "pass" : "na";

  // ── KPI 5장: 툴마다 "숫자 하나" ──────────────────────────────────────────
  const sitesWith = (k: "data" | "spec" | "static" | "hc") => data.sites.filter((s) => s.tools[k].tl);
  const avg = (xs: number[]) => xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : null;
  const dataSites = sitesWith("data"), specSites = sitesWith("spec"), staticSites = sitesWith("static"), hcSites = sitesWith("hc");
  const kpis: { key: string; label: string; big: string; sub: string; tl: TL; app: "qubi" | "honeycomb" | "applestalker" }[] = [
    { key: "data", label: "Data QA", big: dataSites.length ? `${avg(dataSites.map((s) => s.tools.data.score))}%` : "—", sub: dataSites.length ? `${dataSites.length}개 사이트 평균 정상률 · 🔴 ${dataSites.filter((s) => s.tools.data.tl === "red").length}` : "검수 전", tl: worst(...dataSites.map((s) => s.tools.data.tl)), app: "qubi" },
    { key: "spec", label: "Spec QA", big: specSites.length ? `C ${specSites.reduce((a, s) => a + (s.tools.spec.critical || 0), 0)}` : "—", sub: specSites.length ? `Critical 합계 · Warning ${specSites.reduce((a, s) => a + (s.tools.spec.warning || 0), 0)} · ${specSites.length}개 사이트` : "검수 전", tl: worst(...specSites.map((s) => s.tools.spec.tl)), app: "qubi" },
    { key: "static", label: "공통페이지 QA", big: staticSites.length ? `${(() => { const p = staticSites.reduce((a, s) => a + (s.tools.static.pass || 0), 0), q = staticSites.reduce((a, s) => a + (s.tools.static.pass || 0) + (s.tools.static.warn || 0) + (s.tools.static.fail || 0), 0); return q ? Math.round(100 * p / q) : 0; })()}%` : "—", sub: staticSites.length ? `전체 정상률 · 오류(파싱 실패) ${staticSites.reduce((a, s) => a + (s.tools.static.fail || 0), 0)}쪽 · ${staticSites.length}개 사이트` : "검수 전", tl: worst(...staticSites.map((s) => s.tools.static.tl)), app: "qubi" },
    { key: "hc", label: "honeyComb", big: hcSites.length ? `${hcSites.filter((s) => s.tools.hc.tl === "red").length}/${hcSites.length}` : "—", sub: hcSites.length ? `미노출 국가 / 조사 국가 · ${hcSites[0]?.tools.hc.week || ""}` : "수집 전", tl: worst(...hcSites.map((s) => s.tools.hc.tl)), app: "honeycomb" },
    { key: "apple", label: "Apple Stalker", big: data.apple?.has_data ? `${data.apple.changes}건` : "—", sub: data.apple?.has_data ? `변경 · High ${data.apple.high} · Medium ${data.apple.medium} · ${data.apple.timestamp?.slice(0, 10) || ""}` : "수집 전", tl: data.apple?.has_data ? (data.apple.high > 0 ? "red" : data.apple.medium > 0 ? "yellow" : "green") : null, app: "applestalker" },
  ];

  // ── 총괄 말풍선 카드: 중심점(투영 좌표) + 좌/우 칼럼 배치 ─────────────────
  const regionCards = data.regions.map((r) => {
    const ids = new Set(data.sites.filter((s) => s.region === r.region).flatMap((s) => SITE_GEO[s.sitecode] || []));
    const feats = geo.features.filter((f) => ids.has(String(f.id)));
    const c = feats.length ? path.centroid({ type: "FeatureCollection", features: feats } as any) : [W / 2, H / 2];
    const subsList = r.subs.map((n) => subsBy[n]).filter(Boolean);
    const cnt = { red: 0, yellow: 0, green: 0, none: 0 }; subsList.forEach((s) => { cnt[s.overall || "none"]++; });
    // 가장 급한 법인 한 줄 — 🔴 우선, 그 다음 🟡; 이유는 worst 툴
    const urgent = [...subsList].sort((a, b) => (ORDER[b.overall!] || 0) - (ORDER[a.overall!] || 0))[0];
    const why = urgent && urgent.overall ? (() => { const tk = TOOLS.find((tt) => urgent.tools[tt.key] === urgent.overall); const s = urgent.sitecodes.map((sc) => siteBy[sc]).find((x) => tk && x?.tools[tk.key]?.tl === urgent.overall); return tk && s ? `${urgent.subs} · ${tk.label} ${toolText(s.tools[tk.key], tk.key)}` : urgent.subs; })() : null;
    return { r, cx: c[0], cy: c[1], cnt, why, n: subsList.length };
  });
  const leftCards = regionCards.filter((k) => k.cx < W / 2).sort((a, b) => a.cy - b.cy);
  const rightCards = regionCards.filter((k) => k.cx >= W / 2).sort((a, b) => a.cy - b.cy);
  const CARD_W = 19, CARD_H = 15; // %
  const slot = (i: number, n: number) => 4 + (i * (100 - 8 - CARD_H)) / Math.max(1, n - 1);

  // ── 지금 봐야 할 것: 🔴 법인 + 이유 ─────────────────────────────────────
  const urgentSubs = data.subs.filter((s) => s.overall === "red").map((s) => {
    const tk = TOOLS.find((tt) => s.tools[tt.key] === "red")!;
    const site = s.sitecodes.map((sc) => siteBy[sc]).find((x) => x?.tools[tk.key]?.tl === "red");
    return { s, tk, text: site ? `${tk.label} ${toolText(site.tools[tk.key], tk.key)} (${site.sitecode})` : tk.label };
  });

  const Card = ({ k, side, i, n }: { k: typeof regionCards[number]; side: "L" | "R"; i: number; n: number }) => {
    const top = slot(i, n), left = side === "L" ? 1.5 : 100 - 1.5 - CARD_W;
    const on = hovRegionName === k.r.region;
    const bigN = k.cnt.red || k.cnt.yellow; const bigTl: TL = k.cnt.red ? "red" : k.cnt.yellow ? "yellow" : k.cnt.green ? "green" : null;
    const no = String(regionCards.findIndex((x) => x.r.region === k.r.region) + 1).padStart(2, "0");
    return (
      <div className="rgGlass" onClick={(e) => { e.stopPropagation(); setLevel({ kind: "region", region: k.r.region }); }}
        onMouseEnter={() => setHoverRegion(k.r.region)} onMouseLeave={() => setHoverRegion(null)}
        style={{ position: "absolute", left: `${left}%`, top: `${top}%`, width: `${CARD_W}%`, padding: "10px 12px 9px", cursor: "pointer", zIndex: 3, transform: on ? "translateY(-2px) scale(1.02)" : "none", transition: "transform .2s, background .2s", borderLeft: `3px solid ${fill(k.r.overall)}` }}>
        <span className="rgNo">{no}</span>
        <div className="rgLabel">{k.r.region}</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
          <span className="rgBig" style={{ color: bigTl ? SEV[sevKey(bigTl)].ink : "var(--ter)" }}>{bigTl ? (bigTl === "green" ? "OK" : bigN) : "—"}</span>
          <span style={{ fontSize: 11, color: "var(--sec)", fontWeight: 600 }}>{bigTl === "red" ? "법인 오류" : bigTl === "yellow" ? "법인 확인" : bigTl === "green" ? `법인 ${k.n} 모두 정상` : "미검수"}</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 4, fontSize: 11, color: "var(--sec)" }}>
          <span>🔴 {k.cnt.red}</span><span>🟡 {k.cnt.yellow}</span><span>🟢 {k.cnt.green}</span>{k.cnt.none > 0 && <span>⚪ {k.cnt.none}</span>}<span style={{ marginLeft: "auto", color: "var(--ter)" }}>법인 {k.n}</span>
        </div>
        {k.why && k.cnt.red + k.cnt.yellow > 0 && <div style={{ fontSize: 11, color: "var(--label)", marginTop: 5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", borderTop: "1px solid rgba(0,0,0,.06)", paddingTop: 5 }}>↳ {k.why}</div>}
      </div>);
  };

  return (
    <div className="appShell rgStage" style={{ flexDirection: "column", overflow: "auto" }}>
      {/* 헤더 — 제목 · 빵부스러기 · 필터 */}
      <header className="topbar" style={{ position: "sticky", top: 0, zIndex: 5 }}>
        <div className="topbarRow" style={{ gap: 12 }}>
          <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🌍 권역 OVERVIEW</div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5 }}>
            <span onClick={() => setLevel({ kind: "all" })} style={{ cursor: "pointer", color: zoomed ? BLUE : "var(--label)", fontWeight: zoomed ? 500 : 700 }}>전체</span>
            {selRegion && <><span style={{ color: "var(--ter)" }}>›</span><span onClick={() => setLevel({ kind: "region", region: selRegion.region })} style={{ cursor: "pointer", color: level.kind === "region" ? "var(--label)" : BLUE, fontWeight: level.kind === "region" ? 700 : 500 }}>{selRegion.region}</span></>}
            {selSubs && <><span style={{ color: "var(--ter)" }}>›</span><b>{selSubs.subs}</b><span style={{ color: "var(--sec)" }}>{selSubs.countries.join(" · ")}</span></>}
            {zoomed && <span style={{ color: "var(--ter)", fontSize: 11 }}>· Esc 또는 빈 곳 클릭 → 뒤로</span>}
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center", fontSize: 12 }}>
            <span style={{ color: "var(--sec)" }}>{data.generated_at.slice(0, 16)}</span>
            <span onClick={() => setOnlyRed((v) => !v)} style={{ cursor: "pointer", padding: "3px 10px", borderRadius: 999, border: `1px solid ${onlyRed ? SEV.fail.c : "var(--line)"}`, background: onlyRed ? SEV.fail.soft : "#fff", color: onlyRed ? SEV.fail.ink : "var(--label)", fontWeight: 600 }}>🔴 빨강만</span>
            <button className="btnSecondary" style={{ fontSize: 12, padding: "4px 10px" }} onClick={() => setShowList((v) => !v)}>{showList ? "목록 닫기" : "☰ 목록"}</button>
          </div>
        </div>
      </header>

      {/* ① KPI 5장 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0,1fr))", gap: 10, padding: "12px 16px 0" }}>
        {kpis.map((k) => (
          <div key={k.key} className="rgGlass" onClick={() => onGo(k.app)} style={{ position: "relative", padding: "12px 14px 10px", cursor: "pointer", borderTop: `3px solid ${fill(k.tl)}` }} title={`${k.label} 열기`}>
            <span className="rgNo">{String(kpis.indexOf(k) + 1).padStart(2, "0")}</span>
            <div className="rgLabel" style={{ display: "flex", alignItems: "center", gap: 6 }}>{emoji(k.tl)} {k.label}</div>
            <div className="rgBig" style={{ marginTop: 6, color: k.tl ? SEV[sevKey(k.tl)].ink : "var(--ter)" }}>{k.big}</div>
            <div style={{ fontSize: 11, color: "var(--sec)", marginTop: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{k.sub}</div>
          </div>))}
      </div>

      {/* ② 지도 + 말풍선 카드 (줌인하면 카드 대신 오른쪽 패널) */}
      <div style={{ padding: "12px 16px 0", display: "grid", gridTemplateColumns: zoomed ? "minmax(0,1.7fr) minmax(300px,1fr)" : "1fr", gap: 12, alignItems: "start" }}>
        <div className="rgMapWrap" style={{ padding: 0 }}>
          <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", cursor: zoomed ? "zoom-out" : "default" }}
            onClick={(e) => { if ((e.target as Element).tagName === "svg" || (e.target as Element).getAttribute("data-bg")) setLevel((l) => l.kind === "subs" ? { kind: "region", region: subsBy[l.subs]?.region || "" } : { kind: "all" }); }}>
            <rect data-bg="1" x={0} y={0} width={W} height={H} fill="transparent" />
            <g style={{ transform: `translate(${transform.tx}px, ${transform.ty}px) scale(${transform.k})`, transformOrigin: "0 0", transition: "transform .7s cubic-bezier(.2,.8,.2,1)" }}>
              <path d={path({ type: "Sphere" } as any) || ""} fill="rgba(255,255,255,.55)" stroke="rgba(255,255,255,.9)" strokeWidth={1.2 / transform.k} />
              {geo.features.map((f) => {
                const id = String(f.id); const ci = countryInfo(id); const mine = ci.scs.length > 0;
                const inFocus = focusIds.has(id); const dim = zoomed && !inFocus;
                const red = onlyRed && ci.tl !== "red";
                const lit = mine && ((zoomed && inFocus) || (!zoomed && hovRegionName != null && ci.region === hovRegionName));   // 색이 켜지는 조건
                return <path key={id} d={path(f as Feature<Geometry>) || ""}
                  fill={lit ? fill(red ? null : ci.tl) : mine ? MONO_MINE : MONO_OTHER}
                  fillOpacity={dim ? .35 : 1}
                  stroke={hover?.id === id ? "var(--label)" : "#fff"} strokeWidth={(hover?.id === id ? 1.4 : .5) / transform.k}
                  style={{ cursor: mine ? "pointer" : "default", transition: "fill .3s, fill-opacity .3s" }}
                  onMouseMove={(e) => mine && setHover({ id, x: e.clientX, y: e.clientY })} onMouseLeave={() => setHover(null)}
                  onClick={(e) => { e.stopPropagation(); mine && pick(id); }} />;
              })}
              {geo.features.filter((f) => { const id = String(f.id); if (!(idx[id] || []).length) return false; const b = path.bounds(f as any); return (b[1][0] - b[0][0]) * (b[1][1] - b[0][1]) < 60; }).map((f) => {
                const id = String(f.id); const ci = countryInfo(id); const c = path.centroid(f as any); const dim = zoomed && !focusIds.has(id);
                const lit = (zoomed && focusIds.has(id)) || (!zoomed && hovRegionName != null && ci.region === hovRegionName);
                return <circle key={"dot" + id} cx={c[0]} cy={c[1]} r={4.5 / Math.sqrt(transform.k)} fill={lit ? fill(onlyRed && ci.tl !== "red" ? null : ci.tl) : MONO_MINE} stroke="#fff" strokeWidth={1 / transform.k} opacity={dim ? .35 : 1}
                  style={{ cursor: "pointer" }} onMouseMove={(e) => setHover({ id, x: e.clientX, y: e.clientY })} onMouseLeave={() => setHover(null)} onClick={(e) => { e.stopPropagation(); pick(id); }} />;
              })}
              {/* 총괄 중심점 + 지시선(전체 보기일 때만) */}
              {!zoomed && [...leftCards.map((k, i) => ({ k, side: "L" as const, i, n: leftCards.length })), ...rightCards.map((k, i) => ({ k, side: "R" as const, i, n: rightCards.length }))].map(({ k, side, i, n }) => {
                const topPct = slot(i, n) + CARD_H / 2; const ax = side === "L" ? (1.5 + CARD_W) / 100 * W : (100 - 1.5 - CARD_W) / 100 * W; const ay = topPct / 100 * H;
                const col = k.r.overall ? TL_COLOR[k.r.overall] : "var(--gray)"; const on = hovRegionName === k.r.region;
                return <g key={"ld" + k.r.region} style={{ pointerEvents: "none", color: col }}>
                  <path d={`M${ax},${ay} C${(ax + k.cx) / 2},${ay} ${(ax + k.cx) / 2},${k.cy} ${k.cx},${k.cy}`} fill="none" stroke={col} strokeWidth={on ? 1.4 : .8} opacity={on ? .9 : .35} style={{ transition: "opacity .25s" }} />
                  {k.r.overall && <circle className="rgPulse" cx={k.cx} cy={k.cy} r={7} fill="none" stroke={col} strokeWidth={1.5} />}
                  <circle className="rgGlow" cx={k.cx} cy={k.cy} r={on ? 6.5 : 5} fill={col} stroke="#fff" strokeWidth={1.5} style={{ transition: "r .2s" }} />
                </g>;
              })}
            </g>
          </svg>
          {!zoomed && leftCards.map((k, i) => <Card key={k.r.region} k={k} side="L" i={i} n={leftCards.length} />)}
          {!zoomed && rightCards.map((k, i) => <Card key={k.r.region} k={k} side="R" i={i} n={rightCards.length} />)}
          <div style={{ position: "absolute", left: "50%", transform: "translateX(-50%)", bottom: 8, display: "flex", gap: 10, fontSize: 11, color: "var(--sec)", background: "rgba(255,255,255,.85)", padding: "3px 10px", borderRadius: 999 }}>
            {(["green", "yellow", "red", null] as TL[]).map((tl) => <span key={String(tl)}><span style={{ display: "inline-block", width: 9, height: 9, borderRadius: 2, background: fill(tl), verticalAlign: -1, marginRight: 3 }} />{tl === "green" ? "정상" : tl === "yellow" ? "확인" : tl === "red" ? "오류" : "미검수"}</span>)}
            <span style={{ color: "var(--ter)" }}>· 카드에 마우스 → 그 권역 색칠 · 클릭 → 줌인</span>
          </div>
          {hover && hov && hovFeat && (
            <div style={{ position: "fixed", left: hover.x + 14, top: hover.y + 14, zIndex: 50, background: "#111318", color: "#fff", borderRadius: 10, padding: "8px 10px", fontSize: 12, pointerEvents: "none", minWidth: 200, boxShadow: "0 8px 24px rgba(0,0,0,.25)" }}>
              <div style={{ fontWeight: 700 }}>{(hovFeat.properties as any)?.name} <span style={{ opacity: .7, fontWeight: 400 }}>{hov.subs} · {hov.region}</span></div>
              {hov.sites.map((s) => (
                <div key={s.sitecode} style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 4 }}>
                  <span>{emoji(s.overall)}</span><b style={{ minWidth: 60 }}>{s.sitecode}</b>
                  {TOOLS.map((tt) => <span key={tt.key} title={tt.label} style={{ opacity: s.tools[tt.key].tl ? 1 : .4 }}>{emoji(s.tools[tt.key].tl)}</span>)}
                  <span style={{ opacity: .7 }}>{s.latest_at ? s.latest_at.slice(0, 10) : "검수 전"}</span>
                </div>))}
            </div>)}
        </div>

        {/* 줌인 시 오른쪽 패널 */}
        {zoomed && (
          <div className="rgGlass" style={{ position: "sticky", top: 60, padding: 14 }}>
            {selSubs ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 22 }}>{emoji(selSubs.overall)}</span>
                  <div><div style={{ fontSize: 16, fontWeight: 800 }}>{selSubs.subs}</div><div style={{ fontSize: 12, color: "var(--sec)" }}>{selSubs.region} · {selSubs.countries.join(" · ")}</div></div>
                  <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--ter)" }}>{selSubs.latest_at ? `최신 ${selSubs.latest_at.slice(0, 16)}` : "검수 전"}</span>
                </div>
                <div style={{ display: "grid", gap: 6, marginTop: 10 }}>
                  {TOOLS.map((tt) => (
                    <div key={tt.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", background: "var(--rail)", borderRadius: 8, fontSize: 12.5 }}>
                      <span>{emoji(selSubs.tools[tt.key])}</span><b style={{ minWidth: 84 }}>{tt.label}</b>
                      <span style={{ color: "var(--sec)", flex: 1 }}>{selSubs.sitecodes.map((sc) => siteBy[sc]).filter((s) => s?.tools[tt.key]?.tl).map((s) => `${s.sitecode} ${toolText(s.tools[tt.key], tt.key)}`).join(" · ") || "데이터 없음"}</span>
                      <button className="btnSecondary" style={{ fontSize: 11, padding: "3px 8px" }} onClick={() => { onGo(tt.app); toast(`${tt.label} 탭에서 ${selSubs.sitecodes.join(", ")} 를 확인하세요`, "info"); }}>이동 →</button>
                    </div>))}
                </div>
                <div style={{ fontSize: 12, color: "var(--sec)", marginTop: 12 }}>사이트코드</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                  {selSubs.sitecodes.map((sc) => { const s = siteBy[sc]; const k = sevKey(s?.overall || null); return <span key={sc} style={{ fontSize: 12, padding: "3px 9px", borderRadius: 999, background: SEV[k].soft, color: SEV[k].ink, fontWeight: 700 }}>{sc}</span>; })}
                </div>
              </>
            ) : selRegion && (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 22 }}>{emoji(selRegion.overall)}</span>
                  <div><div style={{ fontSize: 16, fontWeight: 800 }}>{selRegion.region}</div><div style={{ fontSize: 12, color: "var(--sec)" }}>법인 {selRegion.subs.length}개 — 급한 순. 클릭하면 줌인</div></div>
                </div>
                <div style={{ display: "grid", gap: 4, marginTop: 10 }}>
                  {data.subs.filter((s) => s.region === selRegion.region && (!onlyRed || s.overall === "red")).map((s) => (
                    <div key={s.subs} onClick={() => setLevel({ kind: "subs", subs: s.subs })} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px", borderRadius: 8, cursor: "pointer", background: "var(--rail)", fontSize: 12.5 }}>
                      <span>{emoji(s.overall)}</span><b style={{ minWidth: 90 }}>{s.subs}</b>
                      <span style={{ color: "var(--sec)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.sitecodes.join(" · ")}</span>
                      {TOOLS.map((tt) => <span key={tt.key} title={tt.label} style={{ opacity: s.tools[tt.key] ? 1 : .35 }}>{emoji(s.tools[tt.key])}</span>)}
                    </div>))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* ③ 지금 봐야 할 것 */}
      <div style={{ padding: "12px 16px" }}>
        <div className="rgGlass" style={{ padding: "10px 14px", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", fontSize: 12.5 }}>
          <span className="rgLabel" style={{ whiteSpace: "nowrap" }}>지금 봐야 할 것</span>
          {urgentSubs.length === 0
            ? <span style={{ color: "var(--sec)" }}>🔴 법인 없음{data.distribution.none === data.subs.length ? " — 아직 검수 결과가 없습니다. 큐비 검수 · 공통페이지 QA · honeyComb 수집을 한 번 돌리면 지도가 채워집니다." : data.distribution.yellow ? ` · 🟡 ${data.distribution.yellow}곳은 지도에서 확인` : " · 모든 법인 정상"}</span>
            : urgentSubs.slice(0, 8).map(({ s, text }) => (
              <span key={s.subs} onClick={() => setLevel({ kind: "subs", subs: s.subs })} style={{ cursor: "pointer", padding: "4px 10px", borderRadius: 999, background: SEV.fail.soft, color: SEV.fail.ink, fontWeight: 600 }}>🔴 {s.subs} <span style={{ fontWeight: 500 }}>— {text}</span></span>))}
          {urgentSubs.length > 8 && <span style={{ color: "var(--sec)" }}>외 {urgentSubs.length - 8}곳 (☰ 목록)</span>}
        </div>
      </div>

      {/* ④ 목록(토글) */}
      {showList && (
        <div style={{ padding: "0 16px 20px" }}>
          <div className="rgGlass" style={{ padding: 0, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
              <thead><tr style={{ background: "var(--rail)" }}>{["총괄", "법인", "국가", "종합", ...TOOLS.map((tt) => tt.label), "최신"].map((h) => <th key={h} style={{ textAlign: "left", padding: "8px 10px", fontSize: 11.5, color: "var(--sec)", fontWeight: 600 }}>{h}</th>)}</tr></thead>
              <tbody>
                {data.subs.filter((s) => !onlyRed || s.overall === "red").map((s) => (
                  <tr key={s.subs} onClick={() => setLevel({ kind: "subs", subs: s.subs })} style={{ cursor: "pointer", borderTop: "1px solid var(--line)", background: selSubs?.subs === s.subs ? "var(--samsung-soft)" : undefined }}>
                    <td style={{ padding: "7px 10px", color: "var(--sec)" }}>{s.region}</td>
                    <td style={{ padding: "7px 10px", fontWeight: 700 }}>{s.subs}</td>
                    <td style={{ padding: "7px 10px", color: "var(--sec)" }}>{s.countries.join(" · ")} <span style={{ color: "var(--ter)" }}>({s.sitecodes.join(", ")})</span></td>
                    <td style={{ padding: "7px 10px", fontSize: 15 }}>{emoji(s.overall)}</td>
                    {TOOLS.map((tt) => <td key={tt.key} style={{ padding: "7px 10px" }}>{emoji(s.tools[tt.key])} <span style={{ color: "var(--sec)", fontSize: 11.5 }}>{s.sitecodes.map((sc) => siteBy[sc]).filter((x) => x?.tools[tt.key]?.tl).map((x) => toolText(x.tools[tt.key], tt.key)).slice(0, 2).join(" / ")}</span></td>)}
                    <td style={{ padding: "7px 10px", color: "var(--ter)", fontSize: 11.5 }}>{s.latest_at ? s.latest_at.slice(0, 10) : "—"}</td>
                  </tr>))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
