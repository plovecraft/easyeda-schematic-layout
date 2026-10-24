"""Functional drawing grammar; measured native positive Y-up rotations."""
import copy
from .geometry import *
from .model import pose,pinmap
from .labels import place_part_labels,NoLayout

class Drawing:
    def __init__(self,source,metrics,positions,rotations,core,scopes):
        self.page=pose(source,positions,rotations);self.metrics=metrics;self.core=core;self.scopes=scopes
        self.pm=pinmap(self.page);self.page.update(markers=[],junctions=[],labelAvoidWires=True)
    def xy(self,ref,num):q=self.pm[(ref,str(num))];return (q['x'],q['y'])
    def net(self,ref,num):return self.pm[(ref,str(num))]['net']
    def wire(self,net,*points):
        points=compact(points)
        if len(points)>1:self.page['wires'].append(dict(net=net,points=points))
    def ground(self,name,point,rotation=0):self.page['markers'].append(dict(id=name,net='GND',scope='global',kind='ground',point=point,rotation=rotation))
    def label(self,name,net,point,align='start',clearance=2,below=False):
        if net not in self.metrics:raise NoLayout('missing measured network text: '+net)
        m=self.metrics[net];w,h=m['width'],m['height'];x,y=point;left=x if align=='start' else x-w if align=='end' else x-w/2
        bottom=y-clearance-h if below else y+clearance
        self.page['markers'].append(dict(id=name,net=net,scope=self.scopes.get(net,'page'),kind='label',point=point,
            label=dict(id=name+'-text',text=net,bbox=asbox((left,bottom,left+w,bottom+h)),fontSize=7.006200555911909,bearingX=m['bearingX'],bearingY=m['bearingY'])))
    def finish(self,options=None):
        options=options or {};targets={}
        for p in self.page['parts']:
            b=box(p['bbox']);x,y=p['x'],p['y']
            for t in p['labels']:
                tb=box(t['bbox']);w,h=tb[2]-tb[0],tb[3]-tb[1];name=t['key']=='Name'
                if p['ref']==self.core:
                    dx=next(box(z['bbox'])[2]-box(z['bbox'])[0] for z in p['labels'] if z['key']=='Designator')+7
                    pt=(b[0]+(dx if name else 0),b[3]+3)
                elif options.get(p['ref'])=='left':pt=(b[0]-7-w,y-10 if name else y+2)
                elif p['rotation'] in (0,180):pt=(x-w/2,b[1]-h-3) if name else (x-w/2,b[3]+3)
                else:pt=(b[2]+7,y-10 if name else y+2)
                targets[t['id']]=[pt]
                if p['ref'] in options.get('_labelY',{}):
                    dw=next(box(z['bbox'])[2]-box(z['bbox'])[0] for z in p['labels'] if z['key']=='Designator')+7
                    targets[t['id']]=[(b[0]+(dw if name else 0),options['_labelY'][p['ref']])]
                    continue
                if options.get('_flex'):
                    if len(p['pins'])==2:
                        alternatives=[(x-w/2,b[3]+(13 if name else 3)),(b[2]+7,y-10 if name else y+2),(b[0]-7-w,y-10 if name else y+2),(x-w/2,b[1]-h-(3 if name else 13))]
                        targets[t['id']]+=[z for z in alternatives if z!=pt]
                    elif p['ref']==self.core and '_coreLabelY' in options:
                        targets[t['id']]=[(b[0]+(dx if name else 0),options['_coreLabelY'])]
        self.page['styleLabelTargets']=targets;place_part_labels(self.page)
        for net in sorted({w['net'] for w in self.page['wires']}):
            ss=[(a,b) for w in self.page['wires'] if w['net']==net for a,b in zip(w['points'],w['points'][1:])]
            for p in sorted({point(z) for a,b in ss for z in (a,b)}):
                dirs=set()
                for a,b in ss:
                    if onseg(p,a,b):
                        for q in (a,b):
                            if q!=p:dirs.add((0 if q[0]>p[0] else 2) if q[1]==p[1] else (1 if q[1]>p[1] else 3))
                if len(dirs)>=3:self.page['junctions'].append(dict(net=net,point=p))
        return self.page

def base_policy(source,scopes,pairs):
    return dict(allowedRotations={p['ref']:([0,90,180,270] if len(p['pins'])==2 and not p['fixedTexts'] else [p['rotation']]) for p in source['parts']},namedIslandScopes=scopes,requiredPhysicalPairs=pairs)

class NativeDrawing(Drawing):
    def __init__(self,source,metrics,positions,rotations,core,scopes):
        self.page=pose(source,positions,rotations,native_rotation=True);self.metrics=metrics;self.core=core;self.scopes=scopes
        self.pm=pinmap(self.page);self.page.update(markers=[],junctions=[],labelAvoidWires=True)
    def stub(self,ref,num,length=65,align=None,name=None):
        q=self.pm[(ref,str(num))]
        if q['noConnected']:return
        d=round(q['rotation']/90)%4;a=(q['x'],q['y']);v=DIRS[d];z=(a[0]+v[0]*length,a[1]+v[1]*length)
        self.wire(q['net'],a,z)
        if q['net']=='GND':self.ground(name or 'ground-'+ref+'-'+str(num),z,(d-3)*90)
        else:self.label(name or 'label-'+ref+'-'+str(num),q['net'],z,align or ('end' if d==0 else 'start' if d==2 else 'middle'),clearance=1)
    def ground(self,name,point,rotation=0):
        # Converted in finish_ground_geometry after ordinary captions are laid out.
        super().ground(name,point,rotation)

def native_ground(m,metrics):
    n=copy.deepcopy(m);n['nativeGlyph']=True;x,y=n['point'];rot=n.get('rotation',0);t=metrics['GND'];w,h=t['width'],t['height']
    ub=(x+11,y-10,x+11+w,y-10+h)
    n['label']=dict(id=n['id']+'-name',text='GND',bbox=asbox(rotate_box(ub,rot,(x,y))),unrotatedBBox=asbox(ub),angle=rot,fontSize=7.006200555911909,bearingX=t['bearingX'],bearingY=t['bearingY'])
    return n

def fit_native_grounds(page,metrics):
    """Find short legal ground leads using actual 21-raw native glyph bounds.

    Unlike the earlier simplified preview, native ground text is an obstacle.
    Every proposed extension is checked against parts, texts, pins and wire
    contacts by the independent validator before it can replace a marker.
    """
    oldgrounds=[m for m in page['markers'] if m['kind']=='ground'];page['markers']=[m for m in page['markers'] if m['kind']!='ground']
    bodies=[box(p['bbox']) for p in page['parts']]
    fixed=[box(t['bbox']) for p in page['parts'] for t in p['labels']+p['fixedTexts']]
    for old in oldgrounds:
        a=point(old['point']);preferred=old.get('rotation',0);choices=[]
        for rot in dict.fromkeys((preferred,0,90,270,180)):
            v=rotate((0,-1),rot)
            for dist in range(0,201,5):
                z=(a[0]+v[0]*dist,a[1]+v[1]*dist);choices.append((dist+(0 if rot==preferred else 25),rot,z,[a,z]))
                if dist>=20:
                    # An elbow can escape a nearby caption instead of forcing a
                    # long straight ground line through it.
                    for side in (-1,1):
                        for elbow in (15,30,50):
                            axis=rotate((side*elbow,0),rot);via=(a[0]+axis[0],a[1]+axis[1]);end=(via[0]+v[0]*dist,via[1]+v[1]*dist)
                            choices.append((dist+elbow+25,rot,end,[a,via,end]))
        best=None
        for cost,rot,z,path in sorted(choices,key=lambda x:(x[0],x[1],x[2])):
            m=native_ground(dict(old,point=z,rotation=rot),metrics);obstacles=[ground_box(m),box(m['label']['bbox'])]
            textboxes=fixed+[box(q['label']['bbox']) for q in page['markers'] if 'label' in q]
            markerboxes=[ground_box(q) for q in page['markers'] if q['kind']=='ground']
            if any(overlap(grow(b,.6),c)>EPS for b in obstacles for c in bodies+textboxes+markerboxes):continue
            existing=[(w['net'],p,q) for w in page['wires'] for p,q in zip(w['points'],w['points'][1:])]
            if any(seg_box(p,q,grow(b,.3)) for b in obstacles for _,p,q in existing):continue
            legal=True;crossings=0
            for p,q in zip(path,path[1:]):
                if p==q:continue
                if any(seg_box(p,q,grow(b,.3)) for b in bodies+textboxes+markerboxes):legal=False;break
                for net,c,d in existing:
                    hit=intersection(p,q,c,d)
                    if net!='GND' and hit is not None:
                        if hit==('overlap',) or hit in (p,q,c,d):legal=False;break
                        crossings+=1
                for part in page['parts']:
                    for pin in part['pins']:
                        if pin['net']!='GND' and onseg((pin['x'],pin['y']),p,q):legal=False
                if not legal:break
            if legal:
                option=(crossings*1000+cost,m,path)
                if best is None or option[0]<best[0]:best=option
                if crossings==0:break
        if best is None:raise NoLayout('native ground placement unavailable: '+old['id'])
        _,m,path=best
        if len(compact(path))>1:page['wires'].append(dict(net='GND',points=compact(path)))
        page['markers'].append(m)
    return page
