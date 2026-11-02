/* toolTheme.ts — [2026-11] ABC 툴 시각 구분(아이콘·색) 단일 정의.
   권역 OVERVIEW(Summary·급한 이슈·사이트 표·지도), 앱 타이틀이 같은 규칙을 쓴다. */
export type ToolLetter = "A" | "B" | "C";
export const TOOL_THEME: Record<ToolLetter, { icon: string; name: string; color: string; soft: string; ink: string }> = {
  A: { icon: "🍎", name: "appleStalker", color: "#E5484D", soft: "#FDECEC", ink: "#B42318" },
  B: { icon: "🐝", name: "qaBee", color: "#7C3AED", soft: "#F1EAFE", ink: "#5B21B6" },
  C: { icon: "🍯", name: "honeyComb", color: "#E8A317", soft: "#FFF4D6", ink: "#8A5A00" },
};
/** 이슈의 tool 키(apple·data·spec·static·hc) → 툴 문자 */
export const letterOf = (tool?: string): ToolLetter => (tool === "apple" ? "A" : tool === "hc" ? "C" : "B");
/** qaBee 안의 세부 검수 이름 */
export const SUBTOOL: Record<string, string> = { apple: "경쟁사 변경", data: "DATA QA", spec: "스펙 QA", static: "공통페이지 QA", hc: "Google Shopping 노출" };

/** [2026-11] 상태색은 브랜드색과 분리한다 — 브랜드색(appleStalker=빨강 등)이 '이 툴은 지금 위험'으로 오해되지 않도록.
    sev: 1=지금 고쳐야 함(빨강) · 2=확인 필요(노랑) · 0=정상(초록) · 그 외(데이터 없음)=회색 */
export const SEV_THEME: Record<number, { color: string; soft: string; ink: string }> = {
  1: { color: "#D8362F", soft: "#FDECEC", ink: "#B42318" },
  2: { color: "#E0A008", soft: "#FFF4D6", ink: "#8A5A00" },
  0: { color: "#2F9E5B", soft: "#E8F7EE", ink: "#15803D" },
};
export const sevTheme = (sev?: number) => (sev == null ? { color: "#C8CCD2", soft: "#F3F4F6", ink: "#8A94A6" } : SEV_THEME[sev]);
