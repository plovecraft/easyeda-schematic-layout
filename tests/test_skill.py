"""Observable graph/geometry invariants and distribution behavior; never accesses EDA."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from layout_engine.model import load_json,save_json
from layout_engine.geometry import asbox,onseg,ground_box
from layout_engine.validator import validate,DSU
from layout_engine.native_verify import verify_graph
from layout_engine.pipeline import build_project,check_model,safe_name
from layout_engine.pin_exit import bad_pin_exits
from layout_engine.packing import pack
from layout_engine.combine import combine
from layout_engine.pipeline import conform
from layout_engine.geometry import shift,box
from layout_engine.drawing import native_ground,calibrate_ground_label
from install_skill import verify as verify_checksums
import hashlib


def native_fixture(page):
    parts=[];wires=[];attrs=[]
    for p in page['parts']:
        c=copy.deepcopy(p['native'])
        c.update(x=p['x'],y=p['y'],rotation=p['rotation'],bbox=p['bbox'],pins=p['pins'])
        parts.append(c)
    for i,w in enumerate(page['wires']):
        for a,b in zip(w['points'],w['points'][1:]):
            wires.append(dict(primitiveId='wire'+str(i),x0=a[0],y0=a[1],x1=b[0],y1=b[1]))
    for i,m in enumerate(page['markers']):
        x,y=m['point']
        if m['kind']=='ground':
            parts.append(dict(primitiveId='ground'+str(i),componentType='netflag',net='GND',
                              x=x,y=y,rotation=m['rotation'],bbox=asbox(ground_box(m))))
        else:
            touched=[w for w in wires if onseg((x,y),(w['x0'],w['y0']),(w['x1'],w['y1']))]
            assert touched
            attrs.append(dict(primitiveId='name'+str(i),Key='Name',Value=m['net'],ValueVisible=True,
                              ParentPrimitiveId=touched[0]['primitiveId'],X=x,Y=y))
    return dict(result=dict(components=parts,wires=wires,pagePrimitives=dict(attributes=attrs),
                            wiresAvailable=True,pinNetsAvailable=True))


class LayoutChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo=Path(os.environ.get('SCHEMATIC_TEST_DEMO',str(ROOT/'layout-demo'))).resolve()
        if not (cls.demo/'result/report.json').is_file():
            raise RuntimeError('First run: python scripts/layout.py demo --out ./layout-demo')
        folder=cls.demo/'result/pages/1'
        cls.source=load_json(folder/'source.json')
        cls.plan=load_json(folder/'candidate.json')
        cls.policy=load_json(folder/'policy.json')

    def rejected(self,plan,kind):
        report=validate(self.source,plan,self.policy)
        self.assertFalse(report['passed'])
        self.assertIn(kind,{r['type'] for r in report['errors']})

    def ground_profile_fixture(self,folder,inconsistent=False):
        components=[];attrs=[];elements=[]
        for i,(x,y) in enumerate([(100,100),(200,200)]):
            components.append(dict(primitiveId='g'+str(i),componentType='netflag',net='GND',x=x,y=y,rotation=0,bbox=asbox(ground_box(dict(point=(x,y),rotation=0,nativeGlyph=True)))))
            attrs.append(dict(primitiveId='a'+str(i),ParentPrimitiveId='g'+str(i),Key='Name',Value='GND',ValueVisible=True,Rotation=0))
            elements.append(dict(id='a'+str(i),tag='text',text='GND',bbox=asbox((x-9+(10 if inconsistent and i else 0),y-30,x+9,y-22))))
        snapshot=folder/'native.json';measurement=folder/'measurement.json'
        save_json(snapshot,dict(result=dict(components=components,pagePrimitives=dict(attributes=attrs))))
        save_json(measurement,dict(elements=elements))
        return snapshot,measurement

    def test_measured_ground_style_matches_multiple_native_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            snapshot,measurement=self.ground_profile_fixture(Path(temp))
            before=(snapshot.read_bytes(),measurement.read_bytes())
            profile=calibrate_ground_label(snapshot,measurement)
            ground=native_ground(dict(id='g',point=(200,200),rotation=0),{'GND':dict(width=18,height=8,bearingX=0,bearingY=0)},profile)
            self.assertEqual(ground['label']['bbox'],load_json(measurement)['elements'][1]['bbox'])
            self.assertEqual(before,(snapshot.read_bytes(),measurement.read_bytes()))

    def test_inconsistent_native_ground_styles_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=self.ground_profile_fixture(Path(temp),inconsistent=True)
            with self.assertRaises(ValueError):calibrate_ground_label(*paths)

    def test_ground_profile_refuses_uncalibrated_rotation(self):
        with tempfile.TemporaryDirectory() as temp:
            profile=calibrate_ground_label(*self.ground_profile_fixture(Path(temp)))
            with self.assertRaises(ValueError):
                native_ground(dict(id='g',point=(0,0),rotation=90),{'GND':dict(width=18,height=8)},profile)

    def test_all_three_pages_pass_and_keep_every_pin(self):
        pins=0
        for i in ('1','2','3'):
            folder=self.demo/'result/pages'/i
            report=validate(load_json(folder/'source.json'),load_json(folder/'candidate.json'),load_json(folder/'policy.json'))
            self.assertTrue(report['passed'],report['errors']);pins+=report['coverage']['pins']
        self.assertEqual(pins,21)

    def test_foreign_short_is_detected(self):
        page=copy.deepcopy(self.plan)
        a=next(q for p in page['parts'] if p['ref']=='U1' for q in p['pins'] if q['pinNumber']=='1')
        b=next(q for p in page['parts'] if p['ref']=='U1' for q in p['pins'] if q['pinNumber']=='4')
        page['wires'].append(dict(net='IN1',points=[(a['x'],a['y']),(a['x'],b['y']),(b['x'],b['y'])]))
        self.rejected(page,'wrong-net-at-pin')

    def test_missing_direct_wire_is_detected(self):
        page=copy.deepcopy(self.plan);page['wires']=[w for w in page['wires'] if w['net']!='3V3']
        self.rejected(page,'required-direct-pair-split')

    def test_nc_connection_is_detected(self):
        page=copy.deepcopy(self.plan)
        pin=next(q for p in page['parts'] for q in p['pins'] if q['noConnected'])
        page['wires'].append(dict(net='IN1',points=[(pin['x'],pin['y']),(pin['x']-20,pin['y'])]))
        self.rejected(page,'nc-connected')

    def test_text_overlap_is_detected(self):
        page=copy.deepcopy(self.plan);labels=page['parts'][0]['labels']
        labels[1]['bbox']=copy.deepcopy(labels[0]['bbox'])
        self.rejected(page,'text-overlap')

    def test_pin_contract_change_is_detected(self):
        page=copy.deepcopy(self.plan);page['parts'][0]['pins'][0]['net']='WRONG'
        self.rejected(page,'pin-contract-changed')

    def test_symbol_identity_change_is_detected(self):
        page=copy.deepcopy(self.plan);page['parts'][0]['native']['uniqueId']='changed'
        self.rejected(page,'component-identity-changed')

    def test_nonoutward_pin_contact_is_detected(self):
        page=copy.deepcopy(self.plan)
        pin=next(q for p in page['parts'] if p['ref']=='C1' for q in p['pins'] if q['pinNumber']=='1')
        page['wires'].append(dict(net=pin['net'],points=[(pin['x'],pin['y']),(pin['x']+10,pin['y'])]))
        self.assertTrue(bad_pin_exits(page));self.rejected(page,'pin-exit-direction')

    def test_same_name_does_not_replace_required_direct_connection(self):
        page=copy.deepcopy(self.plan)
        # Keep the net contracts and both endpoint stubs, remove the actual rail.
        for wire in page['wires']:
            if wire['net']=='3V3' and len(wire['points'])>2:
                a,*_,b=wire['points'];wire['points']=[a,(a[0],a[1]+5)]
                page['wires'].append(dict(net='3V3',points=[b,(b[0],b[1]+5)]));break
        self.rejected(page,'required-direct-pair-split')

    def test_native_fixture_accepts_actual_graph(self):
        report,_=verify_graph(native_fixture(self.plan),self.plan,self.policy)
        self.assertTrue(report['passed'])

    def test_native_missing_wire_rejected_despite_unchanged_pin_net(self):
        raw=native_fixture(self.plan);raw['result']['wires']=raw['result']['wires'][1:]
        with self.assertRaises(AssertionError):verify_graph(raw,self.plan,self.policy)

    def test_native_duplicate_label_rejected(self):
        raw=native_fixture(self.plan)
        raw['result']['pagePrimitives']['attributes'].append(copy.deepcopy(raw['result']['pagePrimitives']['attributes'][0]))
        with self.assertRaises(AssertionError):verify_graph(raw,self.plan,self.policy)

    def test_native_short_rejected_without_trusting_reported_nets(self):
        raw=native_fixture(self.plan)
        pins=next(c['pins'] for c in raw['result']['components'] if c.get('designator')=='U1')
        a=next(q for q in pins if q['pinNumber']=='1');b=next(q for q in pins if q['pinNumber']=='4')
        raw['result']['wires'] += [dict(primitiveId='short',x0=a['x'],y0=a['y'],x1=a['x'],y1=b['y']),
                                  dict(primitiveId='short',x0=a['x'],y0=b['y'],x1=b['x'],y1=b['y'])]
        with self.assertRaises(AssertionError):verify_graph(raw,self.plan,self.policy)

    def test_graph_segment_splitting_is_accepted(self):
        raw=native_fixture(self.plan);w=raw['result']['wires'].pop(0)
        mx=(w['x0']+w['x1'])/2;my=(w['y0']+w['y1'])/2
        raw['result']['wires'] += [dict(w,x1=mx,y1=my),dict(w,primitiveId=w['primitiveId']+'split',x0=mx,y0=my)]
        report,_=verify_graph(raw,self.plan,self.policy);self.assertTrue(report['passed'])

    def test_source_references_cannot_be_assigned_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest=load_json(self.demo/'layout.json')
            manifest['source']=str(self.demo/'source.json');manifest['measurements']=str(self.demo/'measurements.json')
            manifest['modules'][1]['positions']['U1']=[0,0]
            path=Path(temp)/'layout.json';save_json(path,manifest)
            with self.assertRaises(ValueError):build_project(path,Path(temp)/'out')

    def test_duplicate_model_identity_rejected(self):
        page=copy.deepcopy(self.source);page['parts'][1]['id']=page['parts'][0]['id']
        with self.assertRaises(ValueError):check_model(page)

    def test_path_traversal_rejected(self):
        for value in ('../other','a/b','..','',r'a\b'):
            with self.assertRaises(ValueError):safe_name(value)

    def test_pack_is_deterministic_and_rectangles_do_not_overlap(self):
        sizes={'a':(250,120),'b':(160,180),'c':(100,100)};order=list(sizes)
        layout=pack(sizes,500,600,order)
        self.assertEqual(layout,pack(sizes,500,600,order))
        boxes=list(layout.values())
        for i,(x,y,w,h) in enumerate(boxes):
            for a,b,c,d in boxes[i+1:]:self.assertTrue(x+w<=a or a+c<=x or y+h<=b or b+d<=y)

    def test_regeneration_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'result';build_project(self.demo/'layout.json',target)
            self.assertEqual(load_json(target/'pages/1/candidate.json'),self.plan)

    def test_combine_preserves_native_identity_and_namespaces_text(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);a=self.demo/'result/modules/module1/source.json';b=self.demo/'result/modules/module2/source.json'
            combine([a,b],[self.demo/'measurements.json']*2,temp/'combined')
            model=load_json(temp/'combined/source.json');self.assertEqual(len(model['parts']),4)
            self.assertEqual(model['parts'][0]['native'],load_json(a)['parts'][0]['native'])
            self.assertTrue(model['parts'][0]['labels'][0]['id'].startswith('page1__'))

    def test_cli_refuses_optimized_python(self):
        result=subprocess.run([sys.executable,'-O',str(ROOT/'scripts/layout.py'),'doctor'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)

    def test_supported_horizontal_bus_repair_preserves_direct_connection(self):
        page=copy.deepcopy(self.plan)
        pin=next(q for p in page['parts'] if p['ref']=='C1' for q in p['pins'] if q['pinNumber']=='1')
        row=pin['y']
        for wire in page['wires']:
            if wire['net']=='3V3' and len(wire['points'])>2:
                wire['points']=[(x,row if y==wire['points'][1][1] else y) for x,y in wire['points']]
                wire['points']=[v for i,v in enumerate(wire['points']) if not i or v!=wire['points'][i-1]]
        for marker in page['markers']:
            if marker['net']=='3V3':
                dx,dy=0,row-marker['point'][1];marker['point']=(marker['point'][0],row)
                marker['label']['bbox']=asbox(shift(box(marker['label']['bbox']),dx,dy))
        self.assertTrue(bad_pin_exits(page))
        result,policy,changes=conform(self.source,page,self.policy)
        self.assertTrue(changes);self.assertFalse(bad_pin_exits(result))
        self.assertTrue(validate(self.source,result,policy)['passed'])

    def test_multiple_modules_on_one_page_remain_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);manifest=load_json(self.demo/'layout.json')
            manifest['source']=str(self.demo/'source.json');manifest['measurements']=str(self.demo/'measurements.json')
            for module in manifest['modules']:module['page']='1'
            manifest['pages']=[dict(id='1',title='All modules',widths=[650,800],maxHeight=2000)]
            save_json(temp/'layout.json',manifest)
            report=build_project(temp/'layout.json',temp/'out')
            self.assertTrue(report['passed']);self.assertEqual(len(report['pages']),1)
            self.assertEqual(report['parts'],6)

    def test_checksum_detects_modified_source(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);(temp/'scripts').mkdir()
            (temp/'SKILL.md').write_text('skill',encoding='utf-8');(temp/'scripts/layout.py').write_text('code',encoding='utf-8')
            lines=[hashlib.sha256((temp/name).read_bytes()).hexdigest()+'  '+name for name in ['SKILL.md','scripts/layout.py']]
            (temp/'CHECKSUMS.sha256').write_text('\n'.join(lines),encoding='utf-8')
            self.assertEqual(len(verify_checksums(temp)),2)
            (temp/'scripts/layout.py').write_text('changed',encoding='utf-8')
            with self.assertRaises(ValueError):verify_checksums(temp)

    def test_checksum_manifest_cannot_escape_source(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);(temp/'CHECKSUMS.sha256').write_text('0'*64+'  ../other.py',encoding='utf-8')
            with self.assertRaises(ValueError):verify_checksums(temp)

    def test_native_extra_wire_is_rejected(self):
        raw=native_fixture(self.plan);wire=raw['result']['wires'][0]
        raw['result']['wires'].append(dict(primitiveId='extra',x0=wire['x0'],y0=wire['y0'],x1=wire['x0']+5,y1=wire['y0']))
        with self.assertRaises(AssertionError):verify_graph(raw,self.plan,self.policy)

    def test_unknown_nc_and_mirror_are_rejected(self):
        for change in ('mirror','unknown-nc'):
            source=copy.deepcopy(self.source)
            if change=='mirror':source['parts'][0]['mirror']=True
            else:source['parts'][0]['pins'][0]['noConnected']=None
            with self.assertRaises(ValueError):check_model(source)

    def test_page_local_names_from_different_sources_cannot_silently_merge(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);manifest=load_json(self.demo/'layout.json');model=load_json(self.demo/'source.json')
            for part in model['parts']:
                part['sourceDocument']='first' if part['ref'].endswith('1') else 'second'
                for pin in part['pins']:
                    if pin['net']=='IN2':pin['net']='IN1'
            for module in manifest['modules']:module['page']='1';module['scopes']['IN1']='page'
            manifest['pages']=[dict(id='1')];manifest['source']='source.json';manifest['measurements']=str(self.demo/'measurements.json')
            save_json(temp/'layout.json',manifest);save_json(temp/'source.json',model)
            with self.assertRaises(ValueError):build_project(temp/'layout.json',temp/'out')


if __name__=='__main__':unittest.main(verbosity=2)
