import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import agent_appearance
import live_agents
import library_manager
import server
import terminal_runtime as runtime

class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=server.DATA;server.DATA=Path(self.tmp.name)/'workspace'
        server.create_team('test','Test','Test')
        server.write(server.document('test','agent','tester'),server.frontmatter('tester','Test software','# Tester'))
        self.payload={'engine':'Codex','team':'test','agent':'tester','project':self.tmp.name,'model':''}
        self.sessions=[]
    def tearDown(self):
        for s in self.sessions: s.close()
        server.DATA=self.old;self.tmp.cleanup()
    def launch(self,code):
        session=runtime.Session(server.DATA,self.payload,command=[sys.executable,'-u','-c',code]);self.sessions.append(session);return session
    def wait(self,predicate):
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            if predicate(): return
            time.sleep(.03)
        self.fail('Timed out waiting for PTY')
    def test_appearance_roundtrip_and_validation(self):
        content=server.document('test','agent','tester').read_text()
        value={**agent_appearance.DEFAULT,'hairStyle':'long','shirtColor':'#17bbcc','gender':'female'}
        changed=agent_appearance.set_value(content,value)
        self.assertEqual(agent_appearance.get(changed),value)
        server.validate(changed,'agent','tester')
        self.assertIn('# Tester',changed)
        with self.assertRaises(ValueError): agent_appearance.validate({'hairColor':'url(x)'})
        with self.assertRaises(ValueError): agent_appearance.validate({'gender':'invalid'})
    def test_rejects_invalid_project_model_and_size(self):
        for change in ({'project':'relative'},{'model':'--evil'},{'cols':99999}):
            with self.assertRaises(ValueError): runtime.Session(server.DATA,{**self.payload,**change},command=[sys.executable])
        self.assertEqual(live_agents.snapshot(server.DATA)['runs'],[])
    @unittest.skipIf(os.name=='nt','POSIX PTY integration; Windows tested by the separate ConPTY test')
    def test_interactive_input_resize_close_and_lock(self):
        s=self.launch("import sys,time,os; print('READY',os.isatty(0),flush=True); print('ECHO:'+input(),flush=True); time.sleep(60)")
        self.wait(lambda:'READY True' in s.read(0)['output'])
        self.assertEqual(live_agents.snapshot(server.DATA)['lockedTeams'],['test'])
        with self.assertRaises(library_manager.Locked): library_manager.manage(server.DATA,{'team':'test','kind':'agent','id':'tester','action':'delete'})
        with self.assertRaises(ValueError): live_agents.close_run(server.DATA,'Codex',s.id)
        live_agents.report(server.DATA,{**s.payload,'event':'done'})
        self.assertEqual(live_agents.snapshot(server.DATA)['lockedTeams'],['test'])
        s.resize(111,28);s.input('สวัสดี\r')
        self.wait(lambda:'ECHO:สวัสดี' in s.read(0)['output'])
        s.close();self.wait(lambda:not s.alive)
        self.assertEqual(live_agents.snapshot(server.DATA)['lockedTeams'],[])
        self.assertEqual(live_agents.snapshot(server.DATA)['runs'][0]['status'],'closed')
    @unittest.skipUnless(os.name=='nt','Windows only')
    def test_conpty_interaction(self):
        s=self.launch("import time; print('READY',flush=True); print('ECHO:'+input(),flush=True); time.sleep(60)")
        self.wait(lambda:'READY' in s.read(0)['output']);s.resize(100,25);s.input('hello\r\n')
        self.wait(lambda:'ECHO:hello' in s.read(0)['output']);s.close()
        self.assertEqual(live_agents.snapshot(server.DATA)['lockedTeams'],[])
    def test_bounded_buffer_cursor_and_explicit_failure(self):
        s=self.launch("print('COMPLETE',flush=True)")
        self.wait(lambda:not s.alive)
        self.assertIn('COMPLETE',s.read(0)['output'])
        self.assertEqual(live_agents.snapshot(server.DATA)['lockedTeams'],[])
        s.append('x'*1_100_000);r=s.read(0)
        self.assertTrue(r['truncated']);self.assertEqual(len(s.text),1_000_000)
        self.assertEqual(len(r['output']),65536)
        with self.assertRaises(ValueError): s.read(-1)
    @unittest.skipIf(os.name=='nt','POSIX helper exec failure')
    def test_spawn_failure_unlocks(self):
        s=runtime.Session(server.DATA,self.payload,command=['/missing/orchestra-cli']);self.sessions.append(s)
        self.wait(lambda:not s.alive)
        self.wait(lambda:not live_agents.snapshot(server.DATA)['lockedTeams'])
        self.assertEqual(live_agents.snapshot(server.DATA)['runs'][0]['status'],'failed')
