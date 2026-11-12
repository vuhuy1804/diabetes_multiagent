"""Flask API tests for Phase 5 (mocked Coordinator; no actual Neo4j/model needed)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import create_app
from api import routes
from core.contracts import AgentMessage

DATA = {
    'features': {
        'gender': 'Female', 'age': 44, 'hypertension': 0,
        'heart_disease': 0, 'smoking_history': 'never', 'bmi': 27.32,
        'HbA1c_level': 5.7, 'blood_glucose_level': 140,
    },
    'question': 'Bệnh tiểu đường có mấy loại chính?',
}


def fake_result(status='ok', error_type=None, workflow_status='completed'):
    return AgentMessage('req_http_test', 'coordinator', status, payload={
        'workflow_status': workflow_status, 'error_type': error_type,
        'results': {'patient_data': {}, 'dl_prediction': {}, 'rule_based': {}, 'kg_rag': {}},
        'steps': [], 'report_ready': False,
    }, version='coordinator-v1')


class Phase5ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def test_health_phase5_and_coordinator_ready(self):
        with patch.object(routes._kg_service, 'readiness', return_value='ready'), \
             patch.object(routes._dl_service, 'readiness', return_value='ready'):
            body = self.client.get('/api/health').get_json()
        self.assertEqual(body['phase'], '8-monitoring-evaluation')
        self.assertEqual(body['integrations']['coordinator'], 'ready')
        self.assertEqual(body['integrations']['neo4j'], 'ready')

    def test_agent_catalog_coordinator_ready_others_later(self):
        body = self.client.get('/api/agents/status').get_json()
        states = {x['agent']:x['status'] for x in body['agents']}
        self.assertEqual(len(states), 8)
        self.assertEqual(states['coordinator'], 'ready')
        self.assertEqual(states['explanation'], 'ready')
        self.assertEqual(states['monitoring'], 'ready')
        self.assertEqual(states['rl'], 'not_implemented')

    def test_workflow_success_http200_and_disclaimer(self):
        with patch.object(routes._coordinator, 'run', return_value=fake_result()) as run:
            response = self.client.post('/api/workflow/run', json=DATA)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['agent'], 'coordinator')
        self.assertIn('disclaimer', response.get_json())
        self.assertEqual(run.call_args.kwargs['question'], DATA['question'])
        self.assertTrue(run.call_args.kwargs['question_provided'])

    def test_question_optional(self):
        with patch.object(routes._coordinator, 'run', return_value=fake_result()) as run:
            self.assertEqual(self.client.post('/api/workflow/run', json={'features': DATA['features']}).status_code, 200)
        self.assertFalse(run.call_args.kwargs['question_provided'])

    def test_invalid_body_json_array_rejected_before_coord(self):
        with patch.object(routes._coordinator, 'run') as run:
            response = self.client.post('/api/workflow/run', json=['not-object'])
        self.assertEqual(response.status_code, 400)
        run.assert_not_called()

    def test_non_json_body_rejected(self):
        self.assertEqual(self.client.post('/api/workflow/run', data='bad', content_type='text/plain').status_code, 400)

    def test_user_cannot_inject_prediction(self):
        with patch.object(routes._coordinator, 'run') as run:
            response = self.client.post('/api/workflow/run', json={**DATA, 'prediction': {'prediction': 1}})
        self.assertEqual(response.status_code, 400)
        run.assert_not_called()

    def test_patient_invalid_400(self):
        with patch.object(routes._coordinator, 'run', return_value=fake_result('error', 'invalid_patient_data', 'failed')):
            response = self.client.post('/api/workflow/run', json=DATA)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['payload']['error_type'], 'invalid_patient_data')

    def test_question_invalid_400(self):
        with patch.object(routes._coordinator, 'run', return_value=fake_result('error', 'invalid_question', 'failed')):
            self.assertEqual(self.client.post('/api/workflow/run', json=DATA).status_code, 400)

    def test_dl_down_503(self):
        with patch.object(routes._coordinator, 'run', return_value=fake_result('error', 'model_unavailable', 'failed')):
            self.assertEqual(self.client.post('/api/workflow/run', json=DATA).status_code, 503)

    def test_kg_down_503_partial(self):
        with patch.object(routes._coordinator, 'run', return_value=fake_result('error', 'neo4j_unavailable', 'partial')):
            response = self.client.post('/api/workflow/run', json=DATA)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['payload']['workflow_status'], 'partial')

    def test_internal_error_500(self):
        with patch.object(routes._coordinator, 'run', return_value=fake_result('error', 'agent_execution_error', 'failed')):
            self.assertEqual(self.client.post('/api/workflow/run', json=DATA).status_code, 500)

    def test_unicode_wire_compatible_with_windows_powershell(self):
        with patch.object(routes._coordinator, 'run', return_value=fake_result()):
            response = self.client.post('/api/workflow/run', json=DATA)
        response.data.decode('ascii')  # Phase 2 Windows fix: ASCII JSON escapes

    def test_full_assess_still_501_and_legacy_rule(self):
        self.assertEqual(self.client.post('/api/assess', json={**DATA, 'prediction': {'fake': True}}).status_code, 400)
        self.assertEqual(self.client.get('/api/rules/catalog').get_json()['count'], 7)
        self.assertEqual(self.client.post('/api/predict', json={'features':{'age': 44}}).status_code, 400)
        self.assertEqual(self.client.post('/api/patient/validate', json={'features': DATA['features']}).status_code, 200)
        self.assertEqual(self.client.post('/api/knowledge/query', json={'question': ''}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
