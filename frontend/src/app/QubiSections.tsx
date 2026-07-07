"use client";
/* QubiSections.tsx — QubiApp에서 분리한 큰 렌더 블록들(파일 크기 축소용).
   상태/핸들러는 QubiApp에서 ctx 객체로 주입받는다. */
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
    <div ref={c.rulesRef} className="card" style={{ marginTop: 16, padding: 14,
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
          {rules.seo_syntax && (
            <div style={{ borderTop: "2px solid var(--line)", marginTop: 8, paddingTop: 8 }}>
              <b>JSON-LD 문법 오류 기준</b>
              <p style={{ color: "var(--sec)", margin: "2px 0 6px" }}>{rules.seo_syntax["설명"]}</p>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: 220 }}>
                  <div style={{ fontWeight: 700, color: "#0A66E0" }}>Google Rich Result 기준</div>
                  <ul style={{ margin: "4px 0 0 16px", color: "var(--sec)" }}>
                    {(rules.seo_syntax["구글_기준"] || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
                <div style={{ flex: 1, minWidth: 220 }}>
                  <div style={{ fontWeight: 700, color: HONEY }}>우리 기준</div>
                  <ul style={{ margin: "4px 0 0 16px", color: "var(--sec)" }}>
                    {(rules.seo_syntax["우리_기준"] || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
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
                <span style={{ fontSize: 12 }}><span style={{ background: SEV[x.f.status as keyof typeof SEV].c, color: "#fff", fontSize: 10, fontWeight: 700, padding: "1px 5px", borderRadius: 4, marginRight: 5 }}>{SEV[x.f.status as keyof typeof SEV].ko}</span><b>{x.r.sitecode}</b> · {x.item}</span>
                <span style={{ fontSize: 11, color: "#0A66E0" }}>{c.qDetail === key ? "닫기" : "상세"}</span>
              </div>
              {c.qDetail === key && (
                <div style={{ fontSize: 12, marginTop: 4, background: "#F9FAFB", borderRadius: 6, padding: 8 }}>
                  <div style={{ color: "var(--sec)" }}>as-is: {x.f.as_is}</div>
                  <div style={{ fontWeight: 600, marginTop: 2 }}>→ {x.f.to_be}</div>
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
