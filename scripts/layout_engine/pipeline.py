"""Portable manifest adapter for the retained template/geometry algorithms."""
import copy
import math
from pathlib import Path

from .drawing import NativeDrawing, base_policy, fit_native_grounds
from .geometry import asbox, box, shift, point
from .model import load_json, save_json
from .net_labels import adapt
from .packing import bounds, merged, merge_policy, pack, translated
from .pin_exit import bad_pin_exits, shifted_bus
from .render import svg
from .validator import validate


def check_model(page):
    if page.get('schemaVersion') != 1 or not page.get('parts'):
        raise ValueError('Expected a nonempty schemaVersion=1 measured page model')
    for key in ('id', 'ref'):
        values = [p[key] for p in page['parts']]
        if len(values) != len(set(values)):
            raise ValueError('Duplicate component '+key)
    for p in page['parts']:
        if p.get('mirror') is not False:
            raise ValueError('Mirrored glyphs need a calibrated adapter; unsupported: '+p['ref'])
        if len({q['pinNumber'] for q in p['pins']}) != len(p['pins']):
            raise ValueError('Duplicate pin numbers: '+p['ref'])
        for q in p['pins']:
            if q.get('netAmbiguous') or not isinstance(q.get('noConnected'), bool):
                raise ValueError('Unknown pin/NC contract: '+p['ref'])
            if not q['noConnected'] and not q.get('net'):
                raise ValueError('A non-NC pin has no intended net: '+p['ref'])
            if q['rotation'] % 90:
                raise ValueError('Only quarter-turn pin directions are supported')


def endpoint(value, drawing):
    if isinstance(value, list) and len(value) == 2:
        if isinstance(value[0], str):
            return drawing.xy(value[0], str(value[1]))
        return point(value)
    if isinstance(value, dict) and set(value) <= {'pin', 'offset'} and 'pin' in value:
        x, y = drawing.xy(*value['pin'])
        dx, dy = value.get('offset', [0, 0])
        return point((x+dx, y+dy))
    raise ValueError('Endpoint must be [x,y], [ref,pin], or {pin:[ref,pin],offset:[dx,dy]}')


def build_module(source, spec, measurements):
    refs = set(spec['positions'])
    subset = copy.deepcopy(source)
    subset['parts'] = [p for p in source['parts'] if p['ref'] in refs]
    if {p['ref'] for p in subset['parts']} != refs:
        raise ValueError('Unknown reference in module '+spec['name'])
    subset['wires'] = []
    scopes = dict(spec.get('scopes', {}))
    for scope in scopes.values():
        if scope not in ('page', 'global'):
            raise ValueError('scope must be page or global')
    drawing = NativeDrawing(subset, measurements['textMetrics'], spec['positions'],
                            spec.get('rotations', {}), spec.get('core'), scopes)
    drawing.page['coreRef'] = spec.get('core')
    for row in spec.get('wires', []):
        drawing.wire(row['net'], *(endpoint(v, drawing) for v in row['points']))
    for row in spec.get('stubs', []):
        drawing.stub(row['ref'], str(row['pin']), row.get('length', 65),
                     row.get('align'), row.get('id'))
    for row in spec.get('markers', []):
        anchor = endpoint(row['point'], drawing)
        if row['kind'] == 'ground':
            if row.get('net', 'GND') != 'GND':
                raise ValueError('Native ground glyph is calibrated only for net GND')
            drawing.ground(row['id'], anchor, row.get('rotation', 0))
        elif row['kind'] == 'label':
            drawing.label(row['id'], row['net'], anchor, row.get('align', 'start'))
        else:
            raise ValueError('Unknown marker kind')
    page = drawing.finish(dict(_flex=True, **spec.get('captionOptions', {})))
    fit_native_grounds(page, measurements['textMetrics'])
    policy = base_policy(subset, scopes, spec.get('requiredPhysicalPairs', []))
    policy.update(rotationConvention='native-positive', enforcePinExitDirection=True)
    # Numerical/native pin-caption exceptions are explicit inputs, never created
    # automatically to make an unknown library symbol pass.
    for field in ('nativePinTextAllowances', 'nativeTextBoundaryAllowances'):
        policy[field] = copy.deepcopy(spec.get(field, []))
    page['rotationConvention'] = 'native-positive'
    page, policy = adapt(page, policy, measurements['nativeLabelMetrics'])
    for marker in page['markers']:
        marker['id']=spec['name']+'__'+marker['id']
        if 'label' in marker:marker['label']['id']=spec['name']+'__'+marker['label']['id']
    report = validate(subset, page, policy)
    return subset, page, policy, report


def combine_policy(policies):
    result = merge_policy(policies)
    result['enforcePinExitDirection'] = all(p.get('enforcePinExitDirection') for p in policies)
    result['nativeTextBoundaryAllowances'] = []
    seen = {}
    for policy in policies:
        result['nativeTextBoundaryAllowances'] += policy.get('nativeTextBoundaryAllowances', [])
        for net, scope in policy['namedIslandScopes'].items():
            if net in seen and seen[net] != scope:
                raise ValueError('Conflicting scopes for '+net)
            seen[net] = scope
    return result


def packed_page(modules, config, annotation_metrics=None):
    annotation_metrics=annotation_metrics or {}
    sizes, local = {}, {}
    for name, module in modules.items():
        b = bounds(module['candidate'])
        local[name] = (math.floor(b[0]/5)*5, math.floor(b[1]/5)*5,
                       math.ceil(b[2]/5)*5, math.ceil(b[3]/5)*5)
        r = local[name]
        title=module['title']
        if title not in annotation_metrics:
            raise ValueError('Missing measured module title; measure {text: title, fontSize: 12}: '+title)
        sizes[name] = (max(r[2]-r[0]+40,math.ceil((annotation_metrics[title]['width']+40)/5)*5), r[3]-r[1]+60)
    order = list(modules)
    orders = [order, sorted(order, key=lambda n: -sizes[n][1]),
              sorted(order, key=lambda n: -sizes[n][0]*sizes[n][1])]
    default = max(600, max(w for w, h in sizes.values()))
    choices = []
    for width in config.get('widths', [default, default+150, default+300]):
        for sequence in orders:
            placement = pack(sizes, width, config.get('maxHeight', 3000), sequence)
            if placement:
                used_w = max(x+w for x, y, w, h in placement.values())
                used_h = max(y+h for x, y, w, h in placement.values())
                score = used_w*used_h + abs(used_w-used_h)*config.get('aspectPenalty', 50)
                choices.append((score, used_h, used_w, placement))
    if not choices:
        raise ValueError('No module packing fits the supplied widths and maxHeight')
    _, height, width, placement = min(choices, key=lambda v: v[:3])
    items, frames, annotations = [], [], []
    for name in order:
        x, y, w, h = placement[name]
        b = local[name]
        moved = translated(modules[name]['candidate'], x+20-b[0], height-y-40-b[3])
        items.append(moved)
        frames.append(dict(id=name, title=modules[name]['title'],
            rect=asbox((x+5, height-y-h+5, x+w-15, height-y-5)), color='#AA00AA'))
        title=modules[name]['title'];metric=annotation_metrics[title]
        if metric['fontSize']!=12:
            raise ValueError('Frame titles must be measured at fontSize 12')
        annotations.append(dict(id='frame-title-'+name,text=title,fontSize=12,
            bearingX=metric['bearingX'],bearingY=metric['bearingY'],
            bbox=asbox((x+15,height-y-12-metric['height'],x+15+metric['width'],height-y-12))))
    page = merged(items)
    page.update(frames=frames, annotations=annotations, paperless=True, liveApplied=False,
                packing=dict(width=width,height=height,algorithm='best-short-side free rectangles'))
    source = merged([m['source'] for m in modules.values()])
    policy = combine_policy([m['policy'] for m in modules.values()])
    return source, page, policy, validate(source, page, policy)


def build_project(manifest_path, output):
    manifest_path = Path(manifest_path).resolve()
    manifest = load_json(manifest_path)
    base = manifest_path.parent
    source = load_json(base / manifest['source'])
    measurements = load_json(base / manifest['measurements'])
    check_model(source)
    specs = manifest['modules']
    if not specs or len({s['name'] for s in specs}) != len(specs):
        raise ValueError('Expected nonempty modules with unique names')
    assigned = [ref for s in specs for ref in s['positions']]
    if len(assigned) != len(set(assigned)) or set(assigned) != {p['ref'] for p in source['parts']}:
        raise ValueError('Every source part must belong to exactly one module')
    local_origins={}
    for spec in specs:
        for part in source['parts']:
            if part['ref'] not in spec['positions']:continue
            for pin in part['pins']:
                net=pin.get('net')
                if net and spec.get('scopes',{}).get(net,'page')=='page':
                    key=(str(spec['page']),net)
                    local_origins.setdefault(key,set()).add(part.get('sourceDocument','single-source'))
    if any(len(origins)>1 for origins in local_origins.values()):
        raise ValueError('Different source pages reuse a page-local net on one target page; resolve the electrical scope explicitly')
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    modules = {}
    for spec in specs:
        folder = out / 'modules' / safe_name(spec['name'])
        folder.mkdir(parents=True, exist_ok=True)
        before, candidate, policy, report = build_module(source, spec, measurements)
        save_case(folder, before, candidate, policy, report)
        if not report['passed']:
            raise ValueError('Rejected module '+spec['name']+'; see '+str(folder/'report.json'))
        modules[spec['name']] = dict(source=before, candidate=candidate, policy=policy,
                                    title=spec.get('title', spec['name']), page=str(spec['page']))
    page_configs = {str(p['id']): p for p in manifest['pages']}
    if len(page_configs) != len(manifest['pages']) or set(page_configs) != {m['page'] for m in modules.values()}:
        raise ValueError('Page IDs must be unique and exactly cover all used pages')
    summary = []
    for page_id, config in page_configs.items():
        selected = {n: m for n, m in modules.items() if m['page'] == page_id}
        before, candidate, policy, report = packed_page(selected, config, measurements.get('annotationMetrics'))
        folder = out/'pages'/safe_name(page_id)
        folder.mkdir(parents=True, exist_ok=True)
        candidate['pageId'] = page_id
        save_case(folder, before, candidate, policy, report)
        if not report['passed']:
            raise ValueError('Rejected page '+page_id+'; see '+str(folder/'report.json'))
        summary.append(dict(id=page_id, title=config.get('title', page_id),
                            modules=[m['title'] for m in selected.values()], **report['metrics']))
    result = dict(version='1.0.1', passed=True, status='offline-verified', pages=summary,
                  parts=len(source['parts']), liveApplied=False, hardwareVerified=False,
                  nativePersistenceVerified=False, paperless=True)
    save_json(out/'report.json', result)
    write_viewer(out, result)
    return result


def safe_name(value):
    value = str(value)
    if not value or value in ('.','..') or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in value):
        raise ValueError('Output IDs must use letters, numbers, hyphens or underscores')
    return value


def save_case(folder, source, candidate, policy, report):
    for name, value in [('source',source),('candidate',candidate),('policy',policy),('report',report)]:
        save_json(folder/(name+'.json'),value)
    svg(candidate, folder/'candidate.svg')


def write_viewer(out, report):
    import html
    import json
    pages = report['pages']
    options = ''.join('<option value="'+safe_name(p['id'])+'">'+html.escape(p['title'])+'</option>' for p in pages)
    content = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>原理图排版预览</title>
<style>body{font:15px/1.6 system-ui;margin:20px;background:#f2f5f3;color:#24382e}h1{font-size:22px}button,select{font:inherit;padding:5px 12px}#frame{height:74vh;overflow:auto;background:white;border:1px solid #bdcdc2;margin-top:12px}img{display:block;max-width:none}#modules{color:#53665a}</style>
<h1>原理图排版与校验</h1><p>离线算法候选 · 未写入 EDA · 未验证原生持久化或硬件</p>
<select id="pick">OPTIONS</select> <button id="fit">适合窗口</button> <button id="actual">原始比例</button>
<p id="modules"></p><div id="frame"><img id="drawing" alt="离线原理图候选"></div><p><a href="report.json">检查报告</a></p>
<script>const pages=PAGES,pick=document.querySelector('#pick'),img=document.querySelector('#drawing');let fit=true;
function scale(){img.style.width=(fit?Math.min(img.naturalWidth,document.querySelector('#frame').clientWidth):img.naturalWidth)+'px'}
function update(){img.src='pages/'+pick.value+'/candidate.svg';document.querySelector('#modules').textContent=pages.find(p=>p.id===pick.value).modules.join(' / ');img.onload=scale}
pick.onchange=update;document.querySelector('#fit').onclick=()=>{fit=true;scale()};document.querySelector('#actual').onclick=()=>{fit=false;scale()};update();</script></html>'''
    (out/'preview.html').write_text(content.replace('OPTIONS',options).replace('PAGES',json.dumps(pages,ensure_ascii=False).replace('<','\\u003c')),encoding='utf-8')


def conform(source, page, policy, distances=(5,10,15,20,30,40)):
    changes=[]
    for _ in range(40):
        findings=bad_pin_exits(page)
        if not findings:
            check=dict(policy,enforcePinExitDirection=True)
            report=validate(source,page,check)
            if not report['passed']:
                raise ValueError('Conformed geometry failed independent validation')
            return page,check,changes
        accepted=None
        for distance in distances:
            try:
                candidate,change=shifted_bus(page,findings[0],distance)
                check=dict(policy,enforcePinExitDirection=False)
                report=validate(source,candidate,check)
                if report['passed'] and len(bad_pin_exits(candidate))<len(findings):
                    accepted=(candidate,change)
                    break
            except (AssertionError,ValueError):
                continue
        if accepted is None:
            raise ValueError('Unsupported or obstructed pin-exit repair; revise the functional template')
        page,change=accepted
        changes.append(change)
    raise ValueError('Pin-exit repair iteration limit reached')
