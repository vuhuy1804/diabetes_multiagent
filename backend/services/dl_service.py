"""DL prediction facade: legacy scikit-learn or DL-K1 TensorFlow/Keras.

Select DL_MODEL_BACKEND=keras or sklearn in .env, then restart Flask.
No automatic fallback on error. Old standalone unit tests that supply an
explicit temporary root keep the historical sklearn default.
Never load untrusted local model artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from core.features import FEATURE_NAMES, validate_features

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE = "config/model_manifest.json"


class ModelUnavailableError(RuntimeError):
    """No verified training artifact is ready."""


def sha256_file(path: Path) -> str:
    hash_state = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hash_state.update(chunk)
    return hash_state.hexdigest()


class DLPredictionService:
    def __init__(self, root: Path | None = None, *, backend: str | None = None):
        # Backwards compatibility: historical tests instantiate DLPredictionService(tmp).
        # Production uses DLPredictionService() and selects via .env.
        self.root = Path(ROOT if root is None else root).resolve()
        selected = backend if backend is not None else (os.getenv('DL_MODEL_BACKEND', 'sklearn') if root is None else 'sklearn')
        self.backend = selected.strip().lower() if isinstance(selected, str) else 'invalid'
        self._keras_service = None
        self._pipeline = None
        self._manifest: dict | None = None

    def _keras(self):
        if self._keras_service is None:
            from services.keras_dl_service import KerasDLPredictionService
            self._keras_service = KerasDLPredictionService(root=self.root)
        return self._keras_service

    def _read_and_verify(self) -> tuple[dict, Path]:
        file = (self.root / os.environ.get("MODEL_MANIFEST_PATH", MANIFEST_FILE)).resolve()
        if not file.is_relative_to(self.root):
            raise ModelUnavailableError("Manifest path outside project")
        if not file.is_file():
            raise ModelUnavailableError("Model not trained: config/model_manifest.json missing")
        try:
            manifest = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            raise ModelUnavailableError("Model manifest cannot be read") from err
        if manifest.get("status") != "READY":
            raise ModelUnavailableError("Model manifest is not READY")
        if manifest.get("feature_names_in_training_order") != list(FEATURE_NAMES):
            raise ModelUnavailableError("Model feature schema does not match the project")
        relative = manifest.get("artifact_path")
        expected_hash = manifest.get("artifact_sha256")
        if not isinstance(relative, str) or not relative or not isinstance(expected_hash, str):
            raise ModelUnavailableError("Incomplete artifact path or checksum")
        artifact = (self.root / relative).resolve()
        if not artifact.is_relative_to(self.root) or not artifact.is_file():
            raise ModelUnavailableError("Model artifact missing or path outside project")
        if sha256_file(artifact) != expected_hash:
            raise ModelUnavailableError("Model SHA-256 does not match manifest")
        return manifest, artifact

    def readiness(self) -> str:
        if self.backend == 'keras':
            return self._keras().readiness()
        if self.backend != 'sklearn':
            return 'not_configured'
        try:
            self._read_and_verify()
            return "ready"
        except ModelUnavailableError:
            return "not_configured"

    def _get_pipeline(self):
        if self._pipeline is None:
            manifest, artifact = self._read_and_verify()
            try:
                self._pipeline = joblib.load(artifact)
                self._manifest = manifest
            except Exception as err:
                raise ModelUnavailableError("Unable to load trusted local model artifact") from err
            if not hasattr(self._pipeline, "predict_proba"):
                raise ModelUnavailableError("Loaded model has no predict_proba")
        return self._pipeline

    def predict(self, raw_features: Any) -> dict[str, Any]:
        if self.backend == 'keras':
            return self._keras().predict(raw_features)
        if self.backend != 'sklearn':
            raise ModelUnavailableError('Unsupported DL_MODEL_BACKEND; use keras or sklearn')
        validated = validate_features(raw_features)
        model = self._get_pipeline()
        # Explicitly preserve original training column order.
        frame = pd.DataFrame([[validated[name] for name in FEATURE_NAMES]], columns=list(FEATURE_NAMES))
        try:
            prediction = int(model.predict(frame)[0])
            class1_score = float(model.predict_proba(frame)[0, 1])
        except Exception as err:
            raise ModelUnavailableError("Model inference failed") from err
        if prediction not in (0, 1) or not 0.0 <= class1_score <= 1.0:
            raise ModelUnavailableError("Invalid inference outputs")
        return {
            "prediction": prediction,
            "model_score_class_1": round(class1_score, 6),
            "score_is_calibrated": False,
            "output_kind": "dataset_label_classification",
            "model_version": self._manifest["model_version"],
            "input_feature_names": list(FEATURE_NAMES),
        }
