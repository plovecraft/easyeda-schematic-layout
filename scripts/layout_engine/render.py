"""Offline SVG preview preserving original measured component glyphs."""
from pathlib import Path
from lxml import etree
from .geometry import box,unionbox,grow,ground_box
NS='http://www.w3.org/2000/svg'

def el(tag,**attrs):return etree.Element('{'+NS+'}'+tag,{k.replace('_','-'):str(v) for k,v in attrs.items()})

def svg(page,path):
    boxes=[box(p['bbox']) for p in page['parts']]+[box(t['bbox']) for p in page['parts'] for t in p['labels']+p['fixedTexts']]
    boxes += [box(m['label']['bbox']) for m in page.get('markers',[]) if 'label' in m]
    boxes += [box(t['bbox']) for t in page.get('annotations',[])]
    boxes += [box(f['rect']) for f in page.get('frames',[])]
    boxes += [ground_box(m) for m in page.get('markers',[]) if m['kind']=='ground']
    boxes += [(x,y-10,x,y) for w in page['wires'] for x,y in w['points']]
    b=grow(unionbox(boxes),25);width=b[2]-b[0];height=b[3]-b[1]
    root=etree.Element('{'+NS+'}svg',nsmap={None:NS},width=str(width),height=str(height),viewBox=f'{b[0]} {-b[3]} {width} {height}')
    root.append(el('rect',x=b[0],y=-b[3],width=width,height=height,fill='#fff'))
    style=el('style');style.text='*{stroke-linejoin:round;stroke-linecap:round}.wire{stroke:#24763e;stroke-width:0.9;fill:none}.net{font-family:Arial;fill:#000080;stroke:none}';root.append(style)
    for f in page.get('frames',[]):
        b=box(f['rect']);root.append(el('rect',x=b[0],y=-b[3],width=b[2]-b[0],height=b[3]-b[1],fill='none',stroke=f['color'],stroke_width=.5,stroke_dasharray='6 7'))
    for w in page['wires']:
        line=el('polyline',points=' '.join(f'{x},{-y}' for x,y in w['points']),**{'class':'wire','data-net':w['net']});root.append(line)
    for p in page['parts']:
        g=etree.fromstring(p['svg'].encode());dx,dy=p.get('translation',[0,0]);outer=el('g',transform=f'translate({dx},{-dy})',data_ref=p['ref'])
        if p.get('bodyRotation'):
            ox,oy=p['native']['x'],p['native']['y'];body=el('g',transform=f"rotate({-p['bodyRotation']},{ox},{-oy})")
            movable={t['id'] for t in p['labels']}
            for child in list(g):
                if child.get('id') not in movable:g.remove(child);body.append(child)
            g.insert(0,body)
        for t in p['labels']:
            matches=[e for e in g.iter() if e.get('id')==t['id']]
            assert len(matches)==1,(p['ref'],t['id']);e=matches[0];tx,ty=t.get('translation',[0,0])
            if tx or ty:
                parent=e.getparent();i=parent.index(e);parent.remove(e);wrap=el('g',transform=f'translate({tx},{-ty})');wrap.append(e);parent.insert(i,wrap)
        outer.append(g);root.append(outer)
    for m in page.get('markers',[]):
        x,y=m['point']
        if m['kind']=='ground':
            # Offline standard ground glyph; exact native marker mapping is an
            # adapter step and has not been written to EDA.
            ground_path=f'M {x} {-y} v 10 m -10 0 h 20 m -16 5 h 12 m -8 5 h 4' if m.get('nativeGlyph') else f'M {x} {-y} v 4 m -7 0 h 14 m -11 3 h 8 m -6 3 h 4'
            root.append(el('path',d=ground_path,transform=f"rotate({-m.get('rotation',0)},{x},{-y})",fill='none',stroke='#A00000',stroke_width=0.9))
        if 'label' in m:
            t=m['label'];bb=box(t.get('unrotatedBBox',t['bbox']));text=el('text',x=bb[0]-t.get('bearingX',0),y=-bb[3]-t.get('bearingY',0),font_size=t['fontSize'],dominant_baseline='text-before-edge',**{'class':'net','id':t['id']});text.text=t['text']
            if m.get('nativeLabel'):
                text.set('x',str(x));text.set('y',str(-y));text.set('dominant-baseline','ideographic');text.text=None
                span=el('tspan',x=x,dx=0,dy=0);span.text=t['text'];text.append(span)
            if t.get('angle'):text.set('transform',f"rotate({-t['angle']},{x},{-y})")
            root.append(text)
    for z in page.get('junctions',[]):
        x,y=z['point'];root.append(el('circle',cx=x,cy=-y,r=1.5,fill='#24763e'))
    for t in page.get('annotations',[]):
        bb=box(t['bbox']);node=el('text',id=t['id'],x=bb[0]-t.get('bearingX',0),y=-bb[3]-t.get('bearingY',0),font_family='Arial',font_size=t['fontSize'],dominant_baseline='text-before-edge',fill='#666');node.text=t['text'];root.append(node)
    Path(path).write_bytes(etree.tostring(root,encoding='utf-8',xml_declaration=True))
