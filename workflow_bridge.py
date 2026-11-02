"""Local, JSON-only bridge from Codex/Claude chats to the workflow controller."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid
import sys
from http.client import HTTPException
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit,quote
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler

ROOT=Path(__file__).resolve().parent

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*_args,**_kwargs):return None

class Bridge:
    def __init__(self,workspace=None,server=None):
        self.workspace=Path(workspace or ROOT/'workspace').resolve();self.expected_instance=None
        discovery=self.workspace/'runtime'/'server.json'
        if server is None and discovery.is_file():
            info=json.loads(discovery.read_text(encoding='utf-8'));server=info['url'];self.expected_instance=info.get('instance')
        self.url=self.local_url(server or 'http://127.0.0.1:4310')
        self.opener=build_opener(ProxyHandler({}),NoRedirect())
    @staticmethod
    def local_url(raw):
        if not isinstance(raw,str):raise ValueError('Invalid server URL')
        value=urlsplit(raw)
        if value.scheme!='http' or value.hostname not in ('127.0.0.1','localhost') or value.username or value.password or value.path not in ('','/') or value.query or value.fragment:raise ValueError('Bridge connects only to a loopback AIOrchestra server')
        port=value.port or 80
        if not 1<=port<=65535:raise ValueError('Invalid server port')
        return 'http://127.0.0.1:'+str(port)
    def request(self,path,payload=None):
        body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
        request=Request(self.url+path,data=body,headers={'Content-Type':'application/json','Origin':self.url})
        try:
            with self.opener.open(request,timeout=8) as response:
                raw=response.read(8_000_001)
                if len(raw)>8_000_000:raise ValueError('Workflow response exceeds bridge size limit')
                value=json.loads(raw)
                if not isinstance(value,dict):raise ValueError('Server returned an invalid bridge response')
                return value
        except HTTPError as error:
            try:message=json.loads(error.read(10000)).get('error','HTTP '+str(error.code))
            except (ValueError,AttributeError):message='HTTP '+str(error.code)
            raise ValueError(message) from None
        except (URLError,TimeoutError,HTTPException):raise ValueError('AIOrchestra server ไม่พร้อม: เปิดหรือรีสตาร์ต server.py แล้วลองอีกครั้ง; อย่าอ้างว่าเริ่มงานสำเร็จ') from None
    def health(self):
        info=self.request('/api/health')
        if info.get('app')!='AIOrchestra' or Path(info.get('workspace','')).resolve()!=self.workspace:raise ValueError('Server ไม่ใช่ AIOrchestra workspace ที่ตั้งค่าไว้')
        if self.expected_instance and info.get('instance')!=self.expected_instance:raise ValueError('Server discovery หมดอายุ กรุณารีสตาร์ต server')
        return info
    def view(self,run):
        output={key:run.get(key) for key in ('id','state','label','revision','task','team','project','branch','push','remote','error','round','commit','pushed','worktrees')}
        output['dashboard']=self.url;output['outputs']=run.get('outputs',{})
        output['steps']=[{key:step.get(key) for key in ('role','state','engine','error')} for step in run.get('steps',[])]
        gate={'awaiting_plan':1,'awaiting_delivery':2}.get(run['state'])
        if gate:
            output['approval']={'id':run['id'],'revision':run['revision'],'gate':gate,'user_confirmed':False}
            output['instruction']='แสดงแผน/แบบหรือผล Review/QA และเป้าหมาย Git ให้ผู้ใช้ตรวจ แล้วรอคำอนุมัติจริงสำหรับขั้นนี้'
            if gate==2:output['diff']=run.get('diff','');output['verified_digest']=run.get('verified_digest')
        return output
    def get(self,identifier):
        if not isinstance(identifier,str) or not identifier:raise ValueError('ระบุ workflow id')
        return self.request('/api/workflows/run?id='+quote(identifier,safe=''))
    def run(self,payload):
        if not isinstance(payload,dict):raise ValueError('Request must be a JSON object')
        action=payload.get('action','status');self.health()
        if action=='health':return {'ok':True,'server':self.url,'workspace':str(self.workspace)}
        if action=='options':return self.request('/api/workflows/options')
        if action=='list':return self.request('/api/workflows')
        if action in ('status','wait'):
            record=self.get(payload.get('id'));seconds=payload.get('wait_seconds',20 if action=='wait' else 0)
            if type(seconds)!=int or not 0<=seconds<=30:raise ValueError('wait_seconds must be 0–30')
            until=time.monotonic()+seconds;revision=record['revision']
            while seconds and record['state'] not in ('awaiting_plan','awaiting_delivery','failed','interrupted','completed','cancelled') and time.monotonic()<until:
                time.sleep(min(1,max(0,until-time.monotonic())));record=self.get(record['id'])
                if record['revision']!=revision:break
            return self.view(record)
        if os.environ.get('AIORCHESTRA_WORKFLOW_WORKER')=='1':raise ValueError('Workflow workers cannot create or approve other workflows')
        if action=='start':return self.start(payload)
        if action not in ('approve','revise','retry','cancel','recheck'):raise ValueError('Unknown bridge action')
        record=self.get(payload.get('id'));revision=payload.get('revision')
        if type(revision)!=int or revision!=record['revision']:raise ValueError('Revision เปลี่ยนแล้ว อ่าน status และตรวจผลล่าสุดก่อนส่งคำสั่ง')
        if action=='approve':
            gate={'awaiting_plan':1,'awaiting_delivery':2}.get(record['state'])
            if type(payload.get('gate'))!=int or payload['gate']!=gate or payload.get('user_confirmed') is not True:raise ValueError('ต้องมีคำอนุมัติจริง: ส่ง gate, revision ล่าสุด และ user_confirmed=true')
        value={'id':record['id'],'revision':revision,'action':action,'feedback':payload.get('feedback','')}
        return self.view(self.request('/api/workflows/action',value))
    def start(self,payload):
        options=self.request('/api/workflows/options');teams=options['teams'];team=payload.get('team')
        if not team:
            matches=[item for item in teams if item['id']=='developer']
            if not matches and len(teams)==1:matches=teams
            if len(matches)!=1:raise ValueError('มีหลายทีม กรุณาระบุ team จาก options')
            team=matches[0]['id']
        selected=next((item for item in teams if item['id']==team),None)
        if selected is None:raise ValueError('ไม่พบทีม')
        installed=[item['id'] for item in options['engines'] if item['installed']]
        engine=payload.get('engine')
        if not engine:
            pairs=[options['families'].get(key) for key in selected['recommendedModels']]
            engine=next((pair[0] for pair in pairs if pair and pair[0] in installed),None) or next(iter(installed),None)
        if not engine:raise ValueError('ไม่พบ Codex/Claude CLI ในเครื่อง server')
        request={key:payload[key] for key in ('project','task','roles','ui','push','remote','request_id') if key in payload}
        request.update(team=team,engine=engine)
        request.setdefault('request_id',uuid.uuid4().hex)
        value=self.view(self.request('/api/workflows/create',request));value['request_id']=request['request_id'];return value

def main(argv=None):
    if hasattr(sys.stdin,'reconfigure'):sys.stdin.reconfigure(encoding='utf-8')
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace');parser.add_argument('--server')
    parser.add_argument('--request-file',help='Read UTF-8 JSON from a file instead of stdin')
    args=parser.parse_args(argv)
    try:
        raw=Path(args.request_file).read_text(encoding='utf-8') if args.request_file else sys.stdin.read(100001)
        if len(raw)>100000:raise ValueError('Bridge request too large')
        value=Bridge(args.workspace,args.server).run(json.loads(raw));print(json.dumps(value,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
