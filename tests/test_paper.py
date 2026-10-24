"""Measured paper fit behavior, with purely synthetic fixture geometry."""
import copy,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from layout_engine.model import load_json
from layout_engine.paper import select_paper

class PaperChoice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        demo=Path(os.environ.get('SCHEMATIC_TEST_DEMO',str(ROOT/'layout-demo')))
        f=demo/'result/modules/module1'
        cls.modules={'m':dict(source=load_json(f/'source.json'),candidate=load_json(f/'candidate.json'),policy=load_json(f/'policy.json'),title='Controller')}
        cls.metrics=load_json(demo/'measurements.json')['annotationMetrics']
    def paper(self,name,w,h):return dict(id=name,paperBBox=dict(minX=0,minY=0,maxX=w,maxY=h),usableBounds=dict(minX=20,minY=100,maxX=w-20,maxY=h-20),keepouts=[dict(minX=0,minY=0,maxX=w,maxY=80)],source='synthetic measured fixture')
    def select(self,papers):
        with tempfile.TemporaryDirectory() as d:return select_paper(self.modules,dict(papers=papers),self.metrics,Path(d)/'paper-selection.json')
    def test_smallest_fitting_paper_wins_without_input_order_bias(self):
        *_,p=self.select([self.paper('large',900,900),self.paper('small',500,600)])
        self.assertEqual(p['selected'],'small')
    def test_too_small_fails_and_larger_paper_is_selected(self):
        *_,p=self.select([self.paper('tiny',180,220),self.paper('fits',500,600)])
        self.assertFalse(p['candidates'][0]['passed']);self.assertEqual(p['selected'],'fits')
    def test_titleblock_keepout_cannot_be_ignored(self):
        p=self.paper('blocked',500,600);p['keepouts']=[copy.deepcopy(p['usableBounds'])]
        with self.assertRaises(ValueError):self.select([p])
    def test_paper_translation_moves_frames_and_preserves_geometry(self):
        source,page,policy,report,choice=self.select([self.paper('fits',500,600)])
        self.assertTrue(report['passed']);self.assertFalse(page['paperless'])
        self.assertTrue(all(f['rect']['minX']>=20 and f['rect']['minY']>=100 for f in page['frames']))
        self.assertEqual(len(page['parts']),2)
    def test_unmeasured_geometry_and_invalid_bounds_are_rejected(self):
        for field,value in [('source',''),('usableBounds',dict(minX=0,minY=0,maxX=10000,maxY=400))]:
            p=self.paper('bad',500,600);p[field]=value
            with self.assertRaises(ValueError):self.select([p])
    def test_native_rounding_is_snapped_without_moving_measured_bounds(self):
        paper=self.paper('rounding',500,600);paper['usableBounds']['minY']=100.00000000000009
        _,page,_,report,_=self.select([paper])
        self.assertTrue(report['passed'])
        self.assertEqual(page['paper']['usableBounds'],paper['usableBounds'])
        self.assertTrue(all(p['x']%5==0 and p['y']%5==0 for p in page['parts']))
    def test_complete_layout_is_centered_clear_of_titleblock(self):
        from layout_engine.geometry import box,unionbox
        paper=self.paper('fits',500,600);_,page,_,_,_=self.select([paper])
        used=unionbox([box(f['rect']) for f in page['frames']]);usable=box(paper['usableBounds'])
        self.assertLessEqual(abs((used[0]+used[2]-usable[0]-usable[2])/2),2.5)
        self.assertLessEqual(abs((used[1]+used[3]-usable[1]-usable[3])/2),2.5)
    def test_measured_title_font_is_preserved_and_mismatch_rejected(self):
        from layout_engine.pipeline import packed_page
        metrics=copy.deepcopy(self.metrics)
        m=metrics['Controller'];m.update(fontSize=20,width=m['width']*20/12,height=m['height']*20/12)
        _,page,_,report=packed_page(self.modules,dict(titleFontSize=20),metrics)
        self.assertTrue(report['passed']);self.assertEqual(page['annotations'][0]['fontSize'],20)
        with tempfile.TemporaryDirectory() as d:
            _,page,_,report,_=select_paper(self.modules,dict(titleFontSize=20,papers=[self.paper('fits',700,700)]),metrics,Path(d)/'selection.json')
            self.assertTrue(report['passed']);self.assertEqual(page['annotations'][0]['fontSize'],20)
        with self.assertRaises(ValueError):packed_page(self.modules,dict(titleFontSize=12),metrics)
if __name__=='__main__':unittest.main()
