'use client';
import { useState, useEffect, useCallback, useRef } from 'react';

const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

interface Change { id:number; url:string; site:string; level:'High'|'Medium'|'Low';
  category:string; field:string; summary:string; before?:string; after?:string; evidence?:Record<string,any>; }
interface Report { has_data:boolean; run_id?:string; site?:string; timestamp?:string;
  has_changes?:boolean; by_category?:Record<string,number>; changes?:Change[];
  analysis?:{ summary:string; aeo_implications:string; insights:any[]; actions:any[] }; }
interface Session { session:string; run_ids:string[]; sites:string[]; pages:number; changes:number; timestamp:string; }

const CATS = [
  { key:'데이터·스키마', icon:'🔍', tip:'웹페이지의 구조·코드(스키마/HTML)·메뉴 변화. 검색·AI 노출에 영향을 줍니다.' },
  { key:'카피', icon:'✍️', tip:'제목·본문·문구·FAQ 등 글로 쓰인 내용의 변화입니다.' },
  { key:'가격·프로모션', icon:'💰', tip:'가격·구매 버튼·사전예약·보상판매(Trade-in) 등 거래 관련 변화입니다.' },
  { key:'비주얼', icon:'🖼️', tip:'메인 이미지·배너 등 시각 요소의 변화입니다.' },
];
const LV: Record<string,string> = { High:'var(--high)', Medium:'var(--med)', Low:'var(--low)' };
const LV_KO: Record<string,string> = { High:'높음', Medium:'보통', Low:'낮음' };

/* 사이드 'Example'에서만 보여줄 예시 (실제 사이트 관찰 기반) */
const PREV = '(예시용 가상)';
const _changes: Change[] = [
  { id:1, url:'https://www.apple.com/apple-intelligence/', site:'apple', level:'Medium', category:'카피', field:'대표 제목',
    summary:'대표 제목이 "차세대 Apple Intelligence·Siri"로 바뀜', before:PREV,
    after:'Introducing the next generation of Apple Intelligence and Siri', evidence:{ '바뀐 문장':'1개' } },
  { id:2, url:'https://www.apple.com/apple-intelligence/', site:'apple', level:'Medium', category:'데이터·스키마', field:'메뉴/기능',
    summary:'새 기능 안내 추가 — Safari에 "가격·재입고가 바뀌면 알려주는 기능"', before:PREV,
    after:'Safari로 가격·재입고 변경 알림', evidence:{ '변화 유형':'새 항목 추가' } },
  { id:6, url:'https://www.apple.com/iphone/', site:'apple', level:'High', category:'데이터·스키마', field:'구조화 데이터',
    summary:'신제품 라인업(iPhone 17 Pro/Air/17/17e)이 페이지 구조에 반영됨', before:PREV,
    after:'Product 스키마 4종(iPhone 17 Pro / Air / 17 / 17e)', evidence:{ '변화 유형':'항목 증가' } },
  { id:4, url:'https://www.samsung.com/sg/galaxy-ai/', site:'samsung', level:'Medium', category:'카피', field:'대표 제목',
    summary:'대표 제목(슬로건) 변경', before:PREV, after:'Galaxy AI, a true AI companion', evidence:{ '바뀐 문장':'1개' } },
  { id:3, url:'https://www.samsung.com/sg/galaxy-ai/', site:'samsung', level:'Medium', category:'가격·프로모션', field:'안내 문구',
    summary:'"Galaxy AI 2025년 말까지 무료" 프로모션 문구 노출', before:PREV,
    after:'Galaxy AI features free until the end of 2025', evidence:{ '감지된 키워드':'무료 / 2025' } },
  { id:5, url:'https://www.samsung.com/sg/', site:'samsung', level:'Low', category:'비주얼', field:'메인 이미지',
    summary:'메인 화면 이미지가 바뀐 것으로 감지됨', before:PREV, after:'(새 이미지)', evidence:{ '이미지 차이':'14 / 64' } },
];
const _emptyCat = { '데이터·스키마':0, '카피':0, '가격·프로모션':0, '비주얼':0 };
const _now = () => new Date().toISOString();

const EXAMPLES: Record<'changes'|'nochange'|'analysis', Report> = {
  // ① 변화 있음
  changes: {
    has_data:true, run_id:'ex', site:'samsung', timestamp:_now(), has_changes:true,
    by_category:{ '데이터·스키마':2, '카피':2, '가격·프로모션':1, '비주얼':1 }, changes:_changes,
    analysis:{ summary:'애플은 차세대 Siri를 전면에 내세우고 가격·재입고 알림 기능을 추가했습니다. 당사는 Galaxy AI 무료 기간(2025년 말) 안내 문구가 노출돼 있습니다.',
      aeo_implications:'※ 예시 화면입니다. "이전" 값은 과거 시점을 알 수 없어 가상으로 표시했고, "현재" 값만 실제 사이트에서 관찰한 문구입니다.', insights:[], actions:[] } },
  // ② 변화 없음
  nochange: {
    has_data:true, run_id:'ex0', site:'samsung', timestamp:_now(), has_changes:false,
    by_category:{ ..._emptyCat }, changes:[],
    analysis:{ summary:'직전 크롤 대비 새로 감지된 변화가 없습니다. (현행 유지)',
      aeo_implications:'※ 예시 화면입니다. 변화가 없을 때의 모습입니다.', insights:[], actions:[] } },
  // ③ 현행 분석 (변화 유무와 무관한 상태 분석)
  analysis: {
    has_data:true, run_id:'exa', site:'samsung', timestamp:_now(), has_changes:false,
    by_category:{ ..._emptyCat }, changes:[],
    analysis:{ summary:'현행 분석: 애플은 apple-intelligence 페이지에 차세대 Siri·"Notify Me"(가격·재입고 알림)를 노출 중이고, 삼성 SG는 Galaxy AI 무료 기간 안내와 Trade-in 프로모션을 노출 중입니다.',
      aeo_implications:'※ 예시 화면입니다. 변화가 없어도 매 크롤 시 현재 상태를 이렇게 분석합니다. (현재 값은 실제 관찰 기반)', insights:[], actions:[] } },
};


export default function Page() {
  const [tab, setTab] = useState<'changes'|'compare'>('changes');
  const [report, setReport] = useState<Report|null>(null);
  const [runs, setRuns] = useState<Session[]>([]);
  const [sel, setSel] = useState<Change|null>(null);
  const [crawling, setCrawling] = useState(false);
  const [progress, setProgress] = useState<{done:number; total:number; url:string}|null>(null);
  const [showUrl, setShowUrl] = useState(false);
  const [online, setOnline] = useState<boolean|null>(null); // 백엔드 연결 여부
  const [exampleMode, setExampleMode] = useState<'off'|'changes'|'nochange'|'analysis'>('off');
  const [compare, setCompare] = useState<any>(null);
  const sse = useRef<EventSource|null>(null);

  const load = useCallback(async () => {
    try {
      const h = await fetch(`${API}/api/health`); if (!h.ok) throw 0;
      setOnline(true);
      try {
        const r = await fetch(`${API}/api/latest-report`);
        const j = await r.json();
        setReport(r.ok && j.has_data ? j : null);   // 에러/무데이터면 빈 상태
      } catch { setReport(null); }
      try { const rr = await fetch(`${API}/api/runs`); setRuns((await rr.json()).sessions || []); } catch { setRuns([]); }
    } catch { setOnline(false); setReport(null); }
  }, []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (tab !== 'compare') return;
    (async () => { try { const r = await fetch(`${API}/api/compare`); setCompare(await r.json()); }
      catch { setCompare({ status:'insufficient_data' }); } })();
  }, [tab]);

  const startCrawl = async () => {
    if (!online) return;
    try {
      await fetch(`${API}/trigger-crawl/all`, { method:'POST' });
      setCrawling(true); setProgress({ done:0, total:45, url:'' });
      sse.current?.close();
      const es = new EventSource(`${API}/api/crawl-progress`); sse.current = es;
      let done = 0, total = 45;
      es.onmessage = (e) => {
        try { const ev = JSON.parse(e.data);
          if (ev.type==='start') { total = ev.total||45; setProgress({ done:0, total, url:'' }); }
          else if (ev.type==='page_done') { done++; setProgress({ done, total, url:ev.url||'' }); }
          else if (ev.type==='status' && !ev.crawling) { es.close(); setCrawling(false); setProgress(null); load(); }
        } catch {}
      };
      es.onerror = () => { es.close(); setCrawling(false); setProgress(null); };
    } catch { setCrawling(false); }
  };

  const loadSession = async (runId:string) => {
    if (!online) return;
    setExampleMode('off'); setSel(null);
    try { const r = await fetch(`${API}/api/latest-report?run_id=${encodeURIComponent(runId)}`);
      const j = await r.json(); setReport(j.has_data ? j : null); } catch {}
  };
  const delSession = async (ids:string[]) => {
    if (!online) return;
    for (const id of ids) { try { await fetch(`${API}/api/runs/${id}`, { method:'DELETE' }); } catch {} }
    load();
  };
  const addUrl = async () => {
    const el = document.getElementById('nu') as HTMLInputElement; const u = el?.value.trim(); if (!u) return;
    await fetch(`${API}/api/urls`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ url:u }) });
    el.value=''; setShowUrl(false);
  };

  // 화면 캡처 (프론트에서, 서버 부담 0). html2canvas를 클릭 시 CDN에서 로드.
  const downloadCapture = async () => {
    const ensure = () => new Promise<any>((res, rej) => {
      if ((window as any).html2canvas) return res((window as any).html2canvas);
      const sc = document.createElement('script');
      sc.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
      sc.onload = () => res((window as any).html2canvas);
      sc.onerror = () => rej(new Error('html2canvas load fail'));
      document.body.appendChild(sc);
    });
    try {
      const h2c = await ensure();
      const el = document.getElementById('capture-area') || document.body;
      const canvas = await h2c(el, { backgroundColor: '#F2F2F7', scale: 2, useCORS: true });
      const a = document.createElement('a');
      a.href = canvas.toDataURL('image/png');
      a.download = `apple-stalker_${new Date().toISOString().slice(0,16).replace(/[:T]/g,'')}.png`;
      a.click();
    } catch { alert('캡처에 실패했습니다. 잠시 후 다시 시도해 주세요.'); }
  };

  const data = exampleMode!=='off' ? EXAMPLES[exampleMode] : report;
  const isExample = exampleMode!=='off';
  const changes = data?.changes || [];
  const byCat = data?.by_category || {};
  const appleN = changes.filter(c=>c.site==='apple').length;
  const samsungN = changes.filter(c=>c.site==='samsung').length;
  const highN = changes.filter(c=>c.level==='High').length;

  return (
    <div style={{ display:'grid', gridTemplateColumns:'232px 1fr 360px', height:'100vh', overflow:'hidden' }}>
      {/* 좌측 */}
      <aside style={{ background:'var(--rail)', borderRight:'1px solid var(--line)', overflow:'auto', display:'flex', flexDirection:'column' }}>
        <div style={{ padding:'20px 18px 8px' }}>
          <div style={{ fontSize:19, fontWeight:700 }}>Apple Stalker</div>
          <div className="mono" style={{ fontSize:11, color:'var(--sec)', marginTop:2 }}>경쟁사 웹 변화 감지</div>
          <ConnBadge online={online} />
        </div>

        <Sec t="중요도 기준" hint="무엇이 · 얼마나 바뀌었나로 정합니다" />
        <div style={{ padding:'0 14px 4px' }}>
          {[
            ['High','높음','var(--high)','스키마·페이지 구조(레이아웃) 변화, 여러 섹션 동시 변화 — AI 검색 노출에 직접 영향'],
            ['Medium','보통','var(--med)','메뉴·메타 변경, 문장·슬로건 카피 변경, 가격·구매 등 거래 변화'],
            ['Low','낮음','var(--low)','단어 몇 개·오타 등 미세 변화, 작은 이미지 변화'],
          ].map(([k,ko,c,d])=>(
            <div key={k} style={{ display:'flex', gap:9, alignItems:'flex-start', padding:'7px 0', borderBottom:'1px solid var(--line)' }}>
              <span style={{ width:9, height:9, borderRadius:3, background:c as string, marginTop:4, flex:'0 0 auto' }} />
              <div><div style={{ fontWeight:700, fontSize:12 }}>{ko}</div>
                <div style={{ fontSize:11, color:'var(--sec)', lineHeight:1.45, marginTop:1 }}>{d}</div></div>
            </div>
          ))}
        </div>

        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'16px 16px 6px' }}>
          <span style={{ fontSize:11, color:'var(--sec)', fontWeight:600 }}>크롤 이력</span>
          {online && <button onClick={()=>setShowUrl(v=>!v)} style={pillBtn}>＋ URL</button>}
        </div>
        {showUrl && online && (
          <div style={{ margin:'0 12px 8px', display:'flex', gap:6 }}>
            <input id="nu" placeholder="https://…" className="mono" style={{ flex:1, border:'1px solid var(--line2)', borderRadius:9, padding:'8px 10px', fontSize:11 }} />
            <button onClick={addUrl} style={{ background:'var(--blue)', color:'#fff', borderRadius:9, padding:'0 12px', fontSize:11, fontWeight:600 }}>추가</button>
          </div>
        )}
        <div style={{ padding:'0 10px 10px', flex:1 }}>
          {!online && <Muted>백엔드 연결 후 표시됩니다</Muted>}
          {online && runs.length===0 && <Muted>아직 크롤 기록이 없습니다</Muted>}
          {online && runs.map(s=>(
            <div key={s.session} onClick={()=>loadSession(s.run_ids[0])} style={{ display:'flex', alignItems:'center', gap:6, padding:'8px 8px', borderRadius:9, cursor:'pointer' }}
              onMouseEnter={e=>(e.currentTarget.style.background='rgba(0,0,0,.04)')}
              onMouseLeave={e=>(e.currentTarget.style.background='transparent')}>
              <div style={{ flex:1 }}>
                <div className="mono" style={{ fontSize:11.5, fontWeight:600 }}>{s.timestamp}</div>
                <div style={{ fontSize:10.5, color:'var(--sec)' }}>
                  {s.sites.map(x=>x==='apple'?'애플':x==='samsung'?'삼성':x).join('+')} · {s.changes?`${s.changes} 변화`:'변화 없음'}</div>
              </div>
              <button onClick={(e)=>{ e.stopPropagation(); delSession(s.run_ids); }} title="삭제"
                style={{ color:'var(--ter)', fontSize:15, padding:'2px 5px' }}>×</button>
            </div>
          ))}
        </div>

        {/* 모니터링 대상 (좌하단, 작게) */}
        <div style={{ padding:'10px 16px 6px', borderTop:'1px solid var(--line)' }}>
          <div style={{ fontSize:10.5, color:'var(--sec)', fontWeight:600, marginBottom:6 }}>모니터링 대상</div>
          <div style={{ display:'flex', gap:14 }}>
            <span style={{ display:'flex', alignItems:'center', gap:6, fontSize:11.5 }}>
              <span style={{ width:7, height:7, borderRadius:'50%', background:'var(--samsung)' }} /><b>당사</b> Samsung</span>
            <span style={{ display:'flex', alignItems:'center', gap:6, fontSize:11.5 }}>
              <span style={{ width:7, height:7, borderRadius:'50%', background:'var(--apple)' }} /><b>경쟁사</b> Apple</span>
          </div>
        </div>

        {/* 예시 보기 (3상태) */}
        <div style={{ padding:'10px 14px 16px' }}>
          <div style={{ fontSize:10.5, color:'var(--sec)', fontWeight:600, marginBottom:6 }}>예시 화면 (참고용)</div>
          <div style={{ display:'flex', gap:5 }}>
            {[['changes','변화 있음'],['nochange','변화 없음'],['analysis','현행 분석']].map(([k,label])=>(
              <button key={k} onClick={()=>{ setExampleMode(exampleMode===k?'off':k as any); setSel(null); }}
                style={{ flex:1, fontSize:10.5, fontWeight:600, padding:'7px 0', borderRadius:9,
                  color: exampleMode===k?'#fff':'var(--label2)',
                  background: exampleMode===k?'var(--blue)':'rgba(0,0,0,.045)' }}>{label}</button>
            ))}
          </div>
          <div style={{ fontSize:10, color:'var(--ter)', marginTop:6 }}>실제 데이터가 없을 때 참고용 (이전 값은 예시용 가상)</div>
        </div>
      </aside>

      {/* 중앙 */}
      <main style={{ overflow:'auto' }}>
        <div style={{ position:'sticky', top:0, zIndex:5, background:'rgba(242,242,247,.78)', backdropFilter:'saturate(180%) blur(20px)',
          borderBottom:'1px solid var(--line)' }}>
          <div style={{ padding:'13px 24px', display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
            <div style={{ display:'inline-flex', background:'rgba(118,118,128,.12)', borderRadius:11, padding:3, gap:2 }}>
              <Seg on={tab==='changes'} onClick={()=>setTab('changes')}>변경점</Seg>
              <Seg on={tab==='compare'} onClick={()=>setTab('compare')}>현황 비교</Seg>
            </div>
            <span style={{ flex:1 }} />
            {data?.has_data && <button onClick={downloadCapture} style={ghost}>화면 캡처</button>}
            {online && data?.has_data && !isExample && <a href={`${API}/api/export/xlsx`} style={ghost}>Excel</a>}
            {online && data?.has_data && !isExample && <a href={`${API}/api/export/pptx`} style={ghost}>PPTX</a>}
            <button onClick={startCrawl} disabled={!online||crawling}
              style={{ ...ghost, background: online&&!crawling?'var(--blue)':'var(--line2)', color:'#fff', cursor: online&&!crawling?'pointer':'default' }}>
              {crawling ? '크롤 중…' : '크롤 실행'}</button>
          </div>
          {/* 컴팩트 진행바 */}
          {crawling && progress && (
            <div style={{ padding:'0 24px 12px' }}>
              <div style={{ height:6, background:'rgba(118,118,128,.18)', borderRadius:4, overflow:'hidden' }}>
                <div style={{ height:'100%', width:`${Math.round(progress.done/progress.total*100)}%`, background:'var(--blue)', transition:'width .3s' }} /></div>
              <div className="mono" style={{ fontSize:11, color:'var(--sec)', marginTop:5, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                {progress.done}/{progress.total} 수집 중 · {progress.url || '시작…'}</div>
            </div>
          )}
        </div>

        {tab==='compare'
          ? <Compare data={compare} online={online} />
          : (!online
              ? <Empty title="백엔드에 연결되지 않았습니다" desc="프론트엔드 설정(NEXT_PUBLIC_API_URL)에 백엔드 주소를 넣고 다시 배포하세요. 왼쪽 아래 '예시 화면 보기'로 미리 둘러볼 수 있습니다." />
              : !data
                ? <Empty title="아직 수집된 변화가 없습니다" desc="오른쪽 위 [크롤 실행]을 누르면 애플·삼성 페이지를 수집해 변화를 찾아냅니다. (페이지가 많아 몇 분 걸립니다)" cta={startCrawl} />
                : <Changes data={data} byCat={byCat} appleN={appleN} samsungN={samsungN} highN={highN} sel={sel} setSel={setSel} isExample={exampleMode} />
            )}
      </main>

      {/* 우측 */}
      <aside style={{ background:'var(--rail)', borderLeft:'1px solid var(--line)', overflow:'auto', padding:'16px 14px' }}>
        {sel ? <Detail c={sel} /> : <DetailDefault data={data} online={online} />}
      </aside>
    </div>
  );
}

/* ── 변경점 본문: 좌(경쟁사 애플) / 우(당사 삼성) 2칼럼 ── */
function Changes({ data, byCat, appleN, samsungN, highN, sel, setSel, isExample }: any) {
  const a = data.analysis;
  const total = (Object.values(byCat) as number[]).reduce((x,y)=>x+y,0);
  const col = (site:'apple'|'samsung') => CATS.map((cat:any)=>({
    cat, items: data.changes.filter((c:Change)=>c.site===site && c.category===cat.key) }));
  return (
    <div id="capture-area" style={{ padding:'18px 24px 60px' }}>
      {isExample && <div style={{ background:'#FFF8E6', border:'1px solid #FFE5A3', borderRadius:12, padding:'10px 14px', fontSize:12, color:'#8A6D00', marginBottom:14 }}>
        🔍 <b>예시 화면</b>입니다. 실제 데이터가 아니며, 크롤을 실행하면 진짜 변화로 채워집니다.</div>}

      {/* 오늘의 핵심 */}
      <div style={{ background:'#fff', borderRadius:18, padding:'18px 20px', boxShadow:'var(--shadow)' }}>
        <div style={{ display:'flex', gap:14, alignItems:'center', marginBottom:10 }}>
          <span style={{ fontSize:14, fontWeight:700 }}>오늘의 핵심</span>
          <span style={{ fontSize:11.5, color:'var(--sec)' }}>{data.timestamp}</span>
          <span style={{ flex:1 }} />
          <Stat n={total} label="전체 변화" />
          <Stat n={highN} label="높음" color="var(--high)" />
        </div>
        <div style={{ fontSize:13.5, color:'var(--label2)', lineHeight:1.65 }}>
          {a?.summary || '수집된 변화 요약이 여기에 표시됩니다.'}</div>
        {a?.aeo_implications && <div style={{ fontSize:12.5, color:'var(--sec)', marginTop:8 }}>{a.aeo_implications}</div>}
      </div>

      {/* 2칼럼: 경쟁사 vs 당사 */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginTop:14, alignItems:'start' }}>
        <SiteColumn site="apple" title="경쟁사 · Apple" count={appleN} cols={col('apple')} sel={sel} setSel={setSel} />
        <SiteColumn site="samsung" title="당사 · Samsung" count={samsungN} cols={col('samsung')} sel={sel} setSel={setSel} />
      </div>
    </div>
  );
}

function SiteColumn({ site, title, count, cols, sel, setSel }: any) {
  const accent = site==='apple' ? 'var(--apple)' : 'var(--samsung)';
  return (
    <div>
      <div style={{ display:'flex', alignItems:'center', gap:8, padding:'4px 4px 12px' }}>
        <span style={{ width:10, height:10, borderRadius:3, background:accent }} />
        <span style={{ fontWeight:700, fontSize:14 }}>{title}</span>
        <span style={{ fontSize:12, color:'var(--sec)' }}>· 변화 {count}</span>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
        {cols.map(({ cat, items }: any)=>(
          <div key={cat.key} style={{ background:'#fff', borderRadius:16, padding:'14px 16px', boxShadow:'var(--shadow-sm)' }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:items.length?10:0 }}>
              <span style={{ width:26, height:26, borderRadius:8, background:'var(--bg)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:13 }}>{cat.icon}</span>
              <span style={{ fontWeight:600, fontSize:13 }}>{cat.key}</span><Info tip={cat.tip} />
              <span style={{ flex:1 }} />
              <span style={{ fontSize:16, fontWeight:800, color: items.length?'var(--label)':'var(--ter)' }}>{items.length}</span>
            </div>
            {items.length===0
              ? <div style={{ fontSize:11.5, color:'var(--ter)' }}>변화 없음</div>
              : items.map((c:Change)=>(
                <div key={c.id} onClick={()=>setSel(c)} style={{ padding:'9px 16px', marginLeft:-16, marginRight:-16,
                  borderTop:'1px solid var(--line)', cursor:'pointer', borderRadius: sel?.id===c.id?9:0,
                  background: sel?.id===c.id?'var(--blue-soft)':'transparent' }}>
                  <div style={{ marginBottom:4 }}><Badge color={LV[c.level]}>{LV_KO[c.level]}</Badge></div>
                  <div style={{ fontSize:12.5, lineHeight:1.5 }}>{c.summary}</div>
                </div>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── 우측 상세 (AI스러운 라벨 제거) ── */
function Detail({ c }: { c:Change }) {
  return <>
    <Card>
      <div style={{ display:'flex', gap:6, marginBottom:10 }}>
        <Badge color={LV[c.level]}>{LV_KO[c.level]}</Badge>
        <Badge color={c.site==='apple'?'var(--apple)':'var(--samsung)'}>{c.site==='apple'?'Apple':'Samsung'}</Badge>
        <span style={{ fontSize:11, color:'var(--sec)', alignSelf:'center' }}>{c.category} · {c.field}</span>
      </div>
      <div style={{ fontSize:15, fontWeight:700, lineHeight:1.45 }}>{c.summary}</div>
      <a href={c.url} target="_blank" rel="noreferrer" className="mono"
        style={{ fontSize:11, color:'var(--blue)', marginTop:9, display:'block', wordBreak:'break-all' }}>{c.url} ↗</a>
    </Card>
    {c.field !== '메인 이미지' && (() => {
      const d = diffParts(c.before || '', c.after || '');
      return (
      <Card>
        <div style={{ fontSize:12, color:'var(--sec)', marginBottom:9 }}>실제 바뀐 내용 (원문 그대로)</div>
        <div style={{ fontSize:12, color:'var(--sec)', marginBottom:4 }}>이전</div>
        <div className="mono" style={{ fontSize:12, background:'#F7F7F8', borderRadius:10, padding:'9px 11px', color:'var(--sec)', whiteSpace:'pre-wrap', wordBreak:'break-word' }}>
          {c.before ? <>{d.delPre}<mark style={{ background:'#FFD9D4', color:'#8a1c12', borderRadius:3 }}>{d.delMid}</mark>{d.delPost}</> : '(없음)'}</div>
        <div style={{ fontSize:12, color:'var(--blue)', margin:'10px 0 4px' }}>현재</div>
        <div className="mono" style={{ fontSize:12, background:'var(--blue-soft)', borderRadius:10, padding:'9px 11px', color:'var(--label)', whiteSpace:'pre-wrap', wordBreak:'break-word' }}>
          {c.after ? <>{d.addPre}<mark style={{ background:'#B7E8C5', color:'#13642b', borderRadius:3 }}>{d.addMid}</mark>{d.addPost}</> : '(삭제됨)'}</div>
      </Card>);
    })()}
    {c.field === '메인 이미지' && (
      <Card><div style={{ fontSize:12, color:'var(--sec)', marginBottom:9 }}>이미지 변화</div>
        <div style={{ fontSize:12.5, color:'var(--label2)' }}>메인 화면 이미지가 바뀐 것으로 감지되었습니다. 실제 운영 시에는 이전/현재 이미지가 나란히 표시됩니다.</div></Card>
    )}
    {c.evidence && Object.keys(c.evidence).length>0 && (
      <Card><div style={{ fontSize:12, color:'var(--sec)', marginBottom:9 }}>감지 근거</div>
        {Object.entries(c.evidence).map(([k,v])=>(
          <div key={k} style={{ display:'flex', justifyContent:'space-between', padding:'6px 0', borderBottom:'1px solid var(--line)', fontSize:12 }}>
            <span style={{ color:'var(--sec)' }}>{k}</span><span className="mono">{String(v)}</span></div>
        ))}</Card>
    )}
  </>;
}
/* 이전/현재 원문에서 바뀐 구간만 찾아 강조 */
function diffParts(a:string, b:string){
  const A=[...a], B=[...b]; let i=0;
  while(i<A.length&&i<B.length&&A[i]===B[i])i++;
  let ea=A.length-1, eb=B.length-1;
  while(ea>=i&&eb>=i&&A[ea]===B[eb]){ea--;eb--;}
  return { delPre:A.slice(0,i).join(''), delMid:A.slice(i,ea+1).join(''), delPost:A.slice(ea+1).join(''),
           addPre:B.slice(0,i).join(''), addMid:B.slice(i,eb+1).join(''), addPost:B.slice(eb+1).join('') };
}
function DetailDefault({ data, online }: any) {
  if (!online) return <Card><div style={{ fontSize:13.5, fontWeight:700 }}>연결 대기 중</div>
    <div style={{ fontSize:12.5, color:'var(--sec)', marginTop:7 }}>백엔드에 연결되면 여기에 변화 상세가 표시됩니다.</div></Card>;
  return <Card><div style={{ fontSize:13.5, fontWeight:700 }}>변화를 선택하세요</div>
    <div style={{ fontSize:12.5, color:'var(--sec)', marginTop:7 }}>왼쪽 카드에서 항목을 누르면 무엇이 어떻게 바뀌었는지 보여드립니다.</div></Card>;
}

/* ── 현황 비교 ── */
function Compare({ data, online }: any) {
  if (!online) return <Empty title="백엔드에 연결되지 않았습니다" desc="비교 데이터를 불러오려면 백엔드 연결이 필요합니다." />;
  if (!data) return <Empty title="불러오는 중…" desc="" />;
  if (data.status === 'insufficient_data')
    return <Empty title="비교할 데이터가 부족합니다" desc="삼성·애플 두 사이트 모두 1회 이상 크롤이 완료되어야 비교가 가능합니다. (지어낸 숫자 없이 실제 수집값만 비교합니다)" />;
  const rows = data.comparison || [];
  return <div style={{ padding:'18px 24px 60px' }}>
    {data.overall && <div style={{ background:'#fff', borderRadius:16, padding:'15px 17px', boxShadow:'var(--shadow-sm)', marginBottom:14, fontSize:13, lineHeight:1.6, color:'var(--label2)' }}>{data.overall}</div>}
    {rows.map((r:any,i:number)=>(
      <div key={i} style={{ background:'#fff', borderRadius:16, padding:'15px 16px', boxShadow:'var(--shadow-sm)', marginBottom:11 }}>
        <div style={{ fontWeight:700, fontSize:13.5, marginBottom:11 }}>{r.dimension}</div>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
          <Box label="삼성 (당사)" v={r.samsung} bg="var(--blue-soft)" />
          <Box label="애플 (경쟁사)" v={r.apple} bg="rgba(118,118,128,.08)" />
        </div>
        {r.action && <div style={{ fontSize:12.5, color:'var(--label2)', marginTop:10 }}>{r.action}</div>}
      </div>
    ))}
  </div>;
}

/* ── 공통 작은 컴포넌트 ── */
const ghost: React.CSSProperties = { background:'#fff', color:'var(--label)', borderRadius:11, padding:'8px 14px', fontSize:12.5, fontWeight:600, boxShadow:'var(--shadow-sm)', textDecoration:'none' };
const pillBtn: React.CSSProperties = { fontSize:11, color:'var(--sec)', fontWeight:600, padding:'3px 8px', borderRadius:8, background:'rgba(0,0,0,.05)' };
function Seg({ on, onClick, children }: any){ return <button onClick={onClick} style={{ borderRadius:9, padding:'7px 14px', fontSize:12.5, fontWeight:600, color:on?'var(--label)':'var(--label2)', background:on?'#fff':'transparent', boxShadow:on?'var(--shadow-sm)':'none' }}>{children}</button>; }
function Sec({ t, hint }: { t:string; hint?:string }){ return <div style={{ padding:'16px 18px 6px', fontSize:11, color:'var(--sec)', fontWeight:600 }}>{t}{hint && <span style={{ fontWeight:400 }}> · {hint}</span>}</div>; }
function Row({ children }: any){ return <div style={{ margin:'1px 12px', padding:'8px 12px', display:'flex', alignItems:'center', fontSize:13 }}>{children}</div>; }
function Dot({ c }: { c:string }){ return <span style={{ width:8, height:8, borderRadius:'50%', background:c, marginRight:9 }} />; }
function Muted({ children }: any){ return <div style={{ color:'var(--ter)', fontSize:11, padding:'8px 10px' }}>{children}</div>; }
function Badge({ color, children }: any){ return <span style={{ fontSize:10, fontWeight:700, color:'#fff', background:color, padding:'2px 7px', borderRadius:6 }}>{children}</span>; }
function Stat({ n, label, color }: any){ return <div style={{ textAlign:'center', minWidth:46 }}><div style={{ fontSize:18, fontWeight:800, color:color||'var(--label)' }}>{n}</div><div style={{ fontSize:10, color:'var(--sec)' }}>{label}</div></div>; }
function Card({ children }: any){ return <div style={{ background:'#fff', borderRadius:16, boxShadow:'var(--shadow-sm)', padding:16, marginBottom:13 }}>{children}</div>; }
function Box({ label, v, bg }: any){ return <div style={{ background:bg, borderRadius:12, padding:'11px 13px' }}><div style={{ fontSize:11, color:'var(--sec)', fontWeight:600 }}>{label}</div><div className="mono" style={{ fontSize:15, fontWeight:700, marginTop:3 }}>{v}</div></div>; }
function Info({ tip }: { tip:string }){
  const [open, setOpen] = useState(false);
  return (
    <span style={{ position:'relative', display:'inline-flex' }}>
      <span onClick={(e)=>{ e.stopPropagation(); setOpen(v=>!v); }}
        style={{ width:15, height:15, borderRadius:'50%', background:'rgba(118,118,128,.18)', color:'var(--sec)',
          fontSize:10, fontWeight:700, display:'inline-flex', alignItems:'center', justifyContent:'center', cursor:'pointer' }}>i</span>
      {open && (
        <>
          <span onClick={(e)=>{ e.stopPropagation(); setOpen(false); }}
            style={{ position:'fixed', inset:0, zIndex:40 }} />
          <span style={{ position:'absolute', top:20, left:0, zIndex:41, width:220, background:'#fff',
            border:'1px solid var(--line)', boxShadow:'var(--shadow)', borderRadius:10, padding:'10px 12px',
            fontSize:11.5, fontWeight:400, color:'var(--label2)', lineHeight:1.5 }}>{tip}</span>
        </>
      )}
    </span>
  );
}
function ConnBadge({ online }: { online:boolean|null }){
  if (online===null) return null;
  return <div style={{ marginTop:9, display:'inline-flex', alignItems:'center', gap:6, fontSize:11, fontWeight:600,
    color: online?'#1A7F37':'#B42318', background: online?'#EAF8EE':'#FFF0EF', padding:'4px 9px', borderRadius:8 }}>
    <span style={{ width:7, height:7, borderRadius:'50%', background: online?'#1A7F37':'#B42318' }} />
    {online ? '백엔드 연결됨' : '백엔드 연결 안 됨'}</div>;
}
function Empty({ title, desc, cta }: { title:string; desc:string; cta?:()=>void }){
  return <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'70vh', textAlign:'center', padding:24 }}>
    <div style={{ fontSize:34, marginBottom:14 }}>🍎</div>
    <div style={{ fontSize:17, fontWeight:700 }}>{title}</div>
    <div style={{ fontSize:13, color:'var(--sec)', marginTop:8, maxWidth:420, lineHeight:1.6 }}>{desc}</div>
    {cta && <button onClick={cta} style={{ marginTop:18, background:'var(--blue)', color:'#fff', borderRadius:12, padding:'11px 22px', fontSize:13.5, fontWeight:600 }}>크롤 실행</button>}
  </div>;
}
