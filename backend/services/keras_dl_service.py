"""Load the user-trained DL-K1 Keras model for *inference* (DL-K2).

Manifest: outputs/keras_dlk1/experiment_manifest.json (unchanged DL-K1 output).
Model: models/keras_dlk1/diabetes_keras_v1.keras.
Preprocessing: models/keras_dlk1/preprocessor.joblib.

This module never trains, writes model files, or silently falls back to sklearn.
Only load artifacts trained locally and trusted by the project owner. A hash
protects against accidental changes, not against a malicious model/manifest.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from core.features import FEATURE_NAMES, validate_features
from services.dl_service import ModelUnavailableError, ROOT, sha256_file

KERAS_MANIFEST = 'outputs/keras_dlk1/experiment_manifest.json'
KERAS_MODEL_PATH = 'models/keras_dlk1/diabetes_keras_v1.keras'
KERAS_PREPROCESSOR_PATH = 'models/keras_dlk1/preprocessor.joblib'
EXPECTED_VERSION = 'diabetes_keras_v1'


class KerasDLPredictionService:
    """Keras alternative satisfying the same public prediction contract."""

    def __init__(self, root: Path = ROOT):
        self.root = Path(root).resolve()
        self._model = None
        self._preprocessor = None
        self._manifest: dict[str, Any] | None = None

    def _trusted_path(self, relative: str, expected: str) -> Path:
        # Deliberately use fixed experiment locations, not arbitrary manifest paths.
        if relative != expected:
            raise ModelUnavailableError('Unexpected Keras experiment artifact location')
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root) or not target.is_file():
            raise ModelUnavailableError('Keras experiment artifact missing or outside project')
        return target

    def _read_and_verify(self) -> tuple[dict[str, Any], Path, Path]:
        manifest_path = (self.root / KERAS_MANIFEST).resolve()
        if not manifest_path.is_relative_to(self.root) or not manifest_path.is_file():
            raise ModelUnavailableError('DL-K1 experiment manifest is missing')
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ModelUnavailableError('Unable to read DL-K1 experiment manifest') from exc
        if not isinstance(manifest, dict):
            raise ModelUnavailableError('Invalid Keras experiment manifest')
        # DL-K1 writes EXPERIMENT_ONLY_NOT_INTEGRATED. Do not rewrite that file.
        if manifest.get('status') != 'EXPERIMENT_ONLY_NOT_INTEGRATED':
            raise ModelUnavailableError('Unexpected DL-K1 experiment status')
        if manifest.get('framework') != 'tensorflow.keras' or manifest.get('model_version') != EXPECTED_VERSION:
            raise ModelUnavailableError('Unexpected DL-K1 model identity')
        if manifest.get('feature_names_in_training_order') != list(FEATURE_NAMES):
            raise ModelUnavailableError('Keras training features differ from API contract')
        if manifest.get('decision_threshold') != 0.5 or manifest.get('score_is_calibrated') is not False:
            raise ModelUnavailableError('Unsupported Keras score semantics or decision threshold')
        architecture = manifest.get('architecture')
        if not isinstance(architecture, dict) or architecture.get('hidden_layers') != [64, 32] or architecture.get('output') != 'sigmoid':
            raise ModelUnavailableError('Unexpected Keras model architecture metadata')
        info = manifest.get('dataset_info')
        if (not isinstance(info, dict) or type(info.get('input_dim_after_encoding')) is not int
                or not 1 <= info['input_dim_after_encoding'] <= 4096):
            raise ModelUnavailableError('Invalid encoded model input dimension')
        model = self._trusted_path(manifest.get('model_relative_path'), KERAS_MODEL_PATH)
        preprocess = self._trusted_path(manifest.get('preprocessor_relative_path'), KERAS_PREPROCESSOR_PATH)
        for file, key in ((model, 'model_sha256'), (preprocess, 'preprocessor_sha256')):
            expected_hash = manifest.get(key)
            if not isinstance(expected_hash, str) or len(expected_hash) != 64 or sha256_file(file) != expected_hash:
                raise ModelUnavailableError('Keras artifact checksum does not match DL-K1 manifest')
        return manifest, model, preprocess

    def readiness(self) -> str:
        """Lightweight readiness check: existence, schema, hashes, TF availability.

        This does not deserialize .keras/.joblib (expensive); run a prediction for
        full verification. Checksum is rechecked when loading for inference.
        """
        try:
            self._read_and_verify()
            return 'ready' if importlib.util.find_spec('tensorflow') is not None else 'not_configured'
        except (ModelUnavailableError, OSError, ValueError):
            return 'not_configured'

    def _load(self):
        if self._model is not None:
            return self._model, self._preprocessor
        manifest, model_path, preprocess_path = self._read_and_verify()
        try:
            import tensorflow as tf  # lazy: old scikit-learn route remains lightweight
            # safe_mode=True prevents unsafe lambda deserialization in Keras 3.
            model = tf.keras.models.load_model(model_path, compile=False, safe_mode=True)
            preprocessor = joblib.load(preprocess_path)  # Own trusted local artifact only
            if not hasattr(preprocessor, 'transform'):
                raise TypeError('Missing preprocessor transform')
            # Probe with a synthetic vector; never inspect/persist patient data.
            if len(model.inputs) != 1 or model.inputs[0].shape[-1] != manifest['dataset_info']['input_dim_after_encoding']:
                raise ValueError('Keras model input shape does not match manifest')
            if len(model.outputs) != 1 or model.outputs[0].shape[-1] != 1:
                raise ValueError('Keras model output must have one score')
        except Exception as exc:
            raise ModelUnavailableError('Unable to load trusted local Keras model and preprocessor') from exc
        self._model = model
        self._preprocessor = preprocessor
        self._manifest = manifest
        return model, preprocessor

    def predict(self, raw_features: Any) -> dict[str, Any]:
        validated = validate_features(raw_features)
        model, preprocessor = self._load()
        frame = pd.DataFrame([[validated[n] for n in FEATURE_NAMES]], columns=list(FEATURE_NAMES))
        try:
            transformed = np.asarray(preprocessor.transform(frame), dtype=np.float32)
            expected_dim = self._manifest['dataset_info']['input_dim_after_encoding']
            if transformed.shape != (1, expected_dim) or not np.isfinite(transformed).all():
                raise ValueError('Invalid transformed data shape or values')
            raw_scores = np.asarray(model.predict(transformed, verbose=0))
            if raw_scores.shape != (1, 1):
                raise ValueError('Invalid Keras prediction tensor shape')
            score = float(raw_scores[0, 0])
            if not math.isfinite(score) or not 0.0 <= score <= 1.0:
                raise ValueError('Keras score out of range')
        except Exception as exc:
            raise ModelUnavailableError('Keras inference failed') from exc
        return {
            'prediction': int(score >= 0.5),
            'model_score_class_1': round(score, 6),
            'score_is_calibrated': False,
            'output_kind': 'dataset_label_classification',
            'model_version': self._manifest['model_version'],
            'input_feature_names': list(FEATURE_NAMES),
        }
