import unittest
from unittest.mock import patch
import provider_routing


class ProviderRoutingTests(unittest.TestCase):
    def test_single_connected_provider_replaces_engine_and_foreign_model(self):
        self.assertEqual(provider_routing.resolve('Claude','sonnet',{'Codex':True,'Claude':False}),('Codex',''))
        self.assertEqual(provider_routing.resolve('Codex','gpt-6.1-sol',{'Codex':False,'Claude':True}),('Claude',''))

    def test_same_provider_keeps_model(self):
        self.assertEqual(provider_routing.resolve('Claude','opus',{'Codex':False,'Claude':True}),('Claude','opus'))

    def test_both_or_unknown_connections_preserve_workflow(self):
        for connected in [dict(Codex=True,Claude=True),dict(Codex=False,Claude=False)]:
            self.assertEqual(provider_routing.resolve('Claude','sonnet',connected),('Claude','sonnet'))

    def test_only_verified_dashboard_statuses_are_connected(self):
        with patch('quota.cached_codex',return_value={'status':'ok'}),patch('quota.claude_status',return_value={'status':'stale'}):
            self.assertEqual(provider_routing.connections('workspace'),dict(Codex=True,Claude=False))
        with patch('quota.cached_codex',return_value={'status':'login_required'}),patch('quota.claude_status',return_value={'status':'ok'}):
            self.assertEqual(provider_routing.connections('workspace'),dict(Codex=False,Claude=True))
