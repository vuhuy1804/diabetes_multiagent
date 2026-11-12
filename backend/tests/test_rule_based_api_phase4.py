"""Flask Phase 4 API tests, no actual Neo4j or model needed."""
from __future__ import annotations
import copy
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app import create_app  # noqa: E402
from core.features import FEATURE_NAMES  # noqa: E402

FEATURES = {
    'gender':'Female','age':44,'hypertension':0,'heart_disease':0,
    'smoking_history':'No Info','bmi':27.32,'HbA1c_level':6.8,'blood_glucose_level':210,
}
PRED = {
    'prediction':0,'model_score_class_1':0.2,'score_is_calibrated':False,
    'output_kind':'dataset_label_classification','model_version':'fixture-for-testing',
    'input_feature_names':list(FEATURE_NAMES),
}


class RuleBasedApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=create_app().test_client()

    def test_health_phase4_and_ready(self):
        body=self.client.get('/api/health').get_json()
        self.assertEqual(body['phase'],'8-monitoring-evaluation')
        self.assertEqual(body['integrations']['rule_based'],'ready')
        self.assertEqual(body['integrations']['patient_data'],'ready')

    def test_agent_catalog_rule_ready(self):
        body=self.client.get('/api/agents/status').get_json()
        states={a['agent']:a['status'] for a in body['agents']}
        self.assertEqual(states['rule_based'],'ready')
        self.assertEqual(states['coordinator'],'ready')
        self.assertEqual(len(states),8)

    def test_get_rules_catalog(self):
        response=self.client.get('/api/rules/catalog')
        self.assertEqual(response.status_code,200)
        body=response.get_json()
        self.assertEqual(body['count'],7)
        self.assertEqual(body['rules'][0]['rule_id'],'RB001')
        self.assertNotIn('features',body)

    def test_evaluate_returns_flags(self):
        response=self.client.post('/api/rules/evaluate',json={'features':FEATURES,'prediction':PRED})
        self.assertEqual(response.status_code,200)
        body=response.get_json()
        self.assertEqual(body['agent'],'rule_based')
        self.assertEqual(body['status'],'ok')
        self.assertEqual(body['payload']['triggered_rules_count'],5)
        self.assertEqual({r['rule_id'] for r in body['payload']['flags']}, {'RB002','RB003','RB004','RB006','RB007'})
        self.assertEqual(len(body['evidence']),5)

    def test_evaluate_input_invalid(self):
        data={'features':{**FEATURES,'bmi':'27,32'},'prediction':PRED}
        response=self.client.post('/api/rules/evaluate',json=data)
        self.assertEqual(response.status_code,400)
        body=response.get_json()
        self.assertEqual(body['payload']['error_type'],'invalid_rule_input')
        self.assertNotIn('27,32',str(body))

    def test_evaluate_rejects_missing_prediction(self):
        self.assertEqual(self.client.post('/api/rules/evaluate',json={'features':FEATURES}).status_code,400)

    def test_nonobject_and_nonjson_request(self):
        self.assertEqual(self.client.post('/api/rules/evaluate',json=['x']).status_code,400)
        self.assertEqual(self.client.post('/api/rules/evaluate',data='plain',content_type='text/plain').status_code,400)

    def test_unicode_and_legacy_endpoints(self):
        response=self.client.post('/api/rules/evaluate',json={'features':FEATURES,'prediction':PRED})
        response.data.decode('ascii')
        self.assertIn('HbA1c', response.get_json()['payload']['flags'][0]['title'])
        self.assertEqual(self.client.post('/api/assess',json={}).status_code,400)
        self.assertEqual(self.client.post('/api/patient/validate',json={'features':FEATURES}).status_code,200)
        self.assertEqual(self.client.post('/api/predict',json={'features':{'age':44}}).status_code,400)
        self.assertEqual(self.client.post('/api/knowledge/query',json={'question':''}).status_code,400)


if __name__=='__main__':
    unittest.main()
