"""Local reported agent activity, shared by CLI reporters and the dashboard."""
from pathlib import Path
import re
import sqlite3
import time
import team_paths
import agent_skills
import rewards

TIMEOUT = 180
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
SESSION = re.compile(r'[a-zA-Z0-9_-]{1,128}')
EVENTS = {'selected','skill','working','waiting','done','failed','heartbeat'}
TERMINAL = {'done','failed','closed'}


def connect(workspace):
    root = Path(workspace).resolve()
    folder = root/'runtime'
    path = folder/'activity.sqlite3'
    if folder.is_symlink() or path.is_symlink():
        raise ValueError('Activity storage cannot be a symlink')
    folder.mkdir(parents=True,exist_ok=True)
    db = sqlite3.connect(path,timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS runs (
      engine TEXT NOT NULL, session TEXT NOT NULL, team TEXT NOT NULL,
      agent TEXT NOT NULL, project TEXT NOT NULL, project_path TEXT NOT NULL,
      status TEXT NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY(engine,session)
    );
    CREATE TABLE IF NOT EXISTS managed_runs (engine TEXT NOT NULL, session TEXT NOT NULL, active INTEGER NOT NULL, PRIMARY KEY(engine,session));
    CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, engine TEXT NOT NULL,
      session TEXT NOT NULL, team TEXT NOT NULL, agent TEXT NOT NULL,
      project TEXT NOT NULL, kind TEXT NOT NULL, skill TEXT, at REAL NOT NULL
    );
    ''')
    db.executescript(rewards.SCHEMA)
    return db


def identifier(value):
    if not isinstance(value,str) or len(value)>64 or not SLUG.fullmatch(value):
        raise ValueError('Invalid team, agent or skill ID')
    return value


def catalog_path(workspace, team, agent):
    root = Path(workspace).resolve()
    path = (team_paths.team_dir(workspace,team)/'agents'/(identifier(agent)+'.md')).resolve()
    if not path.is_relative_to(root/'teams') or not path.is_file():
        raise ValueError('Agent not found in library')
    return path


def report(workspace, payload):
    if not isinstance(payload,dict): raise ValueError('Event must be an object')
    engine = payload.get('engine')
    session = payload.get('session')
    event = payload.get('event')
    if engine not in ('Codex','Claude') or not isinstance(session,str) or not SESSION.fullmatch(session) or event not in EVENTS:
        raise ValueError('Invalid engine, session or event')
    team,agent = team_paths.team_id(payload.get('team')), identifier(payload.get('agent'))
    catalog_path(workspace,team,agent)
    project = payload.get('project')
    if not isinstance(project,str) or len(project)>2048 or any(ord(c)<32 for c in project):
        raise ValueError('Invalid project path')
    project_path = Path(project).expanduser()
    if not project_path.is_absolute(): raise ValueError('Project must be an absolute local path')
    project_path = project_path.resolve()
    project_name = project_path.name or str(project_path)
    skill = None
    if event=='skill':
        skill=identifier(payload.get('skill'))
        root=Path(workspace).resolve()/'teams'
        path=(team_paths.team_dir(workspace,team)/'skills'/skill/'SKILL.md').resolve()
        if not path.is_relative_to(root) or not path.is_file(): raise ValueError('Skill not found in selected team')
    stamp=time.time()
    db=connect(workspace)
    try:
        with db:
            # Serialize writers, including heartbeat checks and session switches.
            db.execute('BEGIN IMMEDIATE')
            catalog_path(workspace,team,agent)
            if event=='skill':
                if not path.is_file(): raise ValueError('Skill no longer exists')
                assigned=agent_skills.assigned(catalog_path(workspace,team,agent).read_text(encoding='utf-8'))
                if assigned is not None and skill not in assigned: raise ValueError('Skill is not assigned to this agent')
            old=db.execute('SELECT * FROM runs WHERE engine=? AND session=?',(engine,session)).fetchone()
            if event!='selected':
                if old is None: raise ValueError('Report selected before other events')
                if old['team']!=team or old['agent']!=agent or old['project_path']!=str(project_path):
                    raise ValueError('Session belongs to another agent/project; report selected first')
                if old['status'] in TERMINAL:
                    if event=='done' and old['status']=='done': return {'ok':True,'session':session,'status':'done'}
                    raise ValueError('Session has ended; start with selected again')
            managed=db.execute('SELECT active FROM managed_runs WHERE engine=? AND session=?',(engine,session)).fetchone()
            if managed and managed['active'] and event=='selected' and old and (old['team']!=team or old['agent']!=agent or old['project_path']!=str(project_path)):
                raise ValueError('Managed CLI session cannot switch agents/projects')
            status = {'selected':'working','skill':'working','working':'working','waiting':'waiting','done':'done','failed':'failed'}.get(event,old['status'] if old else 'working')
            rewards.lifecycle(db,payload,status,bool(managed and managed['active']))
            if managed and managed['active'] and event in ('done','failed'): status='waiting'
            db.execute('''INSERT INTO runs VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(engine,session) DO UPDATE SET
                team=excluded.team,agent=excluded.agent,project=excluded.project,project_path=excluded.project_path,
                status=excluded.status,updated_at=excluded.updated_at''',
                (engine,session,team,agent,project_name,str(project_path),status,stamp))
            if event!='heartbeat':
                db.execute('INSERT INTO events(engine,session,team,agent,project,kind,skill,at) VALUES(?,?,?,?,?,?,?,?)',
                    (engine,session,team,agent,project_name,event,skill,stamp))
                db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 1000)')
            db.execute('DELETE FROM runs WHERE updated_at < ?', (stamp-30*86400,))
        return {'ok':True,'session':session,'status':status}
    finally:
        db.close()


def snapshot(workspace):
    db=connect(workspace)
    try:
        db.execute('BEGIN')
        rows=db.execute('SELECT * FROM runs ORDER BY updated_at DESC LIMIT 200').fetchall()
        locks=db.execute("SELECT DISTINCT team FROM runs WHERE status NOT IN ('done','failed','closed')").fetchall()
        workflows=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'").fetchone()
        workflow_locks=[row['team'] for row in db.execute("SELECT DISTINCT team FROM workflows WHERE state NOT IN ('completed','cancelled')")] if workflows else []
        events=db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 100').fetchall()
    finally:
        db.close()
    stamp=time.time()
    runs=[]
    teams={}
    for row in rows:
        item=dict(row)
        stale=item['status'] not in TERMINAL and stamp-item['updated_at']>TIMEOUT
        item['reportedStatus']=item['status']
        if stale: item['status']='unknown'
        item['active']=item['status']=='working'
        item['source']='client_reported'
        if item['active']: teams[item['team']]=teams.get(item['team'],0)+1
        runs.append(item)
    return {'runs':runs,'events':[dict(e) for e in events],'activeTeams':teams,'timeoutSeconds':TIMEOUT,
            'updatedAt':stamp,'source':'client_reported','lockedTeams':sorted(set([r['team'] for r in locks]+workflow_locks))}


def close_run(workspace,engine,session):
    if engine not in ('Codex','Claude') or not isinstance(session,str) or not SESSION.fullmatch(session): raise ValueError('Invalid session')
    db=connect(workspace)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM runs WHERE engine=? AND session=?',(engine,session)).fetchone()
            if row is None: raise ValueError('ไม่พบเซสชัน')
            managed=db.execute('SELECT active FROM managed_runs WHERE engine=? AND session=?',(engine,session)).fetchone()
            if managed and managed['active'] and time.time()-row['updated_at']<=TIMEOUT: raise ValueError('ปิด CLI จากแท็บ Terminal เพื่อหยุด process และจบงาน')
            if row['status'] in TERMINAL: return {'ok':True}
            if row['status']!='waiting' and time.time()-row['updated_at']<=TIMEOUT:
                raise ValueError('เซสชันยังรายงานว่าทำงานอยู่ ให้หยุด/จบงานจาก CLI ก่อน')
            stamp=time.time()
            rewards.abandon(db,engine,session)
            db.execute('UPDATE managed_runs SET active=0 WHERE engine=? AND session=?',(engine,session))
            db.execute("UPDATE runs SET status='closed',updated_at=? WHERE engine=? AND session=?",(stamp,engine,session))
            db.execute('INSERT INTO events(engine,session,team,agent,project,kind,skill,at) VALUES(?,?,?,?,?,?,?,?)',
                (engine,session,row['team'],row['agent'],row['project'],'closed',None,stamp))
        return {'ok':True}
    finally:
        db.close()
