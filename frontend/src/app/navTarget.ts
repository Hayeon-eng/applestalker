/* navTarget.ts — [2026-11 E1] 권역 OVERVIEW 등에서 "이 문제를 해당 앱·화면에서 바로 열기" 위한 이동 대상.
   백엔드 insight_rules._site_issues 의 go 필드와 같은 모양. */
export type NavTarget = {
  app: "qubi" | "honeycomb" | "applestalker";
  tab?: "schema" | "copy" | "static";   // qaBee 탭
  run_id?: string | null;                // 열 검수 결과(이력) / honeyComb 주차
  region?: string | null;                // qaBee 결과에서 스크롤할 권역
  sitecode?: string | null;              // 강조·선택할 사이트
  page?: string | null;                  // 공통페이지 QA 페이지 키
  country?: string | null;               // honeyComb 국가 코드
  product?: string | null;               // honeyComb 제품 slug
  n?: number;                            // 같은 대상을 다시 눌러도 동작하도록 증가값
};
