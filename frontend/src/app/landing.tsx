"use client";

/* ════════════════════════════════════════════════════
   홈 랜딩 — 진입점 2개: 🍎 Apple Stalker / 🐝 큐비(QA Bee)
════════════════════════════════════════════════════ */
export function Landing({ onEnterApple, onEnterQubi, onEnterCombi }: { onEnterApple: () => void; onEnterQubi: () => void; onEnterCombi?: () => void }) {
  return (
    <div className="landingShell">
      <div className="landingInner">
        <h1 className="landingTitle" style={{ marginBottom: 6 }}>어떤 도구를 여시겠어요?</h1>
        <p className="landingSub">경쟁사 모니터링과 닷컴 QA — 두 도구를 한 곳에서.</p>

        <div className="landingCardGrid">
          <div className="landingCard" style={{ display: "flex", flexDirection: "column" }}>
            <span className="landingLogo" style={{ fontSize: 40 }}>🍎</span>
            <p className="landingCardTitle" style={{ marginTop: 6, lineHeight: 1.25 }}>
              <span style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "var(--sec)" }}>경쟁사 추적</span>
              <span style={{ fontSize: 22, fontWeight: 800 }}>Apple Stalker</span>
            </p>
            <ul className="landingFactList" style={{ flex: 1 }}>
              <li>경쟁사 닷컴 <b>변화 감지</b> — Samsung + Apple/Pixel/Xiaomi/OPPO/Sony/Dell 등</li>
              <li>데이터·스키마 / 카피 / 프로모션 / 비주얼 <b>3축 분석</b></li>
              <li>변경점 · 현황 비교 · 리포트(PPTX/Excel/메일)</li>
            </ul>
            <button className="landingCTA" style={{ marginTop: 12 }} onClick={onEnterApple}>🍎 애플스토커 깨우기</button>
          </div>

          <div className="landingCard" style={{ display: "flex", flexDirection: "column" }}>
            <span className="landingLogo" style={{ fontSize: 40 }}>🐝</span>
            <p className="landingCardTitle" style={{ marginTop: 6, lineHeight: 1.25 }}>
              <span style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "var(--sec)" }}>QA의 사촌</span>
              <span style={{ fontSize: 22, fontWeight: 800 }}>큐비</span>
            </p>
            <ul className="landingFactList" style={{ flex: 1 }}>
              <li>삼성닷컴 제품 페이지를 <b>붕붕 돌며 QA</b> — 91개 사이트</li>
              <li><b>스키마 QA</b> — JSON-LD 속성·값을 스펙과 대조</li>
              <li><b>스펙 QA</b> — 스펙 값·고유명사 정확성(번역 대응)</li>
            </ul>
            <button className="landingCTA" style={{ marginTop: 12, background: "#E0A008" }} onClick={onEnterQubi}>🐝 큐비 부르기</button>
          </div>

          <div className="landingCard" style={{ display: "flex", flexDirection: "column" }}>
            <span className="landingLogo" style={{ fontSize: 40 }}>🍯</span>
            <p className="landingCardTitle" style={{ marginTop: 6, lineHeight: 1.25 }}>
              <span style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "var(--sec)" }}>Shopping의 사촌</span>
              <span style={{ fontSize: 22, fontWeight: 800 }}>Combi</span>
            </p>
            <ul className="landingFactList" style={{ flex: 1 }}>
              <li>구글쇼핑 Organic Shelf <b>위치 추적</b> — Row·Column·Above Fold</li>
              <li>Merchant Feed <b>Coverage 분석</b> — Present/Missing/Unknown</li>
              <li>경쟁사 대비 부족한 Feed로 <b>Opportunity 자동 계산</b></li>
            </ul>
            <button className="landingCTA" style={{ marginTop: 12, background: "#B8860B" }} onClick={onEnterCombi}>🍯 Combi 깨우기</button>
          </div>
        </div>
      </div>
    </div>
  );
}
