"""Real phase 8 batch evaluation on synthetic demo scenarios.

No features/questions are included in the saved results. Not clinical validation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env', override=False)
from agents.patient_data_agent import PatientDataAgent
from agents.dl_prediction_agent import DLPredictionAgent
from agents.rule_based_agent import RuleBasedAgent
from agents.kg_rag_agent import KGRAGAgent
from agents.explanation_agent import ExplanationAgent
from coordinator.coordinator_agent import CoordinatorAgent
from evaluation.evaluator import evaluate_cases, load_cases


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate real DL/KG workflow with 5 safe synthetic cases')
    parser.add_argument('--cases', type=Path, default=ROOT / 'data/samples/evaluation_phase8_cases.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'outputs/evaluation_phase8.json')
    args = parser.parse_args()
    coordinator = CoordinatorAgent(PatientDataAgent(), DLPredictionAgent(), RuleBasedAgent(),
                                   KGRAGAgent(), ExplanationAgent())
    cases = load_cases(args.cases)
    def run(item):
        return coordinator.run_with_explanation(
            features=item.get('features'), question=item.get('question'),
            question_provided='question' in item)
    summary = evaluate_cases(cases, run)
    summary['created_at_utc'] = datetime.now(timezone.utc).isoformat()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(tmp, args.out)
    finally:
        tmp.unlink(missing_ok=True)
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print('EVALUATION PASS' if summary['failed'] == 0 else 'EVALUATION HAS FAILURES')
    return 0 if summary['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
