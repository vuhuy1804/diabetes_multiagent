"""DL-K1: train a *separate* TensorFlow/Keras MLP experiment.

Run with .venv-keras, not the Flask/backend .venv.
Does not modify config/model_manifest.json or models/diabetes_mlp_v1.joblib.
The data and labels are for an educational prototype, not a clinical diagnosis.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from core.features import CATEGORICAL_VALUES, FEATURE_NAMES  # noqa: E402
from training.train_dl import load_training_data, sha256_file  # noqa: E402

SEED = 42
TEST_SIZE = 0.2
VALIDATION_FRACTION_WITHIN_TRAIN = 0.1
MODEL_VERSION = "diabetes_keras_v1"
EXPERIMENTS = frozenset({"keras_dlk1", "keras_dlk1_smoke"})
METRIC_KEYS = (
    "accuracy", "precision_positive", "recall_positive", "f1_positive",
    "roc_auc", "average_precision",
)


def experiment_paths(project_root: Path, experiment: str = "keras_dlk1") -> dict[str, Path]:
    """Resolve only whitelisted experiment names; never touch the active model."""
    if experiment not in EXPERIMENTS:
        raise ValueError("Unsupported experiment name")
    root = Path(project_root).resolve()
    model_dir = root / "models" / experiment
    output_dir = root / "outputs" / experiment
    paths = {
        "model": model_dir / f"{MODEL_VERSION}.keras",
        "preprocessor": model_dir / "preprocessor.joblib",
        "metrics": output_dir / "metrics.json",
        "manifest": output_dir / "experiment_manifest.json",
        "history": output_dir / "training_history.csv",
        "report": output_dir / "comparison_report.md",
        "chart_metrics": output_dir / "comparison_metrics.png",
        "chart_confusion": output_dir / "keras_confusion_matrix.png",
        "chart_loss": output_dir / "keras_training_loss.png",
    }
    forbidden = {
        (root / "models" / "diabetes_mlp_v1.joblib").resolve(),
        (root / "config" / "model_manifest.json").resolve(),
        (root / "outputs" / "dl_training_metrics.json").resolve(),
    }
    if any(path.resolve() in forbidden for path in paths.values()):
        raise RuntimeError("Experiment outputs overlap the active scikit-learn model")
    return paths


def split_and_preprocess(csv_path: Path, *, random_state: int = SEED):
    """Same dedup + outer test split as train_dl.py; separate training-only val.

    Unlike the original sklearn MLP, preprocessing is fitted only on the
    *fit* portion, not on validation or test, to avoid validation leakage.
    """
    x, y, info = load_training_data(Path(csv_path))
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=TEST_SIZE, random_state=random_state, stratify=y,
    )
    x_fit, x_val, y_fit, y_val = train_test_split(
        x_train, y_train, test_size=VALIDATION_FRACTION_WITHIN_TRAIN,
        random_state=random_state, stratify=y_train,
    )
    categorical = list(CATEGORICAL_VALUES)
    numeric = [col for col in FEATURE_NAMES if col not in categorical]
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), numeric),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
        ],
        remainder="drop",
    )
    x_fit_t = np.asarray(preprocessor.fit_transform(x_fit), dtype=np.float32)
    x_val_t = np.asarray(preprocessor.transform(x_val), dtype=np.float32)
    x_test_t = np.asarray(preprocessor.transform(x_test), dtype=np.float32)
    y_fit_t = y_fit.to_numpy(dtype=np.float32)
    y_val_t = y_val.to_numpy(dtype=np.float32)
    y_test_t = y_test.to_numpy(dtype=np.int64)
    if not (x_fit_t.shape[1] == x_val_t.shape[1] == x_test_t.shape[1]):
        raise RuntimeError("Encoded feature dimensions do not match")
    if not np.isfinite(x_fit_t).all() or not np.isfinite(x_val_t).all() or not np.isfinite(x_test_t).all():
        raise ValueError("Non-finite value after preprocessing")
    split_info = {
        "train_rows_total": int(len(x_train)),
        "fit_rows": int(len(x_fit)),
        "validation_rows": int(len(x_val)),
        "test_rows": int(len(x_test)),
        "input_dim_after_encoding": int(x_fit_t.shape[1]),
        "positive_test_rows": int(y_test_t.sum()),
        "class_counts_deduplicated": info["class_counts"],
        "dropped_exact_duplicates": info["dropped_exact_duplicates"],
    }
    return preprocessor, (x_fit_t, y_fit_t), (x_val_t, y_val_t), (x_test_t, y_test_t), split_info


def evaluate_predictions(y_true: np.ndarray, score: np.ndarray, threshold: float = 0.5) -> dict:
    """Pure evaluation function, independently unit-testable without TensorFlow."""
    true = np.asarray(y_true, dtype=np.int64).reshape(-1)
    s = np.asarray(score, dtype=float).reshape(-1)
    if true.size == 0 or s.shape != true.shape or set(np.unique(true)) != {0, 1}:
        raise ValueError("Evaluation requires binary labels for both classes and matching scores")
    if not (np.isfinite(s).all() and ((0.0 <= s) & (s <= 1.0)).all()):
        raise ValueError("Model scores must be finite between 0 and 1")
    if not 0.0 < threshold < 1.0:
        raise ValueError("Invalid evaluation threshold")
    pred = (s >= threshold).astype(np.int64)
    return {
        "accuracy": round(float(accuracy_score(true, pred)), 5),
        "precision_positive": round(float(precision_score(true, pred, zero_division=0)), 5),
        "recall_positive": round(float(recall_score(true, pred, zero_division=0)), 5),
        "f1_positive": round(float(f1_score(true, pred, zero_division=0)), 5),
        "roc_auc": round(float(roc_auc_score(true, s)), 5),
        "average_precision": round(float(average_precision_score(true, s)), 5),
        "confusion_matrix_0_1": confusion_matrix(true, pred, labels=[0, 1]).tolist(),
        "test_rows": int(true.size),
        "threshold": float(threshold),
    }


def load_sklearn_reference(root: Path, csv_hash: str) -> tuple[dict | None, str]:
    """Use local old result for comparison; never fabricate missing metrics."""
    root = Path(root)
    metrics_file = root / "outputs" / "dl_training_metrics.json"
    manifest_file = root / "config" / "model_manifest.json"
    if not metrics_file.is_file() or not manifest_file.is_file():
        return None, "Chưa tìm thấy đủ metrics và manifest của mô hình scikit-learn cũ."
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        baseline = json.loads(metrics_file.read_text(encoding="utf-8"))
        if manifest.get("dataset_sha256") != csv_hash:
            raise ValueError("CSV differs from the sklearn baseline dataset: comparison is not valid")
        if not all(isinstance(baseline.get(k), (float, int)) for k in METRIC_KEYS):
            return None, "Metrics của scikit-learn không đủ để đối chiếu."
        return baseline, "Cùng SHA256 dataset; cùng seed=42, cùng tỷ lệ outer train/test=80/20."
    except ValueError:
        raise
    except (OSError, TypeError, json.JSONDecodeError) as err:
        return None, f"Không đọc được metrics cũ: {type(err).__name__}"


def write_comparison_report(
    metrics: dict, old: dict | None, info: dict, reference_note: str
) -> str:
    lines = [
        "# DL-K1 — So sánh TensorFlow/Keras và scikit-learn MLP",
        "",
        "> Thử nghiệm kỹ thuật phục vụ môn học; không phải hệ thống chẩn đoán y khoa.",
        "",
        "## Phương pháp",
        "",
        "- Model mới: Keras Dense(64, ReLU) → Dense(32, ReLU) → Dense(1, sigmoid).",
        "- Preprocessing: StandardScaler + OneHotEncoder, fit **chỉ trên tập train con**.",
        "- Tách dữ liệu sau loại bản ghi trùng: 80% train, 20% test; 10% train dành cho validation.",
        "- Seed = 42, stratify theo nhãn; test dùng một lần để báo cáo; ngưỡng = 0.5.",
        f"- Số dòng train tổng: {info['train_rows_total']}; fit: {info['fit_rows']}; validation: {info['validation_rows']}; test: {info['test_rows']}.",
        f"- Đặc trưng sau mã hóa: {info['input_dim_after_encoding']}.",
        f"- Mức độ so sánh với baseline: {reference_note}",
        "",
        "## Chỉ số kiểm thử",
        "",
        "| Chỉ số | Keras mới | scikit-learn cũ | Chênh lệch (Keras - cũ) |",
        "|---|---:|---:|---:|",
    ]
    for key in METRIC_KEYS:
        cur = float(metrics[key])
        before = float(old[key]) if old is not None else None
        lines.append(f"| {key} | {cur:.5f} | {before:.5f} | {cur - before:+.5f} |" if before is not None else f"| {key} | {cur:.5f} | — | — |")
    lines += [
        "",
        "## Confusion Matrix — Keras (hàng: nhãn thật 0/1; cột: dự đoán 0/1)",
        "",
        "| | Pred 0 | Pred 1 |",
        "|---|---:|---:|",
        f"| True 0 | {metrics['confusion_matrix_0_1'][0][0]} | {metrics['confusion_matrix_0_1'][0][1]} |",
        f"| True 1 | {metrics['confusion_matrix_0_1'][1][0]} | {metrics['confusion_matrix_0_1'][1][1]} |",
        "",
        "## Giới hạn",
        "",
        "- Dataset mất cân bằng; đánh giá recall/F1/Average Precision lớp 1 bên cạnh accuracy.",
        "- TensorFlow và scikit-learn khác cơ chế khởi tạo, early stopping và tối ưu nên kết quả không bắt buộc bằng nhau.",
        "- Dữ liệu đã loại **exact duplicates**, nhưng chưa kiểm chứng có nhiều bản ghi của cùng bệnh nhân hay không.",
        "- Không hiệu chỉnh (calibrate) điểm sigmoid thành xác suất lâm sàng.",
        "- Không thay đổi ngưỡng dựa trên tập test; không được diễn giải nhãn dự đoán thành chẩn đoán.",
        "- Khi sử dụng Keras trong backend chính phải cập nhật service và kiểm thử tích hợp ở DL-K2.",
        "",
        "## Biểu đồ có trong thư mục kết quả",
        "",
        "- `comparison_metrics.png` — biểu đồ các chỉ số tổng hợp có thật.",
        "- `keras_confusion_matrix.png` — confusion matrix trên tập test.",
        "- `keras_training_loss.png` — train/validation loss qua từng epoch thực tế.",
        "",
    ]
    return "\n".join(lines)


def save_charts(paths: dict[str, Path], metrics: dict, old: dict | None, history: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = ["Accuracy", "Precision", "Recall", "F1", "ROC-AUC", "Avg. Precision"]
    keys = list(METRIC_KEYS)
    positions = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    width = .36 if old else .65
    ax.bar(positions - (width / 2 if old else 0), [metrics[k] for k in keys], width, label="Keras")
    if old:
        ax.bar(positions + width / 2, [old[k] for k in keys], width, label="scikit-learn")
    ax.set_xticks(positions, names, rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Test metrics: Keras vs sklearn")
    ax.legend() if old else None
    fig.tight_layout()
    fig.savefig(paths["chart_metrics"], dpi=160)
    plt.close(fig)

    cm = np.asarray(metrics["confusion_matrix_0_1"])
    fig, ax = plt.subplots(figsize=(5.2, 4.5))
    ax.imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i,j]:,}", ha="center", va="center", color="black", fontsize=14)
    ax.set_xticks([0, 1], ["Pred 0", "Pred 1"])
    ax.set_yticks([0, 1], ["True 0", "True 1"])
    ax.set_title("Keras confusion matrix")
    fig.tight_layout()
    fig.savefig(paths["chart_confusion"], dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(history["loss"], label="Train loss")
    ax.plot(history["val_loss"], label="Validation loss")
    ax.set_xlabel("Epoch (from 0)")
    ax.set_ylabel("Binary cross-entropy")
    ax.set_title("Training loss — actual Keras history")
    ax.legend()
    fig.tight_layout()
    fig.savefig(paths["chart_loss"], dpi=160)
    plt.close(fig)


def train_keras_experiment(
    csv_path: Path, project_root: Path = ROOT, *, epochs: int = 80,
    batch_size: int = 256, experiment: str = "keras_dlk1", overwrite: bool = False,
) -> dict:
    if not 2 <= epochs <= 1000 or not 16 <= batch_size <= 8192:
        raise ValueError("Use epochs=2..1000 and batch_size=16..8192")
    paths = experiment_paths(project_root, experiment)
    existing = [str(p) for p in paths.values() if p.exists()]
    if existing and not overwrite:
        raise FileExistsError("Experiment outputs already exist; rerun with --overwrite only if intended")
    csv_path = Path(csv_path).resolve()
    csv_hash = sha256_file(csv_path)  # fail early if dataset missing
    if experiment == "keras_dlk1_smoke":
        # Synthetic smoke MUST NOT be compared to the public dataset baseline.
        baseline, baseline_note = None, "Synthetic smoke only — do not report these scores."
    else:
        baseline, baseline_note = load_sklearn_reference(Path(project_root), csv_hash)
    preprocessor, train, val, test, dataset_info = split_and_preprocess(csv_path)

    # Import only when training; old Flask venv can still run unit tests.
    import tensorflow as tf
    random.seed(SEED)
    np.random.seed(SEED)
    tf.keras.utils.set_random_seed(SEED)
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(train[0].shape[1],)),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ], name="diabetes_keras_mlp")
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss="binary_crossentropy", metrics=["accuracy"])
    history = model.fit(
        train[0], train[1], validation_data=val,
        epochs=epochs, batch_size=batch_size,
        callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True)],
        verbose=2,
    )
    scores = model.predict(test[0], batch_size=1024, verbose=0).reshape(-1)
    metrics = evaluate_predictions(test[1], scores)
    metrics["epochs_executed"] = len(history.history["loss"])
    metrics["test_positive_count"] = int(test[1].sum())
    metrics["test_negative_count"] = int(len(test[1]) - test[1].sum())

    for p in paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    model.save(paths["model"])
    joblib.dump(preprocessor, paths["preprocessor"])
    pd.DataFrame(history.history).to_csv(paths["history"], index_label="epoch_zero_based")
    paths["metrics"].write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Verify that a saved Keras model and own preprocessor can be reopened.
    loaded_model = tf.keras.models.load_model(paths["model"], compile=False)
    reloaded_scores = loaded_model.predict(test[0][:5], verbose=0).reshape(-1)
    if not np.allclose(reloaded_scores, scores[:5], rtol=1e-5, atol=1e-5):
        raise RuntimeError("Saved Keras model outputs differ from original outputs")
    reloaded_preprocessor = joblib.load(paths["preprocessor"])  # our own trusted local artifact
    demo_frame = pd.DataFrame([{
        "gender": "Female", "age": 44, "hypertension": 0,
        "heart_disease": 0, "smoking_history": "never", "bmi": 27.32,
        "HbA1c_level": 5.7, "blood_glucose_level": 140,
    }], columns=list(FEATURE_NAMES))
    if reloaded_preprocessor.transform(demo_frame).shape[1] != dataset_info["input_dim_after_encoding"]:
        raise RuntimeError("Saved preprocessor encoded feature count changed")

    manifest = {
        "status": "EXPERIMENT_ONLY_NOT_INTEGRATED",
        "model_version": MODEL_VERSION,
        "framework": "tensorflow.keras",
        "tensorflow_version": tf.__version__,
        "sklearn_version": sklearn.__version__,
        "feature_names_in_training_order": list(FEATURE_NAMES),
        "model_relative_path": str(paths["model"].relative_to(Path(project_root).resolve())).replace("\\", "/"),
        "preprocessor_relative_path": str(paths["preprocessor"].relative_to(Path(project_root).resolve())).replace("\\", "/"),
        "model_sha256": sha256_file(paths["model"]),
        "preprocessor_sha256": sha256_file(paths["preprocessor"]),
        "dataset_sha256": csv_hash,
        "dataset_info": dataset_info,
        "architecture": {"hidden_layers": [64, 32], "activation": "relu", "output": "sigmoid"},
        "test_metrics": metrics,
        "split": {"seed": SEED, "test_fraction": TEST_SIZE,
                  "validation_fraction_of_train": VALIDATION_FRACTION_WITHIN_TRAIN},
        "decision_threshold": 0.5,
        "score_is_calibrated": False,
        "clinical_diagnosis": False,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_comparison_note": baseline_note,
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["report"].write_text(write_comparison_report(metrics, baseline, dataset_info, baseline_note), encoding="utf-8")
    save_charts(paths, metrics, baseline, history.history)
    return {"metrics": metrics, "paths": {k: str(v) for k, v in paths.items()}, "baseline_note": baseline_note}


def main():
    parser = argparse.ArgumentParser(description="Independent TensorFlow/Keras experiment; active sklearn model unchanged")
    parser.add_argument("--data", type=Path, default=ROOT / "data/raw/diabetes_prediction_dataset.csv")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--experiment", choices=sorted(EXPERIMENTS), default="keras_dlk1")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite outputs of this experiment only")
    args = parser.parse_args()
    outcome = train_keras_experiment(args.data, epochs=args.epochs, batch_size=args.batch_size,
                                     experiment=args.experiment, overwrite=args.overwrite)
    print("DL-K1 TRAIN COMPLETE — EXPERIMENT ONLY, NOT IN FLASK")
    print(json.dumps(outcome, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
