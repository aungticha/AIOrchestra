import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile
import server
import token_store

# Deliberately fake keys; no live provider calls are made.
OPENAI = 'fake-openai-test-only'
ANTHROPIC = 'fake-anthropic-test-only'

class TokenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_json_env_and_partial_merge(self):
        token_store.save(self.root, token_store.parse_file(json.dumps({'OPENAI_API_KEY':OPENAI})))
        token_store.save(self.root, token_store.parse_file('# comment\nexport ANTHROPIC_API_KEY="'+ANTHROPIC+'"\n'))
        self.assertEqual(token_store.load(self.root), {'OPENAI_API_KEY':OPENAI,'ANTHROPIC_API_KEY':ANTHROPIC})
        status = json.dumps(token_store.status(self.root))
        self.assertNotIn(OPENAI,status)
        self.assertNotIn(ANTHROPIC,status)
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(token_store.location(self.root).stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(token_store.location(self.root).parent.stat().st_mode),0o700)

    def test_invalid_import_never_changes_existing_file_or_echoes_keys(self):
        token_store.save(self.root, {'OPENAI_API_KEY':OPENAI})
        before = token_store.location(self.root).read_bytes()
        invalid = ['{}','[]','{"OPENAI_API_KEY":""}', 'OPENAI_API_KEY=bad key', 'INVALID-NAME='+ANTHROPIC,
                   '{"OPENAI_API_KEY":true}', '{broken secret-value', 'OPENAI_API_KEY=x\nOPENAI_API_KEY=y',
                   'OPENAI_API_KEY="unclosed', 'x'*24001]
        for content in invalid:
            with self.assertRaises(ValueError) as e:
                token_store.save(self.root, token_store.parse_file(content))
            self.assertNotIn(ANTHROPIC,str(e.exception))
            self.assertEqual(token_store.location(self.root).read_bytes(),before)

    def test_custom_tokens_and_total_size_limit(self):
        token_store.save(self.root, {'OPENAI_API_KEY':OPENAI})
        token_store.save(self.root, token_store.parse_file('GITHUB_TOKEN=fake-github-only\nSTRIPE_SECRET_KEY=fake-stripe-only'))
        token_store.save(self.root, {'GITHUB_TOKEN':'fake-updated'})
        values=token_store.load(self.root)
        self.assertEqual(values['GITHUB_TOKEN'],'fake-updated')
        self.assertEqual(values['OPENAI_API_KEY'],OPENAI)
        status=token_store.status(self.root)
        self.assertTrue(status['providers']['GITHUB_TOKEN']['configured'])
        self.assertNotIn('fake-updated',json.dumps(status))
        before=token_store.location(self.root).read_bytes()
        with self.assertRaises(ValueError):
            token_store.save(self.root, {f'TOKEN_{i}':'x'*8000 for i in range(3)})
        self.assertEqual(token_store.location(self.root).read_bytes(),before)
        for name in ('1TOKEN','bad-name','lowercase','<script>','X'*65):
            with self.assertRaises(ValueError):
                token_store.save(self.root, {name:'fake-test'})

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            try:
                (self.root/'secrets').symlink_to(external, target_is_directory=True)
            except OSError:
                if os.name == 'nt':
                    self.skipTest('Windows symlink privilege unavailable')
                raise
            with self.assertRaises(ValueError):
                token_store.save(self.root, {'OPENAI_API_KEY':OPENAI})
            self.assertEqual(list(Path(external).iterdir()),[])

    def test_http_import_redaction_and_export_exclusion(self):
        original = server.DATA
        server.DATA = self.root
        server.create_team('test','Test','No secrets')
        http = server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread = threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{http.server_port}'
        def post(path,body,origin=None):
            headers={'Content-Type':'application/json'}
            if origin: headers['Origin']=origin
            return urlopen(Request(base+path,data=json.dumps(body).encode(),headers=headers))
        try:
            with post('/api/credentials',{'fileContent':'OPENAI_API_KEY='+OPENAI+'\nGITHUB_TOKEN=fake-github-http'}) as r:
                response=r.read().decode()
                self.assertNotIn(OPENAI,response)
                self.assertNotIn('fake-github-http',response)
                self.assertEqual(r.headers['Cache-Control'],'no-store')
            with urlopen(base+'/api/credentials') as r:
                self.assertTrue(json.load(r)['providers']['OPENAI_API_KEY']['configured'])
            with urlopen(base+'/api/state') as r:
                self.assertNotIn(OPENAI,r.read().decode())
            for target in ('codex','claude','portable'):
                with post('/api/export',{'team':'test','target':target}) as r:
                    with zipfile.ZipFile(io.BytesIO(r.read())) as archive:
                        for name in archive.namelist():
                            self.assertNotIn('secrets',name)
                            self.assertNotIn(OPENAI,archive.read(name).decode())
                            self.assertNotIn('fake-github-http',archive.read(name).decode())
            with self.assertRaises(HTTPError) as e:
                post('/api/credentials',{'keys':{'ANTHROPIC_API_KEY':ANTHROPIC}},'https://evil.example')
            self.assertEqual(e.exception.code,403)
            self.assertNotIn('ANTHROPIC_API_KEY',token_store.load(self.root))
            with self.assertRaises(HTTPError) as e:
                urlopen(base+'/workspace/secrets/api-tokens.json')
            self.assertEqual(e.exception.code,404)
        finally:
            http.shutdown()
            http.server_close()
            thread.join()
            server.DATA = original

if __name__ == '__main__':
    unittest.main()
