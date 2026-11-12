"""Phase 1 tests work WITHOUT the public dataset, using synthetic test rows.

Synthetic tests are deliberately NOT clinical evaluation.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from agents.dl_prediction_agent import DLPredictionAgent  # noqa: E402
from core.features import FEATURE_NAMES, FeatureValidationError, validate_features  # noqa: E402
from services.dl_service import DLPredictionService  # noqa: E402
from training.train_dl import train_model  # noqa: E402

DEMO = {
    "gender": "Female", "age": 44, "hypertension": 0,
    "heart_disease": 0, "smoking_history": "never", "bmi": 27.32,
    "HbA1c_level": 5.7, "blood_glucose_level": 140,
}


class FeatureContractTests(unittest.TestCase):
    def test_preserves_training_order(self):
        self.assertEqual(tuple(validate_features(DEMO)), FEATURE_NAMES)

    def test_missing_field_rejected(self):
        with self.assertRaises(FeatureValidationError):
            validate_features({k: v for k, v in DEMO.items() if k != "age"})

    def test_invalid_boolean_and_string_rejected(self):
        for change in ({"hypertension": True}, {"bmi": "27.3"}, {"smoking_history": "unknown"}):
            with self.subTest(change=change), self.assertRaises(FeatureValidationError):
                validate_features({**DEMO, **change})

    def test_extra_field_rejected(self):
        with self.assertRaises(FeatureValidationError):
            validate_features({**DEMO, "diabetes": 1})


class ActualTrainingRoundTripTests(unittest.TestCase):
    def test_training_writes_real_model_and_inference_runs(self):
        # 260 synthetic samples with explicit synthetic labels for engineering tests only.
        # The real academic evaluation must be done on a separately acquired public dataset.
        gen = np.random.default_rng(2026)
        rows = []
        for i in range(260):
            rows.append({
                "gender": "Female" if i % 2 == 0 else "Male",
                "age": float(gen.integers(18, 78)),
                "hypertension": int(i % 5 == 0),
                "heart_disease": int(i % 7 == 0),
                "smoking_history": "never" if i % 2 else "former",
                "bmi": round(float(gen.uniform(19, 38)), 2),
                "HbA1c_level": round(float(gen.uniform(4, 9)), 2),
                "blood_glucose_level": int(gen.integers(85, 235)),
                "diabetes": int(i % 2 == 0),  # artificial, nonmedical labels
            })
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            csv = root / "synthetic-test-only.csv"
            pd.DataFrame(rows).to_csv(csv, index=False)
            manifest = train_model(csv, output_root=root, max_iter=8)
            self.assertEqual(manifest["status"], "READY")
            self.assertEqual(manifest["feature_names_in_training_order"], list(FEATURE_NAMES))
            self.assertTrue((root / "models/diabetes_mlp_v1.joblib").is_file())
            self.assertTrue((root / "outputs/dl_training_metrics.json").is_file())
            loaded = json.loads((root / "config/model_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["dataset_sha256"], manifest["dataset_sha256"])
            service = DLPredictionService(root)
            self.assertEqual(service.readiness(), "ready")
            output = service.predict(DEMO)
            self.assertIn(output["prediction"], (0, 1))
            self.assertTrue(0 <= output["model_score_class_1"] <= 1)
            self.assertFalse(output["score_is_calibrated"])
            message = DLPredictionAgent(service).run("req_synthetic_test", DEMO)
            self.assertEqual(message.status, "ok")
            self.assertEqual(message.agent, "dl_prediction")
            self.assertEqual(message.evidence, [])

            # The Agent must return the same prediction as original saved pipeline.
            original = joblib.load(root / "models/diabetes_mlp_v1.joblib")
            frame = pd.DataFrame([DEMO], columns=list(FEATURE_NAMES))
            self.assertEqual(output["prediction"], int(original.predict(frame)[0]))
            self.assertAlmostEqual(
                output["model_score_class_1"],
                float(original.predict_proba(frame)[0, 1]), places=5,
            )
            # A mutated artifact must not be reported as READY.
            with (root / "models/diabetes_mlp_v1.joblib").open("ab") as stream:
                stream.write(b"tamper")
            self.assertEqual(DLPredictionService(root).readiness(), "not_configured")

    def test_missing_model_does_not_fake_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            service = DLPredictionService(Path(folder))
            self.assertEqual(service.readiness(), "not_configured")
            message = DLPredictionAgent(service).run("req_missing", DEMO)
            self.assertEqual(message.status, "error")
            self.assertEqual(message.payload["error_type"], "model_unavailable")


if __name__ == "__main__":
    unittest.main()
