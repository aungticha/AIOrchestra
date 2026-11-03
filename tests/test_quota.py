from datetime import datetime, timezone, timedelta
import io
import json
from pathlib import Path
import tempfile
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import server
import unittest
from unittest.mock import patch
import quota

class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bundled_chatgpt_cli_without_terminal_path(self):
        expected=Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex')
        with patch('quota.shutil.which',return_value=None),patch.object(Path,'is_file',lambda path:path==expected):
            self.assertEqual(quota.find_codex(),str(expected))

    def test_path_cli_keeps_priority(self):
        with patch('quota.shutil.which',return_value='/custom/bin/codex'):
            self.assertEqual(quota.find_codex(),'/custom/bin/codex')

    def test_windows_zero_and_invalid_are_not_confused(self):
        self.assertEqual(quota.window('x',100)['remainingPercent'],0)
        self.assertEqual(quota.window('x',0)['remainingPercent'],100)
        for value in (None,'25',True,-1,101,float('nan'),float('inf')):
            self.assertIsNone(quota.window('x',value))
        result={'rateLimitsByLimitId':{'codex':{'primary':{'usedPercent':20,'windowDurationMins':300,'resetsAt':2000000000},'secondary':None}}}
        self.assertEqual(quota.codex_windows(result)[0]['remainingPercent'],80)
        self.assertEqual(quota.codex_windows({'rateLimits':None}),[])

    def test_codex_missing_login_api_and_redaction(self):
        with patch('quota.find_codex',return_value=None):
            self.assertEqual(quota.fetch_codex()['status'],'missing_cli')
        class FakeRpc:
            def __init__(self,_): pass
            def call(self,method,params=None):
                if method=='account/read': return {'account':FakeRpc.account}
                if method=='account/rateLimits/read': return {'rateLimits':{'primary':{'usedPercent':15}}}
                return {}
            def send(self,_): pass
            def close(self): pass
        with patch('quota.find_codex',return_value='codex'),patch('quota.Rpc',FakeRpc):
            FakeRpc.account=None
            self.assertEqual(quota.fetch_codex()['status'],'login_required')
            FakeRpc.account={'type':'apiKey','apiKey':'never-expose-secret'}
            self.assertEqual(quota.fetch_codex()['status'],'api_mode')
            FakeRpc.account={'type':'chatgpt','email':'private@example.com','token':'never-expose-secret'}
            result=quota.fetch_codex()
            self.assertEqual(result['windows'][0]['remainingPercent'],85)
            self.assertNotIn('private@example.com',json.dumps(result))
            self.assertNotIn('never-expose-secret',json.dumps(result))
        with patch('quota.find_codex',return_value='codex'),patch('quota.Rpc',side_effect=TimeoutError):
            self.assertEqual(quota.fetch_codex()['status'],'timeout')

    def test_codex_cache_marks_old_snapshot_stale(self):
        old={'status':'ok','windows':[], 'updatedAt':(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()}
        with patch('quota.CACHE',old):
            self.assertEqual(quota.cached_codex()['status'],'stale')
            self.assertEqual(old['status'],'ok')

    def test_claude_bridge_allowlist_and_stale(self):
        self.assertEqual(quota.claude_status(self.root)['status'],'bridge_required')
        payload={'rate_limits':{'five_hour':{'used_percentage':25,'resets_at':2000000000}},
                 'transcript_path':'secret/transcript','apiKey':'never-save-secret','prompt':'do not store'}
        quota.write_claude_snapshot(self.root,payload)
        self.assertEqual(quota.claude_status(self.root)['windows'][0]['remainingPercent'],75)
        raw=quota.snapshot_path(self.root).read_text()
        for text in ('never-save-secret','secret/transcript','do not store'):
            self.assertNotIn(text,raw)
        saved=json.loads(raw)
        saved['updatedAt']=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()
        quota.snapshot_path(self.root).write_text(json.dumps(saved))
        self.assertEqual(quota.claude_status(self.root)['status'],'stale')
        quota.write_claude_snapshot(self.root,{'rate_limits':None})
        self.assertEqual(quota.claude_status(self.root)['status'],'unavailable')
        self.assertEqual(quota.claude_status(self.root)['windows'],[])

    def test_bridge_settings_preserve_backup_idempotence_and_conflict(self):
        home=self.root/'claude home'
        home.mkdir()
        path=home/'settings.json'
        raw=b'{"permissions":{"allow":[]},"env":{"EXAMPLE":"not-returned"}}'
        path.write_bytes(raw)
        with patch('quota.codex_setup.client_home',return_value=home):
            info=quota.bridge_preview(self.root)
            self.assertTrue(info['canInstall'])
            self.assertNotIn('not-returned',json.dumps(info))
            done=quota.install_bridge(self.root,info['revision'])
            self.assertEqual(Path(done['backup']).read_bytes(),raw)
            self.assertEqual(json.loads(path.read_text())['env']['EXAMPLE'],'not-returned')
            self.assertTrue(done['installed'])
            self.assertIsNone(quota.install_bridge(self.root,done['revision'])['backup'])
            path.write_text('{"statusLine":{"type":"command","command":"my-existing-command"}}')
            info=quota.bridge_preview(self.root)
            self.assertFalse(info['canInstall'])
            with self.assertRaises(ValueError): quota.install_bridge(self.root,info['revision'])
            self.assertIn('my-existing-command',path.read_text())

    def test_http_quota_and_bridge_use_sanitized_data(self):
        original=server.DATA
        server.DATA=self.root
        home=self.root/'claude-config'
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{http.server_port}'
        def post(route,body,origin=None):
            headers={'Content-Type':'application/json'}
            if origin: headers['Origin']=origin
            return urlopen(Request(base+route,data=json.dumps(body).encode(),headers=headers))
        try:
            with patch('quota.codex_status',return_value={'status':'ok','windows':[]}),patch('quota.codex_setup.client_home',return_value=home):
                with post('/api/quota/refresh',{}) as response:
                    result=json.load(response)
                self.assertEqual(result['codex']['status'],'ok')
                self.assertEqual(result['claude']['status'],'bridge_required')
                with urlopen(base+'/api/quota/claude-bridge') as response:
                    info=json.load(response)
                with post('/api/quota/claude-bridge',{'revision':info['revision']}) as response:
                    self.assertTrue(json.load(response)['installed'])
                with self.assertRaises(HTTPError) as error:
                    post('/api/quota/claude-bridge',{'revision':info['revision']},'https://evil.example')
                self.assertEqual(error.exception.code,403)
        finally:
            http.shutdown();http.server_close();thread.join();server.DATA=original

    def test_windows_command_uses_encoded_powershell(self):
        import base64
        with patch('quota.os.name','nt'):
            # Pathlib chooses platform classes at construction; keep native paths in this unit test.
            with patch('quota.Path',wraps=Path) as paths:
                paths.return_value= self.root
                command=quota.bridge_command(self.root)
        self.assertTrue(command.startswith('powershell -NoProfile -EncodedCommand '))
        script=base64.b64decode(command.split()[-1]).decode('utf-16le')
        self.assertIn('--workspace',script)
        self.assertIn('claude_quota_bridge.py',script)

if __name__=='__main__': unittest.main()
