"use client";
import { useState, useEffect, useCallback, useRef } from "react";

export const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export interface Change {
  id: number;
  url: string;
  site: string;
  level: "High" | "Medium" | "Low";
  category: string;
  field: string;
  summary: string;
  before?: string;
  after?: string;
  evidence?: Record<string, any>;
}
export interface Report {
  has_data: boolean;
  run_id?: string;
  site?: string;
  timestamp?: string;
  has_changes?: boolean;
  by_category?: Record<string, number>;
  changes?: Change[];
  category_summary?: Record<string, string>;
  analysis?: { summary: string; aeo_implications: string; insights: any[]; actions: any[] };
  dcv?: { data: Record<string, any>; copy: Record<string, any>; visual: Record<string, any> };
}
export interface Session {
  session: string;
  run_ids: string[];
  sites: string[];
  pages: number;
  changes: number;
  timestamp: string;
}
export interface PageLite {
  url: string;
  title: string;
  word_count: number;
}
export interface PageDetail {
  url: string;
  crawled_at: string;
  data: { facts: any; narrative: string[] };
  copy: { facts: any; narrative: string[] };
  visual: { facts: any; narrative: string[] };
}

/* 변경점(diff) 탭의 4 카테고리를 DATA/COPY/VISUAL 3버킷으로 매핑 (요구사항 1.5 — 중복 귀속 금지) */
export const BUCKET_OF: Record<string, "data" | "copy" | "visual"> = {
  "데이터·스키마": "data",
  카피: "copy",
  "가격·프로모션": "copy",
  비주얼: "visual",
};
export const CATS = [
  {
    key: "데이터·스키마",
    icon: "🔍",
    bucket: "data",
    tip: "웹페이지의 구조·코드(스키마/HTML)·메뉴 변화. 검색·AI 노출에 영향을 줍니다.",
  },
  {
    key: "카피",
    icon: "✍️",
    bucket: "copy",
    tip: "제목·본문·문구·FAQ 등 글로 쓰인 내용의 변화입니다.",
  },
  {
    key: "가격·프로모션",
    icon: "💰",
    bucket: "copy",
    tip: "가격·구매 버튼·사전예약·보상판매(Trade-in) 등 거래 관련 변화입니다.",
  },
  {
    key: "비주얼",
    icon: "🖼️",
    bucket: "visual",
    tip: "메인 이미지·배너 등 시각 요소의 변화입니다.",
  },
];
export const DTABS: { key: "data" | "copy" | "visual"; label: string; icon: string }[] = [
  { key: "data", label: "DATA", icon: "🔍" },
  { key: "copy", label: "COPY", icon: "✍️" },
  { key: "visual", label: "VISUAL", icon: "🖼️" },
];
export const LV: Record<string, string> = { High: "var(--high)", Medium: "var(--med)", Low: "var(--low)" };
export const LV_KO: Record<string, string> = { High: "높음", Medium: "보통", Low: "낮음" };

/* 사이드 'Example'에서만 보여줄 예시 (실제 사이트 관찰 기반) */
export const PREV = "(예시용 가상)";
export const _changes: Change[] = [
  {
    id: 1,
    url: "https://www.apple.com/apple-intelligence/",
    site: "apple",
    level: "Medium",
    category: "카피",
    field: "대표 제목",
    summary: '대표 제목이 "차세대 Apple Intelligence·Siri"로 바뀜',
    before: PREV,
    after: "Introducing the next generation of Apple Intelligence and Siri",
    evidence: { "바뀐 문장": "1개" },
  },
  {
    id: 2,
    url: "https://www.apple.com/apple-intelligence/",
    site: "apple",
    level: "Medium",
    category: "데이터·스키마",
    field: "메뉴/기능",
    summary: '새 기능 안내 추가 — Safari에 "가격·재입고가 바뀌면 알려주는 기능"',
    before: PREV,
    after: "Safari로 가격·재입고 변경 알림",
    evidence: { "변화 유형": "새 항목 추가" },
  },
  {
    id: 6,
    url: "https://www.apple.com/iphone/",
    site: "apple",
    level: "High",
    category: "데이터·스키마",
    field: "구조화 데이터",
    summary: "신제품 라인업(iPhone 17 Pro/Air/17/17e)이 페이지 구조에 반영됨",
    before: PREV,
    after: "Product 스키마 4종(iPhone 17 Pro / Air / 17 / 17e)",
    evidence: { "변화 유형": "항목 증가" },
  },
  {
    id: 4,
    url: "https://www.samsung.com/sg/galaxy-ai/",
    site: "samsung",
    level: "Medium",
    category: "카피",
    field: "대표 제목",
    summary: "대표 제목(슬로건) 변경",
    before: PREV,
    after: "Galaxy AI, a true AI companion",
    evidence: { "바뀐 문장": "1개" },
  },
  {
    id: 3,
    url: "https://www.samsung.com/sg/galaxy-ai/",
    site: "samsung",
    level: "Medium",
    category: "가격·프로모션",
    field: "안내 문구",
    summary: '"Galaxy AI 2025년 말까지 무료" 프로모션 문구 노출',
    before: PREV,
    after: "Galaxy AI features free until the end of 2025",
    evidence: { "감지된 키워드": "무료 / 2025" },
  },
  {
    id: 5,
    url: "https://www.samsung.com/sg/",
    site: "samsung",
    level: "Low",
    category: "비주얼",
    field: "메인 이미지",
    summary: "메인 화면 이미지가 바뀐 것으로 감지됨",
    before: PREV,
    after: "(새 이미지)",
    evidence: { "이미지 차이": "14 / 64" },
  },
];
export const _now = () => new Date().toISOString().slice(0, 16).replace("T", " ");

/* ① 변화 있음 예시 → '변경점' 탭에서 사용 */
export const CHANGES_EXAMPLE: Report = {
  has_data: true,
  run_id: "ex",
  site: "samsung",
  timestamp: _now(),
  has_changes: true,
  by_category: { "데이터·스키마": 2, 카피: 2, "가격·프로모션": 1, 비주얼: 1 },
  changes: _changes,
  category_summary: {
    "데이터·스키마":
      "당사는 FAQ·제품 스키마가 일부 페이지에만 있고, 애플은 제품 스키마를 4종으로 확장 — 애플이 AI 검색 노출 기반을 더 촘촘히 가져가는 중",
    카피: '당사는 "Galaxy AI, a true AI companion"으로 동반자 컨셉, 애플은 "차세대 Siri"를 전면화 — 양사가 AI 주도권 메시지로 정면 경쟁',
    "가격·프로모션":
      '당사는 "Galaxy AI 2025년 말까지 무료"·Trade-in을 노출, 애플은 가격 노출 없음 — 당사가 가격·혜택 소구가 더 적극적',
    비주얼: "당사는 메인 히어로 이미지를 교체, 애플은 변동 없음 — 당사 비주얼 리프레시 주기가 빠름",
  },
  analysis: {
    summary: "",
    aeo_implications:
      '※ 예시 화면입니다. "이전" 값은 과거 시점을 알 수 없어 가상으로 표시했고, "현재" 값만 실제 사이트에서 관찰한 문구입니다.',
    insights: [],
    actions: [],
  },
};

/* ② 변화 없음(= 현행 분석) 예시 → '현황 비교' 탭에서 사용 */
export const COMPARE_EXAMPLE: any = {
  status: "ok",
  _example: true,
  overall:
    "직전 크롤 대비 새로 감지된 변화는 없습니다. 그래서 변화 알림 대신 양사의 현재 상태를 DATA/COPY/VISUAL 영역별로 비교했습니다. (예시 화면이며, 현재 값은 실제 관찰 기반입니다)",
  data: {
    comparison: [
      { dimension: "Schema Coverage", samsung: "62%", apple: "88%", gap: "당사 격차" },
      {
        dimension: "Schema 연결 패턴",
        samsung: "Inline(개별 페이지 임베딩형)",
        apple: "Linked(@id 기반 연결형)",
        gap: "구조적 격차",
      },
      { dimension: "meta description 누락", samsung: "2+", apple: "0", gap: "당사 보강 필요" },
    ],
  },
  copy: {
    comparison: [
      {
        dimension: "빈약 콘텐츠 페이지(150단어 미만)",
        samsung: "3+",
        apple: "1+",
        gap: "당사 격차",
      },
      { dimension: "FAQ 보유 페이지", samsung: "4", apple: "9", gap: "당사 격차" },
      { dimension: "intent 미충족 페이지", samsung: "5+", apple: "2+", gap: "당사 격차" },
    ],
  },
  visual: {
    comparison: [
      { dimension: "Lifestyle 이미지 비율", samsung: "18%", apple: "41%", gap: "당사 격차" },
      {
        dimension: "이미지 편중도(최대 페이지 비중)",
        samsung: "52%",
        apple: "24%",
        gap: "당사 편중 높음",
      },
      { dimension: "스토리텔링 페이지", samsung: "2", apple: "6", gap: "당사 격차" },
    ],
  },
};



/* ── 변경점 본문: 좌(경쟁사 애플) / 우(당사 삼성) 2칼럼, DATA/COPY/VISUAL 필터 적용됨 ── */
export function Changes({
  data,
  changes,
  byCat,
  appleN,
  samsungN,
  highN,
  sel,
  setSel,
  isExample,
  dataTab,
}: any) {
  const a = data.analysis;
  const visibleCats = CATS.filter((c: any) => c.bucket === dataTab);
  const total = changes.length;
  const col = (site: "apple" | "samsung") =>
    visibleCats.map((cat: any) => ({
      cat,
      items: changes.filter((c: Change) => c.site === site && c.category === cat.key),
    }));
  return (
    <div id="capture-area" style={{ padding: "18px 24px 60px" }}>
      {isExample && (
        <div
          style={{
            background: "#FFF8E6",
            border: "1px solid #FFE5A3",
            borderRadius: 12,
            padding: "10px 14px",
            fontSize: 12,
            color: "#8A6D00",
            marginBottom: 14,
          }}
        >
          🔍 <b>예시 화면</b>입니다. 실제 데이터가 아니며, 크롤을 실행하면 진짜 변화로 채워집니다.
        </div>
      )}

      <div
        style={{
          background: "#fff",
          borderRadius: 18,
          padding: "18px 20px",
          boxShadow: "var(--shadow)",
        }}
      >
        <div style={{ display: "flex", gap: 14, alignItems: "center", marginBottom: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 700 }}>
            오늘의 핵심 · {dataTab.toUpperCase()}
          </span>
          <span style={{ fontSize: 11.5, color: "var(--sec)" }}>{data.timestamp}</span>
          <span style={{ flex: 1 }} />
          <Stat n={total} label="이 영역 변화" />
          <Stat n={highN} label="전체 높음" color="var(--high)" />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 7, marginTop: 2 }}>
          {visibleCats.map((cat: any) => {
            const line = (data.category_summary || {})[cat.key] || "변동 없음";
            const none = line === "변동 없음";
            return (
              <div key={cat.key} style={{ display: "flex", gap: 9, alignItems: "flex-start" }}>
                <span style={{ fontSize: 14, flex: "0 0 auto", width: 20, textAlign: "center" }}>
                  {cat.icon}
                </span>
                <span
                  style={{ fontSize: 12, color: "var(--sec)", flex: "0 0 88px", fontWeight: 600 }}
                >
                  {cat.key}
                </span>
                <span
                  style={{
                    fontSize: 12.5,
                    color: none ? "var(--ter)" : "var(--label2)",
                    lineHeight: 1.5,
                  }}
                >
                  {line}
                </span>
              </div>
            );
          })}
        </div>
        {a?.aeo_implications && (
          <div style={{ fontSize: 11.5, color: "var(--ter)", marginTop: 10 }}>
            {a.aeo_implications}
          </div>
        )}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 14,
          marginTop: 14,
          alignItems: "start",
        }}
      >
        <SiteColumn
          site="apple"
          title="경쟁사 · Apple"
          count={appleN}
          cols={col("apple")}
          sel={sel}
          setSel={setSel}
        />
        <SiteColumn
          site="samsung"
          title="당사 · Samsung"
          count={samsungN}
          cols={col("samsung")}
          sel={sel}
          setSel={setSel}
        />
      </div>

      {/* [PHASE3] 요구사항 4: 변화 없음이어도 이 세션(run_id) 자체의 DATA/COPY/VISUAL 분석 노출.
          /api/compare는 항상 '오늘 최신' 비교라서 과거 히스토리를 클릭해도 그 시점 데이터가 아님 —
          그래서 latest-report(run_id)가 들고 있는 dcv를 그대로 써서 정확히 그 시점 분석을 보여준다. */}
      {total === 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 12, color: "var(--sec)", fontWeight: 600, marginBottom: 8 }}>
            이 영역 변화 없음 — {dataTab.toUpperCase()} 현행 분석 (이 크롤 시점 기준)
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {(["apple", "samsung"] as const).map((site) => {
              const block = (data.dcv?.[dataTab] || {})[site];
              const lines: string[] =
                block?.narrative ||
                (block?.insights || []).map((i: any) => i.point).filter(Boolean);
              return (
                <div
                  key={site}
                  style={{
                    background: "#fff",
                    borderRadius: 16,
                    padding: "14px 16px",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 9 }}>
                    <span
                      style={{
                        width: 9,
                        height: 9,
                        borderRadius: 3,
                        background: site === "apple" ? "var(--apple)" : "var(--samsung)",
                      }}
                    />
                    <span style={{ fontWeight: 700, fontSize: 13 }}>
                      {site === "apple" ? "Apple" : "Samsung"}
                    </span>
                  </div>
                  {!lines || lines.length === 0 ? (
                    <div style={{ fontSize: 11.5, color: "var(--ter)" }}>
                      이 크롤에서 수집된 분석 데이터가 없습니다
                    </div>
                  ) : (
                    lines.map((line: string, i: number) => (
                      <div
                        key={i}
                        style={{
                          fontSize: 12,
                          color: "var(--label2)",
                          lineHeight: 1.6,
                          padding: "5px 0",
                          borderTop: i ? "1px solid var(--line)" : "none",
                        }}
                      >
                        {line}
                      </div>
                    ))
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export function SiteColumn({ site, title, count, cols, sel, setSel }: any) {
  const accent = site === "apple" ? "var(--apple)" : "var(--samsung)";
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 4px 12px" }}>
        <span style={{ width: 10, height: 10, borderRadius: 3, background: accent }} />
        <span style={{ fontWeight: 700, fontSize: 14 }}>{title}</span>
        <span style={{ fontSize: 12, color: "var(--sec)" }}>· 변화 {count}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {cols.length === 0 && (
          <div style={{ fontSize: 11.5, color: "var(--ter)", padding: "8px 4px" }}>
            이 영역에 해당하는 카테고리가 없습니다
          </div>
        )}
        {cols.map(({ cat, items }: any) => (
          <div
            key={cat.key}
            style={{
              background: "#fff",
              borderRadius: 16,
              padding: "14px 16px",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: items.length ? 10 : 0,
              }}
            >
              <span
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: 8,
                  background: "var(--bg)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 13,
                }}
              >
                {cat.icon}
              </span>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{cat.key}</span>
              <Info tip={cat.tip} />
              <span style={{ flex: 1 }} />
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: items.length ? "var(--label)" : "var(--ter)",
                }}
              >
                {items.length}
              </span>
            </div>
            {items.length === 0 ? (
              <div style={{ fontSize: 11.5, color: "var(--ter)" }}>
                변화 없음 — 클릭할 항목이 없습니다. '현황 비교' 탭에서 현재 상태를 확인하세요.
              </div>
            ) : (
              items.map((c: Change) => (
                <div
                  key={c.id}
                  onClick={() => setSel(c)}
                  style={{
                    padding: "9px 16px",
                    marginLeft: -16,
                    marginRight: -16,
                    borderTop: "1px solid var(--line)",
                    cursor: "pointer",
                    borderRadius: sel?.id === c.id ? 9 : 0,
                    background: sel?.id === c.id ? "var(--blue-soft)" : "transparent",
                  }}
                >
                  <div style={{ marginBottom: 4 }}>
                    <Badge color={LV[c.level]}>{LV_KO[c.level]}</Badge>
                  </div>
                  <div style={{ fontSize: 12.5, lineHeight: 1.5 }}>{c.summary}</div>
                </div>
              ))
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── 우측 상세: 변경사항 클릭 ── */
export function Detail({ c }: { c: Change }) {
  return (
    <>
      <Card>
        <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
          <Badge color={LV[c.level]}>{LV_KO[c.level]}</Badge>
          <Badge color={c.site === "apple" ? "var(--apple)" : "var(--samsung)"}>
            {c.site === "apple" ? "Apple" : "Samsung"}
          </Badge>
          <span style={{ fontSize: 11, color: "var(--sec)", alignSelf: "center" }}>
            {c.category} · {c.field}
          </span>
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, lineHeight: 1.45 }}>{c.summary}</div>
        <a
          href={c.url}
          target="_blank"
          rel="noreferrer"
          className="mono"
          style={{
            fontSize: 11,
            color: "var(--blue)",
            marginTop: 9,
            display: "block",
            wordBreak: "break-all",
          }}
        >
          {c.url} ↗
        </a>
      </Card>
      {c.field !== "메인 이미지" &&
        (() => {
          const d = diffParts(c.before || "", c.after || "");
          return (
            <Card>
              <div style={{ fontSize: 12, color: "var(--sec)", marginBottom: 9 }}>
                실제 바뀐 내용 (원문 그대로)
              </div>
              <div style={{ fontSize: 12, color: "var(--sec)", marginBottom: 4 }}>이전</div>
              <div
                className="mono"
                style={{
                  fontSize: 12,
                  background: "#F7F7F8",
                  borderRadius: 10,
                  padding: "9px 11px",
                  color: "var(--sec)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {c.before ? (
                  <>
                    {d.delPre}
                    <mark style={{ background: "#FFD9D4", color: "#8a1c12", borderRadius: 3 }}>
                      {d.delMid}
                    </mark>
                    {d.delPost}
                  </>
                ) : (
                  "(없음)"
                )}
              </div>
              <div style={{ fontSize: 12, color: "var(--blue)", margin: "10px 0 4px" }}>현재</div>
              <div
                className="mono"
                style={{
                  fontSize: 12,
                  background: "var(--blue-soft)",
                  borderRadius: 10,
                  padding: "9px 11px",
                  color: "var(--label)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {c.after ? (
                  <>
                    {d.addPre}
                    <mark style={{ background: "#B7E8C5", color: "#13642b", borderRadius: 3 }}>
                      {d.addMid}
                    </mark>
                    {d.addPost}
                  </>
                ) : (
                  "(삭제됨)"
                )}
              </div>
            </Card>
          );
        })()}
      {c.field === "메인 이미지" && (
        <Card>
          <div style={{ fontSize: 12, color: "var(--sec)", marginBottom: 9 }}>이미지 변화</div>
          <div style={{ fontSize: 12.5, color: "var(--label2)" }}>
            메인 화면 이미지가 바뀐 것으로 감지되었습니다. 실제 운영 시에는 이전/현재 이미지가
            나란히 표시됩니다.
          </div>
        </Card>
      )}
      {c.evidence && Object.keys(c.evidence).length > 0 && (
        <Card>
          <div style={{ fontSize: 12, color: "var(--sec)", marginBottom: 9 }}>감지 근거</div>
          {Object.entries(c.evidence).map(([k, v]) => (
            <div
              key={k}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "6px 0",
                borderBottom: "1px solid var(--line)",
                fontSize: 12,
              }}
            >
              <span style={{ color: "var(--sec)" }}>{k}</span>
              <span className="mono">{String(v)}</span>
            </div>
          ))}
        </Card>
      )}
    </>
  );
}

/* ── 우측 상세: 페이지(현행 분석) 클릭 — 요구사항 1 핵심 ── */
export function PageDetailPanel({ d }: { d: PageDetail }) {
  const sections = [
    { key: "data", label: "DATA", icon: "🔍", block: d.data },
    { key: "copy", label: "COPY", icon: "✍️", block: d.copy },
    { key: "visual", label: "VISUAL", icon: "🖼️", block: d.visual },
  ];
  return (
    <>
      <Card>
        <div style={{ fontSize: 11, color: "var(--sec)", marginBottom: 4 }}>페이지 상세 분석</div>
        <a
          href={d.url}
          target="_blank"
          rel="noreferrer"
          className="mono"
          style={{ fontSize: 11.5, color: "var(--blue)", wordBreak: "break-all", display: "block" }}
        >
          {d.url} ↗
        </a>
        <div style={{ fontSize: 10.5, color: "var(--ter)", marginTop: 6 }}>
          크롤 시각: {d.crawled_at}
        </div>
      </Card>
      {sections.map((s) => (
        <Card key={s.key}>
          <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 9 }}>
            {s.icon} {s.label}
          </div>
          {(s.block?.narrative || []).length === 0 ? (
            <div style={{ fontSize: 11.5, color: "var(--ter)" }}>근거 데이터 없음</div>
          ) : (
            s.block.narrative.map((line: string, i: number) => (
              <div
                key={i}
                style={{
                  fontSize: 12,
                  color: "var(--label2)",
                  lineHeight: 1.6,
                  padding: "5px 0",
                  borderTop: i ? "1px solid var(--line)" : "none",
                }}
              >
                {line}
              </div>
            ))
          )}
        </Card>
      ))}
    </>
  );
}

export function diffParts(a: string, b: string) {
  const A = [...a],
    B = [...b];
  let i = 0;
  while (i < A.length && i < B.length && A[i] === B[i]) i++;
  let ea = A.length - 1,
    eb = B.length - 1;
  while (ea >= i && eb >= i && A[ea] === B[eb]) {
    ea--;
    eb--;
  }
  return {
    delPre: A.slice(0, i).join(""),
    delMid: A.slice(i, ea + 1).join(""),
    delPost: A.slice(ea + 1).join(""),
    addPre: B.slice(0, i).join(""),
    addMid: B.slice(i, eb + 1).join(""),
    addPost: B.slice(eb + 1).join(""),
  };
}
export function DetailDefault({ data, online, tab }: any) {
  if (!online)
    return (
      <Card>
        <div style={{ fontSize: 13.5, fontWeight: 700 }}>연결 대기 중</div>
        <div style={{ fontSize: 12.5, color: "var(--sec)", marginTop: 7 }}>
          백엔드에 연결되면 여기에 상세가 표시됩니다.
        </div>
      </Card>
    );
  if (tab === "compare")
    return (
      <Card>
        <div style={{ fontSize: 13.5, fontWeight: 700 }}>페이지를 선택하세요</div>
        <div style={{ fontSize: 12.5, color: "var(--sec)", marginTop: 7 }}>
          중앙 화면 하단의 페이지 목록에서 항목을 누르면 그 페이지의 DATA/COPY/VISUAL 상세 근거가
          표시됩니다.
        </div>
      </Card>
    );
  return (
    <Card>
      <div style={{ fontSize: 13.5, fontWeight: 700 }}>변화를 선택하세요</div>
      <div style={{ fontSize: 12.5, color: "var(--sec)", marginTop: 7 }}>
        왼쪽 카드에서 항목을 누르면 무엇이 어떻게 바뀌었는지 보여드립니다.
      </div>
    </Card>
  );
}

/* ── 현황 비교: DATA/COPY/VISUAL 선택된 영역의 비교 카드 + 페이지 브라우저 ── */
export function Compare({ data, online, isExample, dataTab, pagesBySite, onPickPage, selPageUrl }: any) {
  if (!isExample && !online)
    return (
      <Empty
        title="백엔드에 연결되지 않았습니다"
        desc="비교 데이터를 불러오려면 백엔드 연결이 필요합니다."
      />
    );
  if (!data) return <Empty title="불러오는 중…" desc="" />;
  if (!isExample && data.status === "insufficient_data")
    return (
      <Empty
        title="비교할 데이터가 부족합니다"
        desc="삼성·애플 두 사이트 모두 1회 이상 크롤이 완료되어야 비교가 가능합니다. (지어낸 숫자 없이 실제 수집값만 비교합니다)"
      />
    );
  const block = data[dataTab] || {};
  const rows = block.comparison || [];
  return (
    <div id="capture-area" style={{ padding: "18px 24px 60px" }}>
      {isExample && (
        <div
          style={{
            background: "#FFF8E6",
            border: "1px solid #FFE5A3",
            borderRadius: 12,
            padding: "10px 14px",
            fontSize: 12,
            color: "#8A6D00",
            marginBottom: 14,
          }}
        >
          🔍 <b>예시 화면</b>입니다. 변화가 없을 때는 이렇게 양사의 <b>현행 상태</b>를
          DATA/COPY/VISUAL 영역별로 비교 분석해 보여줍니다.
        </div>
      )}
      {data.overall && (
        <div
          style={{
            background: "#fff",
            borderRadius: 16,
            padding: "15px 17px",
            boxShadow: "var(--shadow-sm)",
            marginBottom: 14,
            fontSize: 13,
            lineHeight: 1.6,
            color: "var(--label2)",
          }}
        >
          {data.overall}
        </div>
      )}

      <div style={{ fontSize: 12, color: "var(--sec)", fontWeight: 600, marginBottom: 8 }}>
        {dataTab.toUpperCase()} 영역 비교
      </div>
      {rows.length === 0 && (
        <div style={{ fontSize: 12, color: "var(--ter)", marginBottom: 14 }}>
          이 영역의 비교 데이터가 없습니다.
        </div>
      )}
      {rows.map((r: any, i: number) => (
        <div
          key={i}
          style={{
            background: "#fff",
            borderRadius: 16,
            padding: "15px 16px",
            boxShadow: "var(--shadow-sm)",
            marginBottom: 11,
          }}
        >
          <div style={{ fontWeight: 700, fontSize: 13.5, marginBottom: 11 }}>{r.dimension}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <Box label="삼성 (당사)" v={r.samsung} bg="var(--blue-soft)" />
            <Box label="애플 (경쟁사)" v={r.apple} bg="rgba(118,118,128,.08)" />
          </div>
          {r.gap && r.gap !== "insufficient_data" && (
            <div style={{ fontSize: 12.5, color: "var(--label2)", marginTop: 10 }}>{r.gap}</div>
          )}
          {r.action && (
            <div style={{ fontSize: 12.5, color: "var(--label2)", marginTop: 10 }}>{r.action}</div>
          )}
        </div>
      ))}

      {/* 요구사항 1/6: 변화 없어도 페이지 클릭 시 상세 — 페이지 브라우저 */}
      {!isExample && (pagesBySite?.samsung?.length || pagesBySite?.apple?.length) ? (
        <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: 12, color: "var(--sec)", fontWeight: 600, marginBottom: 8 }}>
            페이지별 상세 보기 (클릭 시 우측에 근거 표시)
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {(["apple", "samsung"] as const).map((site) => (
              <div key={site}>
                <div
                  style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 4px 8px" }}
                >
                  <span
                    style={{
                      width: 9,
                      height: 9,
                      borderRadius: 3,
                      background: site === "apple" ? "var(--apple)" : "var(--samsung)",
                    }}
                  />
                  <span style={{ fontWeight: 700, fontSize: 13 }}>
                    {site === "apple" ? "경쟁사 · Apple" : "당사 · Samsung"}
                  </span>
                </div>
                <div
                  style={{
                    background: "#fff",
                    borderRadius: 14,
                    boxShadow: "var(--shadow-sm)",
                    maxHeight: 280,
                    overflow: "auto",
                  }}
                >
                  {(pagesBySite[site] || []).length === 0 && (
                    <div style={{ padding: 12, fontSize: 11.5, color: "var(--ter)" }}>
                      크롤 기록 없음
                    </div>
                  )}
                  {(pagesBySite[site] || []).map((p: PageLite) => (
                    <div
                      key={p.url}
                      onClick={() => onPickPage(p.url)}
                      style={{
                        padding: "9px 13px",
                        borderTop: "1px solid var(--line)",
                        cursor: "pointer",
                        background: selPageUrl === p.url ? "var(--blue-soft)" : "transparent",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {p.title}
                      </div>
                      <div
                        className="mono"
                        style={{ fontSize: 10, color: "var(--ter)", marginTop: 2 }}
                      >
                        {p.word_count}단어
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ── 공통 작은 컴포넌트 ── */
export const ghost: React.CSSProperties = {
  background: "#fff",
  color: "var(--label)",
  borderRadius: 11,
  padding: "8px 14px",
  fontSize: 12.5,
  fontWeight: 600,
  boxShadow: "var(--shadow-sm)",
  textDecoration: "none",
};
export const pillBtn: React.CSSProperties = {
  fontSize: 11,
  color: "var(--sec)",
  fontWeight: 600,
  padding: "3px 8px",
  borderRadius: 8,
  background: "rgba(0,0,0,.05)",
};
export function Seg({ on, onClick, children }: any) {
  return (
    <button
      onClick={onClick}
      style={{
        borderRadius: 9,
        padding: "7px 14px",
        fontSize: 12.5,
        fontWeight: 600,
        color: on ? "var(--label)" : "var(--label2)",
        background: on ? "#fff" : "transparent",
        boxShadow: on ? "var(--shadow-sm)" : "none",
      }}
    >
      {children}
    </button>
  );
}
export function Muted({ children }: any) {
  return <div style={{ color: "var(--ter)", fontSize: 11, padding: "8px 10px" }}>{children}</div>;
}
export function Badge({ color, children }: any) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        color: "#fff",
        background: color,
        padding: "2px 7px",
        borderRadius: 6,
      }}
    >
      {children}
    </span>
  );
}
export function Stat({ n, label, color }: any) {
  return (
    <div style={{ textAlign: "center", minWidth: 46 }}>
      <div style={{ fontSize: 18, fontWeight: 800, color: color || "var(--label)" }}>{n}</div>
      <div style={{ fontSize: 10, color: "var(--sec)" }}>{label}</div>
    </div>
  );
}
export function Card({ children }: any) {
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 16,
        boxShadow: "var(--shadow-sm)",
        padding: 16,
        marginBottom: 13,
      }}
    >
      {children}
    </div>
  );
}
export function Box({ label, v, bg }: any) {
  return (
    <div style={{ background: bg, borderRadius: 12, padding: "11px 13px" }}>
      <div style={{ fontSize: 11, color: "var(--sec)", fontWeight: 600 }}>{label}</div>
      <div className="mono" style={{ fontSize: 15, fontWeight: 700, marginTop: 3 }}>
        {v}
      </div>
    </div>
  );
}
export function Info({ tip }: { tip: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span style={{ position: "relative", display: "inline-flex" }}>
      <span
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        style={{
          width: 15,
          height: 15,
          borderRadius: "50%",
          background: "rgba(118,118,128,.18)",
          color: "var(--sec)",
          fontSize: 10,
          fontWeight: 700,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
        }}
      >
        i
      </span>
      {open && (
        <>
          <span
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
            }}
            style={{ position: "fixed", inset: 0, zIndex: 40 }}
          />
          <span
            style={{
              position: "absolute",
              top: 20,
              left: 0,
              zIndex: 41,
              width: 220,
              background: "#fff",
              border: "1px solid var(--line)",
              boxShadow: "var(--shadow)",
              borderRadius: 10,
              padding: "10px 12px",
              fontSize: 11.5,
              fontWeight: 400,
              color: "var(--label2)",
              lineHeight: 1.5,
            }}
          >
            {tip}
          </span>
        </>
      )}
    </span>
  );
}
export function ConnBadge({ online }: { online: boolean | null }) {
  if (online === null) return null;
  return (
    <div
      style={{
        marginTop: 9,
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 11,
        fontWeight: 600,
        color: online ? "#1A7F37" : "#B42318",
        background: online ? "#EAF8EE" : "#FFF0EF",
        padding: "4px 9px",
        borderRadius: 8,
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: online ? "#1A7F37" : "#B42318",
        }}
      />
      {online ? "백엔드 연결됨" : "백엔드 연결 안 됨"}
    </div>
  );
}
export function Empty({ title, desc, cta }: { title: string; desc: string; cta?: () => void }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "70vh",
        textAlign: "center",
        padding: 24,
      }}
    >
      <div style={{ fontSize: 34, marginBottom: 14 }}>🍎</div>
      <div style={{ fontSize: 17, fontWeight: 700 }}>{title}</div>
      <div
        style={{ fontSize: 13, color: "var(--sec)", marginTop: 8, maxWidth: 420, lineHeight: 1.6 }}
      >
        {desc}
      </div>
      {cta && (
        <button
          onClick={cta}
          style={{
            marginTop: 18,
            background: "var(--blue)",
            color: "#fff",
            borderRadius: 12,
            padding: "11px 22px",
            fontSize: 13.5,
            fontWeight: 600,
          }}
        >
          크롤 실행
        </button>
      )}
    </div>
  );
}
