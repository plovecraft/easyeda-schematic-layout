"""Import immutable native snapshots and SVG text envelopes; never edits EDA."""
import copy,hashlib,json
from pathlib import Path
from lxml import etree
from .geometry import box,shift,asbox,point,rotate,rotate_box

def load_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save_json(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def import_page(snapshot,svg,measurements):
    raw=load_json(snapshot);raw=raw.get('response',raw);r=raw.get('result',raw)
    assert r.get('wiresAvailable') is True and r.get('pinNetsAvailable') is True
    measured={e['id']:e for e in load_json(measurements)['elements']}
    tree=etree.parse(str(svg));root=tree.getroot()
    groups=[e for e in root.iter() if e.get('c_partid')=='part']
    texts={e.get('id'):e for e in root.iter() if etree.QName(e).localname=='text'}
    attributes=r['pagePrimitives']['attributes']
    parts=[];missing=[]
    for c in r['components']:
        if c.get('componentType')!='part':continue
        assert c.get('pinsAvailable') is True and all(not q.get('netAmbiguous') for q in c['pins'])
        pid=c['primitiveId'];matches=[g for g in groups if any((e.get('id') or '').startswith(pid+'-') for e in g.iter())]
        if len(matches)!=1:raise ValueError(f'unique native glyph unavailable: {pid}')
        group=matches[0];labels=[];fixed=[]
        movable={a['primitiveId']:a for a in attributes if a.get('ParentPrimitiveId')==pid and a.get('ValueVisible') is True and a.get('Key') in ('Name','Designator')}
        for e in group.iter():
            if etree.QName(e).localname!='text':continue
            tid=e.get('id');m=measured.get(tid)
            if m is None:missing.append(tid);continue
            t=dict(id=tid,text=''.join(e.itertext()),bbox=m['bbox'],parent=pid)
            if tid in movable:t.update(key=movable[tid]['Key'],native=movable[tid]);labels.append(t)
            else:fixed.append(t)
        parts.append(dict(ref=c['designator'],id=pid,x=c['x'],y=c['y'],bbox=c['bbox'],pins=copy.deepcopy(c['pins']),labels=labels,fixedTexts=fixed,
                          rotation=c['rotation'],mirror=c['mirror'],native=c,svg=etree.tostring(group,encoding='unicode')))
    if missing:raise ValueError(f'missing native text geometry: {missing}')
    return dict(schemaVersion=1,units='raw; Y-up; grid 5',parts=parts,wires=copy.deepcopy(r['wires']),
                provenance=dict(snapshot=str(Path(snapshot).resolve()),snapshotSha256=sha256(snapshot),svg=str(Path(svg).resolve()),svgSha256=sha256(svg),
                textGeometry='headless Chrome getBBox of unmodified EDA SVG, including all visible part texts',measurementSha256=sha256(measurements)),
                liveApplied=False)

def place(page,positions):
    out=copy.deepcopy(page);out['wires']=[];out['markers']=[];out['labels']=[]
    for p in out['parts']:
        ox,oy=p['x'],p['y'];nx,ny=positions[p['ref']];dx,dy=nx-ox,ny-oy
        p['translation']=[dx,dy];p['x'],p['y']=nx,ny;p['bbox']=asbox(shift(box(p['bbox']),dx,dy))
        for q in p['pins']:q['x']=round(q['x']+dx,6);q['y']=round(q['y']+dy,6)
        for t in p['labels']+p['fixedTexts']:t['bbox']=asbox(shift(box(t['bbox']),dx,dy));t['translation']=[0,0]
    return out

def pinmap(page):return {(p['ref'],q['pinNumber']):q for p in page['parts'] for q in p['pins']}

def pose(page,positions,rotations,native_rotation=False):
    out=place(page,positions);old={p['ref']:p for p in page['parts']}
    for p in out['parts']:
        target=rotations.get(p['ref'],p['rotation']);delta=(target-p['rotation'])*(1 if native_rotation else -1)
        if not delta:continue
        assert len(p['pins'])==2 and not p['fixedTexts'], 'only fully measured two-pin glyphs without fixed text may rotate offline'
        b=old[p['ref']];origin=(p['x'],p['y']);p['bodyRotation']=delta
        p['bbox']=asbox(rotate_box(box(p['bbox']),delta,origin));p['rotation']=target
        for q in p['pins']:
            q['x'],q['y']=rotate((q['x'],q['y']),delta,origin);q['rotation']=(q['rotation']+delta)%360
    if native_rotation:out['rotationConvention']='native-positive; explicit quarter-turn geometry convention'
    return out
