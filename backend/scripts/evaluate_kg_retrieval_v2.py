"""Evaluate v2 Topic+Fact ranking against an explicit 24-question FAQ fixture.

Default mode checks the live Neo4j database; --offline checks bundled JSON.
Use both: the offline score alone cannot prove the live DB was updated.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from scripts.faq_knowledge_p0 import OfflineRepo
from services.knowledge_service import KnowledgeRetrievalService
from services.neo4j_service import Neo4jKnowledgeRepository


def check_case(response: dict, case: dict) -> bool:
    expected_kind = case.get('expected_kind', 'grounded_extractive')
    if response.get('response_kind') != expected_kind:
        return False
    evidence = response.get('_evidence', [])
    if expected_kind == 'no_evidence':
        return not evidence and response.get('retrieved_fact_count') == 0
    topic = case['expected_topic']
    if not response.get('matched_topics') or response['matched_topics'][0] != topic:
        return False
    if not evidence or response.get('retrieved_fact_count') != len(evidence):
        return False
    if not all(ev.get('source', {}).get('url', '').startswith('https://') for ev in evidence):
        return False
    if case.get('expected_first_fact') and evidence[0]['fact_id'] != case['expected_first_fact']:
        return False
    if case.get('expected_topics'):
        if not set(case['expected_topics']).issubset(set(response['matched_topics'])):
            return False
        if not set(case['expected_topics']).issubset({ev['topic_id'] for ev in evidence}):
            return False
    return all(f'[Nguồn {i}]' in response.get('answer', '') for i in range(1, len(evidence) + 1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true', help='read curated_knowledge.json instead of Neo4j')
    args = parser.parse_args()
    cases = json.loads((ROOT / 'data/samples/faq_retrieval_v2.json').read_text(encoding='utf-8'))
    repo = OfflineRepo() if args.offline else Neo4jKnowledgeRepository()
    passed = 0
    try:
        service = KnowledgeRetrievalService(repo)
        for index, case in enumerate(cases, 1):
            try:
                result = service.query(case['question'])
                ok = check_case(result, case)
                if ok:
                    passed += 1
                ids = [ev['fact_id'] for ev in result.get('_evidence', [])]
                print(f'{index:02d} {"PASS" if ok else "FAIL"}: {case["question"]} -> {result.get("matched_topics", [])} / {ids}')
            except Exception as exc:
                print(f'{index:02d} ERROR {case["question"]}: {type(exc).__name__}: {exc}')
        mode = 'offline' if args.offline else 'live'
        print(f'KG RETRIEVAL V2 {passed}/{len(cases)} PASS (mode={mode})')
        return 0 if passed == len(cases) else 2
    finally:
        if not args.offline:
            repo.close()


if __name__ == '__main__':
    raise SystemExit(main())
