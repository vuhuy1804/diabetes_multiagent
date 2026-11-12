"""Phase 6 report integration: Coordinator -> Explanation, no HTTP or live services."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents.explanation_agent import ExplanationAgent
from agents.patient_data_agent import PatientDataAgent
from agents.rule_based_agent import RuleBasedAgent
from coordinator.coordinator_agent import CoordinatorAgent
from core.contracts import AgentMessage
from core.features import FEATURE_NAMES

FEATURES = {
    'gender': 'Female', 'age': 44, 'hypertension': 0, 'heart_disease': 0,
    'smoking_history': 'never', 'bmi': 27.32, 'HbA1c_level': 5.7, 'blood_glucose_level': 140,
}


class FakeDL:
    def __init__(self, error: bool = False):
        self.error = error
        self.calls = 0

    def run(self, request_id, features):
        self.calls += 1
        if self.error:
            return AgentMessage(request_id, 'dl_prediction', 'error',
                                payload={'error_type': 'model_unavailable'}, version='model-v1')
        return AgentMessage(request_id, 'dl_prediction', 'ok', payload={
            'prediction': 0, 'model_score_class_1': 0.25,
            'score_is_calibrated': False, 'output_kind': 'dataset_label_classification',
            'model_version': 'test-fixture-v1', 'input_feature_names': list(FEATURE_NAMES)}, version='test-fixture-v1')


class FakeKG:
    def __init__(self, error: bool = False, no_evidence: bool = False):
        self.error = error
        self.no_evidence = no_evidence
        self.calls = 0

    def run(self, request_id, question):
        self.calls += 1
        if self.error:
            return AgentMessage(request_id, 'kg_rag', 'error',
                                payload={'error_type': 'neo4j_unavailable'}, version='fixture-kg')
        if self.no_evidence:
            return AgentMessage(request_id, 'kg_rag', 'ok',
                                payload={'response_kind': 'no_evidence', 'retrieved_fact_count': 0}, version='fixture-kg')
        return AgentMessage(request_id, 'kg_rag', 'ok',
                            payload={'response_kind': 'grounded_extractive', 'retrieved_fact_count': 1,
                                     'answer': 'Có nguồn Neo4j.'},
                            evidence=[{'fact_id': 'f01', 'excerpt': 'Dữ kiện tham khảo từ đồ thị Neo4j.',
                                       'source': {'title': 'Overview', 'publisher': 'NIDDK',
                                                  'url': 'https://www.niddk.nih.gov/health-information/diabetes/overview'}}],
                            version='fixture-kg')


class FakeExplanation:
    def __init__(self, response=None, fail=False):
        self.calls = 0
        self.fail = fail
        self.response = response

    def run(self, request_id, workflow):
        self.calls += 1
        if self.fail:
            raise RuntimeError('sensitive details must not leak')
        return self.response


class ReportCoordinatorTests(unittest.TestCase):
    def make(self, *, dl_error=False, kg_error=False, no_evidence=False, explanation=None):
        dl = FakeDL(dl_error)
        kg = FakeKG(error=kg_error, no_evidence=no_evidence)
        exp = explanation if explanation is not None else ExplanationAgent()
        coordinator = CoordinatorAgent(PatientDataAgent(), dl, RuleBasedAgent(), kg, exp)
        return coordinator, dl, kg, exp

    def test_five_stage_workflow_report(self):
        c, dl, kg, exp = self.make()
        result = c.run_with_explanation(features=FEATURES, question='Bệnh tiểu đường có mấy loại?',
                                        question_provided=True)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.payload['workflow_status'], 'completed')
        self.assertTrue(result.payload['report_ready'])
        self.assertEqual([x['agent'] for x in result.payload['steps']],
                         ['patient_data', 'dl_prediction', 'rule_based', 'kg_rag', 'explanation'])
        self.assertEqual(result.payload['explanation_status'], 'ok')
        self.assertEqual(dl.calls, 1)
        self.assertEqual(kg.calls, 1)

    def test_request_id_inherited_from_coordinator(self):
        c, _, _, _ = self.make()
        result = c.run_with_explanation(features=FEATURES, question='Bệnh tiểu đường là gì?',
                                        question_provided=True, request_id='test-one-id')
        self.assertEqual(result.request_id, 'test-one-id')

    def test_explanation_does_not_mutate_source_evidence(self):
        c, _, _, _ = self.make()
        base = c.run(features=FEATURES, question='Bệnh tiểu đường là gì?', question_provided=True)
        baseline = copy.deepcopy(base.evidence)
        from explanation.report_builder import build_report
        build_report(base)
        self.assertEqual(base.evidence, baseline)

    def test_report_citations_match_knowledge_evidence(self):
        c, _, _, _ = self.make()
        result = c.run_with_explanation(features=FEATURES, question='Bệnh tiểu đường là gì?', question_provided=True)
        knowledge = result.payload['report']['sections']['knowledge']
        self.assertEqual(knowledge['facts'][0]['text'], 'Dữ kiện tham khảo từ đồ thị Neo4j.')
        self.assertEqual(knowledge['facts'][0]['citation'], 'K1')
        self.assertIn('K1', [s['citation'] for s in result.payload['report']['sources']])

    def test_report_available_without_question_kg_skipped(self):
        c, _, kg, _ = self.make()
        result = c.run_with_explanation(features=FEATURES)
        self.assertTrue(result.payload['report_ready'])
        self.assertEqual(result.payload['knowledge_status'], 'skipped')
        self.assertEqual(result.payload['report']['sections']['knowledge']['knowledge_status'], 'skipped')
        self.assertEqual(kg.calls, 0)

    def test_no_kg_facts_does_not_invent_sources(self):
        c, _, _, _ = self.make(no_evidence=True)
        result = c.run_with_explanation(features=FEATURES, question='Nguồn tri thức?', question_provided=True)
        self.assertTrue(result.payload['report_ready'])
        self.assertEqual(result.payload['report']['sections']['knowledge']['knowledge_status'], 'no_evidence')

    def test_invalid_patient_skips_explanation(self):
        c, dl, kg, _ = self.make()
        result = c.run_with_explanation(features={**FEATURES, 'bmi': '27,32'})
        self.assertEqual(result.status, 'error')
        self.assertEqual(result.payload['error_type'], 'invalid_patient_data')
        self.assertFalse(result.payload['report_ready'])
        self.assertIsNone(result.payload['report'])
        self.assertEqual(result.payload['steps'][-1]['status'], 'skipped')
        self.assertEqual(dl.calls, 0)
        self.assertEqual(kg.calls, 0)

    def test_invalid_question_skips_explanation(self):
        c, dl, _, _ = self.make()
        result = c.run_with_explanation(features=FEATURES, question='', question_provided=True)
        self.assertEqual(result.payload['error_type'], 'invalid_question')
        self.assertEqual(result.payload['explanation_status'], 'skipped')
        self.assertEqual(dl.calls, 0)

    def test_dl_failure_skips_explanation(self):
        c, _, _, _ = self.make(dl_error=True)
        result = c.run_with_explanation(features=FEATURES)
        self.assertEqual(result.payload['error_type'], 'model_unavailable')
        self.assertEqual(result.payload['explanation_status'], 'skipped')
        self.assertFalse(result.payload['report_ready'])

    def test_kg_failure_skips_explanation_and_retains_partial(self):
        c, _, _, _ = self.make(kg_error=True)
        result = c.run_with_explanation(features=FEATURES, question='Tiểu đường là gì?', question_provided=True)
        self.assertEqual(result.status, 'error')
        self.assertEqual(result.payload['workflow_status'], 'partial')
        self.assertEqual(result.payload['error_type'], 'neo4j_unavailable')
        self.assertIsNotNone(result.payload['results']['dl_prediction'])
        self.assertEqual(result.payload['explanation_status'], 'skipped')

    def test_explanation_error_returns_partial(self):
        stub = FakeExplanation(response=AgentMessage('ignored', 'explanation', 'error',
                                                    payload={'error_type':'invalid_workflow_for_explanation'}))
        # Agent reply must match request id: mismatch is correctly caught as execution error.
        c, _, _, _ = self.make(explanation=stub)
        result = c.run_with_explanation(features=FEATURES)
        self.assertEqual(result.status, 'error')
        self.assertEqual(result.payload['workflow_status'], 'partial')
        self.assertEqual(result.payload['error_type'], 'explanation_execution_error')
        self.assertFalse(result.payload['report_ready'])

    def test_explanation_exception_is_sanitized(self):
        c, _, _, _ = self.make(explanation=FakeExplanation(fail=True))
        result = c.run_with_explanation(features=FEATURES)
        self.assertNotIn('sensitive details', str(result.to_dict()))
        self.assertEqual(result.payload['error_type'], 'explanation_execution_error')

    def test_missing_explanation_agent_fails_closed(self):
        c = CoordinatorAgent(PatientDataAgent(), FakeDL(), RuleBasedAgent(), FakeKG())
        result = c.run_with_explanation(features=FEATURES)
        self.assertEqual(result.payload['error_type'], 'explanation_unavailable')
        self.assertFalse(result.payload['report_ready'])

    def test_legacy_coordinator_run_unchanged(self):
        c, _, _, _ = self.make()
        result = c.run(features=FEATURES)
        self.assertEqual(len(result.payload['steps']), 4)
        self.assertFalse(result.payload['report_ready'])
        self.assertEqual(result.payload['explanation_status'], 'not_implemented')

    def test_not_claiming_monitoring_implemented(self):
        c, _, _, _ = self.make()
        result = c.run_with_explanation(features=FEATURES)
        self.assertEqual(result.payload['monitoring_status'], 'not_implemented')


if __name__ == '__main__':
    unittest.main()
