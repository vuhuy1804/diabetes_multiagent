"""Deterministic KG retrieval v2 tests; no Neo4j server or Flask required."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents.kg_rag_agent import KGRAGAgent
from scripts.evaluate_kg_retrieval_v2 import check_case
from scripts.faq_knowledge_p0 import OfflineRepo
from services.knowledge_service import KnowledgeQueryError, KnowledgeRetrievalService
from services.neo4j_service import Neo4jKnowledgeRepository
import json

ROOT = BACKEND.parent


class RetrievalV2Tests(unittest.TestCase):
    def setUp(self):
        self.repo = OfflineRepo()
        self.service = KnowledgeRetrievalService(self.repo)

    def test_24_contrastive_faq_cases(self):
        cases = json.loads((ROOT / 'data/samples/faq_retrieval_v2.json').read_text(encoding='utf-8'))
        self.assertEqual(len(cases), 24)
        for case in cases:
            with self.subTest(case=case['question']):
                self.assertTrue(check_case(self.service.query(case['question']), case))

    def test_simple_question_does_not_mix_unrelated_topics(self):
        result = self.service.query('Người tiểu đường có ăn cơm được không?')
        self.assertEqual(result['matched_topics'], ['carb_rice'])
        self.assertEqual({e['topic_id'] for e in result['_evidence']}, {'carb_rice'})

    def test_compound_question_balances_two_topics(self):
        result = self.service.query('Ăn cơm và trái cây thế nào?')
        self.assertEqual(result['matched_topics'], ['carb_rice', 'fruits'])
        self.assertEqual([e['topic_id'] for e in result['_evidence']],
                         ['carb_rice', 'fruits', 'carb_rice', 'fruits'])

    def test_source_and_citation_correspond_one_to_one(self):
        result = self.service.query('Bệnh tiểu đường nên ăn gì?')
        self.assertEqual(len(result['_evidence']), result['retrieved_fact_count'])
        self.assertEqual(result['retrieval_method'], 'topic_fact_lexical_v2')
        for index, item in enumerate(result['_evidence'], 1):
            self.assertIn(f"- {item['excerpt']} [Nguồn {index}]", result['answer'])
            self.assertTrue(item['source']['url'].startswith('https://'))

    def test_max_facts_is_enforced_and_invalid_rejected(self):
        result = self.service.query('Bệnh tiểu đường nên ăn gì?', max_facts=2)
        self.assertEqual(len(result['_evidence']), 2)
        for val in (-1, 0, 9, True, '3', 1.5):
            with self.subTest(value=val):
                with self.assertRaises(KnowledgeQueryError):
                    self.service.query('Bệnh tiểu đường nên ăn gì?', max_facts=val)

    def test_current_knowledge_version_is_preserved(self):
        result = self.service.query('Bệnh tiểu đường nên ăn gì?')
        self.assertEqual(result['knowledge_version'], 'demo-kg-v1.3-p1')

    def test_no_medication_dosage_or_unsourced_drug_claims(self):
        for q in ('Metformin là gì?', 'Uống metformin bao nhiêu mg?',
                  'Insulin dùng liều bao nhiêu?', 'Tôi muốn tự tăng liều thuốc tiểu đường'):
            with self.subTest(question=q):
                response = self.service.query(q)
                self.assertEqual(response['response_kind'], 'no_evidence')
                self.assertFalse(response.get('_evidence'))

    def test_unknown_question_returns_no_generic_evidence(self):
        r = self.service.query('Bệnh tiểu đường và thiên thạch Mộc Tinh')
        self.assertEqual(r['response_kind'], 'no_evidence')
        self.assertEqual(r['matched_topics'], [])

    def test_invalid_or_unsourced_rows_are_skipped(self):
        class TamperedRepo(OfflineRepo):
            def evidence_for_topics(self, topic_ids, limit):
                return ([{'fact_id': 'broken', 'topic_id': topic_ids[0],
                          'text': 'Không có nguồn HTTPS', 'source_url': 'http://example.com'}]
                        + super().evidence_for_topics(topic_ids, limit))
        result = KnowledgeRetrievalService(TamperedRepo()).query('Ăn cơm được không?')
        self.assertEqual(result['response_kind'], 'grounded_extractive')
        self.assertTrue(all(e['fact_id'] != 'broken' for e in result['_evidence']))

    def test_all_invalid_rows_do_not_create_answer(self):
        class InvalidRepo(OfflineRepo):
            def evidence_for_topics(self, topic_ids, limit):
                return [{'fact_id': 'bad', 'topic_id': topic_ids[0],
                         'text': 'Lời khuyên thiếu nguồn', 'source_url': 'javascript:alert(1)'}]
        result = KnowledgeRetrievalService(InvalidRepo()).query('Bệnh tiểu đường nên ăn gì?')
        self.assertEqual(result['response_kind'], 'no_evidence')
        self.assertEqual(result['retrieved_fact_count'], 0)

    def test_actual_agent_retains_source_contract(self):
        message = KGRAGAgent(KnowledgeRetrievalService(self.repo)).run('req123', 'Ăn cơm được không?')
        self.assertEqual(message.status, 'ok')
        self.assertEqual(message.agent, 'kg_rag')
        self.assertEqual(message.request_id, 'req123')
        self.assertEqual(len(message.evidence), message.payload['retrieved_fact_count'])
        self.assertNotIn('_evidence', message.payload)

    def test_repository_queries_both_topics_independently(self):
        repo = Neo4jKnowledgeRepository()
        calls = []
        def fake_read(query, params=None):
            calls.append(params)
            return [{'topic_id': params['topic_ids'][0]}]
        repo._read = fake_read
        result = repo.evidence_for_topics(['carb_rice', 'fruits'], limit=15)
        self.assertEqual([p['topic_ids'] for p in calls], [['carb_rice'], ['fruits']])
        self.assertEqual(len(result), 2)
        self.assertEqual([p['limit'] for p in calls], [15, 15])

    def test_retrieval_does_not_write_or_train(self):
        # No dependency on DL model or database write interface.
        self.assertEqual(self.service.query('Đi bộ có lợi gì?')['response_kind'], 'grounded_extractive')


if __name__ == '__main__':
    unittest.main()
