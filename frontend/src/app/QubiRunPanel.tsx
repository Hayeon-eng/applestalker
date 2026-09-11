"use client";
import { HONEY, sel } from "./qubiShared";

/* QubiRunPanel — QubiApp에서 분리된 "① 리전별 검수 크롤" 카드.
   [2026-07 분할] QubiApp.tsx 46KB 제한 대응. JSX 본문은 원본 그대로이며,
   참조하던 상태/핸들러를 동일 이름 props로 받는다(동작 변경 없음).
   과제3(Data/Spec 독립 실행 버튼)도 이 컴포넌트 안에 포함된다. */
export function QubiRunPanel(props: any) {
  const { apiBase, allSites, busy, estimate, fmtEta, liveEtaSeconds, pageCount, progress, regionNames, regionsMap, runByRegion, selectedRegions, selectedSites, setSelectedRegions, setSelectedSites, tab, targetCodes, isUnlaunched, launchStatus, results } = props;
  // [2026-07 신규] 방금 크롤에서 "(collection failed)" 진단이 붙은 페이지들의 sitecode만 모음
  // — 차단/타임아웃 등으로 수집 자체가 실패한 경우만 대상, QA 판정상의 fail(스펙/스키마 불일치)은 제외.
  const failedSitecodes: string[] = Array.from(new Set(
    (results || [])
      .filter((r: any) => (r.schema?.findings || []).some((f: any) => f.block === "(collection failed)"))
      .map((r: any) => r.sitecode)
      .filter(Boolean)
  ));
  // [2026-07 신규] '미출시 있음' 배지를 제품 필터에서 이 드로어로 이동 — 현재 선택된 제품(product) 기준
  // 미출시 사이트만 모아 좌측 URL 대상(사이트 개별 선택) 바로 아래 접힌 상태로 노출.
  const unlaunchedSites: any[] = (allSites || []).filter((s: any) => isUnlaunched?.(s.sitecode));
  // [2026-07 신규] launch_status(출시관리 표)엔 이름이 있지만 실제 크롤 URL이 하나도 등록 안 된 나라들.
  // URL을 임의로 지어내지 않기로 했으므로 크롤 대상엔 못 넣지만, "미출시로 관리는 되고 있다"는 사실은
  // 이 드로어에 같이 보여준다 — 실제 사이트와 헷갈리지 않게 별도 그룹(URL 미등록)으로 구분.
  const registeredCodes = new Set((allSites || []).map((s: any) => s.sitecode));
  const unregisteredLaunchCodes: string[] = Object.keys(launchStatus || {}).filter((c) => !registeredCodes.has(c)).sort();
  return (
          <div className="card" style={{ marginTop: 12, padding: 14 }}>
            <b style={{ fontSize: 14 }}>① 리전별 검수 크롤</b>
            <span style={{ fontSize: 12, color: "var(--sec)", marginLeft: 8 }}>권역/사이트를 선택해 크롤 (아무것도 안 고르면 전체)</span>

            {/* 권역 다중선택 */}
            <div style={{ fontSize: 11.5, color: "var(--sec)", margin: "10px 0 4px" }}>권역 (여러 개 선택 가능)</div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
              {regionNames.map((rg) => {
                const on = selectedRegions.has(rg);
                return (
                  <button key={rg} onClick={() => { setSelectedSites(new Set()); setSelectedRegions((prev) => { const n = new Set(prev); n.has(rg) ? n.delete(rg) : n.add(rg); return n; }); }}
                    style={sel(rg, on)}>{on ? "✓ " : ""}{rg} {regionsMap[rg]?.length || 0}</button>
                );
              })}
              {(selectedRegions.size > 0 || selectedSites.size > 0) &&
                <button onClick={() => { setSelectedRegions(new Set()); setSelectedSites(new Set()); }} style={{ fontSize: 11.5, color: "var(--sec)", background: "none", border: "none", cursor: "pointer" }}>선택 해제</button>}
            </div>

            {/* 사이트 개별 체크박스(접이식) */}
            <details style={{ marginBottom: 8 }}>
              <summary style={{ fontSize: 11.5, color: "#0A66E0", cursor: "pointer" }}>사이트 개별 선택 {selectedSites.size > 0 ? `(${selectedSites.size}개 선택됨)` : ""}</summary>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, maxHeight: 180, overflowY: "auto" }}>
                {allSites.map((s, i) => {
                  const on = selectedSites.has(s.sitecode);
                  return (
                    <label key={s.sitecode + i} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11.5, border: "1px solid var(--line)", borderRadius: 6, padding: "3px 8px", cursor: "pointer", background: on ? "#E8F0FE" : "#fff" }}>
                      <input type="checkbox" checked={on} onChange={() => { setSelectedRegions(new Set()); setSelectedSites((prev) => { const n = new Set(prev); n.has(s.sitecode) ? n.delete(s.sitecode) : n.add(s.sitecode); return n; }); }} />
                      {s.sitecode}<span style={{ color: "var(--sec)" }}>{s.region}</span>
                      {isUnlaunched?.(s.sitecode) && <span style={{ color: "#B54708", fontWeight: 600 }}>미출시</span>}
                    </label>
                  );
                })}
              </div>
            </details>

            {/* [2026-07 신규] 미출시 사이트 — 좌측 URL 대상(사이트 개별 선택) 바로 아래, 기본은 접힌 상태.
                제품 필터 배지 대신 여기서 한 곳에 모아 확인. */}
            {(unlaunchedSites.length > 0 || unregisteredLaunchCodes.length > 0) && (
              <details style={{ marginBottom: 8 }}>
                <summary style={{ fontSize: 11.5, color: "#B54708", cursor: "pointer" }}>
                  🚫 미출시 사이트 ({unlaunchedSites.length + unregisteredLaunchCodes.length}개)
                </summary>
                {unlaunchedSites.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, maxHeight: 180, overflowY: "auto" }}>
                    {unlaunchedSites.map((s, i) => (
                      <span key={s.sitecode + i} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11.5, border: "1px solid #FEDF89", background: "#FFFAEB", borderRadius: 6, padding: "3px 8px" }}>
                        {s.sitecode}<span style={{ color: "var(--sec)" }}>{s.region}</span>
                      </span>
                    ))}
                  </div>
                )}
                {unregisteredLaunchCodes.length > 0 && (
                  <>
                    <div style={{ fontSize: 10.5, color: "var(--sec)", marginTop: unlaunchedSites.length > 0 ? 8 : 8 }}>
                      URL 미등록 — 출시관리 표엔 있지만 크롤 대상 URL이 없어 검수엔 포함되지 않음
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6, maxHeight: 180, overflowY: "auto" }}>
                      {unregisteredLaunchCodes.map((c) => (
                        <span key={c} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11.5, border: "1px dashed #D0D5DD", background: "#F9FAFB", color: "var(--sec)", borderRadius: 6, padding: "3px 8px" }}>
                          {c}<span style={{ fontSize: 10 }}>URL 미등록</span>
                        </span>
                      ))}
                    </div>
                  </>
                )}
              </details>
            )}

            {/* [2026-07 재정렬] 기본 동작은 다시 Data+Spec 동시 검수 — 누르면 확인 팝업.
                과제3(탭별 독립 실행)은 필요할 때만 쓰는 보조 버튼으로 내림. */}
            {/* [2026-09-11] 기본 = 현재 탭만 실행(쨍한 색). 둘을 함께 돌리는 건 회색 보조 버튼. 실행 중엔 멈춤 버튼. */}
            {!busy ? (<>
              <button
                onClick={() => {
                  const label = tab === "schema" ? "Data QA" : "Spec QA";
                  if (window.confirm(`${label} 검수를 시작할까요? · ${targetCodes.length}개 사이트${selectedSites.size ? " (선택)" : selectedRegions.size ? " (권역)" : " (전체)"}`)) {
                    runByRegion(tab === "schema" ? "data" : "spec");
                  }
                }}
                style={{ padding: "8px 14px", borderRadius: 8, border: "none", background: tab === "schema" ? "#1B4FD8" : HONEY, color: "#fff", fontWeight: 700, cursor: "pointer" }}>
                {tab === "schema" ? "▶ Data QA 검수 실행" : "▶ Spec QA 검수 실행"} · {targetCodes.length}개 사이트{selectedSites.size ? " (선택)" : selectedRegions.size ? " (권역)" : " (전체)"}
              </button>
              <button
                onClick={() => { if (window.confirm(`Data QA + Spec QA 를 함께 검수할까요? (시간이 더 걸립니다)`)) runByRegion("all"); }}
                title="두 축을 한 번에 — 시간이 더 걸림"
                style={{ padding: "8px 12px", marginLeft: 8, borderRadius: 8, border: "1px solid var(--line)", background: "#F3F4F6", color: "var(--sec)", fontWeight: 600, cursor: "pointer" }}>
                Data + Spec 함께
              </button>
            </>) : (
              <button
                onClick={async () => { if (window.confirm("검수를 멈출까요? 끝난 페이지까지는 결과로 저장됩니다.")) { await fetch(`${props.apiBase || ""}/api/qb/run-cancel`, { method: "POST" }); } }}
                style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #B42318", background: "#fff", color: "#B42318", fontWeight: 700, cursor: "pointer" }}>
                ■ 멈춤 {progress.active ? `(${progress.done}/${progress.total})` : ""}
              </button>
            )}
            {selectedSites.size === 0 && selectedRegions.size === 0 && pageCount > 0 && !busy && (
              <span style={{ fontSize: 11.5, color: "var(--sec)", marginLeft: 8 }}>사이트당 여러 페이지(PDP·Compare·Buds 등) — 총 {pageCount}개 페이지 검수</span>
            )}
            {!busy && estimate && estimate.totalPages > 0 && (
              <span style={{ fontSize: 11.5, color: "var(--sec)", marginLeft: 8 }}>
                ⏱ 예상 소요시간 약 {fmtEta(estimate.estimatedSeconds)}
                {estimate.sampleRuns > 0 ? ` (최근 ${estimate.sampleRuns}회 이력 기준)` : " (이력 없음 — 참고용 기본치)"}
              </span>
            )}
            {!busy && failedSitecodes.length > 0 && (
              <div style={{ marginTop: 10, padding: "8px 10px", background: "#FEF3F2", border: "1px solid #FDA29B", borderRadius: 8 }}>
                <span style={{ fontSize: 12, color: "#B42318" }}>❗ 수집 실패 {failedSitecodes.length}개 사이트: {failedSitecodes.slice(0, 8).join(", ")}{failedSitecodes.length > 8 ? ` 외 ${failedSitecodes.length - 8}개` : ""}</span>
                <button
                  onClick={() => {
                    if (window.confirm(`수집 실패한 ${failedSitecodes.length}개 사이트만 재시도할까요? (동시성 낮춰서 재시도하는 걸 권장 — QB_BROWSER_CONCURRENCY 값 확인)`)) {
                      setSelectedRegions(new Set());
                      setSelectedSites(new Set(failedSitecodes));
                      runByRegion("all", failedSitecodes);
                    }
                  }}
                  style={{ marginLeft: 10, padding: "4px 10px", borderRadius: 6, border: "1px solid #B42318", background: "#fff", color: "#B42318", fontWeight: 600, fontSize: 11.5, cursor: "pointer" }}>
                  🔄 실패한 사이트만 재시도
                </button>
              </div>
            )}
            {progress.active && (
              <div style={{ marginTop: 10 }}>
                <div style={{ height: 8, background: "#F0F1F3", borderRadius: 999, overflow: "hidden" }}><div style={{ height: "100%", width: `${progress.total ? (progress.done / progress.total) * 100 : 0}%`, background: tab === "schema" ? "#1B4FD8" : HONEY, transition: "width .3s" }} /></div>
                <div style={{ fontSize: 11.5, color: "var(--sec)", marginTop: 4 }}>
                  🐝 {progress.label} · {progress.done}/{progress.total} 페이지
                  {liveEtaSeconds != null && ` · 남은 시간 약 ${fmtEta(liveEtaSeconds)}`}
                </div>
              </div>
            )}
          </div>
  );
}
