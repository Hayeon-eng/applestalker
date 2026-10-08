"use client";
/* RegionOverview.tsx — [2026-10] 🌍 권역별 OVERVIEW
   세계지도(world-atlas 50m, d3-geo)에서 국가를 세 툴의 최신 신호등으로 칠하고, 클릭하면 그 법인(subs) 국가들로 줌인(CSS transition)
   + 오른쪽 패널에 법인 상세. 총괄(EHQ/MENA/…) 칩으로 한 단계 위 줌. 아래 "목록으로 보기" 토글은 같은 데이터의 표.
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
  const hasAny = data.distribution.red + data.distribution.yellow + data.distribution.green > 0;
  const hov = hover ? countryInfo(hover.id) : null;
  const hovFeat = hover ? geo.features.find((f) => String(f.id) === hover.id) : null;
  const visibleSubs = data.subs.filter((s) => (!onlyRed || s.overall === "red") && (level.kind !== "region" || s.region === level.region));

  return (
    <div className="appShell" style={{ flexDirection: "column", overflow: "auto" }}>
      <header className="topbar" style={{ position: "sticky", top: 0, zIndex: 5 }}>
        <div className="topbarRow" style={{ gap: 12 }}>
          <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🌍 권역 OVERVIEW</div>
          {/* 빵부스러기 */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5 }}>
            <span onClick={() => setLevel({ kind: "all" })} style={{ cursor: "pointer", color: level.kind === "all" ? "var(--label)" : BLUE, fontWeight: level.kind === "all" ? 700 : 500 }}>전체</span>
            {selRegion && <><span style={{ color: "var(--ter)" }}>›</span><span onClick={() => setLevel({ kind: "region", region: selRegion.region })} style={{ cursor: "pointer", color: level.kind === "region" ? "var(--label)" : BLUE, fontWeight: level.kind === "region" ? 700 : 500 }}>{selRegion.region}</span></>}
            {selSubs && <><span style={{ color: "var(--ter)" }}>›</span><b>{selSubs.subs}</b><span style={{ color: "var(--sec)" }}>{selSubs.countries.join(" · ")}</span></>}
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center", fontSize: 12 }}>
            <span style={{ color: "var(--sec)" }}>법인 {data.subs.length} · 🔴 {data.distribution.red} 🟡 {data.distribution.yellow} 🟢 {data.distribution.green} ⚪ {data.distribution.none}</span>
            <span onClick={() => setOnlyRed((v) => !v)} style={{ cursor: "pointer", padding: "3px 10px", borderRadius: 999, border: `1px solid ${onlyRed ? SEV.fail.c : "var(--line)"}`, background: onlyRed ? SEV.fail.soft : "#fff", color: onlyRed ? SEV.fail.ink : "var(--label)", fontWeight: 600 }}>🔴 빨강만</span>
            <button className="btnSecondary" style={{ fontSize: 12, padding: "4px 10px" }} onClick={() => setShowList((v) => !v)}>{showList ? "지도만" : "☰ 목록으로 보기"}</button>
          </div>
        </div>
        {/* 총괄 칩 */}
        <div className="topbarRow2" style={{ gap: 6, flexWrap: "wrap" }}>
          {data.regions.map((r) => { const on = level.kind !== "all" && (level.kind === "region" ? level.region : selSubs?.region) === r.region; return (
            <span key={r.region} onClick={() => setLevel(on && level.kind === "region" ? { kind: "all" } : { kind: "region", region: r.region })}
              style={{ cursor: "pointer", fontSize: 12, padding: "3px 10px", borderRadius: 999, border: on ? `1px solid ${BLUE}` : "1px solid var(--line)", background: on ? BLUE : "#fff", color: on ? "#fff" : "var(--label)", display: "inline-flex", gap: 5, alignItems: "center" }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: fill(r.overall), display: "inline-block" }} />{r.region}<span style={{ opacity: .7 }}>{r.subs.length}</span>
            </span>); })}
        </div>
      </header>

      <div style={{ padding: "12px 16px", display: "grid", gridTemplateColumns: selSubs || level.kind === "region" ? "minmax(0,1.6fr) minmax(300px,1fr)" : "1fr", gap: 12, alignItems: "start" }}>
        {/* 지도 */}
        <div className="card" style={{ padding: 8, position: "relative", overflow: "hidden", background: "var(--rail)" }}>
          {!hasAny && <div style={{ position: "absolute", top: 12, left: 12, right: 12, zIndex: 2 }}><EmptyState title="아직 검수·수집 결과가 없습니다" desc="큐비 검수, 공통페이지 QA, honeyComb 수집을 한 번 돌리면 지도가 색칠됩니다. 지금은 사이트 범위만 회색으로 표시." /></div>}
          <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", cursor: level.kind === "all" ? "default" : "zoom-out" }}
            onClick={(e) => { if ((e.target as Element).tagName === "svg" || (e.target as Element).getAttribute("data-bg")) setLevel((l) => l.kind === "subs" ? { kind: "region", region: subsBy[l.subs]?.region || "" } : { kind: "all" }); }}>
            <rect data-bg="1" x={0} y={0} width={W} height={H} fill="transparent" />
            <g style={{ transform: `translate(${transform.tx}px, ${transform.ty}px) scale(${transform.k})`, transformOrigin: "0 0", transition: "transform .7s cubic-bezier(.2,.8,.2,1)" }}>
              <path d={path({ type: "Sphere" } as any) || ""} fill="#fff" stroke="var(--line)" strokeWidth={0.8 / transform.k} />
              {geo.features.map((f) => {
                const id = String(f.id); const ci = countryInfo(id); const mine = ci.scs.length > 0;
                const inFocus = focusIds.has(id); const dim = level.kind !== "all" && !inFocus;
                const red = onlyRed && ci.tl !== "red";
                return <path key={id} d={path(f as Feature<Geometry>) || ""}
                  fill={mine ? fill(red ? null : ci.tl) : "var(--gray-soft)"}
                  fillOpacity={mine ? (dim ? .25 : 1) : (dim ? .3 : .6)}
                  stroke={hover?.id === id ? "var(--label)" : "#fff"} strokeWidth={(hover?.id === id ? 1.4 : .5) / transform.k}
                  style={{ cursor: mine ? "pointer" : "default", transition: "fill .3s, fill-opacity .3s" }}
                  onMouseMove={(e) => mine && setHover({ id, x: e.clientX, y: e.clientY })} onMouseLeave={() => setHover(null)}
                  onClick={(e) => { e.stopPropagation(); mine && pick(id); }} />;
              })}
              {/* 작은 나라 점 — 폴리곤이 작아 클릭이 어려운 곳 */}
              {geo.features.filter((f) => { const id = String(f.id); if (!(idx[id] || []).length) return false; const b = path.bounds(f as any); return (b[1][0] - b[0][0]) * (b[1][1] - b[0][1]) < 60; }).map((f) => {
                const id = String(f.id); const ci = countryInfo(id); const c = path.centroid(f as any); const dim = level.kind !== "all" && !focusIds.has(id);
                return <circle key={"dot" + id} cx={c[0]} cy={c[1]} r={4.5 / Math.sqrt(transform.k)} fill={fill(onlyRed && ci.tl !== "red" ? null : ci.tl)} stroke="#fff" strokeWidth={1 / transform.k} opacity={dim ? .3 : 1}
                  style={{ cursor: "pointer" }} onMouseMove={(e) => setHover({ id, x: e.clientX, y: e.clientY })} onMouseLeave={() => setHover(null)} onClick={(e) => { e.stopPropagation(); pick(id); }} />;
              })}
            </g>
          </svg>
          <div style={{ position: "absolute", left: 14, bottom: 10, display: "flex", gap: 10, fontSize: 11, color: "var(--sec)" }}>
            {(["green", "yellow", "red", null] as TL[]).map((tl) => <span key={String(tl)}><span style={{ display: "inline-block", width: 9, height: 9, borderRadius: 2, background: fill(tl), verticalAlign: -1, marginRight: 3 }} />{tl === "green" ? "정상" : tl === "yellow" ? "확인" : tl === "red" ? "오류" : "데이터 없음"}</span>)}
          </div>
          <div style={{ position: "absolute", right: 14, top: 10, fontSize: 11, color: "var(--ter)" }}>국가 클릭 → 법인으로 줌 · 빈 곳/Esc → 뒤로 · {data.generated_at}</div>
          {hover && hov && hovFeat && (
            <div style={{ position: "fixed", left: hover.x + 14, top: hover.y + 14, zIndex: 50, background: "#111318", color: "#fff", borderRadius: 10, padding: "8px 10px", fontSize: 12, pointerEvents: "none", minWidth: 200, boxShadow: "0 8px 24px rgba(0,0,0,.25)" }}>
              <div style={{ fontWeight: 700 }}>{(hovFeat.properties as any)?.name} <span style={{ opacity: .7, fontWeight: 400 }}>{hov.subs} · {hov.region}</span></div>
              {hov.sites.map((s) => (
                <div key={s.sitecode} style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 4 }}>
                  <span>{emoji(s.overall)}</span><b style={{ minWidth: 60 }}>{s.sitecode}</b>
                  {TOOLS.map((t) => <span key={t.key} title={t.label} style={{ opacity: s.tools[t.key].tl ? 1 : .4 }}>{emoji(s.tools[t.key].tl)}</span>)}
                  <span style={{ opacity: .7 }}>{s.latest_at ? s.latest_at.slice(0, 10) : "검수 전"}</span>
                </div>))}
            </div>)}
        </div>

        {/* 오른쪽 패널 */}
        {(selSubs || level.kind === "region") && (
          <div className="card" style={{ position: "sticky", top: 96 }}>
            {selSubs ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 22 }}>{emoji(selSubs.overall)}</span>
                  <div><div style={{ fontSize: 16, fontWeight: 800 }}>{selSubs.subs}</div><div style={{ fontSize: 12, color: "var(--sec)" }}>{selSubs.region} · {selSubs.countries.join(" · ")}</div></div>
                  <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--ter)" }}>{selSubs.latest_at ? `최신 ${selSubs.latest_at.slice(0, 16)}` : "검수 전"}</span>
                </div>
                <div style={{ display: "grid", gap: 6, marginTop: 10 }}>
                  {TOOLS.map((t) => (
                    <div key={t.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", background: "var(--rail)", borderRadius: 8, fontSize: 12.5 }}>
                      <span>{emoji(selSubs.tools[t.key])}</span><b style={{ minWidth: 80 }}>{t.label}</b>
                      <span style={{ color: "var(--sec)", flex: 1 }}>{selSubs.sitecodes.map((sc) => siteBy[sc]).filter((s) => s?.tools[t.key]?.tl).map((s) => `${s.sitecode} ${toolText(s.tools[t.key], t.key)}`).join(" · ") || "데이터 없음"}</span>
                      <button className="btnSecondary" style={{ fontSize: 11, padding: "3px 8px" }} onClick={() => { onGo(t.app); toast(`${t.label} 탭에서 ${selSubs.sitecodes.join(", ")} 를 확인하세요`, "info"); }}>이동 →</button>
                    </div>))}
                </div>
                <div style={{ fontSize: 12, color: "var(--sec)", marginTop: 12 }}>사이트코드</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                  {selSubs.sitecodes.map((sc) => { const s = siteBy[sc]; return <span key={sc} style={{ fontSize: 12, padding: "3px 9px", borderRadius: 999, background: s?.overall ? SEV[s.overall === "red" ? "fail" : s.overall === "yellow" ? "warn" : "pass"].soft : "var(--gray-soft)", color: s?.overall ? SEV[s.overall === "red" ? "fail" : s.overall === "yellow" ? "warn" : "pass"].ink : "var(--gray-ink)", fontWeight: 700 }}>{sc}</span>; })}
                </div>
              </>
            ) : selRegion && (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 22 }}>{emoji(selRegion.overall)}</span>
                  <div><div style={{ fontSize: 16, fontWeight: 800 }}>{selRegion.region}</div><div style={{ fontSize: 12, color: "var(--sec)" }}>법인 {selRegion.subs.length}개 — 클릭하면 줌인</div></div>
                </div>
                <div style={{ display: "grid", gap: 4, marginTop: 10 }}>
                  {visibleSubs.map((s) => (
                    <div key={s.subs} onClick={() => setLevel({ kind: "subs", subs: s.subs })} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px", borderRadius: 8, cursor: "pointer", background: "var(--rail)", fontSize: 12.5 }}>
                      <span>{emoji(s.overall)}</span><b style={{ minWidth: 90 }}>{s.subs}</b>
                      <span style={{ color: "var(--sec)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.sitecodes.join(" · ")}</span>
                      {TOOLS.map((t) => <span key={t.key} title={t.label} style={{ opacity: s.tools[t.key] ? 1 : .35 }}>{emoji(s.tools[t.key])}</span>)}
                    </div>))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Apple Stalker 글로벌 카드 */}
      <div style={{ padding: "0 16px 12px" }}>
        <div className="card" style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", fontSize: 12.5 }}>
          <span style={{ fontSize: 18 }}>🍎</span><b>Apple Stalker</b>
          {data.apple?.has_data
            ? <span style={{ color: "var(--sec)" }}>{data.apple.timestamp} · 변경 {data.apple.changes}건 (High {data.apple.high} · Medium {data.apple.medium}) · {data.apple.sites?.length}개 사이트 — 권역 개념이 없는 경쟁사 모니터링이라 지도에는 안 올립니다</span>
            : <span style={{ color: "var(--sec)" }}>아직 수집 결과 없음</span>}
          <button className="btnSecondary" style={{ marginLeft: "auto", fontSize: 12, padding: "4px 10px" }} onClick={() => onGo("applestalker")}>열기 →</button>
        </div>
      </div>

      {/* 목록 */}
      {showList && (
        <div style={{ padding: "0 16px 20px" }}>
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
              <thead><tr style={{ background: "var(--rail)" }}>{["총괄", "법인", "국가", "종합", ...TOOLS.map((t) => t.label), "최신"].map((h) => <th key={h} style={{ textAlign: "left", padding: "8px 10px", fontSize: 11.5, color: "var(--sec)", fontWeight: 600 }}>{h}</th>)}</tr></thead>
              <tbody>
                {data.subs.filter((s) => !onlyRed || s.overall === "red").map((s) => (
                  <tr key={s.subs} onClick={() => setLevel({ kind: "subs", subs: s.subs })} style={{ cursor: "pointer", borderTop: "1px solid var(--line)", background: selSubs?.subs === s.subs ? "var(--samsung-soft)" : undefined }}>
                    <td style={{ padding: "7px 10px", color: "var(--sec)" }}>{s.region}</td>
                    <td style={{ padding: "7px 10px", fontWeight: 700 }}>{s.subs}</td>
                    <td style={{ padding: "7px 10px", color: "var(--sec)" }}>{s.countries.join(" · ")} <span style={{ color: "var(--ter)" }}>({s.sitecodes.join(", ")})</span></td>
                    <td style={{ padding: "7px 10px", fontSize: 15 }}>{emoji(s.overall)}</td>
                    {TOOLS.map((t) => <td key={t.key} style={{ padding: "7px 10px" }}>{emoji(s.tools[t.key])} <span style={{ color: "var(--sec)", fontSize: 11.5 }}>{s.sitecodes.map((sc) => siteBy[sc]).filter((x) => x?.tools[t.key]?.tl).map((x) => toolText(x.tools[t.key], t.key)).slice(0, 2).join(" / ")}</span></td>)}
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
