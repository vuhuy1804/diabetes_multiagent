"""No live Neo4j required: test algorithm, message contract and .cypher parser."""
from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from agents.kg_rag_agent import KGRAGAgent  # noqa: E402
from services.knowledge_service import KnowledgeRetrievalService, validate_question, normalize  # noqa: E402
from services.neo4j_service import KnowledgeDatabaseError  # noqa: E402
from scripts.neo4j_cli import statements  # noqa: E402


DATA = json.loads((ROOT/'data/knowledge/curated_knowledge.json').read_text(encoding='utf-8'))


class FakeRepo:
    def __init__(self, fail=False):
        self.fail = fail
        self.topics = DATA['topics']
        self.facts = DATA['facts']
        self.sources = {s['id']:s for s in DATA['sources']}
        self.topic_by_id = {t['id']:t for t in self.topics}
        self.called_topics = None

    def readiness(self):
        return 'ready'

    def list_topics(self):
        if self.fail:
            raise KnowledgeDatabaseError('testing offline')
        return self.topics

    def evidence_for_topics(self, topic_ids, limit):
        self.called_topics = list(topic_ids)
        out = []
        for topic_id in topic_ids:
            for f in self.facts:
                if f['topic_id'] != topic_id: continue
                t = self.topic_by_id[topic_id]
                s = self.sources[f['source_id']]
                out.append({'topic_id':topic_id,'topic_name':t['name'],
                            'fact_id':f['id'],'text':f['text'],
                            'source_id':s['id'],'source_title':s['title'],
                            'publisher':s['publisher'],'source_url':s['url']})
        return out[:limit]


class KnowledgePhase2Tests(unittest.TestCase):
    def test_json_and_cypher_have_expected_volume(self):
        self.assertGreaterEqual(len(DATA['topics']), 24)
        self.assertGreaterEqual(len(DATA['facts']), 82)
        self.assertGreaterEqual(len(DATA['sources']), 18)
        self.assertTrue({f'f{i:02d}' for i in range(1,23)}.issubset({f['id'] for f in DATA['facts']}))
        script = (ROOT/'data/knowledge/DB_diabet.cypher').read_text(encoding='utf-8')
        self.assertGreater(len(statements(script)), 60)

    def test_cypher_parser_rejects_multiple_statements(self):
        with self.assertRaises(ValueError):
            statements('MATCH (n) RETURN n; MATCH (m) RETURN m;')

    def test_unicode_normalization(self):
        self.assertEqual(normalize('Đái THÁO đường!'), 'dai thao duong')

    def test_grounded_topic_types(self):
        fake = FakeRepo()
        msg = KGRAGAgent(KnowledgeRetrievalService(fake)).run('req_1','Bệnh tiểu đường có mấy loại chính?')
        self.assertEqual(msg.status,'ok')
        self.assertEqual(msg.agent,'kg_rag')
        self.assertIn('types',msg.payload['matched_topics'])
        self.assertGreater(msg.payload['retrieved_fact_count'],0)
        self.assertEqual(msg.payload['retrieved_fact_count'],len(msg.evidence))
        self.assertIn('[Nguồn 1]',msg.payload['answer'])
        self.assertTrue(all(e['source']['url'].startswith('https://') for e in msg.evidence))

    def test_symptoms_and_hba1c(self):
        service = KnowledgeRetrievalService(FakeRepo())
        self.assertIn('symptoms',service.query('Dấu hiệu tiểu đường là gì?')['matched_topics'])
        self.assertIn('a1c',service.query('HbA1c phản ánh điều gì?')['matched_topics'])

    def test_no_evidence_no_fabricated_answer(self):
        msg=KGRAGAgent(KnowledgeRetrievalService(FakeRepo())).run('req_2','Mèo phi hành gia trên Sao Hỏa')
        self.assertEqual(msg.status,'ok')
        self.assertEqual(msg.evidence,[])
        self.assertEqual(msg.payload['response_kind'],'no_evidence')

    def test_invalid_input_not_sent_to_db(self):
        for value in ('', ' ', 2, None, 'a' * 501):
            with self.subTest(value=str(value)[:12]):
                msg=KGRAGAgent(KnowledgeRetrievalService(FakeRepo())).run('req_3',value)
                self.assertEqual(msg.status,'error')
                self.assertEqual(msg.payload['error_type'],'invalid_question')

    def test_database_failure_not_faked(self):
        msg=KGRAGAgent(KnowledgeRetrievalService(FakeRepo(fail=True))).run('req_4','Tiểu đường là gì?')
        self.assertEqual(msg.status,'error')
        self.assertEqual(msg.payload['error_type'],'neo4j_unavailable')
        self.assertEqual(msg.evidence,[])


if __name__ == '__main__':
    unittest.main()
