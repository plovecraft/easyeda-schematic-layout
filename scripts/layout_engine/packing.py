"""Rigid module transforms and best-short-side free-rectangle packing."""
import copy,math
from .geometry import *
from .validator import texts

def bounds(page):
    boxes=[box(p['bbox']) for p in page['parts']]+[box(t['bbox']) for t in texts(page)]
    boxes += [(x,y,x,y) for w in page['wires'] for x,y in w['points']]
    boxes += [ground_box(m) for m in page['markers'] if m['kind']=='ground']
    return unionbox(boxes)

def translated(page,dx,dy):
    p=copy.deepcopy(page)
    for c in p['parts']:
        c['x']+=dx;c['y']+=dy;c['bbox']=asbox(shift(box(c['bbox']),dx,dy));a=c.get('translation',[0,0]);c['translation']=[a[0]+dx,a[1]+dy]
        for q in c['pins']:q['x']+=dx;q['y']+=dy
        for t in c['labels']+c['fixedTexts']:t['bbox']=asbox(shift(box(t['bbox']),dx,dy))
    for w in p['wires']:w['points']=[(x+dx,y+dy) for x,y in w['points']]
    for m in p['markers']:
        m['point']=(m['point'][0]+dx,m['point'][1]+dy)
        if 'label' in m:
            m['label']['bbox']=asbox(shift(box(m['label']['bbox']),dx,dy))
            if 'unrotatedBBox' in m['label']:m['label']['unrotatedBBox']=asbox(shift(box(m['label']['unrotatedBBox']),dx,dy))
    for t in p.get('annotations',[]):t['bbox']=asbox(shift(box(t['bbox']),dx,dy))
    for f in p.get('frames',[]):f['rect']=asbox(shift(box(f['rect']),dx,dy))
    for z in p.get('junctions',[]):z['point']=(z['point'][0]+dx,z['point'][1]+dy)
    return p

def merged(items):
    result=dict(schemaVersion=1,units='raw; Y-up; grid 5',rotationConvention='native-positive',liveApplied=False,parts=[],wires=[],markers=[],annotations=[],junctions=[])
    for p in items:
        for key in ('parts','wires','markers','annotations','junctions'):result[key]+=copy.deepcopy(p.get(key,[]))
    return result

def merge_policy(items):
    out=dict(allowedRotations={},namedIslandScopes={},requiredPhysicalPairs=[],nativePinTextAllowances=[],rotationConvention='native-positive')
    for p in items:
        out['allowedRotations'].update(p['allowedRotations']);out['namedIslandScopes'].update(p['namedIslandScopes']);out['requiredPhysicalPairs']+=p['requiredPhysicalPairs'];out['nativePinTextAllowances']+=p.get('nativePinTextAllowances',[])
    return out

def pack(rects,width,height,order):
    free=[(0,0,width,height)];placed={}
    for name in order:
        w,h=rects[name];choices=[]
        for x,y,fw,fh in free:
            if w<=fw and h<=fh:choices.append((min(fw-w,fh-h),y,x,max(fw-w,fh-h),x,y,w,h))
        if not choices:return None
        *_,x,y,w,h=min(choices);used=(x,y,w,h);placed[name]=used;fresh=[]
        for a,b,c,d in free:
            if x>=a+c or x+w<=a or y>=b+d or y+h<=b:fresh.append((a,b,c,d));continue
            if x>a:fresh.append((a,b,x-a,d))
            if x+w<a+c:fresh.append((x+w,b,a+c-x-w,d))
            if y>b:fresh.append((a,b,c,y-b))
            if y+h<b+d:fresh.append((a,y+h,c,b+d-y-h))
        free=[r for i,r in enumerate(fresh) if r[2]>0 and r[3]>0 and not any(i!=j and r[0]>=s[0] and r[1]>=s[1] and r[0]+r[2]<=s[0]+s[2] and r[1]+r[3]<=s[1]+s[3] and (r!=s or i>j) for j,s in enumerate(fresh))]
    return placed
