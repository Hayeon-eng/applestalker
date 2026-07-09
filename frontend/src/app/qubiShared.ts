// qubiShared.ts — 큐비 공용 타입·상수·헬퍼 (QubiApp.tsx / QubiSections.tsx 공유)

export type Finding = { status: "pass" | "warn" | "fail" | "na"; as_is?: string; to_be?: string; block?: string; token?: string; category?: string; kind?: string; region?: string; found?: string[]; expected?: string;
  types?: string[]; missing_props?: string[]; haspart_missing?: string[]; id_mismatch?: string;
  val_mismatch?: { prop: string; expected: string; actual: string }[];
  name_issue?: { prop: string; actual: string; missing: string[]; forbidden: string[] }[]; };
export type PageResult = { sitecode: string; url: string; region?: string; country?: string; page_type?: string;
  schema: { findings: Finding[] }; copy: { findings: Finding[] }; html_qa?: any };
export type SiteRow = { sitecode: string; country?: string; lang?: string; url: string; region?: string };
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
