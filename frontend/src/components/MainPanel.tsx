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

const shortUrl = (url: string) => {
  try {
    const u = new URL(url);
    const parts = u.pathname.replace(/\/$/, '').split('/').filter(Boolean);
    return parts.length === 0 ? u.hostname.replace('www.', '') : `${u.hostname.replace('www.', '')}/${parts[parts.length - 1]}`;
  } catch { return url.replace('https://', '').replace('www.', ''); }
};

// 데모용 카피 변경 예시 데이터
const DEMO_COPY_CHANGES: DiffCopy[] = [
  { location: 'Hero H1', old: 'Hello, Future.', new: 'Hello, Apple Intelligence.' },
  { location: 'Meta Description', old: 'iPhone 17 Pro 의 새로운 기능을 만나보세요.', new: 'iPhone 17 Pro. Apple Intelligence 가 모든 것을 바꿉니다.' },
  { location: 'Subheadline', old: 'Pro 급 카메라. Pro 급 성능.', new: 'AI 가 만드는 프로급 결과물.' },
];

// 데모용 스키마 변경 예시 데이터
const DEMO_SCHEMA_CHANGES: DiffSchema[] = [
  { status: '추가', type: 'speakable', old: '', new: '{"@type":"speakable","cssSelector":["h1","h2"]}' },
  { status: '추가', type: 'FAQPage', old: '', new: '{"@type":"FAQPage","mainEntity":[{"@type":"Question","name":"Apple Intelligence 란?","acceptedAnswer":{"@type":"Answer","text":"개인화된 AI 기능입니다."}}]}' },
  { status: '수정', type: 'Product', old: '{"price":"1399000"}', new: '{"price":"월 58,300 원~"}' },
];

// 데모용 이미지 변경 예시 데이터
const DEMO_IMAGE_CHANGES: DiffImage[] = [
  { location: 'Hero Image', status: '교체', old: 'product-shot.jpg', new: 'lifestyle-group.jpg' },
  { location: 'Feature Section', status: '추가', new: 'ai-features-animation.webp' },
];

export default function MainPanel({ report, onRefresh, isDemo, isSnapshot }: Props) {
  if (!report) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF', fontSize: 13 }}>
        데이터를 선택해주세요
      </div>
    );
  }

  const totalAdded = (report.data_changes || []).reduce((sum, c) => sum + (c.added || 0), 0);
  const totalRemoved = (report.data_changes || []).reduce((sum, c) => sum + (c.removed || 0), 0);

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

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
          <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>변경된 URL</p>
          <p style={{ fontSize: 24, fontWeight: 700, margin: '4px 0 0', color: '#111318' }}>{report.total_changed_urls}</p>
        </div>
        <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
          <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>추가된 라인</p>
          <p style={{ fontSize: 24, fontWeight: 700, margin: '4px 0 0', color: '#22C55E' }}>+{totalAdded}</p>
        </div>
        <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
          <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>제거된 라인</p>
          <p style={{ fontSize: 24, fontWeight: 700, margin: '4px 0 0', color: '#EF4444' }}>-{totalRemoved}</p>
        </div>
        <div style={{ background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #E8EAED' }}>
          <p style={{ fontSize: 10, color: '#6B7280', margin: 0, textTransform: 'uppercase' }}>우선순위</p>
          <p style={{ fontSize: 14, fontWeight: 600, margin: '4px 0 0', color: report.analysis?.priority_label === 'Critical' ? '#EF4444' : '#111318' }}>
            {report.analysis?.priority_label || '—'}
          </p>
        </div>
      </div>

      {/* Data Changes */}
      {!isSnapshot && report.data_changes && report.data_changes.length > 0 && (
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E8EAED', overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid #E8EAED', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14 }}>📊</span>
            <p style={{ fontSize: 13, fontWeight: 600, margin: 0, color: '#111318' }}>감지된 변경 사항</p>
          </div>
          <div style={{ maxHeight: 400, overflowY: 'auto' }}>
            {report.data_changes.map((change, i) => (
              <div key={i} style={{ padding: '12px 16px', borderBottom: i < report.data_changes.length - 1 ? '1px solid #F3F4F6' : 'none', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                <div style={{ width: 3, height: 3, borderRadius: '50%', background: SEV_COLOR[change.severity] || '#9CA3AF', marginTop: 6, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <p style={{ fontSize: 12, fontWeight: 600, margin: 0, color: '#111318', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {shortUrl(change.url)}
                    </p>
                    <span style={{ fontSize: 9, fontWeight: 600, padding: '1px 6px', borderRadius: 4, background: change.site === 'Apple' ? '#F3F4F6' : '#EFF6FF', color: change.site === 'Apple' ? '#374151' : '#1D4ED8' }}>
                      {change.site}
                    </span>
                    <span style={{ fontSize: 9, color: '#6B7280' }}>{change.tier}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
                    {(change.change_types || []).map((type, j) => {
                      const st = TYPE_STYLE[type] || { bg: '#F9FAFB', color: '#4B5563', border: '#E5E7EB' };
                      return (
                        <span key={j} style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: st.bg, color: st.color, border: `1px solid ${st.border}` }}>
                          {type}
                        </span>
                      );
                    })}
                  </div>
                  <div style={{ display: 'flex', gap: 12, fontSize: 10 }}>
                    <span style={{ color: '#22C55E' }}>+{change.added}</span>
                    <span style={{ color: '#EF4444' }}>-{change.removed}</span>
                    <span style={{ color: '#6B7280' }}>Severity: {change.severity}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No Changes Message */}
      {isSnapshot && (
        <div style={{ background: '#F0FDF4', borderRadius: 12, border: '1px solid #BBF7D0', padding: 20, textAlign: 'center' }}>
          <p style={{ fontSize: 14, fontWeight: 600, margin: 0, color: '#15803D' }}>✅ 변경 사항이 감지되지 않았습니다</p>
          <p style={{ fontSize: 11, color: '#166534', margin: '4px 0 0' }}>현재 상태 기반 경쟁 분석을 제공합니다 (우측 패널)</p>
        </div>
      )}

      {/* Copy Change Examples - Main Pane Detailed View */}
      {!isSnapshot && report.data_changes && report.data_changes.length > 0 && (
        <div style={{ marginTop: 14, background: '#fff', borderRadius: 12, border: '1px solid #E8EAED', overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid #E8EAED', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14 }}>✏️</span>
            <p style={{ fontSize: 13, fontWeight: 600, margin: 0, color: '#111318' }}>카피 변경 예시 (이전 → 이후)</p>
          </div>
          <div style={{ padding: '12px 16px' }}>
            {/* Copy Changes */}
            <div style={{ marginBottom: 16 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>📝 헤드라인/카피 변경</p>
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

            {/* Schema Changes */}
            <div style={{ marginBottom: 16 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>🔧 스키마 마크업 변경 (+82 줄 추가)</p>
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

            {/* Image Changes */}
            <div>
              <p style={{ fontSize: 11, fontWeight: 700, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>🖼️ 이미지 변경 (-34 줄 제거)</p>
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
    </div>
  );
}
