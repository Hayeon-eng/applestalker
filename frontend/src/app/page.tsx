"use client";
import { useState, useEffect, useCallback, useRef } from "react";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

interface Change {
  id: number;
  url: string;
  site: string;
  level: "High" | "Medium" | "Low";
  category: string;
  field: string;
  summary: string;
  before?: string;
  after?: string;
  evidence?: Record<string, any>;
}
interface Report {
  has_data: boolean;
  run_id?: string;
  site?: string;
  timestamp?: string;
  has_changes?: boolean;
  by_category?: Record<string, number>;
  changes?: Change[];
  category_summary?: Record<string, string>;
  analysis?: { summary: string; aeo_implications: string; insights: any[]; actions: any[] };
  dcv?: { data: Record<string, any>; copy: Record<string, any>; visual: Record<string, any> };
}
interface Session {
  session: string;
  run_ids: string[];
  sites: string[];
  pages: number;
  changes: number;
  timestamp: string;
}
interface PageLite {
  url: string;
  title: string;
  word_count: number;
}
interface PageDetail {
  url: string;
  crawled_at: string;
  data: { facts: any; narrative: string[] };
  copy: { facts: any; narrative: string[] };
  visual: { facts: any; narrative: string[] };
}

/* 변경점(diff) 탭의 4 카테고리를 DATA/COPY/VISUAL 3버킷으로 매핑 (요구사항 1.5 — 중복 귀속 금지) */
const BUCKET_OF: Record<string, "data" | "copy" | "visual"> = {
  "데이터·스키마": "data",
  카피: "copy",
  "가격·프로모션": "copy",
  비주얼: "visual",
};
const CATS = [
  {
    key: "데이터·스키마",
    icon: "🔍",
    bucket: "data",
    tip: "웹페이지의 구조·코드(스키마/HTML)·메뉴 변화. 검색·AI 노출에 영향을 줍니다.",
  },
  {
    key: "카피",
    icon: "✍️",
    bucket: "copy",
    tip: "제목·본문·문구·FAQ 등 글로 쓰인 내용의 변화입니다.",
  },
  {
    key: "가격·프로모션",
    icon: "💰",
    bucket: "copy",
    tip: "가격·구매 버튼·사전예약·보상판매(Trade-in) 등 거래 관련 변화입니다.",
  },
  {
    key: "비주얼",
    icon: "🖼️",
    bucket: "visual",
    tip: "메인 이미지·배너 등 시각 요소의 변화입니다.",
  },
];
const DTABS: { key: "data" | "copy" | "visual"; label: string; icon: string }[] = [
  { key: "data", label: "DATA", icon: "🔍" },
  { key: "copy", label: "COPY", icon: "✍️" },
  { key: "visual", label: "VISUAL", icon: "🖼️" },
];
const LV: Record<string, string> = { High: "var(--high)", Medium: "var(--med)", Low: "var(--low)" };
const LV_KO: Record<string, string> = { High: "높음", Medium: "보통", Low: "낮음" };

/* 사이드 'Example'에서만 보여줄 예시 (실제 사이트 관찰 기반) */
const PREV = "(예시용 가상)";
const _changes: Change[] = [
  {
    id: 1,
    url: "https://www.apple.com/apple-intelligence/",
    site: "apple",
    level: "Medium",
    category: "카피",
    field: "대표 제목",
    summary: '대표 제목이 "차세대 Apple Intelligence·Siri"로 바뀜',
    before: PREV,
    after: "Introducing the next generation of Apple Intelligence and Siri",
    evidence: { "바뀐 문장": "1개" },
  },
  {
    id: 2,
    url: "https://www.apple.com/apple-intelligence/",
    site: "apple",
    level: "Medium",
    category: "데이터·스키마",
    field: "메뉴/기능",
    summary: '새 기능 안내 추가 — Safari에 "가격·재입고가 바뀌면 알려주는 기능"',
    before: PREV,
    after: "Safari로 가격·재입고 변경 알림",
    evidence: { "변화 유형": "새 항목 추가" },
  },
  {
    id: 6,
    url: "https://www.apple.com/iphone/",
    site: "apple",
    level: "High",
    category: "데이터·스키마",
    field: "구조화 데이터",
    summary: "신제품 라인업(iPhone 17 Pro/Air/17/17e)이 페이지 구조에 반영됨",
    before: PREV,
    after: "Product 스키마 4종(iPhone 17 Pro / Air / 17 / 17e)",
    evidence: { "변화 유형": "항목 증가" },
  },
  {
    id: 4,
    url: "https://www.samsung.com/sg/galaxy-ai/",
    site: "samsung",
    level: "Medium",
    category: "카피",
    field: "대표 제목",
    summary: "대표 제목(슬로건) 변경",
    before: PREV,
    after: "Galaxy AI, a true AI companion",
    evidence: { "바뀐 문장": "1개" },
  },
  {
    id: 3,
    url: "https://www.samsung.com/sg/galaxy-ai/",
    site: "samsung",
    level: "Medium",
    category: "가격·프로모션",
    field: "안내 문구",
    summary: '"Galaxy AI 2025년 말까지 무료" 프로모션 문구 노출',
    before: PREV,
    after: "Galaxy AI features free until the end of 2025",
    evidence: { "감지된 키워드": "무료 / 2025" },
  },
  {
    id: 5,
    url: "https://www.samsung.com/sg/",
    site: "samsung",
    level: "Low",
    category: "비주얼",
    field: "메인 이미지",
    summary: "메인 화면 이미지가 바뀐 것으로 감지됨",
    before: PREV,
    after: "(새 이미지)",
    evidence: { "이미지 차이": "14 / 64" },
  },
];
const _now = () => new Date().toISOString().slice(0, 16).replace("T", " ");
