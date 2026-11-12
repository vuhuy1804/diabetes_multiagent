"""Phase 6: run genuine DL + Neo4j + rules -> Explanation (no data saved).

Usage from project root:
  python backend/scripts/report_cli.py data/samples/report_with_question.json
The returned label/score is from YOUR trained model, never a fabricated demo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env', override=False)

from agents.dl_prediction_agent import DLPredictionAgent
from agents.explanation_agent import ExplanationAgent
from agents.kg_rag_agent import KGRAGAgent
from agents.patient_data_agent import PatientDataAgent
from agents.rule_based_agent import RuleBasedAgent
from coordinator.coordinator_agent import CoordinatorAgent


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('Usage: python backend/scripts/report_cli.py path/to/request.json', file=sys.stderr)
        return 2
    try:
        request = json.loads(Path(argv[1]).read_text(encoding='utf-8'))
        if not isinstance(request, dict) or set(request) - {'features', 'question'}:
            raise ValueError('Invalid request')
    except (OSError, ValueError):
        print('Input error: expected UTF-8 JSON with features and optional question', file=sys.stderr)
        return 2

    coordinator = CoordinatorAgent(PatientDataAgent(), DLPredictionAgent(), RuleBasedAgent(),
                                   KGRAGAgent(), ExplanationAgent())
    result = coordinator.run_with_explanation(
        features=request.get('features'), question=request.get('question'),
        question_provided='question' in request,
    )
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
