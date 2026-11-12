"""Unit tests for DL-K1 that do NOT require TensorFlow to be installed.

Keras training integration is separately checked by keras_smoke_dlk1.py in
an isolated Python environment with TensorFlow available.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from core.features import FEATURE_NAMES  # noqa: E402
from training.keras_dlk1 import (  # noqa: E402
    evaluate_predictions, experiment_paths, load_sklearn_reference,
    split_and_preprocess, write_comparison_report,
)


class DLK1ContractTests(unittest.TestCase):
    def test_new_artifacts_do_not_overlap_active_model(self):
        paths = experiment_paths(PROJECT)
        self.assertEqual(paths["model"].name, "diabetes_keras_v1.keras")
        self.assertEqual(paths["model"].parent.name, "keras_dlk1")
        self.assertNotEqual(paths["manifest"], PROJECT / "config/model_manifest.json")
        self.assertNotEqual(paths["model"], PROJECT / "models/diabetes_mlp_v1.joblib")

    def test_invalid_experiment_directory_rejected(self):
        for x in ("../models", "", "keras-dlk1", "/tmp", "."):
            with self.subTest(x=x), self.assertRaises(ValueError):
                experiment_paths(PROJECT, x)

    def test_metrics_exact_from_confusion(self):
        metrics = evaluate_predictions(np.array([0, 0, 1, 1]), np.array([.1, .8, .9, .2]))
        self.assertEqual(metrics["confusion_matrix_0_1"], [[1, 1], [1, 1]])
        self.assertEqual(metrics["accuracy"], 0.5)
        self.assertEqual(metrics["recall_positive"], 0.5)
        self.assertEqual(metrics["test_rows"], 4)

    def test_metrics_bad_input_rejected(self):
        for true, score in (([0, 1], [0.1]), ([1, 1], [0.1, 0.9]), ([0, 1], [.2, 1.1]), ([0, 1], [float('nan'), .2])):
            with self.subTest(true=true, score=score), self.assertRaises(ValueError):
                evaluate_predictions(np.array(true), np.array(score))

    def test_metric_threshold_is_one_half(self):
        a = evaluate_predictions(np.array([0, 1]), np.array([0.5, 0.49]))
        self.assertEqual(a["confusion_matrix_0_1"], [[0, 1], [1, 0]])
        self.assertEqual(a["threshold"], .5)

    def test_report_does_not_invent_sklearn_baseline(self):
        m = evaluate_predictions(np.array([0, 1]), np.array([.1, .9]))
        info = {"train_rows_total": 8, "fit_rows": 7, "validation_rows": 1, "test_rows": 2,
                "input_dim_after_encoding": 15}
        report = write_comparison_report(m, None, info, "Missing old metrics")
        self.assertIn("—", report)
        self.assertNotIn("97.09%", report)
        self.assertIn("Missing old metrics", report)

    def test_missing_baseline_returns_none(self):
        with tempfile.TemporaryDirectory() as folder:
            baseline, reason = load_sklearn_reference(Path(folder), "dummyhash")
            self.assertIsNone(baseline)
            self.assertTrue(reason)

    def test_preprocess_uses_training_only_and_eight_features(self):
        rng = np.random.default_rng(88)
        rows = []
        for i in range(260):
            rows.append({
                "gender": ["Female", "Male", "Other"][i % 3],
                "age": float(rng.integers(18, 79)),
                "hypertension": int(i % 5 == 0),
                "heart_disease": int(i % 7 == 0),
                "smoking_history": ["never", "former", "current", "No Info"][i % 4],
                "bmi": round(float(rng.uniform(17, 43)), 3),
                "HbA1c_level": round(float(rng.uniform(4, 10)), 3),
                "blood_glucose_level": int(rng.integers(80, 220)),
                "diabetes": int(i % 4 == 0),
            })
        with tempfile.TemporaryDirectory() as folder:
            csv = Path(folder) / "tiny.csv"
            pd.DataFrame(rows).to_csv(csv, index=False)
            preprocessor, fit, val, test, info = split_and_preprocess(csv)
            self.assertEqual(info["train_rows_total"] + info["test_rows"], 260)
            self.assertEqual(info["fit_rows"] + info["validation_rows"], info["train_rows_total"])
            self.assertEqual(fit[0].shape[1], val[0].shape[1])
            self.assertEqual(fit[0].shape[1], test[0].shape[1])
            self.assertEqual(info["input_dim_after_encoding"], len(preprocessor.get_feature_names_out()))
            self.assertEqual(tuple(FEATURE_NAMES), (
                "gender", "age", "hypertension", "heart_disease", "smoking_history",
                "bmi", "HbA1c_level", "blood_glucose_level",
            ))


if __name__ == "__main__":
    unittest.main()
