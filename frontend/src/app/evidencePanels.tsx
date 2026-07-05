"use client";

import {
  Change, AnalysisBlock, MetricTab, SiteKey, METRICS, siteName, shortUrl, actionForChange,
  metricScoreBreakdown, scoreTier, scoreTierEmoji, scoreTierLabel,
} from "./shared";

const EVIDENCE_LABELS: Record<string, string> = {
  kind: "종류", type: "스키마 타입", dom_hash_before: "이전 구조 해시", dom_hash_after: "이후 구조 해시",
  phash_before: "이전 이미지 해시", phash_after: "이후 이미지 해시", sentences_added: "추가된 문장",
  structure_note: "구조 비교 기준", tag_deltas: "핵심 태그 구성 변화", heading_deltas: "H2 문구 변화", cta_deltas: "CTA 문구 변화",
  copy_importance: "카피 중요도 판단",
};
const EVIDENCE_KIND_LABELS: Record<string, string> = {
  schema_added: "스키마 추가됨", schema_removed: "스키마 제거됨",
};

const TAG_NAME_LABELS: Record<string, string> = {
  main: "본문 영역(main)", section: "섹션(section)", article: "콘텐츠 블록(article)",
  header: "헤더(header)", footer: "푸터(footer)", nav: "내비게이션(nav)",
  h1: "H1 제목", h2: "H2 제목", h3: "H3 제목", ul: "목록 묶음(ul)", ol: "목록 묶음(ol)",
  li: "목록 항목(li)", a: "링크(a)", button: "버튼(button)", form: "폼(form)",
  table: "표(table)", figure: "이미지 영역(figure)", picture: "반응형 이미지(picture)",
  img: "이미지(img)", video: "영상(video)",
};

function evidenceValueToText(v: any, evidenceKey?: string): string {
  if (v === "campaign_or_conversion_copy") return "캠페인·프로모션·구매 전환 관련 문구";
  if (v === "minor_ui_or_menu_copy") return "메뉴·탭·짧은 UI 라벨성 문구";
  if (v === "general_copy") return "일반 본문 문구";
  if (Array.isArray(v)) return v.join(", ");
  if (v && typeof v === "object") {
    if ("added" in v || "removed" in v) {
      const added = Array.isArray(v.added) && v.added.length ? `추가: ${v.added.join(", ")}` : "";
      const removed = Array.isArray(v.removed) && v.removed.length ? `제거: ${v.removed.join(", ")}` : "";
      return [added, removed].filter(Boolean).join(" / ") || "변화 있음";
    }
    return Object.entries(v)
      .map(([k, val]: [string, any]) => {
        if (val && typeof val === "object" && "before" in val && "after" in val) {
          const diffNum = typeof val.diff === "number" ? val.diff : Number(val.after) - Number(val.before);
          const diff = Number.isFinite(diffNum) ? ` (${diffNum > 0 ? "+" : ""}${diffNum})` : "";
          const label = evidenceKey === "tag_deltas" ? (TAG_NAME_LABELS[k] || `${k} 태그`) : k;
          const isMinorRepeatTag = evidenceKey === "tag_deltas" && ["li", "a", "button", "ul", "ol"].includes(k) && Math.abs(diffNum || 0) <= 2;
          const note = isMinorRepeatTag ? " · 반복 UI 항목의 소폭 차이로 참고 수준" : "";
          return `${label}: ${val.before} → ${val.after}${diff}${note}`;
        }
        return `${k}: ${String(val)}`;
      })
      .join(" / ");
  }
  return String(v);
}

export function ChangeDrilldown({ change: c }: { change: Change }) {
  const ev: Record<string, any> = c.evidence || {};
  const countDeltas: Record<string, { label: string; before: number; after: number; diff: number }> | undefined =
    ev.count_deltas;
  const sentencesAdded: string[] = Array.isArray(ev.sentences_added) ? ev.sentences_added : [];
  const sentencesRemoved: string[] = Array.isArray(ev.sentences_removed) ? ev.sentences_removed : [];
  const hasStructureDetail = !!(countDeltas || ev.tag_deltas || ev.heading_deltas || ev.cta_deltas);
  const isDomHashOnly = "dom_hash_before" in ev && !("kind" in ev) && !hasStructureDetail;
  const hasKindLabel = !!(ev.kind && EVIDENCE_KIND_LABELS[ev.kind as string]);
  const otherEvidence = Object.entries(ev).filter(
    ([k]) => k !== "count_deltas" && k !== "sentences_added" && k !== "sentences_removed"
      && !(hasKindLabel && (k === "kind" || k === "type"))
  );
  const hasMoreEvidence = !!countDeltas || isDomHashOnly || otherEvidence.length > 0;

  return (
    <div className="drilldown">
      <h3>상세 근거</h3>
      <p>
        <b>페이지:</b>{" "}
        <a href={c.url} target="_blank" rel="noreferrer">{c.url}</a>
      </p>
      <p><b>분류:</b> {c.category || "-"} / {c.field || "-"}</p>
      <p className="findingText siteInsightAction" style={{ margin: "6px 0 4px" }}>액션: {actionForChange(c)}</p>
      {ev.kind && EVIDENCE_KIND_LABELS[ev.kind as string] && (
        <p style={{ marginTop: 4, fontSize: 12.5, fontWeight: 600 }}>
          {EVIDENCE_KIND_LABELS[ev.kind as string]}{ev.type ? ` — ${ev.type}` : ""}
        </p>
      )}

      {/* 정확히 무엇이 바뀌었는지 — 추가/삭제된 문장을 색으로 바로 보이게 (가장 중요한 정보라 상단에 배치) */}
      {(sentencesAdded.length > 0 || sentencesRemoved.length > 0) && (
        <div style={{ marginTop: 8, marginBottom: 4 }}>
          {sentencesRemoved.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: "var(--high)", marginBottom: 3 }}>➖ 삭제된 문장</p>
              {sentencesRemoved.map((s, i) => (
                <p key={i} className="diffContent before" style={{ marginBottom: 2 }}>{s}</p>
              ))}
            </div>
          )}
          {sentencesAdded.length > 0 && (
            <div>
              <p style={{ fontSize: 11, fontWeight: 700, color: "var(--tier-good)", marginBottom: 3 }}>➕ 추가된 문장</p>
              {sentencesAdded.map((s, i) => (
                <p key={i} className="diffContent after" style={{ marginBottom: 2 }}>{s}</p>
              ))}
            </div>
          )}
        </div>
      )}

      {c.before && (
        <div className="diffBlock">
          <p className="diffLabel">이전 (전체)</p>
          <p className="diffContent before">{c.before}</p>
        </div>
      )}
      {c.after && (
        <div className="diffBlock">
          <p className="diffLabel">현재 (전체)</p>
          <p className="diffContent after">{c.after}</p>
        </div>
      )}

      {/* 기술적 원시값(해시, 태그 개수 등)은 필요할 때만 펼쳐서 봄 */}
      {hasMoreEvidence && (
        <details className="siteScoreDetails" style={{ marginTop: 10 }}>
          <summary>근거 더보기</summary>
          {countDeltas && (
            <div style={{ marginTop: 10 }}>
              <p style={{ fontSize: 11.5, fontWeight: 600, color: "var(--sec)", marginBottom: 4 }}>
                구조 세부 변화 (h2/h3/CTA/FAQ/이미지 개수 비교)
              </p>
              <div className="evidenceGrid">
                {Object.values(countDeltas).map((d) => (
                  <>
                    <span key={d.label + "_k"} className="evidenceKey">{d.label}</span>
                    <span key={d.label + "_v"} className="evidenceVal">
                      {d.before} → {d.after} ({d.diff > 0 ? "+" : ""}{d.diff})
                    </span>
                  </>
                ))}
              </div>
            </div>
          )}
          {isDomHashOnly && (
            <p className="termDetail" style={{ marginTop: 8 }}>
              저장된 구조 지표 기준으로 DOM 골격 변화가 감지되었습니다. H2/H3·CTA·FAQ·이미지 개수 변화가 없다면
              요소의 순서, 중첩, 속성 또는 배치가 달라진 케이스로 표시됩니다.
            </p>
          )}
          {otherEvidence.length > 0 && (
            <div className="evidenceGrid" style={{ marginTop: 8 }}>
              {otherEvidence.map(([k, v]) => (
                <>
                  <span key={k + "_k"} className="evidenceKey">{EVIDENCE_LABELS[k] || k}</span>
                  <span key={k + "_v"} className="evidenceVal">{evidenceValueToText(v, k)}</span>
                </>
              ))}
            </div>
          )}
        </details>
      )}
    </div>
  );
}


export type CurrentFindingSelection = {
  site: SiteKey;
  index: number;
  line: string;
  label: string;
};

type DetailRow = { key: string; value: string };

const pctText = (v: any) => (typeof v === "number" ? `${v}%` : v == null ? "-" : String(v));
const countText = (v: any) => (typeof v === "number" ? v.toLocaleString() : v == null ? "-" : String(v));
const ratioText = (v: any) => (typeof v === "number" ? `${Math.round(v * 100)}%` : v == null ? "-" : String(v));

const mapToText = (obj: any, limit = 8) => {
  if (!obj || typeof obj !== "object") return "-";
  const entries = Object.entries(obj).slice(0, limit);
  if (entries.length === 0) return "-";
  return entries.map(([k, v]) => {
    if (v && typeof v === "object") {
      const bits = [
        (v as any).pages != null ? `${countText((v as any).pages)}p` : null,
        (v as any).avg_images != null ? `이미지 ${countText((v as any).avg_images)}장` : null,
        (v as any).avg_words != null ? `단어 ${countText((v as any).avg_words)}` : null,
        (v as any).avg_word_count != null ? `평균 ${countText((v as any).avg_word_count)}단어` : null,
      ].filter(Boolean).join(" · ");
      return `${k} ${bits || JSON.stringify(v).slice(0, 80)}`;
    }
    return `${k} ${countText(v)}`;
  }).join(" / ");
};

const urlListText = (urls: any, emptyText = "없음") => {
  if (!Array.isArray(urls) || urls.length === 0) return emptyText;
  return urls.slice(0, 5).map((u) => shortUrl(String(u))).join(" / ") + (urls.length > 5 ? ` 외 ${urls.length - 5}건` : "");
};

const pageListText = (pages: any, emptyText = "없음") => {
  if (!Array.isArray(pages) || pages.length === 0) return emptyText;
  return pages.slice(0, 5).map((p) => {
    if (typeof p === "string") return shortUrl(p);
    const url = p?.url ? shortUrl(String(p.url)) : "페이지";
    const extras = [p?.count != null ? `${p.count}장` : null, p?.score != null ? `${p.score}점` : null, p?.tier || null]
      .filter(Boolean).join(" · ");
    return extras ? `${url} (${extras})` : url;
  }).join(" / ") + (pages.length > 5 ? ` 외 ${pages.length - 5}건` : "");
};

function detailRowsForFinding(metric: MetricTab, label: string, block?: AnalysisBlock): DetailRow[] {
  const f = block?.facts || {};
  if (!f || Object.keys(f).length === 0) return [];

  if (metric === "visual") {
    const d = f.image_diversity || {};
    const alt = f.alt_text_quality || {};
    const uniq = f.image_uniqueness || {};
    const conc = f.concentration || {};
    const story = f.storytelling || {};
    if (label === "이미지 분류") return [
      { key: "전체 이미지", value: `${countText(d.total_images)}장` },
      { key: "분류 결과", value: `product ${countText(d.product)} / lifestyle ${countText(d.lifestyle)} / 미분류 ${countText(d.unclassified)}` },
      { key: "Lifestyle 비율", value: pctText(d.lifestyle_ratio_pct) },
      { key: "판정 방식", value: d._note || "alt/src/파일명/페이지 URL/주변 텍스트 기반 휴리스틱" },
    ];
    if (label === "alt.copy 품질" || label === "alt 텍스트 품질") return [
      { key: "설명적", value: `${countText(alt["설명적"])}건` },
      { key: "일반적", value: `${countText(alt["일반적"])}건` },
      { key: "비어있음", value: `${countText(alt["비어있음"])}건` },
      { key: "설명적 비율", value: pctText(alt.descriptive_ratio_pct) },
      { key: "판정 방식", value: alt._note || "alt 길이와 제네릭 단어 여부 기준" },
    ];
    if (label === "이미지 고유성") return [
      { key: "고유 src 비율", value: pctText(uniq.unique_src_ratio_pct) },
      { key: "고유 alt 비율", value: pctText(uniq.unique_alt_ratio_pct) },
      { key: "판정 방식", value: uniq._note || "src/alt 중복도 기반 템플릿 재사용 추정" },
    ];
    if (label === "이미지 분포") return [
      { key: "페이지당 평균 이미지", value: `${countText(conc.avg_per_page)}장` },
      { key: "단일 페이지 최대 비중", value: pctText(conc.max_single_page_pct) },
      { key: "이미지 많은 페이지", value: pageListText(conc.image_heavy_pages) },
    ];
    if (label === "Visual tactic") return [
      { key: "Tactic 분포", value: mapToText((f.visual_tactics || {}).distribution) },
      { key: "역할별 이미지/단어", value: mapToText((f.visual_tactics || {}).role_summary) },
      { key: "판단 방식", value: (f.visual_tactics || {})._note || "페이지 역할, 이미지 수, heading/파일명 힌트 기반" },
    ];
    if (label === "스토리텔링") return [
      { key: "스토리텔링 페이지 수", value: `${countText(story.count)}건` },
      { key: "판정 기준", value: "product+lifestyle 이미지가 함께 있고 설명적 alt가 2개 이상인 페이지" },
      { key: "대표 페이지", value: urlListText(story.pages_with_storytelling) },
    ];
  }

  if (metric === "data") {
    const schema = f.schema || {};
    const html = f.html_structure || {};
    if (label === "Schema Coverage") return [
      { key: "적용률", value: pctText(schema.coverage_pct) },
      { key: "적용 페이지", value: `${countText(schema.pages_with_schema)} / ${countText(schema.total_pages)} 페이지` },
      { key: "Schema 타입 분포", value: mapToText(schema.schema_type_counts) },
    ];
    if (label === "Schema Completeness") return Object.entries(schema.completeness || {}).map(([typ, c]: [string, any]) => ({
      key: String(typ),
      value: `충족률 ${ratioText(c?.filled_ratio)}${Array.isArray(c?.missing_properties) && c.missing_properties.length ? ` / 누락 ${c.missing_properties.slice(0, 5).join(", ")}` : " / 누락 없음"}`,
    }));
    if (label === "@id 연결성") {
      const lk = schema.id_linkage || {};
      return [
        { key: "패턴", value: lk.linkage_pattern || "-" },
        { key: "연결 노드", value: `${countText(lk.linked_ids)} / ${countText(lk.total_id_nodes)}` },
        { key: "고립 노드", value: countText(lk.isolated_ids) },
        { key: "해석", value: "Linked/Inline은 우열이 아니라 스키마 아키텍처 특성으로 표시" },
      ];
    }
    if (label === "H-tag 구조") return [
      { key: "시맨틱 nav 페이지", value: `${countText(html.semantic_nav_pages)}건` },
      { key: "heading 이슈", value: pageListText(html.heading_issues) },
    ];
    if (label === "Meta description") return [
      { key: "Meta description 누락", value: urlListText(html.pages_missing_meta_description) },
      { key: "Title 누락", value: urlListText(html.pages_missing_title) },
    ];
  }

  if (metric === "copy") {
    const inventory = f.page_inventory || {};
    const density = f.content_density || {};
    const length = f.copy_length || {};
    const rich = f.copy_richness || {};
    const faq = f.faq || {};
    const commerce = f.commerce_cta || {};
    const dup = f.duplication || {};

    if (label === "수집 기준") return [
      { key: "총 수집 페이지", value: `${countText(inventory.total_pages ?? (rich.all_pages || []).length)}페이지` },
      { key: "역할별 수집", value: mapToText(inventory.by_page_role || length.by_page_role) },
      { key: "분량 구간", value: mapToText(density.distribution) },
      { key: "해석", value: inventory.note || density.note || "품질 등급이 아니라 이번 리포트가 어떤 페이지 역할을 근거로 삼았는지 보여주는 기준" },
    ];
    if (label === "COPY 현재 상태") return [
      { key: "카피 구체성 산식", value: `수치/스펙 근거 ${pctText((rich.weights?.quant ?? 0) * 100)} / H2·CTA·FAQ 구조 ${pctText((rich.weights?.structure ?? 0) * 100)} / 비교·증거 키워드 ${pctText((rich.weights?.evidence_kw ?? 0) * 100)} / FAQ 존재 ${pctText((rich.weights?.faq_presence ?? 0) * 100)}` },
      { key: "강한 페이지", value: pageListText(rich.rich_pages) },
      { key: "보강 후보", value: pageListText(rich.intent_gap_pages) },
      { key: "해석", value: "점수는 사이트 우열이 아니라 PDP·Buying·PF 역할별로 제품 이해/전환 근거가 충분한지 보는 보조 기준" },
    ];
    if (label === "점검 후보") return [
      { key: "짧은 텍스트 페이지", value: urlListText(density.thin_pages) },
      { key: "긴 페이지", value: urlListText(density.rich_pages) },
      { key: "해석", value: "Buying/옵션 페이지가 짧은 것은 정상일 수 있음. PF/PDP가 짧거나, 긴 PDP에 수치·스펙 근거가 적은 경우를 우선 확인" },
    ];
    if (label === "구매 CTA") return [
      { key: "CTA 수집 페이지", value: `${countText(commerce.pages_with_buy_cta)}페이지` },
      { key: "대표 CTA 페이지", value: pageListText(commerce.buy_cta_pages) },
      { key: "CTA 미확인 후보", value: pageListText(commerce.missing_buy_cta_pages) },
      { key: "판단 방식", value: commerce.note || "Buy/Shop/Add to cart/Where to buy 계열 버튼·링크 텍스트 기반" },
    ];
    if (label === "중복 점검") return [
      { key: "중복 CTA 페이지", value: pageListText(dup.duplicate_cta_pages) },
      { key: "중복 문구 페이지", value: pageListText(dup.duplicate_copy_pages) },
      { key: "해석", value: dup.note || "공통 헤더/푸터 반복일 수 있어 삭제 전 본문 반복인지 수동 확인 필요" },
    ];
    if (label === "FAQ") return [
      { key: "FAQ 보유 페이지", value: `${countText(faq.pages_with_faq)}건` },
      { key: "FAQ 문항 수", value: `${countText(faq.total_items)}건` },
      { key: "가중치", value: `구체성 ${pctText((faq.weights?.specificity ?? 0) * 100)} / 질문 현실성 ${pctText((faq.weights?.question_realism ?? 0) * 100)} / 인용 적합성 ${pctText((faq.weights?.citability ?? 0) * 100)}` },
      { key: "점검 필요 페이지", value: pageListText(faq.detail) },
    ];
  }

  return [
    { key: "집계 기준", value: "현재 수집된 페이지의 facts 값과 규칙기반 narrative를 그대로 표시" },
    { key: "원문", value: JSON.stringify(f).slice(0, 500) + (JSON.stringify(f).length > 500 ? "…" : "") },
  ];
}



type EvidenceLens = {
  risk: "high" | "medium" | "low";
  conclusion: string;
  action: string;
  evidenceLine: string;
};

const safeNumber = (v: any): number | undefined => {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const n = Number(v.replace(/[^0-9.-]/g, ""));
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
};

function currentStatusLens(
  metric: MetricTab,
  site: SiteKey,
  label: string,
  line: string,
  block: AnalysisBlock | undefined,
  rows: DetailRow[],
): EvidenceLens {
  const f = block?.facts || {};
  const imageDiversity = f.image_diversity || {};
  const totalImages = safeNumber(imageDiversity.total_images);
  const product = safeNumber(imageDiversity.product) ?? 0;
  const lifestyle = safeNumber(imageDiversity.lifestyle) ?? 0;
  const unclassified = safeNumber(imageDiversity.unclassified) ?? 0;
  const siteLabel = siteName(site);
  const metricLabel = METRICS[metric].label;

  if (metric === "visual" && label === "이미지 분류" && totalImages === 0) {
    return {
      risk: "high",
      conclusion: `${siteLabel}은 이미지/ALT COPY 근거가 없어 이번 리포트에서 Visual 경쟁력을 판단하지 않았습니다.`,
      action: "URL·지역/언어 리다이렉트·lazy-loaded 이미지·스크린샷 저장 여부를 확인하고, 근거가 확보되기 전까지는 경쟁사 비교에 넣지 마세요.",
      evidenceLine: `HTML 메타데이터 기준 이미지 ${totalImages}장, product ${product}장, lifestyle ${lifestyle}장, 미분류 ${unclassified}장입니다. 실제 이미지를 본 판정이 아니므로 원본 페이지도 함께 확인이 필요합니다.`,
    };
  }

  if (metric === "visual" && label === "이미지 분류") {
    const ratio = safeNumber(imageDiversity.lifestyle_ratio_pct);
    const ratioTextValue = ratio == null ? "확인 필요" : `${Math.round(ratio)}%`;
    return {
      risk: ratio == null ? "medium" : ratio >= 25 ? "low" : "medium",
      conclusion: `${siteLabel}의 Visual은 현재 ${totalImages ?? "-"}장 기준으로 lifestyle 비율 ${ratioTextValue}입니다. 픽셀 분석이 아니라 HTML 신호 기반이라 방향성 참고용입니다.`,
      action: "대표 PDP/PF에서 실제 스크린샷과 image src가 같이 잡혔는지 확인하고, product/lifestyle 분류가 맞는 샘플 3~5개를 수동 검증하세요.",
      evidenceLine: `product ${product}장 / lifestyle ${lifestyle}장 / 미분류 ${unclassified}장으로 분류되었습니다. alt, src, 파일명, 주변 텍스트 신호를 사용했습니다.`,
    };
  }

  if (metric === "visual") {
    return {
      risk: "medium",
      conclusion: `${siteLabel}의 ${label}은 실제 페이지와 자동 집계가 맞는지 먼저 확인이 필요한 항목입니다.`,
      action: "대표 페이지 1~2개를 열어 실제 이미지, ALT COPY, gallery 구성이 자동 집계와 맞는지 확인하세요. 불일치하면 이미지 추출 로직을 수정하세요.",
      evidenceLine: line,
    };
  }

  if (metric === "copy") {
    return {
      risk: "medium",
      conclusion: `${siteLabel}의 ${label}은 메시지·구매 전환에 영향을 줄 수 있는 항목입니다.`,
      action: "PF/PDP/Buying 역할별로 실제 페이지를 열어 카피 길이, CTA 위치, FAQ 품질이 자동 집계와 맞는지 확인하세요.",
      evidenceLine: line,
    };
  }

  return {
    risk: "medium",
    conclusion: `${siteLabel}의 ${metricLabel} / ${label}은 검색·AI 요약 노출에 영향을 줄 수 있는 구조 항목입니다.`,
    action: "Schema, H-tag, meta, page role이 실제 페이지 목적과 맞는지 확인하세요. PF/PDP/Buying 역할별로 Product, Breadcrumb, Offer 적용 여부를 점검하세요.",
    evidenceLine: line,
  };
}

const METRIC_WHY_MATTERS: Record<MetricTab, string> = {
  data: "구조 데이터는 존재 여부보다 페이지 역할에 맞는 적합성이 검색·AI 요약 노출에 더 크게 작용합니다.",
  copy: "탐색 이후 다음 행동으로 이어지는 연결이 약하면 페이지 방문이 구매로 이어지는 비율이 줄어들 수 있습니다.",
  visual: "이미지 양보다 설명 밀도 차이가 크면, 이미지가 전달하는 의미 범위가 제한될 수 있습니다.",
};

export function CurrentStatusDrilldown({
  metric, site, block, selection,
}: {
  metric: MetricTab; site: SiteKey; block?: AnalysisBlock; selection: CurrentFindingSelection;
}) {
  const rows = detailRowsForFinding(metric, selection.label, block);
  const lens = currentStatusLens(metric, site, selection.label, selection.line, block, rows);
  const breakdown = metricScoreBreakdown(metric, block);
  const tier = scoreTier(breakdown.total);
  const title = lens.conclusion.split(/(?<=[.다요])\s+/)[0] || lens.conclusion;

  return (
    <div className="currentEvidenceBox">
      <p className="currentEvidenceKicker">
        <span className={`badge ${site}`}>{siteName(site)}</span>
        <span className={`badge ${metric === "data" ? "c1" : metric === "copy" ? "c2" : "c4"}`}>{METRICS[metric].label}</span>
        <span className="badge c6">{selection.label}</span>
        <span className="detailScoreBadge">
          {scoreTierEmoji(tier)} {breakdown.total == null ? "-" : breakdown.total} {scoreTierLabel(tier)}
        </span>
      </p>

      {/* 제목 — 인사이트형 헤드라인 */}
      <p className="detailTitle">{title}</p>
      {/* 1줄 인사이트 */}
      <p className="findingText" style={{ fontSize: 13, color: "var(--label)", marginBottom: 10 }}>{lens.conclusion}</p>

      {/* 핵심 근거 — 점수 구성요소를 사람이 읽을 수 있는 표로 (원시 로그 아님) */}
      <p className="detailSectionLabel">핵심 근거</p>
      <div className="evidenceGrid" style={{ marginBottom: 10 }}>
        {breakdown.components.map((c) => (
          <>
            <span key={`${c.label}_k`} className="evidenceKey">{c.label}</span>
            <span key={`${c.label}_v`} className="evidenceVal">{c.value == null ? "근거 없음" : `${c.value}%`}</span>
          </>
        ))}
      </div>

      {/* 해석 */}
      <p className="detailSectionLabel">해석</p>
      <p className="findingText" style={{ fontSize: 12.5, marginBottom: 10 }}>{lens.evidenceLine}</p>

      {/* 왜 중요한가 */}
      <p className="detailSectionLabel">왜 중요한가</p>
      <p className="findingText" style={{ fontSize: 12.5, marginBottom: 10 }}>{METRIC_WHY_MATTERS[metric]}</p>

      {/* 추천 액션 */}
      <p className="findingText siteInsightAction" style={{ marginBottom: 12 }}>추천 액션: {lens.action}</p>

      <details className="siteScoreDetails">
        <summary>기술 상세 보기</summary>
        {rows.length > 0 ? (
          <div className="evidenceGrid" style={{ marginTop: 10 }}>
            {rows.map((r, i) => (
              <>
                <span key={`${i}_k`} className="evidenceKey">{r.key}</span>
                <span key={`${i}_v`} className="evidenceVal">{r.value}</span>
              </>
            ))}
          </div>
        ) : (
          <p className="muted">표시할 상세 facts가 없습니다.</p>
        )}
      </details>
    </div>
  );
}
