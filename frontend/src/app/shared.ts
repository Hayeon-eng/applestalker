/* ════════════════════════════════════════════════════
   shared.ts — 배럴(re-export). 구현은 sharedCore.ts(타입·상수·URL/라벨 유틸)와
   sharedScoring.ts(점수·티어·액션·원라이너)로 분리됨.
   기존 `import { ... } from "./shared"` 는 그대로 동작합니다.
════════════════════════════════════════════════════ */
export * from "./sharedCore";
export * from "./sharedScoring";
