"use client";

/* QubiSidebar — QubiApp에서 분리된 좌측 사이드바(URL 관리·검수 이력).
   [2026-07 분할] QubiApp.tsx 46KB 제한 대응. JSX 본문은 원본 그대로이며,
   참조하던 상태/핸들러를 동일 이름 props로 받는다(동작 변경 없음). */
export function QubiSidebar(props: any) {
  const { onHome, online, downloadTemplate, uploadTemplate, xlsxFileRef, sitesOpen, setSitesOpen, entries, removeUrl, history, openHistory, removeHistory } = props;
  return (
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🐝 큐비</div>
        <div className="brandSub">QA의 사촌, 큐비 — 닷컴을 붕붕 돌며 스펙을 지켜요</div>
        <div className={`connBadge ${online === true ? "ok" : "bad"}`}><span className="connDot" />{online === null ? "확인 중" : online ? "백엔드 연결됨" : "연결 안 됨"}</div>

        <div className="sideScroll">
          <div className="sideLabel">URL 관리</div>
          {/* [2026-07] 개별 URL 추가 UI 제거 — site_registry.part*.json 갱신으로 일원화 */}
          <div style={{ padding: "0 10px 8px", display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button onClick={downloadTemplate} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }}>⬇ URL 템플릿</button>
            <button onClick={() => xlsxFileRef.current?.click()} className="btnSecondary" style={{ fontSize: 11.5, padding: "5px 8px" }}>⬆ 템플릿 업로드</button>
            <input ref={xlsxFileRef} type="file" accept=".xlsx" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadTemplate(f); e.currentTarget.value = ""; }} />
          </div>
          <div className="sideLabel" style={{ cursor: "pointer" }} onClick={() => setSitesOpen((o) => !o)}>{sitesOpen ? "▾" : "▸"} 모니터링 URL 목록 <span style={{ color: "var(--sec)" }}>{entries.length}개</span></div>
          {sitesOpen && entries.map((s, i) => (
            <div key={`${s.sitecode}-${i}`} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 10px", fontSize: 11.5 }}>
              <span title={s.url}>
                <span style={{ fontWeight: 600 }}>{s.sitecode}</span>
                {s.product && <span style={{ fontSize: 10, background: "#EEF1F6", color: "#475467", borderRadius: 4, padding: "1px 5px", marginLeft: 5 }}>{s.product}{s.page_type ? ` · ${s.page_type}` : ""}</span>}
                {s.country && <span style={{ color: "var(--sec)", marginLeft: 5 }}>{s.country}</span>}
              </span>
              <span role="button" onClick={() => removeUrl(s.sitecode, s.url)} style={{ cursor: "pointer", color: "var(--high)", fontSize: 11 }}>삭제</span>
            </div>
          ))}

          {/* 검수 이력 */}
          <div className="sideLabel" style={{ marginTop: 14 }}>검수 이력 <span style={{ color: "var(--sec)" }}>{history.length}건</span></div>
          {history.length === 0 && <p style={{ padding: "2px 10px", fontSize: 11.5, color: "var(--sec)" }}>아직 저장된 검수가 없어요</p>}
          {history.map((h) => (
            <div key={h.run_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 10px", fontSize: 11.5, cursor: "pointer" }} onClick={() => openHistory(h.run_id)}>
              <span>
                <span style={{ fontWeight: 600 }}>{h.at?.slice(5, 16) || h.run_id}</span>
                <span style={{ color: "var(--sec)" }}> · {h.pages}p</span>
                {h.fail > 0 && <span style={{ color: "var(--high)" }}> · 오류 {h.fail}</span>}
              </span>
              <span role="button" onClick={(e) => { e.stopPropagation(); removeHistory(h.run_id); }} style={{ color: "var(--high)", fontSize: 11 }}>삭제</span>
            </div>
          ))}
        </div>
      </aside>
  );
}
