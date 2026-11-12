"""DL-K2: pure integration-contract tests; no TensorFlow or user data required.

One optional smoke test uses the user's actual DL-K1 artifacts when installed.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from core.features import FEATURE_NAMES, FeatureValidationError  # noqa: E402
from services.dl_service import DLPredictionService, ModelUnavailableError, sha256_file  # noqa: E402
from services.keras_dl_service import KerasDLPredictionService  # noqa: E402

SAMPLE = {
    'gender': 'Female', 'age': 44, 'hypertension': 0,
    'heart_disease': 0, 'smoking_history': 'never', 'bmi': 27.32,
    'HbA1c_level': 5.7, 'blood_glucose_level': 140,
}


def make_artifacts(root: Path) -> dict:
    model = root / 'models/keras_dlk1/diabetes_keras_v1.keras'
    prep = root / 'models/keras_dlk1/preprocessor.joblib'
    manifest_path = root / 'outputs/keras_dlk1/experiment_manifest.json'
    for path in (model, prep, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b'fake keras test fixture; no model is loaded')
    prep.write_bytes(b'fake preprocessor fixture; no joblib is loaded')
    manifest = {
        'status': 'EXPERIMENT_ONLY_NOT_INTEGRATED',
        'framework': 'tensorflow.keras', 'model_version': 'diabetes_keras_v1',
        'feature_names_in_training_order': list(FEATURE_NAMES),
        'decision_threshold': 0.5, 'score_is_calibrated': False,
        'architecture': {'hidden_layers': [64, 32], 'activation': 'relu', 'output': 'sigmoid'},
        'dataset_info': {'input_dim_after_encoding': 15},
        'model_relative_path': 'models/keras_dlk1/diabetes_keras_v1.keras',
        'preprocessor_relative_path': 'models/keras_dlk1/preprocessor.joblib',
        'model_sha256': sha256_file(model), 'preprocessor_sha256': sha256_file(prep),
    }
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    return manifest


def write_manifest(root: Path, manifest: dict):
    (root / 'outputs/keras_dlk1/experiment_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')


class FakePreprocessor:
    def transform(self, frame):
        assert list(frame.columns) == list(FEATURE_NAMES)
        return np.ones((1, 15), dtype=np.float32)


class FakeModel:
    def __init__(self, score=0.7):
        self.score = score
        self.inputs = [SimpleNamespace(shape=(None, 15))]
        self.outputs = [SimpleNamespace(shape=(None, 1))]

    def predict(self, values, verbose=0):
        assert values.shape == (1, 15)
        return np.array([[self.score]])


class KerasDLK2Tests(unittest.TestCase):
    def test_missing_keras_does_not_fallback_to_sklearn(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = DLPredictionService(Path(tmp), backend='keras')
            self.assertEqual(svc.readiness(), 'not_configured')
            with self.assertRaises(ModelUnavailableError):
                svc.predict(SAMPLE)

    def test_old_explicit_root_still_uses_sklearn_even_if_env_keras(self):
        with patch.dict('os.environ', {'DL_MODEL_BACKEND': 'keras'}), tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(DLPredictionService(Path(tmp)).backend, 'sklearn')

    def test_default_backend_respects_env(self):
        with patch.dict('os.environ', {'DL_MODEL_BACKEND': 'keras'}):
            self.assertEqual(DLPredictionService().backend, 'keras')
        with patch.dict('os.environ', {'DL_MODEL_BACKEND': 'sklearn'}):
            self.assertEqual(DLPredictionService().backend, 'sklearn')

    def test_invalid_backend_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = DLPredictionService(Path(tmp), backend='something-else')
            self.assertEqual(svc.readiness(), 'not_configured')
            with self.assertRaises(ModelUnavailableError):
                svc.predict(SAMPLE)

    def test_manifest_hash_and_schema_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_artifacts(root)
            manifest, model, prep = KerasDLPredictionService(root)._read_and_verify()
            self.assertEqual(manifest['model_version'], 'diabetes_keras_v1')
            self.assertTrue(model.is_file() and prep.is_file())

    def test_changed_model_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_artifacts(root)
            with (root / 'models/keras_dlk1/diabetes_keras_v1.keras').open('ab') as fp:
                fp.write(b'tampered')
            with self.assertRaises(ModelUnavailableError):
                KerasDLPredictionService(root)._read_and_verify()

    def test_bad_preprocessor_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_artifacts(root)
            with (root / 'models/keras_dlk1/preprocessor.joblib').open('ab') as fp:
                fp.write(b'tampered')
            with self.assertRaises(ModelUnavailableError):
                KerasDLPredictionService(root)._read_and_verify()

    def test_manifest_mismatch_rejected(self):
        cases = [
            ('status', 'READY'),
            ('feature_names_in_training_order', list(reversed(FEATURE_NAMES))),
            ('decision_threshold', 0.3),
            ('score_is_calibrated', True),
            ('model_relative_path', '../secrets.keras'),
            ('framework', 'another-framework'),
            ('dataset_info', {'input_dim_after_encoding': -1}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = make_artifacts(root)
            for key, bad in cases:
                with self.subTest(key=key):
                    write_manifest(root, {**original, key: bad})
                    with self.assertRaises(ModelUnavailableError):
                        KerasDLPredictionService(root)._read_and_verify()

    def test_valid_prediction_contract_with_mock_keras(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_artifacts(root)
            dummy_model = FakeModel(.68)
            dummy_tf = SimpleNamespace(keras=SimpleNamespace(models=SimpleNamespace(load_model=lambda *_a, **_k: dummy_model)))
            with patch.dict(sys.modules, {'tensorflow': dummy_tf}), patch('joblib.load', return_value=FakePreprocessor()):
                result = DLPredictionService(root, backend='keras').predict(SAMPLE)
            self.assertEqual(result, {
                'prediction': 1, 'model_score_class_1': 0.68, 'score_is_calibrated': False,
                'output_kind': 'dataset_label_classification', 'model_version': 'diabetes_keras_v1',
                'input_feature_names': list(FEATURE_NAMES),
            })

    def test_prediction_uses_point_five_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_artifacts(root)
            dummy_tf = SimpleNamespace(keras=SimpleNamespace(models=SimpleNamespace(load_model=lambda *_a, **_k: FakeModel(.499))))
            with patch.dict(sys.modules, {'tensorflow': dummy_tf}), patch('joblib.load', return_value=FakePreprocessor()):
                self.assertEqual(DLPredictionService(root, backend='keras').predict(SAMPLE)['prediction'], 0)

    def test_invalid_input_is_rejected_before_model_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FeatureValidationError):
                DLPredictionService(Path(tmp), backend='keras').predict({'age': 40})

    def test_invalid_keras_score_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_artifacts(root)
            dummy_tf = SimpleNamespace(keras=SimpleNamespace(models=SimpleNamespace(load_model=lambda *_a, **_k: FakeModel(float('nan')))))
            with patch.dict(sys.modules, {'tensorflow': dummy_tf}), patch('joblib.load', return_value=FakePreprocessor()):
                with self.assertRaises(ModelUnavailableError):
                    DLPredictionService(root, backend='keras').predict(SAMPLE)

    def test_cannot_use_unexpected_tensor_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_artifacts(root)
            bad_model = FakeModel(.8)
            bad_model.outputs = [SimpleNamespace(shape=(None, 2))]
            dummy_tf = SimpleNamespace(keras=SimpleNamespace(models=SimpleNamespace(load_model=lambda *_a, **_k: bad_model)))
            with patch.dict(sys.modules, {'tensorflow': dummy_tf}), patch('joblib.load', return_value=FakePreprocessor()):
                with self.assertRaises(ModelUnavailableError):
                    DLPredictionService(root, backend='keras').predict(SAMPLE)


class OptionalTrainedModelTests(unittest.TestCase):
    def test_live_keras_artifacts_if_present(self):
        svc = DLPredictionService(ROOT, backend='keras')
        if not (ROOT / 'outputs/keras_dlk1/experiment_manifest.json').is_file():
            self.skipTest('User-trained DL-K1 model is not present in this environment')
        self.assertEqual(svc.readiness(), 'ready', 'DL-K1 artifacts missing, altered or TensorFlow not installed')
        output = svc.predict(SAMPLE)
        self.assertEqual(output['model_version'], 'diabetes_keras_v1')
        self.assertTrue(0 <= output['model_score_class_1'] <= 1)
        self.assertFalse(output['score_is_calibrated'])


if __name__ == '__main__':
    unittest.main()
