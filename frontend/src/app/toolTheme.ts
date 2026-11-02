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
