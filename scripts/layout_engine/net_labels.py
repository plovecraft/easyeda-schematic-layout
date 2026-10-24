"""Native wire-label placement on measured physical wire islands."""
import copy,math
from collections import defaultdict
from itertools import combinations
from .geometry import *
from .validator import DSU,segments,validate,texts

def adapt(page,policy,metrics):
    p=copy.deepcopy(page);labels=[m for m in p['markers'] if m['kind']!='ground'];p['markers']=[m for m in p['markers'] if m['kind']=='ground']
    ss=segments(p);ds=DSU()
    for i,j in combinations(range(len(ss)),2):
        n,a,b=ss[i];m,c,d=ss[j]
        if n!=m:continue
        hit=intersection(a,b,c,d)
        if hit is not None and (hit==('overlap',) or hit in (a,b,c,d)):ds.join(i,j)
    islands=defaultdict(list)
    for i,(n,a,b) in enumerate(ss):islands[(n,ds.find(i))].append((a,b))
    def root_at(net,pt):
        roots={ds.find(i) for i,(n,a,b) in enumerate(ss) if n==net and onseg(pt,a,b)}
        if len(roots)!=1:raise ValueError('label anchor has no unique physical island: '+net+' '+str(pt))
        return roots.pop()
    labeled=set()
    for m in labels:labeled.add((m['net'],root_at(m['net'],m['point'])))
    # A wire's net argument is omitted at execution. Direct internal nets need
    # one visible Name too, rather than a hidden implicit source-side name.
    for (net,root),lines in islands.items():
        if net=='GND' or (net,root) in labeled:continue
        a,b=next(((a,b) for a,b in lines if a[1]==b[1]),lines[0])
        labels.append(dict(id='internal-'+net+'-'+str(root),net=net,kind='label',scope=policy['namedIslandScopes'].get(net,'page'),point=a,label=dict(bbox=asbox((min(a[0],b[0]),a[1]+1,min(a[0],b[0])+metrics[net]['maxX']-metrics[net]['minX'],a[1]+8)))))
        policy['namedIslandScopes'][net]=labels[-1]['scope']
    bodies=[box(c['bbox']) for c in p['parts']]+[ground_box(m) for m in p['markers']]
    obstacles=[box(t['bbox']) for t in texts(p)];placed=[]
    # Longer names are less flexible; place those first, retaining a stable key.
    for old in sorted(labels,key=lambda m:(-(metrics[m['net']]['maxX']-metrics[m['net']]['minX']),m['id'])):
        net=old['net'];nm=metrics[net];root=root_at(net,old['point']);desired=box(old['label']['bbox']);options=[]
        for a,b in islands[(net,root)]:
            if a[1]!=b[1]:continue
            lo,hi=sorted((a[0],b[0]));xs={min(max(desired[0]-nm['minX'],lo),hi),min(max(old['point'][0],lo),hi),(lo+hi)/2}
            xs.update(range(math.ceil((lo-100)/5)*5,math.floor((hi+100)/5)*5+1,5))
            for x in xs:
                y=a[1];bb=(x+nm['minX'],y+nm['minY'],x+nm['maxX'],y+nm['maxY'])
                extension=[(lo,y),(x-5,y)] if x<lo else [(hi,y),(x+5,y)] if x>hi else []
                frame=next((box(f['rect']) for f in p.get('frames',[]) if inside(old['point'],box(f['rect']))),None)
                if frame is not None and (not inside((bb[0],bb[1]),grow(frame,-3)) or not inside((bb[2],bb[3]),grow(frame,-3)) or any(not inside(pt,grow(frame,-3)) for pt in extension)):continue
                if any(overlap(grow(bb,.35),o)>EPS for o in bodies+obstacles+placed):continue
                if extension:
                    u,v=extension
                    if any(seg_box(u,v,grow(o,.5)) for o in bodies+obstacles+placed):continue
                    blocked=False
                    for n,c,d in ss:
                        hit=intersection(u,v,c,d)
                        if n!=net and hit is not None and (hit==('overlap',) or hit in (u,v,c,d)):blocked=True;break
                    if blocked:continue
                blocked=False
                for n,c,d in ss:
                    if not seg_box(c,d,bb):continue
                    # Only this physical named line's normal text baseline is
                    # allowed. A vertical segment or another net stays blocked.
                    if n==net and c[1]==d[1]==y:continue
                    blocked=True;break
                if blocked:continue
                cost=abs(bb[0]-desired[0])+abs(bb[1]-desired[1])+abs(x-old['point'][0])*.05
                options.append((cost+((lo-x if x<lo else x-hi)*.5 if extension else 0),x,y,bb,extension))
        for a,b in islands[(net,root)]:
            if a[0]!=b[0]:continue
            lo,hi=sorted((a[1],b[1]));ys={min(max(desired[1]-nm['minY'],lo),hi),min(max(old['point'][1],lo),hi),(lo+hi)/2}
            ys.update(range(math.ceil(lo/5)*5,math.floor(hi/5)*5+1,5))
            for y in ys:
                x=a[0];bb=(x+nm['minX'],y+nm['minY'],x+nm['maxX'],y+nm['maxY'])
                frame=next((box(f['rect']) for f in p.get('frames',[]) if inside(old['point'],box(f['rect']))),None)
                if frame is not None and (not inside((bb[0],bb[1]),grow(frame,-3)) or not inside((bb[2],bb[3]),grow(frame,-3))):continue
                if any(overlap(grow(bb,.35),o)>EPS for o in bodies+obstacles+placed):continue
                blocked=False
                for n,c,d in ss:
                    if not seg_box(c,d,bb):continue
                    if n==net and c[0]==d[0]==x:continue
                    if n==net and c[1]==d[1]==y and onseg((x,y),c,d):continue
                    blocked=True;break
                if not blocked:options.append((25+abs(bb[0]-desired[0])+abs(bb[1]-desired[1]),x,y,bb,[]))
        if not options:raise ValueError('native label cannot fit on its actual wire: '+old['id'])
        _,x,y,bb,extension=min(options);m=copy.deepcopy(old);m.update(kind='label',point=(x,y),nativeLabel=True)
        if extension:p['wires'].append(dict(net=net,points=extension));ss=segments(p)
        m['label']=dict(id=old['id']+'-native-text',text=net,bbox=asbox(bb),fontSize=7.006200555911909,nativeMetrics=nm)
        p['markers'].append(m);placed.append(bb)
    p['nativeLabelContract']=dict(wireCreationNetArgument='omitted',oneVisibleNamePerPlannedMarker=True,metrics='official native SVG + Chrome ideographic label measurement',ownBaselineIntrusionMaximum=1)
    return p,policy
