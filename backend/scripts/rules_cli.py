"""Phase 4 standalone CLI for sample rule-input JSON (not DL inference).

Usage:
  python backend/scripts/rules_cli.py data/samples/rule_input_demo.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents.rule_based_agent import RuleBasedAgent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate educational rule flags')
    parser.add_argument('file', help='UTF-8 JSON with features and prediction payload')
    args = parser.parse_args()
    try:
        body = json.loads(Path(args.file).read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f'Cannot read UTF-8 JSON: {exc}', file=sys.stderr)
        return 2
    if not isinstance(body, dict):
        print('JSON root must be an object', file=sys.stderr)
        return 2
    msg = RuleBasedAgent().run('req_phase4_cli', body.get('features'), body.get('prediction'))
    # ASCII escapes preserve Unicode when Windows PowerShell 5.1 parses JSON.
    print(json.dumps(msg.to_dict(), ensure_ascii=True, indent=2))
    return 0 if msg.status == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())
