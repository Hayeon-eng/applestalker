// qubiShared.ts — 큐비 공용 타입·상수·헬퍼 (QubiApp.tsx / QubiSections.tsx 공유)

export type Finding = { status: "pass" | "warn" | "fail" | "na"; as_is?: string; to_be?: string; block?: string; token?: string; category?: string; kind?: string; region?: string; found?: string[]; expected?: string;
  types?: string[]; missing_props?: string[]; haspart_missing?: string[]; id_mismatch?: string;
  val_mismatch?: { prop: string; expected: string; actual: string }[];
  name_issue?: { prop: string; actual: string; missing: string[]; forbidden: string[] }[];
  translate_confirm?: { prop: string; actual: string; note?: string }[]; };
export type PageResult = { sitecode: string; url: string; region?: string; country?: string; page_type?: string;
  schema: { findings: Finding[] }; copy: { findings: Finding[] }; html_qa?: any; spec_v2?: any; compare_v2?: any };
export type SiteRow = { sitecode: string; country?: string; lang?: string; url: string; region?: string; product?: string; page_type?: string };
export type CatalogItem = { category: string; label: string; ex_value: string; ex_unit: string };
export type Product = { code: string; label: string; spec_only?: boolean };

export const SEV = { fail: { ko: "오류", c: "#D8362F" }, warn: { ko: "확인", c: "#E0A008" }, pass: { ko: "정상", c: "#1F9E5C" }, na: { ko: "해당없음", c: "#98A2B3" } } as const;
export const HONEY = "#E0A008";
export const PAGE_TYPES = ["PDP", "Compare"];
// 버즈는 Compare 페이지가 없음 → PDP만. 폰은 PDP·Compare. (Buying은 검사 제외라 노출 안 함)
export const pageTypesFor = (product: string) =>
  product.startsWith("galaxy-buds") ? ["PDP"] : PAGE_TYPES;
// 마케팅 제품 → 스키마 룰 패밀리(M3=폰 계열 / M12=버즈 계열)
export const family = (code: string) => (code || "").includes("buds") ? "M12" : "M3";

export const tierOf = (c: { fail: number; warn: number }) => (c.fail > 0 ? "bad" : c.warn > 0 ? "mid" : "good");
export const inputStyle = { fontSize: 12, padding: "6px 8px", border: "1px solid var(--line)", borderRadius: 6 } as const;
export const sel = (v: string, on: boolean) => ({ fontSize: 12, padding: "4px 10px", borderRadius: 999, cursor: "pointer", border: on ? "1px solid #0A66E0" : "1px solid var(--line)", background: on ? "#0A66E0" : "#fff", color: on ? "#fff" : "var(--label)" });

// 내부 계산 토큰을 사람이 읽는 말로 (QuickView·DATA QA 상세 등 findings 텍스트 공유)
export const TERM_MAP: Record<string, string> = {
  structure_valid: "FAQ 구조 유효성",
  screen_match: "화면 노출 일치",
  type_combo: "타입 선언(@type)",
  contentUrlOrEmbedUrl: "영상 URL",
  encoding_contentUrl: "3D 파일 URL",
  encoding_encodingFormat: "3D 포맷",
};
export function humanizeTerm(s: string): string {
  if (!s) return s;
  let out = s;
  for (const [k, v] of Object.entries(TERM_MAP)) out = out.split(k).join(v);
  return out;
}

// DATA QA 신호등 색/이모지 (공유)
export const TL_COLOR: Record<string, string> = { green: "#1F9E5C", yellow: "#E0A008", red: "#D8362F" };
export const TL_EMOJI: Record<string, string> = { green: "🟢", yellow: "🟡", red: "🔴" };

// ── 신호등 판정 (QA Bee 전체 공유) ──────────────────────────────
// Data QA(스키마): 점수 기준 — 80%↑ green / 50–79% yellow / 그 미만 red.
// Spec QA(스펙): 엄격 기준 — Critical(오류) 1건이라도 있으면 무조건 red,
//   오류 0 + Warning(확인) 있으면 yellow, 둘 다 0이면 green.
// 색·이모지는 위 TL_COLOR/TL_EMOJI를 공유하므로 두 QA의 신호등이 시각적으로 완전히 동일하다.
export function tlByScore(pct: number | null | undefined, danger = false): "green" | "yellow" | "red" {
  if (danger) return "red";
  const v = pct ?? 0;
  return v < 50 ? "red" : v < 80 ? "yellow" : "green";
}
export function tlSpec(critical: number, warning: number): "green" | "yellow" | "red" {
  if (critical > 0) return "red";      // 스펙 오류 1건이라도 → 빨강
  if (warning > 0) return "yellow";    // 오류 0, 확인만 있음 → 노랑
  return "green";
}
