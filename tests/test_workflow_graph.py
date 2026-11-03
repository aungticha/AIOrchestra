import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import agent_skills
import server
import workflow
import workflow_media as media
import workflow_templates as templates


def result(**extra):
    return {'summary':'Fixture stage','details':'Fixture evidence, not real video inspection','passed':True,'blocked':False,'findings':[],'tests':['fixture check'],'references':[],'storyboard':'','artifacts':[],**extra}

class MediaRunner:
    def __init__(self):
        self.calls=[];self.active=0;self.overlap=0;self.lock=threading.Lock();self.qa_failures=0;self.hold=False;self.stopped=threading.Event()
    def restart(self,identifier):self.stopped.clear()
    def stop(self,identifier):self.stopped.set()
    def execute(self,record,key,cwd,prompt,folder,log):
        self.calls.append(key);log('fixture '+key+'\n')
        node=next(n for n in record['graph']['nodes'] if n['id']==key)
        if self.hold:
            while not self.stopped.wait(.01):pass
            raise InterruptedError('fixture cancelled')
        if node['phase']=='plan':
            return result(references=[{'url':'https://example.com/reference','title':'Fixture reference','evidence':'Synthetic fixture observation','inspected':True}],storyboard='00:00–00:02: fixture shot -> original scene')
        output=Path(record['output_root'])/key
        if node['phase']=='work':
            with self.lock:self.active+=1;self.overlap=max(self.overlap,self.active)
            time.sleep(.06)
            path=output/'preview.mp4';path.write_bytes(b'fixture only, not a real video')
            with self.lock:self.active-=1
            return result(artifacts=[{'path':str(path),'kind':'preview'}])
        if node['phase']=='review' and self.qa_failures:
            self.qa_failures-=1;return result(passed=False,findings=['Fixture correction needed'])
        if node['phase']=='export':
            path=output/'final.mp4';path.write_bytes(b'fixture final, not a real video')
            return result(artifacts=[{'path':str(path),'kind':'final'}])
        return result()

class GraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.workspace=self.root/'workspace';self.project=self.root/'project';self.project.mkdir()
        self.original=server.DATA;server.DATA=self.workspace
        server.create_team('editor','Editorial','Video')
        for role in templates.EDITORIAL:
            server.write(server.document('editor','agent',role),server.frontmatter(role,role,'# Fixture profile'))
        self.runner=MediaRunner();self.engine=workflow.Engine(self.runner)
        self.patch=patch('terminal_runtime.executable',return_value='/fixture/cli');self.patch.start()
    def tearDown(self):
        self.runner.stopped.set();self.engine.shutdown();self.patch.stop();server.DATA=self.original;self.tmp.cleanup()
    def test_single_connected_provider_routes_every_role_without_changing_template(self):
        graph=templates.defaults(self.workspace,'editor')
        for node in graph['nodes']:
            if 'agent' in node:node.update(engine='Claude',model='sonnet')
        original=copy.deepcopy(graph)
        with patch('provider_routing.connections',return_value={'Codex':True,'Claude':False}):
            run=self.create(graph)
        self.assertTrue(all(role['engine']=='Codex' and role['model']=='' for role in run['roles'].values()))
        self.assertEqual(graph,original)
        self.wait(run,'awaiting_plan')

    def planning_runner(self,reference=False):
        import editorial_scope
        templates.install_editorial(self.workspace,'editor')
        original=self.runner.execute
        def execute(record,key,cwd,prompt,folder,log):
            value=original(record,key,cwd,prompt,folder,log)
            if key in ('video-producer','content-researcher-story-producer'):
                self.assertIn('Stage-local result',prompt)
                value['storyboard']='';value['references']=[]
            if key=='script-storyboard-writer':
                path=Path(record['output_root'])/key/'script.md';path.write_text('Fixture script and storyboard')
                value['artifacts']=[dict(path=str(path),kind='plan')]
                if not reference:value['references']=[]
            return value
        self.runner.execute=execute
        return editorial_scope.planning_graph(templates.defaults(self.workspace,'editor'),'reference-based' if reference else 'original')

    def test_original_planning_handoff_accept_and_stop_without_media(self):
        graph=self.planning_runner();run=self.create(graph);ready=self.wait(run,'awaiting_plan')
        self.assertEqual(self.runner.calls,['video-producer','content-researcher-story-producer','script-storyboard-writer'])
        self.assertEqual(ready['reference_candidates'],[])
        done=self.action(ready,'approve');self.wait(done,'completed')
        self.assertEqual(len(self.engine.get(self.workspace,run['id'])['approvals']),1)
        self.assertNotIn('video-editor',self.runner.calls)

    def test_planning_requires_real_writer_artifact(self):
        graph=self.planning_runner();original=self.runner.execute
        def no_artifact(*args,**kwargs):
            value=original(*args,**kwargs);value['artifacts']=[];return value
        self.runner.execute=no_artifact
        failed=self.wait(self.create(graph),'failed');self.assertIn('real script/storyboard',failed['error'])

    def test_reference_planning_cannot_approve_uninspected_source(self):
        graph=self.planning_runner(reference=True);original=self.runner.execute
        def uninspected(*args,**kwargs):
            value=original(*args,**kwargs)
            for ref in value['references']:ref['inspected']=False
            return value
        self.runner.execute=uninspected;ready=self.wait(self.create(graph),'awaiting_plan')
        with self.assertRaises(ValueError):self.accept1(ready)

    def test_reduce_failed_scope_does_not_retry_or_approve(self):
        self.planning_runner();graph=templates.defaults(self.workspace,'editor');original=self.runner.execute
        def blocked(*args,**kwargs):
            value=original(*args,**kwargs);value.update(blocked=True,passed=False);return value
        self.runner.execute=blocked;failed=self.wait(self.create(graph),'failed');count=len(self.runner.calls)
        configured=self.action(failed,'set_scope',scope='planning-only',reference_mode='original')
        self.assertEqual(configured['state'],'failed');self.assertEqual(configured['approvals'],[]);self.assertEqual(len(self.runner.calls),count)
        self.assertNotIn('export',[n['id'] for n in configured['graph']['nodes']])
        self.runner.execute=original;ready=self.wait(self.action(configured,'retry'),'awaiting_plan')
        with self.assertRaises(workflow.Conflict):self.action(self.action(ready,'approve'),'set_scope',scope='planning-only')

    def create(self,graph=None,project=None):
        return self.engine.create(self.workspace,{'team':'editor','task':'Fixture video task','project':str(project or self.project),'engine':'Codex','graph':graph or templates.defaults(self.workspace,'editor')})
    def wait(self,run,state):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            value=self.engine.get(self.workspace,run['id'])
            if value['state']==state:return value
            if value['state']=='failed' and state!='failed':self.fail(value['error'])
            time.sleep(.02)
        self.fail('Timeout: '+str(value))
    def action(self,run,action,**extra):
        return self.engine.action(self.workspace,{'id':run['id'],'revision':run['revision'],'action':action,**extra})
    def accept1(self,run):return self.action(run,'approve',selected_reference='https://example.com/reference')

    def test_editorial_full_gates_parallel_qa_loop_and_export(self):
        graph=templates.defaults(self.workspace,'editor')
        for node in graph['nodes']:node['enabled']=True
        self.runner.qa_failures=1
        run=self.wait(self.create(graph),'awaiting_plan')
        self.assertEqual(self.runner.calls,['video-producer','script-storyboard-writer'])
        with self.assertRaises(ValueError):self.action(run,'approve')
        self.accept1(run);run=self.wait(run,'awaiting_delivery')
        self.assertEqual(self.runner.overlap,3);self.assertEqual(run['round'],1)
        self.assertNotIn('export',self.runner.calls);self.assertEqual(len(run['approvals']),1)
        self.action(run,'approve');run=self.wait(run,'completed')
        self.assertIn('export',self.runner.calls);self.assertEqual(len(run['approvals']),2)
        self.assertTrue(any(a['kind']=='final' for a in run['artifacts'].values()))
        self.assertFalse(run['worktrees']);self.assertNotIn('commit',run)

    def test_defaults_bind_team_agents_optional_disabled_and_reset(self):
        graph=templates.defaults(self.workspace,'editor');self.assertEqual(graph['kind'],'editorial')
        self.assertEqual({n['agent'] for n in graph['nodes'] if 'agent' in n},set(templates.EDITORIAL))
        changed=copy.deepcopy(graph)
        changed['nodes'][0]['model']='custom-model';changed['nodes'][4]['enabled']=True
        templates.save(self.workspace,'editor',changed)
        option=templates.options(self.workspace,'editor')
        self.assertEqual(option['graph'],changed);self.assertEqual(option['default'],graph)
        run=self.wait(self.create(),'awaiting_plan');self.accept1(run);run=self.wait(run,'awaiting_delivery')
        self.assertNotIn('motion-graphic-designer',self.runner.calls)
        self.assertNotIn('audio-editor',self.runner.calls)

    def test_graph_rejects_gate_bypass_unknown_agent_and_bad_parallel(self):
        graph=templates.defaults(self.workspace,'editor')
        tests=[]
        bad=copy.deepcopy(graph);bad['nodes'][2]['enabled']=False;tests.append(bad)
        bad=copy.deepcopy(graph);bad['nodes'][0]['agent']='other-team-agent';tests.append(bad)
        bad=copy.deepcopy(graph);bad['groups'][0].append('accept-1');bad['groups'].remove(['accept-1']);tests.append(bad)
        bad=copy.deepcopy(graph);bad['groups'][3],bad['groups'][0]=bad['groups'][0],bad['groups'][3];tests.append(bad)
        bad=copy.deepcopy(graph);bad['nodes'][-1]['enabled']=False;tests.append(bad)
        for bad in tests:
            with self.subTest(graph=bad),self.assertRaises(ValueError):templates.validate(self.workspace,'editor',bad)

    def test_approval_evidence_change_and_source_selection(self):
        run=self.wait(self.create(),'awaiting_plan')
        with self.assertRaises(ValueError):self.action(run,'approve',selected_reference='https://example.com/other')
        with self.assertRaises(workflow.Conflict):self.engine.action(self.workspace,{'id':run['id'],'revision':0,'action':'approve'})
        self.accept1(run);run=self.wait(run,'awaiting_delivery')
        preview=next(Path(path) for path,a in run['artifacts'].items() if a['kind']=='preview')
        preview.write_bytes(b'changed after QA')
        with self.assertRaises(workflow.Conflict):self.action(run,'approve')
        self.action(run,'revise',feedback='Use a new reference')
        run=self.wait(run,'awaiting_plan');self.assertEqual(run['approvals'],[])

    def test_multiple_workflows_same_team_separate_projects_and_close(self):
        first=self.wait(self.create(),'awaiting_plan');other=self.root/'other';other.mkdir()
        second=self.wait(self.create(project=other),'awaiting_plan')
        with self.assertRaises(workflow.Conflict):self.create()
        closed=self.action(first,'cancel');self.action(closed,'dismiss')
        self.assertEqual([r['id'] for r in self.engine.list(self.workspace)],[second['id']])
        self.assertEqual(self.engine.get(self.workspace,second['id'])['state'],'awaiting_plan')

    def test_cancel_while_running_is_idempotent_and_dismissible(self):
        self.runner.hold=True;run=self.create()
        deadline=time.monotonic()+3
        while not self.runner.calls and time.monotonic()<deadline:time.sleep(.01)
        run=self.engine.get(self.workspace,run['id']);run=self.engine.action(self.workspace,{'id':run['id'],'revision':0,'action':'cancel'})
        self.assertEqual(run['state'],'cancelled')
        run=self.action(run,'cancel');self.action(run,'dismiss')
        self.assertEqual(self.engine.list(self.workspace),[])

    def test_missing_tools_fails_honestly_and_closed_error_unlocks(self):
        original=self.runner.execute
        self.runner.execute=lambda *args:result(blocked=True,summary='Browser unavailable',details='Provide accessible reference')
        run=self.wait(self.create(),'failed');self.assertIn('Browser unavailable',run['error'])
        self.runner.execute=original
        self.action(run,'revise',feedback='Use this accessible reference',references=['https://example.com/reference'])
        run=self.wait(run,'awaiting_plan');self.assertEqual(run['references'],['https://example.com/reference']);self.assertEqual(run['approvals'],[])
        run=self.action(run,'cancel');self.action(run,'dismiss');self.assertEqual(self.engine.list(self.workspace),[])

    def test_profile_install_preserves_custom_metadata_and_is_idempotent(self):
        path=server.document('editor','agent','script-storyboard-writer')
        text=path.read_text().replace('---\n\n#','appearance: {"hair": "custom"}\n---\n\n#')
        path.write_text(text)
        templates.install_editorial(self.workspace,'editor')
        updated=path.read_text();self.assertIn('appearance:',updated)
        self.assertIn('reference-video-analysis',agent_skills.assigned(updated))
        templates.install_editorial(self.workspace,'editor');self.assertEqual(path.read_text(),updated)
        self.assertTrue((self.workspace/'teams/editor/WORKFLOW.md').is_file())

    def test_development_graph_still_isolates_sources_and_commits_after_gate2(self):
        import subprocess
        import workflow_git as git
        server.create_team('developer','Development','Code')
        for role in templates.DEVELOPMENT:
            server.write(server.document('developer','agent',role),server.frontmatter(role,role,'# Fixture'))
        for args in [('init',),('config','user.name','Test'),('config','user.email','test@example.invalid')]:git.git(self.project,*args)
        (self.project/'initial.txt').write_text('original');git.git(self.project,'add','.');git.git(self.project,'commit','-m','initial')
        original=self.runner.execute
        def execute(record,key,cwd,*args):
            if key in ('frontend-developer','backend-developer'):
                (Path(cwd)/(key+'.txt')).write_text('fixture implementation')
            return original(record,key,cwd,*args)
        self.runner.execute=execute
        run=self.engine.create(self.workspace,{'team':'developer','task':'Fixture code','project':str(self.project),'engine':'Codex','graph':templates.defaults(self.workspace,'developer')})
        run=self.wait(run,'awaiting_plan');self.action(run,'approve');run=self.wait(run,'awaiting_delivery')
        self.assertFalse((self.project/'frontend-developer.txt').exists())
        self.assertTrue((Path(run['worktrees']['candidate'])/'frontend-developer.txt').exists())
        self.action(run,'approve');run=self.wait(run,'completed');self.assertTrue(run['commit'])
        self.assertFalse(git.git(self.project,'status','--porcelain'))

    def test_optional_agents_can_be_enabled_at_accept1_and_snapshot_is_stable(self):
        run=self.wait(self.create(),'awaiting_plan')
        templates.save(self.workspace,'editor',templates.defaults(self.workspace,'editor'))
        self.action(run,'approve',selected_reference='https://example.com/reference',optional_nodes={'audio-editor':True})
        run=self.wait(run,'awaiting_delivery')
        self.assertIn('audio-editor',self.runner.calls);self.assertNotIn('motion-graphic-designer',self.runner.calls)
        self.assertEqual(self.runner.overlap,2)

    def test_real_graph_cli_adapter_can_target_a_media_folder_outside_git(self):
        import sys
        import workflow_runner as cli
        script=self.root/'fixture_graph_cli.py'
        content='import sys,json\nfrom pathlib import Path\nsys.stdin.read()\nassert "--search" in sys.argv\nassert "--add-dir" in sys.argv\nassert "--skip-git-repo-check" in sys.argv\noutput=sys.argv[sys.argv.index("--output-last-message")+1]\nPath(output).write_text('+repr(json.dumps(result()))+')\n'
        script.write_text(content)
        record={'id':'graph-cli-fixture','kind':'graph','graph':{'kind':'editorial'},'result_schema':media.SCHEMA,'output_root':str(self.root/'outputs'),'roles':{'plan':{'engine':'Codex','model':''}}}
        with patch('terminal_runtime.cli_command',return_value=[sys.executable,str(script)]):
            value=cli.Runner().execute(record,'plan',str(self.project),'Fixture',self.root/'adapter',lambda _:None)
        self.assertTrue(value['passed'])

    def test_saved_graph_gate_and_interrupted_stage_survive_controller_replacement(self):
        import workflow_store as store
        run=self.wait(self.create(),'awaiting_plan')
        replacement=workflow.Engine(MediaRunner())
        try:
            restored=replacement.get(self.workspace,run['id'])
            self.assertEqual(restored['graph'],run['graph']);self.assertEqual(restored['state'],'awaiting_plan')
            record=store.get(self.workspace,run['id']);record.update(state='planning',owner=99999999);store.save(self.workspace,record)
            restored=replacement.get(self.workspace,run['id'])
            self.assertEqual(restored['state'],'interrupted');self.assertEqual(replacement.runner.calls,[])
            self.engine.action(self.workspace,{'id':run['id'],'action':'cancel','revision':0})
        finally:replacement.shutdown()

    def test_story_research_install_default_order_and_saved_customizations(self):
        import editorial_story
        graph=templates.defaults(self.workspace,'editor')
        graph['nodes'][0]['model']='custom-model';templates.save(self.workspace,'editor',graph)
        templates.install_editorial(self.workspace,'editor')
        saved=templates.options(self.workspace,'editor')
        self.assertEqual(saved['graph']['groups'][:3],[['video-producer'],[editorial_story.AGENT],['script-storyboard-writer']])
        self.assertEqual(saved['default']['groups'][1],[editorial_story.AGENT])
        self.assertEqual(saved['graph']['nodes'][0]['model'],'custom-model')
        for name in ('script-storyboard-writer','video-qa-reviewer'):
            content=server.document('editor','agent',name).read_text()
            self.assertIn('Story Research Handoff',content)
        before=(self.workspace/'teams/editor/WORKFLOW.json').read_text()
        templates.install_editorial(self.workspace,'editor')
        self.assertEqual((self.workspace/'teams/editor/WORKFLOW.json').read_text(),before)
        run=self.wait(self.create(),'awaiting_plan')
        self.assertEqual(self.runner.calls[:3],['video-producer',editorial_story.AGENT,'script-storyboard-writer'])

    def test_material_story_findings_require_new_accept1_not_auto_edit(self):
        templates.install_editorial(self.workspace,'editor')
        original=self.runner.execute
        failed=[False]
        def execute(record,key,*args):
            if key=='video-qa-reviewer' and not failed[0]:
                failed[0]=True
                return result(passed=False,replan_required=True,findings=['Correct the factual timeline'])
            return original(record,key,*args)
        self.runner.execute=execute
        run=self.wait(self.create(),'awaiting_plan');self.accept1(run)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            run=self.engine.get(self.workspace,run['id'])
            if run['state']=='awaiting_plan' and run['round']==1:break
            if run['state']=='failed':self.fail(run['error'])
            time.sleep(.02)
        self.assertEqual(run['state'],'awaiting_plan');self.assertEqual(run['approvals'],[])
        self.assertEqual(self.runner.calls.count('video-editor'),1);self.assertNotIn('export',self.runner.calls)
        self.accept1(run);run=self.wait(run,'awaiting_delivery')
        self.assertEqual(len(run['approvals']),1)

    def test_relative_deliverable_paths_are_normalized_for_preview_links(self):
        original=self.runner.execute
        def execute(record,key,*args):
            value=original(record,key,*args)
            for item in value['artifacts']:item['path']=Path(item['path']).name
            return value
        self.runner.execute=execute
        run=self.wait(self.create(),'awaiting_plan');self.accept1(run);run=self.wait(run,'awaiting_delivery')
        artifacts=[a for output in run['outputs'].values() for a in output['artifacts']]
        self.assertTrue(artifacts)
        self.assertTrue(all(Path(item['path']).is_absolute() and Path(item['path']).is_file() for item in artifacts))

    def test_artifact_serving_is_scoped_and_supports_video_ranges(self):
        import io
        import workflow_artifacts
        run=self.wait(self.create(),'awaiting_plan');self.accept1(run);run=self.wait(run,'awaiting_delivery')
        path=next(p for p,item in run['artifacts'].items() if item['kind']=='preview')
        class Handler:
            headers={'Range':'bytes=0-6'}
            wfile=io.BytesIO()
            values={}
            def send_response(self,code):self.status=code
            def send_header(self,key,value):self.values[key]=value
            def end_headers(self):pass
            def respond(self,code,value):self.status=code
        handler=Handler()
        workflow_artifacts.serve(handler,self.workspace,{'id':[run['id']],'path':[path]})
        self.assertEqual(handler.status,206);self.assertEqual(handler.wfile.getvalue(),b'fixture')
        self.assertEqual(handler.values['Content-Type'],'video/mp4')
        with self.assertRaises(ValueError):workflow_artifacts.serve(handler,self.workspace,{'id':[run['id']],'path':[str(self.project/'outside')]})

    def test_result_artifact_escape_and_invented_export_rejected(self):
        outside=self.root/'outside';outside.write_text('private')
        with self.assertRaises(ValueError):media.artifacts(self.project,[{'path':str(outside),'kind':'preview'}])
        original=self.runner.execute
        def execute(record,key,*args):
            if key=='export':return result()
            return original(record,key,*args)
        self.runner.execute=execute
        run=self.wait(self.create(),'awaiting_plan');self.accept1(run);run=self.wait(run,'awaiting_delivery')
        self.action(run,'approve');run=self.wait(run,'failed');self.assertIn('final',run['error'])

if __name__=='__main__':unittest.main()
