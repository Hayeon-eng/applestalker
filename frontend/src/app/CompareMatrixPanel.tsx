"use client";
import React from "react";

/* CompareMatrixPanel — Compare 전용 결과 UI.
   PDP UI(SpecV2Panel)를 재사용하지 않고, Spec × Product 매트릭스로 표시한다.
   row.compare_v2 = { summary, rows: [{category, spec, values:[{product,value,status,message}]}], products }
   (compare_pipeline.run_compare_pipeline()의 반환 형태 그대로) */

const STATUS_EMOJI: Record<string, string> = {
  pass: "✅", fail: "🔴", warn: "🟡", na: "⚪️", unchecked: "❔",
};
const STATUS_COLOR: Record<string, string> = {
  pass: "#12A150", fail: "#E23434", warn: "#C48A00", na: "#98A2B3", unchecked: "#98A2B3",
};

export function CompareMatrixPanel({ row }: { row: any }) {
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

  return (
    <div className="card qbiPopIn" style={{ marginTop: 10, padding: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
        <b style={{ fontSize: 13 }}>Compare 매트릭스</b>
        {perProduct.map((p) => (
          <span key={p.product} style={{ fontSize: 11.5, border: "1px solid var(--line)", borderRadius: 999,
            padding: "3px 10px", display: "inline-flex", gap: 6, alignItems: "center" }}>
            <b>{p.product}</b>
            <span style={{ color: p.score != null ? (p.score >= 90 ? "#12A150" : p.score >= 70 ? "#C48A00" : "#E23434") : "#98A2B3" }}>
              {p.score != null ? `${p.score}%` : "—"}
            </span>
            <span style={{ color: "var(--sec)" }}>🔴{p.fail}·🟡{p.warn}·❔{p.unchecked}</span>
          </span>
        ))}
      </div>

      <div style={{ overflowX: "auto" }}>
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
    </div>
  );
}
