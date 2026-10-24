# SPDX-FileCopyrightText: 2026 plovecraft
# SPDX-License-Identifier: AGPL-3.0-only
"""Choose the smallest supplied measured paper on which a valid packing fits."""
import copy,math
from .geometry import box,asbox,overlap,unionbox
from .model import save_json
from .packing import translated
from .validator import validate

def rectangle(value):
    b=box(value)
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in b) or b[2]<=b[0] or b[3]<=b[1]:
        raise ValueError('Paper rectangles must be finite and have positive dimensions')
    return b

def contained(a,b):return a[0]>=b[0] and a[1]>=b[1] and a[2]<=b[2] and a[3]<=b[3]

def select_paper(modules,config,metrics,report_path):
    from .pipeline import packed_page,safe_name
    papers=config['papers']
    if not isinstance(papers,list) or not papers or len(papers)>12:raise ValueError('Supply 1 to 12 measured paper alternatives')
    attempts=[];accepted=[];seen=set()
    for index,paper in enumerate(papers):
        name=safe_name(paper['id'])
        if name in seen:raise ValueError('Duplicate paper id')
        seen.add(name);outer=rectangle(paper['paperBBox']);usable=rectangle(paper['usableBounds'])
        if not contained(usable,outer) or not isinstance(paper.get('source'),str) or not paper['source'].strip():raise ValueError('Paper requires contained usable bounds and explicit geometry provenance')
        keepouts=[rectangle(k) for k in paper.get('keepouts',[])]
        if any(not contained(k,outer) for k in keepouts):raise ValueError('Paper keepout outside measured paper')
        # Native getBBox can return 210.00000000000009. Snap the placement
        # origin to the 5-raw design grid; preserve measured bounds unchanged.
        ox=math.ceil((usable[0]-1e-6)/5)*5;oy=math.ceil((usable[1]-1e-6)/5)*5
        width=math.floor((usable[2]-ox+1e-6)/5)*5;height=math.floor((usable[3]-oy+1e-6)/5)*5
        try:
            # Try useful widths up to the measured limit; do not scale symbols,
            # reduce text or alter electrical policies to make a paper fit.
            widths=sorted(set([width]+[w for w in config.get('widths',[]) if 0<w<=width]))
            source,page,policy,report=packed_page(modules,dict(widths=widths,maxHeight=height,aspectPenalty=config.get('aspectPenalty',50),packingOrderTrials=config.get('packingOrderTrials',0),titleFontSize=config.get('titleFontSize',12)),metrics)
            # Center the complete frame/title envelopes in the usable region;
            # keep all electrical geometry rigid and anchors on the design grid.
            used=unionbox([rectangle(f['rect']) for f in page['frames']])
            def centered(lo,hi,a,b):
                lower=math.ceil((lo-a-1e-6)/5)*5;upper=math.floor((hi-b+1e-6)/5)*5
                if lower>upper:raise ValueError('No centered grid placement fits')
                return max(lower,min(upper,round(((lo+hi-a-b)/2)/5)*5))
            ox=centered(usable[0],usable[2],used[0],used[2]);oy=centered(usable[1],usable[3],used[1],used[3])
            page=translated(page,ox,oy);report=validate(source,page,policy)
            occupied=[rectangle(f['rect']) for f in page['frames']]
            if not report['passed'] or any(not contained(b,usable) for b in occupied) or any(overlap(b,k)>0 for b in occupied for k in keepouts):raise ValueError('Packing violates page/keepout bounds or layout constraints')
            area=(outer[2]-outer[0])*(outer[3]-outer[1]);page.update(paperless=False,paper=copy.deepcopy(paper))
            page['paperPlacement']=dict(alignment='center in usable rectangle',offsetRaw=[ox,oy],gridRaw=5)
            row=dict(id=name,passed=True,paperArea=area,contentArea=report['metrics']['area'],utilization=report['metrics']['area']/area)
            accepted.append(((area,report['metrics']['area'],index),(source,page,policy,report),name))
        except ValueError as error:row=dict(id=name,passed=False,reason=str(error))
        attempts.append(row)
    selection=dict(passed=bool(accepted),candidates=attempts,scope='smallest area among supplied measured paper/usable-rectangle alternatives; no scaling or paper API mutation')
    if not accepted:
        save_json(report_path,selection);raise ValueError('No measured paper alternative fits; see paper-selection.json')
    _,result,name=min(accepted,key=lambda v:v[0]);selection['selected']=name;save_json(report_path,selection)
    return (*result,selection)
