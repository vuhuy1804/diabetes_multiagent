"""P1 regression tests for curated Neo4j expansion and independent FAQ evaluation.

All tests work offline and never touch the user's Neo4j instance or patient data.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from scripts.build_kg_seed import generate, validate
from scripts.neo4j_cli import statements
from scripts.faq_knowledge_p0 import OfflineRepo
from scripts.evaluate_kg_p1 import (
    load_cases, run_evaluation, evaluate_case, is_acceptable, summarize,
)
from services.knowledge_service import KnowledgeRetrievalService
from services.neo4j_service import TOPICS_CYPHER


class KGExpansionP1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / 'data/knowledge/curated_knowledge.json').read_text(encoding='utf-8'))
        cls.repo = OfflineRepo()
        cls.svc = KnowledgeRetrievalService(cls.repo)
        cls.cases = load_cases()

    def test_01_p1_counts(self):
        self.assertEqual(validate(self.data), {
            'topics': 35, 'facts': 137, 'sources': 29, 'relations': 34
        })

    def test_02_existing_fact_ids_and_known_content_remain(self):
        items = {f['id']: f for f in self.data['facts']}
        self.assertTrue({f'f{i:02d}' for i in range(1, 83)}.issubset(items))
        self.assertEqual(items['f03']['topic_id'], 'types')
        self.assertEqual(items['f82']['topic_id'], 'checkups')

    def test_03_55_added_facts_have_unique_ids(self):
        facts = [f for f in self.data['facts'] if f['id'].startswith('f') and f['id'][1:].isdigit() and int(f['id'][1:]) >= 83]
        self.assertEqual(len(facts), 55)
        self.assertEqual(len({f['id'] for f in facts}), 55)
        self.assertEqual(facts[0]['id'], 'f083')
        self.assertEqual(facts[-1]['id'], 'f137')

    def test_04_11_new_topics_each_have_five_facts(self):
        topic_ids = ['insulin_basics', 'eye_health', 'kidney_health', 'foot_health',
                     'heart_health', 'after_gestational', 'sick_days',
                     'sleep_stress', 'daily_living', 'travel_health', 'misconceptions']
        counts = Counter(f['topic_id'] for f in self.data['facts'])
        self.assertEqual(len(topic_ids), 11)
        self.assertTrue(all(counts[t] == 5 for t in topic_ids))

    def test_05_source_provenance_and_https(self):
        sources = {s['id']: s for s in self.data['sources']}
        for fact in self.data['facts']:
            with self.subTest(fact=fact['id']):
                self.assertIn(fact['source_id'], sources)
                self.assertTrue(sources[fact['source_id']]['url'].startswith('https://'))
        self.assertEqual(len(sources), 29)

    def test_06_cypher_seed_matches_curated_json(self):
        script = (ROOT / 'data/knowledge/DB_diabet.cypher').read_text(encoding='utf-8')
        self.assertEqual(generate(self.data), script)
        self.assertGreater(len(statements(script)), 400)

    def test_07_priority_is_bounded_and_written_to_neo4j(self):
        self.assertIn('coalesce(t.priority, 0) AS priority', TOPICS_CYPHER)
        self.assertTrue(all(isinstance(t['priority'], int) and 0 <= t['priority'] <= 100
                            for t in self.data['topics']))
        self.assertGreater(next(t['priority'] for t in self.data['topics'] if t['id'] == 'heart_health'), 0)

    def test_08_90_questions_are_split_into_expected_groups(self):
        counts = Counter(c['subset'] for c in self.cases)
        self.assertEqual(counts, {'p1_new': 66, 'p0_legacy': 18, 'out_of_scope': 6})
        self.assertEqual(len({c['case_id'] for c in self.cases}), 90)

    def test_09_reference_cases_do_not_contain_patient_records(self):
        text = (ROOT / 'data/samples/faq_p1_evaluation_90.json').read_text(encoding='utf-8')
        for field in ('patient_id', 'session_id', 'blood_glucose_level', 'health_data'):
            self.assertNotIn('"'+field+'"', text)

    def test_10_offline_90_question_quality_gate(self):
        report = run_evaluation(self.repo, self.cases, self.data)
        self.assertEqual(report['metrics']['cases_total'], 90)
        self.assertTrue(report['quality_gate_pass'])
        self.assertTrue(is_acceptable(report['metrics']))
        self.assertEqual(report['metrics']['citation_provenance_integrity']['passed'], 90)
        self.assertEqual(report['metrics']['out_of_scope_abstention']['passed'], 6)
        # We do not falsely assert all 90 questions pass; ambiguous questions remain documented.
        self.assertGreaterEqual(report['metrics']['full_case_pass']['passed'], 75)

    def test_11_mutated_evidence_url_is_rejected(self):
        answer = self.svc.query('Bệnh tiểu đường gây ảnh hưởng đến tim mạch như thế nào?')
        source_lookup = {s['id']: s for s in self.data['sources']}
        fact_lookup = {f['id']: f for f in self.data['facts']}
        case = {'case_id': 'fake', 'subset': 'p1_new', 'question': 'Kiểm tra',
                'expected_kind': 'grounded_extractive', 'expected_topic': 'heart_health'}
        altered = {**answer, '_evidence': [dict(e) for e in answer['_evidence']]}
        altered['_evidence'][0]['source'] = {**altered['_evidence'][0]['source'],
                                           'url': 'https://unverified.example/test'}
        self.assertFalse(evaluate_case(case, altered, fact_lookup, source_lookup)['citation_ok'])

    def test_12_missing_references_fail_validation(self):
        copy_data = json.loads(json.dumps(self.data))
        copy_data['facts'][-1]['source_id'] = 'unknown-source'
        with self.assertRaises(ValueError):
            validate(copy_data)

    def test_13_duplicate_evaluation_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            obj = {'cases': [dict(c) for c in self.cases]}
            obj['cases'][1]['case_id'] = obj['cases'][0]['case_id']
            p = Path(tempdir) / 'bad.json'
            p.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_cases(p)

    def test_14_unrelated_questions_yield_no_evidence(self):
        for prompt in ('Mật mã của vệ tinh viễn thông là gì?',
                       'Phi hành gia mèo và quỹ đạo Sao Hỏa là gì?'):
            with self.subTest(prompt=prompt):
                answer = self.svc.query(prompt)
                self.assertEqual(answer['response_kind'], 'no_evidence')
                self.assertFalse(answer.get('_evidence'))

    def test_15_no_individualized_medicine_instructions(self):
        # Existing V2 guard must still prevent medication-dosage answers.
        for prompt in ('Tôi muốn tự tăng liều thuốc tiểu đường',
                       'Uống metformin bao nhiêu mg?',
                       'Insulin dùng liều bao nhiêu?'):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.svc.query(prompt)['response_kind'], 'no_evidence')

    def test_16_public_topics_provide_grounded_sources(self):
        prompts = [
            ('Bảo vệ thị lực khi bị tiểu đường thế nào?', 'eye_health'),
            ('Tiểu đường có biến chứng thận không?', 'kidney_health'),
            ('Người tiểu đường bị tê bàn chân do đâu?', 'foot_health'),
            ('Mắc tiểu đường có đi du lịch được không?', 'travel_health'),
            ('Thiếu ngủ có ảnh hưởng đến đường huyết không?', 'sleep_stress'),
        ]
        for prompt, topic in prompts:
            with self.subTest(prompt=prompt):
                answer = self.svc.query(prompt)
                self.assertEqual(answer['response_kind'], 'grounded_extractive')
                self.assertEqual(answer['matched_topics'][0], topic)
                self.assertTrue(all(ev['source']['url'].startswith('https://')
                                    for ev in answer['_evidence']))


if __name__ == '__main__':
    unittest.main()
