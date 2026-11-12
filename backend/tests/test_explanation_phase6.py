"""Phase 6 unit tests: report builder uses only trusted, cited agent outputs."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents.explanation_agent import ExplanationAgent
from core.contracts import AgentMessage
from explanation.report_builder import ReportInputError, build_report


def workflow(with_question: bool = True, fact_count: int = 1) -> AgentMessage:
    pred = {
        'prediction': 1, 'model_score_class_1': 0.78,
        'score_is_calibrated': False, 'output_kind': 'dataset_label_classification',
        'model_version': 'fixture-model-v1',
    }
    rules = {
        'rules_evaluated': 7, 'review_required': True,
        'triggered_rules_count': 2,
        'flags': [
            {'rule_id': 'RB001', 'title': 'Ví dụ HbA1c', 'severity': 'review',
             'message': 'Đối chiếu giá trị xét nghiệm với bác sĩ, không tự kết luận.',
             'source': {'publisher': 'NIDDK', 'title': 'A1C Test', 'url': 'https://example.org/a1c'}},
            {'rule_id': 'RB007', 'title': 'Điểm chưa hiệu chuẩn', 'severity': 'info',
             'message': 'Điểm mô hình chưa được hiệu chuẩn.',
             'source': {'publisher': 'Project data contract', 'title': 'Feature schema', 'url': None}},
        ],
    }
    kg = None
    evidence = [{'agent': 'rule_based', 'rule_id': 'RB001', 'kind': 'rule_reference'}]
    knowledge_status = 'skipped'
    if with_question:
        knowledge_status = 'ok'
        kg = {'response_kind': 'grounded_extractive' if fact_count else 'no_evidence',
              'retrieved_fact_count': fact_count, 'answer': 'Không sử dụng đoạn này nếu không có evidence.'}
        for i in range(fact_count):
            evidence.append({
                'agent': 'kg_rag', 'fact_id': f'f{i:02d}',
                'excerpt': f'Đoạn tham khảo đã được Neo4j trích xuất số {i}.',
                'source': {'publisher': 'NIDDK / NIH', 'title': 'Diabetes Overview',
                           'url': 'https://www.niddk.nih.gov/health-information/diabetes/overview'},
            })
    return AgentMessage(
        request_id='req-fixture', agent='coordinator', status='ok', version='coordinator-v1',
        payload={
            'workflow_status': 'completed', 'knowledge_status': knowledge_status,
            'results': {'patient_data': {'valid': True}, 'dl_prediction': pred,
                        'rule_based': rules, 'kg_rag': kg},
            'steps': [], 'problems': [],
        }, evidence=evidence,
    )


class ExplanationUnitTests(unittest.TestCase):
    def setUp(self):
        self.w = workflow()
        self.agent = ExplanationAgent()

    def test_success_agent_contract(self):
        msg = self.agent.run('req-fixture', self.w)
        self.assertEqual(msg.status, 'ok')
        self.assertEqual(msg.agent, 'explanation')
        self.assertEqual(msg.request_id, 'req-fixture')
        self.assertEqual(msg.version, 'explanation-template-v1')

    def test_four_ordered_sections(self):
        report = build_report(self.w)
        self.assertEqual(report['section_order'], ['prediction', 'rule_assessment', 'knowledge', 'limitations'])
        self.assertEqual(len(report['sections']), 4)

    def test_prediction_label_distinct_from_diagnosis(self):
        report = build_report(self.w)
        prediction = report['sections']['prediction']
        self.assertEqual(prediction['dataset_label'], 1)
        self.assertIn('nhãn 1', prediction['text'])
        self.assertIn('không phải kết luận chẩn đoán', prediction['text'])

    def test_uncalibrated_score_not_reported_as_disease_probability(self):
        text = build_report(self.w)['text']
        self.assertIn('0.7800', text)
        self.assertIn('chưa được hiệu chuẩn', text)
        self.assertNotIn('78% nguy cơ', text)

    def test_rule_ids_and_severities_retained(self):
        report = build_report(self.w)
        flags = report['sections']['rule_assessment']['flags']
        self.assertEqual([f['rule_id'] for f in flags], ['RB001', 'RB007'])
        self.assertEqual([f['severity'] for f in flags], ['review', 'info'])
        self.assertTrue(report['sections']['rule_assessment']['review_required'])

    def test_reference_labels_resolve_to_sources(self):
        report = build_report(self.w)
        labels = {r['citation'] for r in report['sources']}
        self.assertEqual(labels, {'R1', 'R2', 'K1'})
        self.assertEqual(report['sections']['knowledge']['facts'][0]['citation'], 'K1')
        for label in labels:
            self.assertIn(f'[{label}]', report['text'])

    def test_extracts_kg_fact_verbatim(self):
        report = build_report(self.w)
        self.assertEqual(report['sections']['knowledge']['facts'][0]['text'],
                         'Đoạn tham khảo đã được Neo4j trích xuất số 0.')
        self.assertIn('Đoạn tham khảo đã được Neo4j trích xuất số 0.', report['text'])

    def test_does_not_use_unsupported_kg_answer_text(self):
        report = build_report(self.w)
        self.assertNotIn('Không sử dụng đoạn này nếu không có evidence', report['text'])

    def test_does_not_mutate_coordinator_result(self):
        before = copy.deepcopy(self.w.to_dict())
        build_report(self.w)
        self.assertEqual(self.w.to_dict(), before)

    def test_no_question_explicitly_skips_knowledge(self):
        report = build_report(workflow(with_question=False))
        self.assertEqual(report['sections']['knowledge']['knowledge_status'], 'skipped')
        self.assertEqual(report['sections']['knowledge']['facts'], [])
        self.assertNotIn('K1', {x['citation'] for x in report['sources']})

    def test_no_evidence_is_not_fabricated(self):
        report = build_report(workflow(fact_count=0))
        self.assertEqual(report['sections']['knowledge']['knowledge_status'], 'no_evidence')
        self.assertEqual(report['sections']['knowledge']['facts'], [])

    def test_source_from_internal_rule_has_no_fake_url(self):
        report = build_report(self.w)
        internal = next(x for x in report['sources'] if x['reference_id'] == 'RB007')
        self.assertIsNone(internal['url'])
        self.assertIn('Nguồn nội bộ của project', report['text'])

    def test_medication_dosages_not_created(self):
        report = build_report(self.w)
        self.assertIn('Không có chỉ định thuốc', report['text'])

    def test_failed_coordinator_rejected(self):
        self.w.status = 'error'
        self.assertEqual(self.agent.run('req-fixture', self.w).payload['error_type'],
                         'invalid_workflow_for_explanation')

    def test_partially_completed_workflow_rejected(self):
        self.w.payload['workflow_status'] = 'partial'
        with self.assertRaises(ReportInputError):
            build_report(self.w)

    def test_wrong_request_id_rejected(self):
        self.assertEqual(self.agent.run('req-other', self.w).status, 'error')

    def test_injected_dict_not_accepted_as_workflow(self):
        self.assertEqual(self.agent.run('req-fixture', self.w.to_dict()).status, 'error')

    def test_missing_dl_output_rejected(self):
        self.w.payload['results']['dl_prediction'] = None
        with self.assertRaises(ReportInputError):
            build_report(self.w)

    def test_invalid_dl_score_rejected(self):
        self.w.payload['results']['dl_prediction']['model_score_class_1'] = float('nan')
        with self.assertRaises(ReportInputError):
            build_report(self.w)

    def test_wrong_rule_count_rejected(self):
        self.w.payload['results']['rule_based']['triggered_rules_count'] = 400
        with self.assertRaises(ReportInputError):
            build_report(self.w)

    def test_inconsistent_rule_review_rejected(self):
        self.w.payload['results']['rule_based']['review_required'] = False
        with self.assertRaises(ReportInputError):
            build_report(self.w)

    def test_knowledge_evidence_count_mismatch_rejected(self):
        self.w.payload['results']['kg_rag']['retrieved_fact_count'] = 2
        with self.assertRaises(ReportInputError):
            build_report(self.w)

    def test_unsourced_kg_fact_rejected(self):
        self.w.evidence[-1]['source']['url'] = None
        self.assertEqual(self.agent.run('req-fixture', self.w).status, 'error')

    def test_non_https_kg_fact_rejected(self):
        self.w.evidence[-1]['source']['url'] = 'http://fake.local'
        with self.assertRaises(ReportInputError):
            build_report(self.w)

    def test_malformed_kg_excerpt_rejected(self):
        self.w.evidence[-1]['excerpt'] = ''
        with self.assertRaises(ReportInputError):
            build_report(self.w)

    def test_knowledge_without_matching_result_rejected(self):
        self.w.payload['results']['kg_rag'] = None
        with self.assertRaises(ReportInputError):
            build_report(self.w)

    def test_no_rule_flags_does_not_imply_healthy(self):
        w = workflow(with_question=False)
        rule = w.payload['results']['rule_based']
        rule['flags'] = []
        rule['triggered_rules_count'] = 0
        rule['review_required'] = False
        report = build_report(w)
        self.assertIn('không có nghĩa', report['text'])
        self.assertEqual(report['sections']['rule_assessment']['flags'], [])

    def test_vietnamese_roundtrip(self):
        import json
        data = json.loads(json.dumps(build_report(self.w), ensure_ascii=True))
        self.assertIn('BÁO CÁO THAM KHẢO', data['text'])


if __name__ == '__main__':
    unittest.main()
