"use client";

/* ════════════════════════════════════════════════════
   홈 랜딩 — 진입점 3개: 🍎 Apple Stalker / 🐝 큐비(QA Bee) / 🐝C honeyComb  (ABC Tool)
════════════════════════════════════════════════════ */
export function Landing({ onEnterApple, onEnterQubi, onEnterHoneyComb }: { onEnterApple: () => void; onEnterQubi: () => void; onEnterHoneyComb?: () => void }) {
  return (
    <div className="landingShell">
      <div className="landingInner">
        <h1 className="landingTitle" style={{ marginBottom: 6 }}>어떤 도구를 여시겠어요?</h1>
        <p className="landingSub">🍎 무엇이 바뀌었나 · 🐝 맞게 올라갔나 · 🐝C AI/소비자에게 뜨는가 — ABC 세 도구를 한 곳에서.</p>

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

          {/* [2026-09] C · honeyComb — Google Shopping 노출 순위 · GMC 속성 역추적 (목업 단계) */}
          <div className="landingCard" style={{ display: "flex", flexDirection: "column" }}>
            <span className="landingLogo" style={{ fontSize: 40 }}>🍯</span>
            <p className="landingCardTitle" style={{ marginTop: 6, lineHeight: 1.25 }}>
              <span style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "var(--sec)" }}>검색창의 벌집</span>
              <span style={{ fontSize: 22, fontWeight: 800 }}>honey<span style={{ color: "#E8A317" }}>C</span>omb</span>
            </p>
            <ul className="landingFactList" style={{ flex: 1 }}>
              <li>주요 6개국 Google Shopping에서 우리 제품이 <b>1순위(상단 2줄)</b>에 뜨는지</li>
              <li>뜰 때 보이는 <b>GMC 51개 속성</b>을 역추적 — 피드에 넣은 것과 대조</li>
              <li>1위를 차지하는 Shop(Amazon·Shopee…)과 주차별 변화</li>
            </ul>
            <button className="landingCTA" style={{ marginTop: 12, background: "#8A5A00" }} onClick={onEnterHoneyComb}>🍯 벌집 열기</button>
          </div>

        </div>
      </div>
    </div>
  );
}
