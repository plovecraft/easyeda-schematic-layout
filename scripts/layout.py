#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 plovecraft
# SPDX-License-Identifier: AGPL-3.0-only
"""Offline skill CLI. Live EDA mutations belong to the separate EDA connector."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def browser(mode, source, output, extras=None):
    node=shutil.which('node')
    if not node:
        raise ValueError('Node.js was not found; install Node.js or set PATH')
    args=[node,str(HERE/'browser_svg.cjs'),mode,str(source),str(output)]
    if extras: args.append(str(extras))
    subprocess.run(args,check=True,timeout=180)


def main():
    if not __debug__:
        raise ValueError('Python -O disables assertion-based verification; use normal Python')
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Check local dependencies; never connect to EDA')
    p=sub.add_parser('demo',help='Generate and lay out a synthetic three-page example')
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--compare-placements',action='store_true',help='Compare supplied synthetic horizontal and vertical placements')
    for command in ('measure','render','check-preview'):
        p=sub.add_parser(command)
        p.add_argument('--input',required=True,type=Path)
        p.add_argument('--out',required=True,type=Path)
        if command=='measure': p.add_argument('--texts',type=Path,help='JSON array of extra net names')
    p=sub.add_parser('import',help='Convert native JSON + SVG + measured boxes to immutable model')
    p.add_argument('--snapshot',required=True,type=Path)
    p.add_argument('--svg',required=True,type=Path)
    p.add_argument('--measurements',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p=sub.add_parser('combine',help='Combine imported pages; namespace only model/SVG IDs')
    p.add_argument('--models',nargs='+',required=True,type=Path)
    p.add_argument('--measurements',nargs='+',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p=sub.add_parser('calibrate-ground',help='Derive ground-label envelope from multiple real native labels')
    p.add_argument('--snapshot',required=True,type=Path)
    p.add_argument('--measurements',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p=sub.add_parser('build',help='Functional grammar, label search, page packing, checks and preview')
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    for command in ('validate','conform','verify-native'):
        p=sub.add_parser(command)
        p.add_argument('--candidate',required=True,type=Path)
        p.add_argument('--policy',required=True,type=Path)
        p.add_argument('--out',required=True,type=Path)
        if command!='verify-native': p.add_argument('--source',required=True,type=Path)
        else:
            p.add_argument('--snapshot',required=True,type=Path)
            p.add_argument('--svg',type=Path)
            p.add_argument('--measurements',type=Path)
    args=parser.parse_args()
    if args.command=='doctor':
        report=dict(python=sys.version.split()[0],lxml=importlib.util.find_spec('lxml') is not None,
                    node=shutil.which('node'),liveEdaTouched=False)
        if report['node']:
            check=subprocess.run([report['node'],'-e',"try{const p=require(process.env.SCHEMATIC_PLAYWRIGHT_MODULE||'playwright'); console.log('playwright OK')}catch(e){console.log('playwright missing');process.exitCode=1}"],cwd=HERE,capture_output=True,text=True)
            report['browserModule']=check.stdout.strip()
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if report['lxml'] else 2
    if args.command in ('measure','render','check-preview'):
        args.out.parent.mkdir(parents=True,exist_ok=True)
        browser(args.command,args.input,args.out,getattr(args,'texts',None))
        return 0
    from layout_engine.model import load_json,save_json,import_page
    from layout_engine.pipeline import build_project,check_model
    if args.command=='demo':
        from layout_engine.demo import create
        manifest=create(args.out,browser,compare_placements=args.compare_placements)
        report=build_project(manifest,args.out/'result')
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0
    if args.command=='import':
        model=import_page(args.snapshot,args.svg,args.measurements)
        check_model(model)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        save_json(args.out,model)
        print('Imported',len(model['parts']),'parts; no EDA writes')
        return 0
    if args.command=='combine':
        from layout_engine.combine import combine
        combine(args.models,args.measurements,args.out)
        print(args.out/'source.json')
        return 0
    if args.command=='calibrate-ground':
        from layout_engine.drawing import calibrate_ground_label
        profile=calibrate_ground_label(args.snapshot,args.measurements)
        args.out.parent.mkdir(parents=True,exist_ok=True);save_json(args.out,profile)
        print('Measured ground-label profile saved; original inputs unchanged')
        return 0
    if args.command=='build':
        # Refuse old output: a failed new run must not inherit an old success report.
        if args.out.exists() and any(args.out.iterdir()):
            raise ValueError('Output directory is not empty; choose a new candidate directory')
        report=build_project(args.manifest,args.out)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0
    candidate=load_json(args.candidate);policy=load_json(args.policy)
    if args.command=='validate':
        from layout_engine.validator import validate
        report=validate(load_json(args.source),candidate,policy)
    elif args.command=='conform':
        from layout_engine.pipeline import conform
        from layout_engine.render import svg
        before=load_json(args.source)
        page,policy,changes=conform(before,candidate,policy)
        if args.out.exists() and any(args.out.iterdir()):
            raise ValueError('Choose a new, empty conform output directory')
        args.out.mkdir(parents=True,exist_ok=True)
        for name,value in [('candidate',page),('policy',policy),('changes',changes),('source',before)]:
            save_json(args.out/(name+'.json'),value)
        svg(page,args.out/'candidate.svg')
        print('Validated pin-exit changes:',len(changes))
        return 0
    else:
        from layout_engine.native_verify import verify_graph,verify_render
        raw=load_json(args.snapshot)
        raw=raw.get('response',raw)
        if raw.get('result',{}).get('wiresAvailable') is not True or raw['result'].get('pinNetsAvailable') is not True:
            raise ValueError('Native full wire/pin-net readback is required')
        graph_report,graph=verify_graph(raw,candidate,policy)
        report=dict(graph=graph_report,passed=True,status='native-graph-verified',hardwareVerified=False)
        if bool(args.svg)!=bool(args.measurements):
            raise ValueError('--svg and --measurements must be supplied together')
        if args.svg:
            # verify_render reads the immutable normalized actual snapshot.
            if 'response' in load_json(args.snapshot):
                raise ValueError('For SVG verification extract the response JSON to a separate immutable file')
            report['visual']=verify_render(args.snapshot,candidate,policy,args.svg,args.measurements,graph)
            report['passed']=report['visual']['passed']
            report['status']='native-graph-and-svg-verified' if report['passed'] else 'native-visual-rejected'
        report['nativePersistenceVerified']=False
        report['note']='Save/reload success must also be evidenced by the EDA tool log, not inferred from this file'
    args.out.parent.mkdir(parents=True,exist_ok=True)
    save_json(args.out,report)
    print(json.dumps(dict(passed=report['passed'],status=report.get('status'),report=str(args.out),
                         graph=report.get('graph'),metrics=report.get('metrics')),ensure_ascii=False,indent=2))
    return 0 if report['passed'] else 2


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (ValueError,AssertionError,KeyError,RuntimeError,subprocess.SubprocessError,ImportError,OSError) as error:
        print('ERROR: '+str(error),file=sys.stderr)
        raise SystemExit(2)
