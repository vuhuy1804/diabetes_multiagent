"""P0 KG content and seed sync regression, no live database required."""
from __future__ import annotations
import json,sys, unittest
from pathlib import Path
BACKEND=Path(__file__).resolve().parents[1]
ROOT=BACKEND.parent
sys.path.insert(0,str(BACKEND))
from scripts.build_kg_seed import validate,generate
from scripts.neo4j_cli import statements
from services.knowledge_service import KnowledgeRetrievalService
from scripts.faq_knowledge_p0 import OfflineRepo

class ExpandedKGP0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'data/knowledge/curated_knowledge.json').read_text(encoding='utf-8'))
        cls.svc=KnowledgeRetrievalService(OfflineRepo())
    def test_volume(self):
        stats=validate(self.data)
        self.assertGreaterEqual(stats['topics'],24)
        self.assertGreaterEqual(stats['facts'],82)
        self.assertGreaterEqual(stats['sources'],18)
    def test_no_duplicate_ids_and_no_missing_sources(self):
        validate(self.data)
        self.assertTrue(all(s['url'].startswith('https://') for s in self.data['sources']))
    def test_original_fact_ids_preserved(self):
        self.assertTrue({f'f{i:02d}' for i in range(1,23)}.issubset({f['id'] for f in self.data['facts']}))
    def test_seed_in_sync_with_json_and_accepted_by_existing_loader(self):
        script=(ROOT/'data/knowledge/DB_diabet.cypher').read_text(encoding='utf-8')
        self.assertEqual(generate(self.data),script)
        self.assertGreater(len(statements(script)),300)
    def test_cypher_strings_can_have_semicolons_without_splitting(self):
        self.assertEqual(len(statements("MERGE (n:Fact {text: 'Nội dung; dấu chấm phẩy'});")),1)
        with self.assertRaises(ValueError):
            statements('MERGE (n:Fact {id: \'a\'}); MERGE (m:Fact {id: \'b\'});')
    def test_faq_22_questions_match_relevant_topic_and_have_sources(self):
        cases=json.loads((ROOT/'data/samples/faq_knowledge_p0.json').read_text(encoding='utf-8'))
        self.assertEqual(len(cases),22)
        for case in cases:
            with self.subTest(question=case['question']):
                result=self.svc.query(case['question'])
                self.assertEqual(result['response_kind'],'grounded_extractive')
                self.assertEqual(result['matched_topics'][0],case['expected_topic'])
                self.assertTrue(any(e['topic_id']==case['expected_topic'] for e in result['_evidence']))
                self.assertTrue(all(e['source']['url'].startswith('https://') for e in result['_evidence']))
    def test_does_not_fabricate_unknown_subject(self):
        result=self.svc.query('Mèo phi hành gia và lỗ đen vũ trụ')
        self.assertEqual(result['response_kind'],'no_evidence')
    def test_version_matches_curated_metadata(self):
        result=self.svc.query('Bệnh tiểu đường có di truyền không?')
        self.assertEqual(result['knowledge_version'],self.data['version'])

if __name__=='__main__':unittest.main()
