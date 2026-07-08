"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";

function GateForm() {
  const params = useSearchParams();
  const next = params.get("next") || "/";

  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!password) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/gate-auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (res.ok) {
        window.location.href = next;
      } else {
        const d = await res.json().catch(() => ({}));
        setError(d?.error || "비밀번호가 틀렸습니다.");
      }
    } catch {
      setError("접속 중 문제가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  }

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
      <form
        onSubmit={submit}
        style={{
          width: 340,
          background: "#fff",
          borderRadius: 14,
          padding: "36px 32px",
          boxShadow: "0 8px 30px rgba(20,40,160,0.10)",
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 34, marginBottom: 6 }}>🔒</div>
        <h1 style={{ fontSize: 18, fontWeight: 800, margin: "0 0 4px" }}>비밀번호를 입력하세요</h1>
        <p style={{ fontSize: 12.5, color: "#6B7280", margin: "0 0 20px" }}>
          내부 전용 도구입니다 — 접속 비밀번호가 필요합니다.
        </p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
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
        {error && (
          <p style={{ color: "#D93025", fontSize: 12.5, margin: "0 0 12px" }}>{error}</p>
        )}
        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%",
            padding: "11px 0",
            fontSize: 14,
            fontWeight: 700,
            color: "#fff",
            background: "#1428A0",
            border: "none",
            borderRadius: 8,
            cursor: loading ? "default" : "pointer",
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? "확인 중..." : "입장하기"}
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
