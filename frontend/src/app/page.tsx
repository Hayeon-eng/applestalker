'use client';
import { useState, useEffect, useCallback, useRef } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/* ── 타입 ── */
interface Change {
  id: number; url: string; site: string; level: 'High'|'Medium'|'Low';
  category: string; field: string; summary: string;
  before?: string; after?: string; evidence?: Record<string, any>;
}
interface Report {
  has_data: boolean; run_id?: string; site?: string; timestamp?: string;
  has_changes?: boolean; by_category?: Record<string, number>;
  changes?: Change[];
  analysis?: { summary: string; aeo_implications: string; insights: any[]; actions: any[] };
  message?: string;
}
interface RunItem { run_id: string; site: string; timestamp: string; pages: number; changes: number; }

/* ── 카테고리 정의 (4칸) ── */
const CATS = [
  { key: '데이터·스키마', icon: '◧', desc: '스키마·HTML 구조·내비게이션' },
  { key: '카피', icon: '¶', desc: '제목·본문·문구·FAQ' },
  { key: '가격·프로모션', icon: '₩', desc: '가격·CTA·사전예약·Trade-in' },
  { key: '비주얼', icon: '▣', desc: '히어로/이미지 변화' },
];
const LV_COLOR: Record<string,string> = { High:'var(--high)', Medium:'var(--med)', Low:'var(--low)' };
const SITE_LABEL: Record<string,{t:string;c:string}> = {
  apple: { t: '경쟁사 · Apple', c: 'var(--apple)' },
  samsung: { t: '당사 · Samsung', c: 'var(--samsung)' },
};

/* ── 실데이터 없을 때 보여줄 예시(실제 사이트 관찰 기반, 라벨 명시) ── */
const SAMPLE: Report = {
  has_data: true, run_id: 'sample', site: 'samsung',
  timestamp: new Date().toISOString(), has_changes: true,
  by_category: { '데이터·스키마': 2, '카피': 2, '가격·프로모션': 1, '비주얼': 1 },
  changes: [
    { id: 1, url: 'https://www.apple.com/apple-intelligence/', site: 'apple', level: 'High',
      category: '카피', field: 'h1',
      summary: 'H1 메시지 변경 — 차세대 Apple Intelligence·Siri 전면화',
      before: 'Apple Intelligence', after: 'Introducing the next generation of Apple Intelligence and Siri',
      evidence: { 추가된문장: 1 } },
    { id: 2, url: 'https://www.apple.com/apple-intelligence/', site: 'apple', level: 'Medium',
      category: '데이터·스키마', field: 'navigation',
      summary: '신규 기능 진입점 추가 — Safari "Notify Me"(가격·재입고 변화 알림)',
      before: '', after: 'Safari Notify Me', evidence: { 변화유형: '내비 항목 추가' } },
    { id: 3, url: 'https://www.samsung.com/sg/galaxy-ai/', site: 'samsung', level: 'High',
      category: '가격·프로모션', field: 'disclaimer',
      summary: '프로모션 디스클레이머 — "Galaxy AI free until end of 2025" 문구 노출',
      before: '', after: 'Galaxy AI features free until the end of 2025',
      evidence: { 감지키워드: 'free / 2025' } },
    { id: 4, url: 'https://www.samsung.com/sg/galaxy-ai/', site: 'samsung', level: 'Medium',
      category: '카피', field: 'h1',
      summary: 'H1 슬로건 변경', before: 'Galaxy AI',
      after: 'Galaxy AI, a true AI companion', evidence: { 추가된문장: 1 } },
    { id: 5, url: 'https://www.samsung.com/sg/', site: 'samsung', level: 'Low',
      category: '비주얼', field: 'screenshot',
      summary: '메인 히어로 비주얼 변화 감지', before: 'phash …', after: 'phash …',
      evidence: { '이미지차이(거리)': 14 } },
    { id: 6, url: 'https://www.apple.com/iphone/', site: 'apple', level: 'Medium',
      category: '데이터·스키마', field: 'schema_type',
      summary: '구조화 데이터 변화 — 신규 제품 라인업(iPhone 17 Pro/Air/17/17e) 반영',
      before: 'Product×3', after: 'Product×4', evidence: { 변화유형: '스키마 항목 증가' } },
  ],
  analysis: {
    summary: '예시 데이터입니다 (실제 사이트 관찰 기반). 실제 크롤 실행 시 이 자리에 자동 분석이 채워집니다.',
    aeo_implications: '애플은 apple-intelligence 페이지에서 차세대 Siri를 전면화하고 "Notify Me"(변화 알림) 기능을 강조 중. 당사는 Galaxy AI 무료 기간 디스클레이머가 노출되어 프로모션 종료 시점 메시지 점검이 필요.',
    insights: [], actions: [],
  },
};

export default function Page() {
  const [tab, setTab] = useState<'changes'|'compare'>('changes');
  const [report, setReport] = useState<Report|null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [sel, setSel] = useState<Change|null>(null);
  const [crawling, setCrawling] = useState(false);
  const [showUrlMgr, setShowUrlMgr] = useState(false);
  const [usingSample, setUsingSample] = useState(false);
  const [compare, setCompare] = useState<any>(null);
  const sse = useRef<EventSource|null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/latest-report`);
      const j = await r.json();
      if (j.has_data) { setReport(j); setUsingSample(false); }
      else { setReport(SAMPLE); setUsingSample(true); }
    } catch { setReport(SAMPLE); setUsingSample(true); }
    try { const r = await fetch(`${API}/api/runs`); setRuns((await r.json()).runs || []); } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadCompare = useCallback(async () => {
    try { const r = await fetch(`${API}/api/compare`); setCompare(await r.json()); }
    catch { setCompare({ status: 'insufficient_data' }); }
  }, []);
  useEffect(() => { if (tab === 'compare') loadCompare(); }, [tab, loadCompare]);

  const startCrawl = async () => {
    try {
      await fetch(`${API}/trigger-crawl/all`, { method: 'POST' });
      setCrawling(true);
      sse.current?.close();
      const es = new EventSource(`${API}/api/crawl-progress`); sse.current = es;
      es.onmessage = (e) => {
        try { const ev = JSON.parse(e.data);
          if (ev.type === 'status' && !ev.crawling) { es.close(); setCrawling(false); load(); }
        } catch {}
      };
      es.onerror = () => { es.close(); setCrawling(false); };
    } catch { alert('백엔드에 연결할 수 없습니다. NEXT_PUBLIC_API_URL 확인'); }
  };

  const addUrl = async () => {
    const el = document.getElementById('newurl') as HTMLInputElement;
    const u = el?.value.trim(); if (!u) return;
    try { await fetch(`${API}/api/urls`, { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ url: u }) }); el.value=''; setShowUrlMgr(false); alert('추가됨 — 다음 크롤부터 반영'); }
    catch { alert('추가 실패'); }
  };

  const changes = report?.changes || [];
  const byCat = report?.by_category || {};

  return (
    <div style={{ display:'grid', gridTemplateColumns:'234px 1fr 372px', height:'100vh', overflow:'hidden' }}>
      {/* ── 좌측 레일 ── */}
      <aside style={{ background:'var(--rail)', borderRight:'1px solid var(--line)', overflow:'auto' }}>
        <div style={{ padding:'20px 18px 14px' }}>
          <div style={{ fontSize:19, fontWeight:700 }}>Apple Stalker</div>
          <div className="mono" style={{ fontSize:11, color:'var(--sec)', marginTop:2 }}>경쟁사 웹 변화 감지 · AEO</div>
        </div>

        <RailSec t="모니터링 대상" />
        <Target label="당사 · Samsung SG" dot="var(--samsung)" />
        <Target label="경쟁사 · Apple US" dot="var(--apple)" />

        <RailSec t="중요도 기준" />
        <div style={{ margin:'0 12px 6px' }}>
          {[['High','즉시 대응 — 가격·구매·구조(AI노출)','var(--high)'],
            ['Medium','검토 — 카피·섹션·일부 구조','var(--med)'],
            ['Low','참고 — 단어·미세·비주얼','var(--low)']].map(([k,d,c]) => (
            <div key={k} style={{ display:'flex', gap:9, alignItems:'flex-start', padding:'7px 8px',
              background:'#fff', borderRadius:10, marginBottom:6, boxShadow:'var(--shadow-sm)' }}>
              <span style={{ width:9, height:9, borderRadius:3, background:c as string, marginTop:4, flex:'0 0 auto' }} />
              <div><div style={{ fontWeight:700, fontSize:12 }}>{k}</div>
                <div style={{ fontSize:11, color:'var(--sec)' }}>{d}</div></div>
            </div>
          ))}
        </div>

        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'14px 16px 6px' }}>
          <span style={{ fontSize:11, color:'var(--sec)', fontWeight:600 }}>크롤 이력</span>
          <button onClick={() => setShowUrlMgr(v=>!v)} title="모니터링 URL 추가"
            style={{ fontSize:11, color:'var(--sec)', fontWeight:600, padding:'2px 7px',
              borderRadius:7, background:'rgba(0,0,0,.045)' }}>＋ URL</button>
        </div>
        {showUrlMgr && (
          <div style={{ margin:'0 12px 8px', display:'flex', gap:6 }}>
            <input id="newurl" placeholder="https://…" className="mono"
              style={{ flex:1, border:'1px solid var(--line2)', borderRadius:9, padding:'8px 10px', fontSize:11 }} />
            <button onClick={addUrl} style={{ background:'var(--blue)', color:'#fff', borderRadius:9, padding:'0 12px', fontSize:11, fontWeight:600 }}>추가</button>
          </div>
        )}
        <div style={{ padding:'0 10px 16px' }}>
          {runs.length === 0 && <div style={{ color:'var(--ter)', fontSize:11, padding:'6px 8px' }}>아직 없음</div>}
          {runs.map(r => (
            <div key={r.run_id} style={{ padding:'8px 10px', borderRadius:10, marginBottom:2 }}>
              <div className="mono" style={{ fontSize:11, fontWeight:600 }}>{r.timestamp?.slice(5,16)}</div>
              <div style={{ fontSize:11, color:'var(--sec)' }}>{r.site} · {r.pages}p · {r.changes? r.changes+' 변경':'변경 없음'}</div>
            </div>
          ))}
        </div>
      </aside>

      {/* ── 중앙 ── */}
      <main style={{ overflow:'auto' }}>
        <div style={{ position:'sticky', top:0, zIndex:5, background:'rgba(242,242,247,.72)',
          backdropFilter:'saturate(180%) blur(20px)', borderBottom:'1px solid var(--line)',
          padding:'14px 24px', display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
          <div style={{ display:'inline-flex', background:'rgba(118,118,128,.12)', borderRadius:12, padding:3, gap:2 }}>
            <Seg on={tab==='changes'} onClick={()=>setTab('changes')}>변경점</Seg>
            <Seg on={tab==='compare'} onClick={()=>setTab('compare')}>현황 비교 (삼성↔애플)</Seg>
          </div>
          <span style={{ flex:1 }} />
          <a href={`${API}/api/export/xlsx`} style={btn}>⤓ Excel</a>
          <a href={`${API}/api/export/pptx`} style={btn}>⤓ PPTX</a>
          <button onClick={startCrawl} disabled={crawling}
            style={{ ...btn, background:'var(--blue)', color:'#fff', opacity:crawling?0.6:1 }}>
            {crawling ? '크롤 중…' : '크롤 실행'}</button>
        </div>

        {tab === 'changes' ? (
          <div style={{ padding:'16px 24px 60px' }}>
            <Ctx>
              <b>가장 최근 크롤에서 감지된 변경점입니다.</b> 카테고리별로 묶었고, 배지로 <b style={{color:'var(--apple)'}}>경쟁사(애플)</b>·<b style={{color:'var(--samsung)'}}>당사(삼성)</b>를 구분합니다. 항목을 누르면 우측에 무엇이 어떻게 바뀌었는지 표시됩니다.
            </Ctx>
            {usingSample && <SampleBanner />}
            {report && !report.has_changes && !usingSample && <NoChange analysis={report.analysis} />}
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginTop:14 }}>
              {CATS.map(cat => (
                <CategoryCard key={cat.key} cat={cat} count={byCat[cat.key]||0}
                  items={changes.filter(c=>c.category===cat.key)} sel={sel} onSel={setSel} />
              ))}
            </div>
          </div>
        ) : (
          <ComparePane data={compare} />
        )}
      </main>

      {/* ── 우측 인스펙터 ── */}
      <aside style={{ background:'var(--rail)', borderLeft:'1px solid var(--line)', overflow:'auto', padding:'16px 14px' }}>
        {sel ? <Inspector c={sel} /> : <InspectorDefault report={report} />}
      </aside>
    </div>
  );
}

/* ── 작은 컴포넌트들 ── */
const btn: React.CSSProperties = { background:'#fff', color:'var(--label)', borderRadius:11,
  padding:'8px 14px', fontSize:12.5, fontWeight:600, boxShadow:'var(--shadow-sm)', textDecoration:'none' };

function Seg({ on, onClick, children }: any) {
  return <button onClick={onClick} style={{ borderRadius:9, padding:'7px 13px', fontSize:12, fontWeight:600,
    color: on?'var(--label)':'var(--label2)', background:on?'#fff':'transparent',
    boxShadow:on?'var(--shadow-sm)':'none' }}>{children}</button>;
}
function RailSec({ t }: { t:string }) {
  return <div style={{ padding:'14px 18px 7px', fontSize:11, color:'var(--sec)', fontWeight:600 }}>{t}</div>;
}
function Target({ label, dot }: { label:string; dot:string }) {
  return <div style={{ margin:'1px 10px', padding:'9px 12px', borderRadius:11, display:'flex', alignItems:'center', gap:10 }}>
    <span style={{ width:8, height:8, borderRadius:'50%', background:dot }} /><span style={{ fontWeight:600 }}>{label}</span></div>;
}
function Ctx({ children }: any) {
  return <div style={{ background:'#fff', borderRadius:14, padding:'13px 16px', boxShadow:'var(--shadow-sm)',
    display:'flex', gap:11, alignItems:'flex-start' }}>
    <span style={{ width:26, height:26, borderRadius:8, background:'var(--blue-soft)', color:'var(--blue)',
      display:'flex', alignItems:'center', justifyContent:'center', flex:'0 0 auto' }}>◷</span>
    <div style={{ fontSize:12.5, color:'var(--label2)' }}>{children}</div></div>;
}
function SampleBanner() {
  return <div style={{ marginTop:12, background:'#FFF8E6', border:'1px solid #FFE5A3', borderRadius:12,
    padding:'10px 14px', fontSize:12, color:'#8A6D00' }}>
    <b>예시 데이터</b>입니다 (실제 사이트 관찰 기반). 백엔드 연결 + 크롤 실행 시 실제 변경점으로 자동 교체됩니다.</div>;
}
function NoChange({ analysis }: { analysis?: any }) {
  return <div style={{ marginTop:12, background:'#fff', borderRadius:14, padding:'16px', boxShadow:'var(--shadow-sm)' }}>
    <div style={{ fontWeight:700, fontSize:14 }}>오늘 변경 없음 ✓</div>
    <div style={{ fontSize:12.5, color:'var(--label2)', marginTop:6 }}>
      {analysis?.aeo_implications || '현재 상태 분석은 [현황 비교] 탭에서 확인하세요.'}</div></div>;
}
function CategoryCard({ cat, count, items, sel, onSel }: any) {
  return <div style={{ background:'#fff', borderRadius:16, padding:'15px 16px', boxShadow:'var(--shadow-sm)' }}>
    <div style={{ display:'flex', alignItems:'center', gap:9, marginBottom:11 }}>
      <span style={{ width:28, height:28, borderRadius:9, background:'var(--bg)', display:'flex',
        alignItems:'center', justifyContent:'center', fontWeight:700 }}>{cat.icon}</span>
      <div style={{ flex:1 }}><div style={{ fontWeight:700, fontSize:13.5 }}>{cat.key}</div>
        <div style={{ fontSize:11, color:'var(--sec)' }}>{cat.desc}</div></div>
      <span style={{ fontSize:20, fontWeight:800, color: count?'var(--label)':'var(--ter)' }}>{count}</span>
    </div>
    {items.length === 0
      ? <div style={{ fontSize:12, color:'var(--ter)', padding:'8px 0' }}>변화 없음</div>
      : items.map((c: Change) => (
        <div key={c.id} onClick={()=>onSel(c)} style={{ padding:'9px 0', borderTop:'1px solid var(--line)',
          cursor:'pointer', background: sel?.id===c.id?'var(--blue-soft)':'transparent',
          marginLeft:-16, marginRight:-16, paddingLeft:16, paddingRight:16, borderRadius: sel?.id===c.id?10:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:3 }}>
            <span style={{ fontSize:10, fontWeight:700, color:'#fff', background:LV_COLOR[c.level],
              padding:'2px 7px', borderRadius:6 }}>{c.level}</span>
            <span className="mono" style={{ fontSize:9.5, fontWeight:700, padding:'2px 6px', borderRadius:5,
              color:'#fff', background: SITE_LABEL[c.site]?.c || 'var(--sec)' }}>
              {c.site==='apple'?'Apple':c.site==='samsung'?'Samsung':c.site}</span>
          </div>
          <div style={{ fontSize:12.5 }}>{c.summary}</div>
          <div className="mono" style={{ fontSize:10.5, color:'var(--sec)', marginTop:2, overflow:'hidden',
            textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{c.url}</div>
        </div>
      ))}
  </div>;
}

/* ── 인스펙터 ── */
function charDiff(a='', b='') {
  const A=[...a], B=[...b]; let i=0;
  while(i<A.length&&i<B.length&&A[i]===B[i])i++;
  let ea=A.length-1, eb=B.length-1;
  while(ea>=i&&eb>=i&&A[ea]===B[eb]){ea--;eb--;}
  return { delPre:A.slice(0,i).join(''), delMid:A.slice(i,ea+1).join(''), delPost:A.slice(ea+1).join(''),
           addPre:B.slice(0,i).join(''), addMid:B.slice(i,eb+1).join(''), addPost:B.slice(eb+1).join('') };
}
function Inspector({ c }: { c: Change }) {
  const d = charDiff(c.before||'', c.after||'');
  const why: Record<string,string> = {
    High:'즉시 대응 권장 — 가격·구매·구조(AI 노출)에 직접 영향.',
    Medium:'검토 필요 — 메시지·섹션·일부 구조 변화.',
    Low:'참고 — 단어·미세·비주얼 수준.',
  };
  return <>
    <Card><div style={lbl}>변화 상세 · {c.level} · {c.category}</div>
      <div style={{ fontSize:15, fontWeight:700, marginTop:7 }}>{c.summary}</div>
      <div className="mono" style={{ fontSize:11, color:'var(--sec)', marginTop:7, wordBreak:'break-all' }}>{c.url}</div></Card>
    {c.field === 'screenshot'
      ? <Card><div style={lbl}>비교샷</div>
          <div style={{ fontSize:12, color:'var(--sec)' }}>이미지 변화가 감지되었습니다. 실서비스에서는 before/after 썸네일과 변경영역(빨간 박스)이 여기 표시됩니다. (원본 미저장, ~10KB 썸네일만 보관)</div></Card>
      : <Card><div style={lbl}>Before → After</div>
          <div className="mono" style={{ fontSize:11.5, lineHeight:1.7 }}>
            {c.before ? <div style={diffDel}>− {d.delPre}<span style={markDel}>{d.delMid}</span>{d.delPost}</div>
                      : <div style={{ color:'var(--ter)', padding:'6px 0' }}>− (이전 값 없음 · 신규)</div>}
            {c.after ? <div style={diffAdd}>+ {d.addPre}<span style={markAdd}>{d.addMid}</span>{d.addPost}</div>
                     : <div style={{ color:'var(--ter)', padding:'6px 0' }}>+ (제거됨)</div>}
          </div></Card>}
    <Card><div style={lbl}>왜 중요한가요?</div>
      <div style={{ fontSize:12.5, background:'var(--blue-soft)', borderRadius:12, padding:'12px 13px' }}>{why[c.level]}</div></Card>
    <Card><div style={lbl}>근거</div>
      {Object.entries(c.evidence||{}).length
        ? Object.entries(c.evidence||{}).map(([k,v]) => <KV key={k} k={k} v={String(v)} />)
        : <KV k="근거" v="—" />}</Card>
  </>;
}
function InspectorDefault({ report }: { report: Report|null }) {
  const a = report?.analysis;
  return <>
    <Card><div style={lbl}>현황 분석</div>
      <div style={{ fontSize:15, fontWeight:700, marginTop:7 }}>지금 어떤 상태인가요?</div>
      <div style={{ fontSize:11.5, color:'var(--sec)', marginTop:7 }}>변경이 없어도 매 크롤마다 분석합니다 · 모든 내용은 실제 수집 데이터 기반</div></Card>
    <Card><div style={lbl}>요약</div>
      <div style={{ fontSize:12.5, color:'var(--label2)' }}>{a?.summary || '왼쪽에서 변경 항목을 선택하면 상세가 표시됩니다.'}</div></Card>
    {a?.aeo_implications && <Card><div style={lbl}>당사(삼성) 시사점</div>
      <div style={{ fontSize:12.5, background:'var(--blue-soft)', borderRadius:12, padding:'12px 13px' }}>{a.aeo_implications}</div></Card>}
  </>;
}

/* ── 현황 비교 ── */
function ComparePane({ data }: { data: any }) {
  if (!data) return <div style={{ padding:40, color:'var(--sec)' }}>불러오는 중…</div>;
  if (data.status === 'insufficient_data')
    return <div style={{ padding:'24px' }}><Ctx><b>비교 데이터가 부족합니다.</b> 삼성·애플 두 사이트 모두 1회 이상 크롤이 완료되어야 비교가 가능합니다. 추측·환각 없이 실제 수집값만 비교합니다.</Ctx></div>;
  const rows = data.comparison || [];
  return <div style={{ padding:'16px 24px 60px' }}>
    <Ctx><b>현황 비교 (삼성 ↔ 애플)</b> — 각 사이트 최신 크롤의 실제 집계값만 맞대어 봅니다. AEO(AI 검색 노출 구조) 관점에서 격차를 봅니다.</Ctx>
    {data.overall && <div style={{ background:'#fff', borderRadius:14, padding:'14px 16px', boxShadow:'var(--shadow-sm)', margin:'14px 0', fontSize:13, color:'var(--label2)' }}>{data.overall}</div>}
    {rows.map((r: any, i: number) => (
      <div key={i} style={{ background:'#fff', borderRadius:16, padding:'15px 16px', boxShadow:'var(--shadow-sm)', marginBottom:11 }}>
        <div style={{ fontWeight:700, fontSize:13.5, marginBottom:11 }}>{r.dimension}</div>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:10 }}>
          <div style={{ background:'var(--blue-soft)', borderRadius:12, padding:'11px 13px' }}>
            <div style={{ fontSize:11, color:'var(--sec)', fontWeight:600 }}>삼성 (당사)</div>
            <div className="mono" style={{ fontSize:15, fontWeight:700, marginTop:3 }}>{r.samsung}</div></div>
          <div style={{ background:'rgba(118,118,128,.08)', borderRadius:12, padding:'11px 13px' }}>
            <div style={{ fontSize:11, color:'var(--sec)', fontWeight:600 }}>애플 (경쟁사)</div>
            <div className="mono" style={{ fontSize:15, fontWeight:700, marginTop:3 }}>{r.apple}</div></div>
        </div>
        <div style={{ fontSize:12.5, color:'var(--label2)' }}>
          <b style={{ color: String(r.gap).includes('열위')?'var(--high)':'var(--low)' }}>{r.gap}</b> → {r.action}</div>
      </div>
    ))}
  </div>;
}

const lbl: React.CSSProperties = { fontSize:11, letterSpacing:'.02em', textTransform:'uppercase', color:'var(--sec)', fontWeight:700, marginBottom:11 };
const diffDel: React.CSSProperties = { background:'#FFF0EF', color:'#B42318', padding:'8px 11px', borderRadius:10, marginBottom:7, whiteSpace:'pre-wrap', wordBreak:'break-word' };
const diffAdd: React.CSSProperties = { background:'#EAF8EE', color:'#1A7F37', padding:'8px 11px', borderRadius:10, whiteSpace:'pre-wrap', wordBreak:'break-word' };
const markDel: React.CSSProperties = { background:'#FFC9C4', borderRadius:4 };
const markAdd: React.CSSProperties = { background:'#ABEBBC', borderRadius:4 };
function Card({ children }: any) { return <div style={{ background:'#fff', borderRadius:16, boxShadow:'var(--shadow-sm)', padding:16, marginBottom:13 }}>{children}</div>; }
function KV({ k, v }: { k:string; v:string }) {
  return <div style={{ display:'flex', justifyContent:'space-between', padding:'7px 0', borderBottom:'1px solid var(--line)', fontSize:12 }}>
    <span style={{ color:'var(--sec)' }}>{k}</span><span className="mono">{v}</span></div>;
}
