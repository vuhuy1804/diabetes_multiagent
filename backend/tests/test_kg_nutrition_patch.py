"""Question-only Knowledge Graph regression tests, no Neo4j service required."""
import sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from test_kg_phase2 import FakeRepo
from services.knowledge_service import KnowledgeRetrievalService

class NutritionKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo()
        self.svc = KnowledgeRetrievalService(self.repo)

    def test_food_question_matches_nutrition(self):
        output = self.svc.query('Bệnh tiểu đường thì nên ăn gì?')
        self.assertEqual(output['response_kind'], 'grounded_extractive')
        self.assertEqual(output['matched_topics'], ['nutrition'])
        self.assertTrue(all(e['topic_id'] == 'nutrition' for e in output['_evidence']))
        self.assertIn('rau', output['answer'].lower())

    def test_food_synonyms(self):
        for question in ('Chế độ ăn cho người đái tháo đường?',
                         'Nên uống gì khi bị tiểu đường?',
                         'Đái tháo đường: dinh dưỡng như thế nào?'):
            with self.subTest(question=question):
                result = self.svc.query(question)
                self.assertIn('nutrition', result['matched_topics'])

    def test_general_question_remains_general(self):
        result = self.svc.query('Bệnh tiểu đường là gì?')
        self.assertIn('diabetes', result['matched_topics'])

    def test_specific_unknown_question_no_generic_hallucination(self):
        result = self.svc.query('Tiểu đường và thiên thạch Mộc Tinh')
        self.assertEqual(result['response_kind'], 'no_evidence')
        self.assertEqual(result['retrieved_fact_count'], 0)

    def test_seeds_have_evidence_sources(self):
        import json
        kg=json.loads((HERE.parent/'data/knowledge/curated_knowledge.json').read_text(encoding='utf8'))
        source_ids={s['id'] for s in kg['sources']}
        self.assertTrue(all(f['source_id'] in source_ids for f in kg['facts']))

if __name__ == '__main__': unittest.main()
