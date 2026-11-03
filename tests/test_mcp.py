import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import agent_jobs
import mcp_setup
import server
import workflow_bridge
from urllib.error import URLError


def result(**changes):
    return dict(summary='Fixture finished',details='Fixture evidence',passed=True,blocked=False,findings=[],tests=['fake check'],**changes)


class FakeRunner:
    def __init__(self):self.calls=[];self.stop_event=threading.Event();self.hold=False
    def execute(self,record,role,cwd,prompt,folder,log):
        self.calls.append(record);log('fixture log\n')
        if self.hold:self.stop_event.wait(5)
        return result()
    def stop(self,identifier):self.stop_event.set()


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.workspace=self.root/'workspace';self.project=self.root/'project';self.project.mkdir();self.old=server.DATA;server.DATA=self.workspace
        server.create_team('editor','Editorial','Fixture')
        server.write(server.document('editor','agent','writer'),server.frontmatter('writer','Writer','# Fixture'))
        self.runner=FakeRunner();self.manager=agent_jobs.Manager(self.runner)
        self.patch=patch('terminal_runtime.executable',return_value='/fixture/cli');self.patch.start()
        self.payload=dict(team='editor',agent='writer',project=str(self.project),task='Inspect fixture',request_id='request-agent-1234')
    def tearDown(self):self.manager.shutdown();self.patch.stop();server.DATA=self.old;self.tmp.cleanup()
    def wait(self,job):
        for _ in range(200):
            current=self.manager.get(self.workspace,job['id'])
            if current['state'] in agent_jobs.TERMINAL:return current
            time.sleep(.01)
        self.fail('Job did not end')
    def test_direct_job_idempotency_result_and_no_workflow(self):
        job=self.manager.start(self.workspace,self.payload);done=self.wait(job)
        self.assertEqual(done['state'],'completed');self.assertIn('fixture log',done['log'])
        self.assertEqual(self.manager.start(self.workspace,self.payload)['id'],job['id']);self.assertEqual(len(self.runner.calls),1)
        self.assertEqual(self.runner.calls[0]['access'],'read-only')
        with self.assertRaises(ValueError):self.manager.start(self.workspace,{**self.payload,'task':'Changed'})
    def test_cancel_never_becomes_completed(self):
        self.runner.hold=True;job=self.manager.start(self.workspace,self.payload)
        while not self.runner.calls:time.sleep(.01)
        self.manager.cancel(self.workspace,job['id']);self.manager.shutdown()
        self.assertEqual(self.manager.get(self.workspace,job['id'])['state'],'cancelled')
        self.assertTrue(self.manager.get(self.workspace,job['id'])['dismissed'])
    def test_interrupted_after_restart(self):
        self.runner.hold=True;job=self.manager.start(self.workspace,self.payload)
        restored=agent_jobs.Manager(FakeRunner()).get(self.workspace,job['id'])
        self.assertEqual(restored['state'],'interrupted')
        self.manager.cancel(self.workspace,job['id'])
    def test_worker_cannot_spawn(self):
        with patch.dict('os.environ',{'AIORCHESTRA_DIRECT_AGENT':'1'}):
            with self.assertRaises(ValueError):self.manager.start(self.workspace,self.payload)
    def test_private_context_not_returned(self):
        job=self.manager.start(self.workspace,self.payload)
        self.assertNotIn('contexts',job);self.assertNotIn('result_schema',job);self.wait(job)


class SetupTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
    def tearDown(self):self.tmp.cleanup()
    def test_codex_preserves_config_idempotently_and_checks_revision(self):
        path=self.root/'config.toml';path.write_text('model = "custom"\n[mcp_servers.other]\ncommand = "other"\n')
        info=mcp_setup.preview(self.root,'codex',str(path));installed=mcp_setup.install(self.root,'codex',str(path),info['revision'])
        self.assertIn('model = "custom"',path.read_text());self.assertIn('[mcp_servers.other]',path.read_text())
        again=mcp_setup.install(self.root,'codex',str(path),installed['revision']);self.assertFalse(again['updated'])
        path.write_text(path.read_text()+'\n# user change\n')
        with self.assertRaises(ValueError):mcp_setup.install(self.root,'codex',str(path),again['revision'])
    def test_json_preserves_other_mcp_servers(self):
        for client in ('claude','claude-desktop'):
            path=self.root/(client+'.json');path.write_text(json.dumps({'custom':1,'mcpServers':{'other':{'command':'other'}}}))
            info=mcp_setup.preview(self.root,client,str(path));mcp_setup.install(self.root,client,str(path),info['revision'])
            value=json.loads(path.read_text());self.assertEqual(value['custom'],1);self.assertIn('other',value['mcpServers']);self.assertIn('aiorchestra',value['mcpServers'])
    def test_unmanaged_entry_never_overwritten(self):
        path=self.root/'config.toml';path.write_text('[mcp_servers.aiorchestra]\ncommand = "mine"\n')
        with self.assertRaises(ValueError):mcp_setup.preview(self.root,'codex',str(path))
    def test_permission_error_is_not_reported_as_server_down(self):
        bridge=workflow_bridge.Bridge(self.root)
        with patch.object(bridge.opener,'open',side_effect=URLError(PermissionError(1,'denied'))):
            with self.assertRaisesRegex(ValueError,'sandbox'):bridge.health()

class McpIntegrationTests(unittest.TestCase):
    def setUp(self):
        import sys
        import workflow_discovery
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.workspace=self.root/'workspace';self.project=self.root/'project';self.project.mkdir()
        self.old=server.DATA;server.DATA=self.workspace
        server.create_team('editor','Editorial','Fixture');server.write(server.document('editor','agent','writer'),server.frontmatter('writer','Writer','# Fixture'))
        self.old_manager=agent_jobs.manager;agent_jobs.manager=agent_jobs.Manager(FakeRunner())
        self.patch=patch('terminal_runtime.executable',return_value=sys.executable);self.patch.start()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.http.instance_id='mcp-fixture'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();workflow_discovery.write(self.workspace,self.http.server_port,self.http.instance_id)
    def tearDown(self):
        agent_jobs.manager.shutdown();self.http.shutdown();self.http.server_close();self.thread.join();agent_jobs.manager=self.old_manager;self.patch.stop();server.DATA=self.old;self.tmp.cleanup()
    def test_real_stdio_tools_and_direct_job(self):
        import asyncio
        import sys
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        async def exercise():
            parameters=StdioServerParameters(command=sys.executable,args=[str(Path(server.__file__).parent/'orchestra_mcp.py'),'--workspace',str(self.workspace)])
            async with stdio_client(parameters) as (reader,writer):
                async with ClientSession(reader,writer) as session:
                    await session.initialize();tools=await session.list_tools()
                    self.assertIn('start_workflow',[t.name for t in tools.tools]);self.assertIn('report_agent',[t.name for t in tools.tools])
                    for tool,args in [('health',{}),('list_agents',{}),('get_agent_context',dict(team='editor',agent='writer'))]:
                        value=await session.call_tool(tool,args);self.assertFalse(value.isError,str(value.content))
                    started=await session.call_tool('start_agent',dict(team='editor',agent='writer',project=str(self.project),task='Inspect fixture',request_id='mcp-job-123456'))
                    self.assertFalse(started.isError,str(started.content));job=json.loads(started.content[0].text)
                    for _ in range(100):
                        response=await session.call_tool('get_agent_job',dict(id=job['id']));value=json.loads(response.content[0].text)
                        if value['state'] in agent_jobs.TERMINAL:break
                        await asyncio.sleep(.02)
                    self.assertEqual(value['state'],'completed');self.assertNotIn('contexts',value)
                    closed=await session.call_tool('cancel_agent_job',dict(id=job['id']));self.assertFalse(closed.isError)
        asyncio.run(exercise())
