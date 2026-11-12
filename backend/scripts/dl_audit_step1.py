"""Read-only audit of Phase-1 MLP training artifacts (Python standard library only).

Runs from project root:
    .\\.venv\\Scripts\\python.exe backend/scripts/dl_audit_step1.py

It does NOT deserialize .joblib, retrain a model, query Neo4j, or modify an existing artifact.
It writes only aggregate audit reports into outputs/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_FEATURES = [
    "gender", "age", "hypertension", "heart_disease", "smoking_history", "bmi",
    "HbA1c_level", "blood_glucose_level",
]
EXPECTED_METRICS = ["accuracy", "precision_positive", "recall_positive", "f1_positive", "roc_auc", "average_precision"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        result = json.load(handle)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def as_nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def in_root(root: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel:
        raise ValueError("Invalid relative path")
    absolute = (root / rel).resolve()
    if not absolute.is_relative_to(root.resolve()):
        raise ValueError("Artifact path must stay inside project root")
    return absolute


def compute_confusion_metrics(matrix: Any) -> dict[str, float | int]:
    if not (isinstance(matrix, list) and len(matrix) == 2 and all(isinstance(r, list) and len(r) == 2 for r in matrix)):
        raise ValueError("confusion_matrix_0_1 must be [[TN, FP], [FN, TP]]")
    tn, fp = (as_nonnegative_int(matrix[0][0], "TN"), as_nonnegative_int(matrix[0][1], "FP"))
    fn, tp = (as_nonnegative_int(matrix[1][0], "FN"), as_nonnegative_int(matrix[1][1], "TP"))
    total = tn + fp + fn + tp
    if total == 0:
        raise ValueError("Confusion matrix is empty")
    safe_div = lambda a,b: a/b if b else 0.0
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "tn": tn, "fp": fp, "fn": fn, "tp": tp, "test_rows_from_cm": total,
        "test_positive_rows": fn + tp, "test_negative_rows": tn + fp,
        "test_positive_fraction": round((fn + tp) / total, 6),
        "majority_class_accuracy_baseline": round(max((tn + fp), (fn + tp)) / total, 6),
        "accuracy": (tn + tp) / total,
        "precision_positive": precision, "recall_positive": recall, "f1_positive": f1,
        "specificity_negative": safe_div(tn, tn + fp),
        "balanced_accuracy": (recall + safe_div(tn, tn + fp)) / 2,
    }


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []
    summary: dict[str, Any] = {}
    metrics_file = root / "outputs/dl_training_metrics.json"
    manifest_file = root / "config/model_manifest.json"
    report = {
        "audit_kind": "artifact_consistency_and_test_metrics_not_clinical_validation",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL", "errors": errors, "warnings": warnings,
        "checks": checks, "summary": summary,
    }
    try:
        manifest = read_json(manifest_file)
        metrics = read_json(metrics_file)
    except (FileNotFoundError, PermissionError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Unable to read manifest or metrics: {type(exc).__name__}: {exc}")
        return report

    if manifest.get("status") != "READY":
        errors.append("Manifest status is not READY")
    if manifest.get("feature_names_in_training_order") != EXPECTED_FEATURES:
        errors.append("Model feature order is different from Phase-1 eight-feature schema")
    else:
        checks.append("Eight training features and order match project schema")
    summary["model_version"] = manifest.get("model_version")
    summary["architecture"] = manifest.get("architecture")
    summary["training_method"] = manifest.get("training_method")
    summary["model_score_is_calibrated"] = False

    try:
        model = in_root(root, manifest.get("artifact_path"))
        if not model.is_file():
            errors.append(f"Model artifact missing: {model}")
        else:
            model_hash = sha256_file(model)
            if model_hash != manifest.get("artifact_sha256"):
                errors.append("Model SHA256 does not match manifest")
            else:
                checks.append("Model artifact SHA256 matches manifest (file not deserialized)")
            summary["model_size_bytes"] = model.stat().st_size
    except (TypeError, ValueError, OSError) as exc:
        errors.append(f"Model artifact verification failed: {exc}")

    dataset = root / "data/raw/diabetes_prediction_dataset.csv"
    if dataset.is_file():
        try:
            if sha256_file(dataset) != manifest.get("dataset_sha256"):
                warnings.append("Original training CSV SHA256 is different from manifest: check dataset version")
            else:
                checks.append("Original CSV SHA256 matches training manifest")
        except OSError as exc:
            warnings.append(f"Could not hash original CSV: {exc}")
    else:
        warnings.append("Original CSV is unavailable; dataset hash could not be checked")

    dataset_stats = manifest.get("dataset_summary")
    if isinstance(dataset_stats, dict):
        summary["dataset_summary"] = dataset_stats
        counts = dataset_stats.get("class_counts")
        if isinstance(counts, dict):
            try:
                c0 = as_nonnegative_int(counts.get("0"), "class_counts.0")
                c1 = as_nonnegative_int(counts.get("1"), "class_counts.1")
                if c0 + c1:
                    summary["positive_class_fraction_full_dataset"] = round(c1 / (c0 + c1), 6)
                    if min(c0,c1) / (c0+c1) < 0.15:
                        warnings.append("Dataset class distribution is imbalanced (<15% minority); focus on positive recall/F1/PR-AUC rather than accuracy alone")
            except ValueError as exc:
                warnings.append(f"Manifest class count issue: {exc}")
    else:
        warnings.append("No dataset_summary found in manifest")

    try:
        cm = compute_confusion_metrics(metrics.get("confusion_matrix_0_1"))
        summary["confusion_matrix"] = {k:cm[k] for k in ("tn","fp","fn","tp")}
        summary["derived_test_metrics"] = {
            k: round(float(cm[k]), 5) for k in (
                "accuracy", "precision_positive", "recall_positive", "f1_positive",
                "specificity_negative", "balanced_accuracy",
            )
        }
        summary["test_rows"] = cm["test_rows_from_cm"]
        summary["test_positive_fraction"] = cm["test_positive_fraction"]
        summary["majority_class_accuracy_baseline"] = cm["majority_class_accuracy_baseline"]
        for key in ("accuracy", "precision_positive", "recall_positive", "f1_positive"):
            original = metrics.get(key)
            if isinstance(original, bool) or not isinstance(original, (int, float)) or not math.isfinite(original):
                errors.append(f"Metric {key} is missing or invalid")
            elif abs(cm[key] - original) > 1.1e-5:
                errors.append(f"Saved {key}={original} inconsistent with confusion matrix: {cm[key]:.5f}")
        if cm["test_rows_from_cm"] != metrics.get("test_rows"):
            errors.append("test_rows does not equal the sum of the confusion matrix")
        else:
            checks.append("Confusion matrix, accuracy, precision, recall, F1 and test row count are consistent")
        if cm["test_positive_rows"] > 0 and cm["recall_positive"] < 0.7:
            warnings.append("Positive-class recall is below 0.70; inspect false negatives and class imbalance")
        if cm["accuracy"] <= cm["majority_class_accuracy_baseline"]:
            warnings.append("Accuracy does not exceed majority-class baseline; consider balanced metrics")
        if cm["accuracy"] > 0.99:
            warnings.append("Accuracy exceeds 0.99; verify dataset design and any possibility of information leakage, without assuming leakage")
    except ValueError as exc:
        errors.append(str(exc))

    for key in EXPECTED_METRICS:
        value = metrics.get(key)
        if not (isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0 <= value <= 1):
            errors.append(f"Metric {key} must be finite in [0,1]")
        else:
            summary[key] = value
    for key in ("train_rows", "test_rows", "fitted_iterations"):
        value = metrics.get(key)
        if not isinstance(value, int) or isinstance(value,bool) or value <= 0:
            errors.append(f"{key} must be a positive integer")
        else:
            summary[key] = value
    if isinstance(dataset_stats, dict):
        unique_rows = dataset_stats.get("unique_rows")
        if isinstance(unique_rows, int) and isinstance(metrics.get("train_rows"),int) and isinstance(metrics.get("test_rows"),int):
            if metrics["train_rows"]+metrics["test_rows"] != unique_rows:
                errors.append("Train + test rows does not equal number of unique records")
            else:
                checks.append("Train/test row totals match deduplicated dataset size")
    if isinstance(manifest.get("evaluation_metrics"), dict):
        for name in EXPECTED_METRICS + ["confusion_matrix_0_1", "train_rows", "test_rows", "fitted_iterations"]:
            if metrics.get(name) != manifest["evaluation_metrics"].get(name):
                errors.append(f"Manifest and metrics file disagree on {name}")
        if not any("Manifest and metrics" in e for e in errors):
            checks.append("Metrics embedded in manifest match outputs/dl_training_metrics.json")
    else:
        warnings.append("Manifest does not embed evaluation_metrics")
    summary["interpretation"] = (
        "These are held-out test-set results from the training script, not external or clinical validation; "
        "model_score_class_1 is uncalibrated."
    )
    report["status"] = "PASS_WITH_WARNINGS" if warnings and not errors else ("PASS" if not errors else "FAIL")
    return report


def report_to_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Kiểm tra mô hình Deep Learning — Bước DL-1", "",
        f"- Trạng thái: **{report['status']}**",
        f"- Phiên bản: `{s.get('model_version', 'UNKNOWN')}`",
        "- Phạm vi: đối chiếu metadata và metrics đã lưu; **không** kiểm định y khoa.", "",
        "## Chỉ số trên tập test", "",
        "| Chỉ số | Giá trị |", "|---|---:|",
    ]
    for k, label in [
        ("train_rows", "Train rows"), ("test_rows", "Test rows"),
        ("accuracy", "Accuracy"), ("precision_positive", "Precision (class 1)"),
        ("recall_positive", "Recall (class 1)"), ("f1_positive", "F1 (class 1)"),
        ("roc_auc", "ROC-AUC"), ("average_precision", "Average Precision (PR-AUC summary)"),
        ("majority_class_accuracy_baseline", "Majority-class baseline accuracy"),
        ("test_positive_fraction", "Positive-class fraction in test"),
    ]:
        lines.append(f"| {label} | {s.get(k, 'N/A')} |")
    cm = s.get("confusion_matrix")
    if cm:
        lines += ["", "## Confusion matrix", "", "| | Dự đoán 0 | Dự đoán 1 |", "|---|---:|---:|", f"| Thực tế 0 | {cm['tn']} | {cm['fp']} |", f"| Thực tế 1 | {cm['fn']} | {cm['tp']} |"]
    lines += ["", "## Kiểm tra PASS", ""]
    lines.extend([f"- {c}" for c in report["checks"]] or ["- Không có mục nào."])
    lines += ["", "## Cảnh báo cần xem xét", ""]
    lines.extend([f"- {w}" for w in report["warnings"]] or ["- Không có cảnh báo tự động."])
    lines += ["", "## Lỗi dữ liệu hoặc artifact", ""]
    lines.extend([f"- {e}" for e in report["errors"]] or ["- Không phát hiện lỗi nhất quán."])
    lines += ["", "## Giới hạn", "", "- Không kiểm tra leakage ở cấp bệnh nhân hoặc chất lượng lâm sàng.", "- Không nạp file joblib hoặc đánh giá lại trên tập test; chỉ đọc chỉ số đã lưu.", "- Để kết luận chất lượng phải xem thêm dữ liệu, nhãn và phương pháp chia tập.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit saved Phase-1 DL metrics and hashes without loading joblib")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Root directory of diabetes-multiagent")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    result = audit(root)
    dest = root / "outputs"
    dest.mkdir(parents=True, exist_ok=True)
    json_path = dest / "dl_audit_step1.json"
    md_path = dest / "dl_audit_step1.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(report_to_markdown(result), encoding="utf-8")
    print("DL STEP 1 AUDIT:", result["status"])
    print("Checks:", len(result["checks"]), "Warnings:", len(result["warnings"]), "Errors:", len(result["errors"]))
    print("Report:", md_path)
    print("JSON:", json_path)
    for error in result["errors"]:
        print("ERROR:", error)
    for warning in result["warnings"]:
        print("WARNING:", warning)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
