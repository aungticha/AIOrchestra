"""Durable workflow records and revision-checked user approval gates."""
import json
import time
import live_agents

TERMINAL={'completed','cancelled'}
ACTIVE={'planning','designing','implementing','reviewing','testing','publishing','cancelling'}
SCHEMA='''CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY,team TEXT NOT NULL,state TEXT NOT NULL,revision INTEGER NOT NULL,updated REAL NOT NULL,record TEXT NOT NULL);'''

def connect(workspace):
    db=live_agents.connect(workspace);db.executescript(SCHEMA);return db

def save(workspace,record):
    record['updated']=time.time();record['revision']=record.get('revision',0)+1
    db=connect(workspace)
    try:
        with db: db.execute('INSERT INTO workflows VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,revision=excluded.revision,updated=excluded.updated,record=excluded.record',(record['id'],record['team'],record['state'],record['revision'],record['updated'],json.dumps(record,ensure_ascii=False)))
    finally:db.close()

def get(workspace,identifier):
    if not isinstance(identifier,str):raise ValueError('Invalid workflow ID')
    db=connect(workspace)
    try:row=db.execute('SELECT record FROM workflows WHERE id=?',(identifier,)).fetchone()
    finally:db.close()
    if not row:raise ValueError('ไม่พบ Workflow')
    return json.loads(row['record'])

def listing(workspace):
    db=connect(workspace)
    try:return [json.loads(row['record']) for row in db.execute("SELECT record FROM workflows WHERE state NOT IN ('completed','cancelled') OR id IN (SELECT id FROM workflows ORDER BY updated DESC LIMIT 100) ORDER BY updated DESC")]
    finally:db.close()
