"""Persistent virtual rewards, explicit task completion and optional human review.
All lifecycle mutations share the activity SQLite transaction; no real money.
"""
import json
import time
import uuid

SCHEMA='''
CREATE TABLE IF NOT EXISTS treasury (id INTEGER PRIMARY KEY CHECK(id=1), balance INTEGER NOT NULL CHECK(balance>=0));
INSERT OR IGNORE INTO treasury VALUES(1,86400);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, engine TEXT NOT NULL, session TEXT NOT NULL, team TEXT NOT NULL, agent TEXT NOT NULL,
 project TEXT NOT NULL, title TEXT NOT NULL, result TEXT NOT NULL DEFAULT '', state TEXT NOT NULL,
 skills TEXT NOT NULL DEFAULT '[]', started REAL NOT NULL, finished REAL,
 coin INTEGER NOT NULL DEFAULT 0, review_state TEXT NOT NULL DEFAULT 'pending',
 stars INTEGER, comment TEXT NOT NULL DEFAULT '', reviewed REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_job ON jobs(engine,session) WHERE state='working';
CREATE TABLE IF NOT EXISTS agent_accounts (team TEXT NOT NULL, agent TEXT NOT NULL, coins INTEGER NOT NULL DEFAULT 0, rating INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(team,agent));
'''

def text(value,limit,field):
    if not isinstance(value,str) or len(value)>limit or '\x00' in value: raise ValueError('Invalid '+field)
    return value.strip()

def current(db,engine,session):
    return db.execute("SELECT * FROM jobs WHERE engine=? AND session=? AND state='working'",(engine,session)).fetchone()

def lifecycle(db,payload,status,managed=False):
    engine,session=payload['engine'],payload['session'];event=payload['event']
    job=current(db,engine,session)
    summary=text(payload.get('summary') or '',2000,'summary')
    result=text(payload.get('result') or '',8000,'result')
    if event in ('selected','working') and not job:
        exists=db.execute('SELECT 1 FROM jobs WHERE engine=? AND session=?',(engine,session)).fetchone()
        # A duplicate selected cannot mint a new task. Managed CLI starts tasks
        # explicitly via working, not on its login / acknowledgement screen.
        start=(event=='working') or (event=='selected' and not managed and not payload.get('deferJob') and not exists)
        if start:
            identifier=uuid.uuid4().hex
            db.execute("INSERT INTO jobs(id,engine,session,team,agent,project,title,state,started) VALUES(?,?,?,?,?,?,?,'working',?)",(identifier,engine,session,payload['team'],payload['agent'],payload['project'],summary or 'งานของ '+payload['agent'],time.time()))
            job=current(db,engine,session)
    if job and event=='skill':
        skills=json.loads(job['skills'])
        if payload['skill'] not in skills: skills.append(payload['skill'])
        db.execute('UPDATE jobs SET skills=? WHERE id=?',(json.dumps(skills),job['id']))
    if job and event=='done':
        paid=db.execute('UPDATE treasury SET balance=balance-1 WHERE id=1 AND balance>0').rowcount
        db.execute("UPDATE jobs SET state='done',finished=?,coin=?,result=?,title=? WHERE id=?",(time.time(),paid,result,summary or job['title'],job['id']))
        db.execute('INSERT OR IGNORE INTO agent_accounts(team,agent) VALUES(?,?)',(job['team'],job['agent']))
        db.execute('UPDATE agent_accounts SET coins=coins+? WHERE team=? AND agent=?',(paid,job['team'],job['agent']))
    elif job and event=='failed':
        db.execute("UPDATE jobs SET state='failed',finished=?,result=?,review_state='skipped' WHERE id=?",(time.time(),result,job['id']))

def abandon(db,engine,session):
    db.execute("UPDATE jobs SET state='cancelled',finished=?,review_state='skipped' WHERE engine=? AND session=? AND state='working'",(time.time(),engine,session))

def rank(coins):
    levels=[(0,'Rookie','◇'),(5,'Bronze','◆'),(20,'Silver','✦'),(50,'Gold','★'),(100,'Diamond','♛')]
    threshold,name,badge=next(row for row in reversed(levels) if coins>=row[0])
    return {'name':name,'badge':badge,'level':sum(coins>=row[0] for row in levels),'next':next((row[0] for row in levels if row[0]>coins),None)}

def snapshot(workspace):
    import live_agents
    db=live_agents.connect(workspace)
    try:
        db.execute('BEGIN')
        balance=db.execute('SELECT balance FROM treasury WHERE id=1').fetchone()[0]
        accounts=[{**dict(row),'rank':rank(row['coins'])} for row in db.execute('SELECT * FROM agent_accounts')]
        jobs=[]
        # Pending reviews remain reachable even if many later jobs are completed.
        for row in db.execute("SELECT * FROM jobs WHERE state='done' ORDER BY (review_state='pending') DESC,finished DESC LIMIT 500"):
            item=dict(row);item['skills']=json.loads(item['skills']);jobs.append(item)
        pending=db.execute("SELECT count(*) FROM jobs WHERE state='done' AND review_state='pending'").fetchone()[0]
        return {'balance':balance,'initialBalance':86400,'accounts':accounts,'jobs':jobs,'pending':pending,'virtual':True}
    finally: db.close()

def review(workspace,payload):
    import live_agents
    identifier=payload.get('job');action=payload.get('action')
    if not isinstance(identifier,str) or action not in ('review','skip'): raise ValueError('Invalid review action')
    stars=payload.get('stars');comment=text(payload.get('comment',''),4000,'comment')
    if action=='review' and (type(stars)!=int or not 1<=stars<=5): raise ValueError('ให้ดาว 1–5 ดาว')
    db=live_agents.connect(workspace)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            job=db.execute('SELECT * FROM jobs WHERE id=?',(identifier,)).fetchone()
            if not job or job['state']!='done': raise ValueError('Review ได้เฉพาะงานที่สำเร็จ')
            if job['review_state']!='pending': raise ValueError('งานนี้ Review หรือข้ามแล้ว')
            db.execute('UPDATE jobs SET review_state=?,stars=?,comment=?,reviewed=? WHERE id=?',('reviewed' if action=='review' else 'skipped',stars if action=='review' else None,comment if action=='review' else '',time.time(),identifier))
            if action=='review':
                db.execute('INSERT OR IGNORE INTO agent_accounts(team,agent) VALUES(?,?)',(job['team'],job['agent']))
                db.execute('UPDATE agent_accounts SET rating=rating+? WHERE team=? AND agent=?',(stars,job['team'],job['agent']))
    finally: db.close()
    return snapshot(workspace)

def feedback(workspace,team,agent):
    import live_agents
    db=live_agents.connect(workspace)
    try:
        rows=db.execute("SELECT title,stars,comment,skills FROM jobs WHERE team=? AND agent=? AND review_state='reviewed' ORDER BY reviewed DESC LIMIT 12",(team,agent)).fetchall()
        return [{'task':r['title'],'stars':r['stars'],'comment':r['comment'],'skills':json.loads(r['skills'])} for r in rows]
    finally: db.close()
