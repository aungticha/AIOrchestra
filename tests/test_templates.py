import json
from pathlib import Path
import tempfile
import unittest
import live_agents
import server
import task_templates
import team_paths

class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.original=server.DATA
        self.root=Path(self.tmp.name)
        server.DATA=self.root/'workspace'

    def tearDown(self):
        server.DATA=self.original
        self.tmp.cleanup()

    def test_arbitrary_team_ids_roundtrip_and_portable_paths(self):
        names=['ทีมค้นคว้า 01','Studio A','A/B : "visual" <team>','../outside','CON','con','a'*100]
        for index,name in enumerate(names):
            server.create_team(name,'ชื่อทีม '+str(index),'Description',category='research',mode='auto')
            folder=server.teamdir(name)
            self.assertTrue(folder.is_relative_to(server.DATA.resolve()/'teams'))
            self.assertLessEqual(len(folder.name),70)
            self.assertNotIn('/',folder.name)
        state=server.state()
        self.assertEqual({t['id'] for t in state['teams']},set(names))
        self.assertEqual(len({t['folder'] for t in state['teams']}),len(names))
        for t in state['teams']:
            self.assertEqual(t['workType'],'research')
            self.assertEqual(t['routingMode'],'auto')
            self.assertIn('web-search',t['requiredCapabilities'])
        self.assertFalse((self.root/'outside').exists())
        with self.assertRaises(ValueError): server.create_team(names[0],'Duplicate','')

    def test_old_folders_keep_their_paths(self):
        folder=server.DATA/'teams'/'marketing'
        folder.mkdir(parents=True)
        (folder/'README.md').write_text('# Marketing')
        (folder/'RULES.md').write_text('# Rules')
        self.assertEqual(server.teamdir('marketing'),folder.resolve())
        item=server.state()['teams'][0]
        self.assertEqual(item['id'],'marketing')
        self.assertEqual(item['workType'],'general')
        self.assertEqual(item['routingMode'],'recommended')

    def test_custom_team_works_with_export_and_live_reports(self):
        name='ทีมภาพ & "Studio A"'
        server.create_team(name,'Visual studio','Images',category='graphics')
        server.write(server.document(name,'agent','art-director'),server.frontmatter('art-director','Design images','# Role'))
        server.write(server.document(name,'skill','image-review'),server.frontmatter('image-review','Review images','# Review'))
        exported=server.export_files(name,'codex')
        self.assertIn('GPT Image',exported['AGENTS.md'])
        self.assertIn('.agents/skills/image-review/SKILL.md',exported)
        live_agents.report(server.DATA,{'engine':'Claude','session':'visual-1','team':name,'agent':'art-director','project':str(self.root),'event':'selected'})
        live_agents.report(server.DATA,{'engine':'Claude','session':'visual-1','team':name,'agent':'art-director','project':str(self.root),'event':'skill','skill':'image-review'})
        snap=live_agents.snapshot(server.DATA)
        self.assertEqual(snap['activeTeams'],{name:1})

    def test_categories_and_recommendations_match_capabilities(self):
        for category in task_templates.TEMPLATES:
            for model_id in category['models']:
                self.assertTrue(set(category['capabilities']).issubset(task_templates.MODELS[model_id]['capabilities']))
            self.assertTrue(task_templates.defaults(category['id'])['recommendationOnly'])
        with self.assertRaises(ValueError): task_templates.defaults('missing')
        with self.assertRaises(ValueError): task_templates.defaults('general','missing')
        for bad in ('','  ','x\n','x'*129):
            with self.assertRaises(ValueError): team_paths.team_id(bad)

if __name__=='__main__': unittest.main()
