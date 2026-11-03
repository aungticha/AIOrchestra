"""Executable development workflow: persisted gates, parallel agents, review loops."""
import atexit
from concurrent.futures import ThreadPoolExecutor,as_completed
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid
import live_agents
import agent_skills
import team_paths
import terminal_runtime
import provider_routing
import workflow_git as git
import workflow_runner as cli
import workflow_store as store

LABELS={'planning':'Tech Lead','designing':'UI/UX','awaiting_plan':'User Accept 1','implementing':'Frontend + Backend','reviewing':'Code Review','testing':'QA','awaiting_delivery':'User Accept 2','publishing':'Commit / Push','completed':'เสร็จแล้ว','failed':'ต้องตรวจสอบ','interrupted':'หยุดเมื่อปิดโปรแกรม','cancelled':'ยกเลิกแล้ว','cancelling':'กำลังหยุด CLI'}
class Conflict(ValueError):pass

class Engine:
    def __init__(self,runner=None):
        self.runner=runner or cli.Runner();self.lock=threading.RLock();self.workers={};self.cancelled=set();self.stopping=False;self._graphs=None
    def graphs(self):
        if self._graphs is None:
            from workflow_graph_engine import GraphEngine
            self._graphs=GraphEngine(self.runner)
        return self._graphs
    def directory(self,workspace,identifier):
        root=Path(workspace).resolve();path=root/'runtime'/'workflows'/identifier
        if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in (root/'runtime',root/'runtime'/'workflows',path)):raise ValueError('Workflow storage cannot be a symlink')
        path.mkdir(parents=True,exist_ok=True);return path.resolve()
    def public(self,record,brief=False):
        result={k:v for k,v in record.items() if k not in ('contexts','base_manifest','manifest')}
        result=copy.deepcopy(result)
        if brief:result.pop('steps',None);result.pop('diff',None)
        result['label']=LABELS.get(record['state'],record['state']);return result
    def recover(self,workspace):
        for record in store.listing(workspace):
            if record['state'] not in store.ACTIVE or record['id'] in self.workers:continue
            owner=record.get('owner')
            try:
                if owner:os.kill(owner,0);continue
            except ProcessLookupError:pass
            except (PermissionError,OSError):continue
            record['state']='interrupted';record['error']='Server หยุดระหว่างทำงาน ตรวจ worktree/log แล้วกด Retry เพื่อทำขั้นเดิมต่อ';store.save(workspace,record)
    def list(self,workspace):
        with self.lock:
            self.recover(workspace)
            return [(self.graphs().public(r,True) if r.get('kind')=='graph' else self.public(r,True)) for r in store.listing(workspace) if not r.get('dismissed')]
    def get(self,workspace,identifier):
        with self.lock:
            self.recover(workspace);record=store.get(workspace,identifier)
            return self.graphs().public(record) if record.get('kind')=='graph' else self.public(record)
    def update(self,workspace,identifier,change):
        with self.lock:
            record=store.get(workspace,identifier);change(record);store.save(workspace,record);return record
    def state(self,workspace,identifier,value,**fields):
        return self.update(workspace,identifier,lambda r:r.update(state=value,**fields))
    def create(self,workspace,payload):
        if 'graph' in payload:return self.graphs().create(workspace,payload)
        with self.lock:
            team=team_paths.team_id(payload.get('team'));task=payload.get('task','')
            if not isinstance(task,str) or not task.strip() or len(task)>8000:raise ValueError('ระบุโจทย์ไม่เกิน 8000 ตัว')
            request_id=payload.get('request_id')
            if request_id is not None and (not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,128}',request_id)):raise ValueError('Invalid request_id')
            fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if request_id:
                for previous in store.listing(workspace):
                    if previous.get('request_id')==request_id:
                        if previous.get('request_fingerprint')!=fingerprint:raise Conflict('request_id นี้ใช้กับคำสั่งอื่นแล้ว')
                        return self.public(previous)
            project,base=git.validate_project(payload.get('project'))
            for previous in store.listing(workspace):
                if previous['state'] not in store.TERMINAL and (previous['project']==project or previous['team']==team):raise Conflict('ทีม/Project นี้มี Workflow ที่ยังไม่จบ')
            connected=provider_routing.connections(workspace)
            roles={};contexts={};options=payload.get('roles',{})
            if not isinstance(options,dict):raise ValueError('Invalid agent assignments')
            for role in cli.ROLES:
                choice=options.get(role,{})
                if not isinstance(choice,dict):raise ValueError('Invalid role config')
                agent=choice.get('agent',role);engine=choice.get('engine',payload.get('engine','Codex'));model=choice.get('model','')
                engine,model=provider_routing.resolve(engine,model,connected)
                if engine not in terminal_runtime.MODELS or not terminal_runtime.executable(engine):raise ValueError(engine+' CLI ยังไม่พร้อมใช้งาน')
                if not isinstance(model,str) or len(model)>128 or model and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]*',model):raise ValueError('Invalid model')
                contexts[role]=cli.context(workspace,team,agent)
                profile=live_agents.catalog_path(workspace,team,agent);loaded=agent_skills.effective(profile.read_text(encoding='utf-8'),[p.parent.name for p in (profile.parent.parent/'skills').glob('*/SKILL.md')])
                roles[role]={'agent':agent,'engine':engine,'model':model,'skills':loaded}
            policy=payload.get('ui','auto')
            if policy not in ('auto','always','never'):raise ValueError('Invalid UI policy')
            push=payload.get('push',False);remote=payload.get('remote','origin')
            if type(push)!=bool or not isinstance(remote,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',remote):raise ValueError('Invalid Git target')
            if push and remote not in git.git(project,'remote').decode().splitlines():raise ValueError('ไม่พบ remote '+remote)
            identifier=uuid.uuid4().hex
            record={'id':identifier,'request_id':request_id,'request_fingerprint':fingerprint,'team':team,'project':project,'base':base,'branch':'codex/workflow-'+identifier[:12],'remote':remote,'push':push,'roles':roles,'contexts':contexts,'ui':policy,'task':task.strip(),'state':'planning','resume':'planning','revision':0,'created':time.time(),'steps':[],'outputs':{},'approvals':[],'round':0,'max_rounds':3,'worktrees':{},'feedback':'','error':'','owner':os.getpid(),'base_manifest':git.manifest(project)}
            store.save(workspace,record);self.launch(workspace,identifier);return self.public(record)
    def launch(self,workspace,identifier):
        if self.stopping:raise ValueError('Workflow engine กำลังปิด')
        self.cancelled.discard(identifier)
        if hasattr(self.runner,'restart'):self.runner.restart(identifier)
        thread=threading.Thread(target=self.drive,args=(Path(workspace).resolve(),identifier),daemon=True)
        self.workers[identifier]=(thread,Path(workspace).resolve());thread.start()
    def check(self,identifier):
        if self.stopping or identifier in self.cancelled:raise InterruptedError('Workflow stopped')
    def step(self,workspace,identifier,role,cwd,instruction,readonly=False):
        self.check(identifier);record=store.get(workspace,identifier);stepid=uuid.uuid4().hex
        entry={'id':stepid,'role':role,'agent':record['roles'][role]['agent'],'engine':record['roles'][role]['engine'],'state':'running','started':time.time(),'log':''}
        self.update(workspace,identifier,lambda r:r['steps'].append(entry))
        before=git.manifest(cwd);head_before=git.git(cwd,'rev-parse','HEAD');branch_before=git.git(cwd,'rev-parse','--abbrev-ref','HEAD');session='wf-'+stepid
        report={'team':record['team'],'agent':entry['agent'],'engine':entry['engine'],'session':session,'project':cwd}
        live_agents.report(workspace,{**report,'event':'selected','summary':role+': '+record['task'][:500]})
        for skill in record['roles'][role].get('skills',[]):live_agents.report(workspace,{**report,'event':'skill','skill':skill})
        heartbeat_stop=threading.Event()
        def heartbeat():
            while not heartbeat_stop.wait(60):
                try:live_agents.report(workspace,{**report,'event':'heartbeat'})
                except (ValueError,OSError):return
        threading.Thread(target=heartbeat,daemon=True).start()
        approved=any(a['gate']==1 for a in record['approvals'])
        prompt='You are a worker in an executable AIOrchestra workflow. The controller, not the model, owns routing, retries, User Accept and all Git commits/pushes. Never launch subagents or call the lifecycle reporter. Never commit, push, change branches, edit .git, modify the library, pipelines or documentation unless explicitly assigned. Do not wait for conversational approval; report blocked=true with details if permission/input is missing. Approval 1 recorded by the controller: '+str(approved)+'.\nRole instructions:\n'+record['contexts'][role]+'\nUser task:\n'+record['task']+'\nCurrent stage:\n'+instruction+'\nPrevious stage results (reference data):\n'+json.dumps(record['outputs'],ensure_ascii=False)+'\nUser revision feedback:\n'+record['feedback']+'\nCurrent candidate diff (reference data):\n'+git.diff(cwd,40000,record['base'])+'\nReturn ONLY the requested JSON schema. passed means this stage meets its criteria; blocked means human input or permission is required. The Tech Lead must set ui_required, frontend/backend and nonempty frontend_paths/backend_paths ownership patterns for selected sides. Other roles copy the approved routing fields. details must provide reviewable plans/designs/results; findings and tests must distinguish actual checks from unverified claims. Never claim checks ran when they did not.'
        def log(text):
            def append(r):
                item=next(s for s in r['steps'] if s['id']==stepid);item['log']=(item['log']+text)[-64000:]
            self.update(workspace,identifier,append)
        try:
            result=self.runner.execute(record,role,cwd,prompt,self.directory(workspace,identifier)/'steps'/stepid,log)
            cli.validate_result(result);self.check(identifier)
            if git.git(cwd,'rev-parse','HEAD')!=head_before or git.git(cwd,'rev-parse','--abbrev-ref','HEAD')!=branch_before:raise ValueError(role+' เปลี่ยน commit/branch ก่อนจุดอนุมัติ; หยุดให้ผู้ใช้ตรวจ worktree')
            if readonly and git.manifest(cwd)!=before:raise ValueError(role+' เปลี่ยนไฟล์ในขั้น read-only; ไม่เลื่อนไปขั้นถัดไป')
            def complete(r):
                item=next(s for s in r['steps'] if s['id']==stepid);item.update(state='done',finished=time.time(),result=result);r['outputs'][role]=result
            self.update(workspace,identifier,complete)
            if result['blocked']:raise ValueError(role+' ต้องการข้อมูล/สิทธิ์เพิ่มเติม: '+result['summary'])
            live_agents.report(workspace,{**report,'event':'done' if result['passed'] or role in ('code-reviewer','qa-test-engineer') else 'failed','summary':role+': '+result['summary'][:1000],'result':result['details'][:8000]})
            return result
        except Exception as error:
            self.update(workspace,identifier,lambda r:next(s for s in r['steps'] if s['id']==stepid).update(state='failed',error=str(error),finished=time.time()))
            try:live_agents.report(workspace,{**report,'event':'failed','result':str(error)[:8000]})
            except ValueError:pass
            raise
        finally:heartbeat_stop.set()
    def plan(self,workspace,identifier,record):
        if git.digest(record['project'])!=self.base_digest(record):raise ValueError('Project เปลี่ยนระหว่างวางแผน กรุณาเริ่ม Workflow ใหม่')
        result=self.step(workspace,identifier,'tech-lead-architect',record['project'],'Analyze and plan only; do not edit any files. Define acceptance criteria, API contract and explicit per-side path ownership. Explain whether a new page/project/flow requires UI design; skip it for minor button/text/layout changes.',True)
        if not result['passed'] or not (result['frontend'] or result['backend']):raise ValueError('Tech Lead ยังไม่มีแผนที่พร้อมตรวจรับ')
        for side in ('frontend','backend'):
            if result[side] and not result[side+'_paths']:raise ValueError('แผนต้องกำหนดขอบเขตไฟล์ '+side)
            for pattern in result[side+'_paths']:
                if pattern.startswith(('/','\\','-')) or '..' in Path(pattern).parts or '.git' in Path(pattern).parts:raise ValueError('Invalid file ownership pattern')
        ui=record['ui']=='always' or record['ui']=='auto' and result['ui_required']
        return self.state(workspace,identifier,'designing' if ui else 'awaiting_plan',resume='designing' if ui else 'awaiting_plan',needs_ui=ui,error='')
    def base_digest(self,record):return __import__('hashlib').sha256(repr(sorted(record['base_manifest'].items())).encode()).hexdigest()
    def develop(self,workspace,identifier,record):
        if not record['worktrees']:
            git.prepare(record,self.directory(workspace,identifier)/'worktrees')
            self.update(workspace,identifier,lambda r:r.update(worktrees=record['worktrees']))
        candidate=record['worktrees']['candidate'];baseline=git.manifest(candidate);plan=record['outputs']['tech-lead-architect'];workers={}
        for side in ('frontend','backend'):
            if plan[side]:git.synchronize(candidate,record['worktrees'][side]);workers[side]=record['worktrees'][side]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures={pool.submit(self.step,workspace,identifier,side+'-developer',path,'Implement the approved '+side+' scope only. Do not commit/push. Allowed ownership patterns: '+json.dumps(plan[side+'_paths'])+'. Address review/QA/user feedback from prior results. Do not leave mock bypasses in delivered code.'):side for side,path in workers.items()}
            try:
                for future in as_completed(futures):
                    result=future.result()
                    if not result['passed']:raise ValueError(futures[future]+' implementation ยังไม่สำเร็จ')
            except Exception:self.runner.stop(identifier);raise
        self.check(identifier)
        files=git.integrate(candidate,workers,baseline,{side:plan[side+'_paths'] for side in workers})
        self.state(workspace,identifier,'reviewing',resume='reviewing',files=files,error='')
    def inspect(self,workspace,identifier,record,qa=False):
        role='qa-test-engineer' if qa else 'code-reviewer';candidate=record['worktrees']['candidate']
        instruction='Run relevant acceptance/regression tests. Do not edit source files. Report actual commands/results and limitations.' if qa else 'Review the complete candidate against the approved plan and requirements. Do not edit files. Report blocking findings; passed=false if fixes are required.'
        result=self.step(workspace,identifier,role,candidate,instruction,True)
        if result['passed']:
            next_state='awaiting_delivery' if qa else 'testing'
            return self.state(workspace,identifier,next_state,resume=next_state,verified_digest=git.digest(candidate) if qa else '',diff=git.diff(candidate,base=record['base']) if qa else '',error='')
        else:
            count=record['round']+1
            if count>record['max_rounds']:raise ValueError('ครบจำนวนรอบแก้อัตโนมัติแล้ว ตรวจ findings แล้วกด Retry หากต้องการทำต่อ')
            return self.state(workspace,identifier,'implementing',resume='implementing',round=count,error='')
    def drive(self,workspace,identifier):
        try:
            while True:
                self.check(identifier);record=store.get(workspace,identifier);state=record['state']
                if state not in store.ACTIVE:return
                if state=='planning':
                    planned=self.plan(workspace,identifier,record)
                    if planned['state']=='awaiting_plan':return
                elif state=='designing':
                    result=self.step(workspace,identifier,'ui-ux-designer',record['project'],'Design only, no file changes. Provide reviewable wireframes/layout, user flow, states and acceptance notes in details. Implementation waits for dashboard User Accept 1.',True)
                    if not result['passed']:raise ValueError('UI/UX ยังไม่พร้อมตรวจรับ')
                    self.state(workspace,identifier,'awaiting_plan',resume='awaiting_plan',error='');return
                elif state=='implementing':self.develop(workspace,identifier,record)
                elif state=='reviewing':self.inspect(workspace,identifier,record)
                elif state=='testing':
                    checked=self.inspect(workspace,identifier,record,True)
                    if checked['state']=='awaiting_delivery':return
                elif state=='publishing':
                    commit=git.publish(record,lambda value:self.update(workspace,identifier,lambda r:r.update(commit=value))); self.state(workspace,identifier,'completed',commit=commit,pushed=record['push'],error='');return
        except Exception as error:
            with self.lock:
                record=store.get(workspace,identifier)
                if record['state']!='cancelled':record.update(state='interrupted' if self.stopping else 'failed',error=str(error));store.save(workspace,record)
        finally:
            with self.lock:
                current=self.workers.get(identifier)
                if current and current[0] is threading.current_thread():self.workers.pop(identifier,None)
    def action(self,workspace,payload):
        if store.get(workspace,payload.get('id')).get('kind')=='graph':return self.graphs().action(workspace,payload)
        with self.lock:
            identifier=payload.get('id');record=store.get(workspace,identifier);action=payload.get('action')
            if action!='cancel' and payload.get('revision')!=record['revision']:raise Conflict('Workflow เปลี่ยนแล้ว กรุณาโหลดข้อมูลล่าสุดก่อนกด')
            if action=='dismiss':
                if record['state'] not in store.TERMINAL:raise Conflict('ยกเลิกงานก่อนปิดรายการ')
                record['dismissed']=True;store.save(workspace,record);return self.public(record)
            if action=='cancel':
                if record['state'] in store.TERMINAL:return self.public(record)
                if record['state']=='publishing':raise Conflict('กำลังทำ Git operation รอผลก่อนเพื่อไม่ให้ Git ค้างกลางรายการ')
                self.cancelled.add(identifier);record['state']='cancelling';store.save(workspace,record)
            elif action in ('approve','revise'):
                if record['state'] not in ('awaiting_plan','awaiting_delivery'):raise Conflict('ขั้นนี้ยังไม่รอ User Accept')
                gate=1 if record['state']=='awaiting_plan' else 2
                feedback=payload.get('feedback','')
                if not isinstance(feedback,str) or len(feedback)>4000:raise ValueError('Invalid feedback')
                if action=='revise':
                    if not feedback.strip():raise ValueError('ระบุสิ่งที่ต้องแก้')
                    record.update(feedback=feedback,state='planning' if gate==1 else 'implementing',round=0)
                    if gate==1:record['outputs']={}
                else:
                    if gate==2:
                        candidate=record['worktrees']['candidate']
                        if git.digest(candidate)!=record['verified_digest']:raise Conflict('โค้ดเปลี่ยนหลัง QA ให้กดขอแก้ไขเพื่อ Review/QA ใหม่ก่อน Accept')
                        record['accepted_digest']=record['verified_digest']
                    record['approvals'].append({'gate':gate,'at':time.time(),'revision':record['revision'],'digest':record.get('verified_digest') if gate==2 else None})
                    record['state']='implementing' if gate==1 else 'publishing'
                record['resume']=record['state'];record['owner']=os.getpid();record['error']='';store.save(workspace,record);self.launch(workspace,identifier)
            elif action=='recheck':
                if record['state'] not in ('failed','interrupted','awaiting_delivery') or not record['worktrees'] or identifier in self.workers:raise Conflict('ยังตรวจ Candidate ใหม่ไม่ได้')
                record.update(state='reviewing',resume='reviewing',round=0,error='',owner=os.getpid());store.save(workspace,record);self.launch(workspace,identifier)
            elif action=='retry':
                if record['state'] not in ('failed','interrupted') or identifier in self.workers:raise Conflict('ยัง Retry ไม่ได้')
                record['state']=record['resume'];record['round']=0;record['error']='';record['owner']=os.getpid();store.save(workspace,record);self.launch(workspace,identifier)
            else:raise ValueError('Invalid workflow action')
        if action=='cancel':
            try:self.runner.stop(identifier)
            except Exception as error:
                self.state(workspace,identifier,'failed',error='หยุด CLI ไม่สำเร็จ ต้องตรวจ process ก่อนปลดล็อก: '+str(error));raise
            self.state(workspace,identifier,'cancelled',error='')
        return self.get(workspace,identifier)
    def shutdown(self):
        if self._graphs is not None:self._graphs.shutdown()
        self.stopping=True
        with self.lock:workers=list(self.workers.items())
        for identifier,_ in workers:self.runner.stop(identifier)
        for _,(thread,_) in workers:thread.join(timeout=5)
engine=Engine()
atexit.register(engine.shutdown)
