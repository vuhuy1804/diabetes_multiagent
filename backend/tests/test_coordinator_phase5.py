"""Phase 5 Coordinator unit tests: actual Patient Data + Rule agents, fake DL/KG.

Fixtures simulate the model/graph ONLY inside tests. Live smoke tests in README
and GIAI_DOAN_5_HUONG_DAN.md use the real trained model and Neo4j.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from coordinator.coordinator_agent import CoordinatorAgent
from core.contracts import AgentMessage
from core.features import FEATURE_NAMES
from agents.patient_data_agent import PatientDataAgent
from agents.rule_based_agent import RuleBasedAgent

FEATURES = {
    'gender': ' female ', 'age': '44', 'hypertension': '0', 'heart_disease': 0,
    'smoking_history': ' NEVER ', 'bmi': '27.32', 'HbA1c_level': '6.8',
    'blood_glucose_level': '210',
}
PREDICTED = {
    'prediction': 0, 'model_score_class_1': 0.2, 'score_is_calibrated': False,
    'output_kind': 'dataset_label_classification', 'model_version': 'TEST_FIXTURE_NOT_REAL_MODEL',
    'input_feature_names': list(FEATURE_NAMES),
}


class FakeAgent:
    def __init__(self, name, *, mode='ok'):
        self.name = name
        self.mode = mode
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.mode == 'raise':
            raise RuntimeError('exception mentions should never reach API')
        if self.mode == 'wrong_agent':
            return AgentMessage(kwargs['request_id'], 'someone_else', 'ok')
        if self.mode == 'wrong_request':
            return AgentMessage('wrong-request-id', self.name, 'ok')
        if self.mode == 'not_message':
            return 'invalid'
        if self.mode == 'error':
            return AgentMessage(kwargs['request_id'], self.name, 'error',
                                payload={'error_type': 'neo4j_unavailable' if self.name == 'kg_rag' else 'model_unavailable'},
                                error='Dependency unavailable')
        if self.name == 'dl_prediction':
            payload = copy.deepcopy(PREDICTED)
        else:
            payload = {
                'question': kwargs['question'], 'response_kind': 'grounded_extractive',
                'answer': 'Minh họa truy xuất có nguồn.', 'retrieved_fact_count': 1,
                'knowledge_version': 'TEST_FIXTURE_KG',
            }
        evidence = ([{'kind': 'kg_fact', 'fact_id': 'demo1',
                      'source': {'url': 'https://www.niddk.nih.gov/example'}}]
                    if self.name == 'kg_rag' else [])
        return AgentMessage(kwargs['request_id'], self.name, 'ok',
                            payload=payload, evidence=evidence, version='unit-fixture-v1')


class CoordinatorPhase5Tests(unittest.TestCase):
    def setUp(self):
        self.dl = FakeAgent('dl_prediction')
        self.kg = FakeAgent('kg_rag')
        self.coord = CoordinatorAgent(PatientDataAgent(), self.dl,
                                      RuleBasedAgent(), self.kg)

    def run_workflow(self, **kwargs):
        return self.coord.run(features=copy.deepcopy(FEATURES), **kwargs)

    def test_full_success_runs_four_agents_in_order(self):
        result = self.run_workflow(question='Bệnh tiểu đường có mấy loại chính?', question_provided=True)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.payload['workflow_status'], 'completed')
        self.assertEqual([s['agent'] for s in result.payload['steps']], list(CoordinatorAgent.ORDER))
        self.assertEqual([s['status'] for s in result.payload['steps']], ['ok'] * 4)

    def test_common_request_id_travels_to_dl_and_kg(self):
        result = self.run_workflow(request_id='req-123', question='Tiểu đường type 2?', question_provided=True)
        self.assertEqual(result.request_id, 'req-123')
        self.assertEqual(self.dl.calls[0]['request_id'], 'req-123')
        self.assertEqual(self.kg.calls[0]['request_id'], 'req-123')

    def test_ordered_normalization_sent_to_dl(self):
        self.run_workflow()
        got = self.dl.calls[0]['features']
        self.assertEqual(tuple(got.keys()), FEATURE_NAMES)
        self.assertEqual(got['gender'], 'Female')
        self.assertEqual(got['smoking_history'], 'never')
        self.assertEqual(got['age'], 44.0)
        self.assertEqual(got['hypertension'], 0)

    def test_rule_input_from_trusted_dl(self):
        result = self.run_workflow()
        self.assertEqual(result.payload['results']['rule_based']['rules_evaluated'], 7)
        self.assertEqual(result.payload['results']['rule_based']['model_version'], 'TEST_FIXTURE_NOT_REAL_MODEL')

    def test_no_question_skips_kg_not_failing(self):
        result = self.run_workflow()
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.payload['knowledge_status'], 'skipped')
        self.assertEqual(result.payload['workflow_status'], 'completed')
        self.assertIsNone(result.payload['results']['kg_rag'])
        self.assertEqual(self.kg.calls, [])
        self.assertEqual(result.payload['steps'][-1]['status'], 'skipped')

    def test_question_provided_uses_kg(self):
        q = 'Các loại bệnh tiểu đường?'
        result = self.run_workflow(question=q, question_provided=True)
        self.assertEqual(self.kg.calls[0]['question'], q)
        self.assertEqual(result.payload['results']['kg_rag']['retrieved_fact_count'], 1)

    def test_invalid_patient_prevents_all_downstream(self):
        bad = copy.deepcopy(FEATURES)
        del bad['bmi']
        result = self.coord.run(features=bad, question='types?', question_provided=True)
        self.assertEqual(result.status, 'error')
        self.assertEqual(result.payload['error_type'], 'invalid_patient_data')
        self.assertEqual(result.payload['workflow_status'], 'failed')
        self.assertEqual([s['status'] for s in result.payload['steps']], ['error', 'skipped', 'skipped', 'skipped'])
        self.assertFalse(self.dl.calls)
        self.assertFalse(self.kg.calls)

    def test_invalid_raw_features_input_not_object(self):
        result = self.coord.run(features=['oops'])
        self.assertEqual(result.payload['error_type'], 'invalid_patient_data')

    def test_invalid_question_fails_before_costly_model(self):
        result = self.run_workflow(question=' ', question_provided=True)
        self.assertEqual(result.status, 'error')
        self.assertEqual(result.payload['error_type'], 'invalid_question')
        self.assertEqual([s['status'] for s in result.payload['steps']], ['ok', 'skipped', 'skipped', 'error'])
        self.assertFalse(self.dl.calls)
        self.assertFalse(self.kg.calls)

    def test_question_wrong_type_is_invalid(self):
        result = self.run_workflow(question=123, question_provided=True)
        self.assertEqual(result.payload['error_type'], 'invalid_question')

    def test_kg_unavailable_returns_partial_not_success(self):
        self.kg.mode = 'error'
        result = self.run_workflow(question='Bệnh tiểu đường là gì?', question_provided=True)
        self.assertEqual(result.status, 'error')
        self.assertEqual(result.payload['workflow_status'], 'partial')
        self.assertEqual(result.payload['error_type'], 'neo4j_unavailable')
        self.assertIsNotNone(result.payload['results']['dl_prediction'])
        self.assertIsNotNone(result.payload['results']['rule_based'])
        self.assertIsNone(result.payload['results']['kg_rag'])

    def test_dl_unavailable_aborts_rules_and_kg(self):
        self.dl.mode = 'error'
        result = self.run_workflow(question='Tiểu đường là gì?', question_provided=True)
        self.assertEqual(result.status, 'error')
        self.assertEqual(result.payload['error_type'], 'model_unavailable')
        self.assertEqual(result.payload['workflow_status'], 'failed')
        self.assertEqual([t['status'] for t in result.payload['steps']], ['ok', 'error', 'skipped', 'skipped'])
        self.assertEqual(self.kg.calls, [])

    def test_dl_runtime_exception_is_sanitized(self):
        self.dl.mode = 'raise'
        result = self.run_workflow()
        self.assertEqual(result.payload['error_type'], 'agent_execution_error')
        self.assertNotIn('exception mentions', json.dumps(result.to_dict()))

    def test_kg_runtime_exception_sanitized_and_partial(self):
        self.kg.mode = 'raise'
        result = self.run_workflow(question='Tiểu đường là gì?', question_provided=True)
        self.assertEqual(result.payload['workflow_status'], 'partial')
        self.assertEqual(result.payload['error_type'], 'agent_execution_error')

    def test_wrong_agent_identity_is_rejected(self):
        self.dl.mode = 'wrong_agent'
        self.assertEqual(self.run_workflow().payload['error_type'], 'agent_execution_error')

    def test_wrong_request_id_is_rejected(self):
        self.dl.mode = 'wrong_request'
        self.assertEqual(self.run_workflow().payload['error_type'], 'agent_execution_error')

    def test_non_message_agent_return_is_rejected(self):
        self.dl.mode = 'not_message'
        self.assertEqual(self.run_workflow().payload['error_type'], 'agent_execution_error')

    def test_evidence_preserves_origin(self):
        result = self.run_workflow(question='Tiểu đường là gì?', question_provided=True)
        self.assertTrue(any(x.get('agent') == 'kg_rag' and x.get('fact_id') == 'demo1' for x in result.evidence))
        self.assertTrue(any(x.get('agent') == 'rule_based' and x.get('rule_id') for x in result.evidence))

    def test_trace_metadata_does_not_contain_patient_features_or_question(self):
        q = 'Bệnh tiểu đường type 1 đặc biệt?'
        result = self.run_workflow(question=q, question_provided=True)
        trace_text = json.dumps(result.payload['steps'], ensure_ascii=False)
        self.assertNotIn('HbA1c', trace_text)
        self.assertNotIn(q, trace_text)
        self.assertNotIn('27.32', trace_text)
        self.assertNotIn('210', trace_text)

    def test_result_fields_stay_separate(self):
        result = self.run_workflow(question='Tiểu đường là gì?', question_provided=True)
        r = result.payload['results']
        self.assertEqual(set(r), set(CoordinatorAgent.ORDER))
        self.assertNotIn('flags', r['dl_prediction'])
        self.assertNotIn('prediction', r['kg_rag'])

    def test_no_diagnosis_no_explanation_yet(self):
        result = self.run_workflow()
        self.assertEqual(result.payload['report_ready'], False)
        self.assertEqual(result.payload['explanation_status'], 'not_implemented')
        self.assertEqual(result.payload['monitoring_status'], 'not_implemented')
        self.assertFalse(any('diagnosed' in line for line in result.payload['limitations']))

    def test_request_id_generated_nonempty(self):
        result = self.run_workflow()
        self.assertTrue(result.request_id)
        self.assertEqual(result.agent, 'coordinator')
        self.assertEqual(result.version, 'coordinator-v1')

    def test_outcome_valid_json_serializable(self):
        result = self.run_workflow(question='Tiểu đường là gì?', question_provided=True)
        wire = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
        self.assertEqual(wire['status'], 'ok')
        self.assertIsInstance(wire['payload']['steps'], list)

    def test_does_not_mutate_input_features(self):
        raw = copy.deepcopy(FEATURES)
        before = copy.deepcopy(raw)
        self.coord.run(features=raw)
        self.assertEqual(raw, before)

    def test_patient_field_issues_remain_available_to_caller(self):
        bad = copy.deepcopy(FEATURES)
        bad['bmi'] = '27,32'
        result = self.coord.run(features=bad)
        self.assertEqual(result.payload['error_type'], 'invalid_patient_data')
        issues = result.payload['problems'][0]['issues']
        self.assertTrue(any(issue['field'] == 'bmi' for issue in issues))
        self.assertNotIn('27,32', json.dumps(result.to_dict()))

    def test_agent_cannot_spoof_evidence_origin(self):
        class SpoofAgent:
            def run(self, request_id, question):
                return AgentMessage(request_id, 'kg_rag', 'ok',
                    payload={'response_kind': 'grounded_extractive'},
                    evidence=[{'agent':'not_kg', 'source':{'url':'https://example.edu'}}])
        self.coord.agents['kg_rag'] = SpoofAgent()
        result = self.run_workflow(question='Các loại tiểu đường?', question_provided=True)
        self.assertEqual(result.evidence[-1]['agent'], 'kg_rag')

    def test_invalid_evidence_contract_rejected(self):
        class BadEvidenceAgent:
            def run(self, request_id, question):
                return AgentMessage(request_id, 'kg_rag', 'ok',
                    payload={'response_kind':'grounded_extractive'}, evidence=['not-a-dict'])
        self.coord.agents['kg_rag'] = BadEvidenceAgent()
        result = self.run_workflow(question='Các loại tiểu đường?', question_provided=True)
        self.assertEqual(result.payload['error_type'], 'agent_execution_error')
        self.assertEqual(result.payload['workflow_status'], 'partial')

    def test_no_evidence_kg_ok_is_disclosed(self):
        class NoFactsAgent:
            def run(self, request_id, question):
                return AgentMessage(request_id, 'kg_rag', 'ok', payload={
                    'question': question, 'response_kind': 'no_evidence',
                    'answer': 'Không có dữ liệu phù hợp.', 'retrieved_fact_count': 0,
                }, evidence=[], version='test')
        self.coord.agents['kg_rag'] = NoFactsAgent()
        result = self.run_workflow(question='Nội dung không có?', question_provided=True)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.payload['results']['kg_rag']['response_kind'], 'no_evidence')
        self.assertFalse(any(x.get('agent') == 'kg_rag' for x in result.evidence))


if __name__ == '__main__':
    unittest.main()
