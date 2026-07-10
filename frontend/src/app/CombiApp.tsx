"use client";
/**
 * CombiApp.tsx — Combi 🍯 (Google Shopping Organic Shelf Intelligence) 스켈레톤
 *
 * [SKELETON] 백엔드 rule_engine.py가 STUB(결정적 mock)을 반환하는 단계.
 * Prompt Library(10개 test) 선택 → 실행 → Shelf/Coverage/Gap 결과를 조회하는
 * 전체 파이프라인 배선만 먼저 잡고, 실제 크롤러가 붙으면 이 화면은 그대로 두고
 * 백엔드 계산 로직만 교체하면 된다.
 */
import { useEffect, useState } from "react";

type Prompt = {
  id: string;
  text: string;
  category: string;
  intent: string;
  priority: string;
  language: string;
  country_scope: string[];
  branded: boolean;
  active: boolean;
};

type RunSummary = {
  combi_run_id: string;
  prompt_id: string;
  prompt_text: string;
  category: string;
  country: string;
  samsung_rank: number | null;
  samsung_above_fold: boolean;
  gap_count: number;
  created_at: string | null;
};

type ShelfRow = {
  rank: number; row: number; column: number; above_fold: boolean;
  merchant: string; is_samsung: boolean; price: number; rating: number; review_count: number;
};

type RunDetail = {
  combi_run_id: string;
  prompt_text: string;
  category: string;
  country: string;
  shelf: ShelfRow[];
  coverage: Record<string, string>;
  gaps: { attribute: string; competitor: string; samsung_status: string; opportunity: string }[];
  created_at: string | null;
};

export default function CombiApp({ apiBase = "", onHome }: { apiBase?: string; onHome?: () => void }) {
  const API = apiBase || (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
  const [online, setOnline] = useState<boolean | null>(null);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [country, setCountry] = useState("US");
  const [running, setRunning] = useState(false);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [tab, setTab] = useState<"shelf" | "coverage" | "gaps">("shelf");
  const [loadingDetail, setLoadingDetail] = useState(false);

  const load = async () => {
    try {
      const h = await fetch(API + "/api/combi/health", { cache: "no-store" });
      setOnline(h.ok);
      const [rP, rR] = await Promise.all([
        fetch(API + "/api/combi/prompts", { cache: "no-store" }),
        fetch(API + "/api/combi/runs", { cache: "no-store" }),
      ]);
      setPrompts((await rP.json()).prompts || []);
      setRuns((await rR.json()).runs || []);
    } catch {
      setOnline(false);
    }
  };

  useEffect(() => { load(); }, []);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const runSelected = async () => {
    if (selected.size === 0) return;
    setRunning(true);
    try {
      const res = await fetch(API + "/api/combi/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt_ids: Array.from(selected), countries: [country] }),
      });
      if (res.ok) {
        await load();
      }
    } finally {
      setRunning(false);
    }
  };

  const openRun = async (runId: string) => {
    setLoadingDetail(true);
    setTab("shelf");
    try {
      const res = await fetch(API + "/api/combi/runs/" + runId, { cache: "no-store" });
      setDetail(await res.json());
    } finally {
      setLoadingDetail(false);
    }
  };

  return (
    <div className="appShell">
      {/* ── 사이드바 ── */}
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🍯 Combi</div>
        <div className="brandSub">Shopping의 사촌, Combi — 구글쇼핑을 붕붕 돌며 Sweet Spot을 찾아요</div>
        <div className={`connBadge ${online === true ? "ok" : "bad"}`}>
          <span className="connDot" />
          {online === null ? "확인 중" : online ? "백엔드 연결됨" : "연결 안 됨"}
        </div>

        <div className="sideScroll">
          <div className="sideLabel">국가</div>
          <div style={{ padding: "0 10px 10px" }}>
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              style={{ width: "100%", padding: "7px 8px", borderRadius: 8, border: "1px solid var(--line)", fontSize: 12.5 }}
            >
              {["US", "UK", "DE", "AU", "IN", "SG"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div className="sideLabel">Prompt Library (test {prompts.length}개)</div>
          <div style={{ padding: "0 10px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
            {prompts.map((p) => (
              <label key={p.id} style={{ display: "flex", alignItems: "flex-start", gap: 6, fontSize: 12, cursor: "pointer" }}>
                <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggle(p.id)} style={{ marginTop: 2 }} />
                <span>
                  <span style={{ fontWeight: 600 }}>{p.text}</span>
                  <span style={{ display: "block", color: "var(--sec)", fontSize: 10.5 }}>{p.category} · {p.priority}</span>
                </span>
              </label>
            ))}
          </div>

          <div style={{ padding: "0 10px 14px" }}>
            <button
              className="btnPrimary"
              style={{ width: "100%", background: "#B8860B" }}
              disabled={selected.size === 0 || running}
              onClick={runSelected}
            >
              {running ? "실행 중…" : `🍯 선택 ${selected.size}개 실행`}
            </button>
          </div>
        </div>
      </aside>

      {/* ── 본문 ── */}
      <div className="mainArea">
        <div className="contentScroll">
          <div className="panelStack">
            <div className="card">
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>최근 실행</div>
              {runs.length === 0 && (
                <div style={{ fontSize: 12.5, color: "var(--sec)" }}>
                  아직 실행 기록이 없어요. 왼쪽에서 Prompt를 고르고 실행해보세요.
                  <div style={{ marginTop: 6, fontSize: 11, color: "var(--ter, var(--sec))" }}>
                    ※ 지금은 rule_engine이 STUB(결정적 mock) 값을 반환합니다 — 실제 크롤러 연결 전 배선 검증용.
                  </div>
                </div>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {runs.map((r) => (
                  <button
                    key={r.combi_run_id}
                    onClick={() => openRun(r.combi_run_id)}
                    className="changeCard"
                    style={{ textAlign: "left" }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                      <span style={{ fontSize: 12.5, fontWeight: 600 }}>{r.prompt_text}</span>
                      <span className="badge c6">{r.country}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--sec)", marginTop: 3 }}>
                      {r.category} · Samsung {r.samsung_rank ? `#${r.samsung_rank}위` : "미노출"}
                      {r.samsung_above_fold ? " · Above Fold" : ""} · Gap {r.gap_count}건
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {detail && (
              <div className="card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{detail.prompt_text} <span style={{ color: "var(--sec)", fontWeight: 500 }}>· {detail.country}</span></div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {(["shelf", "coverage", "gaps"] as const).map((t) => (
                      <button key={t} className={`tabBtn ${tab === t ? "on" : ""}`} onClick={() => setTab(t)}>
                        {t === "shelf" ? "Shelf Tracker" : t === "coverage" ? "Coverage" : "Gap Finder"}
                      </button>
                    ))}
                  </div>
                </div>

                {loadingDetail && <div style={{ fontSize: 12.5, color: "var(--sec)" }}>불러오는 중…</div>}

                {!loadingDetail && tab === "shelf" && (
                  <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ color: "var(--sec)", textAlign: "left" }}>
                        <th style={{ padding: "4px 6px" }}>Rank</th>
                        <th>Row/Col</th>
                        <th>Above Fold</th>
                        <th>Merchant</th>
                        <th>Price</th>
                        <th>Rating</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.shelf.map((s) => (
                        <tr key={s.rank} style={{ borderTop: "1px solid var(--line)", background: s.is_samsung ? "var(--blue-soft)" : "transparent" }}>
                          <td style={{ padding: "6px" }}>#{s.rank}</td>
                          <td>{s.row}행 {s.column}열</td>
                          <td>{s.above_fold ? "✓" : "—"}</td>
                          <td style={{ fontWeight: s.is_samsung ? 700 : 400 }}>{s.merchant}</td>
                          <td>${s.price}</td>
                          <td>★{s.rating} ({s.review_count})</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {!loadingDetail && tab === "coverage" && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {Object.entries(detail.coverage).map(([attr, status]) => (
                      <span key={attr} className={`badge ${status === "present" ? "good" : status === "missing" ? "bad" : "mid"}`}>
                        {attr}: {status}
                      </span>
                    ))}
                  </div>
                )}

                {!loadingDetail && tab === "gaps" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {detail.gaps.length === 0 && <div style={{ fontSize: 12.5, color: "var(--sec)" }}>Gap 없음.</div>}
                    {detail.gaps.map((g, i) => (
                      <div key={i} style={{ fontSize: 12.5, borderBottom: "1px solid var(--line)", paddingBottom: 6 }}>
                        {g.opportunity}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
