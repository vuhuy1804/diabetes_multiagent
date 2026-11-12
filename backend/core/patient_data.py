"""Phase 3 patient feature validation and conservative normalization.

The agent checks the *data contract*, not whether a person has diabetes.
Existing Phase 1 core.features.validate_features remains the final model schema.
No clinical thresholds, medication rules, database writes, or missing-value guesses.
"""
from __future__ import annotations

import math
import re
from typing import Any

from core.features import (
    BINARY_FIELDS,
    CATEGORICAL_VALUES,
    FEATURE_NAMES,
    NUMERIC_BOUNDS,
    FeatureValidationError,
    validate_features,
)

# Only explicit dot-decimal ASCII numerals, not locale-dependent comma numbers,
# exponents, special IEEE floats (NaN/Inf), or loose float() conversions.
_DECIMAL = re.compile(r"-?\d+(?:\.\d+)?\Z", flags=re.ASCII)


class PatientDataValidationError(ValueError):
    """Failure with actionable, field-level errors, without echoing private input."""

    def __init__(self, issues: list[dict[str, str]]):
        self.issues = issues
        super().__init__("Patient feature validation failed")


def _issue(field: str, code: str, message: str) -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def normalize_patient_features(raw: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Validate eight DL features; return canonical ordered mapping and change log.

    Accept only deterministic, non-ambiguous normalization:
    * known category with surrounding/internal whitespace or different letter case;
    * dot-decimal numeric string -> float (e.g. ' 27.32 ');
    * exact '0'/'1' string -> integer flag.

    Reject missing/unknown features, nulls, booleans, nonfinite numbers, values
    beyond existing engineering bounds, and ambiguous comma-decimal strings.
    Never infer missing values or use medical rules. Does not mutate ``raw``.
    """
    if not isinstance(raw, dict):
        raise PatientDataValidationError([
            _issue("features", "not_object", "features must be a JSON object")
        ])

    issues: list[dict[str, str]] = []
    changes: list[dict[str, str]] = []
    normalized: dict[str, Any] = {}

    for name in FEATURE_NAMES:
        if name not in raw:
            issues.append(_issue(name, "missing_field", "Required feature is missing"))
    # API JSON keys are strings. Keep extra-field errors stable for arbitrary Python callers.
    for name in sorted((key for key in raw if key not in FEATURE_NAMES), key=str):
        issues.append(_issue(str(name), "unexpected_field", "Unknown feature is not allowed"))

    for name in FEATURE_NAMES:
        if name not in raw:
            continue
        value = raw[name]
        if name in CATEGORICAL_VALUES:
            if not isinstance(value, str):
                issues.append(_issue(name, "invalid_category", "Expected a known category string"))
                continue
            # A small vocabulary makes matching case-insensitively unambiguous.
            candidate = " ".join(value.split())
            lookup = {allowed.casefold(): allowed for allowed in CATEGORICAL_VALUES[name]}
            canonical = lookup.get(candidate.casefold())
            if canonical is None:
                issues.append(_issue(name, "invalid_category", f"Allowed values: {', '.join(CATEGORICAL_VALUES[name])}"))
                continue
            if value != canonical:
                changes.append({"field": name, "operation": "canonicalized_category"})
            normalized[name] = canonical
            continue

        if name in BINARY_FIELDS:
            if type(value) is int and value in (0, 1):
                normalized[name] = value
            elif isinstance(value, str) and value.strip() in ("0", "1"):
                normalized[name] = int(value.strip())
                changes.append({"field": name, "operation": "parsed_binary_string"})
            else:
                issues.append(_issue(name, "invalid_binary", "Expected integer 0/1 or string '0'/'1'"))
            continue

        # Continuous/positive measurements: no clinical threshold interpretation.
        if isinstance(value, bool):
            issues.append(_issue(name, "invalid_number", "Expected finite JSON number or dot-decimal numeric string"))
            continue
        if isinstance(value, (int, float)):
            try:
                number = float(value)
            except (OverflowError, ValueError):
                issues.append(_issue(name, "invalid_number", "Numeric value is not representable"))
                continue
        elif isinstance(value, str) and _DECIMAL.fullmatch(value.strip()):
            try:
                number = float(value.strip())
            except (OverflowError, ValueError):
                issues.append(_issue(name, "invalid_number", "Numeric value is not representable"))
                continue
            changes.append({"field": name, "operation": "parsed_numeric_string"})
        else:
            issues.append(_issue(name, "invalid_number", "Expected finite JSON number or dot-decimal numeric string; commas are not accepted"))
            continue

        if not math.isfinite(number):
            issues.append(_issue(name, "non_finite", "Numeric value must be finite"))
            continue
        low, high = NUMERIC_BOUNDS[name]
        if not low <= number <= high:
            issues.append(_issue(name, "out_of_range", f"Outside supported engineering input interval [{low}, {high}]"))
            continue
        normalized[name] = number

    if issues:
        raise PatientDataValidationError(issues)

    # Keep a single authoritative feature contract in the Phase 1 code.
    try:
        canonical_features = validate_features(normalized)
    except FeatureValidationError as exc:
        # Defensive fallback: external model schema may change in future phases.
        raise PatientDataValidationError([
            _issue("features", "model_schema_mismatch", "Normalized features do not match current DL schema")
        ]) from exc
    return canonical_features, changes
