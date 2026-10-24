"""Require a real outward lead before a schematic wire bends or branches."""
import copy
from .geometry import point,onseg,intersection

def bad_pin_exits(page):
    bad=[]
    for p in page['parts']:
        for q in p['pins']:
            pt=point((q['x'],q['y']));direction=round(q['rotation']/90)%4;dx,dy=[(1,0),(0,1),(-1,0),(0,-1)][direction]
            for i,w in enumerate(page['wires']):
                for j,(a,b) in enumerate(zip(w['points'],w['points'][1:])):
                    a=point(a);b=point(b)
                    if not onseg(pt,a,b):continue
                    if any(abs((u[0]-pt[0])*dy-(u[1]-pt[1])*dx)>1e-5 or (u[0]-pt[0])*dx+(u[1]-pt[1])*dy<=0 for u in (a,b) if u!=pt):
                        bad.append(dict(ref=p['ref'],pin=q['pinNumber'],net=q['net'],rotation=q['rotation'],wire=i,segment=j,a=a,b=b))
    return bad

def flatten(page):
    return [dict(net=w['net'],points=[point(a),point(b)]) for w in page['wires'] for a,b in zip(w['points'],w['points'][1:]) if point(a)!=point(b)]

def shifted_bus(page,finding,distance):
    result=copy.deepcopy(page);ss=flatten(result);net=finding['net'];a,b=finding['a'],finding['b'];assert a[1]==b[1],'Only the observed perpendicular horizontal bus class is supported.'
    y=a[1];lo=min(a[0],b[0]);hi=max(a[0],b[0]);selected=set()
    while True:
        old=(lo,hi,len(selected))
        for i,w in enumerate(ss):
            u,v=w['points']
            if w['net']==net and u[1]==v[1]==y and max(min(u[0],v[0]),lo)<=min(max(u[0],v[0]),hi):
                selected.add(i);lo=min(lo,u[0],v[0]);hi=max(hi,u[0],v[0])
        if old==(lo,hi,len(selected)):break
    pins=[q for p in result['parts'] for q in p['pins'] if point((q['x'],q['y']))[1]==y and lo<=point((q['x'],q['y']))[0]<=hi]
    vertical=[q for q in pins if q['rotation']%180==90];assert vertical and len({q['rotation']%360 for q in vertical})==1
    sign=1 if vertical[0]['rotation']%360==90 else -1;ny=y+sign*distance;left,right=lo,hi;extra=[]
    for q in pins:
        x,_=point((q['x'],q['y']));rot=q['rotation']%360
        if rot%180==90:extra.append(dict(net=net,points=[(x,y),(x,ny)]))
        else:
            assert (x==lo and rot==0) or (x==hi and rot==180),'An interior parallel pin needs a separate routing case.'
            ex=x+(5 if rot==0 else -5);extra.extend([dict(net=net,points=[(x,y),(ex,y)]),dict(net=net,points=[(ex,y),(ex,ny)])])
            if x==lo:left=ex
            else:right=ex
    assert left<right and all(left<=point((q['x'],q['y']))[0]<=right for q in vertical)
    keep=[]
    for i,w in enumerate(ss):
        if i in selected:continue
        pts=w['points']
        if w['net']==net and pts[0][0]==pts[1][0]:
            pts=[(x,ny) if py==y and lo<=x<=hi else (x,py) for x,py in pts]
        if pts[0]!=pts[1]:keep.append(dict(net=w['net'],points=pts))
    keep.extend(extra);keep.append(dict(net=net,points=[(left,ny),(right,ny)]));result['wires']=keep
    for m in result['markers']:
        x,py=point(m['point'])
        if m['net']==net and py==y and lo<=x<=hi:
            nx=min(max(x,left),right);m['point']=(nx,ny)
            if 'label' in m:
                t=m['label'];t['bbox']={k:v+(nx-x if k.endswith('X') else ny-y) for k,v in t['bbox'].items()}
    # Explicit dots are presentation data. All joins in these candidates are T
    # or endpoint joins; recompute their positions after moving each bus.
    junctions=[];flat=flatten(result)
    for junction_net in {w['net'] for w in flat}:
        ns=[w['points'] for w in flat if w['net']==junction_net];nodes={p for pair in ns for p in pair}
        for p in nodes:
            dirs=set()
            for u,v in ns:
                if not onseg(p,u,v):continue
                for q in (u,v):
                    if q!=p:dirs.add((0 if q[0]>p[0] else 2) if q[1]==p[1] else (1 if q[1]>p[1] else 3))
            if len(dirs)>2:junctions.append(dict(net=junction_net,point=p))
    result['junctions']=junctions
    return result,dict(net=net,oldRow=y,newRow=ny,span=[lo,hi],outwardLead=5,verticalPins=len(vertical))
