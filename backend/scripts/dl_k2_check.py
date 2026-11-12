"""DL-K2 lightweight integration smoke: validate active or chosen DL backend.

Example from project root:
  python backend/scripts/dl_k2_check.py --backend keras
  python backend/scripts/dl_k2_check.py --backend sklearn
  python backend/scripts/dl_k2_check.py
Does not write/modify the old or new model.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from services.dl_service import DLPredictionService, ModelUnavailableError  # noqa: E402
from core.features import FeatureValidationError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='DL-K2: check Keras/sklearn artifact and inference')
    parser.add_argument('--backend', choices=['keras', 'sklearn'], default=None,
                        help='Override .env for this invocation only')
    parser.add_argument('--sample', type=Path, default=ROOT / 'data/samples/predict_input.json')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env', override=False)
    chosen = args.backend or os.getenv('DL_MODEL_BACKEND', 'sklearn')
    service = DLPredictionService(backend=chosen)
    status = service.readiness()
    print(f'DL-K2 BACKEND: {chosen} | READINESS: {status}')
    if status != 'ready':
        print('DL-K2 CHECK FAIL: selected model is missing, has wrong hash, or lacks required runtime')
        return 2
    try:
        sample = json.loads(args.sample.read_text(encoding='utf-8'))
        result = service.predict(sample['features'])
    except (ValueError, KeyError, OSError, ModelUnavailableError, FeatureValidationError) as exc:
        # Do not print patient data or internal details from errors.
        print(f'DL-K2 CHECK FAIL: {type(exc).__name__}')
        return 2
    expected_version = 'diabetes_keras_v1' if chosen == 'keras' else 'diabetes_mlp_v1'
    if result['model_version'] != expected_version:
        print('DL-K2 CHECK FAIL: unexpected model_version')
        return 2
    print('DL-K2 CHECK PASS')
    print(json.dumps({k: result[k] for k in ('model_version', 'prediction', 'model_score_class_1', 'score_is_calibrated')},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
