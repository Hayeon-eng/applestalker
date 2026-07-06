/* shared.ts에서 분리 — 점수/티어/액션/원라이너 로직. 타입·상수·URL 유틸은 sharedCore.ts */
import {
  MetricTab, MetricView, AnalysisBlock, PageLite, Change, SiteKey, metricActionSentence,
  orderedSiteKeys, siteName, siteShortName, metricAreaLabel,
} from "./sharedCore";

// 사이트 하나의 DATA/COPY/VISUAL 점수(0~100)만 뽑아낸다. 근거 없으면 null.
// (metricScoreBreakdown의 3개 하위지표 평균과 동일한 값 — 아래에서 breakdown 계산 후 재사용)
export const siteMetricScore = (metric: MetricTab, block?: AnalysisBlock): number | null =>
  metricScoreBreakdown(metric, block).total;

export type ScoreComponent = { label: string; value: number | null };
export type ScoreBreakdown = { components: ScoreComponent[]; allComponents: ScoreComponent[]; total: number | null };
export type ScoreTier = "good" | "mid" | "bad" | "none";

// 점수 = 하위 지표 전체의 단순 평균(DATA/COPY 6개, VISUAL 3개). 카드 노출은 주요 3개(components).
// AI 추론 없이 존재하는 facts만 재조합. allComponents = 점수 산출용 전체, components = 표시용 상위 3.
export const metricScoreBreakdown = (metric: MetricTab, block?: AnalysisBlock): ScoreBreakdown => {
  const f: any = block?.facts || {};
  let allComponents: ScoreComponent[];

  if (metric === "data") {
    const schema = typeof f.schema?.coverage_pct === "number" ? Math.round(f.schema.coverage_pct) : null;
    const h1 = typeof f.html_structure?.h_tag_coverage?.h1_coverage_pct === "number"
      ? Math.round(f.html_structure.h_tag_coverage.h1_coverage_pct) : null;
    const typeCount = f.schema?.schema_type_counts ? Object.keys(f.schema.schema_type_counts).length : 0;
    const structured = typeCount > 0 ? Math.min(100, typeCount * 30) : schema;
    const totalPages = typeof f.schema?.total_pages === "number" ? f.schema.total_pages : 0;
    const roleGaps = Array.isArray(f.schema?.role_alignment_gaps) ? f.schema.role_alignment_gaps.length : 0;
    const roleFit = totalPages > 0 ? Math.round(((totalPages - Math.min(roleGaps, totalPages)) / totalPages) * 100) : null;
    const productFill = typeof f.schema?.completeness?.Product?.filled_ratio === "number"
      ? Math.round(f.schema.completeness.Product.filled_ratio * 100) : null;
    const idTotal = typeof f.schema?.id_linkage?.total_id_nodes === "number" ? f.schema.id_linkage.total_id_nodes : 0;
    const idLinked = typeof f.schema?.id_linkage?.linked_ids === "number" ? f.schema.id_linkage.linked_ids : 0;
    const idLinkage = idTotal > 0 ? Math.round((idLinked / idTotal) * 100) : null;
    allComponents = [
      { label: "Schema", value: schema },
      { label: "H-tag", value: h1 },
      { label: "Structured", value: structured },
      { label: "역할적합성", value: roleFit },
      { label: "Product 완성도", value: productFill },
      { label: "@id 연결성", value: idLinkage },
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
    const faqDetail = Array.isArray(f.faq?.detail) ? f.faq.detail : [];
    const faqQuality = faqDetail.length
      ? Math.round(faqDetail.reduce((s: number, d: any) => s + (Number(d?.avg_score) || 0), 0) / faqDetail.length) : null;
    const intentGap = Array.isArray(f.copy_richness?.intent_gap_pages) ? f.copy_richness.intent_gap_pages.length : 0;
    const intentFit = pages.length ? Math.round(((pages.length - Math.min(intentGap, pages.length)) / pages.length) * 100) : null;
    const dupCount = (Array.isArray(f.duplication?.duplicate_copy_pages) ? f.duplication.duplicate_copy_pages.length : 0)
      + (Array.isArray(f.duplication?.duplicate_cta_pages) ? f.duplication.duplicate_cta_pages.length : 0);
    const dupAvoid = totalPages ? 100 - Math.round((Math.min(dupCount, totalPages) / totalPages) * 100) : null;
    allComponents = [
      { label: "Copy richness", value: richness },
      { label: "CTA coverage", value: ctaCoverage },
      { label: "Word coverage", value: wordCoverage },
      { label: "FAQ 품질", value: faqQuality },
      { label: "intent 충족", value: intentFit },
      { label: "중복 회피", value: dupAvoid },
    ];
  } else {
    const altRatio = typeof f.alt_text_quality?.descriptive_ratio_pct === "number"
      ? Math.round(f.alt_text_quality.descriptive_ratio_pct) : null;
    const diversity = typeof f.image_diversity?.lifestyle_ratio_pct === "number"
      ? Math.round(f.image_diversity.lifestyle_ratio_pct) : null;
    const totalImages = typeof f.image_diversity?.total_images === "number" ? f.image_diversity.total_images : 0;
    const totalPages = typeof f.page_inventory?.total_pages === "number" ? f.page_inventory.total_pages : totalImages;
    const coverage = totalImages > 0 && totalPages ? Math.min(100, Math.round((totalImages / totalPages) * 100)) : null;
    allComponents = [
      { label: "ALT ratio", value: altRatio },
      { label: "Image diversity", value: diversity },
      { label: "Coverage", value: coverage },
    ];
  }

  const components = allComponents.slice(0, 3);
  const valid = allComponents.map((c) => c.value).filter((v): v is number => v != null);
  const total = valid.length ? Math.round(valid.reduce((a, b) => a + b, 0) / valid.length) : null;
  return { components, allComponents, total };
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
    const productMissing: string[] = f.schema?.completeness?.Product?.missing_properties || [];
    const advGaps = Array.isArray(f.schema?.role_advanced_gaps) ? f.schema.role_advanced_gaps.length : 0;

    if (schema == null && h1 == null) return "관리 URL·수집 결과 없음 — 먼저 수집 근거를 확보하세요.";
    if (schema === 0 && h1 === 0) return "Schema·H-tag 기본 마크업 없음 — 기본 구조화 마크업부터 추가하세요.";
    if (hasPdp && !hasType(types, /product/i)) return "PDP에 Product 스키마·@id 참조 모두 없음 — Product를 추가하거나 @id로 연결해 제품 신호를 노출하세요.";
    if (hasBuying && !hasType(types, /productgroup/i)) return "Buying에 ProductGroup 없음 — ProductGroup을 추가해 구매 옵션 묶음 신호를 노출하세요.";
    if (hasPf && !hasType(types, /itemlist|collectionpage/i)) return "PF에 ItemList/CollectionPage 없음 — 목록 스키마를 추가해 카테고리 페이지 성격을 노출하세요.";
    if (!hasType(types, /breadcrumb/i) && types.length > 0) return "BreadcrumbList 없음 — Breadcrumb로 탐색 경로 신호를 보강하세요.";
    if (hasType(types, /product/i) && productMissing.length > 0) return "Product는 있으나 가격·재고 등 속성 부족 — offers·price·availability 속성을 채워 구매 단서를 노출하세요.";
    if ((schema ?? 0) < 40 && (h1 ?? 100) >= 70) return "Schema 적용 페이지 비율 낮음 — 적용 페이지를 늘려 구조화 신호를 확대하세요.";
    if ((h1 ?? 0) < 40 && (schema ?? 100) >= 70) return "H1 커버리지 낮음 — H1/H2 계층을 정리해 문서 구조 신호를 명확히 하세요.";
    if (types.length > 0 && types.length <= 2 && hasType(types, /webpage|organization/i)) return "WebPage/Organization 같은 일반 타입만 있음 — PF엔 ItemList, PDP엔 Product처럼 역할에 맞는 타입을 추가하세요.";
    if (hasPdp && advGaps > 0) return "PDP에 FAQPage·Quotation·3DModel·VideoObject 같은 고급 스키마 없음 — 없어도 되지만 있으면 검색·AI 노출에 유리한 보강 기회입니다(선택).";
    if ((schema ?? 0) >= 40 && (schema ?? 0) < 70) return "역할별 스키마 적용 범위 편차 — PF/PDP/Buying별 적용을 점검하세요.";
    if ((schema ?? 0) >= 70 && (h1 ?? 0) >= 70 && types.length >= 3) return "핵심 스키마 신호 양호 — 현재 구조 유지, 다음 수집에서 변화만 확인하세요.";
    return "역할별로 PF는 ItemList/Breadcrumb, PDP는 Product/Breadcrumb, Buying은 ProductGroup 중심으로 점검하세요.";
  }

  if (metric === "copy") {
    const richness = val("Copy richness");
    const cta = val("CTA coverage");
    const words = val("Word coverage");
    const buyCtaPages = typeof f.commerce_cta?.pages_with_buy_cta === "number" ? f.commerce_cta.pages_with_buy_cta : null;
    const faqPages = typeof f.faq?.pages_with_faq === "number" ? f.faq.pages_with_faq : null;
    const dupCount = (Array.isArray(f.duplication?.duplicate_copy_pages) ? f.duplication.duplicate_copy_pages.length : 0)
      + (Array.isArray(f.duplication?.duplicate_cta_pages) ? f.duplication.duplicate_cta_pages.length : 0);

    if (richness == null && cta == null) return "카피 근거 없음 — 먼저 수집 근거를 확보하세요.";
    if ((words ?? 100) < 40) return "본문 분량(80단어 이상) 충족 페이지 비율 낮음 — 스펙·소재·기능 설명을 추가해 제품 이해도↑.";
    if ((richness ?? 100) < 40) return "카피 구체성 점수 낮음 — 수치·소재·기능 언급을 추가해 구체성↑.";
    if ((faqPages ?? 0) > 0 && (words ?? 100) < 70) return "FAQ는 있으나 본문 분량 충족 페이지가 적음 — 제품 설명 분량을 보강해 이해도↑.";
    if ((richness ?? 100) < 60) return "카피 구체성 점수 보통 — 수치·혜택·비교 근거를 더해 구체성↑.";
    if ((faqPages ?? 0) === 0) return "FAQ 구조 없음 — PDP·Buying 핵심 질문(가격·호환·배송) 대응 FAQ를 추가하세요.";
    if ((words ?? 100) >= 70 && dupCount > 0) return "본문 분량은 충분하나 중복 카피·CTA 반복 — 중복을 정리해 페이지별 메시지를 차별화하세요.";
    if (cta === 0 && buyCtaPages === 0) return "구매 CTA 없음 — PDP·Buying에 Buy/Where to buy 버튼을 배치해 전환 경로를 확보하세요.";
    if ((cta ?? 100) < 30) return "구매 CTA 커버리지 낮음 — CTA 없는 PDP·Buying에 구매 버튼을 보강하세요.";
    if ((richness ?? 0) >= 70 && (words ?? 0) >= 70) return "핵심 카피 신호 양호 — 현재 유지, 경쟁사 문구 변화만 모니터하세요.";
    return "PDP·Buying 카피의 구체성(수치·혜택·소재)을 보강하고, 구매 CTA는 부족한 페이지에 한해 함께 점검하세요.";
  }

  const alt = val("ALT ratio");
  const diversity = val("Image diversity");
  const coverage = val("Coverage");
  const totalImages = typeof f.image_diversity?.total_images === "number" ? f.image_diversity.total_images : 0;
  const CAVEAT = " (HTML 신호 기준, 실제 이미지 미검증)";
  let a: string;
  if (alt == null && diversity == null) a = "이미지 근거 없음 — 원본/렌더 확인 후 재수집하세요.";
  else if (totalImages === 0) a = "수집된 이미지 없음 — 렌더 여부를 확인하고 핵심 비교에서 제외하세요.";
  else if (alt === 0) a = "설명형 ALT 없음 — 전 페이지에 ALT 텍스트를 추가하세요.";
  else if ((alt ?? 100) < 30) a = "설명형 ALT 비율 낮음 — ALT에 제품명·핵심 기능을 반영해 이미지 의미를 전달하세요.";
  else if ((diversity ?? 100) < 20 && (alt ?? 0) >= 50) a = "제품 단독컷 위주(lifestyle 신호 낮음) — 사용 장면 이미지를 추가하세요.";
  else if ((coverage ?? 100) < 50) a = "이미지 적은 페이지 비율 높음 — 해당 페이지 이미지를 소싱/촬영하세요.";
  else if ((alt ?? 0) >= 40 && (alt ?? 0) < 70) a = "설명형 ALT 비율 중간 — ALT 품질을 페이지 전반으로 확대하세요.";
  else if ((diversity ?? 0) >= 60 && (alt ?? 0) < 60) a = "이미지 구성은 다양하나 ALT 설명이 상대적으로 부족 — ALT를 보강하세요.";
  else if ((alt ?? 0) >= 70 && (diversity ?? 0) >= 40) a = "이미지 신호 양호 — 현재 구성 유지, 대표 페이지만 수동 확인하세요.";
  else a = "제품명·핵심 기능·사용 장면이 드러나도록 ALT와 이미지 구성을 보강하세요.";
  return a + CAVEAT;
};

// ③B: 페이지 단위 조건부 액션 목록. 첫 매칭 1개가 아니라 해당 페이지에 걸리는 것들을 모두 반환.
// facts는 페이지 상세 API가 만든 '이 페이지 1건'의 facts (사이트 집계와 동일 구조).
export const pageActionLines = (metric: MetricTab, block?: AnalysisBlock): string[] => {
  const f: any = block?.facts || {};
  const out: string[] = [];

  if (metric === "data") {
    const nodes = f.schema?.schema_type_counts ? Object.keys(f.schema.schema_type_counts) : [];
    const role = Object.keys(f.schema?.page_role_distribution || {})[0] || "";
    const productMissing: string[] = f.schema?.completeness?.Product?.missing_properties || [];
    const coreGaps = Array.isArray(f.schema?.role_alignment_gaps) ? f.schema.role_alignment_gaps : [];
    const advGaps = Array.isArray(f.schema?.role_advanced_gaps) ? f.schema.role_advanced_gaps : [];
    if ((f.schema?.total_pages ?? 0) === 0 || nodes.length === 0) {
      out.push("구조화 데이터 없음 — 페이지 역할에 맞는 스키마부터 추가.");
    } else {
      coreGaps.slice(0, 1).forEach((g: any) => {
        const miss = (g.missing || []).join(", ");
        if (miss) out.push(`역할(${g.page_role}) 기대 신호 ${miss} 없음 — 추가하거나 @id 연결 여부를 확인.`);
      });
      if (hasType(nodes, /product/i) && productMissing.length > 0) {
        out.push("Product는 있으나 가격·재고 속성 부족 — offers·price·availability를 채워 구매 단서 노출.");
      }
      advGaps.slice(0, 1).forEach((g: any) => {
        const opp = (g.opportunity || []).join(", ");
        if (opp) out.push(`고급 스키마 ${opp} 없음 — 없어도 되지만 있으면 검색·AI 노출에 유리(선택).`);
      });
    }
    if (!out.length) out.push("핵심 스키마 신호 양호 — 현재 구조 유지.");
    return out.slice(0, 3);
  }

  if (metric === "copy") {
    const pages = Array.isArray(f.copy_richness?.all_pages) ? f.copy_richness.all_pages : [];
    const p0 = pages[0] || {};
    const wc = Number(p0.word_count) || 0;
    const score = Number(p0.score) || 0;
    const faqPages = typeof f.faq?.pages_with_faq === "number" ? f.faq.pages_with_faq : 0;
    const buyCta = typeof f.commerce_cta?.pages_with_buy_cta === "number" ? f.commerce_cta.pages_with_buy_cta : 0;
    if (faqPages > 0 && wc > 0 && wc < 150) {
      out.push(`FAQ는 있으나 본문 ${wc}단어 — 스펙·소재·기능 설명을 추가해 제품 이해도↑.`);
    } else if (wc > 0 && wc < 80) {
      out.push(`본문 ${wc}단어 — 스펙·소재·기능 설명을 추가해 제품 이해도↑.`);
    }
    if (score > 0 && score < 45) out.push(`카피 구체성 점수 ${Math.round(score)} — 수치·혜택·비교 근거를 추가해 구체성↑.`);
    if (buyCta === 0) out.push("구매 CTA 없음 — Buy/Where to buy 버튼을 배치해 전환 경로 확보.");
    if (faqPages === 0) out.push("FAQ 없음 — 가격·호환·배송 등 핵심 질문 대응 FAQ 추가.");
    if (!out.length) out.push("핵심 카피 신호 양호 — 현재 유지.");
    return out.slice(0, 3);
  }

  const alt = typeof f.alt_text_quality?.descriptive_ratio_pct === "number" ? Math.round(f.alt_text_quality.descriptive_ratio_pct) : null;
  const totalImages = typeof f.image_diversity?.total_images === "number" ? f.image_diversity.total_images : 0;
  const diversity = typeof f.image_diversity?.lifestyle_ratio_pct === "number" ? Math.round(f.image_diversity.lifestyle_ratio_pct) : null;
  const CAVEAT = " (HTML 신호 기준, 실제 이미지 미검증)";
  if (totalImages === 0) out.push("수집된 이미지 없음 — 렌더 여부 확인, 비교에서 제외 권장" + CAVEAT);
  else {
    if (alt != null && alt < 50) out.push(`설명형 ALT ${alt}% — ALT에 제품명·핵심 기능을 반영해 이미지 의미 전달` + CAVEAT);
    if (diversity != null && diversity < 20) out.push("제품 단독컷 위주 — 사용 장면 이미지를 추가" + CAVEAT);
  }
  if (!out.length) out.push("이미지 신호 양호 — 현재 구성 유지" + CAVEAT);
  return out.slice(0, 3);
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
