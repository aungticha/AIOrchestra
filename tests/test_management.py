import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import server
import live_agents
import library_manager
import agent_skills

class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.original=server.DATA
        server.DATA=Path(self.tmp.name)/'workspace'
        server.create_team('test','Team','Description')
        for name in ('review','research'):
            server.write(server.document('test','skill',name),server.frontmatter(name,'Skill description','# '+name))
        self.agent=server.document('test','agent','writer')
        server.write(self.agent,server.frontmatter('writer','Write stuff','# writer\nSee skills/review/SKILL.md'))
        self.event={'engine':'Codex','session':'s1','team':'test','agent':'writer','project':str(Path(self.tmp.name))}

    def tearDown(self):
        server.DATA=self.original
        self.tmp.cleanup()

    def manage(self,kind,action,**kwargs):
        return library_manager.manage(server.DATA,{'team':'test','kind':kind,'action':action,**kwargs})

    def report(self,event): live_agents.report(server.DATA,{**self.event,'event':event})

    def test_shared_labels_and_explicit_bindings(self):
        item=server.state()['teams'][0]['agents'][0]
        self.assertEqual(item['skills'],['research','review'])
        self.assertEqual(item['skillMode'],'shared')
        self.manage('agent','skills',id='writer',skills=['review'])
        item=server.state()['teams'][0]['agents'][0]
        self.assertEqual(item['skills'],['review'])
        self.assertEqual(item['skillMode'],'assigned')
        self.assertIn('skills: ["review"]',item['content'])
        self.manage('agent','skills',id='writer',skills=[])
        self.assertEqual(server.state()['teams'][0]['agents'][0]['skills'],[])
        with self.assertRaises(ValueError): self.manage('agent','skills',id='writer',skills=['missing'])

    def test_skill_rename_and_delete_update_references_and_backups(self):
        self.manage('agent','skills',id='writer',skills=['review'])
        info=self.manage('skill','rename',id='review',name='fact-check')
        self.assertTrue((Path(info['archive'])/'before/skills/review/SKILL.md').is_file())
        self.assertEqual(agent_skills.assigned(self.agent.read_text()),['fact-check'])
        self.assertIn('skills/fact-check/SKILL.md',self.agent.read_text())
        self.assertIn('name: "fact-check"',server.document('test','skill','fact-check').read_text())
        self.assertFalse(server.document('test','skill','review').exists())
        info=self.manage('skill','delete',id='fact-check')
        self.assertEqual(agent_skills.assigned(self.agent.read_text()),[])
        self.assertNotIn('skills/fact-check/',self.agent.read_text())
        self.assertIsNone(info['archive'])
        self.assertFalse(server.document('test','skill','fact-check').exists())

    def test_team_display_rename_agent_rename_and_delete_team(self):
        self.manage('team','rename',name='ทีมชื่อใหม่')
        state=server.state()['teams'][0]
        self.assertEqual(state['id'],'test')
        self.assertTrue(state['overview'].startswith('# ทีมชื่อใหม่'))
        self.manage('agent','rename',id='writer',name='editor')
        self.assertFalse(self.agent.exists())
        self.assertIn('name: "editor"',server.document('test','agent','editor').read_text())
        self.manage('agent','delete',id='editor')
        self.assertEqual(server.state()['teams'][0]['agents'],[])
        info=self.manage('team','delete')
        self.assertEqual(server.state()['teams'],[])
        self.assertIsNone(info['archive'])

    def test_working_waiting_and_unknown_stay_locked_until_closed(self):
        self.report('selected')
        for status in ('working','waiting','unknown'):
            if status=='waiting': self.report('waiting')
            if status=='unknown':
                db=live_agents.connect(server.DATA)
                with db: db.execute('UPDATE runs SET updated_at=?',(time.time()-1000,))
                db.close()
            self.assertTrue(server.state()['teams'][0]['locked'])
            for kind,args in (('team',{}),('agent',{'id':'writer'}),('skill',{'id':'review'})):
                with self.assertRaises(library_manager.Locked): self.manage(kind,'delete',**args)
        live_agents.close_run(server.DATA,'Codex','s1')
        self.assertFalse(server.state()['teams'][0]['locked'])
        self.manage('agent','delete',id='writer')

    def test_cannot_close_fresh_working_session_or_use_unassigned_skill(self):
        self.manage('agent','skills',id='writer',skills=['review'])
        self.report('selected')
        with self.assertRaises(ValueError): live_agents.close_run(server.DATA,'Codex','s1')
        with self.assertRaises(ValueError): live_agents.report(server.DATA,{**self.event,'event':'skill','skill':'research'})
        self.report('done')
        self.manage('agent','delete',id='writer')

    def test_rollback_restores_files(self):
        before=self.agent.read_bytes()
        with patch('library_manager.write',side_effect=OSError('simulated failure')):
            with self.assertRaises(OSError): self.manage('agent','rename',id='writer',name='new-writer')
        self.assertEqual(self.agent.read_bytes(),before)
        self.assertFalse(server.document('test','agent','new-writer').exists())

    def test_skills_yaml_block_and_inline(self):
        body='---\nname: writer\ndescription: write\nskills:\n  - review\n  - research\nrouting_mode: auto\n---\n# Body'
        self.assertEqual(agent_skills.assigned(body),['review','research'])
        updated=agent_skills.set_assigned(body,['research'])
        self.assertEqual(agent_skills.assigned(updated),['research'])
        self.assertIn('routing_mode: auto',updated)
        self.assertIn('# Body',updated)
        self.assertEqual(agent_skills.assigned(body.replace('skills:\n  - review\n  - research','skills: [review, research]')),['review','research'])

    def test_permanent_deletes_never_create_backup(self):
        self.manage('skill','delete',id='review')
        self.assertFalse((server.DATA/'.trash').exists())
        self.manage('agent','delete',id='writer')
        self.assertFalse((server.DATA/'.trash').exists())
        self.manage('team','delete')
        self.assertFalse((server.DATA/'.trash').exists())
        self.assertFalse(server.teamdir('test').exists())

    def test_description_create_edit_legacy_and_export(self):
        state=server.state()['teams'][0]
        self.assertEqual(state['description'],'Description')
        before=state['overview'].split('## เป้าหมาย',1)[1]
        self.manage('team','description',description='คำอธิบายทีม\nบรรทัดที่สอง')
        state=server.state()['teams'][0]
        self.assertEqual(state['description'],'คำอธิบายทีม\nบรรทัดที่สอง')
        self.assertEqual(state['overview'].split('## เป้าหมาย',1)[1],before)
        self.assertEqual(json.loads((server.teamdir('test')/'TEAM.json').read_text())['description'],state['description'])
        self.assertIn(state['description'],server.export_files('test','codex')['AGENTS.md'])
        self.manage('team','description',description='')
        self.assertEqual(server.state()['teams'][0]['description'],'')
        server.write(server.teamdir('test')/'README.md','# Legacy\n\nOld description\n\n## Rules\nKeep this')
        self.assertEqual(server.state()['teams'][0]['description'],'Old description')
        self.manage('team','description',description='New legacy description')
        self.assertIn('## Rules\nKeep this',server.state()['teams'][0]['overview'])
        self.report('selected')
        with self.assertRaises(library_manager.Locked): self.manage('team','description',description='Blocked')

    def test_agent_display_name_role_and_description(self):
        item=server.state()['teams'][0]['agents'][0]
        self.assertEqual(item['displayName'],'writer')
        self.assertEqual(item['role'],'Write stuff')
        self.manage('agent','skills',id='writer',skills=['review'])
        self.manage('agent','profile',id='writer',displayName='ไอซ์',role='Developer',description='ใช้เมื่อต้องเขียนโค้ดหรือแก้บั๊ก')
        item=server.state()['teams'][0]['agents'][0]
        self.assertEqual(item['displayName'],'ไอซ์')
        self.assertEqual(item['role'],'Developer')
        self.assertEqual(item['description'],'ใช้เมื่อต้องเขียนโค้ดหรือแก้บั๊ก')
        self.assertEqual(item['id'],'writer')
        self.assertEqual(item['skills'],['review'])
        self.assertIn('# writer',item['content'])
        self.assertIn('display_name: "ไอซ์"',server.export_files('test','claude')['.claude/agents/writer.md'])
        self.report('selected')
        with self.assertRaises(library_manager.Locked): self.manage('agent','profile',id='writer',displayName='Changed',role='Editor',description='Blocked')
        self.report('done')
        self.manage('agent','rename',id='writer',name='coder')
        renamed=server.state()['teams'][0]['agents'][0]
        self.assertEqual(renamed['displayName'],'ไอซ์')
        self.assertEqual(renamed['role'],'Developer')
        self.assertEqual(renamed['id'],'coder')

    def test_profile_invalid_fields_do_not_modify_file(self):
        before=self.agent.read_bytes()
        for name,role,description in (('', 'Developer','Use coding'),('Ice','','Use coding'),('Ice','Developer',''),('Ice\nNew','Developer','Use coding')):
            with self.assertRaises(ValueError): self.manage('agent','profile',id='writer',displayName=name,role=role,description=description)
            self.assertEqual(self.agent.read_bytes(),before)

    def test_http_locked_mutation_and_save_rejected(self):
        self.report('selected')
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{http.server_port}'
        def post(route,payload):
            return urlopen(Request(base+route,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'}))
        try:
            for route,payload in (('/api/library/manage',{'team':'test','kind':'team','action':'delete'}),('/api/save',{'team':'test','kind':'agent','id':'writer','content':self.agent.read_text()})):
                with self.assertRaises(HTTPError) as error: post(route,payload)
                self.assertEqual(error.exception.code,409)
            self.report('done')
            with post('/api/library/manage',{'team':'test','kind':'agent','action':'skills','id':'writer','skills':['review']}) as response:
                self.assertEqual(json.load(response)['state']['teams'][0]['agents'][0]['skills'],['review'])
        finally:
            http.shutdown();http.server_close();thread.join()

if __name__=='__main__': unittest.main()
