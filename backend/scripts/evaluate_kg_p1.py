"""Run the 90-question P1 FAQ evaluation, offline or against live Neo4j.

This evaluates *retrieval*, not correctness of individual clinical decisions.
Offline mode checks the curated JSON implementation. Live mode verifies actual
Neo4j query responses. The questions were used for development QA; this is not a blind clinical study.
The JSON report stores public synthetic FAQ only.

Usage:
  python backend/scripts/evaluate_kg_p1.py --offline
  python backend/scripts/evaluate_kg_p1.py
  python backend/scripts/evaluate_kg_p1.py --offline --verbose
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from scripts.faq_knowledge_p0 import OfflineRepo
from services.knowledge_service import KnowledgeRetrievalService
from services.neo4j_service import Neo4jKnowledgeRepository

FIXTURE = ROOT / 'data/samples/faq_p1_evaluation_90.json'
DATASET = ROOT / 'data/knowledge/curated_knowledge.json'


def load_cases(fixture: Path = FIXTURE) -> list[dict]:
    data = json.loads(fixture.read_text(encoding='utf-8'))
    cases = data.get('cases')
    if not isinstance(cases, list) or len(cases) != 90:
        raise ValueError('P1 evaluation expects exactly 90 cases')
    ids = set()
    allowed_subsets = {'p1_new', 'p0_legacy', 'out_of_scope'}
    for case in cases:
        if not isinstance(case, dict) or not all(isinstance(case.get(k), str) and case[k]
                                                     for k in ('case_id', 'subset', 'question', 'expected_kind')):
            raise ValueError('invalid case')
        if case['case_id'] in ids or case['subset'] not in allowed_subsets:
            raise ValueError('duplicate id or invalid subset')
        ids.add(case['case_id'])
        if case['expected_kind'] not in {'grounded_extractive', 'no_evidence'}:
            raise ValueError('unknown expected_kind')
        if case['expected_kind'] == 'grounded_extractive' and not case.get('expected_topic'):
            raise ValueError('grounded case missing expected_topic')
    return cases


def evaluate_case(case: dict, answer: dict, fact_lookup: dict, source_lookup: dict) -> dict:
    """Check topic, specific evidence ID when provided, source provenance and abstention."""
    expected_kind = case['expected_kind']
    actual_kind = answer.get('response_kind')
    evidence = answer.get('_evidence') or []
    topics = answer.get('matched_topics') or []
    if not isinstance(evidence, list):
        evidence = []

    citation_ok = (
        answer.get('retrieved_fact_count') == len(evidence)
        and all(isinstance(e, dict) and isinstance(e.get('source'), dict) for e in evidence)
        and all(f'[Nguồn {index}]' in answer.get('answer', '')
                for index in range(1, len(evidence) + 1))
    )
    # Verify the reported Fact id -> Topic id -> Source id -> URL mapping.
    # A valid https URL alone does not prove the content has the correct origin.
    for e in evidence:
        if not isinstance(e, dict):
            citation_ok = False
            break
        fact = fact_lookup.get(e.get('fact_id'))
        src = source_lookup.get((fact or {}).get('source_id'))
        url = (e.get('source') or {}).get('url', '')
        if (not fact or not src or not isinstance(url, str) or urlsplit(url).scheme != 'https'
                or e.get('topic_id') != fact.get('topic_id')
                or e['source'].get('id') != src['id'] or url != src['url']
                or e.get('excerpt') != fact['text']):
            citation_ok = False
            break

    if expected_kind == 'no_evidence':
        abstain_ok = actual_kind == 'no_evidence' and len(evidence) == 0
        return {
            'case_id': case['case_id'], 'subset': case['subset'],
            'question': case['question'], 'expected_topic': None,
            'actual_topics': topics, 'actual_fact_ids': [x.get('fact_id') for x in evidence if isinstance(x, dict)],
            'topic_ok': None, 'fact_ok': None, 'citation_ok': citation_ok,
            'abstention_ok': abstain_ok, 'passed': abstain_ok and citation_ok,
        }

    topic_ok = (actual_kind == 'grounded_extractive'
                and bool(topics) and topics[0] == case['expected_topic']
                and any(e.get('topic_id') == case['expected_topic'] for e in evidence))
    expected_fact = case.get('expected_fact_id')
    fact_ok = None if not expected_fact else any(e.get('fact_id') == expected_fact for e in evidence)
    passed = topic_ok and citation_ok and (fact_ok is not False)
    return {
        'case_id': case['case_id'], 'subset': case['subset'],
        'question': case['question'], 'expected_topic': case['expected_topic'],
        'expected_fact_id': expected_fact, 'actual_topics': topics,
        'actual_fact_ids': [e.get('fact_id') for e in evidence],
        'topic_ok': topic_ok, 'fact_ok': fact_ok, 'citation_ok': citation_ok,
        'abstention_ok': None, 'passed': passed,
    }


def summarize(results: list[dict]) -> dict:
    def ratio(rows: list, field: str) -> dict:
        valid = [r for r in rows if r[field] is not None]
        matched = sum(r[field] is True for r in valid)
        return {'passed': matched, 'total': len(valid),
                'rate': round(matched / len(valid), 4) if valid else None}

    return {
        'cases_total': len(results),
        'full_case_pass': ratio(results, 'passed'),
        'topical_accuracy': ratio(results, 'topic_ok'),
        'target_fact_recall_at_4': ratio(results, 'fact_ok'),
        'citation_provenance_integrity': ratio(results, 'citation_ok'),
        'out_of_scope_abstention': ratio(results, 'abstention_ok'),
        'by_subset': {name: ratio([r for r in results if r['subset'] == name], 'passed')
                      for name in ('p1_new', 'p0_legacy', 'out_of_scope')},
    }


def is_acceptable(metrics: dict) -> bool:
    def rate(key):
        value = metrics[key]['rate']
        return value if value is not None else 0
    # Course-level QA gates; a failure is an honest finding, not permission to
    # manufacture answer content or force pass the test set.
    return (rate('topical_accuracy') >= 0.85
            and rate('target_fact_recall_at_4') >= 0.65
            and rate('citation_provenance_integrity') == 1.0
            and rate('out_of_scope_abstention') == 1.0)


def run_evaluation(repo, cases: list[dict], curated: dict, verbose: bool = False) -> dict:
    svc = KnowledgeRetrievalService(repo)
    fact_lookup = {f['id']: f for f in curated['facts']}
    source_lookup = {s['id']: s for s in curated['sources']}
    results = []
    for case in cases:
        try:
            response = svc.query(case['question'])
            result = evaluate_case(case, response, fact_lookup, source_lookup)
        except Exception as exc:
            result = {
                'case_id': case['case_id'], 'subset': case['subset'],
                'question': case['question'], 'expected_topic': case.get('expected_topic'),
                'error_type': type(exc).__name__, 'topic_ok': False,
                'fact_ok': False if 'expected_fact_id' in case else None,
                'citation_ok': False,
                'abstention_ok': False if case['expected_kind'] == 'no_evidence' else None,
                'passed': False,
            }
        results.append(result)
        if verbose or not result['passed']:
            print(f"{result['case_id']} {'PASS' if result['passed'] else 'REVIEW'}: "
                  f"{case['question']} -> {result.get('actual_topics',[])} / {result.get('actual_fact_ids',[])}")
    metrics = summarize(results)
    return {'evaluation_type':'source_grounded_kg_retrieval_not_clinical_accuracy',
            'faq_set':'P1-90 (66 new, 18 legacy, 6 out-of-domain; development QA)',
            'metrics':metrics,
            'review_cases':[r for r in results if not r['passed']],
            'all_results':results,
            'quality_gate_pass':is_acceptable(metrics)}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--offline', action='store_true', help='use curated JSON (no Neo4j connection)')
    p.add_argument('--verbose', action='store_true', help='print all 90 cases')
    p.add_argument('--no-write', action='store_true', help='do not save a JSON result file')
    args = p.parse_args()
    curated = json.loads(DATASET.read_text(encoding='utf-8'))
    cases = load_cases()
    repo = OfflineRepo() if args.offline else Neo4jKnowledgeRepository()
    mode = 'offline' if args.offline else 'live'
    try:
        report = run_evaluation(repo, cases, curated, verbose=args.verbose)
    finally:
        if not args.offline:
            repo.close()

    report['mode'] = mode
    metrics = report['metrics']
    for label in ('full_case_pass','topical_accuracy','target_fact_recall_at_4',
                  'citation_provenance_integrity','out_of_scope_abstention'):
        m=metrics[label]
        print(f'{label}: {m["passed"]}/{m["total"]} ({(m["rate"] or 0)*100:.1f}%)')
    print(f'P1 EVALUATION {"PASS" if report["quality_gate_pass"] else "NEEDS_REVIEW"} (mode={mode})')
    if not args.no_write:
        dest=ROOT/'outputs'/f'evaluation_kg_p1_{mode}.json'
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Report:',dest.relative_to(ROOT))
    return 0 if report['quality_gate_pass'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
