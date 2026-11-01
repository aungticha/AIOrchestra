import io
import os
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile
import server

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = server.DATA
        server.DATA = Path(self.tmp.name)
        server.create_team('marketing', 'Marketing', 'Team description')
        self.agent = server.frontmatter('writer', 'Write content', '# Role\nWrite verified content')
        self.skill = server.frontmatter('review', 'Review content', '# Steps\nCheck sources')
        server.write(server.document('marketing','agent','writer'), self.agent)
        server.write(server.document('marketing','skill','review'), self.skill)

    def tearDown(self):
        server.DATA = self.original
        self.tmp.cleanup()

    def test_markdown_persistence_and_duplicate_protection(self):
        self.assertEqual(server.state()['teams'][0]['agents'][0]['content'], self.agent)
        with self.assertRaises(ValueError):
            server.create_team('marketing', 'Duplicate', '')
        self.assertIn('Marketing', server.read(server.teamdir('marketing')/'README.md'))

    def test_paths_and_symlinks_cannot_escape_workspace(self):
        for value in ('../escape','/tmp','UPPER','a/b','x\n'):
            with self.assertRaises(ValueError):
                server.document(value,'rules')
        try:
            (server.teamdir('marketing')/'agents'/'escape.md').symlink_to(Path(self.tmp.name).parent/'outside.md')
        except OSError:
            if os.name == 'nt':
                self.skipTest('Windows symlink privilege unavailable; path validation completed')
            raise
        with self.assertRaises(ValueError):
            server.document('marketing','agent','escape')

    def test_required_metadata(self):
        server.validate(self.skill,'skill','review')
        for content in ('# no metadata', self.skill.replace('review','other'), self.skill.replace('Review content','')):
            with self.assertRaises(ValueError):
                server.validate(content,'skill','review')

    def test_exports_include_shared_rules_and_skills(self):
        rules=server.read(server.teamdir('marketing')/'RULES.md')
        codex=server.export_files('marketing','codex','writer')
        self.assertIn(rules,codex['AGENTS.md'])
        self.assertIn(self.agent,codex['AGENTS.md'])
        self.assertEqual(codex['.agents/skills/review/SKILL.md'],self.skill)
        claude=server.export_files('marketing','claude')
        self.assertIn(rules,claude['.claude/agents/writer.md'])
        self.assertIn(self.skill,claude['.claude/agents/writer.md'])
        portable=server.export_files('marketing','portable')['CONTEXT.md']
        self.assertIn(self.skill,portable)
        with self.assertRaises(ValueError):
            server.export_files('marketing','codex','missing')

    def test_http_save_zip_and_cross_origin_rejection(self):
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        worker=threading.Thread(target=http.serve_forever,daemon=True)
        worker.start()
        base=f'http://127.0.0.1:{http.server_port}'
        def post(path,body,origin=None):
            headers={'Content-Type':'application/json'}
            if origin: headers['Origin']=origin
            return urlopen(Request(base+path,data=json.dumps(body).encode(),headers=headers))
        try:
            self.assertEqual(urlopen(base).status,200)
            updated='# Updated rules\n\nVerify all claims.'
            with post('/api/save',{'team':'marketing','kind':'rules','content':updated}) as r:
                self.assertEqual(json.load(r)['teams'][0]['rules'],updated)
            with post('/api/export',{'team':'marketing','target':'codex'}) as r:
                with zipfile.ZipFile(io.BytesIO(r.read())) as z:
                    self.assertIn(updated,z.read('AGENTS.md').decode())
            with self.assertRaises(HTTPError) as e:
                post('/api/save',{'team':'marketing','kind':'rules','content':'bad'},'https://evil.example')
            self.assertEqual(e.exception.code,403)
            self.assertEqual(server.read(server.teamdir('marketing')/'RULES.md'),updated)
            with self.assertRaises(HTTPError) as e:
                post('/api/create',{'team':'marketing','kind':'agent','id':'writer','content':self.agent})
            self.assertEqual(e.exception.code,400)
        finally:
            http.shutdown()
            http.server_close()
            worker.join()

if __name__ == '__main__':
    unittest.main()
