/* ════════════════════════════════════════════════════
   shared.ts — 타입 / 상수(CRITERIA·METRICS·TIER_META) / 유틸 함수
   page.tsx, sections.tsx 양쪽에서 가져다 씁니다.
════════════════════════════════════════════════════ */

/* ── 타입 */
export type View = "home" | "dashboard";
export type MainTab = "overview" | "pages";
export type MetricTab = "data" | "copy" | "visual";
export type MetricView = MetricTab | "all";
export type SiteKey = "samsung" | "apple";
export type CrawlProgress = {
  active: boolean; site?: string; total: number; done: number;
  currentUrl?: string; error?: string;
};
export type Change = {
  id: number; url: string; site?: string; level?: "High" | "Medium" | "Low";
  category?: string; field?: string; summary?: string; before?: string; after?: string;
  evidence?: Record<string, unknown>;
};
export type AnalysisBlock = {
  facts?: Record<string, any>;
  insights?: { point?: string; evidence_url?: string }[];
  narrative?: string[];
  _source?: "gemini" | "rule_based";
};
export type Report = {
  has_data?: boolean; timestamp?: string; has_changes?: boolean;
  changes?: Change[]; by_category?: Record<string, number>;
  category_summary?: Record<string, string>;
  dcv?: Record<MetricTab, Record<string, AnalysisBlock>>;
  analysis?: { summary?: string };
};
export type Session = {
  session: string; run_ids: string[]; sites: string[];
  pages: number; changes: number; timestamp: string;
};
export type PageLite = { url: string; title: string; word_count: number };
export type PageDetail = {
  url: string; crawled_at?: string;
  data?: { facts?: any; narrative?: string[] };
  copy?: { facts?: any; narrative?: string[] };
  visual?: { facts?: any; narrative?: string[] };
};
export type UrlRow = { url: string; tier_level?: number; site_key?: string };
export type LineTag = { label: string; cls: string };

/* ── 기준 설명 (Drawer 콘텐츠 + ⓘ 아이콘 연동) */
export const CRITERIA: {
  id: string; title: string; note?: string;
  items: { q: string; a: string; detail?: string; scoring?: "weighted" }[];
}[] = [
  {
    id: "severity",
    title: "중요도 기준 (High / Medium / Low)",
    note: "가중치 합산이 아니라 규칙 기반(rule-based) 분류입니다 — 필드 종류(가격/구매 등)에 따라 등급이 정해집니다.",
    items: [
      { q: "High — 높음", a: "Schema·DOM·여러 섹션 동시 변화, 가격·구매처럼 검색 노출이나 구매 판단에 직접 영향을 주는 변화입니다.",
        detail: "Schema(스키마)는 검색엔진이 페이지 내용을 이해하도록 붙이는 구조화 데이터 태그(예: '이건 제품 페이지고 가격은 얼마다')입니다. DOM은 브라우저가 HTML을 해석해서 만드는 페이지 구조(요소들이 부모-자식으로 연결된 트리)를 말합니다. 이 둘이 바뀌면 화면에 안 보여도 검색엔진/AI가 페이지를 이해하는 방식이 바뀔 수 있어서 중요도를 높게 봅니다." },
      { q: "Medium — 보통", a: "문장·슬로건·메뉴·meta·FAQ 같이 의미 해석에 영향을 주는 변화입니다.",
        detail: "meta(메타 디스크립션)는 검색결과에 미리보기로 뜨는 한두 줄 요약 문구입니다. 화면에는 안 보이지만 클릭률에 영향을 줍니다." },
      { q: "Low — 낮음", a: "단어 몇 개·오타·작은 이미지 변화 등 영향이 제한적인 변화입니다." },
    ],
  },
  {
    id: "data",
    title: "DATA — Schema / HTML / Meta / H-tag",
    note: "가중치 없음 — 모두 단순 집계(비율·개수)입니다. 여러 지표를 하나로 합친 'DATA 종합점수'는 없고, 항목별로 따로 봐야 합니다.",
    items: [
      { q: "Schema Coverage", a: "전체 페이지 중 구조화 데이터가 적용된 비율. Product·FAQPage·Organization·BreadcrumbList 포함.",
        detail: "구조화 데이터(=Schema.org, 보통 JSON-LD 형식)는 페이지 안에 '이건 제품이고 이름은 A, 가격은 B'처럼 기계가 읽을 수 있는 태그를 심어두는 것입니다. Product(제품)·FAQPage(자주묻는질문)·Organization(회사정보)·BreadcrumbList(경로표시)가 대표적인 타입입니다." },
      { q: "Schema Completeness", a: "Product 기준 필수 속성(name·image·description·brand·offers·aggregateRating·review) 충족률.",
        detail: "예를 들어 Product 스키마는 이름(name)·이미지(image)·설명(description)·브랜드(brand)·가격정보(offers)·평점(aggregateRating)·리뷰(review) 같은 세부 항목을 채워야 완전합니다. 태그는 있는데 이 항목들이 비어있으면 '적용은 됐지만 미완성'인 상태입니다." },
      { q: "Schema Distribution", a: "템플릿(카테고리·PDP·홈 등) 유형별로 Schema가 고르게 적용됐는지." },
      { q: "Schema Alignment", a: "페이지 목적(PDP엔 Product, FAQ엔 FAQPage 등)과 실제 Schema 타입이 일치하는지.",
        detail: "PDP(Product Detail Page)는 제품 상세 페이지를 뜻하는 업계 용어입니다." },
      { q: "@id 연결성(아키텍처 참고)", a: "Linked(@id 상호참조형) vs Inline(개별 페이지 임베딩형). 우열 기준이 아닌 구조적 특성입니다.",
        detail: "@id는 JSON-LD(구조화 데이터 작성 형식) 안에서 각 데이터 조각에 붙이는 고유 식별자입니다. 여러 스키마 조각이 서로 @id로 참조하면 'Linked(연결형)', 페이지마다 따로따로 다 적어두면 'Inline(임베딩형)'입니다." },
      { q: "H-tag 구조", a: "H1 없음·H2 없이 H3만 존재(depth 불연속) 등 heading 계층 오류를 감지합니다.",
        detail: "H-tag(H1~H6)는 HTML의 제목 태그입니다. H1이 가장 큰 제목, H2는 그 아래 소제목, H3는 더 아래 소제목처럼 계층을 이룹니다. 검색엔진과 화면낭독기는 이 계층으로 글의 구조를 파악하는데, H2를 건너뛰고 H1 다음에 H3가 나오면(계층이 끊기면) 구조 오류로 감지됩니다." },
      { q: "Meta description", a: "비어있거나 누락된 페이지를 집계합니다.",
        detail: "검색결과에서 제목 아래 나오는 한두 줄 설명 문구를 담는 HTML 태그(meta description)입니다." },
    ],
  },
  {
    id: "copy",
    title: "COPY — 카피 풍부성 / FAQ 품질",
    note: "⚖️ 표시된 2개(카피 풍부성 점수, FAQ 품질 점수)만 가중합산 공식이 있고, 나머지(정량지표·빈약 콘텐츠)는 단순 집계입니다.",
    items: [
      { q: "카피 풍부성 점수 (0~100)", a: "정량지표(숫자+단위 밀도) 35% + 구조지표(H2·CTA·FAQ 보유) 25% + 비교·근거 키워드 20% + FAQ 보유 20%. 70+ 우수, 40~69 보통, 40 미만 미흡.",
        scoring: "weighted",
        detail: "'구조지표'는 본문에 소제목(H2)·행동유도버튼(CTA, 예: '구매하기' 버튼)·FAQ가 있는지를 보는 지표입니다. CTA는 Call To Action(행동을 유도하는 버튼·문구)의 줄임말입니다." },
      { q: "정량지표", a: "본문 100단어당 숫자+단위(GB·mAh·mm·% 등) 출현량. 목표 3개/100단어 기준으로 스케일." },
      { q: "빈약 콘텐츠", a: "150단어 미만은 빈약(thin) 콘텐츠로 분류합니다. 단순 수치 기준이 아닌 밀도 4단계 분포로 판단.",
        detail: "'thin content(빈약 콘텐츠)'는 SEO 업계 용어로, 분량이 적어 검색엔진이 페이지의 가치를 판단하기 어려운 콘텐츠를 말합니다." },
      { q: "FAQ 품질 점수 (0~100)", a: "구체성(수치·스펙 포함) 40% + 질문현실성(실제 의문형) 30% + AI인용적합성(첫 문장 인용 가능) 30%.",
        scoring: "weighted" },
    ],
  },
  {
    id: "visual",
    title: "VISUAL — 이미지 분석",
    note: "가중치 없음 — 모두 개수·비율 집계입니다. 종합 'VISUAL 점수'는 없습니다.",
    items: [
      { q: "이미지 분류", a: "alt+src+파일명+페이지 URL 텍스트 기반 휴리스틱. lifestyle(사람이 쓰는 상황) / product(제품 자체) / unclassified 3종.",
        detail: "alt는 이미지에 붙이는 대체 텍스트(alt text)이고, src는 이미지 파일 경로입니다. Samsung처럼 모델명·KV·gallery 중심으로 표기되는 파일명도 product 신호로 함께 봅니다. 실제 이미지 픽셀을 읽는 Vision 분석은 아닙니다." },
      { q: "alt 텍스트 품질", a: "비어있음·일반적(image/photo/배너 등)·설명적(15자 이상, 제네릭 아님) 3단계. Vision AI 분석이 아닌 텍스트 기반 판정입니다." },
      { q: "이미지 고유성", a: "src/alt 중복도 기반 추정치. 같은 이미지·문구가 여러 페이지에 반복 사용되는 템플릿화 정도." },
      { q: "스토리텔링", a: "product+lifestyle 혼합이면서 설명적 alt가 2개 이상인 페이지를 스토리텔링 페이지로 분류합니다." },
    ],
  },
];

/* ── 상수 */
export const METRICS: Record<MetricTab, { label: string; plain: string; criteriaId: string }> = {
  data: { label: "DATA 구조", plain: "Schema·HTML·Meta·H-tag를 분석합니다.", criteriaId: "data" },
  copy: { label: "COPY 문구", plain: "카피 풍부성·FAQ 품질·콘텐츠 밀도를 분석합니다.", criteriaId: "copy" },
  visual: { label: "VISUAL 이미지", plain: "이미지 다양성·alt 품질·스토리텔링을 분석합니다.", criteriaId: "visual" },
};
export const CATEGORY_BUCKETS: Record<string, MetricTab> = {
  "데이터·스키마": "data", "데이터/스키마": "data", "DATA/Schema": "data",
  technical: "data", navigation: "data",
  카피: "copy", "가격·프로모션": "copy", "가격/프로모션": "copy",
  content: "copy", commerce: "copy",
  비주얼: "visual", visual: "visual",
};
export const TIER_META: Record<number, { label: string; desc: string }> = {
  0: { label: "Tier 0 · 홈", desc: "브랜드 홈페이지" },
  1: { label: "Tier 1 · 카테고리", desc: "제품 카테고리 목록 페이지" },
  2: { label: "Tier 2 · 캠페인", desc: "비교·전환·캠페인성 페이지 (예: Compare, Switch, AI 소개)" },
  3: { label: "Tier 3 · 제품 상세", desc: "개별 제품 소개 페이지" },
  4: { label: "Tier 4 · 구매/스펙", desc: "구매·스펙 상세 페이지" },
};

// ── 세부 항목 뱃지 분류기: narrative 한 줄이 어느 세부 기준에 해당하는지 키워드로 판정 ──
export const DATA_LINE_TAGS: [RegExp, LineTag][] = [
  [/Schema 적용 범위/, { label: "Schema Coverage", cls: "c1" }],
  [/스키마.*충족|충족률|필수 속성/, { label: "Schema Completeness", cls: "c2" }],
  [/스키마 아키텍처/, { label: "@id 연결성", cls: "c4" }],
  [/H-?tag|heading|계층/i, { label: "H-tag 구조", cls: "c5" }],
  [/meta description|메타 디스크립션/i, { label: "Meta description", cls: "c6" }],
];
export const COPY_LINE_TAGS: [RegExp, LineTag][] = [
  [/콘텐츠 밀도 분포/, { label: "콘텐츠 밀도", cls: "c1" }],
  [/빈약 콘텐츠/, { label: "빈약 콘텐츠", cls: "c3" }],
  [/카피 풍부성|풍부성 점수/, { label: "카피 풍부성", cls: "c2" }],
  [/FAQ/, { label: "FAQ 품질", cls: "c4" }],
];
export const VISUAL_LINE_TAGS: [RegExp, LineTag][] = [
  [/이미지.*장 중|product.*lifestyle/i, { label: "이미지 분류", cls: "c1" }],
  [/alt 텍스트 품질/, { label: "alt 텍스트 품질", cls: "c2" }],
  [/고유 이미지 비율|이미지 재사용도/, { label: "이미지 고유성", cls: "c3" }],
  [/이미지 편중/, { label: "이미지 분포", cls: "c5" }],
  [/스토리텔링/, { label: "스토리텔링", cls: "c4" }],
];

/* ── 유틸 */
export const siteName = (s?: string) =>
  s === "apple" ? "Apple 경쟁사" : s === "samsung" ? "Samsung 당사" : s || "미분류";
export const siteClass = (s?: string) => (s === "apple" ? "apple" : "samsung");
export const levelKo = (l?: string) => l === "High" ? "높음" : l === "Medium" ? "보통" : "낮음";
export const levelClass = (l?: string) => l === "High" ? "high" : l === "Medium" ? "med" : "low";
export const severityEmoji = (l?: string) => l === "High" ? "🔴" : l === "Medium" ? "🟠" : "🟢";

export const actionForChange = (c: Change): string => {
  const level = c.level || "Low";
  const isApple = c.site === "apple";
  if (level === "High") {
    return isApple ? "경쟁사 핵심 변경 즉시 확인 및 당사 영향 검토" : "즉시 변경사항 확인 및 대응 필요";
  }
  if (level === "Medium") {
    return isApple ? "경쟁사 변화 지속 모니터링" : "지속 모니터링 및 필요 시 후속 점검";
  }
  return "참고용 기록 유지 및 다음 수집에서 재확인";
};
// 이 목록 안에서 가장 심각한 등급의 변화만 골라 반환 (High가 없으면 Medium, 그마저 없으면 Low)
export const topSeverityChanges = (pool: Change[], n = 3): { level: "High" | "Medium" | "Low"; changes: Change[] } | null => {
  for (const lvl of ["High", "Medium", "Low"] as const) {
    const matches = pool.filter((c) => c.level === lvl);
    if (matches.length) return { level: lvl, changes: matches.slice(0, n) };
  }
  return null;
};
// 변경점을 URL(페이지) 단위로 그룹핑 — 엑셀/PPT의 '페이지별 변경점'과 동일한 방식.
// 등장 순서를 유지하고, 그룹 내부는 severity(High→Low) 순으로 정렬한다.
export const groupByUrl = (changes: Change[]): { url: string; items: Change[] }[] => {
  const order: string[] = [];
  const map: Record<string, Change[]> = {};
  for (const c of changes) {
    const url = c.url || "(URL 없음)";
    if (!map[url]) { map[url] = []; order.push(url); }
    map[url].push(c);
  }
  const sevRank: Record<string, number> = { High: 0, Medium: 1, Low: 2 };
  return order.map((url) => ({
    url,
    items: [...map[url]].sort((a, b) => (sevRank[a.level || "Low"] ?? 2) - (sevRank[b.level || "Low"] ?? 2)),
  }));
};
export const shortUrl = (u: string) => {
  try { const x = new URL(u); return (x.hostname + x.pathname).replace(/\/$/, ""); } catch { return u; }
};
export const linesFromBlock = (b?: AnalysisBlock) => [
  ...(b?.narrative || []),
  ...((b?.insights || []).map((x) => x.point || "").filter(Boolean)),
];
// 백엔드 config.py::tier_for_url() 과 동일 로직(폴백용). 1차 소스는 /api/urls 의 tier_level.
export const tierForUrl = (u: string): number => {
  try {
    const path = new URL(u).pathname.toLowerCase();
    const segments = path.split("/").filter((s) => s && !["sg", "us", "en"].includes(s));
    if (segments.length === 0) return 0;
    if (/buy|shop|specs|purchase/.test(path)) return 4;
    if (/compare|find-your|switch-to|galaxy-ai|apple-intelligence|mobile\/|one-ui/.test(path)) return 2;
    if (/iphone-|galaxy-|apple-watch-|buds|watch-ultra/.test(path)) return 3;
    if (/all-smartphones|all-watches|all-audio|iphone|watch|airpods/.test(path)) return 1;
    return Math.min(segments.length, 3);
  } catch { return 3; }
};
export const tierFromUrl = (u: string) => `Tier ${tierForUrl(u)}`;
export const tagForLine = (metric: MetricTab, line: string): LineTag => {
  const table = metric === "data" ? DATA_LINE_TAGS : metric === "copy" ? COPY_LINE_TAGS : VISUAL_LINE_TAGS;
  for (const [re, tag] of table) if (re.test(line)) return tag;
  return { label: METRICS[metric].label, cls: "c6" };
};
export const bucketOf = (c: Change): MetricTab => {
  if (CATEGORY_BUCKETS[c.category || ""]) return CATEGORY_BUCKETS[c.category || ""];
  const raw = ((c.category || "") + " " + (c.field || "")).toLowerCase();
  if (/schema|dom|canonical|meta|html|h-tag|nav/.test(raw)) return "data";
  if (/visual|image|screenshot|alt|lifestyle/.test(raw)) return "visual";
  return "copy";
};
export const metricAverage = (sitePages: PageLite[], block?: AnalysisBlock) => {
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

// 지표(DATA/COPY/VISUAL) 하나를 핵심 한줄 + 숫자 통계로 요약. 실제 facts/changes만 사용(생성 없음).
export const metricOneLiner = (
  metric: MetricTab,
  dcvForMetric: Record<string, AnalysisBlock> | undefined,
  changes: Change[]
): string => {
  const af = dcvForMetric?.apple?.facts || {};
  const sf = dcvForMetric?.samsung?.facts || {};
  const high = changes.filter((c) => c.level === "High").length;
  let statLine = "";
  if (metric === "data") {
    const a = af.schema?.coverage_pct, s = sf.schema?.coverage_pct;
    statLine = `Schema 적용률 Apple ${a ?? "-"}% · Samsung ${s ?? "-"}%`;
  } else if (metric === "copy") {
    const a = af.content_density?.thin_pages?.length, s = sf.content_density?.thin_pages?.length;
    statLine = `빈약 콘텐츠 Apple ${a ?? "-"}개 · Samsung ${s ?? "-"}개`;
  } else {
    const a = af.image_diversity?.lifestyle_ratio_pct, s = sf.image_diversity?.lifestyle_ratio_pct;
    statLine = `Lifestyle 이미지 Apple ${a ?? "-"}% · Samsung ${s ?? "-"}%`;
  }
  return `${statLine} · 변경 ${changes.length}건 (High ${high})`;
};

/* ── 화면 캡처 */
export const captureScreen = async () => {
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
