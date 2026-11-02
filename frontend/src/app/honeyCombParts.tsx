"use client";
/* honeyCombParts.tsx — [2026-11] HoneyCombApp.tsx 용량(47KB) 제한으로 분리한 부분.
   타입·상수·작은 표시 컴포넌트, 속성 표(AttrTable), Apple 비교 카드(8-3), 키워드 관리 탭.
   상태(state)는 HoneyCombApp 이 그대로 갖고 있고, 여기 컴포넌트는 props 로 받아 그리기만 한다(동작 변경 없음). */
import { Fragment } from "react";

export type Cell = { country: string; product: string; keyword: string; keyword_type: string; position: number | null; status: string;
  first_store?: string | null; scom_exposed?: string | null; attrs: Record<string, string>; attr_values?: Record<string, any>; feed: Record<string, string>;
  competitor_benchmark?: { position: number; title: string; merchant: string; price?: string; link?: string; attrs: Record<string, string>; attr_values?: Record<string, any> } | null };
export type Attr = { no: number; sub?: boolean; category: string; name: string; code: string; observe: string };
export type Keyword = { id: string; product: string; text: string; type: string; subtype?: string; countries: string[]; enabled: boolean; note?: string };

export const HONEY = "#E0A008", HONEY_DARK = "#8A5A00";
export const STATUS: Record<string, string> = { top1: "1순위", topn: "상단 노출", low: "8위 밖 노출", absent: "미노출", unranked: "순위 기록 없음", unchecked: "아직 조회 안 함" };
// [2026-10 통일] 순위 등급색 — 1위/상단/미노출은 공용 토큰(초록/노랑/빨강), 하단은 구분용 주황 하나만 추가
export const COLOR: Record<string, string> = { top1: "var(--green)", topn: "var(--amber)", low: "#E07A1F", absent: "var(--red)", unranked: "var(--gray)", unchecked: "var(--gray-soft)", error: "#F3F4F6" };
export const TXT: Record<string, string> = { top1: "#fff", topn: "#3A2A0F", low: "#fff", absent: "#fff", unranked: "#fff", unchecked: "#6B7280", error: "#9CA3AF" };
export const OBS: Record<string, string> = { card: "검색 결과 카드", detail: "제품 상세 창", feed: "검색 결과에 안 나옴" };
export const akey = (a: Attr) => a.code + (a.sub ? `#${a.no}` : "");
export const hexPts = (cx: number, cy: number, r: number) =>
  [0, 1, 2, 3, 4, 5].map((i) => { const a = (Math.PI / 180) * (60 * i - 30); return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`; }).join(" ");
export const J = (b: any) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
export const chip = (on: boolean): React.CSSProperties => ({ fontSize: 12, padding: "4px 10px", borderRadius: 999, cursor: "pointer", border: on ? `1px solid ${HONEY}` : "1px solid var(--line)", background: on ? HONEY : "#fff", color: on ? "#fff" : "var(--label)", fontWeight: on ? 700 : 500 });
export const th: React.CSSProperties = { textAlign: "left", fontSize: 11.5, color: "var(--sec)", fontWeight: 600, padding: "6px 8px", borderBottom: "1px solid var(--line)", whiteSpace: "nowrap" };
export const td: React.CSSProperties = { fontSize: 12, padding: "6px 8px", borderBottom: "1px solid var(--line)", verticalAlign: "top" };
export const inp: React.CSSProperties = { fontSize: 12, padding: "6px 8px", border: "1px solid var(--line)", borderRadius: 6 };
export const Badge = ({ st }: { st: string }) => <span className="badge" style={{ background: COLOR[st], color: TXT[st] }}>{STATUS[st] || st}</span>;
// [2026-11 D4] unchecked = 상세 창을 열어보지 않았거나 조회 실패(안 보임과 다름) · na = 검색 결과로는 원래 볼 수 없는 속성
export const Mark = ({ v }: { v: string }) => v === "entered" ? <span style={{ color: "#15803D", fontWeight: 700 }}>✓ 보임</span> : v === "missed" ? <span style={{ color: "var(--red-ink)", fontWeight: 700 }}>✗ 안 보임</span> : v === "unchecked" ? <span style={{ color: "var(--sec)" }}>○ 확인 안 함</span> : <span style={{ color: "var(--ter)" }}>· 확인 불가</span>;

/* ── [2026-11 D3·8-3] Apple 비교 카드 — 전체·국가별 1위 비율과 속성 영역별 노출 ── */
export function AppleCompareCard({ ap }: { ap: any }) {

                const f = (v: any) => (v == null ? "—" : `${v}%`);
                const tone = (a: any, b: any) => (a != null && b != null && b - a >= 10 ? "var(--red-ink)" : undefined);
                return (
                  <div className="card" style={{ padding: "12px 16px" }}>
                    <b style={{ fontSize: 13 }}>Apple 비교</b> <span style={{ fontSize: 11.5, color: "var(--sec)" }}>{ap.models.join(" · ")} · 공식몰(apple.com) 리스팅 기준</span>
                    <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginTop: 8 }}>
                      <div style={{ minWidth: 220 }}>
                        <div style={{ fontSize: 11.5, color: "var(--sec)" }}>1위 비율 (전체)</div>
                        <div style={{ fontSize: 18, fontWeight: 800 }}><span style={{ color: tone(ap.overall.samsung_top1, ap.overall.apple_top1) }}>삼성 {f(ap.overall.samsung_top1)}</span> <span style={{ color: "var(--sec)", fontWeight: 500, fontSize: 13 }}>vs</span> Apple {f(ap.overall.apple_top1)}</div>
                        <table style={{ borderCollapse: "collapse", marginTop: 6 }}><thead><tr><th style={th}>국가</th><th style={th}>삼성</th><th style={th}>Apple</th></tr></thead>
                          <tbody>{ap.by_country.map((r: any) => <tr key={r.country}><td style={td}>{r.country}</td><td style={{ ...td, color: tone(r.samsung_top1, r.apple_top1) }}>{f(r.samsung_top1)}</td><td style={td}>{f(r.apple_top1)}</td></tr>)}</tbody></table>
                      </div>
                      <div style={{ minWidth: 220 }}>
                        <div style={{ fontSize: 11.5, color: "var(--sec)" }}>속성 영역별 노출</div>
                        <table style={{ borderCollapse: "collapse", marginTop: 6 }}><thead><tr><th style={th}>영역</th><th style={th}>삼성</th><th style={th}>Apple</th></tr></thead>
                          <tbody>{ap.by_group.map((r: any) => <tr key={r.group}><td style={td}>{r.group}</td><td style={{ ...td, color: tone(r.samsung, r.apple) }}>{f(r.samsung)}</td><td style={td}>{f(r.apple)}</td></tr>)}</tbody></table>
                      </div>
                    </div>
                    <div style={{ fontSize: 10.5, color: "var(--gray)", marginTop: 6 }}>빨간 숫자 = Apple보다 10%p 이상 낮음</div>
                  </div>);
}

/* ── 키워드 관리 탭 ── */
export function KeywordsTab({ cfg, taxonomy, showTax, setShowTax, keywords, kwForm, setKwForm, msg, toggleKeyword, saveKeyword, removeKeyword }: {
  cfg: any; taxonomy: any; showTax: boolean; setShowTax: (f: (v: boolean) => boolean) => void;
  keywords: Keyword[]; kwForm: Partial<Keyword>; setKwForm: (v: any) => void; msg: string;
  toggleKeyword: (k: Keyword) => void; saveKeyword: () => any; removeKeyword: (id: string) => any;
}) {
  return (<>
              {taxonomy && (
                <div className="card" style={{ padding: "14px 20px" }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                    <b style={{ fontSize: 14 }}>키워드 분류 기준</b>
                    <span style={{ fontSize: 12, color: "var(--sec)" }}>제품명 키워드만 사용합니다 — "우리 제품이 1위여야 하는 검색어". 제품당 1~2개(1개 추가 = 국가 수만큼 API 호출 증가)</span>
                    <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--blue)", cursor: "pointer" }} onClick={() => setShowTax((v) => !v)}>{showTax ? "접기" : "펼치기"}</span>
                  </div>
                  {showTax && (<>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 14, marginTop: 10 }}>
                      {(["brand"] as const).filter((k) => taxonomy[k]).map((k) => { const t = taxonomy[k]; return (
                        <div key={k} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "10px 14px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}><span className="badge samsung">A</span><b style={{ fontSize: 13 }}>{t.label}</b></div>
                          <div style={{ fontSize: 12, color: "var(--label2)", margin: "6px 0 2px" }}><b>목적·KPI</b> — {t.goal}</div>
                          <div style={{ fontSize: 12, color: "var(--label2)", marginBottom: 8 }}><b>분류 규칙</b> — {t.rule}</div>
                          <table style={{ width: "100%", borderCollapse: "collapse" }}><tbody>
                            {Object.entries(t.subtypes || {}).map(([code, st]: any) => (
                              <tr key={code}><td style={{ ...td, whiteSpace: "nowrap", fontWeight: 700, color: "var(--label2)" }}>{code} {st.label}</td><td style={{ ...td, color: "var(--sec)" }}>{st.desc}</td><td style={{ ...td, fontStyle: "italic" }}>{st.ex}</td></tr>))}
                          </tbody></table>
                        </div>); })}
                    </div>
                    <div style={{ marginTop: 10, fontSize: 12, color: "var(--label2)" }}><b>작성 규칙</b>
                      <ul style={{ margin: "4px 0 0 16px", padding: 0, lineHeight: 1.6 }}>{(taxonomy.writing_rules || []).map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
                    </div>
                  </>)}
                </div>
              )}
              <div className="card">
                <b style={{ fontSize: 14 }}>키워드 추가 · 수정</b>
                <p style={{ fontSize: 12, color: "var(--sec)", margin: "4px 0 10px" }}>제품별 Google Shopping 검색어(제품명 키워드)를 관리합니다. 제품당 사용 중 키워드는 2개까지 — 키워드 1개가 늘면 국가 수(6)만큼 API 호출이 늘어납니다. 국가를 비우면 전 국가에 적용됩니다.</p>
                <div style={{ display: "grid", gridTemplateColumns: "150px 1fr 200px 1fr auto", gap: 8, alignItems: "center" }}>
                  <select value={kwForm.product || ""} onChange={(e) => setKwForm({ ...kwForm, product: e.target.value })} style={inp}>
                    <option value="">제품 선택</option>{cfg.products.map((p: any) => <option key={p.slug} value={p.slug}>{p.label}</option>)}
                  </select>
                  <input value={kwForm.text || ""} onChange={(e) => setKwForm({ ...kwForm, text: e.target.value, subtype: "A1", type: "brand" })} placeholder='제품명 키워드 (예: "Galaxy Z Fold8 Ultra")' style={inp} title="제품명 키워드만 등록할 수 있습니다" />
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>{cfg.countries.map((c: any) => { const on = (kwForm.countries || []).includes(c.code); return <span key={c.code} style={{ ...chip(on), fontSize: 11, padding: "2px 7px" }} onClick={() => setKwForm({ ...kwForm, countries: on ? (kwForm.countries || []).filter((x) => x !== c.code) : [...(kwForm.countries || []), c.code] })}>{c.code}</span>; })}</div>
                  <input value={kwForm.note || ""} onChange={(e) => setKwForm({ ...kwForm, note: e.target.value })} placeholder="메모(선택)" style={inp} />
                  <button className="btnPrimary" style={{ background: HONEY_DARK, padding: "7px 14px" }} onClick={saveKeyword}>🔒 추가</button>
                </div>
                {msg && <p style={{ fontSize: 12, color: HONEY_DARK, marginTop: 8 }}>{msg}</p>}
              </div>
              <div className="card">
                <b style={{ fontSize: 14 }}>등록된 키워드 <span style={{ color: "var(--sec)", fontWeight: 500 }}>{keywords.length}개 · 사용 중 {keywords.filter((k) => k.enabled).length}</span></b>
                <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
                  <thead><tr><th style={th}>제품</th><th style={th}>키워드</th><th style={th}>유형</th><th style={th}>국가</th><th style={th}>상태</th><th style={th}>메모</th><th style={th}></th></tr></thead>
                  <tbody>
                    {[...keywords].sort((a, b) => a.product.localeCompare(b.product) || a.type.localeCompare(b.type)).map((k) => (<tr key={k.id} style={{ opacity: k.enabled ? 1 : 0.5 }}>
                      <td style={td}>{cfg.products.find((p: any) => p.slug === k.product)?.label || k.product}</td><td style={td}>{k.text}</td>
                      <td style={td}><span className="badge samsung" title={taxonomy?.brand?.subtypes?.[k.subtype || ""]?.desc || ""}>{k.subtype || "A"} · {taxonomy?.brand?.subtypes?.[k.subtype || ""]?.label || "제품명"}</span></td>
                      <td style={td}>{k.countries?.length ? k.countries.join(", ") : "전 국가"}</td>
                      <td style={td}><span role="button" style={{ cursor: "pointer", color: k.enabled ? "#15803D" : "var(--sec)", fontWeight: 600 }} onClick={() => toggleKeyword(k)}>{k.enabled ? "사용 중" : "꺼짐"}</span></td>
                      <td style={{ ...td, color: "var(--sec)" }}>{k.note || ""}</td>
                      <td style={td}><span role="button" style={{ cursor: "pointer", color: "var(--sec)", marginRight: 10 }} onClick={() => setKwForm({ ...k })}>수정</span><span role="button" style={{ cursor: "pointer", color: "var(--high)" }} onClick={() => removeKeyword(k.id)}>삭제</span></td>
                    </tr>))}
                  </tbody>
                </table>
              </div>
  </>);
}

export function AttrValue({ v }: { v: any }) {
  if (v == null || v === "") return <span style={{ color: "var(--sec)" }}>—</span>;
  if (Array.isArray(v)) {
    return <ul style={{ margin: 0, paddingLeft: 16 }}>{v.slice(0, 6).map((x, i) => <li key={i} style={{ fontSize: 11.5 }}>{String(x)}</li>)}{v.length > 6 && <li style={{ fontSize: 11, color: "var(--sec)" }}>외 {v.length - 6}개</li>}</ul>;
  }
  const s = String(v);
  if (/^https?:\/\/.+\.(jpg|jpeg|png|webp|gif)(\?|$)/i.test(s)) {
    return <a href={s} target="_blank" rel="noreferrer" style={{ display: "flex", alignItems: "center", gap: 6 }}><img src={s} alt="" style={{ width: 28, height: 28, objectFit: "cover", borderRadius: 4, border: "1px solid var(--line)" }} /><span style={{ fontSize: 11, color: "var(--sec)", wordBreak: "break-all" }}>이미지 보기</span></a>;
  }
  if (/^https?:\/\//i.test(s)) return <a href={s} target="_blank" rel="noreferrer" style={{ fontSize: 11.5, wordBreak: "break-all" }}>{s.length > 60 ? s.slice(0, 60) + "…" : s}</a>;
  return <span style={{ fontSize: 11.5 }} title={s.length > 140 ? s : undefined}>{s.length > 140 ? s.slice(0, 140) + "…" : s}</span>;
}

export function AttrTable({ attrs, cell }: { attrs: Attr[]; cell: Cell }) {
  const cats = [...new Set(attrs.map((a) => a.category))];
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead><tr><th style={th}>#</th><th style={th}>속성</th><th style={th}>보이는 곳</th><th style={th}>화면</th><th style={th}>노출 내용 <span style={{ fontWeight: 400, color: "var(--sec)" }}>실제 관측값</span></th></tr></thead>
      <tbody>
        {cats.map((cat) => (<Fragment key={cat}>
          <tr><td colSpan={5} style={{ ...td, background: "var(--rail)", fontWeight: 700, fontSize: 11.5, color: "var(--label2)" }}>{cat}</td></tr>
          {attrs.filter((a) => a.category === cat).map((a) => { const v = cell.attrs[akey(a)] || "na";
            return (<tr key={akey(a)} style={{ background: v === "missed" ? "var(--high-soft)" : undefined }}>
              <td style={{ ...td, color: "var(--sec)" }}>{a.no}{a.sub ? "·" : ""}</td><td style={td}>{a.name}</td><td style={{ ...td, color: "var(--sec)" }}>{OBS[a.observe]}</td>
              <td style={td}><Mark v={v} /></td>
              <td style={{ ...td, maxWidth: 320 }}>{v === "entered" ? <AttrValue v={cell.attr_values?.[akey(a)]} /> : <span style={{ color: "var(--sec)" }}>—</span>}</td>
            </tr>); })}
        </Fragment>))}
      </tbody>
    </table>
  );
}
