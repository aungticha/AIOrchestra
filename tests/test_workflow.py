import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import library_manager
import live_agents
import server
import workflow
import workflow_git as git
import workflow_runner as cli
import workflow_store as store


def result(**changes):
    value={'summary':'Completed stage','details':'Verified fixture output','passed':True,'blocked':False,'ui_required':False,'frontend':True,'backend':True,'frontend_paths':['frontend.txt'],'backend_paths':['backend.txt'],'findings':[],'tests':['Fixture checks passed']}
    return {**value,**changes}

class FakeRunner:
    def __init__(self,ui=False,review_failures=0,qa_failures=0):
        self.ui=ui;self.review_failures=review_failures;self.qa_failures=qa_failures;self.calls=[];self.overlap=0;self.active=0;self.lock=threading.Lock();self.stopped=False
    def stop(self,identifier):self.stopped=True
    def execute(self,record,role,cwd,prompt,folder,log):
        self.calls.append(role);log('Fixture CLI '+role+'\n')
        if role=='tech-lead-architect':return result(ui_required=self.ui)
        if role in ('frontend-developer','backend-developer'):
            with self.lock:self.active+=1;self.overlap=max(self.overlap,self.active)
            time.sleep(.08)
            name='frontend.txt' if role=='frontend-developer' else 'backend.txt'
            (Path(cwd)/name).write_text(role+' '+str(record['round']))
            with self.lock:self.active-=1
        if role=='code-reviewer' and self.review_failures:
            self.review_failures-=1;return result(passed=False,findings=['Fix frontend validation'])
        if role=='qa-test-engineer' and self.qa_failures:
            self.qa_failures-=1;return result(passed=False,findings=['Backend regression'])
        return result()

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.project=self.root/'project';self.project.mkdir();self.workspace=self.root/'workspace';self.original=server.DATA;server.DATA=self.workspace
        self.git('init');self.git('config','user.name','Workflow Test');self.git('config','user.email','workflow@example.invalid')
        (self.project/'initial.txt').write_text('original');self.git('add','.');self.git('commit','-m','initial')
        server.create_team('developer','Development','Test')
        for role in cli.ROLES:server.write(server.document('developer','agent',role),server.frontmatter(role,'Test '+role,'# Fixture role'))
        self.runner=FakeRunner();self.engine=workflow.Engine(self.runner)
        self.patcher=patch('terminal_runtime.executable',return_value='/fixture/codex');self.patcher.start()
    def tearDown(self):
        self.engine.shutdown();self.patcher.stop();server.DATA=self.original;self.tmp.cleanup()
    def git(self,*args):return git.git(self.project,*args)
    def create(self,**payload):return self.engine.create(self.workspace,{'team':'developer','project':str(self.project),'task':'Implement feature','engine':'Codex',**payload})
    def wait(self,identifier,state):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            run=self.engine.get(self.workspace,identifier)
            if run['state']==state:return run
            if run['state']=='failed' and state!='failed':self.fail(run['error'])
            time.sleep(.03)
        self.fail('Workflow did not reach '+state+': '+str(run))
    def action(self,run,action,**extra):
        return self.engine.action(self.workspace,{'id':run['id'],'revision':run['revision'],'action':action,**extra})
    def test_real_sequence_parallel_gates_and_commit(self):
        created=self.create();run=self.wait(created['id'],'awaiting_plan')
        self.assertEqual(self.runner.calls,['tech-lead-architect'])
        self.assertFalse(run['worktrees']);self.assertEqual(live_agents.snapshot(self.workspace)['lockedTeams'],['developer'])
        with self.assertRaises(library_manager.Locked):library_manager.manage(self.workspace,{'team':'developer','kind':'team','action':'rename','name':'x'})
        self.action(run,'approve');run=self.wait(run['id'],'awaiting_delivery')
        self.assertEqual(self.runner.overlap,2);self.assertIn('qa-test-engineer',self.runner.calls)
        candidate=Path(run['worktrees']['candidate']);self.assertTrue((candidate/'frontend.txt').is_file());self.assertTrue((candidate/'backend.txt').is_file())
        self.assertEqual(git.git(candidate,'rev-parse','HEAD').decode().strip(),run['base'])
        self.assertFalse((self.project/'frontend.txt').exists());self.assertFalse(self.git('status','--porcelain'))
        self.action(run,'approve');done=self.wait(run['id'],'completed')
        self.assertNotEqual(done['commit'],run['base']);self.assertFalse(done['pushed'])
        self.assertEqual(len(done['approvals']),2);self.assertEqual(live_agents.snapshot(self.workspace)['lockedTeams'],[])
    def test_ui_branch_and_review_qa_fix_loops(self):
        self.runner.ui=True;self.runner.review_failures=1;self.runner.qa_failures=1
        run=self.wait(self.create()['id'],'awaiting_plan');self.assertIn('ui-ux-designer',self.runner.calls)
        self.action(run,'approve');done=self.wait(run['id'],'awaiting_delivery')
        self.assertEqual(done['round'],2);self.assertEqual(self.runner.calls.count('code-reviewer'),3);self.assertEqual(self.runner.calls.count('qa-test-engineer'),2)
    def test_approval_revision_and_changed_candidate_are_rejected(self):
        run=self.wait(self.create()['id'],'awaiting_plan')
        with self.assertRaises(workflow.Conflict):self.engine.action(self.workspace,{'id':run['id'],'revision':0,'action':'approve'})
        self.action(run,'approve');run=self.wait(run['id'],'awaiting_delivery')
        (Path(run['worktrees']['candidate'])/'frontend.txt').write_text('changed after QA')
        with self.assertRaises(workflow.Conflict):self.action(run,'approve')
        self.assertEqual(self.engine.get(self.workspace,run['id'])['state'],'awaiting_delivery')
    def test_revision_feedback_replans_and_does_not_accept(self):
        run=self.wait(self.create()['id'],'awaiting_plan');self.action(run,'revise',feedback='Use a smaller design')
        updated=self.wait(run['id'],'awaiting_plan');self.assertEqual(updated['approvals'],[]);self.assertEqual(self.runner.calls.count('tech-lead-architect'),2)
    def test_gate_survives_new_engine_and_cancel_unlocks(self):
        run=self.wait(self.create()['id'],'awaiting_plan');second=workflow.Engine(FakeRunner())
        self.assertEqual(second.get(self.workspace,run['id'])['state'],'awaiting_plan')
        second.action(self.workspace,{'id':run['id'],'revision':run['revision'],'action':'cancel'})
        self.assertEqual(live_agents.snapshot(self.workspace)['lockedTeams'],[]);second.shutdown()
    def test_failed_stage_blocks_approval_and_can_retry(self):
        original=self.runner.execute
        def fail(*args,**kwargs):raise ValueError('CLI auth unavailable')
        self.runner.execute=fail
        run=self.wait(self.create()['id'],'failed')
        with self.assertRaises(workflow.Conflict):self.action(run,'approve')
        self.runner.execute=original;self.action(run,'retry');run=self.wait(run['id'],'awaiting_plan')
        self.assertEqual(run['approvals'],[])
    def test_dirty_repository_rejected(self):
        (self.project/'initial.txt').write_text('user work')
        with self.assertRaises(ValueError):self.create()
        self.assertEqual((self.project/'initial.txt').read_text(),'user work')
    def test_commit_push_to_local_remote_only_after_second_accept(self):
        remote=self.root/'remote.git';subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True);self.git('remote','add','origin',str(remote))
        run=self.wait(self.create(push=True)['id'],'awaiting_plan');self.action(run,'approve');run=self.wait(run['id'],'awaiting_delivery')
        self.assertFalse(self.git('ls-remote','--heads','origin'))
        self.action(run,'approve');done=self.wait(run['id'],'completed')
        self.assertTrue(done['pushed']);self.assertIn(done['commit'],self.git('ls-remote','--heads','origin').decode())
    def test_out_of_scope_files_block_integration(self):
        original=self.runner.execute
        def out_of_scope(record,role,cwd,*args):
            value=original(record,role,cwd,*args)
            if role=='frontend-developer':(Path(cwd)/'unexpected.txt').write_text('not approved')
            return value
        self.runner.execute=out_of_scope;run=self.wait(self.create()['id'],'awaiting_plan');self.action(run,'approve');run=self.wait(run['id'],'failed')
        self.assertIn('unexpected.txt',run['error']);self.assertFalse((self.project/'unexpected.txt').exists())
    def test_invalid_structured_result_never_advances(self):
        self.runner.execute=lambda *a,**k:{'summary':'trust me'}
        run=self.wait(self.create()['id'],'failed');self.assertEqual(run['approvals'],[]);self.assertEqual(run['worktrees'],{})

    def test_interrupted_owner_is_not_silently_restarted(self):
        run=self.wait(self.create()['id'],'awaiting_plan');record=store.get(self.workspace,run['id'])
        record.update(state='planning',owner=99999999);store.save(self.workspace,record)
        second=workflow.Engine(FakeRunner());restored=second.get(self.workspace,run['id'])
        self.assertEqual(restored['state'],'interrupted');self.assertEqual(second.runner.calls,[]);second.shutdown()

    def test_git_changes_by_worker_are_rejected_before_qa(self):
        original=self.runner.execute
        def commits(record,role,cwd,*args):
            value=original(record,role,cwd,*args)
            if role=='frontend-developer':git.git(cwd,'add','frontend.txt');git.git(cwd,'commit','-m','unauthorized fixture commit')
            return value
        self.runner.execute=commits;run=self.wait(self.create()['id'],'awaiting_plan');self.action(run,'approve');run=self.wait(run['id'],'failed')
        self.assertIn('commit/branch',run['error']);self.assertNotIn('qa-test-engineer',self.runner.calls)

    def test_real_cli_adapter_uses_stdin_and_structured_output(self):
        import sys
        script=self.root/'fixture_cli.py';script.write_text('import sys,json\nfrom pathlib import Path\nprompt=sys.stdin.read()\nassert "fixture prompt" in prompt\noutput=sys.argv[sys.argv.index("--output-last-message")+1]\nPath(output).write_text('+repr(json.dumps(result()))+')\nprint("fixture CLI completed",flush=True)\n')
        record={'id':'fixture','roles':{'tech-lead-architect':{'engine':'Codex','model':''}}};runner=cli.Runner();logs=[]
        with patch('terminal_runtime.cli_command',return_value=[sys.executable,'-u',str(script)]):
            value=runner.execute(record,'tech-lead-architect',str(self.project),'fixture prompt',self.root/'adapter',logs.append)
        self.assertTrue(value['passed']);self.assertIn('fixture CLI completed',''.join(logs));self.assertEqual(runner.processes,{})

    def test_claude_cli_adapter_reads_structured_output(self):
        import sys
        script=self.root/'fixture_claude.py';script.write_text('import sys,json\nsys.stdin.read()\nprint('+repr(json.dumps({'structured_output':result(),'is_error':False}))+')\n')
        record={'id':'claude-fixture','roles':{'tech-lead-architect':{'engine':'Claude','model':'sonnet'}}};runner=cli.Runner()
        with patch('terminal_runtime.cli_command',return_value=[sys.executable,'-u',str(script)]):
            value=runner.execute(record,'tech-lead-architect',str(self.project),'fixture',self.root/'claude-adapter',lambda _:None)
        self.assertTrue(value['passed'])

    def test_cli_process_cancel_stops_owned_worker(self):
        import sys
        script=self.root/'waiting_cli.py';script.write_text('import sys,time\nsys.stdin.read()\nprint("running",flush=True)\ntime.sleep(60)\n')
        record={'id':'cancel-fixture','roles':{'tech-lead-architect':{'engine':'Codex','model':''}}};runner=cli.Runner();errors=[]
        def run():
            try:runner.execute(record,'tech-lead-architect',str(self.project),'fixture',self.root/'cancel-adapter',lambda _:None)
            except Exception as error:errors.append(error)
        with patch('terminal_runtime.cli_command',return_value=[sys.executable,'-u',str(script)]):
            thread=threading.Thread(target=run);thread.start();deadline=time.monotonic()+5
            while not runner.processes and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(runner.processes);runner.stop('cancel-fixture');thread.join(timeout=5)
        self.assertFalse(thread.is_alive());self.assertTrue(errors);self.assertEqual(runner.processes,{})

    def test_push_failure_retry_does_not_create_duplicate_commit(self):
        remote=self.root/'retry-remote.git';subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True);self.git('remote','add','origin',str(remote))
        run=self.wait(self.create(push=True)['id'],'awaiting_plan');self.action(run,'approve');run=self.wait(run['id'],'awaiting_delivery')
        original=git.git
        def fail_push(project,*args,**kwargs):
            if args and args[0]=='push':raise git.GitError('Fixture remote unavailable')
            return original(project,*args,**kwargs)
        with patch('workflow_git.git',side_effect=fail_push):
            self.action(run,'approve');failed=self.wait(run['id'],'failed')
        self.assertTrue(failed['commit']);self.action(failed,'retry');done=self.wait(run['id'],'completed')
        self.assertEqual(done['commit'],failed['commit']);self.assertTrue(done['pushed'])
        self.assertEqual(git.git(done['worktrees']['candidate'],'rev-list','--count','HEAD').decode().strip(),'2')

    @unittest.skipIf(os.name=='nt','POSIX hook fixture')
    def test_hook_changes_require_new_review_and_accept_before_push(self):
        remote=self.root/'hook-remote.git';subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True);self.git('remote','add','origin',str(remote))
        run=self.wait(self.create(push=True)['id'],'awaiting_plan');self.action(run,'approve');run=self.wait(run['id'],'awaiting_delivery')
        hook=self.project/'.git/hooks/pre-commit';hook.write_text('#!/bin/sh\nprintf "hook change" > frontend.txt\ngit add frontend.txt\n');hook.chmod(0o755)
        self.action(run,'approve');failed=self.wait(run['id'],'failed')
        self.assertIn('Git hook',failed['error']);self.assertFalse(self.git('ls-remote','--heads','origin'))
        self.action(failed,'recheck');ready=self.wait(run['id'],'awaiting_delivery')
        self.assertFalse(self.git('ls-remote','--heads','origin'));self.action(ready,'approve');done=self.wait(run['id'],'completed');self.assertTrue(done['pushed'])

    def test_cancel_failure_keeps_team_locked(self):
        run=self.wait(self.create()['id'],'awaiting_plan');original=self.runner.stop
        def cannot_stop(_identifier):raise ValueError('Fixture process permission error')
        self.runner.stop=cannot_stop
        with self.assertRaises(ValueError):self.action(run,'cancel')
        failed=self.engine.get(self.workspace,run['id']);self.assertEqual(failed['state'],'failed');self.assertEqual(live_agents.snapshot(self.workspace)['lockedTeams'],['developer'])
        self.runner.stop=original;self.action(failed,'cancel');self.assertEqual(live_agents.snapshot(self.workspace)['lockedTeams'],[])
