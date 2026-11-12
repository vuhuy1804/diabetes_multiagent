"""HTTP tests for trusted /api/report/generate (mocked Coordinator, no model/Neo4j)."""
from __future__ import annotations

import copy
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
        'gender': 'Female', 'age': 44, 'hypertension': 0, 'heart_disease': 0,
        'smoking_history': 'never', 'bmi': 27.32, 'HbA1c_level': 5.7,
        'blood_glucose_level': 140,
    },
    'question': 'Bệnh tiểu đường là gì?',
}


def fake_result(status='ok', error_type=None, workflow_status='completed'):
    ready = status == 'ok'
    return AgentMessage('req-report-unit', 'coordinator', status, version='coordinator-v1',
                        payload={
                            'workflow_status': workflow_status,
                            'error_type': error_type,
                            'report_ready': ready,
                            'explanation_status': 'ok' if ready else 'skipped',
                            'monitoring_status': 'not_implemented',
                            'report': {'title': 'Báo cáo có dấu tiếng Việt',
                                       'report_kind': 'educational_evidence_grounded_not_diagnosis',
                                       'sections': {'knowledge': {'facts': []}}} if ready else None,
                            'steps': [{'agent': 'explanation', 'status': 'ok' if ready else 'skipped'}],
                            'results': {}, 'problems': [],
                        })


class ExplanationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def test_health_and_agent_catalog_phase6(self):
        resp = self.client.get('/api/health')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body['phase'], '8-monitoring-evaluation')
        self.assertEqual(body['integrations']['explanation'], 'ready')
        self.assertEqual(body['integrations']['monitoring'], 'ready')
        agents = self.client.get('/api/agents/status').get_json()
        self.assertEqual(agents['count'], 8)
        states = {a['agent']: a['status'] for a in agents['agents']}
        self.assertEqual(states['explanation'], 'ready')
        self.assertEqual(states['monitoring'], 'ready')
        self.assertEqual(states['rl'], 'not_implemented')

    def test_generate_ok_and_safe_contract(self):
        with patch.object(routes._coordinator, 'run_with_explanation', return_value=fake_result()) as run:
            response = self.client.post('/api/report/generate', json=DATA)
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result['payload']['report_ready'])
        self.assertEqual(result['agent'], 'coordinator')
        self.assertIn('disclaimer', result)
        self.assertEqual(run.call_args.kwargs['question'], DATA['question'])

    def test_question_is_optional(self):
        with patch.object(routes._coordinator, 'run_with_explanation', return_value=fake_result()) as run:
            response = self.client.post('/api/report/generate', json={'features': DATA['features']})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(run.call_args.kwargs['question_provided'])

    def test_array_body_rejected_without_calling_coordinator(self):
        with patch.object(routes._coordinator, 'run_with_explanation') as run:
            response = self.client.post('/api/report/generate', json=['no'])
        self.assertEqual(response.status_code, 400)
        run.assert_not_called()

    def test_plaintext_rejected(self):
        response = self.client.post('/api/report/generate', data='hello', content_type='text/plain')
        self.assertEqual(response.status_code, 400)

    def test_cannot_inject_model_prediction(self):
        with patch.object(routes._coordinator, 'run_with_explanation') as run:
            response = self.client.post('/api/report/generate', json={**DATA, 'prediction': {'prediction': 1}})
        self.assertEqual(response.status_code, 400)
        run.assert_not_called()

    def test_cannot_inject_prepared_report_or_sources(self):
        for key in ('evidence', 'report', 'rule_flags', 'steps', 'request_id'):
            with self.subTest(key=key):
                with patch.object(routes._coordinator, 'run_with_explanation') as run:
                    response = self.client.post('/api/report/generate', json={**DATA, key: {}})
                self.assertEqual(response.status_code, 400)
                run.assert_not_called()

    def test_invalid_patient_returns_400(self):
        with patch.object(routes._coordinator, 'run_with_explanation',
                          return_value=fake_result('error', 'invalid_patient_data', 'failed')):
            response = self.client.post('/api/report/generate', json=DATA)
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(response.get_json()['payload']['report'])

    def test_invalid_question_returns_400(self):
        with patch.object(routes._coordinator, 'run_with_explanation',
                          return_value=fake_result('error', 'invalid_question', 'failed')):
            response = self.client.post('/api/report/generate', json=DATA)
        self.assertEqual(response.status_code, 400)

    def test_dl_unavailable_returns_503(self):
        with patch.object(routes._coordinator, 'run_with_explanation',
                          return_value=fake_result('error', 'model_unavailable', 'failed')):
            response = self.client.post('/api/report/generate', json=DATA)
        self.assertEqual(response.status_code, 503)

    def test_neo4j_failure_returns_503_no_fabricated_report(self):
        with patch.object(routes._coordinator, 'run_with_explanation',
                          return_value=fake_result('error', 'neo4j_unavailable', 'partial')):
            response = self.client.post('/api/report/generate', json=DATA)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()['payload']['report_ready'])

    def test_explanation_unavailable_returns_503(self):
        with patch.object(routes._coordinator, 'run_with_explanation',
                          return_value=fake_result('error', 'explanation_unavailable', 'partial')):
            response = self.client.post('/api/report/generate', json=DATA)
        self.assertEqual(response.status_code, 503)

    def test_explanation_execution_error_returns_500(self):
        with patch.object(routes._coordinator, 'run_with_explanation',
                          return_value=fake_result('error', 'explanation_execution_error', 'partial')):
            response = self.client.post('/api/report/generate', json=DATA)
        self.assertEqual(response.status_code, 500)

    def test_windows_5_1_unicode_fix_retained(self):
        with patch.object(routes._coordinator, 'run_with_explanation', return_value=fake_result()):
            resp = self.client.post('/api/report/generate', json=DATA)
        self.assertEqual(resp.status_code, 200)
        resp.data.decode('ascii')
        self.assertEqual(resp.get_json()['payload']['report']['title'], 'Báo cáo có dấu tiếng Việt')

    def test_original_workflow_uses_old_run(self):
        with patch.object(routes._coordinator, 'run', return_value=fake_result()) as run:
            resp = self.client.post('/api/workflow/run', json=DATA)
        self.assertEqual(resp.status_code, 200)
        run.assert_called_once()

    def test_full_assess_stays_501_until_monitoring(self):
        resp = self.client.post('/api/assess', json={**DATA, 'report': {'fake': True}})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()['error_type'], 'invalid_request')

    def test_existing_rule_and_validation_apis_unaffected(self):
        self.assertEqual(self.client.get('/api/rules/catalog').get_json()['count'], 7)
        self.assertEqual(self.client.post('/api/patient/validate',json={'features':DATA['features']}).status_code,200)
        self.assertEqual(self.client.post('/api/predict',json={'features':{'age':44}}).status_code,400)
        self.assertEqual(self.client.post('/api/knowledge/query',json={'question':''}).status_code,400)


if __name__ == '__main__':
    unittest.main()
