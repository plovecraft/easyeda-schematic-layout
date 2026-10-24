# SPDX-FileCopyrightText: 2026 plovecraft
# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic placement choices: orientation follows verified geometry, not part type."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from layout_engine.model import load_json,save_json
from layout_engine.pipeline import build_project
from layout_engine.selection import select_module,expand_variants,objective_weights,score_metrics
from layout_engine.validator import validate


class PlacementChoices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo=Path(os.environ.get('SCHEMATIC_TEST_DEMO',str(ROOT/'layout-demo'))).resolve()
        cls.source=load_json(cls.demo/'source.json');cls.measure=load_json(cls.demo/'measurements.json')
        cls.spec=load_json(cls.demo/'layout.json')['modules'][0]

    def horizontal(self,x=-80):
        return dict(id='flat',positions={'C1':[x,90]},rotations={'C1':270},
            wires=[dict(net='3V3',points=[['U1','3'],[0,90],['C1','1']])],
            markers=[dict(id='supply1',kind='label',net='3V3',point=[-40,90])])

    def select(self,spec):
        with tempfile.TemporaryDirectory() as temp:
            return select_module(self.source,spec,self.measure,Path(temp))

    def test_compact_horizontal_placement_can_win(self):
        spec=copy.deepcopy(self.spec);spec['positions']['C1']=[-320,85]
        spec['wires'][0]['points'][2]=[-320,110];spec['variants']=[self.horizontal()]
        source,page,policy,report,choice=self.select(spec)
        self.assertEqual(choice['selected'],'flat');self.assertTrue(report['passed'])
        self.assertTrue(validate(source,page,policy)['passed'])
        self.assertEqual(next(p['rotation'] for p in page['parts'] if p['ref']=='C1'),270)

    def test_compact_vertical_placement_can_win(self):
        spec=copy.deepcopy(self.spec);spec['variants']=[self.horizontal(-350)]
        _,page,_,report,choice=self.select(spec)
        self.assertEqual(choice['selected'],'base');self.assertTrue(report['passed'])
        self.assertEqual(next(p['rotation'] for p in page['parts'] if p['ref']=='C1'),0)
        self.assertTrue(all(r['passed'] for r in choice['candidates']))

    def test_invalid_small_overlap_cannot_beat_valid_placement(self):
        spec=copy.deepcopy(self.spec);spec['variants']=[dict(id='tiny',positions={'C1':[0,0]})]
        *_,choice=self.select(spec)
        self.assertEqual(choice['selected'],'base')
        self.assertFalse(choice['candidates'][1]['passed']);self.assertTrue(choice['candidates'][1]['errors'])

    def test_fewer_bends_and_shorter_routes_win_legal_comparison(self):
        spec=copy.deepcopy(self.spec)
        spec['wires'][0]['points']=[['U1','3'],[0,80],[-60,80],[-60,145],[-150,145],[-150,110],[-110,110],['C1','1']]
        spec['markers'][0]['point']=[-100,145]
        spec['variants']=[dict(id='direct',wires=copy.deepcopy(self.spec['wires']),markers=copy.deepcopy(self.spec['markers']))]
        *_,choice=self.select(spec);self.assertEqual(choice['selected'],'direct')
        a,b=choice['candidates'];self.assertTrue(a['passed'] and b['passed'])
        self.assertLess(b['metrics']['bends'],a['metrics']['bends'])
        self.assertLess(b['metrics']['wireLength'],a['metrics']['wireLength'])

    def test_missing_required_direct_connection_stays_rejected(self):
        spec=copy.deepcopy(self.spec);spec['variants']=[dict(id='no-direct',wires=[])]
        *_,choice=self.select(spec)
        self.assertFalse(choice['candidates'][1]['passed']);self.assertEqual(choice['selected'],'base')

    def test_source_spec_and_measurements_remain_immutable(self):
        spec=copy.deepcopy(self.spec);spec['variants']=[self.horizontal()]
        original=copy.deepcopy((self.source,spec,self.measure));self.select(spec)
        self.assertEqual(original,(self.source,spec,self.measure))

    def test_equal_geometry_chooses_base_deterministically(self):
        spec=dict(copy.deepcopy(self.spec),variants=[dict(id='same')])
        first=self.select(spec);second=self.select(spec)
        self.assertEqual(first,second);self.assertEqual(first[-1]['selected'],'base')

    def test_variants_cannot_change_electrical_policy(self):
        for field in ('scopes','requiredPhysicalPairs','nativePinTextAllowances','core','page'):
            spec=dict(copy.deepcopy(self.spec),variants=[dict(id='unsafe',**{field:{}})])
            with self.assertRaises(ValueError):expand_variants(spec)

    def test_unknown_references_and_nonfinite_anchors_are_rejected(self):
        for values in ({'UNKNOWN':[0,0]},{'C1':[float('nan'),0]},{'C1':[0]},{'C1':[True,0]}):
            spec=dict(copy.deepcopy(self.spec),variants=[dict(id='bad',positions=values)])
            with self.assertRaises(ValueError):expand_variants(spec)

    def test_variant_ids_and_uncalibrated_angles_are_rejected(self):
        for rows in ([dict(id='../escape')],[dict(id='base')],[dict(id='same'),dict(id='same')],[dict(id='bad-angle',rotations={'C1':45})]):
            with self.assertRaises(ValueError):expand_variants(dict(self.spec,variants=rows))

    def test_objective_cannot_use_negative_nonfinite_or_unknown_weights(self):
        for weights in ({'area':0},{'bends':-1},{'wireLength':float('inf')},{'area':True},{'partType':1}):
            with self.assertRaises(ValueError):objective_weights(weights)
        with self.assertRaises(ValueError):score_metrics(dict(area=10,bends=0,wireLength=0,crossings=0),objective_weights({'area':1e308}))

    def test_all_failed_attempts_leave_explicit_failure_report(self):
        spec=copy.deepcopy(self.spec);spec['positions']['C1']=[0,0];spec['variants']=[dict(id='same-invalid')]
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            with self.assertRaises(ValueError):select_module(self.source,spec,self.measure,folder)
            result=load_json(folder/'selection.json');self.assertFalse(result['passed'])
            self.assertNotIn('selected',result);self.assertEqual(len(result['candidates']),2)

    def test_project_build_saves_candidate_reports_and_retains_pin_count(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);manifest=load_json(self.demo/'layout.json')
            manifest['source']=str(self.demo/'source.json');manifest['measurements']=str(self.demo/'measurements.json')
            manifest['modules'][0]['variants']=[self.horizontal(-350)]
            save_json(temp/'layout.json',manifest);report=build_project(temp/'layout.json',temp/'out')
            self.assertEqual(report['moduleSelections'][0]['selected'],'base')
            self.assertTrue((temp/'out/modules/module1/variants/flat/report.json').is_file())
            pins=sum(len(p['pins']) for n in ('1','2','3') for p in load_json(temp/'out/pages'/n/'candidate.json')['parts'])
            self.assertEqual(pins,21)


if __name__=='__main__':unittest.main(verbosity=2)
