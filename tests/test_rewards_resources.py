import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
import agent_skills
import live_agents
import library_manager
import rewards
import server
import team_resources

class RewardsResourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=server.DATA;server.DATA=Path(self.tmp.name)/'workspace'
        server.create_team('team','Team','Test')
        server.write(server.document('team','agent','editor'),server.frontmatter('editor','Edit','# Editor'))
        server.write(server.document('team','skill','review'),server.frontmatter('review','Review','# Review'))
        self.base={'engine':'Codex','session':'job1','team':'team','agent':'editor','project':self.tmp.name}
    def tearDown(self): server.DATA=self.old;self.tmp.cleanup()
    def report(self,event,**extra): return live_agents.report(server.DATA,{**self.base,'event':event,**extra})
    def complete(self):
        self.report('selected',summary='Edit landing page');self.report('skill',skill='review');self.report('done',result='Revised copy and verified spelling')
        return rewards.snapshot(server.DATA)['jobs'][0]
    def test_coin_once_and_persists_with_rank(self):
        self.assertEqual(rewards.snapshot(server.DATA)['balance'],86400)
        job=self.complete();self.report('done');self.report('selected');self.report('done')
        result=rewards.snapshot(Path(str(server.DATA)))
        self.assertEqual(result['balance'],86399);self.assertEqual(len(result['jobs']),1)
        self.assertEqual(result['accounts'][0]['coins'],1);self.assertEqual(job['skills'],['review'])
        self.assertEqual(rewards.rank(5)['name'],'Bronze');self.assertEqual(rewards.rank(100)['name'],'Diamond')
    def test_rating_review_skip_and_feedback(self):
        job=self.complete()
        with self.assertRaises(ValueError): rewards.review(server.DATA,{'job':job['id'],'action':'review','stars':True})
        result=rewards.review(server.DATA,{'job':job['id'],'action':'review','stars':4,'comment':'Check punctuation in review Skill'})
        self.assertEqual(result['accounts'][0]['rating'],4);self.assertEqual(result['balance'],86399)
        self.assertEqual(rewards.feedback(server.DATA,'team','editor')[0]['skills'],['review'])
        with self.assertRaises(ValueError): rewards.review(server.DATA,{'job':job['id'],'action':'review','stars':5})
        self.base['session']='job2';job=self.complete()
        result=rewards.review(server.DATA,{'job':job['id'],'action':'skip'})
        self.assertEqual(result['accounts'][0]['rating'],4);self.assertEqual(result['pending'],0)
    def test_cancelled_failed_and_deferred_jobs_never_pay(self):
        self.report('selected',deferJob=True);self.report('waiting');live_agents.close_run(server.DATA,'Codex','job1')
        self.base['session']='job2';self.report('selected');self.report('failed')
        self.assertEqual(rewards.snapshot(server.DATA)['balance'],86400)
        self.base['session']='job3';self.report('selected');self.report('waiting');live_agents.close_run(server.DATA,'Codex','job3')
        self.assertEqual(rewards.snapshot(server.DATA)['jobs'],[])
    def test_managed_multi_task_keeps_lock_and_pays_per_done(self):
        self.report('selected',deferJob=True)
        db=live_agents.connect(server.DATA)
        with db: db.execute('INSERT INTO managed_runs VALUES(?,?,1)',('Codex','job1'))
        db.close()
        for index in range(2):
            self.report('working',summary='Task '+str(index));self.report('done',result='Delivered');self.report('done')
            self.assertEqual(live_agents.snapshot(server.DATA)['lockedTeams'],['team'])
        result=rewards.snapshot(server.DATA)
        self.assertEqual(result['balance'],86398);self.assertEqual(len(result['jobs']),2)
    def test_concurrent_completion_no_double_payment_or_overdraft(self):
        self.report('selected')
        errors=[]
        def finish():
            try: self.report('done')
            except Exception as e: errors.append(e)
        threads=[threading.Thread(target=finish) for _ in range(8)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(errors,[]);self.assertEqual(rewards.snapshot(server.DATA)['balance'],86399)
        db=live_agents.connect(server.DATA)
        with db:db.execute('UPDATE treasury SET balance=0')
        db.close();self.base['session']='job2';self.complete()
        result=rewards.snapshot(server.DATA)
        self.assertEqual(result['balance'],0);self.assertEqual(result['accounts'][0]['coins'],1)
    def upload(self,name='sample.txt',content=b'reference'):
        return team_resources.upload(server.DATA,{'team':'team','name':name,'description':'Editor sample','data':base64.b64encode(content).decode()})
    def test_resource_roundtrip_index_and_delete_lock(self):
        result=self.upload();item=result['items'][0]
        metadata,path=team_resources.fetch(server.DATA,item['id'])
        self.assertEqual(path.read_bytes(),b'reference');self.assertEqual(metadata['description'],'Editor sample')
        self.assertIn(item['filename'],(path.parent/'RESOURCES.md').read_text())
        self.report('selected')
        with self.assertRaises(library_manager.Locked):team_resources.delete(server.DATA,{'id':item['id']})
        self.report('done');team_resources.delete(server.DATA,{'id':item['id']})
        self.assertFalse(path.exists());self.assertEqual(team_resources.listing(server.DATA,'team')['items'],[])
    def test_resource_path_type_and_size_validation(self):
        for name in ('../a.txt','C:\\a.txt','x.html','x.svg','x.exe'):
            with self.assertRaises(ValueError):self.upload(name)
        with self.assertRaises(ValueError):self.upload('fake.png')
        with self.assertRaises(ValueError):team_resources.fetch(server.DATA,'../runtime/activity.sqlite3')
        with self.assertRaises(ValueError):team_resources.upload(server.DATA,{'team':'team','name':'a.txt','data':'%notbase64'})
    def test_agent_rename_preserves_rewards_and_reviews(self):
        job=self.complete();rewards.review(server.DATA,{'job':job['id'],'action':'review','stars':5})
        library_manager.manage(server.DATA,{'team':'team','kind':'agent','id':'editor','action':'rename','name':'copy-editor'})
        result=rewards.snapshot(server.DATA)
        self.assertEqual(result['accounts'][0]['agent'],'copy-editor');self.assertEqual(result['accounts'][0]['rating'],5)
        self.assertEqual(result['jobs'][0]['agent'],'copy-editor')

    def test_http_resource_headers_and_review_origin(self):
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(http.server_port)
        def post(route,payload,origin=None):
            headers={'Content-Type':'application/json'}
            if origin: headers['Origin']=origin
            return urlopen(Request(base+route,data=json.dumps(payload).encode(),headers=headers),timeout=5)
        try:
            with post('/api/resources/upload',{'team':'team','name':'ref.txt','data':base64.b64encode(b'reference').decode()}) as response:
                item=json.load(response)['items'][0]
            with urlopen(base+'/api/resources/file?id='+item['id']+'&preview=1') as response:
                self.assertEqual(response.headers['Content-Type'],'application/octet-stream')
                self.assertIn('attachment',response.headers['Content-Disposition']);self.assertEqual(response.read(),b'reference')
            with self.assertRaises(HTTPError) as error:
                post('/api/rewards/review',{'job':'fake','action':'review','stars':5},'https://example.com')
            self.assertEqual(error.exception.code,403)
            with urlopen(base+'/api/rewards') as response:self.assertEqual(json.load(response)['balance'],86400)
        finally: http.shutdown();http.server_close();thread.join()
