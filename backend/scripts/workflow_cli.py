"""Run the real Coordinator (trained local DL, real Neo4j) from a JSON file.

Usage: python backend/scripts/workflow_cli.py data/samples/workflow_with_question.json
This script does not write patient data or responses to disk.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env', override=False)

from agents.patient_data_agent import PatientDataAgent
from agents.dl_prediction_agent import DLPredictionAgent
from agents.rule_based_agent import RuleBasedAgent
from agents.kg_rag_agent import KGRAGAgent
from coordinator.coordinator_agent import CoordinatorAgent


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('Usage: python backend/scripts/workflow_cli.py path/to/request.json', file=sys.stderr)
        return 2
    try:
        raw = json.loads(Path(argv[1]).read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or set(raw) - {'features', 'question'}:
            raise ValueError('Expected JSON with features and optional question only')
    except (OSError, ValueError) as exc:
        print('Input error: invalid JSON request or unsupported fields', file=sys.stderr)
        return 2
    agent = CoordinatorAgent(PatientDataAgent(), DLPredictionAgent(),
                             RuleBasedAgent(), KGRAGAgent())
    result = agent.run(features=raw.get('features'), question=raw.get('question'),
                       question_provided='question' in raw)
    # Python CLI can use UTF-8 without changing the terminal's codepage.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.status == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
