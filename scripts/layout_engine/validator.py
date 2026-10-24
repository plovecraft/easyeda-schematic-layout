# SPDX-FileCopyrightText: 2026 plovecraft
# SPDX-License-Identifier: AGPL-3.0-only
"""Independent segment-level checker; does not use Router or its occupancy grid.

An offline check of the retained page only, not native EDA or hardware acceptance.
"""
from collections import defaultdict
from itertools import combinations
from .geometry import EPS,box,overlap,seg_box,onseg,intersection,manhattan,unionbox,point,ground_box,rotate,rotate_box,shift

class DSU:
    def __init__(self):self.parent={}
    def find(self,x):
        if x not in self.parent:self.parent[x]=x
        if self.parent[x]!=x:self.parent[x]=self.find(self.parent[x])
        return self.parent[x]
    def join(self,a,b):self.parent[self.find(a)]=self.find(b)

def segments(page):
    return [(w['net'],point(a),point(b)) for w in page['wires'] for a,b in zip(w['points'],w['points'][1:]) if point(a)!=point(b)]

def texts(page):
    return [dict(t,ref=p['ref']) for p in page['parts'] for t in p['labels']+p['fixedTexts']]+[dict(m['label'],ref=m['id']) for m in page.get('markers',[]) if 'label' in m]+[dict(t,ref='annotation') for t in page.get('annotations',[])]

def validate(before,page,policy=None):
    policy=policy or {}
    errors=[];ss=segments(page);ds=DSU();pin_count=0
    def fail(kind,**detail):errors.append(dict(type=kind,**detail))
    for key in ('id','ref'):
        if len({p[key] for p in page['parts']})!=len(page['parts']):fail('duplicate-component-'+key)
    for left,right in combinations(page['parts'],2):
        if overlap(box(left['bbox']),box(right['bbox']))>EPS:fail('part-overlap',refs=[left['ref'],right['ref']])
    identifiers=[t['id'] for t in texts(page)]
    if len(set(identifiers))!=len(identifiers):fail('duplicate-text-id')
    if policy.get('enforcePinExitDirection'):
        from .pin_exit import bad_pin_exits
        for detail in bad_pin_exits(page):fail('pin-exit-direction',**detail)
    old={p['id']:p for p in before['parts']};new={p['id']:p for p in page['parts']}
    if set(old)!=set(new):fail('component-set-changed')
    immutable=('primitiveId','uniqueId','device','footprint','symbol','addIntoBom','addIntoPcb','otherProperty','designator','name','subPartName')
    for pid,p in new.items():
        if pid not in old:continue
        for key in ('mirror','svg'):
            if p.get(key)!=old[pid].get(key):fail('locked-glyph-changed',ref=p['ref'],field=key)
        if p['rotation'] not in policy.get('allowedRotations',{}).get(p['ref'],[old[pid]['rotation']]):fail('unapproved-rotation',ref=p['ref'])
        sign=1 if policy.get('rotationConvention')=='native-positive' else -1
        delta=sign*(p['rotation']-old[pid]['rotation'])
        if p.get('bodyRotation',0)%360!=delta%360:fail('glyph-pose-mismatch',ref=p['ref'])
        expected_body=rotate_box(shift(box(old[pid]['bbox']),p['x']-old[pid]['x'],p['y']-old[pid]['y']),delta,(p['x'],p['y']))
        if any(abs(a-b)>1e-5 for a,b in zip(box(p['bbox']),expected_body)):fail('body-envelope-changed',ref=p['ref'])
        original_text={t['id']:t['text'] for t in old[pid]['labels']+old[pid]['fixedTexts']}
        actual_text={t['id']:t['text'] for t in p['labels']+p['fixedTexts']}
        if original_text!=actual_text:fail('visible-text-changed',ref=p['ref'])
        dx,dy=p['x']-old[pid]['x'],p['y']-old[pid]['y']
        if point(p.get('translation',[0,0]))!=point((dx,dy)):
            fail('glyph-translation-mismatch',ref=p['ref'])
        original_geometry={t['id']:t for t in old[pid]['labels']+old[pid]['fixedTexts']}
        for category in ('labels','fixedTexts'):
            for t in p[category]:
                if t['id'] not in original_geometry:continue
                tx,ty=t.get('translation',[0,0]) if category=='labels' else (0,0)
                expected_text=shift(box(original_geometry[t['id']]['bbox']),dx+tx,dy+ty)
                if any(abs(a-b)>1e-5 for a,b in zip(box(t['bbox']),expected_text)):
                    fail('text-envelope-transform-mismatch',ref=p['ref'],text=t['id'])
        for key in immutable:
            if p['native'].get(key)!=old[pid]['native'].get(key):fail('component-identity-changed',ref=p['ref'],field=key)
        original={q['pinNumber']:q for q in old[pid]['pins']}
        if set(original)!={q['pinNumber'] for q in p['pins']}:fail('pin-set-changed',ref=p['ref'])
        for q in p['pins']:
            pin_count+=1;o=original[q['pinNumber']]
            if any(q.get(k)!=o.get(k) for k in ('net','noConnected','pinName')):fail('pin-contract-changed',ref=p['ref'],pin=q['pinNumber'])
            delta=sign*(p['rotation']-old[pid]['rotation']);expected=rotate((o['x']-old[pid]['x'],o['y']-old[pid]['y']),delta)
            if point((q['x']-p['x'],q['y']-p['y']))!=expected or q['rotation']!=(o['rotation']+delta)%360:fail('pin-pose-changed',ref=p['ref'],pin=q['pinNumber'])
            pt=point((q['x'],q['y']));touch=[i for i,(n,a,b) in enumerate(ss) if onseg(pt,a,b)]
            if q['noConnected']:
                if touch:fail('nc-connected',ref=p['ref'],pin=q['pinNumber'])
            elif not touch:fail('pin-unwired',ref=p['ref'],pin=q['pinNumber'])
            for i in touch:
                if ss[i][0]!=q['net']:fail('wrong-net-at-pin',ref=p['ref'],pin=q['pinNumber'],actual=ss[i][0],expected=q['net'])
    for i,(n,a,b) in enumerate(ss):
        ds.find(i)
        if a[0]!=b[0] and a[1]!=b[1]:fail('diagonal-wire',segment=i)
        for p in page['parts']:
            if seg_box(a,b,box(p['bbox'])):fail('wire-through-body',segment=i,ref=p['ref'])
            pb=box(p['bbox'])
            for q in p['pins']:
                if q['net']==n and not q['noConnected']:continue
                pp=(q['x'],q['y']);d=round(q['rotation']/90)%4
                end=(pb[2],pp[1]) if d==0 else (pp[0],pb[3]) if d==1 else (pb[0],pp[1]) if d==2 else (pp[0],pb[1])
                if intersection(a,b,pp,end) is not None:fail('wire-through-foreign-pin-stem',segment=i,ref=p['ref'],pin=q['pinNumber'])
        for m in page.get('markers',[]):
            if m['kind']=='ground':
                bb=ground_box(m)
                if seg_box(a,b,bb):fail('wire-through-ground-glyph',segment=i,marker=m['id'])
    cross=set()
    for i,j in combinations(range(len(ss)),2):
        n,a,b=ss[i];m,c,d=ss[j];hit=intersection(a,b,c,d)
        if hit is None:continue
        if n==m:
            # Same-net T/end contacts join. A same-net interior X only joins when
            # the candidate explicitly includes an electrical junction.
            joined=hit==('overlap',) or hit in (a,b,c,d) or any(z['net']==n and point(z['point'])==hit for z in page.get('junctions',[]))
            if joined:ds.join(i,j)
        elif hit==('overlap',) or hit in (a,b,c,d):fail('foreign-net-contact',segments=[i,j],nets=[n,m],point=hit)
        else:cross.add((tuple(sorted((n,m))),hit))
    all_text=texts(page);text_overlaps=[];wire_text=[];body_text=[];inherited_pin_caption_contacts=[];native_label_baselines=[];native_text_rounding=[]
    for m in page.get('markers',[]):
        if 'label' not in m:continue
        t=m['label']
        if t.get('fontSize')!=7.006200555911909:
            fail('marker-font-changed',marker=m['id'])
        if m.get('nativeLabel'):
            metric=t.get('nativeMetrics');x,y=m['point']
            if not metric or any(abs(t['bbox'][key]-(metric[key]+(x if key.endswith('X') else y)))>1e-5 for key in ('minX','minY','maxX','maxY')):
                fail('native-label-envelope-mismatch',marker=m['id'])
    for i,j in combinations(range(len(all_text)),2):
        a,b=all_text[i],all_text[j];area=overlap(box(a['bbox']),box(b['bbox']))
        if area>EPS:
            aa=box(a['bbox']);bb=box(b['bbox']);extent=min(min(aa[2],bb[2])-max(aa[0],bb[0]),min(aa[3],bb[3])-max(aa[1],bb[1]))
            row=next((r for r in policy.get('nativeTextBoundaryAllowances',[]) if r['ref']==a['ref']==b['ref'] and set(r['textIds'])=={a['id'],b['id']} and extent<=min(.001,r['maxOverlapExtentRaw'])),None)
            if row is not None:native_text_rounding.append(dict(a=a['id'],b=b['id'],extentRaw=extent,area=area))
            else:text_overlaps.append(dict(a=a['id'],b=b['id'],area=round(area,4)))
    for t in all_text:
        # Internal native pin text is intentionally inside its own symbol body.
        fixed=any(t['id']==u['id'] for p in page['parts'] for u in p['fixedTexts'])
        for p in page['parts']:
            if fixed and p['ref']==t['ref']:continue
            if overlap(box(t['bbox']),box(p['bbox']))>EPS:body_text.append(dict(text=t['id'],ref=p['ref']))
        for m in page.get('markers',[]):
            if m['kind']=='ground':
                if overlap(box(t['bbox']),ground_box(m))>EPS:body_text.append(dict(text=t['id'],ref=m['id']))
        for i,(n,a,b) in enumerate(ss):
            if seg_box(a,b,box(t['bbox'])):
                allowed=False
                marker=next((m for m in page.get('markers',[]) if m.get('nativeLabel') and m['id']==t['ref']),None)
                if marker is not None:
                    x,y=marker['point'];bb=box(t['bbox'])
                    island={ds.find(j) for j,(nn,c,d) in enumerate(ss) if nn==marker['net'] and onseg((x,y),c,d)}
                    if n==marker['net'] and a[1]==b[1]==y and ds.find(i) in island and 0<=y-bb[1]<=1.05:
                        allowed=True;native_label_baselines.append(dict(marker=marker['id'],segment=i,intrusion=y-bb[1]))
                    elif n==marker['net'] and a[0]==b[0]==x and ds.find(i) in island and 0<=x-bb[0]<=1.05:
                        allowed=True;native_label_baselines.append(dict(marker=marker['id'],segment=i,intrusion=x-bb[0],axis='vertical'))
                for row in policy.get('nativePinTextAllowances',[]):
                    if row['textId']!=t['id'] or row['ref']!=t['ref'] or not fixed:continue
                    part=next(p for p in page['parts'] if p['ref']==row['ref']);pin=next(q for q in part['pins'] if q['pinNumber']==row['pin'])
                    pt=point((pin['x'],pin['y']));bb=box(t['bbox']);d=round(pin['rotation']/90)%4
                    intrude=max(0,pt[0]-bb[0] if d==2 else bb[2]-pt[0] if d==0 else bb[3]-pt[1] if d==1 else pt[1]-bb[1])
                    if n==pin['net'] and not pin['noConnected'] and pt in (a,b) and intrude<=row['maxLeadIntrusion']:
                        allowed=True;inherited_pin_caption_contacts.append(dict(text=t['id'],ref=row['ref'],pin=row['pin'],segment=i,intrusion=intrude));break
                if not allowed:wire_text.append(dict(text=t['id'],segment=i,net=n))
    if text_overlaps:fail('text-overlap',details=text_overlaps)
    if wire_text:fail('wire-through-text',details=wire_text)
    if body_text:fail('text-over-body',details=body_text)
    # Reconstruct physical islands, then check named ground islands separately.
    net_islands=defaultdict(set);marker_islands=defaultdict(set)
    for i,(n,_,_) in enumerate(ss):net_islands[n].add(ds.find(i))
    for m in page.get('markers',[]):
        pt=point(m['point']);touch=[i for i,(n,a,b) in enumerate(ss) if onseg(pt,a,b)]
        if not touch:fail('floating-marker',marker=m['id'])
        for i in touch:
            if ss[i][0]!=m['net']:fail('marker-net-mismatch',marker=m['id'])
            marker_islands[m['net']].add(ds.find(i))
        required_scope=policy.get('namedIslandScopes',{}).get(m['net'])
        if required_scope and m.get('scope')!=required_scope:fail('marker-scope-changed',marker=m['id'])
    for n,islands in net_islands.items():
        if n=='GND' or n in policy.get('namedIslandScopes',{}):
            if not islands<=marker_islands[n]:fail('unnamed-net-island',net=n,count=len(islands-marker_islands[n]))
        elif len(islands)!=1:fail('direct-net-split',net=n,islands=len(islands))
    pins={(p['ref'],q['pinNumber']):q for p in page['parts'] for q in p['pins']}
    for left,right in policy.get('requiredPhysicalPairs',[]):
        qs=[pins[tuple(left)],pins[tuple(right)]];roots=[]
        for q in qs:
            roots.append({ds.find(i) for i,(n,a,b) in enumerate(ss) if n==q['net'] and onseg((q['x'],q['y']),a,b)})
        if not roots[0]&roots[1]:fail('required-direct-pair-split',pins=[left,right])
    # Degrees computed from full segments (including T points), independently of
    # the A* path representation, for a consistent before/after bend metric.
    bends=0;length=sum(manhattan(a,b) for _,a,b in ss)
    for n in net_islands:
        ns=[(a,b) for net,a,b in ss if net==n];nodes={p for a,b in ns for p in (a,b)}
        for p in nodes:
            dirs=set()
            for a,b in ns:
                if not onseg(p,a,b):continue
                for q in (a,b):
                    if q!=p:dirs.add((0 if q[0]>p[0] else 2) if q[1]==p[1] else (1 if q[1]>p[1] else 3))
            if len(dirs)==2 and dirs not in ({0,2},{1,3}):bends+=1
    boxes=[box(p['bbox']) for p in page['parts']]+[box(t['bbox']) for t in all_text]+[(x,y,x,y) for _,a,b in ss for x,y in (a,b)]
    bounds=unionbox(boxes)
    return dict(status='offline-verified' if not errors else 'candidate-rejected',passed=not errors,errors=errors,
                nativePinCaptionContacts=inherited_pin_caption_contacts,nativeWireLabelBaselineContacts=native_label_baselines,nativeTextBoundaryRoundingContacts=native_text_rounding,
                coverage=dict(parts=len(page['parts']),pins=pin_count,visiblePartTexts=sum(len(p['labels'])+len(p['fixedTexts']) for p in page['parts']),markerTexts=sum('label' in m for m in page.get('markers',[])),
                              annotationTexts=len(page.get('annotations',[])),
                              textMeasurement='native SVG Chrome getBBox',electricalScope='retained single-page graph; explicitly scoped named islands plus required direct physical pin pairs' if policy else 'retained single-page graph; GND named globally; all other local pin islands must remain physically connected',liveApplied=False,nativePersistenceVerified=False),
                metrics=dict(textOverlapCount=len(text_overlaps),textOverlapArea=round(sum(z['area'] for z in text_overlaps),3),wireTextContacts=len(wire_text),textBodyContacts=len(body_text),
                             crossings=len(cross),bends=bends,wireLength=round(length,3),width=round(bounds[2]-bounds[0],3),height=round(bounds[3]-bounds[1],3),area=round((bounds[2]-bounds[0])*(bounds[3]-bounds[1]),3)))

def native_baseline(page):
    """Normalize exact native segments; infer tree names only from physical pins."""
    import copy
    out=copy.deepcopy(page);groups=defaultdict(list)
    for w in page['wires']:groups[w['primitiveId']].append(w)
    out['wires']=[];unknown=[]
    for wid,ws in groups.items():
        ns={q['net'] for p in page['parts'] for q in p['pins'] if not q['noConnected'] and any(onseg((q['x'],q['y']),(w['x0'],w['y0']),(w['x1'],w['y1'])) for w in ws)}
        if len(ns)!=1:unknown.append(dict(wire=wid,nets=sorted(ns)));continue
        seen=set();net=ns.pop()
        for w in ws:
            a=point((w['x0'],w['y0']));b=point((w['x1'],w['y1']));key=tuple(sorted((a,b)))
            if key not in seen and a!=b:out['wires'].append(dict(net=net,points=[a,b]));seen.add(key)
    if unknown:raise ValueError('native tree net inference incomplete: '+str(unknown))
    out['markers']=[]
    return out
