"""Regression tests Phase 0/1 + HTTP contracts Phase 2. No Neo4j needed."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app import create_app  # noqa: E402
from api import routes  # noqa: E402
from core.contracts import AgentMessage  # noqa: E402


class ApiPhase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def test_health_returns_200_without_claiming_kg_ready(self):
        with patch.object(routes._kg_service, 'readiness', return_value='not_configured'):
            resp = self.client.get('/api/health')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body['phase'], '8-monitoring-evaluation')
        self.assertEqual(body['integrations']['neo4j'], 'not_configured')
        self.assertIn(body['integrations']['deep_learning'], ('not_configured','ready'))

    def test_agent_catalog_seven_plus_optional_rl(self):
        with patch.object(routes._kg_service, 'readiness', return_value='ready'):
            body = self.client.get('/api/agents/status').get_json()
        self.assertEqual(body['count'], 8)
        statuses = {item['agent']: item['status'] for item in body['agents']}
        self.assertEqual(statuses['kg_rag'], 'ready')
        self.assertIn(statuses['dl_prediction'], ('model_missing','ready'))
        self.assertEqual(statuses['rl'], 'not_implemented')

    def test_predict_still_rejects_incomplete_features(self):
        resp = self.client.post('/api/predict', json={'features':{'age':20}})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()['payload']['error_type'], 'invalid_features')

    def test_knowledge_query_rejects_invalid_question(self):
        resp = self.client.post('/api/knowledge/query', json={'question':''})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()['payload']['error_type'], 'invalid_question')

    def test_knowledge_query_returns_same_agent_contract_and_sources(self):
        fake = AgentMessage('req_unit','kg_rag','ok',
                            payload={'answer':'Có trích nguồn.','response_kind':'grounded_extractive'},
                            evidence=[{'fact_id':'f01','source':{'url':'https://www.niddk.nih.gov'}}],
                            version='demo-kg-v1')
        with patch.object(routes._kg_agent, 'run', return_value=fake):
            resp = self.client.post('/api/knowledge/query', json={'question':'Tiểu đường là gì?'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['agent'], 'kg_rag')
        self.assertEqual(len(resp.get_json()['evidence']), 1)

    def test_unavailable_neo4j_returns_503(self):
        fake = AgentMessage('req_unit','kg_rag','error',
                            payload={'error_type':'neo4j_unavailable'}, version='phase2')
        with patch.object(routes._kg_agent, 'run', return_value=fake):
            self.assertEqual(self.client.post('/api/knowledge/query', json={'question':'Tiểu đường là gì?'}).status_code, 503)

    def test_full_mas_still_501(self):
        self.assertEqual(self.client.post('/api/assess', json={'question':'demo'}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
