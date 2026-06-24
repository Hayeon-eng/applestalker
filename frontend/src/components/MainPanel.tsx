import { ReportData, DiffCopy, DiffImage, DiffSchema } from '../app/page';

interface Props {
  report: ReportData | null;
  onRefresh: () => void;
  isDemo?: boolean;
  isSnapshot?: boolean;
}

const SEV_COLOR: Record<string, string> = {
  Critical: '#EF4444',
  High: '#F97316',
  Medium: '#EAB308',
  Low: '#22C55E',
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

const STATUS_STYLE: Record<string, { bg: string; color: string; dot: string }> = {
  '위험': { bg: '#FEF2F2', color: '#991B1B', dot: '#EF4444' },
  '주의': { bg: '#FFF7ED', color: '#92400E', dot: '#F97316' },
  '양호': { bg: '#F0FDF4', color: '#166534', dot: '#22C55E' },
};

const shortUrl = (url: string) => {
  try {
    const u = new URL(url);
    const parts = u.pathname.replace(/\/$/, '').split('/').filter(Boolean);
    return parts.length === 0 ? u.hostname.replace('www.', '') : `${u.hostname.replace('www.', '')}/${parts[parts.length - 1]}`;
  } catch { return url.replace('https://', '').replace('www.', ''); }
};

const DEMO_COPY_CHANGES: DiffCopy[] = [
  {
    location: 'apple.com/iphone/ — og:title / Page Title',
    old: 'iPhone - Apple',
    new: 'iPhone 17 — Built for Apple Intelligence. - Apple',
  },
  {
    location: 'apple.com/iphone/ — Hero H1',
    old: 'iPhone.',
    new: 'Hello, Apple Intelligence.',
  },
  {
    location: 'apple.com/apple-intelligence/ — Meta Description',
    old: 'Meet Apple Intelligence, the personal intelligence system for iPhone, iPad, and Mac.',
    new: 'Apple Intelligence is here. Personal intelligence that understands you — privately and securely.',
  },
];

const DEMO_SCHEMA_CHANGES: DiffSchema[] = [
  {
    status: '추가',
    type: 'FAQPage (인라인 임베드)',
    old: '',
    new: '{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"What is Apple Intelligence?","acceptedAnswer":{"@type":"Answer","text":"Apple Intelligence is the personal intelligence system for iPhone, iPad, and Mac."}},{"@type":"Question","name":"Which devices support Apple Intelligence?","acceptedAnswer":{"@type":"Answer","text":"Available on iPhone 16 series, iPhone 17 series, iPad with M1 or later, and Mac with Apple silicon."}}]}',
  },
  {
    status: '추가',
    type: 'BreadcrumbList (인라인)',
    old: '',
    new: '{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"iPhone","item":"https://www.apple.com/iphone/"},{"@type":"ListItem","position":2,"name":"iPhone 17","item":"https://www.apple.com/iphone-17/"}]}',
  },
  {
    status: '수정',
    type: 'Product > offers',
    old: '{"@type":"Offer","price":"999.00","priceCurrency":"USD","availability":"https://schema.org/InStock"}',
    new: '{"@type":"AggregateOffer","lowPrice":"58300","priceCurrency":"KRW","offerCount":"4","description":"월 할부 기준, iPhone 17 128GB 기준"}',
  },
];

const DEMO_IMAGE_CHANGES: DiffImage[] = [
  {
    location: 'apple.com/iphone/ — Section 1 Hero',
    status: '교체',
    old: '/v/iphone/home/images/overview/hero/hero_iphone16_large__fkb9q06bpuuq_large.jpg',
    new: '/v/iphone/home/images/overview/hero/hero_iphone17_large__fkb9q06bpuuq_large.jpg',
  },
  {
    location: 'apple.com/iphone/ — Apple Intelligence 기능 섹션',
    status: '추가',
    new: '/v/iphone/home/images/overview/ai_writing_tools/writing_tools__f78bixs8xlea_large.jpg',
  },
  {
    location: 'apple.com/apple-intelligence/ — Hero Background',
    status: '교체',
    old: '/v/apple-intelligence/a/images/overview/hero/hero_static__fq07f7drjxia_medium.jpg',
    new: '/v/apple-intelligence/b/images/overview/hero/hero_animation__fq07f7drjxia_large.jpg',
  },
];

export default function MainPanel({ report, onRefresh, isDemo, isSnapshot }: Props) {
  if (!report) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF', fontSize: 13 }}>
        데이터를 선택해주세요
      </div>
    );
  }

  const topArea = (() => {
    const counts: Record<string, number> = {};
    (report.data_changes || []).forEach(c => {
      (c.change_types || []).forEach(t => { counts[t] = (counts[t] || 0) + 1; });
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || '—';
  })();

  const highPriorityCount = (report.data_changes || []).filter(c =>
    c.severity === 'Critical' || c.severity === 'High'
  ).length;

  const dangerAreas = report.analysis?.category_insights
    ? Object.entries(report.analysis.category_insights).filter(([, v]) => v.status === '위험')
    : [];
  const warningAreas = report.analysis?.category_insights
    ? Object.entries(report.analysis.category_insights).filter(([, v]) => v.status === '주의')
    : [];

  const priorityColor = report.analysis?.priority_label === 'Critical'
    ? '#EF4444'
    : report.analysis?.priority_label === 'High'
    ? '#F97316'
    : '#111318';

  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: '#111318' }}>
            {isSnapshot ? '현재 상태 분석' : '변경 감지 리포트'}
          </h1>
          <p style={{ fontSize: 11, color: '#6B7280', margin: '4px 0 0' }}>
            {report.site_name} · {report.tier} · {report.timestamp ? new Date(report.timestamp).toLocaleString('ko-KR') : '—'}
          </p>
        </div>
        <button
          onClick={onRefresh}
          style={{ padding: '8px 14px', borderRadius: 8, border: '1px solid #E8EAED', background: '#fff', cursor: 'pointer', fontSize: 12, color: '#111318' }}
        >
          🔄 새로고침
        </button>
      </div>

      {/* ─── 변경 있는 경우 ─── */}
      {!isSnapshot && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
            <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
              <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>변경된 URL</p>
              <p style={{ fontSize: 24, fontWeight: 700, margin: '4px 0 0', color: '#111318' }}>{report.total_changed_urls}</p>
            </div>
            <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
              <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>주요 변경 영역</p>
              <p style={{ fontSize: 12, fontWeight: 600, margin: '6px 0 0', color: '#111318', lineHeight: 1.4 }}>{topArea}</p>
            </div>
            <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
              <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>High 이상 페이지</p>
              <p style={{ fontSize: 24, fontWeight: 700, margin: '4px 0 0', color: highPriorityCount > 0 ? '#EF4444' : '#22C55E' }}>{highPriorityCount}</p>
            </div>
            <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
              <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>AI 우선순위</p>
              <p style={{ fontSize: 14, fontWeight: 600, margin: '4px 0 0', color: priorityColor }}>
                {report.analysis?.priority_label || '—'}
              </p>
            </div>
          </div>

          {report.data_changes && report.data_changes.length > 0 && (
            <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E8EAED', overflow: 'hidden' }}>
              <div style={{ padding: '14px 16px', borderBottom: '1px solid #E8EAED', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14 }}>📊</span>
                <p style={{ fontSize: 13, fontWeight: 600, margin: 0, color: '#111318' }}>감지된 변경 사항</p>
              </div>
              <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                {report.data_changes.map((change, i) => (
                  <div key={i} style={{ padding: '12px 16px', borderBottom: i < report.data_changes.length - 1 ? '1px solid #F3F4F6' : 'none', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: SEV_COLOR[change.severity] || '#9CA3AF', marginTop: 4, flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                        <p style={{ fontSize: 12, fontWeight: 600, margin: 0, color: '#111318', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {shortUrl(change.url)}
                        </p>
                        <span style={{ fontSize: 9, fontWeight: 600, padding: '1px 6px', borderRadius: 4, background: change.site === 'Apple' ? '#F3F4F6' : '#EFF6FF', color: change.site === 'Apple' ? '#374151' : '#1D4ED8' }}>
                          {change.site}
                        </span>
                        <span style={{ fontSize: 9, fontWeight: 600, padding: '1px 6px', borderRadius: 4, background: (SEV_COLOR[change.severity] || '#9CA3AF') + '18', color: SEV_COLOR[change.severity] || '#9CA3AF' }}>
                          {change.severity}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {(change.change_types || []).map((type, j) => {
                          const st = TYPE_STYLE[type] || { bg: '#F9FAFB', color: '#4B5563', border: '#E5E7EB' };
                          return (
                            <span key={j} style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: st.bg, color: st.color, border: `1px solid ${st.border}` }}>
                              {type}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.data_changes && report.data_changes.length > 0 && (
            <div style={{ marginTop: 14, background: '#fff', borderRadius: 12, border: '1px solid #E8EAED', overflow: 'hidden' }}>
              <div style={{ padding: '14px 16px', borderBottom: '1px solid #E8EAED', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14 }}>📸</span>
                <p style={{ fontSize: 13, fontWeight: 600, margin: 0, color: '#111318' }}>페이지 스크린샷</p>
                <span style={{ fontSize: 10, color: '#9CA3AF', marginLeft: 'auto' }}>크롤링 시 자동 캡처 (Desktop 1920×1080)</span>
              </div>
              <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {report.data_changes.map((change, i) => {
                  const backendBase = process.env.NEXT_PUBLIC_API_URL || '';
                  const screenshotSrc = change.screenshot_url ? `${backendBase}${change.screenshot_url}` : null;
                  return (
                    <div key={i} style={{ borderRadius: 8, border: '1px solid #E8EAED', overflow: 'hidden' }}>
                      <div style={{ padding: '8px 12px', background: '#F9FAFB', display: 'flex', alignItems: 'center', gap: 6, borderBottom: '1px solid #E8EAED' }}>
                        <div style={{ width: 6, height: 6, borderRadius: '50%', background: (SEV_COLOR[change.severity] || '#9CA3AF'), flexShrink: 0 }} />
                        <p style={{ fontSize: 11, fontWeight: 600, margin: 0, color: '#111318' }}>{shortUrl(change.url)}</p>
                        <span style={{ fontSize: 9, color: '#6B7280', marginLeft: 'auto' }}>{change.severity}</span>
                      </div>
                      {screenshotSrc ? (
                        <a href={screenshotSrc} target="_blank" rel="noopener noreferrer" style={{ display: 'block' }}>
                          <img
                            src={screenshotSrc}
                            alt={`Screenshot of ${change.url}`}
                            style={{ width: '100%', height: 160, objectFit: 'cover', objectPosition: 'top', display: 'block', cursor: 'zoom-in' }}
                            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                          />
                        </a>
                      ) : (
                        <div style={{ height: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F9FAFB', flexDirection: 'column', gap: 6 }}>
                          <span style={{ fontSize: 20 }}>🖥️</span>
                          <p style={{ fontSize: 10, color: '#9CA3AF', margin: 0 }}>실제 크롤링 시 스크린샷이 여기에 표시됩니다</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {report.data_changes && report.data_changes.length > 0 && (
            <div style={{ marginTop: 14, background: '#fff', borderRadius: 12, border: '1px solid #E8EAED', overflow: 'hidden' }}>
              <div style={{ padding: '14px 16px', borderBottom: '1px solid #E8EAED', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14 }}>✏️</span>
                <p style={{ fontSize: 13, fontWeight: 600, margin: 0, color: '#111318' }}>상세 변경 내역 (이전 → 이후)</p>
              </div>
              <div style={{ padding: '12px 16px' }}>
                <div style={{ marginBottom: 16 }}>
                  <p style={{ fontSize: 11, fontWeight: 700, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>📝 헤드라인 · 카피</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {(report.data_changes[0]?.diff_detail?.copies || DEMO_COPY_CHANGES).map((copy, idx) => (
                      <div key={idx} style={{ padding: '10px 12px', background: '#F9FAFB', borderRadius: 8, border: '1px solid #E8EAED' }}>
                        <p style={{ fontSize: 10, fontWeight: 600, color: '#6B7280', marginBottom: 6 }}>{copy.location}</p>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                            <span style={{ fontSize: 9, fontWeight: 700, color: '#EF4444', flexShrink: 0, marginTop: 2 }}>이전:</span>
                            <p style={{ fontSize: 11, color: '#111318', margin: 0, textDecoration: 'line-through', opacity: 0.7 }}>{copy.old}</p>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                            <span style={{ fontSize: 9, fontWeight: 700, color: '#22C55E', flexShrink: 0, marginTop: 2 }}>이후:</span>
                            <p style={{ fontSize: 11, color: '#111318', margin: 0, fontWeight: 600 }}>{copy.new}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ marginBottom: 16 }}>
                  <p style={{ fontSize: 11, fontWeight: 700, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>🔧 스키마 마크업</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {(report.data_changes[0]?.diff_detail?.schemas || DEMO_SCHEMA_CHANGES).map((schema, idx) => (
                      <div key={idx} style={{ padding: '8px 10px', background: schema.status === '추가' ? '#F0FDF4' : schema.status === '제거' ? '#FEF2F2' : '#EFF6FF', borderRadius: 6, border: `1px solid ${schema.status === '추가' ? '#BBF7D0' : schema.status === '제거' ? '#FECACA' : '#BFDBFE'}` }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                          <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 4, background: schema.status === '추가' ? '#22C55E' : schema.status === '제거' ? '#EF4444' : '#2563EB', color: '#fff' }}>{schema.status}</span>
                          <span style={{ fontSize: 10, fontWeight: 600, color: '#111318' }}>{schema.type}</span>
                        </div>
                        {schema.new && <p style={{ fontSize: 9, color: '#6B7280', margin: 0, fontFamily: 'monospace', wordBreak: 'break-all', maxHeight: 60, overflowY: 'auto' }}>{schema.new}</p>}
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <p style={{ fontSize: 11, fontWeight: 700, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>🖼️ 이미지</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {(report.data_changes[0]?.diff_detail?.images || DEMO_IMAGE_CHANGES).map((img, idx) => (
                      <div key={idx} style={{ padding: '8px 10px', background: img.status === '교체' ? '#FFF7ED' : img.status === '추가' ? '#EFF6FF' : '#FEF2F2', borderRadius: 6, border: `1px solid ${img.status === '교체' ? '#FED7AA' : img.status === '추가' ? '#BFDBFE' : '#FECACA'}` }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                          <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 4, background: img.status === '교체' ? '#C2410C' : img.status === '추가' ? '#2563EB' : '#EF4444', color: '#fff' }}>{img.status}</span>
                          <span style={{ fontSize: 10, fontWeight: 600, color: '#111318' }}>{img.location}</span>
                        </div>
                        <div style={{ fontSize: 9, color: '#6B7280' }}>
                          {img.old && <p style={{ margin: '2px 0', textDecoration: 'line-through', opacity: 0.7 }}>이전: {img.old}</p>}
                          {img.new && <p style={{ margin: '2px 0', fontWeight: 600 }}>이후: {img.new}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ─── 변경 없는 경우 ─── */}
      {isSnapshot && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
            <div style={{ background: '#F0FDF4', borderRadius: 12, padding: 16, border: '1px solid #BBF7D0' }}>
              <p style={{ fontSize: 10, color: '#166534', margin: 0, textTransform: 'uppercase' }}>변경 감지</p>
              <p style={{ fontSize: 18, fontWeight: 700, margin: '6px 0 0', color: '#15803D' }}>없음 ✅</p>
            </div>
            <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
              <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>감시 사이트</p>
              <p style={{ fontSize: 13, fontWeight: 600, margin: '6px 0 0', color: '#111318' }}>Apple · Samsung</p>
            </div>
            <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
              <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>분석 레벨</p>
              <p style={{ fontSize: 14, fontWeight: 600, margin: '4px 0 0', color: priorityColor }}>
                {report.analysis?.priority_label || '—'}
              </p>
            </div>
          </div>

          {report.analysis?.consumer_perception && (
            <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E8EAED', padding: '14px 16px', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{ fontSize: 14 }}>🍎</span>
                <p style={{ fontSize: 13, fontWeight: 600, margin: 0, color: '#111318' }}>Apple 현재 포지션</p>
              </div>
              <p style={{ fontSize: 12, color: '#374151', margin: 0, lineHeight: 1.7 }}>
                {report.analysis.consumer_perception}
              </p>
            </div>
          )}

          {(dangerAreas.length > 0 || warningAreas.length > 0) && (
            <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E8EAED', overflow: 'hidden' }}>
              <div style={{ padding: '14px 16px', borderBottom: '1px solid #E8EAED', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14 }}>🔷</span>
                <p style={{ fontSize: 13, fontWeight: 600, margin: 0, color: '#111318' }}>Samsung 핵심 개선 포인트</p>
                <span style={{ fontSize: 10, color: '#9CA3AF', marginLeft: 'auto' }}>영역별 상세 → 우측 패널</span>
              </div>
              <div style={{ padding: '10px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[...dangerAreas, ...warningAreas].slice(0, 4).map(([key, value]) => {
                  const st = STATUS_STYLE[value.status] || STATUS_STYLE['양호'];
                  const topPoint = value.improvement_points?.[0];
                  return (
                    <div key={key} style={{ padding: '10px 12px', borderRadius: 10, background: st.bg, border: `1px solid ${st.dot}30`, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                      <div style={{ width: 7, height: 7, borderRadius: '50%', background: st.dot, marginTop: 5, flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                          <p style={{ fontSize: 11, fontWeight: 700, margin: 0, color: '#111318' }}>{key}</p>
                          <span style={{ fontSize: 9, fontWeight: 600, padding: '1px 6px', borderRadius: 10, background: `${st.dot}20`, color: st.color }}>{value.status}</span>
                        </div>
                        <p style={{ fontSize: 10, margin: 0, color: '#4B5563', lineHeight: 1.5 }}>{value.summary}</p>
                        {topPoint && (
                          <p style={{ fontSize: 10, margin: '4px 0 0', color: st.color, fontWeight: 600 }}>→ {topPoint}</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
