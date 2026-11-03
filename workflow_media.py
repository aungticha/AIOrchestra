"""Structured media evidence, paths and approval fingerprints."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

FIELDS = {
    'summary':{'type':'string'}, 'details':{'type':'string'},
    'passed':{'type':'boolean','description':'The current assigned stage is complete; this does not mean the entire workflow is ready for user acceptance.'}, 'blocked':{'type':'boolean','description':'A real missing prerequisite prevents this stage, not a deliverable owned by a later agent.'},
    'findings':{'type':'array','items':{'type':'string'}},
    'tests':{'type':'array','items':{'type':'string'}},
    'references':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{'url':{'type':'string'},'title':{'type':'string'},'evidence':{'type':'string'},'inspected':{'type':'boolean'}},'required':['url','title','evidence','inspected']}},
    'storyboard':{'type':'string'},
    'artifacts':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{'path':{'type':'string'},'kind':{'type':'string','enum':['plan','asset','preview','final','report']}},'required':['path','kind']}},
}
SCHEMA = {'type':'object','additionalProperties':False,'properties':{**FIELDS,'replan_required':{'type':'boolean'}},'required':[*FIELDS,'replan_required']}

def validate(value):
    if not isinstance(value,dict) or set(value) not in (set(FIELDS),set(FIELDS)|{'replan_required'}):
        raise ValueError('Invalid workflow result schema')
    if 'replan_required' in value and type(value['replan_required']) is not bool:raise ValueError('Invalid replan_required')
    for key in ('summary','details','storyboard'):
        if not isinstance(value[key],str) or len(value[key])>60000:
            raise ValueError('Invalid result '+key)
    if not value['summary'].strip() or any(type(value[key]) is not bool for key in ('passed','blocked')):
        raise ValueError('Invalid result status')
    for key in ('findings','tests'):
        if not isinstance(value[key],list) or len(value[key])>100 or any(not isinstance(s,str) or len(s)>4000 for s in value[key]):
            raise ValueError('Invalid result '+key)
    if not isinstance(value['references'],list) or len(value['references'])>10:
        raise ValueError('Invalid references')
    for ref in value['references']:
        if not isinstance(ref,dict) or set(ref)!={'url','title','evidence','inspected'} or type(ref['inspected']) is not bool:
            raise ValueError('Invalid reference evidence')
        if any(not isinstance(ref[k],str) or len(ref[k])>4000 for k in ('url','title','evidence')):
            raise ValueError('Invalid reference text')
        url=urlsplit(ref['url'])
        if url.scheme not in ('http','https','file') or url.username or url.password:
            raise ValueError('Invalid reference URL')
    if not isinstance(value['artifacts'],list) or len(value['artifacts'])>100:
        raise ValueError('Invalid artifacts')
    for item in value['artifacts']:
        if not isinstance(item,dict) or set(item)!={'path','kind'} or item['kind'] not in ('plan','asset','preview','final','report') or not isinstance(item['path'],str):
            raise ValueError('Invalid artifact')
    return value

def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

def artifacts(root, values, hash_content=True):
    result={}
    root=Path(root).resolve()
    for item in values:
        path=Path(item['path'])
        path=path if path.is_absolute() else root/path
        if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path,*path.parents] if p.is_relative_to(root)):
            raise ValueError('Artifact ต้องอยู่ใน output folder ของงานและไม่เป็น symlink')
        if not path.is_file() or path.name.startswith('.env') or 'secrets' in path.parts:
            raise ValueError('Artifact ไม่พบหรือเป็นไฟล์ข้อมูลลับ')
        result[str(path.resolve())]={'kind':item['kind'],'sha256':file_hash(path) if hash_content else None}
    return result

def evidence(record):
    files={}
    if record.get('artifacts'):
        files=artifacts(record['output_root'],[{'path':path,'kind':item['kind']} for path,item in record['artifacts'].items()])
    value={'outputs':record['outputs'],'files':files,'graph':record['graph'],'references':record.get('references',[]),'selected_reference':record.get('selected_reference','')}
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
