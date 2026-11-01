import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import codex_setup
import server

class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root/'codex home'
        self.library = self.root/'Application with spaces'/'workspace'/'teams'
        self.library.mkdir(parents=True)
        self.env = patch.dict('os.environ', {'CODEX_HOME':str(self.home)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_discovery_creation_and_dynamic_library(self):
        info=codex_setup.preview(self.library)
        self.assertEqual(info['path'],str(self.home/'AGENTS.md'))
        self.assertFalse(info['exists'])
        self.assertIn(str(self.library),info['block'])
        self.assertNotIn('/Users/aungticha',info['block'])
        result=codex_setup.install(self.library,None,info['revision'])
        self.assertTrue(result['updated'])
        self.assertIsNone(result['backup'])
        self.assertIn('Before starting a task:',(self.home/'AGENTS.md').read_text())

    def test_default_home_discovery_without_codex_home(self):
        with patch.dict('os.environ',{},clear=True), patch('codex_setup.Path.home',return_value=self.root):
            self.assertEqual(codex_setup.target_path(),self.root/'.codex'/'AGENTS.md')

    def test_preserves_bytes_backup_crlf_and_idempotence(self):
        self.home.mkdir()
        path=self.home/'AGENTS.md'
        original=b'\xef\xbb\xbf# Existing instructions\r\nKeep project preferences.\r\n'
        path.write_bytes(original)
        info=codex_setup.preview(self.library)
        result=codex_setup.install(self.library,None,info['revision'])
        self.assertEqual(Path(result['backup']).read_bytes(),original)
        self.assertTrue(path.read_bytes().startswith(original))
        self.assertIn(b'\r\n## AIOrchestra',path.read_bytes())
        before=path.read_bytes()
        result=codex_setup.install(self.library,None,result['revision'])
        self.assertFalse(result['updated'])
        self.assertIsNone(result['backup'])
        self.assertEqual(before,path.read_bytes())
        moved=self.root/'moved application'/'workspace'/'teams'
        info=codex_setup.preview(moved)
        codex_setup.install(moved,None,info['revision'])
        self.assertEqual(path.read_text(encoding='utf-8-sig').count(codex_setup.BEGIN),1)
        self.assertIn(str(moved),path.read_text(encoding='utf-8-sig'))
        self.assertTrue(path.read_bytes().startswith(original))

    def test_manual_path_override_warning_and_stale_preview(self):
        manual=self.root/'manual codex'
        manual.mkdir()
        (manual/'AGENTS.override.md').write_text('Override')
        info=codex_setup.preview(self.library,str(manual))
        self.assertEqual(info['path'],str(manual/'AGENTS.md'))
        self.assertEqual(len(info['warnings']),2)
        (manual/'AGENTS.md').write_text('A concurrent edit')
        with self.assertRaises(ValueError):
            codex_setup.install(self.library,str(manual),info['revision'])
        self.assertEqual((manual/'AGENTS.md').read_text(),'A concurrent edit')
        self.assertEqual((manual/'AGENTS.override.md').read_text(),'Override')

    def test_rejects_invalid_files_and_markers(self):
        self.home.mkdir()
        path=self.home/'AGENTS.md'
        for content in (b'\xff',codex_setup.BEGIN.encode(),(codex_setup.END+codex_setup.BEGIN).encode()):
            path.write_bytes(content)
            with self.assertRaises(ValueError):
                codex_setup.preview(self.library)
            self.assertEqual(path.read_bytes(),content)
        for custom in ('relative/file','/tmp/OTHER.md'):
            with self.assertRaises(ValueError):
                codex_setup.target_path(custom)

    def test_claude_default_and_config_dir(self):
        with patch.dict('os.environ',{},clear=True), patch('codex_setup.Path.home',return_value=self.root):
            self.assertEqual(codex_setup.target_path(client='claude'),self.root/'.claude'/'CLAUDE.md')
        claude_home=self.root/'Claude custom home'
        with patch.dict('os.environ',{'CLAUDE_CONFIG_DIR':str(claude_home)}):
            info=codex_setup.preview(self.library,client='claude')
            self.assertEqual(info['path'],str(claude_home/'CLAUDE.md'))
            self.assertEqual(info['detectedBy'],'CLAUDE_CONFIG_DIR')
            self.assertEqual(info['filename'],'CLAUDE.md')
            self.assertEqual(info['warnings'],[])

    def test_claude_install_preserves_existing_and_codex(self):
        claude_home=self.root/'claude'
        claude_home.mkdir()
        path=claude_home/'CLAUDE.md'
        original=b'# Existing Claude preferences\r\nKeep them.\r\n'
        path.write_bytes(original)
        self.home.mkdir()
        (self.home/'AGENTS.md').write_text('Codex remains unchanged')
        with patch.dict('os.environ',{'CLAUDE_CONFIG_DIR':str(claude_home)}):
            info=codex_setup.preview(self.library,client='claude')
            result=codex_setup.install(self.library,None,info['revision'],client='claude')
            self.assertEqual(Path(result['backup']).read_bytes(),original)
            self.assertTrue(Path(result['backup']).name.startswith('CLAUDE.md.aiorchestra-'))
            self.assertTrue(path.read_bytes().startswith(original))
            repeat=codex_setup.install(self.library,None,result['revision'],client='claude')
            self.assertFalse(repeat['updated'])
            self.assertEqual(path.read_text().count(codex_setup.BEGIN),1)
            self.assertEqual((self.home/'AGENTS.md').read_text(),'Codex remains unchanged')
            with self.assertRaises(ValueError):
                codex_setup.target_path(str(self.home/'AGENTS.md'),client='claude')
            with self.assertRaises(ValueError):
                codex_setup.preview(self.library,client='unknown')

    def test_http_preview_and_setup(self):
        original=server.DATA
        server.DATA=self.library.parent
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{http.server_port}'
        def post(route,body,origin=None):
            headers={'Content-Type':'application/json'}
            if origin: headers['Origin']=origin
            return urlopen(Request(base+route,data=json.dumps(body).encode(),headers=headers))
        try:
            with urlopen(base+'/api/setup') as r:
                info=json.load(r)
            self.assertFalse((self.home/'AGENTS.md').exists())
            claude_home=self.root/'http claude'
            with post('/api/setup/preview',{'client':'claude','path':str(claude_home)}) as r:
                claude=json.load(r)
            self.assertEqual(claude['filename'],'CLAUDE.md')
            with post('/api/setup/install',{'client':'claude','path':claude['path'],'revision':claude['revision']}) as r:
                self.assertTrue(json.load(r)['updated'])
            self.assertIn(str(self.library),(claude_home/'CLAUDE.md').read_text())
            with post('/api/setup/install',{'path':info['path'],'revision':info['revision']}) as r:
                self.assertTrue(json.load(r)['updated'])
            self.assertIn(str(self.library),(self.home/'AGENTS.md').read_text())
            with self.assertRaises(HTTPError) as e:
                post('/api/setup/install',{'revision':info['revision']},'https://evil.example')
            self.assertEqual(e.exception.code,403)
        finally:
            http.shutdown();http.server_close();thread.join();server.DATA=original

if __name__=='__main__':
    unittest.main()
