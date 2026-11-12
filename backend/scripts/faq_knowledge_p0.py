"""Run FAQ checks against LIVE Neo4j (default) or curated JSON (--offline)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
BACKEND=Path(__file__).resolve().parents[1]
ROOT=BACKEND.parent
sys.path.insert(0,str(BACKEND))
from services.knowledge_service import KnowledgeRetrievalService
from services.neo4j_service import Neo4jKnowledgeRepository

class OfflineRepo:
    def __init__(self):
        data=json.loads((ROOT/'data/knowledge/curated_knowledge.json').read_text(encoding='utf-8'))
        self.topics=data['topics']
        self.facts=data['facts']
        self.by_topic={t['id']:t for t in self.topics}
        self.sources={s['id']:s for s in data['sources']}
    def list_topics(self): return self.topics
    def evidence_for_topics(self, topic_ids, limit):
        rows=[]
        for topic_id in topic_ids:
            for f in self.facts:
                if f['topic_id']!=topic_id:continue
                s=self.sources[f['source_id']]
                rows.append({'topic_id':topic_id,'topic_name':self.by_topic[topic_id]['name'],
                             'fact_id':f['id'],'text':f['text'],'source_id':s['id'],
                             'source_title':s['title'],'publisher':s['publisher'],
                             'source_url':s['url']})
        return rows[:limit]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--offline',action='store_true',help='test bundled JSON, without Neo4j')
    args=p.parse_args()
    cases=json.loads((ROOT/'data/samples/faq_knowledge_p0.json').read_text(encoding='utf-8'))
    repo=OfflineRepo() if args.offline else Neo4jKnowledgeRepository()
    passed=0
    try:
        svc=KnowledgeRetrievalService(repo)
        for i,case in enumerate(cases,1):
            try:
                r=svc.query(case['question'])
                topics=r.get('matched_topics') or []
                evidence=r.get('_evidence') or []
                ok=(r.get('response_kind')=='grounded_extractive' and
                    bool(topics) and topics[0]==case['expected_topic'] and
                    bool(evidence) and any(e['topic_id']==case['expected_topic'] for e in evidence) and
                    all(e['source']['url'].startswith('https://') for e in evidence))
                status='PASS' if ok else 'FAIL'
                print(f'{i:02d} {status}: {case["question"]} -> {topics}')
                if ok:passed+=1
            except Exception as e:
                print(f'{i:02d} ERROR: {case["question"]} ({type(e).__name__})')
        print(f'FAQ P0 {passed}/{len(cases)} PASS (mode={"offline" if args.offline else "live"})')
        return 0 if passed==len(cases) else 2
    finally:
        if not args.offline:repo.close()

if __name__=='__main__':raise SystemExit(main())
