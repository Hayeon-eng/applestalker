"use client";
/**
 * QubiApp.tsx — 큐비 🐝 (QA Bee) 독립 앱
 * 탭: [스키마 QA] [스펙 QA] · 제품×페이지타입 선택 · 입력 3종(붙여넣기/파일/링크)
 * 스펙 관리(메인 표) · 스키마 룰 추가(타입 드롭다운) · Quick View + 권역 신호등
 */
import { useEffect, useMemo, useRef, useState, Fragment } from "react";
import { Finding, PageResult, SiteRow, CatalogItem, Product, SEV, HONEY, PAGE_TYPES, pageTypesFor, family, tierOf, inputStyle, sel } from "./qubiShared";
import { CriteriaPanel, ScorePanel, QuickView } from "./QubiSections";
import { HtmlQaSummary, SiteOverview } from "./QubiDataQa";
import { SpecV2Panel, DictionaryPanel, SpecV2RuleTable, SpecV2Criteria, SpecV2Score } from "./QubiSpecQa";

export default function QubiApp({ apiBase = "", onHome }: { apiBase?: string; onHome?: () => void }) {
  const [tab, setTab] = useState<"schema" | "copy">("schema");
  const [product, setProduct] = useState("galaxy-s26-ultra");
  const [v2Products, setV2Products] = useState<string[]>([]); // Rule DB(V2)가 있는 제품 — 기준/점수 패널을 V2판으로 게이트
  const isV2 = v2Products.includes(product);
  const [pageType, setPageType] = useState("PDP");
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set()); // 배치 크롤용 제품 멀티선택 (비면 전체)
  const [selectedPageTypes, setSelectedPageTypes] = useState<Set<string>>(new Set(["PDP"])); // 배치 크롤용 타입 멀티선택
  const [results, setResults] = useState<PageResult[]>([]);
  const [qaExpandedSite, setQaExpandedSite] = useState<string | null>(null); // HTML QA 일괄검수 드릴다운(사이트별 펼침)
  const [rules, setRules] = useState<any>(null);
  const [showRules, setShowRules] = useState(false); // 검수 기준은 기본 숨김 — "ⓘ 검수 기준" 클릭 시 뿅 등장
  const rulesRef = useRef<HTMLDivElement | null>(null);
  const [rulesFlash, setRulesFlash] = useState(false);
  const openCriteria = () => {
    setShowRuleAdd(false);
    setShowScore(false);   // 점수 패널은 닫고
    setShowRules(true);
    // 패널로 스크롤 + 잠깐 하이라이트(뿅!)
    setTimeout(() => {
      rulesRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      setRulesFlash(true);
      setTimeout(() => setRulesFlash(false), 1200);
    }, 60);
  };
  const openScore = () => {
    setShowRuleAdd(false);
    setShowRules(false);   // 검수 기준은 닫고
    setShowScore(true);
    setTimeout(() => {
      scoreRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 60);
  };
  const hideAll = () => { setShowRules(false); setShowScore(false); };
  const [showRuleAdd, setShowRuleAdd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [online, setOnline] = useState<boolean | null>(null);

  const [regionsMap, setRegionsMap] = useState<Record<string, SiteRow[]>>({});
  const [pageCount, setPageCount] = useState(0);
  const [selectedRegions, setSelectedRegions] = useState<Set<string>>(new Set()); // 권역 다중선택(비었으면 전체)
  const [showScore, setShowScore] = useState(false); // 점수 계산 로직 패널
  const scoreRef = useRef<HTMLDivElement>(null);
  const regionRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const scrollToRegion = (region: string) => {
    const el = regionRefs.current[region];
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const [selectedSites, setSelectedSites] = useState<Set<string>>(new Set()); // 사이트 개별 다중선택(우선)
  const [progress, setProgress] = useState({ active: false, done: 0, total: 0, label: "" });

  const [sitesOpen, setSitesOpen] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const xlsxFileRef = useRef<HTMLInputElement>(null);

  // 스펙 관리
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [specProduct, setSpecProduct] = useState("galaxy-s26-ultra");
  const [specs, setSpecs] = useState<any[]>([]);
  const [newProd, setNewProd] = useState("");
  const [specForm, setSpecForm] = useState({ category: "", value: "", unit: "" });
  const [schemaTypes, setSchemaTypes] = useState<string[]>([]);
  const [ruleForm, setRuleForm] = useState({ block_type: "", property: "", value: "", value_kind: "exists", nested: "", kind: "spec", token: "" });

  // Quick View
  const [quickOpen, setQuickOpen] = useState(false);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [qCountry, setQCountry] = useState("전체");
  const [qDetail, setQDetail] = useState<string | null>(null);

  // 검수 이력
  const [history, setHistory] = useState<any[]>([]);
  const [runId, setRunId] = useState<string | null>(null); // 현재 화면에 표시 중인 결과의 run_id — Excel/메일이 화면과 같은 데이터를 받도록 서버에 전달
  const [overview, setOverview] = useState<any>(null); // 전사이트 현황(각 권역 최신 검수 AEO 평균)

  const api = (p: string) => `${apiBase}${p}`;
  const flash = (m: string) => { setOk(m); setTimeout(() => setOk(""), 2500); };
  const J = (b: any) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });

  useEffect(() => {
    fetch(api("/api/health")).then((r) => setOnline(r.ok)).catch(() => setOnline(false));
    loadSites(); loadCatalog(); loadProducts(); loadSpecs("galaxy-s26-ultra"); loadHistory(); loadOverview();
    fetch(api("/api/qb/spec-rules/products")).then((r) => r.json())
      .then((d) => {
        const codes = (d.products || []).map((p: any) => p.product);
        if (codes.length) setV2Products((prev) => Array.from(new Set([...prev, ...codes])));
      }).catch(() => {});
  }, []);
  useEffect(() => { loadRules(); setSpecProduct(product); }, [product, pageType]);
  useEffect(() => { if (!pageTypesFor(product).includes(pageType)) setPageType("PDP"); }, [product]);
  useEffect(() => { loadSpecs(specProduct); }, [specProduct]);

  async function loadSites() { try { const d = await (await fetch(api("/api/qb/sites"))).json(); setRegionsMap(d.regions || {}); setPageCount(d.page_count || 0); } catch { /* */ } }
  async function loadCatalog() { try { setCatalog((await (await fetch(api("/api/qb/spec-catalog"))).json()).catalog || []); } catch { /* */ } }
  async function loadProducts() {
    try {
      const ps = (await (await fetch(api("/api/qb/products"))).json()).products || [];
      setProducts(ps);
      // [견고성] /spec-rules/products 호출이 실패해도(배포 불일치 등) 제품 목록의 v2 플래그로 게이트가 열리게 병합
      const flagged = ps.filter((p: any) => p.v2).map((p: any) => p.code);
      if (flagged.length) setV2Products((prev) => Array.from(new Set([...prev, ...flagged])));
    } catch { /* */ }
  }
  async function loadSpecs(p: string) { try { setSpecs((await (await fetch(api(`/api/qb/specs?product=${encodeURIComponent(p)}`))).json()).specs || []); } catch { /* */ } }
  async function loadRules() {
    try { const d = await (await fetch(api(`/api/qb/rules?product=${family(product)}&page_type=${pageType}&market_product=${encodeURIComponent(product)}`))).json(); setRules(d); if (d.schema_types) setSchemaTypes(d.schema_types); } catch (e: any) { setErr(String(e)); }
  }
  async function loadHistory() { try { setHistory((await (await fetch(api("/api/qb/history"))).json()).history || []); } catch { /* */ } }
  async function loadOverview() { try { setOverview(await (await fetch(api("/api/qb/overview"))).json()); } catch { /* */ } }
  const openHistory = async (id: string) => {
    try { const d = await (await fetch(api(`/api/qb/history/${id}`))).json(); setResults(d.results || []); setRunId(id); flash(`이력 ${id} 불러옴`); }
    catch { setErr("이력 불러오기 실패"); }
  };
  const removeHistory = async (id: string) => { await fetch(api("/api/qb/history/remove"), J({ run_id: id })); loadHistory(); };

  const allSites = useMemo(() => Object.entries(regionsMap).flatMap(([rg, arr]) => arr.map((s) => ({ ...s, region: rg }))), [regionsMap]);
  const regionNames = useMemo(() => Object.keys(regionsMap), [regionsMap]);

  // ── 검수 ──
  // Apple Stalker의 trigger-crawl/all + crawl-progress 패턴과 동일:
  // /run 은 즉시 반환(started)되고, 실제 크롤은 서버 백그라운드에서 동시성 제한으로
  // '나눠서' 진행된다. 프론트는 SSE로 진행률만 구독하다가 done 이벤트에서 결과를 받아온다.
  // → 91개를 한 요청에 다 물지 않으므로 'Failed to fetch'(게이트웨이 타임아웃)가 사라진다.
  const targetCodes = useMemo(() => {
    if (selectedSites.size > 0) return Array.from(selectedSites);
    if (selectedRegions.size > 0) return allSites.filter((s) => selectedRegions.has(s.region || "")).map((s) => s.sitecode);
    return allSites.map((s) => s.sitecode); // 아무것도 안 고르면 전체
  }, [selectedSites, selectedRegions, allSites]);

  const runByRegion = async () => {
    if (busy) return;
    setBusy(true); setErr(""); setResults([]); setRunId(null);
    const codes = targetCodes;
    if (codes.length === 0) { setErr("검수할 사이트를 하나 이상 선택하세요."); setBusy(false); return; }
    const label = selectedSites.size ? `사이트 ${codes.length}개` : (selectedRegions.size ? Array.from(selectedRegions).join(", ") : "전체");
    setProgress({ active: true, done: 0, total: codes.length, label });
    try {
      const r = await fetch(api("/api/qb/run"), J({
        product: family(product), market_product: product, sitecodes: codes,
        products: Array.from(selectedProducts),
        page_types: Array.from(selectedPageTypes),
      }));
      if (r.status === 501) throw new Error("크롤러 미연결 — 붙여넣기/파일/링크 검수를 이용하세요.");
      if (r.status === 409) {
        // 이전 검수가 서버에 갇힌 상태일 수 있음 — 강제 해제 후 1회 재시도
        await fetch(api("/api/qb/run-reset"), { method: "POST" }).catch(() => {});
        const retry = await fetch(api("/api/qb/run"), J({
          product: family(product), market_product: product, sitecodes: codes,
          products: Array.from(selectedProducts), page_types: Array.from(selectedPageTypes),
        }));
        if (!retry.ok) throw new Error(retry.status === 409 ? "이미 검수가 진행 중이에요. 잠시 후 다시 시도하세요." : `실행 실패 (${retry.status})`);
      } else if (!r.ok) {
        throw new Error(`실행 실패 (${r.status})`);
      }
      await new Promise<void>((resolve, reject) => {
        const es = new EventSource(api("/api/qb/run-progress"));
        const timeout = setTimeout(() => { es.close(); reject(new Error("진행이 오래 걸려요 — 검수 이력에서 완료 여부를 확인해보세요.")); }, 20 * 60 * 1000);
        es.onmessage = (ev) => {
          try {
            const d = JSON.parse(ev.data);
            if (d.type === "start") setProgress((p) => ({ ...p, total: d.total || p.total, done: 0 }));
            else if (d.type === "page_done") setProgress((p) => ({ ...p, done: d.done ?? p.done + 1 }));
            else if (d.type === "done") {
              clearTimeout(timeout); es.close();
              fetch(api(`/api/qb/history/${encodeURIComponent(d.run_id)}`))
                .then((rr) => rr.ok ? rr.json() : null)
                .then((dd) => { if (dd?.results) { setResults(dd.results); setRunId(d.run_id); } resolve(); })
                .catch(() => resolve());
            } else if (d.type === "status" && d.crawling === false) { clearTimeout(timeout); es.close(); resolve(); }
            else if (d.type === "error") { clearTimeout(timeout); es.close(); reject(new Error(d.message || "크롤 중 오류가 발생했어요.")); }
          } catch { /* heartbeat 무시 */ }
        };
        es.onerror = () => { clearTimeout(timeout); es.close(); reject(new Error("진행 상황 연결이 끊겼어요 — 완료 후 검수 이력에서 확인하세요.")); };
      });
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); setProgress((p) => ({ ...p, active: false })); loadHistory(); loadOverview(); }
  };

  const downloadBlob = async (url: string, body: any, filename: string) => {
    try {
      const r = body === null
        ? await fetch(api(url))
        : await fetch(api(url), J(body));
      if (!r.ok) throw new Error(`서버 오류 (${r.status})`);
      const blob = await r.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href; a.download = filename; document.body.appendChild(a); a.click();
      a.remove(); setTimeout(() => URL.revokeObjectURL(href), 1500);
    } catch (e: any) {
      setErr(`${filename} 다운로드 실패 — ${e.message || e}`);
    }
  };
  const reportQs = () => (runId ? `?run_id=${encodeURIComponent(runId)}` : ""); // 화면에 보이는 이력과 동일 데이터 보장
  const emailQs = () => { // 메일은 현재 탭 내용만 — schema/copy 중 지금 보는 것만 복사
    const base = runId ? `?run_id=${encodeURIComponent(runId)}` : "?";
    return `${base}${base.endsWith("?") ? "" : "&"}tab=${tab}`;
  };
  const downloadXlsx = async () => {
    if (!results.length) { setErr("먼저 검수를 실행한 뒤 Excel을 받을 수 있어요."); return; }
    await downloadBlob(`/api/qb/report.xlsx${reportQs()}`, null, "qubi_qa_report.xlsx");
  };
  const copyEmail = async () => {
    if (!results.length) { setErr("먼저 검수를 실행한 뒤 메일 본문을 복사할 수 있어요."); return; }
    try {
      // Apple Stalker와 동일: 본문 없는 GET(CORS preflight 회피). run_id가 있으면 그 이력을, 없으면 서버가 든 마지막 결과를 받음
      const r = await fetch(api(`/api/qb/email-draft${emailQs()}`), { cache: "no-store" });
      if (!r.ok) throw new Error(`서버 오류 (${r.status})`);
      const body = await r.text();
      if (navigator.clipboard && "write" in navigator.clipboard && typeof ClipboardItem !== "undefined") {
        await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([body], { type: "text/html" }), "text/plain": new Blob([body], { type: "text/plain" }) })]);
        flash("메일 본문 복사됨 — 붙여넣기 🐝");
      } else if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(body); flash("메일 본문 복사됨 🐝"); }
      else { const w = window.open("", "_blank"); if (w) { w.document.write(body); w.document.close(); } flash("새 탭에서 복사하세요"); }
    } catch (e: any) { setErr(`메일 복사 실패 — ${e.message || e}`); }
  };

  // ── URL 관리 ──
  const addUrl = async () => { if (!newUrl.trim()) return; await fetch(api("/api/qb/sites/add"), J({ url: newUrl.trim() })); setNewUrl(""); loadSites(); flash("URL 추가"); };
  const removeUrl = async (sc: string) => { await fetch(api("/api/qb/sites/remove"), J({ sitecode: sc })); loadSites(); };
  const downloadTemplate = () => downloadBlob("/api/qb/sites/template.xlsx", null, "qubi_url_template.xlsx");
  const uploadTemplate = async (file: File) => {
    const b64: string = await new Promise((res, rej) => { const rd = new FileReader(); rd.onload = () => res(String(rd.result)); rd.onerror = rej; rd.readAsDataURL(file); });
    const d = await (await fetch(api("/api/qb/sites/upload"), J({ b64 }))).json(); loadSites(); flash(`${d.added || 0}개 URL 추가`);
  };

  // ── 스펙/제품/룰 ──
  const pickCatalog = (cat: string) => { const c = catalog.find((x) => x.category === cat); setSpecForm({ category: cat, value: c?.ex_value || "", unit: c?.ex_unit || "" }); };
  const addSpec = async () => { if (!specForm.category || !specForm.value) return; await fetch(api("/api/qb/specs/add"), J({ product: specProduct, ...specForm })); setSpecForm({ category: "", value: "", unit: "" }); loadSpecs(specProduct); flash("스펙 추가"); };
  const removeSpec = async (i: number) => { await fetch(api("/api/qb/specs/remove"), J({ index: i, product: specProduct })); loadSpecs(specProduct); };
  const addProduct = async () => { if (!newProd.trim()) return; await fetch(api("/api/qb/products/add"), J({ product: newProd.trim() })); const p = newProd.trim(); setNewProd(""); await loadProducts(); setSpecProduct(p); flash("제품 추가"); };
  const addRule = async () => {
    if (tab === "schema") {
      if (!ruleForm.block_type || !ruleForm.property) return;
      await fetch(api("/api/qb/rules/schema/add"), J({
        product: family(product), page_type: pageType, block_type: ruleForm.block_type, property: ruleForm.property,
        value: ruleForm.value, value_kind: ruleForm.value_kind, nested: ruleForm.nested,
      }));
    } else {
      if (!ruleForm.token) return;
      await fetch(api("/api/qb/rules/copy/add"), J({ product, kind: ruleForm.kind, token: ruleForm.token }));
    }
    setRuleForm({ ...ruleForm, property: "", value: "", token: "" }); loadRules(); flash("룰 추가됨");
  };

  // 현재 탭 오류 행 — Quick View·flat 테이블 공용.
  // [V2 정합] 스펙 탭에서 결과가 spec_v2(Rule DB 판정)를 가지면 화면(SpecV2Panel)과 동일한
  // 소스에서 행을 만든다: Critical=룰 fail, Warning=미등록 표현(candidates).
  // N/A(못 찾음·페이지타입 미적용)는 오류가 아니므로 Quick View에 싣지 않는다.
  // spec_v2가 없는 제품(S26 등)만 기존 copy findings 폴백 — 메인 화면과 같은 분기 원칙.
  const rows = useMemo(() => {
    const out: { r: PageResult; f: Finding; item: string }[] = [];
    for (const r of results) {
      if (tab === "schema") {
        // [정합] 화면(HtmlQaDetail)은 '번역 확인 필요'처럼 실제 오류(값불일치·속성누락·@id/hasPart·name이슈)가
        // 없는 안내성 finding은 판정근거에서 제외한다. Quick View도 같은 기준을 써야 100점인데 오류로 뜨는 불일치가 사라진다.
        for (const f of r.schema?.findings || []) {
          if (f.status !== "fail" && f.status !== "warn") continue;
          const hasReal = (f.val_mismatch || []).length || (f.missing_props || []).length ||
                          (f.name_issue || []).length || f.id_mismatch || (f.haspart_missing || []).length;
          const onlyTranslate = (f.translate_confirm || []).length && !hasReal;
          if (onlyTranslate) continue;
          out.push({ r, f, item: f.block || f.token || f.category || "" });
        }
      } else if (r.spec_v2) {
        for (const it of r.spec_v2.items || []) {
          if (it.status !== "fail") continue;
          out.push({
            r, item: it.attribute,
            f: { status: "fail", category: it.category, region: it.section,
                 as_is: it.found ? `현재 '${it.found}'` : (it.message || "값 불일치"),
                 to_be: `기준 ${it.expected}${it.unit ? ` ${it.unit}` : ""}${it.fix_guide ? ` — ${it.fix_guide}` : ""}`,
                 expected: `${it.expected}${it.unit ? ` ${it.unit}` : ""}`,
                 found: it.found ? [String(it.found)] : [] },
          });
        }
        for (const c of r.spec_v2.candidates || []) {
          out.push({
            r, item: c.alias,
            f: { status: "warn", category: "Dictionary",
                 as_is: `미등록 표현 발견: '${c.alias}'`,
                 to_be: "번역/표기 확인 후 [Dictionary 추가]로 승인하면 다음 검수부터 정식 판정" },
          });
        }
      } else {
        // 스펙 탭인데 spec_v2가 없는 결과(seed 미등록 제품 등) → 구 카피엔진 폴백을 쓰지 않는다.
        // (구 엔진은 페이지의 임의 숫자를 스펙으로 오인해 허위 오류를 만들었음 — 표시 안 함)
      }
    }
    const rank: Record<string, number> = { fail: 0, warn: 1, na: 2 };
    return out.sort((a, b) => (rank[a.f.status] ?? 3) - (rank[b.f.status] ?? 3));
  }, [results, tab]);
  const failCount = rows.filter((x) => x.f.status === "fail").length;

  // 권역 신호등
  // 권역 신호등 — [V2 정합] 현재 탭 기준으로만 집계(기존엔 schema+copy 합산이라 탭 화면과 불일치).
  // 스펙 탭: spec_v2 있으면 summary(critical/warning) 그대로 — SpecV2Panel 종합 배너와 같은 숫자.
  // 한 결과에서 스키마/스펙 각각의 (fail,warn) 집계 헬퍼 — 두 곳(현재탭 신호등·양탭 신호등)에서 공용
  const schemaCount = (r: any) => {
    let fail = 0, warn = 0;
    for (const f of r.schema?.findings || []) {
      if (f.status !== "fail" && f.status !== "warn") continue;
      const hasReal = (f.val_mismatch || []).length || (f.missing_props || []).length ||
                      (f.name_issue || []).length || f.id_mismatch || (f.haspart_missing || []).length;
      if ((f.translate_confirm || []).length && !hasReal) continue;  // 안내성 제외
      if (f.status === "fail") fail++; else warn++;
    }
    return { fail, warn };
  };
  const specCount = (r: any) => {
    if (r.spec_v2) return { fail: r.spec_v2.summary?.critical || 0, warn: r.spec_v2.summary?.warning || 0 };
    return { fail: 0, warn: 0 };  // seed 미등록 → 구 카피엔진 쓰지 않음(허위 카운트 방지)
  };
  // 현재 탭 기준 권역 신호등 (Quick View 오류목록·요약과 동일 기준)
  const regionTier = useMemo(() => {
    const m: Record<string, { fail: number; warn: number }> = {};
    for (const r of results) {
      const rg = r.region || "기타"; m[rg] = m[rg] || { fail: 0, warn: 0 };
      const c = tab === "schema" ? schemaCount(r) : specCount(r);
      m[rg].fail += c.fail; m[rg].warn += c.warn;
    }
    return m;
  }, [results, tab]);
  // 두 탭 동시 표시용 — 한 사이트가 "스키마 초록·스펙 빨강"인 걸 한눈에
  const regionTierBoth = useMemo(() => {
    const m: Record<string, { schema: { fail: number; warn: number }; spec: { fail: number; warn: number } }> = {};
    for (const r of results) {
      const rg = r.region || "기타";
      m[rg] = m[rg] || { schema: { fail: 0, warn: 0 }, spec: { fail: 0, warn: 0 } };
      const sc = schemaCount(r), sp = specCount(r);
      m[rg].schema.fail += sc.fail; m[rg].schema.warn += sc.warn;
      m[rg].spec.fail += sp.fail; m[rg].spec.warn += sp.warn;
    }
    return m;
  }, [results]);

  const countries = useMemo(() => Array.from(new Set(results.map((r) => r.country).filter(Boolean))) as string[], [results]);
  const quickRows = useMemo(() => rows.filter((x) => qCountry === "전체" || x.r.country === qCountry), [rows, qCountry]);

  // QubiSections.tsx 로 분리한 렌더 블록에 상태·핸들러를 한 번에 주입
  const ctx = {
    tab, product, pageType, rules, showRules, showRuleAdd, rulesRef, rulesFlash, qaExpandedSite, setQaExpandedSite, overview,
    showScore, scoreRef, regionRefs, scrollToRegion,
    specProduct, setSpecProduct, products, newProd, setNewProd, addProduct, v2Products, isV2,
    specs, removeSpec, catalog, specForm, pickCatalog, setSpecForm, addSpec,
    ruleForm, setRuleForm, schemaTypes, addRule,
    quickOpen, setQuickOpen, results, regionTier, regionTierBoth, countries, qCountry, setQCountry,
    quickRows, qDetail, setQDetail,
  };

  return (
    <div className="appShell">
      {/* ── 사이드바 ── */}
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🐝 큐비</div>
        <div className="brandSub">QA의 사촌, 큐비 — 닷컴을 붕붕 돌며 스펙을 지켜요</div>
        <div className={`connBadge ${online === true ? "ok" : "bad"}`}><span className="connDot" />{online === null ? "확인 중" : online ? "백엔드 연결됨" : "연결 안 됨"}</div>

        <div className="sideScroll">
          <div className="sideLabel">URL 관리</div>
          <div style={{ padding: "0 10px", marginBottom: 6 }}>
            <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="https://www.samsung.com/…/compare/" style={{ ...inputStyle, width: "100%" }} />
            <button onClick={addUrl} style={{ marginTop: 6, fontSize: 12, fontWeight: 700, color: "#0A66E0", background: "none", border: "none", cursor: "pointer" }}>＋ URL 추가</button>
          </div>
          <div style={{ padding: "0 10px 8px", display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button onClick={downloadTemplate} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }}>⬇ URL 템플릿</button>
            <button onClick={() => xlsxFileRef.current?.click()} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }}>⬆ 템플릿 업로드</button>
            <input ref={xlsxFileRef} type="file" accept=".xlsx" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadTemplate(f); e.currentTarget.value = ""; }} />
          </div>
          <div className="sideLabel" style={{ cursor: "pointer" }} onClick={() => setSitesOpen((o) => !o)}>{sitesOpen ? "▾" : "▸"} 모니터링 URL 목록 <span style={{ color: "var(--sec)" }}>{allSites.length}개</span></div>
          {sitesOpen && allSites.map((s) => (
            <div key={s.sitecode} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 10px", fontSize: 11.5 }}>
              <span title={s.url}>
                <span style={{ fontWeight: 600 }}>{s.sitecode}</span>
                {s.region && <span style={{ fontSize: 10, background: "#EEF1F6", color: "#475467", borderRadius: 4, padding: "1px 5px", marginLeft: 5 }}>{s.region}</span>}
                {s.country && <span style={{ color: "var(--sec)", marginLeft: 5 }}>{s.country}</span>}
              </span>
              <span role="button" onClick={() => removeUrl(s.sitecode)} style={{ cursor: "pointer", color: "var(--high)", fontSize: 11 }}>삭제</span>
            </div>
          ))}

          {/* 검수 이력 */}
          <div className="sideLabel" style={{ marginTop: 14 }}>검수 이력 <span style={{ color: "var(--sec)" }}>{history.length}건</span></div>
          {history.length === 0 && <p style={{ padding: "2px 10px", fontSize: 11.5, color: "var(--sec)" }}>아직 저장된 검수가 없어요</p>}
          {history.map((h) => (
            <div key={h.run_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 10px", fontSize: 11.5, cursor: "pointer" }} onClick={() => openHistory(h.run_id)}>
              <span>
                <span style={{ fontWeight: 600 }}>{h.at?.slice(5, 16) || h.run_id}</span>
                <span style={{ color: "var(--sec)" }}> · {h.pages}p</span>
                {h.fail > 0 && <span style={{ color: "var(--high)" }}> · 오류 {h.fail}</span>}
              </span>
              <span role="button" onClick={(e) => { e.stopPropagation(); removeHistory(h.run_id); }} style={{ color: "var(--high)", fontSize: 11 }}>삭제</span>
            </div>
          ))}
        </div>
      </aside>

      {/* ── 메인 ── */}
      <div className="mainArea">
        <header className="topbar">
          <div className="topbarRow1">
            <div className="tabGroup">
              <button className={`tabBtn ${tab === "schema" ? "on" : ""}`} onClick={() => setTab("schema")}>DATA QA</button>
              <button className={`tabBtn ${tab === "copy" ? "on" : ""}`} onClick={() => setTab("copy")}>스펙 QA</button>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              <button className="toolBtn" onClick={() => (showRules ? setShowRules(false) : openCriteria())}>
                {showRules ? "ⓘ 검수 기준 숨기기" : "ⓘ 검수 기준 보기"}
              </button>
              <button className="toolBtn" onClick={() => (showScore ? setShowScore(false) : openScore())}>
                {showScore ? "ⓘ 점수 계산 숨기기" : "ⓘ 점수 계산 보기"}
              </button>
              <button className="toolBtn" onClick={copyEmail}>✉ 메일 복사</button>
              <button className="toolBtn" onClick={downloadXlsx}>📊 Excel</button>
            </div>
          </div>
        </header>

        <div className="contentScroll" style={{ padding: "20px 28px 80px" }}>
          <h2 style={{ fontSize: 18, margin: "0 0 4px" }}>
            {tab === "schema" ? "DATA QA" : "스펙 QA"} <span style={{ fontSize: 12, fontWeight: 400, color: "var(--sec)" }}>
              {tab === "schema" ? "스키마 · H태그 · Meta title/description — GEO 관점 종합 검수" : "스펙 값·고유명사 정확성 (번역 대응)"}</span>
          </h2>

          <SiteOverview ctx={ctx} />

          {/* 제품 · 페이지타입 (여러 개 선택 가능 — 배치 크롤 대상) */}
          <div style={{ display: "flex", gap: 6, alignItems: "center", margin: "10px 0 4px", flexWrap: "wrap" }}>
            <span style={{ fontSize: 12.5, color: "var(--sec)" }}>제품:</span>
            {products.filter((p) => !p.spec_only).map((p) => {
              const on = selectedProducts.has(p.code);
              return <button key={p.code} onClick={() => {
                setProduct(p.code);
                setSelectedProducts((prev) => { const n = new Set(prev); n.has(p.code) ? n.delete(p.code) : n.add(p.code); return n; });
              }} style={sel(p.code, on)}>{on ? "✓ " : ""}{p.label}</button>;
            })}
            <span style={{ fontSize: 12.5, color: "var(--sec)", marginLeft: 10 }}>페이지타입:</span>
            {PAGE_TYPES.map((p) => {
              const on = selectedPageTypes.has(p);
              return <button key={p} onClick={() => {
                setPageType(p);
                setSelectedPageTypes((prev) => { const n = new Set(prev); n.has(p) ? (n.size > 1 && n.delete(p)) : n.add(p); return n; });
              }} style={sel(p, on)}>{on ? "✓ " : ""}{p}</button>;
            })}
          </div>

          {ok && <div style={{ background: "#ECFDF3", color: "#067647", padding: "8px 12px", borderRadius: 8, fontSize: 13, margin: "8px 0" }}>{ok}</div>}
          {err && <div style={{ background: "#FEF3F2", color: "#B42318", padding: 10, borderRadius: 8, fontSize: 13, margin: "8px 0", fontWeight: 600 }}>{err}</div>}

          {/* ① 리전별 검수 크롤 (91사이트) — 먼저 노출 */}
          <div className="card" style={{ marginTop: 12, padding: 14 }}>
            <b style={{ fontSize: 14 }}>① 리전별 검수 크롤</b>
            <span style={{ fontSize: 12, color: "var(--sec)", marginLeft: 8 }}>권역/사이트를 선택해 크롤 (아무것도 안 고르면 전체)</span>

            {/* 권역 다중선택 */}
            <div style={{ fontSize: 11.5, color: "var(--sec)", margin: "10px 0 4px" }}>권역 (여러 개 선택 가능)</div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
              {regionNames.map((rg) => {
                const on = selectedRegions.has(rg);
                return (
                  <button key={rg} onClick={() => { setSelectedSites(new Set()); setSelectedRegions((prev) => { const n = new Set(prev); n.has(rg) ? n.delete(rg) : n.add(rg); return n; }); }}
                    style={sel(rg, on)}>{on ? "✓ " : ""}{rg} {regionsMap[rg]?.length || 0}</button>
                );
              })}
              {(selectedRegions.size > 0 || selectedSites.size > 0) &&
                <button onClick={() => { setSelectedRegions(new Set()); setSelectedSites(new Set()); }} style={{ fontSize: 11.5, color: "var(--sec)", background: "none", border: "none", cursor: "pointer" }}>선택 해제</button>}
            </div>

            {/* 사이트 개별 체크박스(접이식) */}
            <details style={{ marginBottom: 8 }}>
              <summary style={{ fontSize: 11.5, color: "#0A66E0", cursor: "pointer" }}>사이트 개별 선택 {selectedSites.size > 0 ? `(${selectedSites.size}개 선택됨)` : ""}</summary>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, maxHeight: 180, overflowY: "auto" }}>
                {allSites.map((s, i) => {
                  const on = selectedSites.has(s.sitecode);
                  return (
                    <label key={s.sitecode + i} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11.5, border: "1px solid var(--line)", borderRadius: 6, padding: "3px 8px", cursor: "pointer", background: on ? "#E8F0FE" : "#fff" }}>
                      <input type="checkbox" checked={on} onChange={() => { setSelectedRegions(new Set()); setSelectedSites((prev) => { const n = new Set(prev); n.has(s.sitecode) ? n.delete(s.sitecode) : n.add(s.sitecode); return n; }); }} />
                      {s.sitecode}<span style={{ color: "var(--sec)" }}>{s.region}</span>
                    </label>
                  );
                })}
              </div>
            </details>

            <button onClick={runByRegion} disabled={busy} style={{ padding: "8px 14px", borderRadius: 8, border: "none", background: HONEY, color: "#fff", fontWeight: 700, cursor: "pointer" }}>
              {busy ? "붕붕 검수 중…" : `${targetCodes.length}개 사이트 검수${selectedSites.size ? " (선택)" : selectedRegions.size ? " (권역)" : " (전체)"}`}
            </button>
            {selectedSites.size === 0 && selectedRegions.size === 0 && pageCount > 0 && !busy && (
              <span style={{ fontSize: 11.5, color: "var(--sec)", marginLeft: 8 }}>사이트당 여러 페이지(PDP·Compare·Buds 등) — 총 {pageCount}개 페이지 검수</span>
            )}
            {progress.active && (
              <div style={{ marginTop: 10 }}>
                <div style={{ height: 8, background: "#F0F1F3", borderRadius: 999, overflow: "hidden" }}><div style={{ height: "100%", width: `${progress.total ? (progress.done / progress.total) * 100 : 0}%`, background: HONEY, transition: "width .3s" }} /></div>
                <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 4 }}>🐝 {progress.label} · {progress.done}/{progress.total} 페이지</div>
              </div>
            )}
          </div>

          {/* 스펙 탭은 V2(Rule DB) 전용. V2 제품이면 Rule DB 뷰어+기준+점수, 비V2(seed 미등록)면 준비중 안내.
              스키마 탭에서는 구 CriteriaPanel/ScorePanel이 동작. */}
          {tab === "copy" && isV2 && <SpecV2RuleTable product={product} api={api} flash={flash} />}
          {tab === "copy" && isV2 && <SpecV2Criteria show={showRules} panelRef={rulesRef} />}
          {tab === "copy" && isV2 && <SpecV2Score show={showScore} panelRef={scoreRef} />}
          {tab === "copy" && !isV2 && (
            <div className="card" style={{ marginTop: 18, padding: 16, background: "#FFFAEB", border: "1px solid #FEDF89" }}>
              <b style={{ fontSize: 13.5, color: "#93540A" }}>이 제품은 아직 스펙 검수 기준(Rule DB)이 등록되지 않았어요</b>
              <p style={{ fontSize: 12, color: "#93540A", margin: "6px 0 0", lineHeight: 1.6 }}>
                <b>{product}</b>의 Rule DB가 준비되면 스펙 검수가 활성화됩니다. 스펙 탭의 <b>Rule DB 엑셀 업로드</b>로 등록하거나, 담당자에게 시드 등록을 요청하세요. (스키마 검수는 Data QA 탭에서 정상 이용 가능)
              </p>
            </div>
          )}
          {tab === "schema" && <CriteriaPanel ctx={ctx} />}
          {tab === "schema" && <ScorePanel ctx={ctx} />}
          <HtmlQaSummary ctx={ctx} />

          {/* ═══ Spec QA [V2] — Rule 기반 Validation (spec_v2 있는 결과만) ═══ */}
          {tab === "copy" && results.some((r: any) => r.spec_v2) && (
            <>
              <DictionaryPanel product={(results.find((r: any) => r.spec_v2) as any)?.market_product || product} api={api} />
              {results.filter((r: any) => r.spec_v2).map((r: any, i: number) => (
                <SpecV2Panel key={(r.sitecode || "") + i} row={r}
                  product={r.market_product || product} api={api} flash={flash} />
              ))}
            </>
          )}

          {/* 결과 — 오류 빨강 강조. AEO(schema) 탭은 위 HtmlQaSummary 그룹으로 대체하므로 스펙(copy) 탭에서만 flat 테이블 노출
              [V2] spec_v2가 있으면 위 새 화면으로 교체되고, 룰셋 없는 제품만 기존 테이블로 폴백 */}
          {tab === "copy" && !results.some((r: any) => r.spec_v2) && rows.length > 0 && (
            <>
              <div style={{ margin: "18px 0 8px", fontSize: 13, fontWeight: 700, color: failCount ? "#B42318" : "var(--label)" }}>
                {failCount ? `🔴 오류 ${failCount}건` : "🟡 검토"}
                {(() => { const w = rows.filter((x) => x.f.status === "warn").length; const na = rows.filter((x) => x.f.status === "na").length;
                  return <span style={{ color: "var(--sec)", fontWeight: 400 }}> · 확인 {w}건{na ? ` · 해당없음 ${na}건` : ""}</span>; })()}
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead><tr style={{ color: "var(--sec)", fontSize: 11, textAlign: "left" }}>
                  <th style={{ padding: "6px 8px" }}>사이트</th><th style={{ padding: "6px 8px" }}>항목</th><th style={{ padding: "6px 8px" }}>심각도</th><th style={{ padding: "6px 8px" }}>as-is → to-be</th></tr></thead>
                <tbody>
                  {rows.map((x, i) => (
                    <Fragment key={i}>
                      <tr onClick={() => setExpandedRow(expandedRow === i ? null : i)}
                        style={{ background: x.f.status === "fail" ? "#FEF3F2" : undefined, opacity: x.f.status === "na" ? 0.6 : 1, cursor: "pointer" }}>
                        <td style={{ padding: 8, borderTop: "1px solid var(--line)", whiteSpace: "nowrap" }}>{x.r.sitecode}</td>
                        <td style={{ padding: 8, borderTop: "1px solid var(--line)" }}>{x.item}</td>
                        <td style={{ padding: 8, borderTop: "1px solid var(--line)", whiteSpace: "nowrap" }}><span style={{ display: "inline-block", background: SEV[x.f.status].c, color: "#fff", fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 5, whiteSpace: "nowrap", lineHeight: 1.5 }}>{SEV[x.f.status].ko}</span></td>
                        <td style={{ padding: 8, borderTop: "1px solid var(--line)" }}><div style={{ color: "var(--sec)" }}>{x.f.as_is}</div>{x.f.to_be ? <div style={{ fontWeight: 600, color: x.f.status === "fail" ? "#B42318" : "var(--label)" }}>→ {x.f.to_be}</div> : null}<div style={{ fontSize: 11, color: "#0A66E0", marginTop: 3 }}>{expandedRow === i ? "▲ 근거 접기" : "▼ 상세 근거"}</div></td>
                      </tr>
                      {expandedRow === i && (
                        <tr>
                          <td colSpan={4} style={{ padding: "12px 14px", background: "#F9FAFB", borderTop: "1px solid var(--line)" }}>
                            {/* 문제 → 수정 방법 */}
                            <div style={{ marginBottom: 10 }}>
                              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--sec)" }}>무엇이 잘못됐나</div>
                              <div style={{ fontSize: 12.5, color: "var(--label)", marginTop: 2 }}>{x.f.as_is || "—"}</div>
                              {x.f.to_be && <>
                                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--sec)", marginTop: 6 }}>어떻게 고치나</div>
                                <div style={{ fontSize: 12.5, fontWeight: 600, color: x.f.status === "fail" ? "#B42318" : "var(--label)", marginTop: 2 }}>→ {x.f.to_be}</div>
                              </>}
                            </div>
                            {/* 발생 위치·근거 */}
                            <div style={{ display: "grid", gridTemplateColumns: "90px 1fr", gap: "4px 10px", fontSize: 12 }}>
                              <span style={{ color: "var(--sec)" }}>사이트코드</span><b>{x.r.sitecode}</b>
                              {x.r.country && <><span style={{ color: "var(--sec)" }}>국가</span><span>{x.r.country}</span></>}
                              {x.r.region && <><span style={{ color: "var(--sec)" }}>권역</span><span>{x.r.region}</span></>}
                              {x.r.page_type && <><span style={{ color: "var(--sec)" }}>페이지타입</span><span>{x.r.page_type}</span></>}
                              {x.f.region && <><span style={{ color: "var(--sec)" }}>발견 위치</span><span>{x.f.region === "disclaimer" ? "각주(Disclaimer)" : "본문"}</span></>}
                              {x.f.expected && <><span style={{ color: "var(--sec)" }}>기준값</span><span>{x.f.expected}</span></>}
                              {x.f.found && x.f.found.length > 0 && <><span style={{ color: "var(--sec)" }}>페이지 값</span><span style={{ color: "#B42318" }}>{x.f.found.join(", ")}</span></>}
                              {x.r.url && <><span style={{ color: "var(--sec)" }}>URL</span><a href={x.r.url} target="_blank" rel="noreferrer" style={{ fontFamily: "monospace", fontSize: 11, color: "#0A66E0", wordBreak: "break-all" }}>{x.r.url}</a></>}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {tab === "copy" && !results.some((r: any) => r.spec_v2) && results.length > 0 && rows.length === 0 && <p style={{ color: "#1F9E5C", marginTop: 16 }}>이 탭(스펙)에서 발견된 오류가 없어요 🐝</p>}
        </div>
      </div>

      {/* Quick View (QubiSections.tsx로 분리) */}
      <QuickView ctx={ctx} />
    </div>
  );
}
