"""Quickly test the Patient Data Agent without Flask or a model/database.

From project root:
  python backend/scripts/patient_data_cli.py data/samples/patient_input_normalize.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from agents.patient_data_agent import PatientDataAgent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3: validate patient demo input JSON")
    parser.add_argument("file", help="JSON with a top-level features object")
    args = parser.parse_args()
    try:
        body = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"Cannot read valid UTF-8 JSON file: {exc}", file=sys.stderr)
        return 2
    raw_features = body.get("features") if isinstance(body, dict) else None
    message = PatientDataAgent().run("req_phase3_cli", raw_features)
    # ASCII-only on Windows PowerShell 5.1; it round-trips as Unicode when parsed.
    print(json.dumps(message.to_dict(), ensure_ascii=True, indent=2))
    return 0 if message.status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
