'use client';
import { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar from '../components/Sidebar';
import MainPanel from '../components/MainPanel';
import InsightsPanel from '../components/InsightsPanel';

export interface Run {
  run_id: string; timestamp: string | null;
  pages_crawled: number; changed_urls: number;
}
export interface DiffCopy  { location: string; old: string; new: string; }
export interface DiffImage { location: string; status: '교체' | '추가' | '제거'; old?: string; new?: string; }
export interface DiffSchema { status: '추가' | '수정' | '제거'; type: string; old?: string; new?: string; }
export interface DiffDetail { copies?: DiffCopy[]; images?: DiffImage[]; schemas?: DiffSchema[]; }
export interface DataChange {
  url: string; site: string; tier: string;
  added: number; removed: number; title_changed: boolean;
  severity: string; severity_score: number; change_types: string[];
  diff_detail?: DiffDetail;
  screenshot_url?: string | null;
}
export interface CategoryInsight {
  status: '양호' | '주의' | '위험';
  summary: string;
  apple_score?: number;
  samsung_score?: number;
  improvement_points?: string[];
}
export interface Analysis {
  change_summary: string; consumer_perception: string;
  samsung_comparison: string; insights: string[];
  action_items: string[]; priority_label: string; functional_area: string;
  category_insights?: Record<string, CategoryInsight>;
}
export interface ReportData {
  run_id: string; url: string; site_name: string; tier: string;
  timestamp: string | null; analysis: Analysis | null;
  data_changes: DataChange[];
  content_changes: { url: string; site: string; tier: string }[];
  total_changed_urls: number;
}

interface CrawlProgressItem {
  url: string; site: string; tier: string;
  status: 'success' | 'error'; title?: string; error?: string;
}
interface CrawlProgress {
  run_id?: string; total: number; done: number;
  items: CrawlProgressItem[]; currentTier?: string; finished: boolean;
}

// ── 데모 데이터 ──────────────────────────────────────────────────────────────
const DEMO_REPORT: ReportData = {
  run_id: 'demo', url: 'https://www.apple.com/iphone/',
  site_name: 'Apple', tier: 'Tier 0', timestamp: new Date().toISOString(),
  analysis: {
    change_summary: 'apple.com/iphone/ Hero H1 이 교체됐습니다. apple.com/apple-intelligence/ 에 FAQPage 스키마 (5개 Q&A) 가 신규 추가됐고, apple.com/iphone-17-pro/ Product 스키마 내 가격이 월 할부 기준으로 변경됐습니다.',
    consumer_perception: 'Apple Intelligence 전면 배치로 AI 퍼스트 브랜드 이미지가 강화됩니다.',
    samsung_comparison: 'Galaxy AI 관련 페이지의 JSON-LD 스키마 completeness 가 Apple 대비 낮습니다.',
    insights: [
      'AI: apple.com/apple-intelligence/ 에 FAQPage 스키마 (5개 Q&A) 신규 추가 — AI Overview 스니펫 노출 경쟁 본격화',
      'Brand: apple.com/iphone/ H1 「iPhone.」→「Hello, Apple Intelligence.」 교체 — og:title·meta description 동시 반영',
      'UX: apple.com/iphone/ Hero 이미지를 라이프스타일 그룹 컷으로 교체 — 타깃 연령대 확장 의도',
      'Pricing: apple.com/iphone-17-pro/ Product 스키마 price 「1,399,000」→「월 58,300원~」 변경',
      'SEO: apple.com/apple-intelligence/ BreadcrumbList 스키마 신규 추가 — 구조화 데이터 완비',
    ],
    action_items: [
      '🚨 samsung.com/sg/galaxy-ai/ 에 FAQPage JSON-LD 스키마 적용 — apple.com/apple-intelligence/ 대비 GEO 노출 구조 취약',
      '⚠️ samsung.com/sg/galaxy-ai/ H1 슬로건 단일화 — 페이지별 4가지 상이 버전 통일',
      '👀 samsung.com/sg/smartphones/galaxy-s26-ultra/buy/ CTA 버튼 sticky 상단 고정',
    ],
    priority_label: 'Critical', functional_area: 'SEO·AI 인덱싱 · 헤드라인·슬로건',
    category_insights: {
      'SEO·AI 인덱싱':  { status: '위험', summary: 'apple.com/apple-intelligence/ 에 FAQPage 2개 Q&A 인라인 임베드 신규 추가 → AI Overview 스니펫 직접 트리거 가능. samsung.com/sg/galaxy-ai/ 는 @id 참조 기반 연결형 스키마 구조 — 유효하나 AI 크롤러가 FAQPage 스니펫으로 파싱하기 어려움.', apple_score: 9, samsung_score: 6, improvement_points: ['samsung.com/sg/galaxy-ai/ 에 FAQPage 완전 인라인 임베드 적용', '@id 참조 구조를 self-contained 블록으로 전환'] },
      '헤드라인·슬로건': { status: '위험', summary: 'apple.com/iphone/ H1 이 「Hello, Apple Intelligence.」로 일관 교체됨. samsung.com/sg/galaxy-ai/ H1 은 「Galaxy AI」·「AI that works for you」·「당신의 AI」 등 3가지 버전 혼재.', apple_score: 9, samsung_score: 5, improvement_points: ['samsung.com/sg/galaxy-ai/ H1 슬로건 단일화'] },
      '가격·프로모션':   { status: '주의', summary: 'apple.com/iphone-17-pro/ Product 스키마 price 가 월 할부 기준으로 변경됨. samsung.com/sg/smartphones/galaxy-s26-ultra/ 는 일시불 기준만 표기.', apple_score: 8, samsung_score: 5, improvement_points: ['Galaxy S26 Ultra 페이지 월 할부 기준 가격 Hero 배치'] },
      '비주얼·미디어':   { status: '주의', summary: 'apple.com/iphone/ Hero 이미지가 제품 단독 컷 → 라이프스타일 그룹 컷으로 교체됨. alt 텍스트에 AI 기능 키워드 포함. Samsung Hero 이미지 alt 텍스트 다수 누락.', apple_score: 8, samsung_score: 6, improvement_points: ['Galaxy S26 Ultra 이미지 alt 텍스트 AI 키워드 포함'] },
      '내비게이션·구조': { status: '양호', summary: '양사 모두 BreadcrumbList 스키마 적용. apple.com 클릭 2회 내 구매 페이지 도달. samsung.com/sg 구조 동등 수준.', apple_score: 8, samsung_score: 7 },
      'CTA·구매 흐름':  { status: '주의', summary: 'apple.com/iphone/ CTA (Buy) sticky 상단 고정. samsung.com/sg/smartphones/galaxy-s26-ultra/buy/ CTA 는 스크롤 60% 이상 내려야 노출.', apple_score: 9, samsung_score: 6, improvement_points: ['samsung.com/sg/smartphones/galaxy-s26-ultra/buy/ CTA sticky 상단 고정'] },
      '본문·기능 설명':  { status: '양호', summary: '양사 주요 제품 스펙 수치 일관 사용. Samsung Galaxy S26 Ultra 카메라 수치(200MP) 구체 명시. Apple iPhone 17 Pro 카메라 ProRes 영상 명시.', apple_score: 8, samsung_score: 7 },
    },
  },
  data_changes: [
    { url: 'https://www.apple.com/iphone/', site: 'Apple', tier: 'Tier 1', added: 82, removed: 34, title_changed: true, severity: 'Critical', severity_score: 88, change_types: ['헤드라인·슬로건', 'SEO·AI 인덱싱'], screenshot_url: null },
    { url: 'https://www.apple.com/apple-intelligence/', site: 'Apple', tier: 'Tier 2', added: 56, removed: 12, title_changed: false, severity: 'High', severity_score: 65, change_types: ['SEO·AI 인덱싱', '본문·기능 설명'], screenshot_url: null },
    { url: 'https://www.apple.com/iphone-17-pro/', site: 'Apple', tier: 'Tier 3', added: 18, removed: 5, title_changed: false, severity: 'Medium', severity_score: 38, change_types: ['가격·프로모션'], screenshot_url: null },
  ],
  content_changes: [{ url: 'https://www.apple.com/iphone/', site: 'Apple', tier: 'Tier 1' }],
  total_changed_urls: 3,
};

const DEMO_SNAPSHOT: ReportData = {
  run_id: 'demo-snapshot', url: 'https://www.apple.com/iphone/',
  site_name: 'Apple', tier: 'Tier 0', timestamp: new Date().toISOString(),
  analysis: {
    change_summary: '이번 크롤링 (45 개 페이지) 에서 Apple·Samsung 주요 페이지 변경이 감지되지 않았습니다. 현재 상태 기반 Apple vs Samsung 경쟁 현황을 분석합니다.',
    consumer_perception: 'Apple 은 "Built for Apple Intelligence" 슬로건을 전 제품 페이지에 일관 적용하고 있으며 H1·og:title·meta description 이 동일 메시지로 정렬되어 있습니다.',
    samsung_comparison: 'apple.com/apple-intelligence/ 는 FAQPage 5개 Q&A + BreadcrumbList 완비. samsung.com/sg/galaxy-ai/ 는 기본 WebPage 스키마만 적용 — GEO 노출 경쟁에서 뒤처질 위험.',
    insights: [
      'AI: Apple iPhone 전 제품 페이지 FAQPage + BreadcrumbList 스키마 완비 — Google AI Overview 내 노출 구조 선점',
      'Brand: "Built for Apple Intelligence" H1 이 og:title·meta description 4 개 필드에 동시 적용 — 채널 전반 메시지 통일',
      'UX: iPhone 구매 페이지 CTA sticky 고정 — 이탈 방지 구조. Galaxy 구매 페이지 CTA 하단 위치',
      'Product: FAQPage 스키마 5 개 Q&A 등록 — 음성 검색·AI 답변 최적화',
      'Pricing: iPhone 전 모델 월 할부 기준 가격 Hero 최상단 배치 — 진입 장벽 낮추는 전략',
      'SEO: Apple alt 텍스트에 AI 기능 키워드 포함 — Samsung 대비 이미지 SEO 우위',
    ],
    action_items: [
      '🚨 samsung.com/sg/galaxy-ai/ 에 FAQPage JSON-LD 스키마 적용 — apple.com/apple-intelligence/ 대비 GEO 노출 구조 취약',
      '⚠️ samsung.com/sg/galaxy-ai/ H1 을 「Galaxy AI. 당신의 일상을 바꾸다.」 단일화',
      '⚠️ samsung.com/sg/smartphones/galaxy-s26-ultra/buy/ CTA sticky 상단 고정',
      '👀 samsung.com/sg/smartphones/galaxy-s26/ Hero 에 월 할부 기준 가격 추가 표기',
      '👀 samsung.com/sg/smartphones/all-smartphones/ 이미지 alt 텍스트에 Galaxy AI 기능 키워드 포함',
    ],
    priority_label: 'High', functional_area: 'SEO·AI 인덱싱 · CTA·구매 흐름 · 헤드라인·슬로건',
    category_insights: {
      'SEO·AI 인덱싱':  { status: '주의', summary: '양사 모두 Product·BreadcrumbList·Organization 스키마 보유. 차이는 구현 방식: Apple 은 FAQPage 완전 인라인 임베드로 AI Overview 직접 노출 가능. Samsung 은 @id 참조 연결형 구조 — AI 크롤러가 FAQPage 스니펫으로 파싱하기 어려운 방식.', apple_score: 9, samsung_score: 6, improvement_points: ['samsung.com/sg/galaxy-ai/ FAQPage 완전 인라인 임베드로 전환', '@id 연결 스키마를 self-contained 블록 병행 적용'] },
      '헤드라인·슬로건': { status: '위험', summary: 'apple.com 전 제품 H1·og:title·meta description 이 "Built for Apple Intelligence" 단일 메시지로 정렬. samsung.com/sg/galaxy-ai/ H1 은 「Galaxy AI」·「AI that works for you」 등 혼재.', apple_score: 9, samsung_score: 4, improvement_points: ['samsung.com/sg/galaxy-ai/ H1 단일화', 'og:title 패턴 전 페이지 정렬'] },
      '가격·프로모션':   { status: '주의', summary: 'apple.com/iphone-17-pro/ 월 58,300원~ Hero 최상단 표기 + Trade-in ₩550,000 크레딧 병기. samsung.com/sg/smartphones/galaxy-s26-ultra/ 일시불 SGD 1,898 기준, 할부 정보는 구매 페이지 하단.', apple_score: 8, samsung_score: 5, improvement_points: ['Galaxy S26 Ultra Hero 에 월 할부 기준 가격 표기'] },
      '비주얼·미디어':   { status: '주의', summary: 'apple.com/iphone/ 색상 선택 시 Hero 이미지 실시간 전환 + AI 기능 시연 영상 자동 재생. samsung.com/sg/smartphones/galaxy-s26-ultra/ 색상 스와치 없음, 이미지 alt 텍스트 다수 누락.', apple_score: 8, samsung_score: 6, improvement_points: ['Galaxy S26 Ultra 색상별 이미지 전환 지원', '이미지 alt 텍스트 Galaxy AI 키워드 포함'] },
      '내비게이션·구조': { status: '양호', summary: '양사 모두 BreadcrumbList 스키마 적용. apple.com 클릭 2회 내 구매 완료. samsung.com/sg 도 동등 수준의 구매 흐름 제공.', apple_score: 8, samsung_score: 7 },
      'CTA·구매 흐름':  { status: '주의', summary: 'apple.com/iphone/ CTA (Buy) sticky 상단 고정 — 스크롤 위치 무관 노출. samsung.com/sg/smartphones/galaxy-s26-ultra/buy/ CTA 는 스크롤 60% 이상 내려야 노출됨.', apple_score: 9, samsung_score: 6, improvement_points: ['galaxy-s26-ultra/buy/ CTA sticky 상단 고정', '구매 4단계 진행 바 명확화'] },
      '본문·기능 설명':  { status: '양호', summary: '양사 주요 스펙 수치 구체 명시. Apple iPhone 17 Pro ProRes 비디오·A19 Bionic 강조. Samsung Galaxy S26 Ultra 200MP·S Pen 강조. 동등 수준.', apple_score: 8, samsung_score: 7 },
    },
  },
  data_changes: [], content_changes: [], total_changed_urls: 0,
};

// ── 크롤링 진행 패널 ─────────────────────────────────────────────────────────
function CrawlProgressPanel({ progress, onStop }: { progress: CrawlProgress; onStop: () => void }) {
  const successCount = progress.items.filter(i => i.status === 'success').length;
  const errorCount   = progress.items.filter(i => i.status === 'error').length;
  const pct = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;

  return (
    <div style={{ background: '#fff', border: '1px solid #E8EAED', borderRadius: 12, overflow: 'hidden', marginBottom: 14 }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #E8EAED', background: '#F9FAFB' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {!progress.finished
              ? <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#2563EB', display: 'inline-block' }} />
              : <span style={{ fontSize: 14 }}>✅</span>}
            <span style={{ fontSize: 13, fontWeight: 700, color: '#111318' }}>
              {progress.finished ? '크롤링 완료' : '크롤링 진행 중...'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {errorCount > 0 && <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20, background: '#FEF2F2', color: '#991B1B', border: '1px solid #FECACA' }}>실패 {errorCount}</span>}
            <span style={{ fontSize: 11, color: '#6B7280' }}>{progress.done} / {progress.total}</span>
            {!progress.finished && (
              <button onClick={onStop} style={{ padding: '3px 10px', borderRadius: 6, border: '1px solid #FECACA', background: '#FEF2F2', color: '#DC2626', cursor: 'pointer', fontSize: 10, fontWeight: 600 }}>⏹ 중단</button>
            )}
          </div>
        </div>
        <div style={{ height: 5, background: '#E8EAED', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${pct}%`, background: progress.finished ? '#22C55E' : '#2563EB', borderRadius: 3, transition: 'width 0.4s ease' }} />
        </div>
        {progress.currentTier && !progress.finished && (
          <p style={{ fontSize: 10, color: '#9CA3AF', margin: '5px 0 0' }}>현재: {progress.currentTier}</p>
        )}
      </div>
      <div style={{ maxHeight: 260, overflowY: 'auto', padding: '6px 0' }}>
        {[...progress.items].reverse().slice(0, 12).map((item, i) => (
          <div key={i} style={{ padding: '6px 16px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid #F3F4F6' }}>
            <span style={{ fontSize: 11, color: item.status === 'success' ? '#22C55E' : '#DC2626', flexShrink: 0 }}>{item.status === 'success' ? '✓' : '✗'}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontSize: 11, fontWeight: 500, margin: 0, color: item.status === 'error' ? '#DC2626' : '#111318', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.title || item.url}
              </p>
              {item.error && <p style={{ fontSize: 10, color: '#DC2626', margin: '1px 0 0' }}>{item.error}</p>}
            </div>
            <span style={{ fontSize: 9, fontWeight: 600, padding: '1px 6px', borderRadius: 4, flexShrink: 0, background: item.site === 'Apple' ? '#F3F4F6' : '#EFF6FF', color: item.site === 'Apple' ? '#374151' : '#1D4ED8' }}>{item.site}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  const [runs, setRuns]                     = useState<Run[]>([]);
  const [selectedRunId, setSelectedRunId]   = useState<string | null>(null);
  const [report, setReport]                 = useState<ReportData | null>(null);
  const [loading, setLoading]               = useState(false);
  const [crawling, setCrawling]             = useState(false);
  const [error, setError]                   = useState<string | null>(null);
  const [crawlProgress, setCrawlProgress]   = useState<CrawlProgress | null>(null);
  const [isWithinActiveHours, setIsWithinActiveHours] = useState(false);
  const sseRef = useRef<EventSource | null>(null);
  const api    = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const fetchRuns = useCallback(async () => {
    try { const r = await fetch(`${api}/api/runs`); const j = await r.json(); setRuns(j.runs || []); } catch {}
  }, [api]);

  const fetchReport = useCallback(async (runId?: string) => {
    setLoading(true); setError(null);
    try {
      const url = runId ? `${api}/api/latest-report?run_id=${runId}` : `${api}/api/latest-report`;
      const res = await fetch(url);
      const json = await res.json();
      if ('error' in json) { setError(json.error); return; }
      setReport(json as ReportData);
      setSelectedRunId(json.run_id);
    } catch (e: any) { setError(e.message || '데이터 로드 실패'); }
    finally { setLoading(false); }
  }, [api]);

  const connectSSE = useCallback(() => {
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    const es = new EventSource(`${api}/api/crawl-progress`);
    sseRef.current = es;
    setCrawlProgress({ total: 0, done: 0, items: [], finished: false });

    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        if (ev.type === 'heartbeat') return;
        if (ev.type === 'status') { if (!ev.crawling) { es.close(); sseRef.current = null; } return; }
        if (ev.type === 'start') {
          setCrawling(true);
          setCrawlProgress({ run_id: ev.run_id, total: ev.total, done: 0, items: [], finished: false });
          return;
        }
        if (ev.type === 'tier_start') {
          setCrawlProgress(p => p ? { ...p, currentTier: ev.tier } : p);
          return;
        }
        if (ev.type === 'page_done') {
          setCrawlProgress(p => {
            if (!p) return p;
            return { ...p, done: p.done + 1, items: [...p.items, { url: ev.url, site: ev.site, tier: ev.tier, status: ev.status, title: ev.title, error: ev.error }] };
          });
          return;
        }
        if (ev.type === 'done' || ev.type === 'stopped') {
          setCrawling(false);
          setCrawlProgress(p => p ? { ...p, finished: true, currentTier: undefined } : p);
          es.close(); sseRef.current = null;
          setTimeout(() => { fetchRuns(); fetchReport(); }, 1500);
          return;
        }
      } catch {}
    };
    es.onerror = () => { es.close(); sseRef.current = null; };
  }, [api, fetchRuns, fetchReport]);

  const triggerCrawl = async (tiers: string[]) => {
    try {
      const res = await fetch(`${api}/trigger-crawl/all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tiers }),
      });
      if (res.status === 409) { setCrawling(true); connectSSE(); return; }
      setCrawling(true);
      connectSSE();
    } catch {}
  };

  const stopCrawl = async () => {
    try { await fetch(`${api}/api/crawl-stop`, { method: 'POST' }); } catch {}
  };

  const deleteRun = async (runId: string) => {
    // 낙관적 UI 업데이트 — 먼저 지우고 API 호출
    setRuns(prev => prev.filter(r => r.run_id !== runId));
    if (selectedRunId === runId) { setReport(null); setSelectedRunId(null); }
    try {
      const res = await fetch(`${api}/api/run/${runId}`, { method: 'DELETE' });
      if (!res.ok) console.warn('Delete API failed:', res.status);
    } catch (e) { console.error('Delete fetch error:', e); }
  };

  const showDemo         = () => { setReport(DEMO_REPORT);   setSelectedRunId('demo');          setError(null); };
  const showDemoSnapshot = () => { setReport(DEMO_SNAPSHOT); setSelectedRunId('demo-snapshot'); setError(null); };
  const goHome = () => { setReport(null); setSelectedRunId(null); setError(null); };

  useEffect(() => {
    const init = async () => {
      try {
        const r = await fetch(`${api}/api/crawl-status`);
        const j = await r.json();
        if (j.crawling) { setCrawling(true); connectSSE(); }
      } catch {}
    };
    init(); fetchRuns(); fetchReport();
    return () => { if (sseRef.current) { sseRef.current.close(); sseRef.current = null; } };
  }, []);

  // 완료 5 초 후 진행 패널 자동 닫기
  useEffect(() => {
    if (crawlProgress?.finished) {
      const t = setTimeout(() => setCrawlProgress(null), 5000);
      return () => clearTimeout(t);
    }
  }, [crawlProgress?.finished]);

  // 9 AM - 2 PM 활성 시간대 체크 (애니메이션용)
  useEffect(() => {
    const checkActiveHours = () => {
      const now = new Date();
      const hour = now.getHours();
      // 오전 9 시부터 오후 2 시 (14 시) 까지
      const isActive = hour >= 9 && hour < 14;
      setIsWithinActiveHours(isActive);
    };
    
    checkActiveHours();
    const interval = setInterval(checkActiveHours, 60000); // 1 분마다 확인
    return () => clearInterval(interval);
  }, []);

  const isDemoMode = selectedRunId === 'demo' || selectedRunId === 'demo-snapshot';
  // 변경 없음 모드: snapshot (InsightsPanel 을 항상 보여주되 모드 구분용)
  const isSnapshot = !isDemoMode && report !== null && report.total_changed_urls === 0;
  const isDemoSnapshot = selectedRunId === 'demo-snapshot';

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar
        runs={runs} selectedRunId={selectedRunId}
        onSelectRun={(id) => { setSelectedRunId(id); fetchReport(id); }}
        onNewCrawl={triggerCrawl}
        onDeleteRun={deleteRun}
        onShowDemo={showDemo}
        onShowDemoSnapshot={showDemoSnapshot}
        onGoHome={goHome}
        onStopCrawl={stopCrawl}
        crawling={crawling} api={api}
      />
      <main style={{ flex: 1, overflow: 'auto', padding: '20px 16px' }}>
        {crawlProgress && <CrawlProgressPanel progress={crawlProgress} onStop={stopCrawl} />}

        {crawling && !crawlProgress && (
          <div style={{ marginBottom: 12, padding: '9px 14px', borderRadius: 10, background: '#EFF6FF', border: '1px solid #BFDBFE', fontSize: 12, color: '#1D4ED8', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#2563EB', display: 'inline-block' }} />
            크롤링 진행 중입니다. 완료되면 자동으로 업데이트됩니다.
          </div>
        )}

        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: '#9CA3AF', fontSize: 13 }}>데이터를 불러오는 중...</div>
        ) : error ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60vh', gap: 14 }}>
            <p style={{ color: '#9CA3AF', fontSize: 13 }}>{error}</p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={showDemo} style={{ padding: '9px 18px', borderRadius: 10, background: '#fff', color: '#111318', border: '1px solid #E8EAED', cursor: 'pointer', fontSize: 12 }}>예시 1 보기</button>
              <button onClick={showDemoSnapshot} style={{ padding: '9px 18px', borderRadius: 10, background: '#fff', color: '#111318', border: '1px solid #E8EAED', cursor: 'pointer', fontSize: 12 }}>예시 2 보기</button>
              <button onClick={() => triggerCrawl(['Tier 0', 'Tier 1', 'Tier 2', 'Tier 3', 'Tier 4'])} disabled={crawling}
                style={{ padding: '9px 22px', borderRadius: 10, background: crawling ? '#F3F4F6' : '#111318', color: crawling ? '#9CA3AF' : '#fff', border: 'none', cursor: crawling ? 'not-allowed' : 'pointer', fontSize: 13, fontWeight: 500 }}>
                {crawling ? '크롤링 중...' : '지금 크롤링 실행'}
              </button>
            </div>
          </div>
        ) : report ? (
          /* 변경 유무 무관하게 항상 MainPanel + InsightsPanel 함께 표시 */
          (isDemoSnapshot || isSnapshot) ? (
            // snapshot 모드: MainPanel 풀스크린 + 우측 InsightsPanel
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 14, alignItems: 'start' }}>
              <MainPanel report={report} onRefresh={() => fetchReport(selectedRunId ?? undefined)} isDemo={isDemoMode} isSnapshot={true} />
              <InsightsPanel analysis={report.analysis} isSnapshot={true} />
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 14, alignItems: 'start' }}>
              <MainPanel report={report} onRefresh={() => fetchReport(selectedRunId ?? undefined)} isDemo={isDemoMode} isSnapshot={false} />
              <InsightsPanel analysis={report.analysis} isSnapshot={false} />
            </div>
          )
        ) : null}
      </main>
    </div>
  );
}
