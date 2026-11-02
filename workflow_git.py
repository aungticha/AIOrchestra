"""Isolated worktrees and deterministic candidate integration; no model-driven push."""
import fnmatch
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

class GitError(ValueError):pass

def git(project,*args,timeout=30):
    try:result=subprocess.run(['git','-C',str(project),*args],capture_output=True,timeout=timeout,env={**os.environ,'GIT_TERMINAL_PROMPT':'0'})
    except subprocess.TimeoutExpired:raise GitError('Git operation timed out; inspect the worktree before retrying') from None
    if result.returncode:raise GitError(result.stderr.decode('utf-8','replace')[-4000:] or 'Git command failed')
    return result.stdout

def validate_project(raw):
    if not isinstance(raw,str) or len(raw)>2048 or any(ord(c)<32 for c in raw):raise ValueError('Invalid project path')
    path=Path(raw).expanduser()
    if not path.is_absolute() or not path.is_dir():raise ValueError('Project ต้องเป็น absolute path ของโฟลเดอร์ในเครื่อง')
    path=path.resolve();root=Path(git(path,'rev-parse','--show-toplevel').decode().strip()).resolve()
    if path!=root:raise ValueError('เลือกโฟลเดอร์ root ของ Git repository')
    head=git(path,'rev-parse','HEAD').decode().strip()
    if git(path,'status','--porcelain','--untracked-files=all'):raise ValueError('Project มีงานที่ยังไม่ commit กรุณาจัดการงานเดิมก่อนเริ่ม Workflow')
    return str(path),head

def files(project):
    tracked=git(project,'ls-files','-z').split(b'\0');untracked=git(project,'ls-files','--others','--exclude-standard','-z').split(b'\0')
    return {value.decode('utf-8','surrogateescape') for value in tracked+untracked if value}

def path_in(root,name):
    candidate=Path(root)/name;actual=candidate.resolve()
    if candidate.is_symlink() or not actual.is_relative_to(Path(root).resolve()) or name=='.git' or name.startswith('.git/'):
        raise GitError('ไม่รองรับ symlink หรือ path นอก worktree: '+name)
    return candidate

def manifest(project):
    result={}
    for name in sorted(files(project)):
        path=path_in(project,name)
        if path.is_file():result[name]=hashlib.sha256(path.read_bytes()).hexdigest()+('x' if path.stat().st_mode&0o111 else '')
        elif path.exists():raise GitError('ไม่รองรับการเปลี่ยน submodule/directory: '+name)
    return result

def digest(project):return hashlib.sha256(repr(sorted(manifest(project).items())).encode()).hexdigest()

def changed(before,after):return {name for name in before.keys()|after.keys() if before.get(name)!=after.get(name)}

def copy_paths(source,destination,names):
    for name in names:
        origin=path_in(source,name);target=path_in(destination,name)
        if origin.is_file():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(origin,target)
        elif target.is_file():target.unlink()

def synchronize(source,destination):
    before,after=manifest(destination),manifest(source);copy_paths(source,destination,changed(before,after))

def prepare(record,folder):
    if git(record['project'],'rev-parse','HEAD').decode().strip()!=record['base'] or git(record['project'],'status','--porcelain','--untracked-files=all'):
        raise GitError('Project เปลี่ยนจากตอนวางแผน กรุณาเริ่ม Workflow ใหม่เพื่อไม่ทับงานอื่น')
    paths={}
    for role in ['candidate','frontend','backend']:
        path=Path(folder)/role;branch=record['branch']+('-'+role if role!='candidate' else '')
        if not path.exists():git(record['project'],'worktree','add','-b',branch,str(path),record['base'])
        if git(path,'rev-parse','HEAD').decode().strip()!=record['base']:raise GitError('Worktree มี commit นอกขั้นตอนที่อนุมัติ')
        paths[role]=str(path)
    record['worktrees']=paths

def owns(name,patterns):
    return any(fnmatch.fnmatchcase(name,pattern) or (pattern.endswith('/') and name.startswith(pattern)) for pattern in patterns)

def integrate(candidate,workers,baseline,ownership):
    changes={};snapshots={role:manifest(path) for role,path in workers.items()}
    for role,snapshot in snapshots.items():
        names=changed(baseline,snapshot)
        outside=[name for name in names if not owns(name,ownership[role])]
        if outside:raise GitError(role+' แก้ไฟล์นอกขอบเขตที่อนุมัติ: '+', '.join(sorted(outside)))
        for name in names:
            if name in changes and snapshots[changes[name]].get(name)!=snapshot.get(name):raise GitError('Frontend/Backend แก้ไฟล์ชนกัน: '+name+'; เก็บ worktree ทั้งสองไว้แล้ว ให้แก้ conflict ก่อน Retry')
            changes[name]=role
    if manifest(candidate)!=baseline:raise GitError('Candidate ถูกเปลี่ยนระหว่างทำงาน ไม่เขียนทับการแก้ไขภายนอก')
    for name,role in changes.items():copy_paths(workers[role],candidate,[name])
    return sorted(changes)

def diff(project,limit=100000,base="HEAD"):
    text=git(project,'diff','--no-ext-diff','--no-textconv','--stat',base).decode('utf-8','replace')
    text+='\n'+git(project,'diff','--no-ext-diff','--no-textconv',base).decode('utf-8','replace')
    new=git(project,'ls-files','--others','--exclude-standard').decode('utf-8','replace')
    return (text+'\nNew files:\n'+new)[:limit]

def publish(record,on_commit=lambda _commit:None):
    path=record['worktrees']['candidate']
    if digest(path)!=record['accepted_digest']:raise GitError('Candidate เปลี่ยนหลัง Accept ต้อง Review/QA และ Accept ใหม่')
    changed_names=changed(record['base_manifest'],manifest(path))
    for name in changed_names:
        filename=Path(name).name.lower()
        if filename=='.env' or filename.startswith('.env.') and filename!='.env.example' or filename in ('api-tokens.json','id_rsa','id_ed25519') or 'secrets' in Path(name).parts:
            raise GitError('พบไฟล์ที่อาจมี credentials ไม่ commit อัตโนมัติ: '+name)
    if git(path,'rev-parse','--abbrev-ref','HEAD').decode().strip()!=record['branch']:raise GitError('Candidate branch เปลี่ยนจากเป้าหมายของ Workflow')
    head=git(path,'rev-parse','HEAD').decode().strip()
    if head!=record.get('commit',record['base']):raise GitError('Candidate HEAD เปลี่ยนนอก controller ตรวจประวัติ Git ก่อนส่ง')
    git(path,'add','--all')
    if git(path,'diff','--cached','--name-only'):
        git(path,'commit','-m','AIOrchestra: '+record['task'].splitlines()[0][:100],timeout=120)
    commit=git(path,'rev-parse','HEAD').decode().strip();on_commit(commit)
    if git(path,'status','--porcelain','--untracked-files=all') or digest(path)!=record['accepted_digest']:raise GitError('Git hook เปลี่ยนไฟล์หลัง Accept ต้อง Review/QA และ Accept ใหม่ก่อน Push')
    if record['push']:
        git(path,'push',record['remote'],'HEAD:refs/heads/'+record['branch'],timeout=120)
    return commit
