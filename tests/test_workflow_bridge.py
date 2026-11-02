import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import codex_setup
import server
import workflow
import workflow_bridge
import workflow_discovery
import workflow_runner
import workflow_setup
from test_workflow import FakeRunner

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.workspace=self.root/'workspace';self.project=self.root/'project';self.project.mkdir()
        for args in [('init',),('config','user.name','Bridge Test'),('config','user.email','bridge@example.invalid')]:subprocess.run(['git','-C',str(self.project),*args],check=True,capture_output=True)
        (self.project/'initial.txt').write_text('original')
        for args in [('add','.'),('commit','-m','initial')]:subprocess.run(['git','-C',str(self.project),*args],check=True,capture_output=True)
        self.old_data=server.DATA;self.old_engine=workflow.engine;server.DATA=self.workspace;workflow.engine=workflow.Engine(FakeRunner())
        server.create_team('developer','Development','Bridge fixture')
        for role in workflow_runner.ROLES:server.write(server.document('developer','agent',role),server.frontmatter(role,'Fixture','# Fixture'))
        self.patch=patch('terminal_runtime.executable',return_value=sys.executable);self.patch.start()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.http.instance_id='bridge-test'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        workflow_discovery.write(self.workspace,self.http.server_port,self.http.instance_id)
        self.bridge=workflow_bridge.Bridge(self.workspace)
    def tearDown(self):
        workflow.engine.shutdown();self.http.shutdown();self.http.server_close();self.thread.join();workflow.engine=self.old_engine;server.DATA=self.old_data;self.patch.stop();self.temp.cleanup()
    def start(self,**extra):return self.bridge.run({'action':'start','project':str(self.project),'task':'Build feature','request_id':'request-bridge-fixture',**extra})
    def wait(self,identifier,state):
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            result=self.bridge.run({'action':'status','id':identifier})
            if result['state']==state:return result
            if result['state']=='failed':self.fail(result['error'])
            time.sleep(.05)
        self.fail('Did not reach '+state)
    def test_chat_start_gates_approval_and_status(self):
        run=self.start();ready=self.wait(run['id'],'awaiting_plan');approval=ready['approval']
        self.assertFalse(approval['user_confirmed']);self.assertEqual(approval['gate'],1)
        with self.assertRaises(ValueError):self.bridge.run({'action':'approve',**approval})
        with self.assertRaises(ValueError):self.bridge.run({'action':'approve',**approval,'user_confirmed':True,'gate':2})
        self.bridge.run({'action':'approve',**approval,'user_confirmed':True})
        delivery=self.wait(run['id'],'awaiting_delivery');self.assertEqual(delivery['approval']['gate'],2);self.assertIn('diff',delivery)
        self.bridge.run({'action':'approve',**delivery['approval'],'user_confirmed':True});self.wait(run['id'],'completed')
    def test_submission_idempotency_and_stale_revision(self):
        first=self.start();second=self.start();self.assertEqual(first['id'],second['id'])
        with self.assertRaises(ValueError):self.start(task='different task')
        ready=self.wait(first['id'],'awaiting_plan')
        with self.assertRaises(ValueError):self.bridge.run({'action':'approve',**ready['approval'],'revision':0,'user_confirmed':True})
    def test_wrong_workspace_or_server_instance_rejected(self):
        other=workflow_bridge.Bridge(self.root/'different',self.bridge.url)
        with self.assertRaises(ValueError):other.run({'action':'health'})
        self.bridge.expected_instance='wrong'
        with self.assertRaises(ValueError):self.bridge.run({'action':'health'})
    def test_loopback_only_and_worker_recursion_guard(self):
        for url in ('https://127.0.0.1:4310','http://example.com','http://localhost@evil.example','http://127.0.0.1:4310/path'):
            with self.assertRaises(ValueError):workflow_bridge.Bridge(self.workspace,url)
        with patch.dict(os.environ,{'AIORCHESTRA_WORKFLOW_WORKER':'1'}):
            with self.assertRaises(ValueError):self.start()
    def test_real_bridge_script_health(self):
        command=[sys.executable,str(Path(workflow_bridge.__file__)),'--workspace',str(self.workspace)]
        result=subprocess.run(command,input=json.dumps({'action':'health'}),text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout);self.assertTrue(json.loads(result.stdout)['ok'])
    def test_setup_installs_skill_preserves_unrelated_text(self):
        home=self.root/'codex-home';home.mkdir();(home/'AGENTS.md').write_text('# My instructions\nKeep this.\n')
        with patch.dict(os.environ,{'CODEX_HOME':str(home)}):
            before=codex_setup.preview(self.workspace/'teams');installed=codex_setup.install(self.workspace/'teams',None,before['revision'])
            content=Path(installed['workflowSkillPath']).read_text();self.assertIn(str(Path(workflow_bridge.__file__).resolve()),content);self.assertNotIn('__COMMAND__',content)
            self.assertTrue((home/'AGENTS.md').read_text().startswith('# My instructions\nKeep this.\n'))
            again=codex_setup.install(self.workspace/'teams',None,installed['revision']);self.assertFalse(again['updated'])
    def test_unmanaged_skill_never_overwritten(self):
        home=self.root/'custom';skill=home/'skills/aiorchestra-workflow/SKILL.md';skill.parent.mkdir(parents=True);skill.write_text('User skill')
        with self.assertRaises(ValueError):codex_setup.preview(self.workspace/'teams',str(home))
        self.assertEqual(skill.read_text(),'User skill')
