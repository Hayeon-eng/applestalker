"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

function GateForm() {
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const hasError = params.get("error") === "1";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#F5F6FA",
      }}
    >
      {/* 자바스크립트 없이도(=캐시된 구버전 번들이어도) 동작하도록 순수 HTML 폼 POST 방식 사용 */}
      <form
        method="POST"
        action="/api/gate-auth"
        style={{
          width: 340,
          background: "#fff",
          borderRadius: 14,
          padding: "36px 32px",
          boxShadow: "0 8px 30px rgba(20,40,160,0.10)",
          textAlign: "center",
        }}
      >
        <input type="hidden" name="next" value={next} />
        <div style={{ fontSize: 34, marginBottom: 6 }}>🔒</div>
        <h1 style={{ fontSize: 18, fontWeight: 800, margin: "0 0 4px" }}>비밀번호를 입력하세요</h1>
        <p style={{ fontSize: 12.5, color: "#6B7280", margin: "0 0 20px" }}>
          내부 전용 도구입니다 — 접속 비밀번호가 필요합니다.
        </p>
        <input
          type="password"
          name="password"
          autoFocus
          autoComplete="current-password"
          placeholder="비밀번호"
          style={{
            width: "100%",
            boxSizing: "border-box",
            padding: "11px 12px",
            fontSize: 14,
            border: "1px solid #DDE1EC",
            borderRadius: 8,
            outline: "none",
            marginBottom: 12,
          }}
        />
        {hasError && (
          <p style={{ color: "#D93025", fontSize: 12.5, margin: "0 0 12px" }}>
            비밀번호가 틀렸습니다.
          </p>
        )}
        <button
          type="submit"
          style={{
            width: "100%",
            padding: "11px 0",
            fontSize: 14,
            fontWeight: 700,
            color: "#fff",
            background: "#1428A0",
            border: "none",
            borderRadius: 8,
            cursor: "pointer",
          }}
        >
          입장하기
        </button>
      </form>
    </div>
  );
}

export default function GatePage() {
  return (
    <Suspense fallback={null}>
      <GateForm />
    </Suspense>
  );
}
