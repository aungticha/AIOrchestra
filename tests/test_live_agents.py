import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import urlopen
import live_agents
import report_agent
import server
import codex_setup

class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.workspace=self.root/'workspace'
        agent=self.workspace/'teams/developer/agents/software-engineer.md'
        agent.parent.mkdir(parents=True)
        agent.write_text('---\nname: software-engineer\ndescription: Build software\n---\n')
        skill=self.workspace/'teams/developer/skills/implementation-review/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('# Review')
        self.base={'engine':'Codex','session':'session-1','team':'developer','agent':'software-engineer','project':str(self.root/'shop-app')}

    def tearDown(self):
        self.temp.cleanup()

    def event(self,event,**kwargs):
        return live_agents.report(self.workspace,{**self.base,'event':event,**kwargs})

    def test_lifecycle_active_skill_and_finish(self):
        self.event('selected')
        self.event('skill',skill='implementation-review')
        snap=live_agents.snapshot(self.workspace)
        self.assertEqual(snap['activeTeams'],{'developer':1})
        self.assertEqual(snap['runs'][0]['project'],'shop-app')
        self.assertEqual(snap['events'][0]['skill'],'implementation-review')
        self.event('waiting')
        self.assertEqual(live_agents.snapshot(self.workspace)['activeTeams'],{})
        self.event('working')
        self.event('done')
        self.assertEqual(live_agents.snapshot(self.workspace)['runs'][0]['status'],'done')
        self.assertEqual(live_agents.snapshot(self.workspace)['activeTeams'],{})
        with self.assertRaises(ValueError): self.event('heartbeat')

    def test_heartbeat_expires_and_does_not_fill_activity(self):
        with patch('live_agents.time.time',return_value=1000):
            self.event('selected')
        with patch('live_agents.time.time',return_value=1181):
            self.assertEqual(live_agents.snapshot(self.workspace)['runs'][0]['status'],'unknown')
            self.assertEqual(live_agents.snapshot(self.workspace)['activeTeams'],{})
            self.event('heartbeat')
            snap=live_agents.snapshot(self.workspace)
            self.assertEqual(snap['activeTeams'],{'developer':1})
            self.assertEqual(len(snap['events']),1)

    def test_sessions_and_engines_do_not_overwrite_each_other(self):
        self.event('selected')
        self.event('selected',engine='Claude')
        self.event('selected',session='second',project=str(self.root/'launch'))
        self.event('done',engine='Claude')
        snap=live_agents.snapshot(self.workspace)
        self.assertEqual(len(snap['runs']),3)
        self.assertEqual(snap['activeTeams'],{'developer':2})
        self.assertEqual({r['project'] for r in snap['runs']},{'shop-app','launch'})

    def test_validation_and_reported_data_allowlist(self):
        with self.assertRaises(ValueError): self.event('working')
        for overrides in ({'team':'../secret'},{'agent':'missing'},{'project':'relative'},{'engine':'unknown'},{'session':'bad/session'}):
            with self.assertRaises(ValueError): self.event('selected',**overrides)
        self.event('selected',apiKey='never-store-secret',prompt='never-store-prompt')
        with self.assertRaises(ValueError): self.event('skill',skill='missing')
        with self.assertRaises(ValueError): self.event('done',project=str(self.root/'other'))
        payload=json.dumps(live_agents.snapshot(self.workspace))
        self.assertNotIn('never-store-secret',payload)
        self.assertNotIn('never-store-prompt',payload)

    def test_report_cli_and_setup_instructions(self):
        output=io.StringIO()
        args=['--workspace',str(self.workspace),'--engine','Claude','--team','developer','--agent','software-engineer','--project',str(self.root),'--event','selected']
        with contextlib.redirect_stdout(output):
            self.assertEqual(report_agent.main(args),0)
        session=json.loads(output.getvalue())['session']
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(report_agent.main(args[:-1]+['done','--session',session]),0)
        for client,engine in (('codex','Codex'),('claude','Claude')):
            block=codex_setup.instruction_block(self.workspace/'teams',client)
            self.assertIn('--engine '+engine,block)
            self.assertIn('report_agent.py',block)
            self.assertIn('--event skill --skill',block)

    def test_http_snapshot_reads_cli_reports(self):
        self.event('selected')
        original=server.DATA
        server.DATA=self.workspace
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        worker=threading.Thread(target=http.serve_forever,daemon=True)
        worker.start()
        try:
            with urlopen(f'http://127.0.0.1:{http.server_port}/api/live') as response:
                result=json.load(response)
            self.assertEqual(result['runs'][0]['agent'],'software-engineer')
            self.assertEqual(result['activeTeams'],{'developer':1})
        finally:
            http.shutdown();http.server_close();worker.join();server.DATA=original

if __name__=='__main__': unittest.main()
