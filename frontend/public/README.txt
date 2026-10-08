world-atlas@2 countries-50m.json 을 40KB 이하 조각으로 분할한 것 (저장소 업로드 제한 47KB).
  head.json   : type/bbox/transform + objects.countries(geometries 제외) + arcs_parts/geom_parts(조각 수)
  arcs-N.json : arcs 배열을 순서대로 N등분          geom-N.json : objects.countries.geometries 를 N등분
RegionOverview.tsx 가 head 를 먼저 받고 조각들을 병렬로 받아 이어 붙여 TopoJSON 으로 복원한다.
다시 만들려면 frontend 에서 (LIM 을 바꾸면 조각 크기 조절):
  python - <<'PY'
  import json,os; w=json.load(open('node_modules/world-atlas/countries-50m.json')); LIM=40*1024
  def ch(l):
      o=[];c=[];s=2
      for x in l:
          n=len(json.dumps(x,separators=(',',':')))+1
          if c and s+n>LIM: o.append(c);c=[];s=2
          c.append(x);s+=n
      return o+[c] if c else o
  A=ch(w.pop('arcs')); G=ch(w['objects']['countries'].pop('geometries'))
  for i,c in enumerate(A,1): json.dump(c,open(f'public/world/arcs-{i}.json','w'),separators=(',',':'))
  for i,c in enumerate(G,1): json.dump(c,open(f'public/world/geom-{i}.json','w'),separators=(',',':'))
  w['arcs_parts']=len(A); w['geom_parts']=len(G); json.dump(w,open('public/world/head.json','w'),separators=(',',':'))
  PY
