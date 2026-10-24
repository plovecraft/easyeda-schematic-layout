# SPDX-FileCopyrightText: 2026 plovecraft
# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded, validated template alternatives; no component-type orientation bias."""
import copy
import math

from .model import save_json
from .labels import NoLayout

DEFAULT_WEIGHTS=dict(area=1.0,bends=400.0,wireLength=2.0,crossings=5000.0)
EDITABLE={'positions','rotations','wires','stubs','markers','captionOptions'}


def objective_weights(values=None):
    values={} if values is None else values
    if not isinstance(values,dict) or set(values)-set(DEFAULT_WEIGHTS):
        raise ValueError('Unknown placement objective field')
    weights=dict(DEFAULT_WEIGHTS,**values)
    if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 for v in weights.values()) or weights['area']<=0:
        raise ValueError('Placement weights must be finite and nonnegative, with positive area weight')
    return weights


def score_metrics(metrics,weights):
    values={k:metrics[k] for k in weights}
    if any(not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 for v in values.values()):
        raise ValueError('Invalid candidate metrics')
    score=sum(weights[k]*values[k] for k in weights)
    if not math.isfinite(score):raise ValueError('Placement objective overflow')
    return score


def expand_variants(spec):
    from .pipeline import safe_name
    rows=spec.get('variants',[])
    if not isinstance(rows,list) or len(rows)>63:
        raise ValueError('variants must be a list of at most 63 alternatives plus the base')
    base={k:copy.deepcopy(v) for k,v in spec.items() if k not in ('variants','objective')}
    expanded=[('base',base)];seen={'base'};refs=set(base['positions'])
    for row in rows:
        if not isinstance(row,dict) or set(row)-({'id'}|EDITABLE) or 'id' not in row:
            raise ValueError('Variant may only override geometry, captions, and explicit routes')
        name=safe_name(row['id'])
        if name in seen:raise ValueError('Duplicate or reserved variant id: '+name)
        seen.add(name);candidate=copy.deepcopy(base)
        for key,value in row.items():
            if key=='id':continue
            if key in ('positions','rotations'):
                if not isinstance(value,dict) or set(value)-refs:
                    raise ValueError('Variant must retain the exact module reference set')
                candidate[key]=dict(candidate.get(key,{}),**copy.deepcopy(value))
                if key=='positions' and any(not isinstance(v,(list,tuple)) or len(v)!=2 or any(isinstance(q,bool) or not isinstance(q,(int,float)) or not math.isfinite(q) for q in v) for v in value.values()):
                    raise ValueError('Variant positions must be finite two-dimensional anchors')
                if key=='rotations' and any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v%90 for v in value.values()):
                    raise ValueError('Variant rotations must use calibrated quarter turns')
            elif key=='captionOptions':
                if not isinstance(value,dict):raise ValueError('captionOptions must be an object')
                candidate[key]=dict(candidate.get(key,{}),**copy.deepcopy(value))
            else:
                if not isinstance(value,list):raise ValueError('Variant drawing lists replace the complete original list')
                candidate[key]=copy.deepcopy(value)
        expanded.append((name,candidate))
    return expanded


def select_module(source,spec,measurements,folder):
    from .pipeline import build_module,save_case
    weights=objective_weights(spec.get('objective'));expanded=expand_variants(spec)
    attempts=[];accepted=[]
    for index,(name,variant) in enumerate(expanded):
        target=folder/'variants'/name;target.mkdir(parents=True,exist_ok=True)
        try:
            result=build_module(source,variant,measurements)
            before,page,policy,report=result
            save_case(target,before,page,policy,report)
            row=dict(id=name,passed=report['passed'],metrics=report['metrics'],errors=report['errors'])
            if report['passed']:
                score=score_metrics(report['metrics'],weights);row['score']=score
                rank=(score,report['metrics']['area'],report['metrics']['bends'],report['metrics']['wireLength'],index)
                accepted.append((rank,result,name))
        except (ValueError,AssertionError,NoLayout) as error:
            row=dict(id=name,passed=False,errors=[dict(type=type(error).__name__,message=str(error))])
            save_json(target/'report.json',row)
        attempts.append(row)
    report=dict(passed=bool(accepted),weights=weights,candidates=attempts,
                formula='area*areaWeight + bends*bendWeight + wireLength*lengthWeight + crossings*crossingWeight',
                scope='minimum score among supplied fully validated module alternatives; no global-optimum claim',
                orientationPreference='none')
    if not accepted:
        save_json(folder/'selection.json',report)
        raise ValueError('All placement alternatives rejected for '+spec['name']+'; see selection.json')
    rank,result,name=min(accepted,key=lambda r:r[0]);report.update(selected=name,score=rank[0])
    save_json(folder/'selection.json',report)
    return (*result,report)
