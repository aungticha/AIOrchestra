"""Recoverable library mutations serialized with lifecycle reporting."""
from pathlib import Path
import json
import os
import re
import shutil
import tempfile
import time
import uuid
import agent_skills
import agent_appearance
import live_agents
import team_paths
import team_description

class Locked(ValueError): pass


def assert_unlocked(db,team):
    row=db.execute("SELECT agent,status FROM runs WHERE team=? AND status NOT IN ('done','failed','closed') LIMIT 1",(team,)).fetchone()
    exists=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'").fetchone()
    if exists and db.execute("SELECT 1 FROM workflows WHERE team=? AND state NOT IN ('completed','cancelled') LIMIT 1",(team,)).fetchone(): raise Locked('ทีมถูกล็อกโดย Workflow ที่ยังไม่จบ กรุณาจบหรือยกเลิก Workflow ก่อน')
    if row: raise Locked(f'ทีมถูกล็อก: {row["agent"]} มีเซสชันที่ยังไม่จบ ({row["status"]}) กรุณาจบงานหรือปิดรายงานเซสชันค้างก่อน')


def checked_file(root,path):
    actual=path.resolve()
    if path.is_symlink() or not actual.is_relative_to(root.resolve()): raise ValueError('ไม่แก้ไฟล์ symlink หรือ path นอกทีม')
    return path


def write(path,content):
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
            tmp=f.name;f.write(content)
        os.replace(tmp,path)
    finally:
        if tmp and os.path.exists(tmp): os.unlink(tmp)


def validate_bindings(folder,content):
    values=agent_skills.assigned(content)
    if values is not None:
        for value in values:
            path=checked_file(folder,folder/'skills'/value/'SKILL.md')
            if not path.is_file(): raise ValueError('ไม่พบ Skill ที่ผูกกับ Agent: '+value)


def rename_manifest(content,old,new):
    match=agent_skills.front(content)
    metadata=match.group(2)
    metadata,count=re.subn(r'^name\s*:.*$',lambda _: 'name: '+json.dumps(new),metadata,count=1,flags=re.M)
    if count!=1: raise ValueError('ไม่พบ name ใน frontmatter')
    updated=content[:match.start(2)]+metadata+content[match.end(2):]
    return re.sub(r'^# '+re.escape(old)+r'[ \t]*$',lambda _: '# '+new,updated,count=1,flags=re.M)


def manage(workspace,payload):
    team=team_paths.team_id(payload.get('team'))
    kind,action=payload.get('kind'),payload.get('action')
    if kind not in ('team','agent','skill') or action not in ('rename','delete','skills','description','profile'): raise ValueError('คำสั่งจัดการไม่ถูกต้อง')
    if action=='profile' and kind!='agent': raise ValueError('Profile ใช้สำหรับ Agent เท่านั้น')
    if action=='description' and kind!='team': raise ValueError('Description ใช้สำหรับทีมเท่านั้น')
    if action=='skills' and kind!='agent': raise ValueError('ผูก Skill ได้เฉพาะ Agent')
    root=Path(workspace).resolve()
    if (root/'teams'/team_paths.folder_name(team)).is_symlink(): raise ValueError('ไม่แก้ทีมที่เป็น symlink')
    folder=team_paths.team_dir(workspace,team)
    db=live_agents.connect(workspace)
    archive=None
    mutated=False
    original_changes={}
    try:
        db.execute('BEGIN IMMEDIATE')
        assert_unlocked(db,team)
        if not folder.is_dir(): raise ValueError('ไม่พบทีม')
        for path in folder.rglob('*'):
            if path.is_symlink(): raise ValueError('ไม่แก้ทีมที่มี symlink กรุณาตรวจไฟล์ก่อน')
        name=payload.get('id')
        if kind=='team': target=folder
        else:
            name=live_agents.identifier(name)
            target=folder/'agents'/(name+'.md') if kind=='agent' else folder/'skills'/name
            if not target.exists(): raise ValueError('ไม่พบรายการ')
        changes={}
        destination=None
        if action=='rename':
            new=payload.get('name')
            if kind=='team':
                if not isinstance(new,str) or not new.strip() or len(new)>200 or any(ord(c)<32 for c in new): raise ValueError('ชื่อทีมต้องมี 1–200 ตัวอักษรในบรรทัดเดียว')
                text=(folder/'README.md').read_text(encoding='utf-8')
                updated,count=re.subn(r'^# [^\r\n]*',lambda _:'# '+new.strip(),text,count=1,flags=re.M)
                changes[folder/'README.md']=updated if count else '# '+new.strip()+'\n\n'+text
            else:
                new=live_agents.identifier(new)
                destination=folder/'agents'/(new+'.md') if kind=='agent' else folder/'skills'/new
                if destination.exists(): raise ValueError('ID ปลายทางมีอยู่แล้ว')
                if kind=='agent' and db.execute('SELECT 1 FROM agent_accounts WHERE team=? AND agent=?',(team,new)).fetchone(): raise ValueError('ID นี้มีประวัติ coins/rating อยู่แล้ว กรุณาเลือก ID ใหม่')
                manifest=target if kind=='agent' else target/'SKILL.md'
                changes[manifest]=rename_manifest(manifest.read_text(encoding='utf-8'),name,new)
        if action=='description':
            description=team_description.validate(payload.get('description'))
            changes[folder/'README.md']=team_description.replace((folder/'README.md').read_text(encoding='utf-8'),description)
            metadata=json.loads((folder/'TEAM.json').read_text(encoding='utf-8')) if (folder/'TEAM.json').exists() else {'id':team}
            metadata['description']=description
            changes[folder/'TEAM.json']=json.dumps(metadata,ensure_ascii=False,indent=2)+'\n'
        if action=='profile':
            changes[target]=agent_skills.set_profile(target.read_text(encoding='utf-8'),payload.get('displayName'),payload.get('role'),payload.get('description'))
            if 'appearance' in payload: changes[target]=agent_appearance.set_value(changes[target],payload['appearance'])
        if action=='skills':
            values=payload.get('skills')
            if not isinstance(values,list): raise ValueError('skills ต้องเป็น list')
            content=agent_skills.set_assigned(target.read_text(encoding='utf-8'),values)
            validate_bindings(folder,content)
            changes[target]=content
        if kind=='skill' and action in ('rename','delete'):
            for path in (folder/'agents').glob('*.md'):
                text=path.read_text(encoding='utf-8')
                values=agent_skills.assigned(text)
                if values is not None and name in values:
                    values=[new if value==name else value for value in values] if action=='rename' else [value for value in values if value!=name]
                    changes[path]=agent_skills.set_assigned(text,values)
        if kind=='skill' and action=='delete':
            reference=r'(?:\./)?skills/'+re.escape(name)+r'/[^\s)<>]*'
            for path in folder.rglob('*.md'):
                if path.is_relative_to(folder/'resources'): continue
                if path.is_relative_to(target): continue
                text=changes.get(path,path.read_text(encoding='utf-8'))
                updated=re.sub(r'\[([^\]]+)\]\('+reference+r'\)',lambda match:match.group(1)+' (removed Skill: '+name+')',text)
                updated=re.sub(reference,lambda _:'[removed Skill: '+name+']',updated)
                if updated!=text: changes[path]=updated
        # Update relative Markdown references when renaming; do not replace unrelated prose.
        if action=='rename' and kind!='team':
            old_ref=('skills/'+name+'/') if kind=='skill' else ('agents/'+name+'.md')
            new_ref=('skills/'+new+'/') if kind=='skill' else ('agents/'+new+'.md')
            for path in folder.rglob('*.md'):
                if path.is_relative_to(folder/'resources'): continue
                text=changes.get(path,path.read_text(encoding='utf-8'))
                if old_ref in text: changes[path]=text.replace(old_ref,new_ref)
        if action!='delete':
            trash=root/'.trash'
            if trash.is_symlink(): raise ValueError('Trash storage cannot be a symlink')
            archive=trash/uuid.uuid4().hex
            archive.mkdir(parents=True)
            shutil.copytree(folder,archive/'before')
            (archive/'operation.json').write_text(json.dumps({'team':team,'teamFolder':folder.name,'kind':kind,'id':name,'action':action,'at':time.time()},ensure_ascii=False,indent=2),encoding='utf-8')
        original_changes={path:path.read_text(encoding='utf-8') if path.exists() else None for path in changes}
        mutated=True
        for path,text in changes.items(): write(checked_file(folder,path),text)
        if action=='delete':
            if target.is_dir(): shutil.rmtree(target)
            else: target.unlink()
        if destination is not None: os.replace(target,destination)
        if kind=='agent' and action=='rename':
            db.execute('UPDATE agent_accounts SET agent=? WHERE team=? AND agent=?',(new,team,name))
            db.execute('UPDATE jobs SET agent=? WHERE team=? AND agent=?',(new,team,name))
        if kind=='team' and action=='delete':
            exists=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resources'").fetchone()
            if exists: db.execute('DELETE FROM resources WHERE team=?',(team,))
        db.commit()
        return {'archive':str(archive) if archive else None,'id':new if action=='rename' and kind!='team' else name}
    except Exception:
        if mutated and archive and (archive/'before').is_dir():
            # Restore the exact pre-operation team after a partial filesystem failure.
            if folder.exists(): shutil.rmtree(folder)
            shutil.copytree(archive/'before',folder)
        elif mutated and archive is None:
            for path,text in original_changes.items():
                if path.parent.is_dir():
                    if text is not None: write(path,text)
                    elif path.exists(): path.unlink()
        db.rollback()
        raise
    finally:
        db.close()
