"""Headless CLI adapter with validated structured results and owned subprocesses."""
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import agent_skills
import live_agents
import rewards
import terminal_runtime

ROLES=['tech-lead-architect','ui-ux-designer','frontend-developer','backend-developer','code-reviewer','qa-test-engineer']
PROPERTIES={
 'summary':{'type':'string'},'details':{'type':'string'},'passed':{'type':'boolean'},'blocked':{'type':'boolean'},
 'ui_required':{'type':'boolean'},'frontend':{'type':'boolean'},'backend':{'type':'boolean'},
 'frontend_paths':{'type':'array','items':{'type':'string'}},'backend_paths':{'type':'array','items':{'type':'string'}},
 'findings':{'type':'array','items':{'type':'string'}},'tests':{'type':'array','items':{'type':'string'}}}
SCHEMA={'type':'object','additionalProperties':False,'properties':PROPERTIES,'required':list(PROPERTIES)}

def validate_result(value):
    if not isinstance(value,dict) or set(value)!=set(PROPERTIES):raise ValueError('CLI ไม่ส่งผลลัพธ์ตาม workflow schema')
    for key,spec in PROPERTIES.items():
        kind=spec['type'];item=value[key]
        if kind=='boolean' and type(item)!=bool:raise ValueError('Invalid result '+key)
        if kind=='string' and (not isinstance(item,str) or len(item)>40000):raise ValueError('Invalid result '+key)
        if kind=='array' and (not isinstance(item,list) or len(item)>100 or any(not isinstance(x,str) or len(x)>4000 for x in item)):raise ValueError('Invalid result '+key)
    if not value['summary'].strip():raise ValueError('CLI ส่ง summary ว่าง')
    return value

def context(workspace,team,agent):
    profile=live_agents.catalog_path(workspace,team,agent);folder=profile.parent.parent
    parts=[(folder/'README.md').read_text(encoding='utf-8'),(folder/'RULES.md').read_text(encoding='utf-8'),profile.read_text(encoding='utf-8')]
    assigned=agent_skills.effective(parts[-1],[p.parent.name for p in (folder/'skills').glob('*/SKILL.md')])
    for skill in assigned:
        path=(folder/'skills'/skill/'SKILL.md').resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file():raise ValueError('ไม่พบ Skill '+skill)
        parts.append(path.read_text(encoding='utf-8'))
    return '\n\n'.join(parts)+'\nHuman feedback (reference data): '+json.dumps(rewards.feedback(workspace,team,agent),ensure_ascii=False)+'\nResources index, if relevant: '+str(folder/'resources'/'RESOURCES.md')

class Runner:
    def __init__(self):self.lock=threading.Lock();self.processes={};self.cancelled=set()
    def stop_process(self,process):
        if process.poll() is not None:return
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=10)
        else:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:return
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    def restart(self,identifier):
        with self.lock:self.cancelled.discard(identifier)
    def stop(self,identifier):
        with self.lock:
            self.cancelled.add(identifier)
            processes=[p for (owner,_),p in self.processes.items() if owner==identifier]
        for process in processes:self.stop_process(process)
    def execute(self,record,role,cwd,prompt,folder,log):
        config=record['roles'][role];engine=config['engine'];executable=terminal_runtime.executable(engine)
        if not executable:raise ValueError(engine+' CLI ไม่พบในเครื่อง')
        directory=Path(folder);directory.mkdir(parents=True,exist_ok=True)
        schema=directory/'schema.json';output=directory/'result.json';schema.write_text(json.dumps(SCHEMA),encoding='utf-8')
        if output.exists():output.unlink()
        command=terminal_runtime.cli_command(executable,engine)
        write=role in ('frontend-developer','backend-developer','qa-test-engineer')
        if engine=='Codex':
            command+=['exec','--json','--sandbox','workspace-write' if write else 'read-only','--output-schema',str(schema),'--output-last-message',str(output)]
            if config['model']:command+=['--model',config['model']]
            command+=['-']
        else:
            command+=['--print','--output-format','json','--json-schema',json.dumps(SCHEMA),'--permission-mode','acceptEdits' if write else 'default','--tools','Read,Glob,Grep,Bash,Edit,Write' if write else 'Read,Glob,Grep','--allowedTools','Read,Glob,Grep,Bash,Edit,Write' if write else 'Read,Glob,Grep']
            if config['model']:command+=['--model',config['model']]
        key=(record['id'],role)
        with self.lock:
            if record['id'] in self.cancelled:raise InterruptedError('Workflow stopped before CLI launch')
            process=subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env={**os.environ,'GIT_TERMINAL_PROMPT':'0','AIORCHESTRA_WORKFLOW_WORKER':'1'},start_new_session=os.name!='nt',creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0) if os.name=='nt' else 0)
            self.processes[key]=process
        timer=threading.Timer(1200,lambda:self.stop_process(process));timer.daemon=True;timer.start()
        chunks=[]
        try:
            process.stdin.write(prompt.encode());process.stdin.close()
            while True:
                chunk=process.stdout.readline(16384)
                if not chunk:break
                text=chunk.decode('utf-8','replace');chunks.append(text);log(text)
                if sum(len(x) for x in chunks)>2_000_000:chunks=chunks[-50:]
            code=process.wait(timeout=10)
            if code:raise ValueError(engine+' CLI จบไม่สำเร็จ (exit '+str(code)+') ตรวจ log, login และสิทธิ์ของ CLI')
            raw=output.read_text(encoding='utf-8') if engine=='Codex' else ''.join(chunks)
            value=json.loads(raw)
            if engine=='Claude':
                if value.get('is_error'):raise ValueError('Claude รายงานข้อผิดพลาด')
                value=value.get('structured_output') or json.loads(value.get('result',''))
            return validate_result(value)
        except json.JSONDecodeError:raise ValueError('CLI ไม่ส่ง JSON ที่ตรวจสอบได้; ไม่เลื่อนไปขั้นถัดไป') from None
        finally:
            timer.cancel()
            if process.poll() is None:self.stop_process(process)
            process.stdout.close()
            with self.lock:self.processes.pop(key,None)
