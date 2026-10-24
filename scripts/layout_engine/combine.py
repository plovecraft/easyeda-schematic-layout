"""Namespace logical IDs across pages without changing native instance identity."""
import copy
from lxml import etree
from .model import load_json,save_json
from .pipeline import check_model


def combine(models,measurements,out):
    if len(models)!=len(measurements):
        raise ValueError('Each source model needs its own matching measurement file')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Choose a new, empty combined output directory')
    result=dict(schemaVersion=1,units='raw; Y-up; grid 5',parts=[],wires=[],provenance=[],liveApplied=False)
    measured=dict(textMetrics={},nativeLabelMetrics={},annotationMetrics={})
    for i,(model_path,measurement_path) in enumerate(zip(models,measurements)):
        page=load_json(model_path);check_model(page)
        result['provenance'].append(copy.deepcopy(page.get('provenance',{})))
        prefix='page'+str(i+1)+'__'
        for p in page['parts']:
            part=copy.deepcopy(p);part['id']=prefix+part['id'];part['sourceDocument']='source'+str(i+1)
            group=etree.fromstring(part['svg'].encode())
            mapping={e.get('id'):prefix+e.get('id') for e in group.iter() if e.get('id')}
            for e in group.iter():
                for key,value in list(e.attrib.items()):
                    if key=='id':e.set(key,mapping[value])
                    else:
                        for old,new in mapping.items():value=value.replace('url(#'+old+')','url(#'+new+')')
                        if value.startswith('#') and value[1:] in mapping:value='#'+mapping[value[1:]]
                        e.set(key,value)
            part['svg']=etree.tostring(group,encoding='unicode')
            for text in part['labels']+part['fixedTexts']:text['id']=mapping[text['id']]
            result['parts'].append(part)
        metrics=load_json(measurement_path)
        for field in measured:
            for value,record in metrics.get(field,{}).items():
                if value in measured[field] and any(abs(record[k]-measured[field][value][k])>.03 for k in record):
                    raise ValueError('Inconsistent font metrics across inputs: '+value)
                measured[field][value]=record
    check_model(result)
    out.mkdir(parents=True,exist_ok=True)
    save_json(out/'source.json',result);save_json(out/'measurements.json',measured)
