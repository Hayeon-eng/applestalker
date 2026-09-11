"use client";
import { useRef } from "react";
import { QubiUrlList } from "./QubiUrlList";

/* QubiSidebar — QubiApp에서 분리된 좌측 사이드바(URL 관리·검수 이력).
   [2026-07 분할] QubiApp.tsx 46KB 제한 대응. JSX 본문은 원본 그대로이며,
   참조하던 상태/핸들러를 동일 이름 props로 받는다(동작 변경 없음). */
export function QubiSidebar(props: any) {
  const { onHome, online, apiBase, history, openHistory, removeHistory, onHistoryChanged } = props;
  const histFileRef = useRef<HTMLInputElement>(null);
  return (
      <aside className="sidebar">
        <div className="brand" style={{ cursor: "pointer" }} onClick={onHome} title="홈으로">🐝 큐비</div>
        <div className="brandSub">닷컴을 붕붕 날아다니며, 스키마와 스펙이 제대로 올라갔는지 콕콕 검수해요</div>
        <div className={`connBadge ${online === true ? "ok" : "bad"}`}><span className="connDot" />{online === null ? "확인 중" : online ? "백엔드 연결됨" : "연결 안 됨"}</div>

        <div className="sideScroll">
          {/* [2026-09-11] URL 은 저장소의 site_registry 파일(정적)로 관리 — 화면에서는 보기만. 워치·공통 페이지 URL 은
              GitHub Actions "resolve-urls" 가 삼성 사이트에서 찾아 site_registry.part5.json 으로 커밋한다. */}
          <QubiUrlList apiBase={apiBase} />

          {/* 검수 이력 */}
          <div className="sideLabel" style={{ marginTop: 14 }}>검수 이력 <span style={{ color: "var(--sec)" }}>{history.length}건</span></div>
          {/* [2026-09] 이력 공유 — 공용 DB 대신 JSON 파일로 내보내기/가져오기(사내망 DB 포트 차단 대응) */}
          <div style={{ padding: "0 10px 6px", display: "flex", gap: 6, flexWrap: "wrap" }}>
            <a className="btnSecondary" style={{ fontSize: 11, padding: "4px 8px" }} href={`${apiBase}/api/qb/history/export`} title="최근 이력 전체를 JSON 파일로 저장 — 다른 사람에게 전달">⬇ 이력 내보내기</a>
            <button className="btnSecondary" style={{ fontSize: 11, padding: "4px 8px" }} onClick={() => histFileRef.current?.click()} title="받은 이력 JSON 을 내 화면에 추가">⬆ 이력 가져오기</button>
            <input ref={histFileRef} type="file" accept=".json" hidden onChange={async (e) => {
              const f = e.target.files?.[0]; if (!f) return;
              try { const txt = await f.text(); const r = await (await fetch(`${apiBase}/api/qb/history/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: txt })).json();
                alert(`이력 가져오기: 추가 ${r.added} · 이미 있음 ${r.skipped}`); onHistoryChanged?.(); } catch { alert("가져오기 실패 — 큐비 이력 JSON 인지 확인"); }
              e.currentTarget.value = ""; }} />
          </div>
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
