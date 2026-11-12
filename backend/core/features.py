"""Shared model input schema.

PHASE 1: This is minimal data-shape validation for safe standalone model
inference. Patient Data Agent (full normalization and audits) is PHASE 3.
There are intentionally NO clinical thresholds in this module.
"""
from __future__ import annotations

import math
from typing import Any

FEATURE_NAMES = (
    "gender",
    "age",
    "hypertension",
    "heart_disease",
    "smoking_history",
    "bmi",
    "HbA1c_level",
    "blood_glucose_level",
)
TARGET = "diabetes"

CATEGORICAL_VALUES = {
    "gender": ("Female", "Male", "Other"),
    "smoking_history": (
        "No Info", "current", "ever", "former", "never", "not current"
    ),
}
# Engineering sanity limits only, not clinical reference ranges or rules.
NUMERIC_BOUNDS = {
    "age": (0.0, 120.0),
    "bmi": (0.0, 150.0),
    "HbA1c_level": (0.0, 30.0),
    "blood_glucose_level": (0.0, 1000.0),
}
BINARY_FIELDS = ("hypertension", "heart_disease")


class FeatureValidationError(ValueError):
    """The model input does not follow its documented schema."""


def validate_features(raw: Any) -> dict[str, Any]:
    """Return canonical ordered features; refuse missing/extra/malformed input.

    This does not diagnose anything or perform Patient Data Agent rules.
    """
    if not isinstance(raw, dict):
        raise FeatureValidationError("features must be a JSON object")
    missing = [name for name in FEATURE_NAMES if name not in raw]
    extra = [name for name in raw if name not in FEATURE_NAMES]
    if missing or extra:
        raise FeatureValidationError(f"feature mismatch: missing={missing}, extra={extra}")

    clean: dict[str, Any] = {}
    for name in FEATURE_NAMES:
        value = raw[name]
        if name in CATEGORICAL_VALUES:
            if not isinstance(value, str) or value not in CATEGORICAL_VALUES[name]:
                raise FeatureValidationError(
                    f"{name} must be one of {list(CATEGORICAL_VALUES[name])}"
                )
            clean[name] = value
        elif name in BINARY_FIELDS:
            if type(value) is not int or value not in (0, 1):
                raise FeatureValidationError(f"{name} must be integer 0 or 1")
            clean[name] = value
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise FeatureValidationError(f"{name} must be a finite number")
            number = float(value)
            if not math.isfinite(number):
                raise FeatureValidationError(f"{name} must be a finite number")
            low, high = NUMERIC_BOUNDS[name]
            if not low <= number <= high:
                raise FeatureValidationError(
                    f"{name} is outside supported input range [{low}, {high}]"
                )
            clean[name] = number
    return clean
