"""Synthetic teaching fixture. It contains no vendor asset IDs or real circuit."""
import html,copy
from pathlib import Path
from .geometry import asbox
from .model import save_json,import_page


def create(out,browser,compare_placements=False):
    out=Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Demo output must be new or empty')
    out.mkdir(parents=True,exist_ok=True)
    components=[];attributes=[];groups=[];modules=[];extras=['GND','3V3']
    def text(tid,value,x,y):
        return f'<text id="{tid}" x="{x}" y="{-y}" font-family="Arial" font-size="7.006200555911909" dominant-baseline="text-before-edge">{html.escape(value)}</text>'
    def add(ref,name,x,y,body,pins,kind):
        pid='demo-'+ref
        rows=[]
        for i,(px,py,number,pin_name,net,nc,rotation) in enumerate(pins):
            rows.append(dict(pinNumber=str(number),pinName=pin_name,x=x+px,y=y+py,
                             net=net,noConnected=nc,rotation=rotation,netAmbiguous=False))
        bbox=asbox((x+body[0],y+body[1],x+body[2],y+body[3]))
        native=dict(primitiveId=pid,uniqueId='synthetic-'+ref,designator=ref,name=name,componentType='part',
                    device=dict(uuid='synthetic-demo',libraryUuid='synthetic-library'),footprint=None,symbol=None,
                    x=x,y=y,rotation=0,mirror=False,bbox=bbox,pins=rows,pinsAvailable=True,
                    addIntoBom=False,addIntoPcb=False,otherProperty={})
        components.append(native)
        labels=[]
        for key,value,ty in [('Designator',ref,y+body[3]+15),('Name',name,y+body[1]-18)]:
            tid=pid+'-'+key;labels.append(text(tid,value,x+body[0],ty))
            attributes.append(dict(primitiveId=tid,ParentPrimitiveId=pid,Key=key,Value=value,ValueVisible=True))
        if kind=='chip':
            shape=f'<rect x="{x-30}" y="{-y-30}" width="60" height="60" fill="none" stroke="#a22"/>'
            for row in rows:
                px,py=row['x'],row['y'];rot=row['rotation']
                ex=x+30 if rot==0 else x-30 if rot==180 else px
                ey=y+30 if rot==90 else y-30 if rot==270 else py
                shape+=f'<path d="M {px} {-py} L {ex} {-ey}" stroke="#a22"/>'
                if row['noConnected']:
                    shape+=f'<path d="M {px-3} {-py-3} l 6 6 m -6 0 l 6 -6" stroke="#399b51"/>'
        else:
            shape=f'<path d="M {x} {-y-15} V {-y-2} M {x-8} {-y-2} h 16 M {x-8} {-y+2} h 16 M {x} {-y+2} V {-y+15}" fill="none" stroke="#a22"/>'
        groups.append(f'<g c_partid="part" id="{pid}-glyph">{shape}{"".join(labels)}</g>')
    titles=['Controller','Power interface','Key interface']
    for i,title in enumerate(titles,1):
        core='U'+str(i);cap='C'+str(i);in_net='IN'+str(i);out_net='OUT'+str(i)
        extras.extend([in_net,out_net,dict(text=title,fontSize=12)])
        # Deliberately scattered source; imported pin coordinates are exact.
        add(core,'DEMO_IC',i*260,180,( -30,-30,30,30),[
            (-50,20,1,'IN',in_net,False,180),(50,20,2,'OUT',out_net,False,0),
            (0,50,3,'VCC','3V3',False,90),(0,-50,4,'GND','GND',False,270),
            (-50,-20,5,'NC','',True,180)],'chip')
        add(cap,'100n',i*260+150,-80,(-8,-2,8,2),[
            (0,15,1,'1','3V3',False,90),(0,-15,2,'2','GND',False,270)],'capacitor')
        modules.append(dict(name='module'+str(i),title=title,page=str(i),core=core,
            positions={core:[0,0],cap:[-110,85]},captionOptions={'_coreLabelY':115},
            scopes={'3V3':'global','GND':'global',in_net:'page',out_net:'page'},
            wires=[dict(net='3V3',points=[[core,'3'],[0,110],[-110,110],[cap,'1']])],
            stubs=[dict(ref=core,pin='1',length=70),dict(ref=core,pin='2',length=70),
                   dict(ref=core,pin='4',length=25),dict(ref=cap,pin='2',length=30)],
            markers=[dict(id='supply'+str(i),kind='label',net='3V3',point=[-50,110])],
            requiredPhysicalPairs=[[[core,'3'],[cap,'1']]]))
    native=dict(result=dict(components=components,wires=[],wiresAvailable=True,pinNetsAvailable=True,
                           pagePrimitives=dict(attributes=attributes)))
    save_json(out/'synthetic_snapshot.json',native)
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -320 1100 500">'+''.join(groups)+'</svg>'
    (out/'synthetic_source.svg').write_text(svg,encoding='utf-8')
    save_json(out/'extra_texts.json',extras)
    browser('measure',out/'synthetic_source.svg',out/'measurements.json',out/'extra_texts.json')
    model=import_page(out/'synthetic_snapshot.json',out/'synthetic_source.svg',out/'measurements.json')
    model['evidenceClass']='synthetic teaching fixture; not a real device or verified EDA project'
    save_json(out/'source.json',model)
    if compare_placements:
        for i,module in enumerate(modules,1):
            core='U'+str(i);cap='C'+str(i)
            horizontal_x=-80 if i!=2 else -360
            module['variants']=[dict(id='horizontal',positions={cap:[horizontal_x,90]},rotations={cap:270},
                wires=[dict(net='3V3',points=[[core,'3'],[0,90],[cap,'1']])],
                markers=[dict(id='supply'+str(i),kind='label',net='3V3',point=[-40,90])])]
            if i==1:
                module['positions'][cap]=[-340,85]
                module['wires']=[dict(net='3V3',points=[[core,'3'],[0,110],[-340,110],[cap,'1']])]
            if i==3:
                module['variants'].append(dict(id='invalid-overlap',positions={cap:[0,0]}))
    manifest=dict(schemaVersion=1,source='source.json',measurements='measurements.json',modules=modules,
                  pages=[dict(id=str(i),title=t,widths=[650,800],maxHeight=2000) for i,t in enumerate(titles,1)])
    save_json(out/'layout.json',manifest)
    return out/'layout.json'
