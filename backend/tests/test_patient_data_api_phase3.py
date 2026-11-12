"""HTTP-level Patient Data tests using Flask's in-process test client.

No Neo4j instance or trained model required; existing services report readiness only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app import create_app  # noqa: E402

DEMO = {
    "gender": "female", "age": "44", "hypertension": "0",
    "heart_disease": 0, "smoking_history": " Never ", "bmi": "27.32",
    "HbA1c_level": "5.7", "blood_glucose_level": "140",
}


class PatientDataApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def test_success_agent_message(self):
        response = self.client.post('/api/patient/validate', json={"features": DEMO})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['agent'], 'patient_data')
        self.assertEqual(data['payload']['features']['gender'], 'Female')
        self.assertEqual(data['payload']['features']['smoking_history'], 'never')
        self.assertEqual(data['payload']['features']['age'], 44.0)
        self.assertGreater(len(data['payload']['normalizations']), 0)
        self.assertIsInstance(data['request_id'], str)
        self.assertIn('disclaimer', data)

    def test_missing_features_returns_400_and_structured_issues(self):
        response = self.client.post('/api/patient/validate', json={'features': {'age': 45}})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data['agent'], 'patient_data')
        self.assertEqual(data['payload']['error_type'], 'invalid_patient_data')
        self.assertIn('missing_field', {e['code'] for e in data['payload']['issues']})

    def test_json_body_not_object_returns_400(self):
        response = self.client.post('/api/patient/validate', json=['oops'])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['payload']['issues'][0]['code'], 'not_object')

    def test_unicode_survives_http_roundtrip(self):
        response = self.client.post('/api/patient/validate', json={'features': {**DEMO, 'gender': ' không hợp lệ '}})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['status'], 'error')
        response.data.decode('ascii')  # ensure_ascii=True from Phase 2 Windows fix

    def test_health_and_catalog_phase3(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body['phase'], '8-monitoring-evaluation')
        self.assertEqual(body['integrations']['patient_data'], 'ready')
        self.assertIn(body['integrations']['deep_learning'], ('not_configured', 'ready'))
        agents = self.client.get('/api/agents/status').get_json()
        self.assertEqual(agents['count'], 8)
        statuses = {item['agent']: item['status'] for item in agents['agents']}
        self.assertEqual(statuses['patient_data'], 'ready')
        self.assertEqual(statuses['coordinator'], 'ready')

    def test_predict_contract_unchanged_and_assess_still_501(self):
        response = self.client.post('/api/predict', json={'features': {'age': 45}})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['payload']['error_type'], 'invalid_features')
        self.assertEqual(self.client.post('/api/assess', json={}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
