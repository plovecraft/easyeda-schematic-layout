"""Independent verification of actual native readback and SVG geometry."""
import copy
from collections import defaultdict,Counter
from itertools import combinations
from pathlib import Path
from .model import load_json,save_json,import_page,sha256
from .geometry import point,onseg,intersection,box,ground_box,overlap,seg_box,EPS
from .validator import DSU
from .pin_exit import bad_pin_exits

def native_parts(raw):
    items=[c for c in raw['result']['components'] if c['componentType']=='part']
    assert len({c['designator'] for c in items})==len(items), 'duplicate native designators'
    return {c['designator']:c for c in items}

def guard_identity(old,new,retained=True):
    fields=('uniqueId','name','designator','subPartName','addIntoBom','addIntoPcb','manufacturer','manufacturerId','supplier','supplierId','otherProperty','device','footprint','symbol')
    for key in fields:
        assert old.get(key)==new.get(key), (old.get('designator'), 'identity changed',key)
    if retained: assert old['primitiveId']==new['primitiveId']

def merge_intervals(rows):
    result=[]
    for lo,hi in sorted(rows):
        if result and lo<=result[-1][1]+1e-5:result[-1][1]=max(hi,result[-1][1])
        else:result.append([lo,hi])
    return result

def interval_map(segments):
    result=defaultdict(list)
    for n,a,b in segments:
        assert a[0]==b[0] or a[1]==b[1],('diagonal',a,b)
        axis=0 if a[1]==b[1] else 1;fixed=a[1-axis]
        result[(n,axis,round(fixed,5))].append(sorted((a[axis],b[axis])))
    return {k:merge_intervals(v) for k,v in result.items()}

def verify_graph(raw,plan,policy):
    r=raw['result'];actual=native_parts(raw);want={p['ref']:p for p in plan['parts']};assert set(actual)==set(want)
    pins={};pin_roots={};counts=0
    for ref,p in want.items():
        c=actual[ref];guard_identity(p['native'],c,False)
        assert (c['x'],c['y'],c['rotation'],c['mirror'])==(p['x'],p['y'],p['rotation'],p['mirror'])
        qs={q['pinNumber']:q for q in c['pins']};assert set(qs)=={q['pinNumber'] for q in p['pins']}
        for q in p['pins']:
            a=qs[q['pinNumber']];assert not a.get('netAmbiguous')
            assert (a['net'],a['noConnected'],a['pinName'],a['rotation'])==(q['net'],q['noConnected'],q['pinName'],q['rotation']),(ref,q['pinNumber'],'pin contract',a,q)
            assert abs(a['x']-q['x'])<1e-5 and abs(a['y']-q['y'])<1e-5
            pins[(ref,q['pinNumber'])]=a;counts+=1
    ws=[];seen=set()
    for w in r['wires']:
        a=point((w['x0'],w['y0']));b=point((w['x1'],w['y1']));assert a!=b,'zero-length native wire'
        k=(w['primitiveId'],tuple(sorted((a,b))))
        if k not in seen:ws.append((w['primitiveId'],a,b));seen.add(k)
    ds=DSU()
    for i in range(len(ws)):ds.find(i)
    for i,j in combinations(range(len(ws)),2):
        u,a,b=ws[i];v,c,d=ws[j];hit=intersection(a,b,c,d)
        if hit is not None and (hit==('overlap',) or hit in (a,b,c,d) or u==v):ds.join(i,j)
    def roots(pt):return {ds.find(i) for i,(_,a,b) in enumerate(ws) if onseg(pt,a,b)}
    names=defaultdict(set);root_pins=defaultdict(list)
    for key,q in pins.items():
        touch=roots(point((q['x'],q['y'])));pin_roots[key]=touch
        if q['noConnected']:assert not touch,(key,'NC wired')
        else:
            assert len(touch)==1,(key,'unwired/ambiguous physical root',touch)
            root=next(iter(touch));names[root].add(q['net']);root_pins[root].append(key)
    wire_ids={w[0] for w in ws};labels=[]
    for a in r['pagePrimitives']['attributes']:
        if a['Key']=='Name' and a['ParentPrimitiveId'] in wire_ids and a.get('ValueVisible') and a.get('Value'):
            rr=roots(point((a['X'],a['Y'])));assert len(rr)==1,('orphan/ambiguous label',a)
            root=next(iter(rr));names[root].add(a['Value']);labels.append(a)
    # Native paper/title-block components are non-electrical. Their bounds and
    # title fields are checked separately; they must never count as net flags.
    flags=[c for c in r['components'] if c['componentType'] not in ('part','sheet')]
    assert len(flags)==sum(m['kind']=='ground' for m in plan['markers'])
    matched_flags={};remaining=flags.copy()
    for m in [m for m in plan['markers'] if m['kind']=='ground']:
        matches=[c for c in remaining if c['componentType']=='netflag' and c['net']==m['net'] and point((c['x'],c['y']))==point(m['point'])]
        assert len(matches)==1,(m['id'],'ground missing/duplicate');c=matches[0];remaining.remove(c);matched_flags[m['id']]=c
        assert c['rotation']%360==m['rotation']%360
        assert max(abs(a-b) for a,b in zip(box(c['bbox']),ground_box(m)))<1e-5,(m['id'],'ground body geometry')
        rr=roots(point(m['point']));assert len(rr)==1;names[next(iter(rr))].add(c['net'])
    planned_labels=[m for m in plan['markers'] if m['kind']!='ground'];assert len(labels)==len(planned_labels),(len(labels),len(planned_labels),'visible net labels')
    matched_labels={};unused=labels.copy()
    for m in planned_labels:
        aa=[a for a in unused if a['Value']==m['net'] and point((a['X'],a['Y']))==point(m['point'])]
        assert len(aa)==1,(m['id'],'label missing/duplicate');a=aa[0];unused.remove(a);matched_labels[m['id']]=a
    for root in {ds.find(i) for i in range(len(ws))}:
        assert len(names[root])==1,('conflicting/unknown physical net',root,names[root]);assert root_pins[root],('orphan wire tree',root)
    ss=[(next(iter(names[ds.find(i)])),a,b) for i,(_,a,b) in enumerate(ws)]
    assert not bad_pin_exits(dict(parts=[dict(ref=ref,pins=c['pins']) for ref,c in actual.items()],wires=[dict(net=n,points=[a,b]) for n,a,b in ss])), 'native pin exit direction mismatch'
    expected=[(w['net'],point(a),point(b)) for w in plan['wires'] for a,b in zip(w['points'],w['points'][1:])]
    ai=interval_map(ss);ei=interval_map(expected)
    assert set(ai)==set(ei),('wire axes/coverage/net set changed',set(ai)^set(ei))
    for k,v in ei.items():assert len(ai[k])==len(v) and all(abs(a-b)<1e-5 for x,y in zip(ai[k],v) for a,b in zip(x,y)),('wire coverage mismatch',k,ai[k],v)
    for a,b in policy.get('requiredPhysicalPairs',[]):assert pin_roots[tuple(a)] & pin_roots[tuple(b)],('required physical pair split',a,b)
    for n,a,b in ss:
        for ref,c in actual.items():assert not seg_box(a,b,box(c['bbox'])),('wire through body',ref)
    report=dict(passed=True,parts=len(actual),pins=counts,physicalWireIslands=len(names),wireSegments=len(ss),visibleWireNames=len(labels),groundFlags=len(flags),requiredPhysicalPairs=len(policy.get('requiredPhysicalPairs',[])),coverage='fresh actual pin nets, NC, identities, physical DSU, exact bidirectional interval coverage, required direct pairs; no planned net names used to infer actual wires')
    return report,dict(segments=ss,matchedFlags=matched_flags,matchedLabels=matched_labels,parts=actual,pins=pins)

def verify_render(raw,plan,policy,svg_path,measurement_path,graph):
    from lxml import etree
    actual_page=import_page(raw,svg_path,measurement_path) if isinstance(raw,(str,Path)) else None
    # import_page needs the retained raw file; all measurements remain immutable.
    assert actual_page is not None
    rr=load_json(raw)['result'];mm={e['id']:e for e in load_json(measurement_path)['elements'] if e['tag']=='text' and e['text']}
    expected={p['ref']:p for p in plan['parts']};actual={p['ref']:p for p in actual_page['parts']};mapped={};used=set();envelope_delta=0
    def match(t,a,category):
        nonlocal envelope_delta
        assert t['text']==a['text'],(category,'text changed',t['text'],a['text'])
        delta=max(abs(t['bbox'][k]-a['bbox'][k]) for k in t['bbox']);envelope_delta=max(envelope_delta,delta)
        assert delta<.03,(category,'rendered envelope differs',t['text'],delta,t['bbox'],a['bbox'])
        used.add(a['id']);mapped[a['id']]=t['id']
    for ref,p in expected.items():
        a=actual[ref]
        for category in ('labels','fixedTexts'):
            assert len(p[category])==len(a[category]),(ref,category,'text count')
            unused=a[category].copy()
            for t in p[category]:
                candidates=[v for v in unused if v['text']==t['text'] and (category!='labels' or v.get('key')==t.get('key'))];assert candidates,(ref,'text missing',t['text'])
                v=min(candidates,key=lambda v:sum(abs(t['bbox'][k]-v['bbox'][k]) for k in t['bbox']));unused.remove(v);match(t,v,ref)
    for m in plan['markers']:
        if m['kind']=='ground':
            pid=graph['matchedFlags'][m['id']]['primitiveId'];aa=[a for a in rr['pagePrimitives']['attributes'] if a['ParentPrimitiveId']==pid and a['Key']=='Name' and a.get('ValueVisible')]
            assert len(aa)==1;tid=aa[0]['primitiveId']
        else:tid=graph['matchedLabels'][m['id']]['primitiveId']
        assert tid in mm,('rendered marker text missing',m['id'],tid);match(m['label'],mm[tid],m['id'])
    # Frame font metrics are verified from the actual render and occupancy,
    # without assuming SDK text height equals its raw fontSize argument.
    # The native exporter owns paper/table lettering. Keep all of it in the
    # collision checks, while distinguishing it from planned module titles.
    root=etree.parse(str(svg_path)).getroot()
    sheet_text_ids={e.get('id') for group in root.iter() if group.get('c_partid')=='sheet' for e in group.iter() if etree.QName(e).localname=='text'}
    rest=[v for tid,v in mm.items() if tid not in used and tid not in sheet_text_ids]
    assert Counter(v['text'] for v in rest)==Counter(f['title'] for f in plan['frames']),('unexpected or missing visible text',[v['text'] for v in rest])
    texts=list(mm.values());text_collisions=[];wire_collisions=[];body_collisions=[];allowed=[];numeric_contacts=[]
    fixed={t['id']:p['ref'] for p in actual_page['parts'] for t in p['fixedTexts']}
    wire_names={a['primitiveId']:m for m in plan['markers'] if m['kind']!='ground' for a in [graph['matchedLabels'][m['id']]]}
    for a,b in combinations(texts,2):
        area=overlap(box(a['bbox']),box(b['bbox']))
        if area>EPS:
            aa=box(a['bbox']);bb=box(b['bbox']);extent=min(min(aa[2],bb[2])-max(aa[0],bb[0]),min(aa[3],bb[3])-max(aa[1],bb[1]))
            row=next((r for r in policy.get('nativeTextBoundaryAllowances',[]) if fixed.get(a['id'])==fixed.get(b['id'])==r['ref'] and {mapped.get(a['id']),mapped.get(b['id'])}==set(r['textIds']) and extent<=min(.001,r['maxOverlapExtentRaw'])),None)
            if row is not None:numeric_contacts.append((a['id'],b['id'],extent))
            else:text_collisions.append((a['id'],b['id'],area))
    for t in texts:
        bb=box(t['bbox'])
        for ref,c in graph['parts'].items():
            if fixed.get(t['id'])==ref:continue
            if overlap(bb,box(c['bbox']))>EPS:body_collisions.append((t['id'],ref))
        for m in [m for m in plan['markers'] if m['kind']=='ground']:
            if overlap(bb,ground_box(m))>EPS:body_collisions.append((t['id'],m['id']))
        for i,(n,a,b) in enumerate(graph['segments']):
            if not seg_box(a,b,bb):continue
            okay=False;m=wire_names.get(t['id'])
            if m is not None:
                x,y=m['point']
                if n==m['net'] and ((a[1]==b[1]==y and 0<=y-bb[1]<=1.05) or (a[0]==b[0]==x and 0<=x-bb[0]<=1.05)):okay=True
            for row in policy.get('nativePinTextAllowances',[]):
                if mapped.get(t['id'])!=row['textId'] or fixed.get(t['id'])!=row['ref']:continue
                q=graph['pins'][(row['ref'],row['pin'])];pt=point((q['x'],q['y']));d=round(q['rotation']/90)%4
                intrude=max(0,pt[0]-bb[0] if d==2 else bb[2]-pt[0] if d==0 else bb[3]-pt[1] if d==1 else pt[1]-bb[1])
                if n==q['net'] and pt in (a,b) and intrude<=row['maxLeadIntrusion']:okay=True
            if okay:allowed.append((t['id'],i))
            else:wire_collisions.append((t['id'],i,n))
    return dict(passed=not(text_collisions or wire_collisions or body_collisions),textsChecked=len(texts),nativeSheetTextsChecked=len(sheet_text_ids),maximumExpectedTextEnvelopeDelta=envelope_delta,textOverlaps=text_collisions,wireTextContacts=wire_collisions,textBodyContacts=body_collisions,nativeOwnBaselineAndPinCaptionContacts=allowed,nativeFixedTextBoundaryRoundingContacts=numeric_contacts,measurement='actual unmodified native SVG, fresh Chrome getBBox; title field values and paper bounds require separate native readback',svgSha256=sha256(svg_path),snapshotSha256=sha256(raw))
