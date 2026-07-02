"use client";

import { Change, AnalysisBlock, MetricTab, SiteKey, METRICS, siteName, shortUrl } from "./shared";

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
  return (
    <div className="drilldown">
      <h3>상세 근거</h3>
      <p>
        <b>페이지:</b>{" "}
        <a href={c.url} target="_blank" rel="noreferrer">{c.url}</a>
      </p>
      <p><b>분류:</b> {c.category || "-"} / {c.field || "-"}</p>

      {/* 정확히 무엇이 바뀌었는지 — 추가/삭제된 문장을 색으로 바로 보이게 (가장 중요한 정보라 최상단에 배치) */}
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
      {ev.kind && EVIDENCE_KIND_LABELS[ev.kind as string] && (
        <p style={{ marginTop: 8, fontSize: 12.5, fontWeight: 600 }}>
          {EVIDENCE_KIND_LABELS[ev.kind as string]}{ev.type ? ` — ${ev.type}` : ""}
        </p>
      )}
      {countDeltas && (
        <div style={{ marginTop: 8 }}>
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
      {Object.keys(ev).length > 0 && (
        <div className="evidenceGrid" style={{ marginTop: 8 }}>
          {Object.entries(ev)
            .filter(([k]) => k !== "count_deltas" && k !== "sentences_added" && k !== "sentences_removed"
                           && !(hasKindLabel && (k === "kind" || k === "type")))
            .map(([k, v]) => (
              <>
                <span key={k + "_k"} className="evidenceKey">{EVIDENCE_LABELS[k] || k}</span>
                <span key={k + "_v"} className="evidenceVal">{evidenceValueToText(v, k)}</span>
              </>
            ))}
        </div>
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
  return entries.map(([k, v]) => `${k} ${countText(v)}`).join(" / ");
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
    if (label === "alt 텍스트 품질") return [
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
    const density = f.content_density || {};
    const rich = f.copy_richness || {};
    const faq = f.faq || {};
    if (label === "콘텐츠 양" || label === "텍스트 부족") return [
      { key: "콘텐츠 밀도 분포", value: mapToText(density.distribution) },
      { key: "텍스트 부족 페이지", value: urlListText(density.thin_pages) },
      { key: "풍부 콘텐츠 페이지", value: urlListText(density.rich_pages) },
    ];
    if (label === "카피 구체성") return [
      { key: "가중치", value: `구체 근거 ${pctText((rich.weights?.quant ?? 0) * 100)} / 구조 ${pctText((rich.weights?.structure ?? 0) * 100)} / 근거 키워드 ${pctText((rich.weights?.evidence_kw ?? 0) * 100)} / FAQ ${pctText((rich.weights?.faq_presence ?? 0) * 100)}` },
      { key: "우수 페이지", value: pageListText(rich.rich_pages) },
      { key: "미흡 페이지", value: pageListText(rich.intent_gap_pages) },
    ];
    if (label === "FAQ 품질") return [
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

export function CurrentStatusDrilldown({
  metric, site, block, selection,
}: {
  metric: MetricTab; site: SiteKey; block?: AnalysisBlock; selection: CurrentFindingSelection;
}) {
  const rows = detailRowsForFinding(metric, selection.label, block);
  return (
    <div className="currentEvidenceBox">
      <p className="currentEvidenceKicker">
        <span className={`badge ${site}`}>{siteName(site)}</span>
        <span className={`badge ${metric === "data" ? "c1" : metric === "copy" ? "c2" : "c4"}`}>{METRICS[metric].label}</span>
        <span className="badge c6">{selection.label}</span>
      </p>
      <div className="diffBlock">
        <p className="diffLabel">요약 문장</p>
        <p className="diffContent after">{selection.line}</p>
      </div>
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
      <p className="termDetail" style={{ marginTop: 10 }}>
        변경점이 없어도 현재 상태 집계에 사용된 facts를 보여주는 영역입니다. Gemini 실패 시에도 규칙기반 집계값을 근거로 표시합니다.
      </p>
    </div>
  );
}
