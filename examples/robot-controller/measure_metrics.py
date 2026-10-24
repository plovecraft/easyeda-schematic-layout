# SPDX-FileCopyrightText: 2026 plovecraft
# SPDX-License-Identifier: AGPL-3.0-only
"""Identical read-only geometry metrics for both native schematic exports.

Input: components.list envelope, browser SVG getBBox JSON, original native SVG.
No circuit placement or routing is performed.
"""
import json,sys
from collections import defaultdict
from pathlib import Path
from lxml import etree

def wire_metrics(segments):
    axes=defaultdict(list)
    for x0,y0,x1,y1 in segments:
        if x0==x1 and y0!=y1:axes[('v',x0)].append(tuple(sorted((y0,y1))))
        elif y0==y1 and x0!=x1:axes[('h',y0)].append(tuple(sorted((x0,x1))))
        else:raise ValueError('Expected nonzero orthogonal native segment')
    merged=[]
    for (axis,constant),intervals in axes.items():
        union=[]
        for a,b in sorted(intervals):
            if union and a<=union[-1][1]+1e-7:union[-1]=(union[-1][0],max(union[-1][1],b))
            else:union.append((a,b))
        for a,b in union:merged.append((constant,a,constant,b) if axis=='v' else (a,constant,b,constant))
    endpoints={(x,y) for s in segments for x,y in ((s[0],s[1]),(s[2],s[3]))}
    incident=defaultdict(set)
    for x0,y0,x1,y1 in merged:
        points=sorted((x,y) for x,y in endpoints if (x0==x1==x and y0<=y<=y1) or (y0==y1==y and x0<=x<=x1))
        for a,b in zip(points,points[1:]):incident[a].add(b);incident[b].add(a)
    bends=0
    for p,neighbors in incident.items():
        if len(neighbors)!=2:continue
        a,b=neighbors
        if (a[0]==p[0])!=(b[0]==p[0]):bends+=1
    return dict(wireLength=round(sum(abs(x1-x0)+abs(y1-y0) for x0,y0,x1,y1 in merged),6),geometricBends=bends,uniqueIntervals=len(merged))

def metrics(snapshot,measurements,svg):
    raw=json.loads(Path(snapshot).read_text(encoding='utf-8-sig'));raw=raw.get('response',raw);r=raw.get('result',raw)
    measured=json.loads(Path(measurements).read_text(encoding='utf-8-sig'))
    tree=etree.parse(str(svg));excluded=set()
    for group in tree.getroot().iter():
        if group.get('c_partid') in ('sheet','table'):excluded.update(e.get('id') for e in group.iter() if e.get('id'))
    texts=[t for t in measured['elements'] if t['tag']=='text' and t['id'] not in excluded and t.get('text','').strip()]
    boxes=[c['bbox'] for c in r['components'] if c['componentType']!='sheet' and c.get('bbox')]+[t['bbox'] for t in texts]
    segments=[tuple(round(w[k],6) for k in ('x0','y0','x1','y1')) for w in r['wires']]
    for x0,y0,x1,y1 in segments:boxes.append(dict(minX=min(x0,x1),maxX=max(x0,x1),minY=min(y0,y1),maxY=max(y0,y1)))
    content={key:fun(b[key] for b in boxes) for key,fun in [('minX',min),('minY',min),('maxX',max),('maxY',max)]}
    return dict(**wire_metrics(segments),contentBounds=content,contentArea=round((content['maxX']-content['minX'])*(content['maxY']-content['minY']),6),contentTexts=len(texts),
                definition='Visible content bbox includes component/marker bodies, all non-sheet text and wires; excludes paper/titleblock and decorative module rectangles. Wire length unions coincident intervals. Geometric bends are degree-two 90-degree vertices, excluding T/X junctions. raw, Y-up.')
if __name__=='__main__':print(json.dumps(metrics(*sys.argv[1:4]),ensure_ascii=False,indent=2))
