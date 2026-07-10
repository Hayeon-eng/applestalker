"use client";
/* QubiSections.tsx — QubiApp에서 분리한 큰 렌더 블록들(파일 크기 축소용).
   상태/핸들러는 QubiApp에서 ctx 객체로 주입받는다. */
import { useState, Fragment } from "react";
import type { ReactNode } from "react";
import { SEV, HONEY, tierOf, inputStyle, sel } from "./qubiShared";

export function SpecTable({ ctx: c }: { ctx: any }) {
  if (c.tab !== "copy") return null;
  return (
    <div className="card" style={{ marginTop: 18, padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <b style={{ fontSize: 14 }}>검수 기준 스펙</b>
        <span style={{ fontSize: 12, color: "var(--sec)" }}>제품:</span>
        <select value={c.specProduct} onChange={(e) => c.setSpecProduct(e.target.value)} style={{ ...inputStyle }}>
          {c.products.map((p: any) => <option key={p.code} value={p.code}>{p.label}</option>)}
        </select>
        <input value={c.newProd} onChange={(e) => c.setNewProd(e.target.value)} placeholder="새 제품 추가(galaxy-buds4-pro)" style={{ ...inputStyle, width: 220 }} />
        <button onClick={c.addProduct} className="btnSecondary" style={{ fontSize: 12, padding: "5px 10px" }}>＋ 제품</button>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 10, fontSize: 12.5 }}>
        <thead><tr style={{ color: "var(--sec)", fontSize: 11, textAlign: "left" }}>
          <th style={{ padding: "4px 6px" }}>항목</th><th style={{ padding: "4px 6px" }}>값(여러 값=콤마)</th><th style={{ padding: "4px 6px" }}>단위</th><th style={{ padding: "4px 6px" }}>적용 페이지</th><th /></tr></thead>
        <tbody>
          {c.specs.map((sp: any, i: number) => (
            <tr key={i}>
              <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}>{sp.category}</td>
              <td style={{ padding: 6, borderTop: "1px solid var(--line)", fontWeight: 700 }}>{(sp.values || (sp.value != null ? [sp.value] : [])).join(" / ")}</td>
              <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}>{sp.unit}</td>
              <td style={{ padding: 6, borderTop: "1px solid var(--line)", color: "var(--sec)", fontSize: 11 }}>{(sp.page_types || ["PDP"]).join(", ")}</td>
              <td style={{ padding: 6, borderTop: "1px solid var(--line)", textAlign: "right" }}><span role="button" onClick={() => c.removeSpec(i)} style={{ cursor: "pointer", color: "var(--high)", fontSize: 11 }}>삭제</span></td>
            </tr>
          ))}
          <tr>
            <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}>
              <select value={c.specForm.category} onChange={(e) => c.pickCatalog(e.target.value)} style={{ ...inputStyle, width: "100%" }}>
                <option value="">항목 선택…</option>
                {c.catalog.map((cc: any) => <option key={cc.category} value={cc.category}>{cc.category} · {cc.label}</option>)}
              </select>
            </td>
            <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}><input value={c.specForm.value} onChange={(e) => c.setSpecForm({ ...c.specForm, value: e.target.value })} placeholder="예: 31  또는  7,8" style={{ ...inputStyle, width: 90 }} /></td>
            <td style={{ padding: 6, borderTop: "1px solid var(--line)" }}><input value={c.specForm.unit} onChange={(e) => c.setSpecForm({ ...c.specForm, unit: e.target.value })} placeholder="단위" style={{ ...inputStyle, width: 60 }} /></td>
            <td style={{ padding: 6, borderTop: "1px solid var(--line)", color: "var(--sec)", fontSize: 11 }}>PDP</td>
            <td style={{ padding: 6, borderTop: "1px solid var(--line)", textAlign: "right" }}><button onClick={c.addSpec} className="btnSecondary" style={{ fontSize: 12, padding: "4px 10px" }}>＋ 추가</button></td>
          </tr>
        </tbody>
      </table>
      <p style={{ fontSize: 11, color: "var(--sec)", marginTop: 6 }}>값에 콤마를 넣으면 국별 표기 차이를 모두 인정합니다(예: 재생시간 7,8 → 7h·8h 둘 다 통과). 숫자 콤마·공백(2,600=2600)도 자동 인식.</p>
    </div>
  );
}

export function RuleAddPanel({ ctx: c }: { ctx: any }) {
  if (!c.showRuleAdd) return null;
  return (
    <div className="card" style={{ marginTop: 16, padding: 14 }}>
      <b style={{ fontSize: 14 }}>룰 추가 — {c.tab === "schema" ? `스키마 (${c.product}·${c.pageType})` : "스펙"}</b>
      {c.tab === "schema" ? (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <input list="qb-schema-types" value={c.ruleForm.block_type} onChange={(e) => c.setRuleForm({ ...c.ruleForm, block_type: e.target.value })} placeholder="① 스키마 타입 (WebPage…)" style={{ ...inputStyle, width: 180 }} />
            <datalist id="qb-schema-types">{c.schemaTypes.map((t: string) => <option key={t} value={t} />)}</datalist>
            <input value={c.ruleForm.property} onChange={(e) => c.setRuleForm({ ...c.ruleForm, property: e.target.value })} placeholder="② 속성 (name, url, @id…)" style={{ ...inputStyle, width: 170 }} />
            <select value={c.ruleForm.value_kind} onChange={(e) => c.setRuleForm({ ...c.ruleForm, value_kind: e.target.value })} style={{ ...inputStyle, width: 190 }}>
              <option value="exists">③ 존재만 (값 검사 안 함)</option>
              <option value="url">URL/@id (SITECODE 가변·정확)</option>
              <option value="enum">enum/타입 (정확 일치)</option>
              <option value="text">번역 텍스트 (확인만·warn)</option>
            </select>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginTop: 6 }}>
            {c.ruleForm.value_kind !== "exists" && c.ruleForm.value_kind !== "text" && (
              <input value={c.ruleForm.value} onChange={(e) => c.setRuleForm({ ...c.ruleForm, value: e.target.value })}
                placeholder={c.ruleForm.value_kind === "url" ? "④ 기대값 예: https://www.samsung.com/{SITECODE}/…/#webpage" : "④ 기대값 예: WebPage,ItemPage"}
                style={{ ...inputStyle, width: 420 }} />
            )}
            <select value={c.ruleForm.nested} onChange={(e) => c.setRuleForm({ ...c.ruleForm, nested: e.target.value })} style={{ ...inputStyle, width: 150 }}>
              <option value="">중첩 없음</option>
              <option value="@id">중첩 @id 로 검사</option>
              <option value="@type">중첩 @type 로 검사</option>
            </select>
            <button onClick={c.addRule} className="toolBtn">추가</button>
          </div>
          <div style={{ fontSize: 11, color: "var(--sec)", marginTop: 8, lineHeight: 1.6 }}>
            타입 블록에 속성을 등록하고, <b>값 종류</b>까지 지정하면 값 검수(#5)에 바로 반영됩니다.
            블록이 없으면 새로 만들어 이 페이지타입에 등록해요.<br />
            · <b>존재만</b>: 있는지만 확인 · <b>URL/@id</b>: <code>{"{SITECODE}"}</code>·<code>{"{LANG-CODE}"}</code> 자동 치환 후 정확 일치(불일치=오류)
            · <b>enum/타입</b>: 정확 일치 · <b>번역 텍스트</b>: 번역 여부 확인(warn, 오류 아님)
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
          <select value={c.ruleForm.kind} onChange={(e) => c.setRuleForm({ ...c.ruleForm, kind: e.target.value })} style={{ ...inputStyle, width: 140 }}>
            <option value="spec">스펙 토큰</option><option value="proper_noun">고유명사</option>
          </select>
          <input value={c.ruleForm.token} onChange={(e) => c.setRuleForm({ ...c.ruleForm, token: e.target.value })} placeholder={c.ruleForm.kind === "spec" ? "예: 2600 nits" : "예: Corning Gorilla Armor 2"} style={{ ...inputStyle, width: 260 }} />
          <button onClick={c.addRule} className="toolBtn">추가</button>
        </div>
      )}
    </div>
  );
}

export function CriteriaPanel({ ctx: c }: { ctx: any }) {
  const { rules } = c;
  if (!c.showRules || !rules) return null;
  return (
    <div ref={c.rulesRef} className="card qbiPopIn" style={{ marginTop: 16, padding: 14,
      outline: c.rulesFlash ? `3px solid ${HONEY}` : "3px solid transparent",
      boxShadow: c.rulesFlash ? `0 0 0 6px ${HONEY}22` : "none",
      transition: "outline .3s, box-shadow .3s" }}>
      <b style={{ fontSize: 14 }}>검수 기준 — {c.tab === "schema" ? `스키마 (${c.product}·${c.pageType})` : "스펙"}</b>
      {c.tab === "schema" ? (
        <div style={{ fontSize: 12.5, marginTop: 8 }}>
          {rules.schema_set_label && <p style={{ color: "var(--label)", fontWeight: 700 }}>세트: {rules.schema_set_label}</p>}
          <p style={{ color: "var(--sec)" }}>{rules.schema?.["설명"]}</p>
          {rules.schema?.["출처"] && <p style={{ color: "var(--sec)", fontSize: 11 }}>{rules.schema["출처"]}</p>}
          {(rules.schema?.blocks || []).length === 0 && <p style={{ color: "var(--sec)" }}>이 페이지타입은 스키마 검사 대상이 아니거나 아직 룰이 없어요.</p>}
          {(rules.schema?.blocks || []).map((b: any, i: number) => (
            <div key={i} style={{ borderTop: "1px solid var(--line)", padding: "6px 0" }}><b>{b.block}</b> <span style={{ color: "var(--sec)" }}>{(b.types || []).join(", ")}</span>{b.required_properties?.length > 0 && <div>필수: {b.required_properties.join(", ")}</div>}</div>
          ))}
          {rules.check_methods && (
            <div style={{ borderTop: "2px solid var(--line)", marginTop: 8, paddingTop: 8 }}>
              <b>우리 기준 — 검사 방식</b>
              <p style={{ color: "var(--sec)", margin: "2px 0 6px" }}>{rules.check_methods["설명"]}</p>
              <div style={{ fontWeight: 700, color: "var(--high)" }}>🔴 정확히 일치 안 하면 오류</div>
              <ul style={{ margin: "2px 0 6px 16px", color: "var(--sec)", lineHeight: 1.7 }}>
                {(rules.check_methods["정확히_일치_오류"] || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
              </ul>
              <div style={{ fontWeight: 700, color: "var(--high)" }}>🔴 필수 항목 없으면 오류</div>
              <ul style={{ margin: "2px 0 6px 16px", color: "var(--sec)", lineHeight: 1.7 }}>
                {(rules.check_methods["필수_있어야_함_오류"] || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
              </ul>
              <div style={{ fontWeight: 700, color: HONEY }}>🟡 확인(경고) — 오류 아님</div>
              <ul style={{ margin: "2px 0 0 16px", color: "var(--sec)", lineHeight: 1.7 }}>
                {(rules.check_methods["확인_경고"] || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
          {rules.google_criteria && (
            <div style={{ borderTop: "2px solid var(--line)", marginTop: 8, paddingTop: 8 }}>
              <b>Google 기준</b>
              <p style={{ color: "var(--sec)", margin: "2px 0 8px" }}>{rules.google_criteria["설명"]}</p>

              <div style={{ fontWeight: 700, fontSize: 12.5 }}>· 문법 오류</div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 4 }}>
                <div style={{ flex: 1, minWidth: 220 }}>
                  <div style={{ fontWeight: 700, color: "#0A66E0" }}>Google Rich Result 기준</div>
                  <ul style={{ margin: "4px 0 0 16px", color: "var(--sec)" }}>
                    {(rules.google_criteria["문법_오류"]?.["구글_기준"] || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
                <div style={{ flex: 1, minWidth: 220 }}>
                  <div style={{ fontWeight: 700, color: HONEY }}>우리 기준</div>
                  <ul style={{ margin: "4px 0 0 16px", color: "var(--sec)" }}>
                    {(rules.google_criteria["문법_오류"]?.["우리_기준"] || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              </div>

              <div style={{ fontWeight: 700, fontSize: 12.5, marginTop: 10 }}>· 리치결과 필수/권장 속성</div>
              <div style={{ fontWeight: 700, color: "var(--high)", marginTop: 4 }}>🔴 필수 속성 누락/형식오류</div>
              <ul style={{ margin: "2px 0 6px 16px", color: "var(--sec)", lineHeight: 1.7 }}>
                {(rules.google_criteria["리치결과_필수_권장"]?.["필수_속성_누락_오류"] || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
              </ul>
              <div style={{ fontWeight: 700, color: HONEY }}>🟡 권장 속성 누락</div>
              <ul style={{ margin: "2px 0 6px 16px", color: "var(--sec)", lineHeight: 1.7 }}>
                {(rules.google_criteria["리치결과_필수_권장"]?.["권장_속성_누락_경고"] || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
              </ul>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                {Object.entries(rules.google_criteria["리치결과_필수_권장"]?.["타입별_상태"] || {}).map(([t, s]: any) => (
                  <span key={t} style={{ fontSize: 11, background: "#F2F4F7", borderRadius: 6, padding: "3px 8px" }}><b>{t}</b> — {s}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div style={{ fontSize: 12.5, marginTop: 8 }}>
          <p style={{ color: "var(--sec)" }}>{rules.copy?.["설명"]}</p>
          <div style={{ borderTop: "1px solid var(--line)", marginTop: 8, paddingTop: 8 }}>
            <div style={{ fontWeight: 700, color: HONEY, marginBottom: 4 }}>우리 기준 — 검사 방식</div>
            <ul style={{ margin: "0 0 0 16px", color: "var(--sec)", lineHeight: 1.7 }}>
              <li><b style={{ color: "var(--high)" }}>정확히 일치</b> — 숫자+하드웨어 단위(200 MP · 1 TB · 512 GB · 5000 mAh · 2600 nits · 100x …)는 번역돼도 동일하므로 페이지에 정확히 있는지 검사. 같은 단위인데 <b>다른 값</b>이 있으면 오류(예: 2600 nits 자리에 600).</li>
              <li><b style={{ color: HONEY }}>확인(WARN)</b> — 기대 스펙 값이 <b>아예 없으면</b> 확인 필요(나라별로 미표기일 수 있어 오류 아님).</li>
              <li><b style={{ color: HONEY }}>확인(WARN)</b> — 고유명사(Snapdragon 8 Elite Gen 5 · Vapor Chamber · Galaxy AI …)는 현지어 대체 가능성이 있어 <b>존재만</b> 확인.</li>
              <li><b style={{ color: "var(--sec)" }}>해당없음(회색)</b> — 그 페이지타입에 원래 없는 스펙은 검사 제외.</li>
              <li>서술형 문장은 값 일치를 검사하지 않습니다.</li>
            </ul>
          </div>
          {(rules.copy?.spec_tokens || []).length > 0 && <div style={{ marginTop: 8 }}><b>스펙 토큰:</b> {(rules.copy?.spec_tokens || []).join(", ")}</div>}
          {(rules.copy?.proper_nouns || []).length > 0 && <div style={{ marginTop: 6 }}><b>고유명사:</b> {(rules.copy?.proper_nouns || []).join(", ")}</div>}
        </div>
      )}
    </div>
  );
}

// 내부 계산 토큰을 사람이 읽는 말로 (QuickView 등 findings 텍스트에 노출될 때)
const TERM_MAP: Record<string, string> = {
  structure_valid: "FAQ 구조 유효성",
  screen_match: "화면 노출 일치",
  type_combo: "타입 선언(@type)",
  contentUrlOrEmbedUrl: "영상 URL",
  encoding_contentUrl: "3D 파일 URL",
  encoding_encodingFormat: "3D 포맷",
};
function humanizeTerm(s: string): string {
  if (!s) return s;
  let out = s;
  for (const [k, v] of Object.entries(TERM_MAP)) out = out.split(k).join(v);
  return out;
}

export function QuickView({ ctx: c }: { ctx: any }) {
  if (!c.quickOpen) {
    return (
      <button onClick={() => c.setQuickOpen(true)} style={{ position: "fixed", right: 20, bottom: 20, zIndex: 40, background: "#101318", color: "#fff", border: "none", borderRadius: 999, padding: "12px 18px", fontWeight: 700, cursor: "pointer", boxShadow: "0 6px 20px rgba(0,0,0,.2)" }}>
        🐝 Quick View{c.results.length ? ` · ${c.results.length}` : ""}
      </button>
    );
  }
  return (
    <div style={{ position: "fixed", right: 20, bottom: 20, zIndex: 40, width: 380, maxHeight: "72vh", overflow: "auto", background: "#fff", border: "1px solid var(--line)", borderRadius: 14, boxShadow: "0 10px 30px rgba(0,0,0,.22)" }}>
      <div style={{ position: "sticky", top: 0, background: "#101318", color: "#fff", padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center", borderRadius: "14px 14px 0 0" }}>
        <b style={{ fontSize: 13 }}>🐝 Quick View — {c.tab === "schema" ? "스키마" : "스펙"}</b>
        <span role="button" onClick={() => c.setQuickOpen(false)} style={{ cursor: "pointer" }}>✕</span>
      </div>
      <div style={{ padding: 14 }}>
        <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--sec)", marginBottom: 6 }}>권역 신호등</div>
        {Object.keys(c.regionTier).length === 0 && <p style={{ fontSize: 12, color: "var(--sec)" }}>검수를 실행하면 권역별 상태가 표시됩니다.</p>}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
          {Object.entries(c.regionTier).map(([rg, cc]: [string, any]) => (
            <span key={rg} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, border: "1px solid var(--line)", borderRadius: 999, padding: "3px 9px" }}>
              <span className={`scoreDot ${tierOf(cc)}`} />{rg}<span style={{ color: "var(--sec)" }}>{cc.fail ? `오류${cc.fail}` : cc.warn ? `확인${cc.warn}` : "정상"}</span>
            </span>
          ))}
        </div>
        {c.countries.length > 0 && (
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 10 }}>
            <button onClick={() => c.setQCountry("전체")} style={sel("전체", c.qCountry === "전체")}>전체</button>
            {c.countries.map((cn: string) => <button key={cn} onClick={() => c.setQCountry(cn)} style={sel(cn, c.qCountry === cn)}>{cn}</button>)}
          </div>
        )}
        {c.quickRows.length === 0 && <p style={{ fontSize: 12, color: "var(--sec)" }}>표시할 오류가 없어요.</p>}
        {c.quickRows.slice(0, 60).map((x: any, i: number) => {
          const key = `${x.r.sitecode}-${i}`;
          return (
            <div key={key} style={{ borderTop: "1px solid var(--line)", padding: "7px 0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 6, cursor: "pointer" }} onClick={() => c.setQDetail(c.qDetail === key ? null : key)}>
                <span style={{ fontSize: 12 }}><span style={{ background: SEV[x.f.status as keyof typeof SEV].c, color: "#fff", fontSize: 10, fontWeight: 700, padding: "1px 5px", borderRadius: 4, marginRight: 5 }}>{SEV[x.f.status as keyof typeof SEV].ko}</span><b>{x.r.sitecode}</b> · {humanizeTerm(x.item)}</span>
                <span style={{ fontSize: 11, color: "#0A66E0" }}>{c.qDetail === key ? "닫기" : "상세"}</span>
              </div>
              {c.qDetail === key && (
                <div style={{ fontSize: 12, marginTop: 4, background: "#F9FAFB", borderRadius: 6, padding: 8 }}>
                  <div style={{ color: "var(--sec)" }}>as-is: {humanizeTerm(x.f.as_is)}</div>
                  <div style={{ fontWeight: 600, marginTop: 2 }}>→ {humanizeTerm(x.f.to_be)}</div>
                  {x.r.url && <div style={{ fontFamily: "monospace", fontSize: 10.5, color: "#98A2B3", marginTop: 4, wordBreak: "break-all" }}>{x.r.url}</div>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── HTML QA 종합 패널 [신규] ──────────────────────────────────────
// 최상단 종합판단(전체 신호등 + 타입별 신호등) + 항목별 그룹핑(Meta/H태그 · 스키마 정보적합성 ·
// 파싱+리치결과 · id연결성). Level1(적용율%)+Level2(3축) 백엔드(/api/qb/check-html-qa) 결과를 그대로 렌더링.
const TL_COLOR: Record<string, string> = { green: "#1F9E5C", yellow: "#E0A008", red: "#D8362F" };
const TL_EMOJI: Record<string, string> = { green: "🟢", yellow: "🟡", red: "🔴" };

function Accordion({ title, defaultOpen, children }: { title: ReactNode; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 10, marginTop: 10, overflow: "hidden" }}>
      <div onClick={() => setOpen((v) => !v)} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", background: "#F9FAFB", cursor: "pointer", fontSize: 13, fontWeight: 700 }}>
        <span>{title}</span><span style={{ fontSize: 11, color: "#0A66E0" }}>{open ? "▲ 접기" : "▼ 펼치기"}</span>
      </div>
      {open && <div className="qbiPopIn" style={{ padding: "10px 12px" }}>{children}</div>}
    </div>
  );
}

// 속성별 '수정 위치 + 영향' 표시용 정적 사전(로직/점수와 무관, 표현 전용)
const PROP_HELP: Record<string, { label: string; where: string; why: string }> = {
  name: { label: "제품명(name)", where: "JSON-LD → Product → name", why: "제품명 누락 시 Product 리치결과 생성 불가" },
  image: { label: "대표 이미지(image)", where: "JSON-LD → Product → image", why: "이미지 없으면 리치결과 미표기 가능" },
  brand: { label: "브랜드(brand)", where: "JSON-LD → Product → brand", why: "브랜드 정보로 신뢰도·매칭 향상" },
  manufacturer: { label: "제조사(manufacturer)", where: "JSON-LD → Product → manufacturer", why: "제조사 정보 보강" },
  potentialAction: { label: "구매 액션(potentialAction)", where: "JSON-LD → Product → potentialAction", why: "구매 액션 연결" },
  subjectOf: { label: "연결 선언(subjectOf)", where: "JSON-LD → Product → subjectOf(@id)", why: "영상·3D·FAQ 연결 선언" },
  offers: { label: "가격·재고(offers)", where: "JSON-LD → Product → offers", why: "가격·재고 정보(단독형 PDP 필수)" },
  sku: { label: "제품 식별자(sku)", where: "JSON-LD → Product → sku", why: "제품 식별자" },
  // 내부 계산 키 → 사람이 읽는 라벨
  structure_valid: { label: "FAQ 구조 유효성", where: "JSON-LD → FAQPage → mainEntity(Question/Answer)", why: "질문·답변 구조가 올바라야 FAQ로 인식" },
  screen_match: { label: "화면 노출 일치", where: "FAQPage 마크업 ↔ 화면 Q&A", why: "마크업과 실제 화면 내용이 일치해야 함" },
  type_combo: { label: "타입 선언(@type)", where: "JSON-LD → @type", why: "필수 타입 조합 선언" },
  url: { label: "URL", where: "JSON-LD → url", why: "정규 URL과 일치" },
  numberOfItems: { label: "항목 수(numberOfItems)", where: "JSON-LD → ItemList → numberOfItems", why: "선언 개수 = 실제 항목 수" },
  itemListElement: { label: "목록 항목(itemListElement)", where: "JSON-LD → ItemList → itemListElement", why: "목록 항목 완비" },
  mainEntityOfPage: { label: "페이지 연결(mainEntityOfPage)", where: "JSON-LD → mainEntityOfPage", why: "페이지와 상호 연결" },
  encoding_contentUrl: { label: "3D 파일 URL(encoding.contentUrl)", where: "JSON-LD → 3DModel → encoding.contentUrl", why: "3D 모델 파일 경로" },
  encoding_encodingFormat: { label: "3D 포맷(encoding.encodingFormat)", where: "JSON-LD → 3DModel → encoding.encodingFormat", why: "유효한 3D MIME" },
  thumbnailUrl: { label: "썸네일(thumbnailUrl)", where: "JSON-LD → VideoObject → thumbnailUrl", why: "영상 썸네일" },
  uploadDate: { label: "업로드일(uploadDate)", where: "JSON-LD → VideoObject → uploadDate", why: "ISO8601 업로드일" },
  contentUrlOrEmbedUrl: { label: "영상 URL(contentUrl/embedUrl)", where: "JSON-LD → VideoObject → contentUrl 또는 embedUrl", why: "재생 가능한 영상 경로" },
  duration: { label: "재생 길이(duration)", where: "JSON-LD → VideoObject → duration", why: "영상 길이(PT#S)" },
  description: { label: "설명(description)", where: "JSON-LD → description", why: "요약 설명" },
};
const propHelp = (p: string) => PROP_HELP[p] || { label: p, where: `JSON-LD → ${p}`, why: "" };

// PASS/부족 배지
function StatusChip({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span style={{ fontSize: 11, borderRadius: 6, padding: "3px 8px", whiteSpace: "nowrap",
      background: ok ? "#ECFDF3" : "#FEF3F2", color: ok ? "#067647" : "#D8362F" }}>
      {ok ? "✅" : "❌"} {label}
    </span>
  );
}

// 충족률 게이지(작은 막대) — KPI 유지용
function Meter({ pct, danger }: { pct: number | null; danger?: boolean }) {
  const v = pct == null ? 0 : pct;
  const color = danger || v < 50 ? "#D8362F" : v < 80 ? "#E0A008" : "#1F9E5C";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 130 }}>
      <div style={{ flex: 1, height: 6, background: "#EEF1F6", borderRadius: 999 }}>
        <div style={{ width: `${v}%`, height: "100%", background: color, borderRadius: 999 }} />
      </div>
      <b style={{ fontSize: 12.5, color }}>{pct == null ? "—" : `${pct}%`}</b>
    </div>
  );
}

export function HtmlQaDetail({ hq, findings = [] }: { hq: any; findings?: any[] }) {
  const l1 = hq.level1_apply_rate || {};
  const axis2 = hq.level2?.axis2_parsing_rich_result || {};
  const axis3 = hq.level2?.axis3_id_linkage || {};
  const perType: Record<string, any> = hq.level2?.per_type || {};
  const sig = l1.signals || {};

  // findings를 블록별로 묶어 '수정 위치' 표시에 활용
  const findingsByBlock: Record<string, any[]> = {};
  for (const f of findings || []) (findingsByBlock[f.block || "기타"] ||= []).push(f);

  // HTML QA 항목(Meta/H태그) — PASS/FAIL 한눈에
  const titleLen = (sig.title || "").length;
  const descLen = (sig.meta_description || "").length;
  const h1n = (sig.h1_list || []).length;
  const htmlItems = [
    { key: "Meta Title", ok: !!sig.title && titleLen <= 60, val: sig.title, note: sig.title ? `${titleLen}자` : "누락", where: "<head> → <title>" },
    { key: "Meta Description", ok: !!sig.meta_description && descLen <= 160, val: sig.meta_description, note: sig.meta_description ? `${descLen}자` : "누락", where: "<head> → meta[name=description]" },
    { key: "H1", ok: h1n === 1, val: (sig.h1_list || []).join(" / "), note: `${h1n}개`, where: "본문 <h1>" },
    { key: "H2", ok: (sig.h2_list || []).length > 0, val: `${(sig.h2_list || []).length}개`, note: `${(sig.h2_list || []).length}개`, where: "본문 <h2>" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* ═══ HTML QA 카드 ═══ */}
      <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "12px 14px" }}>
        <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 8 }}>HTML 검수 <span style={{ fontWeight: 400, color: "var(--sec)", fontSize: 11.5 }}>Meta · 제목 태그</span></div>
        {/* 문제 먼저 */}
        {htmlItems.filter((i) => !i.ok).length > 0 && (
          <div style={{ background: "#FEF3F2", borderRadius: 8, padding: "8px 10px", marginBottom: 8 }}>
            {htmlItems.filter((i) => !i.ok).map((i) => (
              <div key={i.key} style={{ fontSize: 12.5, padding: "2px 0" }}>
                <b style={{ color: "#B42318" }}>❌ {i.key}</b> <span style={{ color: "var(--sec)" }}>{i.note}</span>
                <span style={{ color: "var(--sec)", marginLeft: 6, fontSize: 11.5 }}>· 수정 위치: {i.where}</span>
              </div>
            ))}
          </div>
        )}
        {/* 실제 태깅 값 + PASS */}
        <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", rowGap: 7, fontSize: 12.5, alignItems: "start" }}>
          {htmlItems.map((i) => (
            <Fragment key={i.key}>
              <span style={{ color: "var(--sec)" }}>{i.ok ? "✅" : "❌"} {i.key}</span>
              <span>
                {i.key === "H2"
                  ? ((sig.h2_list || []).length ? (sig.h2_list || []).map((t: string, k: number) => <span key={k} style={{ display: "inline-block", background: "#F2F4F7", padding: "2px 6px", borderRadius: 5, margin: "1px 4px 1px 0", fontSize: 11.5 }}>{t}</span>) : <i style={{ color: "#B42318" }}>누락</i>)
                  : (i.val ? <code style={{ background: "#F2F4F7", padding: "2px 6px", borderRadius: 5, wordBreak: "break-word" }}>{i.val}</code> : <i style={{ color: "#B42318" }}>누락</i>)}
              </span>
            </Fragment>
          ))}
        </div>
      </div>

      {/* ═══ Schema QA 카드들 — 타입별 ═══ */}
      <div>
        <div style={{ fontSize: 13, fontWeight: 800, margin: "0 0 8px" }}>Schema 검수 <span style={{ fontWeight: 400, color: "var(--sec)", fontSize: 11.5 }}>구조화 데이터(JSON-LD)</span></div>
        {Object.keys(perType).length === 0 && <p style={{ color: "var(--sec)", fontSize: 12.5 }}>감지된 Schema가 없어요.</p>}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {Object.entries(perType).map(([t, v]: [string, any]) => {
            const missReq: string[] = v.missing_required || [];
            const weakRec: string[] = v.weak_recommended || [];
            const blockFindings = (findingsByBlock[t] || []).filter((f) => f.status === "fail" || f.status === "warn");
            // 파싱/리치결과 Critical 중, 이미 '필수 누락'으로 위에 표시한 속성과 겹치는 메시지는 제외(중복 방지)
            const parseCritical = (axis2.by_type?.[t]?.detail || []).filter((d: any) =>
              d.severity === "Critical" && !missReq.some((p) => (d.message || "").includes(p)));
            const allBlockFindings = (findingsByBlock[t] || []);
            const codeSnippet = allBlockFindings.find((f: any) => f.raw)?.raw || "";
            return (
              <details key={t} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "12px 14px" }}>
                <summary style={{ listStyle: "none", cursor: "pointer" }}>
                  {/* 헤더: 신호등 + 타입 + 최종% */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span>{TL_EMOJI[v.traffic_light] || "⚪"}</span>
                    <b style={{ fontSize: 13 }}>{t}</b>
                    {v.rich_result_status && v.rich_result_status !== "정식" &&
                      <span style={{ fontSize: 10.5, color: "var(--sec)", background: "#F2F4F7", borderRadius: 5, padding: "1px 6px" }}>리치결과 {v.rich_result_status}</span>}
                    <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
                      <Meter pct={v.final_pct} danger={v.axis1_gate_triggered || v.axis2_gate === 0} />
                      <span style={{ fontSize: 11, color: "#0A66E0" }}>펼치기 ▾</span>
                    </span>
                  </div>

                  {/* 1) 문제 먼저 (사람 라벨 + 영향 + 수정 위치) */}
                  {missReq.length > 0 && (
                    <div style={{ background: "#FEF3F2", borderRadius: 8, padding: "8px 10px", marginTop: 8 }}>
                      {missReq.map((p) => {
                        const h = propHelp(p);
                        return (
                          <div key={p} style={{ fontSize: 12.5, padding: "3px 0" }}>
                            <b style={{ color: "#B42318" }}>❌ {h.label} 누락/미흡</b>
                            {h.why && <div style={{ color: "var(--sec)", fontSize: 11.5, marginLeft: 18 }}>영향: {h.why}</div>}
                            <div style={{ color: "var(--sec)", fontSize: 11.5, marginLeft: 18 }}>수정 위치: {h.where}</div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {parseCritical.length > 0 && (
                    <div style={{ background: "#FEF3F2", borderRadius: 8, padding: "8px 10px", marginTop: 6 }}>
                      {parseCritical.map((d: any, i: number) => (
                        <div key={i} style={{ fontSize: 12.5, color: "#B42318" }}>❌ {d.message}</div>
                      ))}
                    </div>
                  )}

                  {/* 2) 충족 현황(개수) */}
                  <div style={{ display: "flex", gap: 16, fontSize: 12.5, flexWrap: "wrap", marginTop: 8 }}>
                    <span style={{ color: "var(--sec)" }}>정보 충족률 <b style={{ color: "var(--label)" }}>{v.axis1_info_adequacy_pct}%</b></span>
                    <span style={{ color: "var(--sec)" }}>필수 속성 <b style={{ color: v.required_ok < v.required_total ? "#B42318" : "#067647" }}>{v.required_ok} / {v.required_total}</b></span>
                    <span style={{ color: "var(--sec)" }}>권장 속성 <b style={{ color: v.recommended_ok < v.recommended_total ? "#E0A008" : "#067647" }}>{v.recommended_ok} / {v.recommended_total}</b></span>
                  </div>
                  {weakRec.length > 0 && (
                    <div style={{ marginTop: 6, fontSize: 11.5, color: "var(--sec)" }}>🟡 권장 보강: {weakRec.map((p) => propHelp(p).label).join(", ")}</div>
                  )}
                  {missReq.length === 0 && !v.axis1_gate_triggered && weakRec.length === 0 && parseCritical.length === 0 && (
                    <div style={{ marginTop: 6, fontSize: 12, color: "#067647" }}>✅ 모든 필수·권장 항목 충족</div>
                  )}
                </summary>

                {/* ── 펼침: 속성별 상세 + JSON-LD 코드 ── */}
                <div style={{ marginTop: 10, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
                  <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--sec)", marginBottom: 4 }}>속성별 상세</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr auto", rowGap: 4, fontSize: 12 }}>
                    {(v.prop_detail || []).length > 0 ? (v.prop_detail || []).map((pd: any, i: number) => (
                      <Fragment key={i}>
                        <span>{pd.score >= 1 ? "✅" : pd.score > 0 ? "🟡" : "❌"} {propHelp(pd.prop).label}</span>
                        <span style={{ color: "var(--sec)", textAlign: "right" }}>{pd.score >= 1 ? "충족" : pd.score > 0 ? "부분" : "누락"}</span>
                      </Fragment>
                    )) : <span style={{ color: "var(--sec)" }}>상세 정보 없음</span>}
                  </div>
                  {blockFindings.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--sec)", marginBottom: 4 }}>판정 근거</div>
                      {blockFindings.map((f: any, i: number) => (
                        <div key={i} style={{ fontSize: 11.5, color: "var(--sec)", padding: "2px 0" }}>· {f.as_is}{f.to_be ? ` → ${f.to_be}` : ""}</div>
                      ))}
                    </div>
                  )}
                  {codeSnippet && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--sec)", marginBottom: 4 }}>현재 JSON-LD (수정 대상)</div>
                      <pre style={{ margin: 0, background: "#0F172A", color: "#E2E8F0", fontSize: 11, borderRadius: 8, padding: "8px 10px", overflowX: "auto", lineHeight: 1.5 }}>
{codeSnippet.split("\n").map((ln: string, i: number) => (
  <div key={i}><span style={{ color: "#475569", userSelect: "none", display: "inline-block", width: 26, textAlign: "right", marginRight: 10 }}>{i + 1}</span>{ln}</div>
))}
                      </pre>
                    </div>
                  )}
                </div>
              </details>
            );
          })}
        </div>
      </div>

      {/* ═══ 연결성(@id) — 있을 때만, 간단히 ═══ */}
      {(axis3.checks || []).length > 0 && (
        <Accordion title={`Schema 연결성(@id) — ${axis3.id_pct ?? "—"}%${axis3.gate === 0 ? " · 🔴 연결 끊김" : ""}`}>
          {(axis3.checks || []).map((ck: any, i: number) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 0", borderTop: "1px solid var(--line)" }}>
              <span>{ck.item.replace(" ★게이트", "")}</span>
              <span style={{ color: "var(--sec)" }}>{ck.score === null ? "해당없음" : `${Math.round(ck.score * 100)}%`} · {ck.detail}</span>
            </div>
          ))}
        </Accordion>
      )}
    </div>
  );
}

function OverallBanner({ hq }: { hq: any }) {
  const l1 = hq.level1_apply_rate || {};
  const perType: Record<string, any> = hq.level2?.per_type || {};
  const overall = hq.overall || {};
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <span style={{ fontSize: 18 }}>{TL_EMOJI[overall.traffic_light] || "⚪"}</span>
      <b style={{ fontSize: 13.5 }}>종합 판단</b>
      <span style={{ fontSize: 11.5, color: "var(--sec)" }}>
        데이터 유무 {l1.apply_rate_pct ?? "—"}% · 퀄리티 {overall.final_pct ?? "—"}%
      </span>
      <span style={{ marginLeft: "auto", display: "flex", gap: 6, flexWrap: "wrap" }}>
        {Object.entries(perType).map(([t, v]: [string, any]) => (
          <span key={t} style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 9px",
            background: (TL_COLOR[v.traffic_light] || "#98A2B3") + "1A", color: TL_COLOR[v.traffic_light] || "#98A2B3" }}>
            {TL_EMOJI[v.traffic_light]} {t} {v.final_pct ?? "—"}%
          </span>
        ))}
      </span>
    </div>
  );
}

// ctx.results 안의 각 행에 html_qa가 들어있으면(일괄검수/이력 포함 전부 공통) 그걸 그대로 씀.
// 단일검수(1건)면 상세 4개 아코디언을 바로 펼치고, 다건(일괄검수)이면 전체 집계 배너 +
// 사이트별 신호등 리스트(최악 사이트 먼저) → 클릭하면 그 사이트의 4개 아코디언이 펼쳐짐.
export function HtmlQaSummary({ ctx: c }: { ctx: any }) {
  if (c.tab !== "schema") return null;
  const rowsWithQa: any[] = (c.results || []).filter((r: any) => r.html_qa);
  if (rowsWithQa.length === 0) return null;

  if (rowsWithQa.length === 1) {
    const hq = rowsWithQa[0].html_qa;
    const findings = rowsWithQa[0].schema?.findings || [];
    return (
      <div className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
        <OverallBanner hq={hq} />
        <HtmlQaDetail hq={hq} findings={findings} />
      </div>
    );
  }

  // 일괄검수 — 집계 + 사이트별 드릴다운
  const finals = rowsWithQa.map((r) => r.html_qa.overall?.final_pct).filter((v: any) => v != null) as number[];
  const avg = finals.length ? Math.round((finals.reduce((a, b) => a + b, 0) / finals.length) * 10) / 10 : null;
  const dist = { green: 0, yellow: 0, red: 0 } as Record<string, number>;
  for (const r of rowsWithQa) dist[r.html_qa.overall?.traffic_light || "red"]++;
  const sorted = [...rowsWithQa].sort((a, b) => (a.html_qa.overall?.final_pct ?? -1) - (b.html_qa.overall?.final_pct ?? -1));
  const applyVals = rowsWithQa.map((r) => r.html_qa.level1_apply_rate?.apply_rate_pct).filter((v: any) => v != null) as number[];
  const avgApply = applyVals.length ? Math.round((applyVals.reduce((a, b) => a + b, 0) / applyVals.length) * 10) / 10 : null;
  const expanded = c.qaExpandedSite;

  return (
    <div className="card qbiPopIn" style={{ marginTop: 16, padding: 14 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <b style={{ fontSize: 13.5 }}>DATA QA 종합</b>
        <span style={{ fontSize: 11.5, color: "var(--sec)" }}>{rowsWithQa.length}개 사이트 · 데이터 유무 {avgApply ?? "—"}% · 퀄리티 {avg ?? "—"}%</span>
        <span style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
          <span style={{ fontSize: 12 }}>🟢 {dist.green}</span>
          <span style={{ fontSize: 12 }}>🟡 {dist.yellow}</span>
          <span style={{ fontSize: 12 }}>🔴 {dist.red}</span>
        </span>
      </div>
      <div style={{ marginTop: 10 }}>
        {sorted.map((r, i) => {
          const hq = r.html_qa; const tl = hq.overall?.traffic_light;
          const key = r.sitecode + i;
          return (
            <div key={key} style={{ borderTop: "1px solid var(--line)" }}>
              <div onClick={() => c.setQaExpandedSite(expanded === key ? null : key)}
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 4px", cursor: "pointer", fontSize: 12.5 }}>
                <span>{TL_EMOJI[tl] || "⚪"}</span>
                <b>{r.sitecode}</b>
                <span style={{ color: "var(--sec)" }}>{r.region} · {r.country}</span>
                <span style={{ marginLeft: "auto" }}>AEO {hq.overall?.final_pct ?? "—"}% · 적용율 {hq.level1_apply_rate?.apply_rate_pct ?? "—"}%</span>
                <span style={{ fontSize: 11, color: "#0A66E0" }}>{expanded === key ? "▲" : "▼"}</span>
              </div>
              {expanded === key && <div className="qbiPopIn" style={{ padding: "0 4px 10px" }}><HtmlQaDetail hq={hq} findings={r.schema?.findings || []} /></div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── 전사이트 현황판 [신규] ────────────────────────────────────────
// 최상단. 이력에서 '각 권역의 가장 최근 검수'를 모아 AEO 점수를 평균낸 전사이트 스냅샷.
// 기본은 전체 점수만 한 줄로. '권역별 점수 ▸' 누르면 권역 칩이 펼쳐짐.
export function SiteOverview({ ctx: c }: { ctx: any }) {
  const [open, setOpen] = useState(false);
  if (c.tab !== "schema") return null;
  const ov = c.overview;
  if (!ov || !ov.regions || ov.regions.length === 0) return null;
  const tl = (a: number | null) => (a == null ? "red" : a >= 80 ? "green" : a >= 50 ? "yellow" : "red");
  const total = ov.total_avg_aeo;
  const dist = ov.distribution || { green: 0, yellow: 0, red: 0 };

  return (
    <div className="summaryCard" style={{ marginTop: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "var(--sec)", fontWeight: 700 }}>전사이트 현황</span>
        <span style={{ display: "inline-flex", alignItems: "baseline", gap: 5 }}>
          <b style={{ fontSize: 26, color: TL_COLOR[tl(total)] }}>{total ?? "—"}</b>
          <span style={{ fontSize: 12, color: "var(--sec)" }}>점 · 평균 AEO 퀄리티</span>
        </span>
        <span style={{ fontSize: 12, color: "var(--sec)" }}>🟢 {dist.green} · 🟡 {dist.yellow} · 🔴 {dist.red}</span>
        <button onClick={() => setOpen((v) => !v)}
          style={{ marginLeft: "auto", background: "none", border: "1px solid var(--line)", borderRadius: 8, padding: "4px 10px", fontSize: 12, cursor: "pointer", color: "var(--label)" }}>
          권역별 점수 {open ? "▾" : "▸"}
        </button>
      </div>
      {open && (
        <div className="qbiPopIn" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          {ov.regions.map((r: any) => (
            <span key={r.region} title={r.at}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
                border: "1px solid var(--line)", borderRadius: 999, padding: "4px 11px" }}>
              <span style={{ color: "var(--sec)" }}>{r.region}</span>
              <b style={{ color: TL_COLOR[tl(r.avg_aeo)] }}>{r.avg_aeo ?? "—"}</b>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
