import { ReactNode } from 'react';
import { Analysis, CategoryInsight, ReportData } from '../app/page';

interface Props { 
  analysis: Analysis | null; 
  isSnapshot?: boolean;
  report?: ReportData | null;
}

const CARD: React.CSSProperties = {
  background: 'rgba(255,255,255,0.68)',
  backdropFilter: 'saturate(180%) blur(20px)',
  WebkitBackdropFilter: 'saturate(180%) blur(20px)',
  border: '0.5px solid rgba(255,255,255,0.6)',
  borderRadius: 14,
  padding: '14px 16px',
};

const categoryConfig: Record<string, { bg: string; color: string; label: string; emoji: string }> = {
  AI:      { bg: 'rgba(37,99,235,0.1)',   color: '#1A4FA8', label: 'AI',      emoji: '🤖' },
  UX:      { bg: 'rgba(52,199,89,0.1)',   color: '#1A6B3A', label: 'UX',      emoji: '✨' },
  Brand:   { bg: 'rgba(175,82,222,0.1)',  color: '#5B2DA0', label: 'Brand',   emoji: '💎' },
  Product: { bg: 'rgba(255,149,0,0.1)',   color: '#8A4500', label: 'Product', emoji: '📦' },
  Pricing: { bg: 'rgba(255,59,48,0.1)',   color: '#A0001A', label: 'Pricing', emoji: '💰' },
  General: { bg: 'rgba(0,0,0,0.05)',      color: '#555555', label: '일반',    emoji: '📌' },
};

const priorityConfig: Record<string, { bg: string; color: string }> = {
  Critical: { bg: 'rgba(255,59,48,0.1)',  color: '#A0001A' },
  High:     { bg: 'rgba(255,149,0,0.1)',  color: '#8A4500' },
  Medium:   { bg: 'rgba(255,204,0,0.12)', color: '#7A5200' },
  Low:      { bg: 'rgba(52,199,89,0.1)',  color: '#1A6B3A' },
};

const SEVEN_CATS: { key: string; emoji: string; label: string }[] = [
  { key: 'SEO·AI 인덱싱',  emoji: '🔎', label: 'SEO·AI 인덱싱' },
  { key: '가격·프로모션',   emoji: '💰', label: '가격·프로모션' },
  { key: '헤드라인·슬로건', emoji: '✏️', label: '헤드라인·슬로건' },
  { key: '비주얼·미디어',   emoji: '🖼',  label: '비주얼·미디어' },
  { key: '내비게이션·구조', emoji: '🗂',  label: '내비게이션·구조' },
  { key: 'CTA·구매 흐름',  emoji: '🛒', label: 'CTA·구매 흐름' },
  { key: '본문·기능 설명',  emoji: '📄', label: '본문·기능 설명' },
];

const STATUS_STYLE: Record<string, { bg: string; color: string; dot: string; label: string }> = {
  '양호': { bg: 'rgba(52,199,89,0.08)',  color: '#1A6B3A', dot: '#34C759', label: '양호' },
  '주의': { bg: 'rgba(255,149,0,0.08)',  color: '#8A4500', dot: '#FF9500', label: '주의' },
  '위험': { bg: 'rgba(215,0,21,0.08)',   color: '#A0001A', dot: '#D70015', label: '위험' },
};

function parseInsight(raw: string) {
  const sep = raw.indexOf(': ');
  if (sep > 0 && sep < 12) return { category: raw.slice(0, sep), text: raw.slice(sep + 2) };
  return { category: 'General', text: raw };
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ ...CARD }}>
      <p style={{ fontSize: 10, fontWeight: 600, color: 'rgba(0,0,0,0.35)', margin: '0 0 10px', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{title}</p>
      {children}
    </div>
  );
}

function CategoryInsightsPanel({ data }: { data: Record<string, CategoryInsight> }) {
  const statusOrder: Record<string, number> = { '위험': 0, '주의': 1, '양호': 2 };
  const sorted = [...SEVEN_CATS].sort((a, b) => {
    const sa = statusOrder[data[a.key]?.status ?? '양호'] ?? 2;
    const sb = statusOrder[data[b.key]?.status ?? '양호'] ?? 2;
    return sa - sb;
  });

  return (
    <div style={{ ...CARD }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
        <span style={{ fontSize: 14 }}>📊</span>
        <p style={{ fontSize: 12, fontWeight: 600, margin: 0, color: '#1D1D1F', letterSpacing: '-0.3px' }}>7 개 영역별 현황 분석</p>
      </div>
      <p style={{ fontSize: 10, color: 'rgba(0,0,0,0.35)', margin: '0 0 12px', lineHeight: 1.5 }}>
        Apple vs Samsung 7 개 영역 경쟁 현황
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {sorted.map(({ key, emoji, label }) => {
          const insight = data[key];
          if (!insight) return null;
          const st = STATUS_STYLE[insight.status] || STATUS_STYLE['양호'];
          return (
            <div key={key} style={{ borderRadius: 10, border: `0.5px solid ${st.dot}30`, background: st.bg, overflow: 'hidden' }}>
              <div style={{ padding: '8px 11px 7px', display: 'flex', alignItems: 'center', gap: 7 }}>
                <span style={{ fontSize: 13 }}>{emoji}</span>
                <p style={{ fontSize: 11, fontWeight: 600, margin: 0, color: '#1D1D1F', flex: 1, letterSpacing: '-0.2px' }}>{label}</p>
                <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 20, background: `${st.dot}18`, color: st.color, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: st.dot, display: 'inline-block' }} />
                  {st.label}
                </span>
              </div>
              <div style={{ padding: '0 11px 9px 31px' }}>
                <p style={{ fontSize: 10, color: 'rgba(0,0,0,0.55)', margin: 0, lineHeight: 1.65 }}>{insight.summary}</p>
                {(insight.apple_score !== undefined && insight.samsung_score !== undefined) && (
                  <div style={{ marginTop: 7, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {([
                      { label: '🍎 Apple', score: insight.apple_score, color: '#111318' },
                      { label: '🔷 Samsung', score: insight.samsung_score, color: '#2563EB' },
                    ] as { label: string; score: number; color: string }[]).map(({ label, score, color }) => (
                      <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 9, color: 'rgba(0,0,0,0.45)', width: 58, flexShrink: 0 }}>{label}</span>
                        <div style={{ flex: 1, height: 4, background: 'rgba(0,0,0,0.08)', borderRadius: 2, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${score * 10}%`, background: color, borderRadius: 2 }} />
                        </div>
                        <span style={{ fontSize: 9, fontWeight: 700, color, width: 14, textAlign: 'right', flexShrink: 0 }}>{score}</span>
                      </div>
                    ))}
                  </div>
                )}
                {insight.improvement_points && insight.improvement_points.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    {insight.improvement_points.map((pt: string, idx: number) => (
                      <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 4, marginTop: 3 }}>
                        <span style={{ fontSize: 9, color: st.dot, flexShrink: 0, marginTop: 1 }}>→</span>
                        <p style={{ fontSize: 10, color: st.color, margin: 0, lineHeight: 1.5, fontWeight: 500 }}>{pt}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function InsightsPanel({ analysis, isSnapshot }: Props) {
  if (!analysis) {
    return (
      <div style={{ ...CARD, color: 'rgba(0,0,0,0.3)', fontSize: 12, textAlign: 'center' }}>
        분석 데이터 없음
      </div>
    );
  }

  const pc = priorityConfig[analysis.priority_label] || priorityConfig.Low;
  const hasCategoryInsights =
    analysis.category_insights &&
    Object.keys(analysis.category_insights).length > 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

      <Section title={isSnapshot ? '현재 상태 요약' : '분석 개요'}>
        <p style={{ fontSize: 12, color: '#1D1D1F', lineHeight: 1.7, margin: '0 0 10px', letterSpacing: '-0.1px' }}>
          {analysis.change_summary || '—'}
        </p>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 10, fontWeight: 500, padding: '3px 9px', borderRadius: 20, background: pc.bg, color: pc.color }}>
            {analysis.priority_label}
          </span>
          {analysis.functional_area && (
            <span style={{ fontSize: 10, padding: '3px 9px', borderRadius: 20, background: 'rgba(0,0,0,0.05)', color: 'rgba(0,0,0,0.45)' }}>
              {analysis.functional_area}
            </span>
          )}
        </div>
      </Section>

      {hasCategoryInsights && (
        <CategoryInsightsPanel data={analysis.category_insights!} />
      )}

      <div style={{ ...CARD }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          <span style={{ fontSize: 14 }}>⚡</span>
          <p style={{ fontSize: 12, fontWeight: 600, margin: 0, color: '#1D1D1F', letterSpacing: '-0.3px' }}>핵심 인사이트</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {(analysis.insights || []).length === 0 ? (
            <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.3)' }}>인사이트 없음</p>
          ) : (
            (analysis.insights || []).map((raw, i) => {
              const { category, text } = parseInsight(raw);
              const cfg = categoryConfig[category] || categoryConfig.General;
              return (
                <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '8px 10px', borderRadius: 9, background: 'rgba(0,0,0,0.03)', border: '0.5px solid rgba(0,0,0,0.06)' }}>
                  <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 5, background: cfg.bg, color: cfg.color, whiteSpace: 'nowrap', flexShrink: 0, marginTop: 1, display: 'flex', alignItems: 'center', gap: 3 }}>
                    <span>{cfg.emoji}</span> {cfg.label}
                  </span>
                  <p style={{ fontSize: 11, lineHeight: 1.6, margin: 0, color: '#1D1D1F', letterSpacing: '-0.1px' }}>{text}</p>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div style={{ ...CARD }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
          <span style={{ fontSize: 12 }}>🔍</span>
          <p style={{ fontSize: 12, fontWeight: 600, margin: 0, color: '#1D1D1F', letterSpacing: '-0.3px' }}>삼성 vs 경쟁사 비교</p>
        </div>
        <p style={{ fontSize: 12, color: '#1D1D1F', lineHeight: 1.7, margin: 0, letterSpacing: '-0.1px' }}>
          {analysis.samsung_comparison || '—'}
        </p>
      </div>

      <div style={{ background: 'rgba(37,99,235,0.07)', backdropFilter: 'saturate(180%) blur(20px)', WebkitBackdropFilter: 'saturate(180%) blur(20px)', borderRadius: 14, border: '0.5px solid rgba(37,99,235,0.18)', padding: '14px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
          <span style={{ fontSize: 12 }}>🎯</span>
          <p style={{ fontSize: 12, fontWeight: 600, margin: 0, color: '#1A3A7A', letterSpacing: '-0.3px' }}>즉시 실행 액션</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          {(analysis.action_items || []).length === 0 ? (
            <p style={{ fontSize: 12, color: 'rgba(37,99,235,0.5)' }}>액션 없음</p>
          ) : (
            (analysis.action_items || []).map((item, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '8px 10px', borderRadius: 9, background: 'rgba(255,255,255,0.65)', border: '0.5px solid rgba(37,99,235,0.15)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)' }}>
                <span style={{ fontSize: 11, color: '#2563EB', fontWeight: 700, flexShrink: 0 }}>{i + 1}</span>
                <p style={{ fontSize: 11, lineHeight: 1.6, margin: 0, color: '#1A3A7A', letterSpacing: '-0.1px' }}>{item}</p>
              </div>
            ))
          )}
        </div>
      </div>

    </div>
  );
}
