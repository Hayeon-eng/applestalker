"use client";

/* ════════════════════════════════════════════════════
   홈 랜딩 — 진입점 2개: 🍎 Apple Stalker / 🐝 큐비(QA Bee)
════════════════════════════════════════════════════ */
export function Landing({ onEnterApple, onEnterQubi }: { onEnterApple: () => void; onEnterQubi: () => void }) {
  return (
    <div className="landingShell">
      <div className="landingInner">
        <h1 className="landingTitle" style={{ marginBottom: 6 }}>어떤 도구를 여시겠어요?</h1>
        <p className="landingSub">경쟁사 모니터링과 닷컴 QA — 두 도구를 한 곳에서.</p>

        <div className="landingCardGrid">
          <div className="landingCard" style={{ display: "flex", flexDirection: "column" }}>
            <span className="landingLogo" style={{ fontSize: 40 }}>🍎</span>
            <p className="landingCardTitle" style={{ fontSize: 18, marginTop: 6 }}>Apple Stalker</p>
            <ul className="landingFactList" style={{ flex: 1 }}>
              <li>경쟁사 닷컴 <b>변화 감지</b> — Samsung + Apple/Pixel/Xiaomi/OPPO/Sony/Dell 등</li>
              <li>데이터·스키마 / 카피 / 프로모션 / 비주얼 <b>3축 분석</b></li>
              <li>변경점 · 현황 비교 · 리포트(PPTX/Excel/메일)</li>
            </ul>
            <button className="landingCTA" style={{ marginTop: 12 }} onClick={onEnterApple}>애플스토커 열기</button>
          </div>

          <div className="landingCard" style={{ display: "flex", flexDirection: "column" }}>
            <span className="landingLogo" style={{ fontSize: 40 }}>🐝</span>
            <p className="landingCardTitle" style={{ fontSize: 18, marginTop: 6 }}>큐비 <span style={{ fontWeight: 400, fontSize: 13, color: "var(--muted)" }}>QA Bee</span></p>
            <ul className="landingFactList" style={{ flex: 1 }}>
              <li>삼성닷컴 제품 페이지 <b>QA 검수</b> — 91개 사이트</li>
              <li><b>스키마 QA</b> — JSON-LD를 스펙과 대조</li>
              <li><b>카피 QA</b> — 스펙 값·고유명사 정확성(번역 대응)</li>
            </ul>
            <button className="landingCTA" style={{ marginTop: 12, background: "#E0A008" }} onClick={onEnterQubi}>큐비 열기</button>
          </div>
        </div>
      </div>
    </div>
  );
}
