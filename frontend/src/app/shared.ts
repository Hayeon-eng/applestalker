/* ════════════════════════════════════════════════════
   shared.ts — 타입 / 상수(CRITERIA·METRICS·TIER_META) / 유틸 함수
   page.tsx, sections.tsx 양쪽에서 가져다 씁니다.
════════════════════════════════════════════════════ */

/* ── 타입 */
export type View = "home" | "dashboard";
export type MainTab = "overview" | "pages" | "products";
export type MetricTab = "data" | "copy" | "visual";
export type MetricView = MetricTab | "all";
export type SiteKey = string;
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
export type PageWireframe = {
  page_role?: string; title?: string; h1?: string; h2?: string[]; h3?: string[];
  ctas?: { text?: string }[]; image_count?: number; faq_count?: number;
  schema_types?: string[]; word_count?: number;
};
export type PageDetail = {
  url: string; crawled_at?: string; wireframe?: PageWireframe;
  data?: { facts?: any; narrative?: string[] };
  copy?: { facts?: any; narrative?: string[] };
  visual?: { facts?: any; narrative?: string[] };
};
export type ProductCategory = "phone" | "tablet" | "audio" | "watch" | "laptop" | "ai_glass";
export type UrlRow = { url: string; tier_level?: number; site_key?: string; page_role?: string; product_category?: ProductCategory | string; page_label?: string };
export type LineTag = { label: string; cls: string };

/* ── 기준 설명 (Drawer 콘텐츠 + ⓘ 아이콘 연동) */
export const CRITERIA: {
  id: string; title: string; note?: string;
  items: { q: string; a: string; detail?: string; scoring?: "weighted" }[];
}[] = [
  {
    id: "severity",
    title: "중요도 기준 (High / Medium / Low)",
    note: "변화 폭, 페이지 역할(PF/PDP/Buying), 검색·AI 해석 영향, 구매전환 영향, 렌더링 노이즈 여부를 함께 봅니다. 필드명 하나만 보고 등급을 고정하지 않습니다.",
    items: [
      { q: "High — 높음", a: "Product/FAQ 스키마, 핵심 H1/H2, 구매 CTA, 가격·프로모션, 상위 PDP 메시지처럼 검색·AI 요약·구매전환에 직접 영향을 줄 가능성이 큰 변화입니다.", detail: "예: PDP Product schema가 사라짐, Buying CTA가 크게 바뀜, hero copy가 새 포지셔닝으로 변경됨." },
      { q: "Medium — 보통", a: "meta description, FAQ 문구, 중간 섹션 카피, 이미지 alt/src 구성처럼 의미 해석이나 클릭률에 영향을 줄 수 있지만 범위가 제한적인 변화입니다.", detail: "한두 페이지의 보조 카피 변경이나 특정 섹션 구조 변화가 여기에 해당합니다." },
      { q: "Low — 낮음", a: "짧은 UI 라벨, 반복되는 footer/header 문구, 렌더링 차이처럼 실제 사용자·AI 검색 영향이 제한적인 변화입니다.", detail: "단, Low가 반복되면 템플릿 변화 신호일 수 있어 누적 추세는 유지합니다." },
    ],
  },
  {
    id: "data",
    title: "DATA — Schema / HTML / Meta / H-tag",
    note: "삼성 구조를 정답으로 두지 않습니다. 사이트별로 Linked(@id 참조형)와 Inline(페이지별 임베딩형)처럼 구조가 다를 수 있으므로, ‘좋고 나쁨’보다 페이지 역할과 실제 Schema 타입이 맞는지를 먼저 봅니다.",
    items: [
      { q: "Schema Coverage", a: "전체 수집 페이지 중 Schema.org 구조화 데이터가 하나라도 발견된 페이지 비율입니다.", detail: "판단 방법: 각 페이지의 JSON-LD/microdata에서 WebPage, Product, FAQPage, Organization, BreadcrumbList, ItemList 등 schema type 존재 여부를 집계합니다. Coverage가 낮으면 검색엔진·AI가 페이지 의미를 파악할 단서가 적을 수 있습니다." },
      { q: "Product Completeness", a: "Product schema가 있는 페이지에서 제품명·이미지·설명·브랜드·구매정보·평점·리뷰 같은 주요 속성이 어느 정도 채워졌는지 봅니다.", detail: "판단 방법: name, image, description, brand, offers, aggregateRating, review를 확인합니다. 단, 모든 브랜드가 평점/리뷰를 공식 페이지에 넣는 것은 아니므로 ‘누락=무조건 문제’가 아니라 PDP/Buying에서 제품 이해와 구매 판단에 필요한 속성이 부족한지로 해석합니다." },
      { q: "Role-fit Schema (PF/PDP/Buying)", a: "페이지 역할에 맞는 Schema 타입이 있는지 봅니다. PF는 CollectionPage·ItemList, PDP/Buying은 Product·ItemPage·BreadcrumbList가 핵심입니다.", detail: "판단 방법: URL 패턴과 page_role로 PF(Product Family), PDP(Product Detail Page), Buying을 나누고, 역할별 기대 타입을 비교합니다. PF에 Product가 없다고 바로 나쁘게 보지 않고, 제품 목록을 설명하는 ItemList/CollectionPage가 있으면 역할에 맞는 구조로 봅니다." },
      { q: "Schema Alignment", a: "페이지 목적과 실제 Schema가 어긋나는지 확인합니다.", detail: "예: 제품 상세 페이지인데 Product 신호가 없거나, 구매 페이지인데 offers/price/availability 같은 구매 단서가 전혀 없으면 alignment gap으로 봅니다. 반대로 브랜드 홈/카테고리 페이지는 WebPage/Organization/BreadcrumbList 중심이어도 자연스럽습니다." },
      { q: "@id 연결성", a: "Linked(@id 상호참조형)인지 Inline(페이지 안에 독립 임베딩형)인지 구조적 특성만 봅니다. 우열 기준이 아닙니다.", detail: "판단 방법: schema node가 @id로 서로 참조되는지, 독립적으로 반복되는지 확인합니다. Linked는 데이터 그래프를 관리하기 좋고, Inline은 페이지 단위 구현이 단순합니다. 둘 중 무엇이 더 좋다고 단정하지 않고 일관성과 누락 리스크를 봅니다." },
      { q: "H-tag 구조", a: "H1 누락, H2 없이 H3만 나오는 depth 불연속, 제목 계층의 과도한 반복을 확인합니다.", detail: "판단 방법: HTML heading 순서를 읽고 H1/H2/H3의 계층이 자연스러운지 봅니다. 사용자가 보기에는 비슷해도 검색엔진과 스크린리더는 heading 계층으로 페이지 구조를 이해합니다." },
      { q: "Meta description", a: "검색결과 요약 후보가 되는 meta description이 비어 있거나 누락된 페이지를 집계합니다.", detail: "판단 방법: <meta name='description'> 값을 확인합니다. 없는 경우 검색엔진이 본문을 임의로 잘라 보여줄 수 있어 핵심 메시지 통제가 약해집니다." },
    ],
  },
  {
    id: "copy",
    title: "COPY — 카피 길이 / 톤 / CTA / FAQ",
    note: "PF·PDP·Buying을 같은 길이 기준으로 재단하지 않습니다. PF는 탐색, PDP는 설득, Buying은 전환이라는 역할 차이를 기준으로 봅니다.",
    items: [
      { q: "카피 구체성 점수 (0~100)", a: "숫자·스펙·가격·기간 같은 구체 근거, H2/CTA/FAQ 구조, 비교·증거 키워드를 합쳐 페이지 카피가 얼마나 설명력 있는지 봅니다.", scoring: "weighted", detail: "판단 방법: 정량 표현(GB, mAh, %, 가격, 시간 등), 구조 신호(H2·CTA·FAQ), 근거 키워드(compare, tested, certified 등)를 집계합니다. 70점 이상은 구체적, 40~69점은 보통, 40점 미만은 설명 근거가 약한 편으로 봅니다." },
      { q: "역할별 카피 길이", a: "PF/PDP/Buying별 평균 단어 수를 따로 봅니다.", detail: "판단 방법: PF는 제품군을 빠르게 훑을 수 있는지, PDP는 기능과 차별점을 충분히 설득하는지, Buying은 옵션/가격/혜택/CTA가 짧고 명확한지로 해석합니다." },
      { q: "구매 CTA 감지", a: "Buying hard URL이 없는 글로벌 사이트는 가짜 URL을 만들지 않고, PF/PDP 안의 Buy/Shop/Add to cart/Where to buy CTA 신호를 확인합니다.", detail: "판단 방법: 버튼·링크 텍스트, aria-label, title에서 buy/shop/order/add to cart/where to buy/구매/장바구니 등 문구를 찾고 href가 있으면 함께 저장합니다. 즉 ‘별도 Buying URL 없음’은 크롤 실패가 아니라 PDP 내부 전환 구조로 처리합니다." },
      { q: "토널리티", a: "spec proof, benefit, urgency, AI, sustainability 같은 키워드 신호로 어떤 메시지 톤을 밀고 있는지 봅니다.", detail: "예: Apple이 creative/pro workflow를 강조하고, Xiaomi가 productivity/spec을 강조하는 식의 방향성을 잡습니다. 단어 수만 보는 것이 아니라 어떤 메시지로 설득하는지가 핵심입니다." },
      { q: "중복 CTA/중복 텍스트", a: "동일 버튼명이나 긴 문장 반복을 찾아 불필요한 버튼·중복 문구 가능성을 점검합니다.", detail: "판단 방법: 동일 CTA 텍스트 반복, 긴 문장 반복, header/footer 반복 신호를 분리해 봅니다. 반복 자체가 항상 문제는 아니므로 삭제 전 사람이 확인해야 합니다." },
      { q: "FAQ 품질", a: "FAQ가 실제 사용자의 질문처럼 보이는지, 답변 첫 문장만으로도 인용 가능한지, 수치·조건이 포함되는지 봅니다.", scoring: "weighted", detail: "판단 방법: 질문 현실성, 답변 구체성, AI 인용 적합성을 점수화합니다. FAQ가 길어도 조건·수치가 없으면 품질 점수는 낮을 수 있습니다." },
    ],
  },
  {
    id: "visual",
    title: "VISUAL — 이미지 메타데이터 / alt.copy / Visual tactic",
    note: "현재 도구는 이미지 스크린샷이나 픽셀을 직접 보지 않습니다. HTML에서 수집한 alt 텍스트, src 파일명, URL, 주변 텍스트만으로 이미지 전략 신호를 판단합니다.",
    items: [
      { q: "이미지 분류", a: "alt/src/파일명/URL 신호로 product, lifestyle, unclassified를 나눕니다.", detail: "판단 방법: 제품명·색상·gallery·KV·device 같은 단어는 product, lifestyle·hands·wearing·desk·person 같은 단어는 사용 상황 신호로 봅니다. 실제 이미지를 본 판정은 아닙니다." },
      { q: "alt.copy 품질", a: "비어 있음, 일반적(image/photo/banner), 설명적 alt를 구분합니다.", detail: "판단 방법: alt가 비어 있거나 너무 짧고 일반적인지, 제품/기능/상황을 설명하는지 봅니다. 설명적 alt는 접근성과 AI 검색 이해도에 도움이 됩니다." },
      { q: "Visual tactic", a: "PF/PDP/Buying 역할과 이미지 수·alt/src 힌트를 묶어 category grid, product showcase, feature gallery, commerce CTA 등으로 해석합니다.", detail: "판단 방법: PF에서 여러 제품 이미지가 반복되면 category grid, PDP에서 feature/gallery 이미지가 많으면 feature storytelling, Buying에서 CTA/옵션 주변 이미지가 많으면 commerce support로 봅니다." },
      { q: "이미지 고유성", a: "src/alt 중복도를 통해 같은 이미지가 여러 페이지에 반복되는 정도를 봅니다.", detail: "고유 이미지 비율이 낮으면 템플릿화 신호일 수 있지만, 로고·아이콘·공통 UI 이미지는 반복될 수 있으므로 핵심 PDP/Buying 중심으로 해석합니다." },
      { q: "페이지 길이/이미지 밀도", a: "역할별 평균 단어 수와 이미지 수를 같이 봅니다.", detail: "긴 PDP에 이미지가 거의 없으면 설득력이 약할 수 있고, 짧은 Buying 페이지에 이미지가 너무 많으면 전환 정보가 묻힐 수 있습니다. 그래서 단어 수와 이미지 수를 함께 봅니다." },
    ],
  },
];

/* ── 사이트 표시 메타 */
export const DEFAULT_SITE_ORDER: SiteKey[] = [
  "samsung", "apple", "google_pixel", "xiaomi", "oppo", "vivo",
  "sony_audio", "garmin", "dell", "meta_ai_glasses",
];
export const SITE_META: Record<string, { label: string; short: string; cls: string }> = {
  samsung: { label: "Samsung", short: "Samsung", cls: "samsung" },
  apple: { label: "Apple", short: "Apple", cls: "apple" },
  google_pixel: { label: "Google Pixel", short: "Pixel", cls: "competitor" },
  xiaomi: { label: "Xiaomi", short: "Xiaomi", cls: "competitor" },
  oppo: { label: "OPPO", short: "OPPO", cls: "competitor" },
  vivo: { label: "vivo", short: "vivo", cls: "competitor" },
  sony_audio: { label: "Sony Audio", short: "Sony", cls: "competitor" },
  garmin: { label: "Garmin", short: "Garmin", cls: "competitor" },
  dell: { label: "Dell", short: "Dell", cls: "competitor" },
  meta_ai_glasses: { label: "Meta AI Glasses", short: "Meta", cls: "competitor" },
};
export const orderedSiteKeys = (keys: string[]): SiteKey[] => {
  const uniq = Array.from(new Set(keys.filter(Boolean)));
  return uniq.sort((a, b) => {
    const ia = DEFAULT_SITE_ORDER.indexOf(a), ib = DEFAULT_SITE_ORDER.indexOf(b);
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib) || a.localeCompare(b);
  });
};

/* ── 상수 */
export const METRICS: Record<MetricTab, { label: string; plain: string; criteriaId: string }> = {
  data: { label: "DATA / Schema", plain: "Schema·HTML·Meta·H-tag가 페이지 역할과 맞는지 확인합니다.", criteriaId: "data" },
  copy: { label: "COPY / CTA", plain: "카피 구체성, 구매 CTA, FAQ가 전환 흐름에 맞는지 확인합니다.", criteriaId: "copy" },
  visual: { label: "VISUAL / ALT COPY", plain: "이미지 전략, ALT COPY, 사용 장면 신호가 충분한지 확인합니다.", criteriaId: "visual" },
};
export const CATEGORY_BUCKETS: Record<string, MetricTab> = {
  "데이터·스키마": "data", "데이터/스키마": "data", "DATA/Schema": "data",
  technical: "data", navigation: "data",
  카피: "copy", "가격·프로모션": "copy", "가격/프로모션": "copy",
  content: "copy", commerce: "copy",
  비주얼: "visual", visual: "visual",
};
export const PAGE_ROLE_META: Record<string, { label: string; desc: string }> = {
  pf: { label: "PF", desc: "제품군/카테고리 탐색 페이지" },
  pdp: { label: "PDP", desc: "개별 제품 상세 페이지" },
  buying: { label: "Buying", desc: "구매·옵션·가격·혜택 중심 페이지" },
  specs: { label: "Specs", desc: "상세 스펙 페이지" },
  campaign_or_compare: { label: "Compare/Campaign", desc: "비교·캠페인·전환 보조 페이지" },
  campaign: { label: "Campaign", desc: "캠페인·전환 보조 페이지" },
  compare: { label: "Compare", desc: "제품 비교 페이지" },
  home: { label: "Home", desc: "브랜드/스토어 홈" },
  content: { label: "Content", desc: "기타 콘텐츠 페이지" },
};
export const PRODUCT_CATEGORY_ORDER: ProductCategory[] = ["phone", "tablet", "audio", "watch", "laptop", "ai_glass"];
export const PRODUCT_CATEGORY_META: Record<string, { label: string; desc: string }> = {
  phone: { label: "폰", desc: "스마트폰 PF/PDP/Buying" },
  tablet: { label: "태블릿", desc: "태블릿 PF/PDP/Buying" },
  audio: { label: "버즈/오디오", desc: "이어버드·헤드폰 PF/PDP/Buying" },
  watch: { label: "워치", desc: "스마트워치 PF/PDP/Buying" },
  laptop: { label: "노트북/PC", desc: "노트북·PC PF/PDP/Buying" },
  ai_glass: { label: "AI Glass", desc: "AI Glass PF/PDP/Buying" },
};
// 하위 호환용. 화면에서는 더 이상 Tier 기준을 노출하지 않고 PAGE_ROLE_META를 사용한다.
export const TIER_META: Record<number, { label: string; desc: string }> = {
  0: { label: "Home", desc: PAGE_ROLE_META.home.desc },
  1: { label: "PF", desc: PAGE_ROLE_META.pf.desc },
  2: { label: "Compare/Campaign", desc: PAGE_ROLE_META.campaign_or_compare.desc },
  3: { label: "PDP", desc: PAGE_ROLE_META.pdp.desc },
  4: { label: "Buying/Specs", desc: `${PAGE_ROLE_META.buying.desc} / ${PAGE_ROLE_META.specs.desc}` },
};

// ── 세부 항목 뱃지 분류기: narrative 한 줄이 어느 세부 기준에 해당하는지 키워드로 판정 ──
export const DATA_LINE_TAGS: [RegExp, LineTag][] = [
  [/Schema 적용 범위|Schema 적용 현황|구조화 데이터/, { label: "구조화 데이터 적용률", cls: "c1" }],
  [/페이지 역할|PF|PDP|Buying|Role-fit|역할별 Schema|Schema 보강/, { label: "페이지 역할 적합성", cls: "c1" }],
  [/스키마.*충족|Product detail|충족률|필수 속성|Product schema/, { label: "제품 정보 완성도", cls: "c2" }],
  [/스키마 아키텍처|Linked|Inline|@id/, { label: "스키마 연결 구조", cls: "c4" }],
  [/H-?tag|heading|계층/i, { label: "H-tag 구조", cls: "c5" }],
  [/meta description|메타 디스크립션/i, { label: "Meta description", cls: "c6" }],
];
export const COPY_LINE_TAGS: [RegExp, LineTag][] = [
  [/수집 페이지 기준|관리 기준|실제 수집/, { label: "수집 기준", cls: "c1" }],
  [/COPY 현재 상태|카피 구체성|평균 구체성|구체 근거/, { label: "COPY 현재 상태", cls: "c2" }],
  [/우선 점검 페이지|긴 설명 대비|텍스트가 짧|짧은 텍스트/, { label: "점검 후보", cls: "c3" }],
  [/구매 CTA|Buy CTA|Shop|Add to cart/, { label: "구매 CTA", cls: "c3" }],
  [/중복 CTA|중복 문구|중복 텍스트|불필요한 버튼/, { label: "중복 점검", cls: "c3" }],
  [/토널리티|메시지 톤/, { label: "토널리티", cls: "c5" }],
  [/FAQ/, { label: "FAQ", cls: "c4" }],
];
export const VISUAL_LINE_TAGS: [RegExp, LineTag][] = [
  [/이미지 분석 방식|이미지.*장 중|product.*lifestyle/i, { label: "이미지 분류", cls: "c1" }],
  [/alt\.copy 품질|alt 텍스트 품질/, { label: "alt.copy 품질", cls: "c2" }],
  [/고유 이미지 비율|이미지 재사용도/, { label: "이미지 고유성", cls: "c3" }],
  [/이미지 편중/, { label: "이미지 분포", cls: "c5" }],
  [/Visual tactic|비주얼 택틱|페이지 역할별 길이|페이지 역할별 Visual|페이지 길이/, { label: "Visual tactic", cls: "c5" }],
  [/alt\.copy|alt 샘플|alt 미흡|alt.*보강/, { label: "alt.copy", cls: "c2" }],
  [/스토리텔링/, { label: "스토리텔링", cls: "c4" }],
];

/* ── 유틸 */
export const siteName = (s?: string) => SITE_META[s || ""]?.label || s || "미분류";
export const siteShortName = (s?: string) => SITE_META[s || ""]?.short || s || "미분류";
export const siteClass = (s?: string) => SITE_META[s || ""]?.cls || "competitor";
export const levelKo = (l?: string) => l === "High" ? "높음" : l === "Medium" ? "보통" : "낮음";
export const levelClass = (l?: string) => l === "High" ? "high" : l === "Medium" ? "med" : "low";
export const severityEmoji = (l?: string) => l === "High" ? "🔴" : l === "Medium" ? "🟠" : "🟢";
export const isLegacySamsungUsUrl = (site?: string, url?: string) =>
  site === "samsung" && /https?:\/\/www\.samsung\.com\/us\//i.test(url || "");


export const metricAreaLabel = (metric: MetricTab) => {
  if (metric === "data") return "DATA / Schema";
  if (metric === "copy") return "COPY / CTA";
  return "VISUAL / ALT COPY";
};

export const metricIssueSentence = (metric: MetricTab) => {
  if (metric === "data") return "Schema와 H-tag가 페이지 역할에 맞는지 확인이 필요합니다.";
  if (metric === "copy") return "카피의 구체성과 구매 전환 연결이 제한적인 지점이 있습니다.";
  return "ALT COPY의 구체성과 사용 장면 설명 범위가 제한적인 지점이 있습니다.";
};

export const metricActionSentence = (metric: MetricTab) => {
  if (metric === "data") return "PF는 ItemList/Breadcrumb, PDP는 Product/Breadcrumb, Buying은 Offer 중심으로 점검하세요.";
  if (metric === "copy") return "PDP·Buying 카피의 구체성(수치·혜택·소재)을 보강하고, 구매 CTA는 부족한 페이지에 한해 함께 점검하세요.";
  return "제품명, 핵심 기능, 사용 장면이 드러나도록 ALT COPY와 이미지 설명을 보강하세요.";
};

export const actionForChange = (c: Change): string => {
  const metric = bucketOf(c);
  const role = pageRoleKo(pageRoleFromUrl(c.url || ""));
  const isOurs = c.site === "samsung";
  const subject = isOurs ? `우리 ${role}` : `${siteShortName(c.site)} ${role}`;
  if (metric === "data") {
    return isOurs
      ? `우리 ${role}에 적용된 Schema/H-tag가 페이지 역할과 맞는지 점검하고, ${metricActionSentence("data")}`
      : `${subject}의 Schema/H-tag 변경을 확인하고, ${metricActionSentence("data")}`;
  }
  if (metric === "visual") {
    return isOurs
      ? `우리 ${role}의 이미지/ALT COPY가 제품·기능·사용 장면을 충분히 설명하는지 점검하고, ${metricActionSentence("visual")}`
      : `${subject}의 이미지/ALT COPY 변경을 확인하고, ${metricActionSentence("visual")}`;
  }
  return isOurs
    ? `우리 ${role}의 카피가 구매 전환 흐름에 맞는지 점검하고, ${metricActionSentence("copy")}`
    : `${subject}의 카피 변경을 확인하고, ${metricActionSentence("copy")}`;
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
const RAW_JARGON_LINE_PATTERN = /@id|Inline\(|Inline형|Linked\s*구조|노드가 페이지별|스키마 아키텍처/;
export const linesFromBlock = (b?: AnalysisBlock) => [
  ...(b?.narrative || []),
  ...((b?.insights || []).map((x) => x.point || "").filter(Boolean)),
].filter((line) => !RAW_JARGON_LINE_PATTERN.test(line));
export const pageRoleFromUrl = (u: string): "home" | "pf" | "pdp" | "buying" | "compare" | "campaign" | "campaign_or_compare" | "specs" | "content" => {
  try {
    const url = new URL(u);
    const path = url.pathname.toLowerCase();
    const clean = path.replace(/\/$/, "");
    if (!clean || clean === "/" || clean === "/us" || clean === "/sg" || clean === "/global") return "home";
    if (/\/shop\//.test(path) || /\/buy\//.test(path) || /\/cart\//.test(path) || /\/checkout\//.test(path) || /\/config\//.test(path) || /shop-all/.test(path)) return "buying";
    if (/specs|specifications|tech-specs/.test(path)) return "specs";
    if (/compare|find-your|switch-to|galaxy-ai|apple-intelligence|one-ui/.test(path) && !/ray-ban-meta/.test(path)) return "campaign_or_compare";
    if (/iphone-17-pro|pixel_10_pro|xiaomi-17-ultra|find-x9-ultra|x300-ultra|ipad-pro|xiaomi-pad-8-pro|airpods-pro|apple-watch-ultra|watch-ultra|buds4-pro|wf1000|wf-1000|fenix|macbook-pro|xps-16|xps-da|galaxy-s26-ultra|galaxy-tab-s11|galaxy-book|galaxy-book6-ultra|ray-ban-meta/.test(path)) return "pdp";
    if (/iphone|ipad|phones|smartphones|product-list|products|tablets|watch|watches|airpods|audio|headphones|wearables|mac|laptops|galaxybooks|galaxy-book|computers|ai-glasses/.test(path)) return "pf";
    return "content";
  } catch { return "content"; }
};
export const pageRoleKo = (role?: string) => {
  if (role === "pf") return "PF";
  if (role === "pdp") return "PDP";
  if (role === "buying") return "Buying";
  if (role === "compare") return "Compare";
  if (role === "campaign" || role === "campaign_or_compare") return "Compare/Campaign";
  if (role === "specs") return "Specs";
  if (role === "content") return "Content";
  if (role === "home") return "Home";
  return role || "Page";
};
export const productCategoryKo = (category?: string) => PRODUCT_CATEGORY_META[category || ""]?.label || category || "제품군 미확정";
export const productCategoryDesc = (category?: string) => PRODUCT_CATEGORY_META[category || ""]?.desc || "제품군이 확정되지 않은 URL입니다. 관리 URL 라벨을 확인하세요.";
export const roleDisplayKo = (role?: string) => {
  if (role === "pf") return "PF";
  if (role === "pdp") return "제품 상세 페이지";
  if (role === "buying") return "구매페이지";
  if (role === "specs") return "스펙 페이지";
  if (role === "campaign" || role === "compare" || role === "campaign_or_compare") return "비교/캠페인 페이지";
  if (role === "home") return "홈";
  return "콘텐츠 페이지";
};
export const productCategoryFromUrl = (u: string): ProductCategory => {
  try {
    const url = new URL(u);
    const raw = `${url.hostname} ${url.pathname} ${url.search}`.toLowerCase();
    // site별 대표 제품군 fallback. /products, /p/1723221처럼 제품명이 짧은 URL도 기타로 보내지 않습니다.
    if (/meta\.com|ai-glasses|ray-ban-meta/.test(raw)) return "ai_glass";
    if (/garmin\.com|watch|watches|wearables|smartwatches|fenix/.test(raw)) return "watch";
    if (/electronics\.sony\.com|audio-sound|airpods|buds|headphones|earbuds|wf1000|wf-1000/.test(raw)) return "audio";
    // Galaxy Book SG 일부 URL은 /business/tablets/ 아래에 있어도 제품군은 노트북/PC로 봅니다.
    if (/dell\.com|galaxy[-]?book|macbook|\/mac\/|laptop|laptops|xps|computers/.test(raw)) return "laptop";
    if (/tablet|tablets|ipad|xiaomi-pad|galaxy-tab/.test(raw)) return "tablet";
    if (/vivo\.com|oppo\.com|store\.google\.com|smartphone|smartphones|phone|phones|iphone|pixel|xiaomi-17|find-x|x300|galaxy-s/.test(raw)) return "phone";
    return "phone";
  } catch { return "phone"; }
};
export const productCategoryFromRow = (row?: Partial<UrlRow> | null, url?: string): ProductCategory => {
  const raw = (row?.product_category || "") as ProductCategory;
  return PRODUCT_CATEGORY_META[raw] ? raw : productCategoryFromUrl(url || row?.url || "");
};
export const productPageLabel = (row?: Partial<UrlRow> | null, url?: string) => {
  if (row?.page_label) return row.page_label;
  const target = url || row?.url || "";
  const category = productCategoryFromRow(row, target);
  const role = row?.page_role || pageRoleFromUrl(target);
  return `${productCategoryKo(category)} ${roleDisplayKo(role)}`;
};
export const pageRoleFromText = (raw: string) => {
  const t = raw.toLowerCase();
  if (/buying|buy|구매|shop|cart|장바구니/.test(t)) return "buying";
  if (/pf|family|category|카테고리|제품군/.test(t)) return "pf";
  if (/pdp|detail|상세/.test(t)) return "pdp";
  if (/spec|스펙|specs/.test(t)) return "specs";
  if (/compare|비교|campaign|캠페인/.test(t)) return "campaign_or_compare";
  return undefined;
};

// 백엔드 config.py::tier_for_url() 과 동일 계열 로직(폴백용). 1차 소스는 /api/urls 의 tier_level.
export const tierForUrl = (u: string): number => {
  try {
    const role = pageRoleFromUrl(u);
    if (role === "home") return 0;
    if (role === "pf") return 1;
    if (role === "campaign" || role === "compare") return 2;
    if (role === "pdp") return 3;
    if (role === "buying") return 4;
    return 3;
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
// 사이트 하나의 DATA/COPY/VISUAL 점수(0~100)만 뽑아낸다. 근거 없으면 null.
// (metricScoreBreakdown의 3개 하위지표 평균과 동일한 값 — 아래에서 breakdown 계산 후 재사용)
export const siteMetricScore = (metric: MetricTab, block?: AnalysisBlock): number | null =>
  metricScoreBreakdown(metric, block).total;

export type ScoreComponent = { label: string; value: number | null };
export type ScoreBreakdown = { components: ScoreComponent[]; total: number | null };
export type ScoreTier = "good" | "mid" | "bad" | "none";

// 점수 = 하위 지표 3개의 단순 평균 (AI 추론 없이 존재하는 facts만 재조합).
export const metricScoreBreakdown = (metric: MetricTab, block?: AnalysisBlock): ScoreBreakdown => {
  const f: any = block?.facts || {};
  let components: ScoreComponent[];

  if (metric === "data") {
    const schema = typeof f.schema?.coverage_pct === "number" ? Math.round(f.schema.coverage_pct) : null;
    const h1 = typeof f.html_structure?.h_tag_coverage?.h1_coverage_pct === "number"
      ? Math.round(f.html_structure.h_tag_coverage.h1_coverage_pct) : null;
    const typeCount = f.schema?.schema_type_counts ? Object.keys(f.schema.schema_type_counts).length : 0;
    const structured = typeCount > 0 ? Math.min(100, typeCount * 30) : schema;
    components = [
      { label: "Schema", value: schema },
      { label: "H-tag", value: h1 },
      { label: "Structured", value: structured },
    ];
  } else if (metric === "copy") {
    const pages = Array.isArray(f.copy_richness?.all_pages) ? f.copy_richness.all_pages : [];
    const richness = pages.length
      ? Math.round(pages.reduce((s: number, p: any) => s + (Number(p?.score) || 0), 0) / pages.length) : null;
    const totalPages = pages.length || (typeof f.page_inventory?.total_pages === "number" ? f.page_inventory.total_pages : 0);
    const buyCta = typeof f.commerce_cta?.pages_with_buy_cta === "number" ? f.commerce_cta.pages_with_buy_cta : null;
    const ctaCoverage = buyCta != null && totalPages ? Math.round((buyCta / totalPages) * 100) : null;
    const wordOk = pages.filter((p: any) => (Number(p?.word_count) || 0) >= 80).length;
    const wordCoverage = pages.length ? Math.round((wordOk / pages.length) * 100) : null;
    components = [
      { label: "Copy richness", value: richness },
      { label: "CTA coverage", value: ctaCoverage },
      { label: "Word coverage", value: wordCoverage },
    ];
  } else {
    const altRatio = typeof f.alt_text_quality?.descriptive_ratio_pct === "number"
      ? Math.round(f.alt_text_quality.descriptive_ratio_pct) : null;
    const diversity = typeof f.image_diversity?.lifestyle_ratio_pct === "number"
      ? Math.round(f.image_diversity.lifestyle_ratio_pct) : null;
    const totalImages = typeof f.image_diversity?.total_images === "number" ? f.image_diversity.total_images : 0;
    const totalPages = typeof f.page_inventory?.total_pages === "number" ? f.page_inventory.total_pages : totalImages;
    const coverage = totalImages > 0 && totalPages ? Math.min(100, Math.round((totalImages / totalPages) * 100)) : null;
    components = [
      { label: "ALT ratio", value: altRatio },
      { label: "Image diversity", value: diversity },
      { label: "Coverage", value: coverage },
    ];
  }

  const valid = components.map((c) => c.value).filter((v): v is number => v != null);
  const total = valid.length ? Math.round(valid.reduce((a, b) => a + b, 0) / valid.length) : null;
  return { components, total };
};

// 절대 기준 신호등 — 평균 대비가 아니라 고정 구간(70/40)으로 판단
export const scoreTier = (score: number | null): ScoreTier => {
  if (score == null) return "none";
  if (score >= 70) return "good";
  if (score >= 40) return "mid";
  return "bad";
};
export const scoreTierEmoji = (tier: ScoreTier) => tier === "good" ? "🟢" : tier === "mid" ? "🟡" : tier === "bad" ? "🔴" : "⚪";
export const scoreTierLabel = (tier: ScoreTier) => tier === "good" ? "Strong" : tier === "mid" ? "Moderate" : tier === "bad" ? "Needs Attention" : "근거 없음";

// 지표 상태를 짧은 서술 phrase로 — 배지성 금지어("약함","부족","보완 필요") 대신 구체적 방향성 서술
export const metricPhrase = (metric: MetricTab, tier: ScoreTier): string => {
  if (metric === "data") {
    if (tier === "good") return "구조 데이터 적용 범위 넓음";
    if (tier === "mid") return "구조 데이터 적용 범위 보통";
    if (tier === "bad") return "구조 데이터 적용 범위 제한적";
    return "구조 데이터 근거 없음";
  }
  if (metric === "copy") {
    if (tier === "good") return "CTA 연결 범위 높음";
    if (tier === "mid") return "CTA 연결 범위 보통";
    if (tier === "bad") return "CTA 연결 범위 제한적";
    return "카피 근거 없음";
  }
  if (tier === "good") return "설명형 ALT 비율 높음";
  if (tier === "mid") return "설명형 ALT 비율 보통";
  if (tier === "bad") return "설명형 ALT 비율 낮음";
  return "이미지 근거 없음";
};

// 짧은 우선 액션 phrase (문장이 아니라 2~6단어 지시형) — 스펙 톤: "PDP Product Schema 보강" 같은 형태
export const shortActionPhrase = (metric: MetricTab, tier: ScoreTier): string => {
  if (metric === "data") return tier === "bad" ? "PDP Product 스키마 보강" : tier === "mid" ? "Buying Offer 스키마 점검" : "현재 구조 유지";
  if (metric === "copy") return tier === "bad" ? "PDP CTA 우선 추가" : tier === "mid" ? "FAQ 구체성 보강" : "현재 카피 유지";
  return tier === "bad" ? "기능 중심 ALT 보강" : tier === "mid" ? "사용 장면 ALT 추가" : "현재 이미지 구성 유지";
};

// ── 세분화된 액션 규칙표 ──
// 등급(tier) 3단만으로는 액션이 다 똑같아 보이므로, 실제 facts(스키마 타입 종류/CTA 개수/이미지 개수 등)를
// 조건으로 걸어 축마다 10개 이상의 서로 다른 액션이 나오게 한다. 위에서부터 먼저 맞는 규칙을 채택.
const hasType = (types: string[], re: RegExp) => types.some((t) => re.test(t));

export const detailedAction = (metric: MetricTab, block?: AnalysisBlock): string => {
  const f: any = block?.facts || {};
  const breakdown = metricScoreBreakdown(metric, block);
  const val = (label: string) => breakdown.components.find((c) => c.label === label)?.value ?? null;

  if (metric === "data") {
    const schema = val("Schema");
    const h1 = val("H-tag");
    const types = f.schema?.schema_type_counts ? Object.keys(f.schema.schema_type_counts) : [];
    const roles = f.page_inventory?.by_page_role || {};
    const hasPf = (roles.pf || 0) > 0, hasPdp = (roles.pdp || 0) > 0, hasBuying = (roles.buying || 0) > 0;

    if (schema == null && h1 == null) return "관리 URL과 수집 결과부터 확보하세요.";
    if (schema === 0 && h1 === 0) return "Schema와 H-tag 기본 마크업부터 추가하세요.";
    if (hasPdp && !hasType(types, /product/i)) return "PDP에 Product 스키마를 추가하세요.";
    if (hasBuying && !hasType(types, /offer/i)) return "Buying 페이지에 Offer 스키마를 추가해 가격·재고 신호를 노출하세요.";
    if (hasPf && !hasType(types, /itemlist|collectionpage/i)) return "PF에 ItemList/CollectionPage 스키마를 추가하세요.";
    if (!hasType(types, /breadcrumb/i) && types.length > 0) return "Breadcrumb 스키마를 추가해 탐색 경로 신호를 보강하세요.";
    if ((schema ?? 0) < 40 && (h1 ?? 100) >= 70) return "Schema 마크업 적용 페이지를 늘리세요.";
    if ((h1 ?? 0) < 40 && (schema ?? 100) >= 70) return "H1/H2 태그 계층을 정리하세요.";
    if (types.length > 0 && types.length <= 2 && hasType(types, /webpage|organization/i)) return "일반 타입(WebPage/Organization) 외에 역할별 스키마 타입을 확장하세요.";
    if ((schema ?? 0) >= 40 && (schema ?? 0) < 70) return "역할별(PF/PDP/Buying) 스키마 적용 범위를 점검하세요.";
    if ((schema ?? 0) >= 70 && (h1 ?? 0) >= 70 && types.length >= 3) return "현재 구조 유지, 다음 수집에서 변화만 확인하세요.";
    return "PF는 ItemList/Breadcrumb, PDP는 Product/Breadcrumb, Buying은 Offer 중심으로 점검하세요.";
  }

  if (metric === "copy") {
    const richness = val("Copy richness");
    const cta = val("CTA coverage");
    const words = val("Word coverage");
    const buyCtaPages = typeof f.commerce_cta?.pages_with_buy_cta === "number" ? f.commerce_cta.pages_with_buy_cta : null;
    const faqCount = typeof f.faq?.count === "number" ? f.faq.count : null;

    if (richness == null && cta == null) return "카피 근거부터 확보하세요.";
    // 실제 카피(분량·구체성)를 CTA보다 먼저 판단 — 우선 액션이 CTA로 쏠리지 않도록
    if ((words ?? 100) < 40) return "제품 설명 분량(스펙·소재·기능)을 먼저 보강하세요.";
    if ((richness ?? 100) < 40) return "카피 구체성(수치·소재·기능 언급)을 보강하세요.";
    if ((richness ?? 100) < 60) return "PDP·PF 카피에 수치·혜택·비교 근거를 더해 구체성을 높이세요.";
    if (faqCount === 0) return "FAQ 콘텐츠를 추가해 탐색 단계 이탈을 줄이세요.";
    if ((words ?? 100) < 70) return "페이지별 설명 분량 편차를 줄이세요.";
    if ((richness ?? 0) >= 60 && (richness ?? 0) < 70) return "톤 일관성과 혜택 문구를 점검하세요.";
    // CTA는 실제로 비어 있거나 매우 낮을 때만, 그리고 카피 점검 뒤 후순위로
    if (cta === 0 && buyCtaPages === 0) return "구매 관련 페이지에 구매 CTA가 없으니 최소한의 CTA부터 추가하세요.";
    if ((cta ?? 100) < 30) return "카피는 갖춰졌으나 구매 CTA가 부족한 페이지에 CTA를 보강하세요.";
    if ((richness ?? 0) >= 70 && (words ?? 0) >= 70) return "현재 카피 유지, 경쟁사 문구 변화만 주기적으로 확인하세요.";
    return "PDP·Buying 카피의 구체성(수치·혜택·소재)을 보강하고, 구매 CTA는 부족한 경우에만 함께 점검하세요.";
  }

  const alt = val("ALT ratio");
  const diversity = val("Image diversity");
  const coverage = val("Coverage");
  const totalImages = typeof f.image_diversity?.total_images === "number" ? f.image_diversity.total_images : 0;

  if (alt == null && diversity == null) return "이미지 근거부터 확보하세요.";
  if (totalImages === 0) return "제품 페이지에 이미지부터 확보하세요.";
  if (alt === 0) return "ALT 텍스트부터 전 페이지에 추가하세요.";
  if ((alt ?? 100) < 30) return "ALT 텍스트에 제품명·핵심 기능을 구체적으로 담으세요.";
  if ((diversity ?? 100) < 20 && (alt ?? 0) >= 50) return "제품 단독 컷 위주라 사용 장면 이미지를 추가하세요.";
  if ((diversity ?? 0) >= 20 && (diversity ?? 0) < 40) return "라이프스타일 이미지 비중을 조금 더 늘리세요.";
  if ((coverage ?? 100) < 50) return "이미지가 적은 페이지부터 추가 촬영/소싱하세요.";
  if ((alt ?? 0) >= 40 && (alt ?? 0) < 70) return "설명형 ALT 비율을 페이지 전반으로 확대하세요.";
  if ((diversity ?? 0) >= 60 && (alt ?? 0) < 60) return "이미지 구성은 다양하나 설명(ALT)이 상대적으로 부족하니 보강하세요.";
  if ((alt ?? 0) >= 70 && (diversity ?? 0) >= 40) return "현재 이미지 구성 유지, 신제품 출시 시 사용 장면 컷만 추가하세요.";
  return "제품명, 핵심 기능, 사용 장면이 드러나도록 ALT COPY와 이미지 설명을 보강하세요.";
};

export const metricAverage = (sitePages: PageLite[], block?: AnalysisBlock) => {
  const f = block?.facts || {};
  const copyPages = Array.isArray(f.copy_richness?.all_pages) ? f.copy_richness.all_pages.length : null;
  const buyCtaPages = typeof f.commerce_cta?.pages_with_buy_cta === "number" ? f.commerce_cta.pages_with_buy_cta : null;
  return {
    pages: sitePages.length,
    avgWords: sitePages.length
      ? Math.round(sitePages.reduce((a, p) => a + (p.word_count || 0), 0) / sitePages.length)
      : 0,
    schema: typeof f.schema?.coverage_pct === "number" ? f.schema.coverage_pct + "%" : "-",
    thin: buyCtaPages != null
      ? `${buyCtaPages}p`
      : copyPages != null ? `${copyPages}p` : "-",
    lifestyle: typeof f.image_diversity?.lifestyle_ratio_pct === "number"
      ? f.image_diversity.lifestyle_ratio_pct + "%" : "-",
  };
};

// 지표(DATA/COPY/VISUAL) 하나를 핵심 한줄 + 숫자 통계로 요약. 실제 facts/changes만 사용(생성 없음).
// expectedSites를 넘기면 “현재 수집된 사이트만”이 아니라 “관리 대상 전체 중 어디가 수집/미수집인지”까지 보여준다.
export const metricOneLiner = (
  metric: MetricTab,
  dcvForMetric: Record<string, AnalysisBlock> | undefined,
  changes: Change[],
  expectedSites: SiteKey[] = []
): string => {
  const blocks = dcvForMetric || {};
  const collectedKeys = orderedSiteKeys(Object.keys(blocks));
  const managedKeys = orderedSiteKeys([...expectedSites, ...collectedKeys, ...changes.map((c) => c.site || "")]);
  const high = changes.filter((c) => c.level === "High").length;
  const changedSites = orderedSiteKeys(changes.map((c) => c.site || "")).map(siteShortName);
  const missingKeys = managedKeys.filter((site) => !blocks[site]);
  const collectedLabel = collectedKeys.length ? collectedKeys.slice(0, 5).map(siteShortName).join(", ") : "없음";
  const missingLabel = missingKeys.length
    ? ` · 근거 부족 ${missingKeys.length}개(${missingKeys.slice(0, 4).map(siteShortName).join(", ")}${missingKeys.length > 4 ? " 외" : ""})`
    : "";

  const numberList = <T,>(items: T[], mapper: (x: T) => number | null | undefined) => {
    const vals = items.map(mapper).map((x) => Number(x)).filter((x) => Number.isFinite(x));
    if (vals.length === 0) return "-";
    return Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10;
  };

  let statLine = "";
  if (metric === "data") {
    const avg = numberList(collectedKeys, (site) => blocks[site]?.facts?.schema?.coverage_pct);
    statLine = `DATA / Schema: 근거 확보 ${collectedKeys.length}/${managedKeys.length || collectedKeys.length}개 사이트 · 평균 Schema ${avg}% · 대상 ${collectedLabel}${missingLabel}`;
  } else if (metric === "copy") {
    const copyAvg = (f: any) => {
      const pages = f?.copy_richness?.all_pages || [];
      if (!Array.isArray(pages) || pages.length === 0) return null;
      const total = pages.reduce((sum: number, p: any) => sum + (Number(p?.score) || 0), 0);
      return Math.round((total / pages.length) * 10) / 10;
    };
    const avg = numberList(collectedKeys, (site) => copyAvg(blocks[site]?.facts));
    const cta = numberList(collectedKeys, (site) => blocks[site]?.facts?.commerce_cta?.pages_with_buy_cta);
    statLine = `COPY / CTA: 근거 확보 ${collectedKeys.length}/${managedKeys.length || collectedKeys.length}개 사이트 · 구매 CTA 평균 ${cta}페이지 · 카피 구체성 ${avg}점 · 대상 ${collectedLabel}${missingLabel}`;
  } else {
    const avg = numberList(collectedKeys, (site) => blocks[site]?.facts?.image_diversity?.lifestyle_ratio_pct);
    statLine = `VISUAL / ALT COPY: 근거 확보 ${collectedKeys.length}/${managedKeys.length || collectedKeys.length}개 사이트 · 사용 장면 신호 평균 ${avg}% · 대상 ${collectedLabel}${missingLabel}`;
  }
  const changeText = changes.length
    ? `변경 ${changes.length}건(High ${high}) · 변경 사이트: ${changedSites.join(", ") || "-"}`
    : "큰 변경 없음 · 현재 상태를 유지하며 다음 비교에서 변화만 확인";
  return `${statLine} · ${changeText} · ${metricActionSentence(metric)}`;
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
