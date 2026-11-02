"""Install the local workflow skill while preserving unrelated client configuration."""
import json
import os
from pathlib import Path
import tempfile
import sys

ROOT=Path(__file__).resolve().parent
MARKER='<!-- AIORCHESTRA:MANAGED-SKILL -->'

def skill_target(instructions,client='codex'):
    home=Path(instructions).parent
    if client=='codex' and home.resolve()==(Path.home()/'.codex').resolve():return Path.home()/'.agents'/'skills'/'aiorchestra-workflow'/'SKILL.md'
    return home/'skills'/'aiorchestra-workflow'/'SKILL.md'

def content(workspace):
    command=[sys.executable,str(ROOT/'workflow_bridge.py'),'--workspace',str(Path(workspace).resolve())]
    source=(ROOT/'integrations/aiorchestra-workflow/SKILL.md').read_text(encoding='utf-8')
    return source.replace('__COMMAND__',json.dumps(command,ensure_ascii=False))

def preview(workspace,instructions,client):
    target=skill_target(instructions,client)
    if any(p.is_symlink() for p in (target,target.parent,target.parent.parent,target.parent.parent.parent)):raise ValueError('Workflow Skill path cannot be a symlink')
    previous=target.read_text(encoding='utf-8') if target.is_file() else ''
    if previous and MARKER not in previous:raise ValueError('พบ Skill aiorchestra-workflow ของผู้ใช้อยู่แล้ว ไม่เขียนทับ กรุณาเลือกชื่อ/ตำแหน่งอื่นก่อน Setup')
    return {'workflowSkillPath':str(target),'workflowSkillChanged':previous!=content(workspace),'workflowBridgePath':str(ROOT/'workflow_bridge.py')}

def install(workspace,instructions,client):
    info=preview(workspace,instructions,client);target=Path(info['workflowSkillPath'])
    if not info['workflowSkillChanged']:return {**info,'workflowSkillUpdated':False}
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        with tempfile.NamedTemporaryFile(dir=target.parent,prefix='SKILL.',suffix='.bak',delete=False) as backup:backup.write(target.read_bytes())
    with tempfile.NamedTemporaryFile(dir=target.parent,mode='w',encoding='utf-8',delete=False) as output:output.write(content(workspace));temporary=output.name
    os.chmod(temporary,0o600);os.replace(temporary,target)
    return {**info,'workflowSkillUpdated':True}
