# SPDX-FileCopyrightText: 2026 plovecraft
# SPDX-License-Identifier: AGPL-3.0-only
"""Finite collision-free caption search; no live EDA operations."""
from .geometry import *
class NoLayout(RuntimeError): pass

def marker_boxes(page):
    # Ground bars are real visible obstacles, not just a zero-area net anchor.
    return [(m['id'],m['net'],ground_box(m)) for m in page.get('markers',[]) if m['kind']=='ground']

def pin_stems(page):
    out=[]
    for p in page['parts']:
        b=box(p['bbox'])
        for q in p['pins']:
            a=point((q['x'],q['y']));d=round(q['rotation']/90)%4
            end=(b[2],a[1]) if d==0 else (a[0],b[3]) if d==1 else (b[0],a[1]) if d==2 else (a[0],b[1])
            out.append((p['ref'],q['pinNumber'],q.get('net') or 'NC:'+p['ref']+':'+q['pinNumber'],a,end))
    return out

def place_part_labels(page):
    """Finite candidates; preserve exact strings, glyphs, font sizes and rotations."""
    fixed=[(p['ref'],box(t['bbox'])) for p in page['parts'] for t in p['fixedTexts']]
    fixed += [('annotation',box(t['bbox'])) for t in page.get('annotations',[])]
    fixed += [(m['id'],box(m['label']['bbox'])) for m in page.get('markers',[]) if 'label' in m]
    bodies=[box(p['bbox']) for p in page['parts']]+[grow(b,1) for _,_,b in marker_boxes(page)]
    stems=pin_stems(page);chosen=[];moves=[]
    for p in page['parts']:
        for q in p['pins']:
            d=round(q['rotation']/90)%4;a=(q['x'],q['y']);z=(a[0]+DIRS[d][0]*10,a[1]+DIRS[d][1]*10)
            stems.append((p['ref'],q['pinNumber'],q['net'],a,z))
    ordered=sorted([(p,t) for p in page['parts'] for t in p['labels']],key=lambda v:(0 if v[0]['ref']==page.get('coreRef') else 1,0 if v[1]['key']=='Designator' else 1,-(box(v[1]['bbox'])[2]-box(v[1]['bbox'])[0]),v[1]['id']))
    for p,t in ordered:
        old=box(t['bbox']);w,h=old[2]-old[0],old[3]-old[1];b=box(p['bbox']);x,y=p['x'],p['y'];name=t['key']=='Name'
        strict_targets=page.get('styleLabelTargets',{}).get(t['id'])
        targets=strict_targets or [(old[0],old[1])]
        if not strict_targets:
            for margin in (10,15,25,40):
                targets += [(b[2]+margin,y-(h+3 if name else -2)),(b[0]-margin-w,y-(h+3 if name else -2)),
                            (b[0],b[3]+margin+(h+3 if not name else 0)),(b[0],b[1]-margin-h-(h+3 if name else 0))]
        candidates=[]
        for rank,(tx,ty) in enumerate(targets):
            nb=(tx,ty,tx+w,ty+h)
            if any(overlap(grow(nb,2),r)>EPS for r in bodies):continue
            if any(overlap(grow(nb,1.5),r)>EPS for _,r in fixed):continue
            if any(seg_box(a,z,grow(nb,2)) for _,_,_,a,z in stems):continue
            if any(overlap(grow(nb,2),r)>EPS for r in chosen):continue
            if page.get('labelAvoidWires') and any(seg_box(a,z,grow(nb,1)) for wire in page['wires'] for a,z in zip(wire['points'],wire['points'][1:])):continue
            displacement=abs(tx-old[0])+abs(ty-old[1])
            if displacement>180 and not strict_targets:continue
            candidates.append((displacement+(rank*1000000 if strict_targets else 0),tx,ty,nb))
        if not candidates:raise NoLayout('no safe label candidate: '+p['ref']+' '+t['key'])
        _,tx,ty,nb=min(candidates);t['translation']=[tx-old[0],ty-old[1]];t['bbox']=asbox(nb);chosen.append(nb)
        if t['translation']!=[0,0]:moves.append(dict(ref=p['ref'],key=t['key'],delta=t['translation']))
    return moves
