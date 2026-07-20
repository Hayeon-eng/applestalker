"use client";
import { useState } from "react";
import { MiniDiff } from "./specQaShared";

/* CompareMatrixPanel — Compare 전용 결과 UI.
   row.compare_v2 = { summary, rows: [{category, spec, values:[{product,value,status,message}]}], products }
   (compare_pipeline.run_compare_pipeline()의 반환 형태 그대로 — 백엔드 출력은 변경하지 않음)

   [2026-07 과제2] 표시를 PDP Spec QA(SpecV2Panel)와 동일한 형식으로 정렬한다.
   · 상태 어휘 통일: 🔴 오류 / 🟡 확인 / ✅ 정상 (PDP와 동일)
   · 문제 항목은 PDP처럼 "현재값 → 기준값" MiniDiff로 표시(기준값은 message에서 파싱)
   · 전체 매트릭스 표는 기본 접힘 — 필요할 때만 "전체 표 보기"로 펼침 */

const STATUS_EMOJI: Record<string, string> = {
  pass: "✅", fail: "🔴", warn: "🟡", na: "⚪️", unchecked: "❔",
};
const STATUS_COLOR: Record<string, string> = {
  pass: "#12A150", fail: "#E23434", warn: "#C48A00", na: "#98A2B3", unchecked: "#98A2B3",
};
// PDP Spec QA와 동일한 상태 어휘(오류/확인/정상)
const STATUS_LABEL: Record<string, string> = {
  fail: "오류", warn: "확인", unchecked: "DB 미등록", na: "값 없음",
};

// compare_qa 메시지("오기재 — 정답 'X'이 아닌 'Y' 표기")에서 기준값(정답)만 뽑아
// PDP식 현재값→기준값 diff에 쓴다. 못 뽑으면 null(그땐 메시지 그대로 노출).
function _expectedFromMessage(msg: string): string | null {
  const m = (msg || "").match(/정답\s+'([^']*)'/);
  return m ? m[1] : null;
}

export function CompareMatrixPanel({ row }: { row: any }) {
  const [showTable, setShowTable] = useState(false);
  const cv = row?.compare_v2;
  if (!cv) return null; // Compare 페이지가 아니거나 파이프라인이 스킵된 경우 — 기존 화면에 영향 없음

  const products: string[] = cv.products || [];
  const rows: any[] = cv.rows || [];
  const summary = cv.summary || {};

  if (!summary.checked) {
    return (
      <div className="card qbiPopIn" style={{ marginTop: 10, padding: 12, fontSize: 12, color: "var(--sec)" }}>
        Compare 매트릭스: {summary.reason || "QA 대조 대상 아님(추출 결과만 있음)"}
        {rows.length > 0 && ` · ${rows.length}개 스펙 행 추출됨`}
      </div>
    );
  }

  const perProduct: any[] = summary.per_product || [];
  const siteLabel = row.sitecode || row.country || "";
  const prodLabel = row.market_product || row.product || "";

  // 틀렸거나(fail) 확인 필요(warn)한 셀만 모아 압축 리스트로 — "전체 항목 중 뭐가 틀렸는지"
  const problems: { category: string; spec: string; product: string; value: string; status: string; message: string }[] = [];
  let passCount = 0, naCount = 0, unchCount = 0;
  for (const r of rows) {
    for (const cell of r.values || []) {
      const st = cell.status || "unchecked";
      if (st === "pass") passCount++;
      else if (st === "na") naCount++;
      else if (st === "unchecked") unchCount++;
      if (st === "fail" || st === "warn") {
        problems.push({ category: r.category, spec: r.spec, product: cell.product, value: cell.value, status: st, message: cell.message || "" });
      }
    }
  }
  const unregistered: { category: string; spec: string; products: string[] }[] = [];
  for (const r of rows) {
    const missing = (r.values || []).filter((c: any) => c.status === "unchecked");
    if (missing.length) unregistered.push({ category: r.category, spec: r.spec, products: missing.map((c: any) => c.product) });
  }

  return (
    <div className="card qbiPopIn" style={{ marginTop: 10, padding: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
        <b style={{ fontSize: 13 }}>Compare 결과 요약</b>
        {(siteLabel || prodLabel) && (
          <span style={{ fontSize: 11, color: "var(--sec)", border: "1px solid var(--line)", borderRadius: 6, padding: "2px 8px" }}>
            {siteLabel}{siteLabel && prodLabel ? " · " : ""}{prodLabel}
          </span>
        )}
        {row.url && (
          <a href={row.url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: "#0A66E0" }}>원본 페이지 ↗</a>
        )}
      </div>

      {/* 제품별 점수 배지 — 몇 개 중 몇 개가 맞았는지 한눈에 */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        {perProduct.map((p) => (
          <span key={p.product} style={{ fontSize: 12, border: "1px solid var(--line)", borderRadius: 999,
            padding: "4px 12px", display: "inline-flex", gap: 7, alignItems: "center" }}>
            <b>{p.product}</b>
            <span style={{ color: p.score != null ? (p.score >= 90 ? "#12A150" : p.score >= 70 ? "#C48A00" : "#E23434") : "#98A2B3", fontWeight: 700 }}>
              {p.score != null ? `${p.score}%` : "—"}
            </span>
            <span style={{ color: "var(--sec)" }}>✅{p.pass}·🔴{p.fail}·🟡{p.warn}·❔{p.unchecked}</span>
          </span>
        ))}
      </div>

      {/* 문제 항목 — PDP Spec QA와 동일하게 "🔴 오류 N · 🟡 확인 N · ✅ 정상 N" 요약 + 현재값→기준값 */}
      {problems.length === 0 ? (
        <div style={{ fontSize: 12.5, color: "#12A150", padding: "6px 2px" }}>
          ✅ 정상 {passCount}건 · 오류 없음{unchCount ? ` · DB 미등록 ${unchCount}건` : ""}
        </div>
      ) : (
        <div style={{ marginBottom: 4 }}>
          <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>
            🔴 오류 {problems.filter((p) => p.status === "fail").length} · 🟡 확인 {problems.filter((p) => p.status === "warn").length} · ✅ 정상 {passCount}
            {unchCount ? <span style={{ color: "var(--sec)", fontWeight: 400 }}> · ❔ DB 미등록 {unchCount}</span> : null}
          </div>
          <div style={{ display: "grid", rowGap: 5 }}>
            {problems.map((p, i) => {
              const exp = p.status === "fail" ? _expectedFromMessage(p.message) : null;
              return (
                <div key={i} style={{ fontSize: 12, padding: "6px 8px", borderRadius: 6,
                  background: p.status === "fail" ? "#FEF3F2" : "#FFFAEB" }}>
                  <div>
                    <span style={{ color: STATUS_COLOR[p.status] }}>{STATUS_EMOJI[p.status]}</span>{" "}
                    <b>{p.product}</b> · {p.category ? `${p.category} — ` : ""}{p.spec}
                    <span style={{ color: STATUS_COLOR[p.status], marginLeft: 6, fontSize: 11, fontWeight: 700 }}>[{STATUS_LABEL[p.status]}]</span>
                  </div>
                  {/* PDP SpecV2Panel과 동일한 현재값→기준값 표기 */}
                  <div style={{ marginTop: 3, fontSize: 11.5 }}>
                    {exp
                      ? <MiniDiff expected={exp} actual={p.value} />
                      : <span style={{ color: "var(--sec)" }}>페이지 값 "{p.value}"{p.message ? ` — ${p.message}` : ""}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* DB 미등록 항목 — 오류가 아니라 Rule DB/Dictionary 보완이 필요한 항목 (예: 번역 미등록) */}
      {unregistered.length > 0 && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ fontSize: 11.5, color: "var(--sec)", cursor: "pointer" }}>
            ❔ DB 미등록 항목 {unregistered.length}건 (페이지 오류 아님 — Dictionary/Rule DB 보완 필요)
          </summary>
          <div style={{ display: "grid", rowGap: 3, marginTop: 6 }}>
            {unregistered.map((u, i) => (
              <div key={i} style={{ fontSize: 11.5, color: "var(--sec)", padding: "2px 8px" }}>
                {u.category ? `${u.category} — ` : ""}{u.spec} <span>({u.products.join(", ")})</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* 전체 매트릭스는 기본 접힘 — 필요할 때만 펼침 */}
      <button
        onClick={() => setShowTable((v) => !v)}
        style={{ marginTop: 10, fontSize: 11.5, color: "#0A66E0", background: "none", border: "1px solid var(--line)",
          borderRadius: 6, padding: "4px 10px", cursor: "pointer" }}>
        {showTable ? "전체 표 접기" : `전체 표 보기 (${rows.length}개 항목 × ${products.length}개 제품)`}
      </button>

      {showTable && (
        <div style={{ overflowX: "auto", marginTop: 10 }}>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "2px solid var(--line)" }}>Category</th>
                <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "2px solid var(--line)" }}>Spec</th>
                {products.map((p) => (
                  <th key={p} style={{ textAlign: "left", padding: "6px 8px", borderBottom: "2px solid var(--line)" }}>{p}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--line)" }}>
                  <td style={{ padding: "6px 8px", color: "var(--sec)" }}>{r.category || "—"}</td>
                  <td style={{ padding: "6px 8px", fontWeight: 600 }}>{r.spec}</td>
                  {products.map((p) => {
                    const cell = (r.values || []).find((v: any) => v.product === p);
                    if (!cell) return <td key={p} style={{ padding: "6px 8px", color: "#C7CCD4" }}>—</td>;
                    const st = cell.status || "unchecked";
                    return (
                      <td key={p} style={{ padding: "6px 8px" }} title={cell.message || ""}>
                        <span style={{ color: STATUS_COLOR[st] }}>{STATUS_EMOJI[st]}</span>{" "}
                        <span>{cell.value}</span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
