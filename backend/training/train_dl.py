"""Train a compact 2-hidden-layer MLP from a user-supplied public CSV.

Invoke from project root:
  .\\.venv\\Scripts\\python.exe backend/training/train_dl.py

NEVER treat this model's class predictions as clinical diagnosis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn import __version__ as sklearn_version
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score,
                             average_precision_score)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from core.features import (  # noqa: E402
    BINARY_FIELDS, CATEGORICAL_VALUES, FEATURE_NAMES, NUMERIC_BOUNDS, TARGET
)

PROJECT_ROOT = BACKEND.parent
DATASET_SOURCE = "https://www.kaggle.com/datasets/iammustafatz/diabetes-prediction-dataset"
MODEL_RELATIVE_PATH = "models/diabetes_mlp_v1.joblib"
MANIFEST_RELATIVE_PATH = "config/model_manifest.json"
METRICS_RELATIVE_PATH = "outputs/dl_training_metrics.json"
MODEL_VERSION = "diabetes_mlp_v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_training_data(path: Path) -> tuple[pd.DataFrame, pd.Series, dict]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing dataset: {path}\n"
            "Download diabetes_prediction_dataset.csv from Kaggle and place it in data/raw/."
        )
    data = pd.read_csv(path)
    required = [*FEATURE_NAMES, TARGET]
    missing = [name for name in required if name not in data.columns]
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    data = data.loc[:, required].copy()
    if data.isna().any().any():
        raise ValueError("Dataset has missing values. Check dataset version and clean it first.")
    original_rows = len(data)
    data = data.drop_duplicates().reset_index(drop=True)
    if len(data) < 100:
        raise ValueError("At least 100 unique rows are required for this demonstration.")

    for name in (*NUMERIC_BOUNDS, *BINARY_FIELDS, TARGET):
        data[name] = pd.to_numeric(data[name], errors="raise")
        if not np.isfinite(data[name].to_numpy(dtype=float)).all():
            raise ValueError(f"Non-finite numeric values in {name}")
    for name in CATEGORICAL_VALUES:
        unusual = sorted(set(data[name].unique()) - set(CATEGORICAL_VALUES[name]))
        if unusual:
            raise ValueError(f"Unsupported category in {name}: {unusual}")
    for name in (*BINARY_FIELDS, TARGET):
        if not data[name].isin([0, 1]).all():
            raise ValueError(f"{name} contains values other than 0/1")
    for name, (low, high) in NUMERIC_BOUNDS.items():
        if not data[name].between(low, high).all():
            raise ValueError(f"{name} contains unsupported values outside {low}..{high}")
    distribution = data[TARGET].value_counts().to_dict()
    if set(distribution) != {0, 1} or min(distribution.values()) < 20:
        raise ValueError("Need both label classes with at least 20 examples each.")
    info = {
        "original_rows": int(original_rows),
        "unique_rows": int(len(data)),
        "dropped_exact_duplicates": int(original_rows - len(data)),
        "class_counts": {str(k): int(v) for k, v in sorted(distribution.items())},
    }
    return data.loc[:, list(FEATURE_NAMES)], data[TARGET].astype(int), info


def train_model(
    csv_path: Path,
    output_root: Path = PROJECT_ROOT,
    *,
    random_state: int = 42,
    max_iter: int = 80,
) -> dict:
    csv_path = Path(csv_path).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()
    X, y, dataset_stats = load_training_data(csv_path)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=random_state, stratify=y,
    )

    categorical_cols = list(CATEGORICAL_VALUES)
    numeric_cols = [name for name in FEATURE_NAMES if name not in categorical_cols]
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), numeric_cols),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_cols),
        ],
        remainder="drop",
    )
    # Two nonlinear hidden layers = small multilayer neural network.
    # For a course demo, sklearn makes CPU training and serialization simpler.
    classifier = MLPClassifier(
        hidden_layer_sizes=(64, 32), activation="relu", solver="adam",
        batch_size=256, learning_rate_init=0.001, max_iter=max_iter,
        early_stopping=True, validation_fraction=0.1,
        n_iter_no_change=8, random_state=random_state,
    )
    pipeline = Pipeline([("preprocess", preprocessor), ("mlp", classifier)])
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_score = pipeline.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 5),
        "precision_positive": round(float(precision_score(y_test, y_pred, zero_division=0)), 5),
        "recall_positive": round(float(recall_score(y_test, y_pred, zero_division=0)), 5),
        "f1_positive": round(float(f1_score(y_test, y_pred, zero_division=0)), 5),
        "roc_auc": round(float(roc_auc_score(y_test, y_score)), 5),
        "average_precision": round(float(average_precision_score(y_test, y_score)), 5),
        "confusion_matrix_0_1": confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist(),
        "train_rows": len(X_train), "test_rows": len(X_test),
        "fitted_iterations": int(classifier.n_iter_),
    }
    model_path = output_root / MODEL_RELATIVE_PATH
    manifest_path = output_root / MANIFEST_RELATIVE_PATH
    metrics_path = output_root / METRICS_RELATIVE_PATH
    for path in (model_path, manifest_path, metrics_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    model_tmp = model_path.with_suffix(".tmp")
    try:
        joblib.dump(pipeline, model_tmp)
        os.replace(model_tmp, model_path)
    finally:
        model_tmp.unlink(missing_ok=True)

    manifest = {
        "status": "READY",
        "model_name": "2-hidden-layer MLP (scikit-learn)",
        "framework": "scikit-learn",
        "artifact_path": MODEL_RELATIVE_PATH,
        "artifact_sha256": sha256_file(model_path),
        "preprocessor_path": "embedded_in_pipeline",
        "feature_names_in_training_order": list(FEATURE_NAMES),
        "target_label_mapping": {"0": "dataset_label_0", "1": "dataset_label_1"},
        "output_semantics": "Binary dataset-label classification; score is UNCALIBRATED class-1 model output, NOT a clinical probability or diagnosis.",
        "model_version": MODEL_VERSION,
        "architecture": {"hidden_layers": [64, 32], "activation": "relu"},
        "decision_threshold": 0.5,
        "dataset_source": DATASET_SOURCE,
        "dataset_sha256": sha256_file(csv_path),
        "dataset_summary": dataset_stats,
        "evaluation_metrics": metrics,
        "training_method": "80% stratified training / 20% untouched test, internal early stopping only in train split; removed exact duplicate rows before split.",
        "sklearn_version": sklearn_version,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "prototype_only": True,
    }
    # Metadata is saved ONLY after the real artifact is written.
    for dest, value in ((metrics_path, metrics), (manifest_path, manifest)):
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a real MLP model from the Kaggle diabetes CSV")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data/raw/diabetes_prediction_dataset.csv")
    parser.add_argument("--max-iter", type=int, default=80,
                        help="Maximum optimizer epochs. 80 by default; early stopping may end earlier.")
    args = parser.parse_args()
    if args.max_iter < 5:
        parser.error("--max-iter must be >= 5")
    manifest = train_model(args.data, output_root=PROJECT_ROOT, max_iter=args.max_iter)
    print("TRAINING COMPLETE (educational prototype; NOT a medical diagnostic model)")
    print(f"Model: {MODEL_RELATIVE_PATH}")
    print(f"Manifest: {MANIFEST_RELATIVE_PATH}")
    print(f"Metrics: {METRICS_RELATIVE_PATH}")
    print(json.dumps(manifest["evaluation_metrics"], indent=2))


if __name__ == "__main__":
    main()
