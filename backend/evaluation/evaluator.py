"""Reproducible workflow evaluation. No medical accuracy inferred from these demos.

The output includes only scenario identifiers, status checks and performance,
never features, questions, predictions or raw reports.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Callable

from core.contracts import AgentMessage


class EvaluationError(ValueError):
    pass


def load_cases(path: str | Path) -> list[dict]:
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(doc, list) or not 1 <= len(doc) <= 100:
        raise EvaluationError('Expected 1 to 100 scenarios')
    seen = set()
    for item in doc:
        if (not isinstance(item, dict) or set(item) != {'case_id', 'request', 'expect'}
            or not isinstance(item['case_id'], str) or not item['case_id'].isascii()
            or not item['case_id'].replace('_', '').isalnum() or not 1 <= len(item['case_id']) <= 40
            or item['case_id'] in seen or not isinstance(item['request'], dict)
            or set(item['request']) - {'question', 'features'}
            or not isinstance(item['expect'], dict) or set(item['expect']) - {'status', 'error_type', 'knowledge_status', 'report_ready'}
            or item['expect'].get('status') not in ('ok', 'error')):
            raise EvaluationError('Invalid scenario contract')
        seen.add(item['case_id'])
    return doc


def evaluate_cases(cases: list[dict], run: Callable[[dict], AgentMessage]) -> dict:
    """Runner is dependency-injected; during real runs uses Coordinator and DL/Neo4j."""
    if not isinstance(cases, list) or not cases:
        raise EvaluationError('Missing scenarios')
    summaries = []
    for case in cases:
        started = perf_counter()
        try:
            result = run(case['request'])
            if not isinstance(result, AgentMessage) or result.agent != 'coordinator':
                raise EvaluationError('Runner did not return a Coordinator AgentMessage')
            status = result.status
            payload = result.payload
            actual = {'status': status,
                      'error_type': payload.get('error_type'),
                      'knowledge_status': payload.get('knowledge_status'),
                      'report_ready': payload.get('report_ready')}
            steps = payload.get('steps', [])
            step_statuses = {s['agent']: s['status'] for s in steps if isinstance(s, dict) and 'agent' in s and 'status' in s}
        except Exception:
            actual = {'status': 'error', 'error_type': 'evaluation_runner_error',
                      'knowledge_status': None, 'report_ready': False}
            step_statuses = {}
        latency_ms = round((perf_counter() - started) * 1000, 3)
        expected = case['expect']
        checks = {key: actual.get(key) == value for key, value in expected.items()}
        summaries.append({'case_id': case['case_id'], 'passed': all(checks.values()),
                          'checks': checks, 'observed_status': actual['status'],
                          'observed_error_type': actual['error_type'], 'duration_ms': latency_ms,
                          'step_statuses': step_statuses})
    passed = sum(c['passed'] for c in summaries)
    return {'evaluation_kind': 'workflow_contract_smoke_not_clinical_accuracy',
            'total_cases': len(summaries), 'passed': passed,
            'failed': len(summaries) - passed,
            'pass_rate': round(passed / len(summaries), 4),
            'avg_duration_ms': round(mean(c['duration_ms'] for c in summaries), 3),
            'cases': summaries,
            'limitations': ['Uses a small synthetic functional fixture set; not a medical accuracy study.',
                            'For DL classifier metrics, use outputs/dl_training_metrics.json from a separate held-out test split.'],
            'stores_patient_values': False}
