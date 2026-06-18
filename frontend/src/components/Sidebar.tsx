import { useState, useEffect } from 'react';
import { Run } from '../app/page';

interface DiffDetail {
  title?: { old: string; new: string } | null;
  images?: { status: string; alt: string }[];
  sections?: { heading: string; status: string; old?: string; new?: string }[];
  schema?: { status: string; type: string; old?: string; new?: string }[];
}
interface PageDetail {
  url: string; site: string; tier: string; title: string;
  body_content: string; timestamp: string | null;
  changed: boolean; severity: string | null; severity_score: number;
  change_types: string[]; added_lines: number; removed_lines: number;
  diff_summary: string; diff_detail: DiffDetail;
}
interface RunDetail {
  run_id: string; total: number; changed_count: number;
  tiers: Record<string, PageDetail[]>;
}
interface Props {
  runs: Run[]; selectedRunId: string | null;
  onSelectRun: (id: string) => void;
  onNewCrawl: (tiers: string[]) => void;
  onDeleteRun: (id: string) => void;
  onShowDemo: () => void;
  onShowDemoSnapshot: () => void;
  onGoHome: () => void;
  onStopCrawl: () => void;
  crawling: boolean; api: string;
}

const C = {
  surface: '#FFFFFF', border: '#E8EAED',
  text: '#111318', textSub: '#6B7280', textMute: '#9CA3AF',
  blue: '#2563EB', blueBg: '#EFF6FF', blueBorder: '#BFDBFE',
};
const SEV_COLOR: Record<string, string> = {
  Critical: '#EF4444', High: '#F97316', Medium: '#EAB308', Low: '#22C55E',
};
const TYPE_DISPLAY: Record<string, string> = {
  'SEO·AI 인덱싱': '검색·AI', '가격·프로모션': '가격·혜택', '헤드라인·슬로건': '헤드라인',
  '비주얼·미디어': '이미지·영상', '내비게이션·구조': '사이트 구조', 'CTA·구매 흐름': '구매 유도', '본문·기능 설명': '제품 설명',
};
const TYPE_STYLE: Record<string, { bg: string; color: string; border: string }> = {
  'SEO·AI 인덱싱':  { bg: '#EFF6FF', color: '#1D4ED8', border: '#BFDBFE' },
  '가격·프로모션':   { bg: '#F0FDF4', color: '#15803D', border: '#BBF7D0' },
  '헤드라인·슬로건': { bg: '#FAF5FF', color: '#7E22CE', border: '#E9D5FF' },
  '비주얼·미디어':   { bg: '#FFF7ED', color: '#C2410C', border: '#FED7AA' },
  '내비게이션·구조': { bg: '#F9FAFB', color: '#374151', border: '#E5E7EB' },
  'CTA·구매 흐름':  { bg: '#FFF1F2', color: '#BE123C', border: '#FECDD3' },
  '본문·기능 설명':  { bg: '#F9FAFB', color: '#4B5563', border: '#E5E7EB' },
};
const ALL_TIERS = ['Tier 0', 'Tier 1', 'Tier 2', 'Tier 3', 'Tier 4'];
const TIER_DESC: Record<string, string> = {
  'Tier 0': '브랜드 홈 (2)',
  'Tier 1': '카테고리 (6)',
  'Tier 2': '캠페인 (8)',
  'Tier 3': '제품 상세 (14)',
  'Tier 4': '구매·스펙 (15)',
};

const fmt = (ts: string | null) => {
  if (!ts) return '—';
  const d = new Date(ts);
  return isNaN(d.getTime()) ? ts : d.toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};
const shortUrl = (url: string) => {
  try {
    const u = new URL(url);
    const parts = u.pathname.replace(/\/$/, '').split('/').filter(Boolean);
    return parts.length === 0 ? u.hostname.replace('www.', '') : `${u.hostname.replace('www.', '')}/${parts[parts.length - 1]}`;
  } catch { return url.replace('https://', '').replace('www.', ''); }
};
const volumeText = (a: number, r: number) => {
  const t = a + r;
  if (t >= 100) return '대규모 업데이트';
  if (t >= 30)  return '상당한 변경';
  if (t >= 10)  return '일부 변경';
  return '소폭 수정';
};

export default function Sidebar({ runs, selectedRunId, onSelectRun, onNewCrawl, onDeleteRun, onShowDemo, onShowDemoSnapshot, onGoHome, onStopCrawl, crawling, api }: Props) {
  const [drawerOpen, setDrawerOpen]       = useState(false);
  const [detail, setDetail]               = useState<RunDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [expandedUrl, setExpandedUrl]     = useState<string | null>(null);
  const [guideOpen, setGuideOpen]         = useState(false);
  const [tierPanelOpen, setTierPanelOpen] = useState(false);
  const [selectedTiers, setSelectedTiers] = useState<string[]>(ALL_TIERS);
  const [autoCrawl, setAutoCrawl]         = useState(true);
  const [togglingAuto, setTogglingAuto]   = useState(false);

  // 자동 크롤링 상태 로드
  useEffect(() => {
    fetch(`${api}/api/settings`)
      .then(r => r.json())
      .then(d => setAutoCrawl(d.auto_crawl_enabled ?? true))
      .catch(() => {});
  }, [api]);

  const toggleAutoCrawl = async () => {
    setTogglingAuto(true);
    try {
      const res = await fetch(`${api}/api/auto-crawl`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !autoCrawl }),
      });
      const d = await res.json();
      setAutoCrawl(d.auto_crawl_enabled);
    } catch {} finally { setTogglingAuto(false); }
  };

  const toggleTier = (tier: string) => {
    setSelectedTiers(prev =>
      prev.includes(tier) ? prev.filter(t => t !== tier) : [...prev, tier]
    );
  };

  const handleStartCrawl = () => {
    if (selectedTiers.length === 0) return;
    onNewCrawl(selectedTiers);
    setTierPanelOpen(false);
  };

  const openDrawer = async (run: Run, e: React.MouseEvent) => {
    e.stopPropagation();
    setDrawerOpen(true); setDetail(null); setExpandedUrl(null); setLoadingDetail(true);
    try { const res = await fetch(`${api}/api/run-detail/${run.run_id}`); setDetail(await res.json()); }
    catch {} finally { setLoadingDetail(false); }
  };

  return (
    <>
      <aside style={{ width: 240, flexShrink: 0, background: C.surface, borderRight: `1px solid ${C.border}`, display: 'flex', flexDirection: 'column', height: '100vh' }}>

        {/* 로고 */}
        <div style={{ padding: '18px 16px 14px', borderBottom: `1px solid ${C.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button onClick={onGoHome} title="홈으로"
              style={{ width: 36, height: 36, borderRadius: 10, background: C.text, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, border: 'none', cursor: 'pointer', padding: 0 }}>
              <span style={{ fontSize: 18 }}>🔍</span>
            </button>
            <div>
              <p style={{ fontSize: 14, fontWeight: 700, margin: 0, color: C.text, letterSpacing: '-0.5px' }}>Apple Stalker</p>
              <p style={{ fontSize: 10, margin: '2px 0 0', color: C.textMute }}>경쟁사 인텔리전스</p>
            </div>
          </div>
        </div>

        {/* ── 자동 크롤링 토글 ── */}
        <div style={{ padding: '10px 14px 0', borderBottom: `1px solid ${C.border}`, paddingBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div>
              <p style={{ fontSize: 11, fontWeight: 600, margin: 0, color: C.text }}>자동 크롤링</p>
              <p style={{ fontSize: 10, margin: '1px 0 0', color: C.textMute }}>오전 9 시 · 오후 2 시</p>
            </div>
            <button
              onClick={toggleAutoCrawl}
              disabled={togglingAuto}
              title={autoCrawl ? '자동 크롤링 끄기' : '자동 크롤링 켜기'}
              style={{
                width: 40, height: 22, borderRadius: 11, border: 'none', cursor: 'pointer',
                background: autoCrawl ? '#22C55E' : '#D1D5DB',
                position: 'relative', transition: 'background 0.2s', flexShrink: 0,
              }}
            >
              <span style={{
                position: 'absolute', top: 3, left: autoCrawl ? 20 : 3,
                width: 16, height: 16, borderRadius: '50%', background: '#fff',
                transition: 'left 0.2s', display: 'block',
                boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
              }} />
            </button>
          </div>

          {/* ── 수동 크롤링 — Tier 선택 ── */}
          {crawling ? (
            <button onClick={onStopCrawl}
              style={{ width: '100%', padding: '8px 0', borderRadius: 9, background: '#FEF2F2', color: '#DC2626', border: '1px solid #FECACA', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
              ⏹ 크롤링 중단
            </button>
          ) : (
            <div>
              <button
                onClick={() => setTierPanelOpen(v => !v)}
                style={{ width: '100%', padding: '8px 0', borderRadius: 9, background: C.text, color: '#fff', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                <span>+ 수동 크롤링</span>
                <span style={{ fontSize: 10, opacity: 0.7 }}>{tierPanelOpen ? '▲' : '▼'}</span>
              </button>

              {tierPanelOpen && (
                <div style={{ marginTop: 8, padding: '10px 10px 8px', background: '#F9FAFB', borderRadius: 8, border: `1px solid ${C.border}` }}>
                  <p style={{ fontSize: 10, fontWeight: 700, color: C.textSub, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>크롤링할 Tier 선택</p>
                  {ALL_TIERS.map(tier => (
                    <label key={tier} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '4px 0', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={selectedTiers.includes(tier)}
                        onChange={() => toggleTier(tier)}
                        style={{ width: 13, height: 13, cursor: 'pointer', accentColor: C.blue }}
                      />
                      <span style={{ fontSize: 11, color: C.text, fontWeight: 500 }}>{tier}</span>
                      <span style={{ fontSize: 10, color: C.textMute, marginLeft: 'auto' }}>{TIER_DESC[tier]}</span>
                    </label>
                  ))}
                  <div style={{ display: 'flex', gap: 5, marginTop: 8 }}>
                    <button onClick={() => setSelectedTiers(ALL_TIERS)}
                      style={{ flex: 1, padding: '5px 0', borderRadius: 6, border: `1px solid ${C.border}`, background: C.surface, cursor: 'pointer', fontSize: 10, color: C.textSub }}>전체</button>
                    <button onClick={() => setSelectedTiers([])}
                      style={{ flex: 1, padding: '5px 0', borderRadius: 6, border: `1px solid ${C.border}`, background: C.surface, cursor: 'pointer', fontSize: 10, color: C.textSub }}>해제</button>
                    <button
                      onClick={handleStartCrawl}
                      disabled={selectedTiers.length === 0}
                      style={{ flex: 2, padding: '5px 0', borderRadius: 6, border: 'none', background: selectedTiers.length === 0 ? '#F3F4F6' : C.blue, color: selectedTiers.length === 0 ? C.textMute : '#fff', cursor: selectedTiers.length === 0 ? 'not-allowed' : 'pointer', fontSize: 11, fontWeight: 600 }}>
                      실행 ({selectedTiers.length})
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 히스토리 */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          <p style={{ fontSize: 10, fontWeight: 700, color: C.textMute, padding: '8px 16px 4px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>히스토리</p>

          <button onClick={onShowDemo} style={{ width: '100%', textAlign: 'left', padding: '8px 16px', border: 'none', cursor: 'pointer', background: selectedRunId === 'demo' ? C.blueBg : 'transparent', borderLeft: selectedRunId === 'demo' ? `3px solid ${C.blue}` : '3px solid transparent', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 10, padding: '1px 7px', borderRadius: 5, background: '#FFF7ED', color: '#92400E', fontWeight: 700, border: '1px solid #FED7AA', flexShrink: 0 }}>예시 1</span>
            <div><p style={{ fontSize: 11, fontWeight: 600, margin: 0, color: C.text }}>변경 감지됨</p><p style={{ fontSize: 10, margin: '1px 0 0', color: C.textMute }}>Apple 5 개 페이지 변경</p></div>
          </button>
          <button onClick={onShowDemoSnapshot} style={{ width: '100%', textAlign: 'left', padding: '8px 16px', border: 'none', cursor: 'pointer', background: selectedRunId === 'demo-snapshot' ? C.blueBg : 'transparent', borderLeft: selectedRunId === 'demo-snapshot' ? `3px solid ${C.blue}` : '3px solid transparent', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 10, padding: '1px 7px', borderRadius: 5, background: '#FAF5FF', color: '#7E22CE', fontWeight: 700, border: '1px solid #E9D5FF', flexShrink: 0 }}>예시 2</span>
            <div><p style={{ fontSize: 11, fontWeight: 600, margin: 0, color: C.text }}>변경 없음</p><p style={{ fontSize: 10, margin: '1px 0 0', color: C.textMute }}>현재 상태 기반 분석</p></div>
          </button>

          {runs.length > 0 && <div style={{ margin: '4px 16px', borderTop: `1px solid ${C.border}` }} />}

          {runs.length === 0 ? (
            <p style={{ fontSize: 11, color: C.textMute, padding: '6px 16px' }}>실행 기록 없음</p>
          ) : runs.map(run => (
            <div key={run.run_id} style={{ position: 'relative' }}>
              <button onClick={() => onSelectRun(run.run_id)} style={{ width: '100%', textAlign: 'left', padding: '8px 56px 8px 16px', border: 'none', cursor: 'pointer', background: run.run_id === selectedRunId ? C.blueBg : 'transparent', borderLeft: run.run_id === selectedRunId ? `3px solid ${C.blue}` : '3px solid transparent' }}>
                <p style={{ fontSize: 11, fontWeight: 600, margin: 0, color: C.text }}>{fmt(run.timestamp)}</p>
                <p style={{ fontSize: 10, margin: '2px 0 0', color: C.textMute }}>
                  {run.pages_crawled}페이지 · <span style={{ color: run.changed_urls > 0 ? '#F97316' : C.textMute, fontWeight: run.changed_urls > 0 ? 600 : 400 }}>{run.changed_urls}개 변경</span>
                </p>
              </button>
              <button onClick={(e) => openDrawer(run, e)} title="크롤링 상세" style={{ position: 'absolute', right: 28, top: '50%', transform: 'translateY(-50%)', width: 22, height: 22, borderRadius: 6, border: `1px solid ${C.border}`, background: C.surface, cursor: 'pointer', fontSize: 11, color: C.textSub, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>↗</button>
              <button onClick={(e) => { e.stopPropagation(); if (confirm('이 기록을 삭제할까요?')) onDeleteRun(run.run_id); }} title="삭제" style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)', width: 22, height: 22, borderRadius: 6, border: `1px solid ${C.border}`, background: C.surface, cursor: 'pointer', fontSize: 13, color: '#EF4444', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</button>
            </div>
          ))}
        </div>

        {/* 이용 안내 (접을 수 있음) */}
        <div style={{ borderTop: `1px solid ${C.border}` }}>
          <button onClick={() => setGuideOpen(v => !v)} style={{ width: '100%', padding: '10px 16px', border: 'none', cursor: 'pointer', background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: C.textSub, textTransform: 'uppercase', letterSpacing: '0.08em' }}>📋 이용 안내</span>
            <span style={{ fontSize: 10, color: C.textMute }}>{guideOpen ? '▲' : '▼'}</span>
          </button>
          {guideOpen && (
            <div style={{ padding: '0 12px 14px', display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
              <div style={{ padding: '10px 12px', borderRadius: 10, background: C.blueBg, border: `1px solid ${C.blueBorder}` }}>
                <p style={{ fontSize: 11, fontWeight: 700, color: '#1D4ED8', margin: '0 0 4px' }}>어떻게 작동하나요?</p>
                <p style={{ fontSize: 11, color: '#1E40AF', margin: 0, lineHeight: 1.6 }}>하루 2 회 (오전 9 시, 오후 2 시) 자동으로 경쟁사 주요 페이지 45 개를 방문해 지난번과 달라진 점을 감지합니다. 변경 유무와 관계없이 매번 AI 인사이트를 생성합니다.</p>
              </div>
              <div style={{ padding: '10px 12px', borderRadius: 10, background: '#FAF5FF', border: '1px solid #E9D5FF' }}>
                <p style={{ fontSize: 11, fontWeight: 700, color: '#7E22CE', margin: '0 0 4px' }}>인사이트 분석</p>
                <p style={{ fontSize: 11, color: '#6B21A8', margin: 0, lineHeight: 1.6 }}>변경이 없을 때도 Apple vs Samsung 현행 경쟁 분석을 제공합니다. SEO·가격·헤드라인·UX 등 7 개 영역별 점수와 개선 포인트를 확인하세요.</p>
              </div>
            </div>
          )}
        </div>

        {/* 모니터링 대상 */}
        <div style={{ borderTop: `1px solid ${C.border}`, padding: '10px 16px' }}>
          <p style={{ fontSize: 10, fontWeight: 700, color: C.textMute, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>모니터링 대상</p>
          {[{ name: 'Apple', color: '#111318' }, { name: 'Samsung', color: '#2563EB' }].map(({ name, color }) => (
            <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '3px 0' }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: color }} />
              <span style={{ fontSize: 11, color: C.text, fontWeight: 500 }}>{name}</span>
              <span style={{ fontSize: 10, color: autoCrawl ? '#22C55E' : C.textMute, marginLeft: 'auto', fontWeight: 600 }}>
                {autoCrawl ? '● 자동 ON' : '○ 자동 OFF'}
              </span>
            </div>
          ))}
        </div>
      </aside>

      {/* 드로어 오버레이 */}
      {drawerOpen && <div onClick={() => setDrawerOpen(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.2)', zIndex: 40 }} />}

      {/* 드로어 */}
      <div style={{ position: 'fixed', top: 0, right: drawerOpen ? 0 : '-540px', width: 520, height: '100vh', zIndex: 50, background: C.surface, borderLeft: `1px solid ${C.border}`, transition: 'right 0.22s cubic-bezier(0.4,0,0.2,1)', display: 'flex', flexDirection: 'column', boxShadow: drawerOpen ? '-8px 0 32px rgba(0,0,0,0.08)' : 'none' }}>
        <div style={{ padding: '16px 20px', borderBottom: `1px solid ${C.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: 14, fontWeight: 700, margin: 0, color: C.text }}>크롤링 상세</p>
            {detail && <p style={{ fontSize: 11, margin: '3px 0 0', color: C.textSub }}>총 {detail.total}개 페이지 · <span style={{ color: '#F97316', fontWeight: 600 }}>{detail.changed_count}개 변경</span></p>}
          </div>
          <button onClick={() => setDrawerOpen(false)} style={{ width: 28, height: 28, borderRadius: 8, border: `1px solid ${C.border}`, background: C.surface, cursor: 'pointer', fontSize: 16, color: C.textSub, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
          {loadingDetail ? (
            <p style={{ fontSize: 12, color: C.textMute, textAlign: 'center', marginTop: 40 }}>불러오는 중...</p>
          ) : !detail ? (
            <p style={{ fontSize: 12, color: C.textMute, textAlign: 'center', marginTop: 40 }}>데이터 없음</p>
          ) : Object.entries(detail.tiers).map(([tier, pages]) => (
            <div key={tier} style={{ marginBottom: 24 }}>
              <p style={{ fontSize: 10, fontWeight: 700, color: C.textMute, margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{tier} · {pages.length}개</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {pages.map(page => {
                  const isExp = expandedUrl === page.url;
                  const sc    = SEV_COLOR[page.severity || ''] || C.border;
                  const dd: DiffDetail = page.diff_detail || {};
                  return (
                    <div key={page.url} style={{ borderRadius: 10, overflow: 'hidden', background: C.surface, border: `1px solid ${C.border}`, borderLeft: page.changed ? `3px solid ${sc}` : '3px solid transparent' }}>
                      <button onClick={() => setExpandedUrl(isExp ? null : page.url)} style={{ width: '100%', textAlign: 'left', padding: '10px 12px', border: 'none', cursor: 'pointer', background: 'transparent', display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 7, height: 7, borderRadius: '50%', background: page.site === 'Apple' ? '#111318' : '#2563EB', flexShrink: 0 }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <p style={{ fontSize: 12, fontWeight: 600, margin: 0, color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{shortUrl(page.url)}</p>
                          {page.title && <p style={{ fontSize: 10, margin: '2px 0 0', color: C.textMute, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{page.title}</p>}
                          {page.changed && page.change_types.length > 0 && (
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginTop: 5 }}>
                              {page.change_types.map(key => {
                                const st = TYPE_STYLE[key] || { bg: '#F9FAFB', color: '#4B5563', border: '#E5E7EB' };
                                return <span key={key} style={{ fontSize: 10, padding: '1px 6px', borderRadius: 5, background: st.bg, color: st.color, border: `1px solid ${st.border}`, fontWeight: 500 }}>{TYPE_DISPLAY[key] || key}</span>;
                              })}
                              <span style={{ fontSize: 10, color: C.textMute, padding: '1px 3px' }}>{volumeText(page.added_lines, page.removed_lines)}</span>
                            </div>
                          )}
                        </div>
                        <span style={{ fontSize: 10, color: C.textMute, flexShrink: 0 }}>{isExp ? '▲' : '▼'}</span>
                      </button>
                      {isExp && (
                        <div style={{ borderTop: `1px solid ${C.border}`, padding: '12px 14px', background: '#F9FAFB' }}>
                          <p style={{ fontSize: 10, color: C.blue, margin: '0 0 12px', wordBreak: 'break-all' }}>{page.url}</p>
                          {!page.changed && <p style={{ fontSize: 11, color: C.textMute, textAlign: 'center', padding: '8px 0' }}>변경 없음 — 정상 수집 완료</p>}
                          {page.changed && page.diff_summary && (
                            <div>
                              <p style={{ fontSize: 10, fontWeight: 700, color: C.textSub, margin: '0 0 5px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>감지된 변경 내용</p>
                              <pre style={{ fontSize: 10, lineHeight: 1.65, margin: 0, padding: '8px 10px', borderRadius: 8, background: C.surface, border: `1px solid ${C.border}`, whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: C.text, fontFamily: 'inherit' }}>{page.diff_summary.slice(0, 400)}</pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
