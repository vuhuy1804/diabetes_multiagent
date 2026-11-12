"""Phase 3 Patient Data Agent unit tests: no Flask, model, or Neo4j required."""
from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from agents.patient_data_agent import PatientDataAgent  # noqa: E402
from core.features import FEATURE_NAMES, validate_features  # noqa: E402
from core.patient_data import PatientDataValidationError, normalize_patient_features  # noqa: E402

VALID = {
    "gender": "Female", "age": 44, "hypertension": 0,
    "heart_disease": 0, "smoking_history": "never", "bmi": 27.32,
    "HbA1c_level": 5.7, "blood_glucose_level": 140,
}


class PatientDataUnitTests(unittest.TestCase):
    def assert_has_code(self, raw, code, field):
        with self.assertRaises(PatientDataValidationError) as caught:
            normalize_patient_features(raw)
        self.assertIn((field, code), [(e["field"], e["code"]) for e in caught.exception.issues])

    def test_valid_preserves_column_order(self):
        clean, changes = normalize_patient_features(VALID)
        self.assertEqual(tuple(clean), FEATURE_NAMES)
        self.assertEqual(changes, [])
        self.assertEqual(clean, validate_features(VALID))

    def test_normalize_categorical_spaces_and_case(self):
        clean, changes = normalize_patient_features({**VALID, "gender": " female ", "smoking_history": " No    Info "})
        self.assertEqual(clean["gender"], "Female")
        self.assertEqual(clean["smoking_history"], "No Info")
        self.assertEqual({c["field"] for c in changes}, {"gender", "smoking_history"})

    def test_normalize_known_other_category(self):
        clean, _ = normalize_patient_features({**VALID, "gender": " OTHER "})
        self.assertEqual(clean["gender"], "Other")

    def test_parse_unambiguous_numeric_strings(self):
        raw = {**VALID, "age": "44", "bmi": " 27.32 ", "HbA1c_level": "5.7", "blood_glucose_level": "140"}
        clean, changes = normalize_patient_features(raw)
        for field in ("age", "bmi", "HbA1c_level", "blood_glucose_level"):
            self.assertIsInstance(clean[field], float)
        self.assertEqual(len(changes), 4)
        self.assertEqual(clean["age"], 44.0)

    def test_binary_strings_only_zero_one(self):
        clean, changes = normalize_patient_features({**VALID, "hypertension": " 1 ", "heart_disease": "0"})
        self.assertEqual((clean["hypertension"], clean["heart_disease"]), (1, 0))
        self.assertEqual(len(changes), 2)

    def test_bool_is_never_silently_accepted(self):
        self.assert_has_code({**VALID, "hypertension": True}, "invalid_binary", "hypertension")
        self.assert_has_code({**VALID, "age": False}, "invalid_number", "age")

    def test_missing_and_extra_fields_reported_together(self):
        raw = {k: v for k, v in VALID.items() if k != "age"}
        raw["extra_health_field"] = "PRIVATE TEST SENTINEL"
        with self.assertRaises(PatientDataValidationError) as caught:
            normalize_patient_features(raw)
        self.assertEqual({e["code"] for e in caught.exception.issues}, {"missing_field", "unexpected_field"})
        self.assertNotIn("PRIVATE TEST SENTINEL", str(caught.exception.issues))

    def test_null_and_nonobject(self):
        self.assert_has_code({**VALID, "bmi": None}, "invalid_number", "bmi")
        self.assert_has_code(None, "not_object", "features")
        self.assert_has_code([], "not_object", "features")

    def test_comma_decimal_rejected(self):
        self.assert_has_code({**VALID, "bmi": "27,32"}, "invalid_number", "bmi")

    def test_nonfinite_values_rejected(self):
        for v in (math.nan, math.inf, -math.inf, "NaN", "Infinity", "1e9999"):
            with self.subTest(v=v):
                self.assert_has_code({**VALID, "bmi": v}, "non_finite" if type(v) is float else "invalid_number", "bmi")

    def test_outside_engineering_bounds_rejected(self):
        self.assert_has_code({**VALID, "age": -1}, "out_of_range", "age")
        self.assert_has_code({**VALID, "bmi": "151"}, "out_of_range", "bmi")

    def test_invalid_category_and_binary(self):
        self.assert_has_code({**VALID, "gender": "Femal"}, "invalid_category", "gender")
        self.assert_has_code({**VALID, "heart_disease": 1.0}, "invalid_binary", "heart_disease")

    def test_multiple_errors_not_short_circuited(self):
        raw = {**VALID, "gender": None, "bmi": -20, "age": "abc"}
        with self.assertRaises(PatientDataValidationError) as caught:
            normalize_patient_features(raw)
        self.assertEqual(len(caught.exception.issues), 3)

    def test_original_input_unmodified(self):
        raw = {**VALID, "gender": " male ", "age": "44"}
        saved = copy.deepcopy(raw)
        normalize_patient_features(raw)
        self.assertEqual(raw, saved)

    def test_agent_success_contract(self):
        msg = PatientDataAgent().run("req_unit", VALID)
        self.assertEqual((msg.request_id, msg.agent, msg.status), ("req_unit", "patient_data", "ok"))
        self.assertTrue(msg.payload["valid"])
        self.assertEqual(msg.payload["feature_order"], list(FEATURE_NAMES))
        self.assertEqual(msg.evidence, [])
        self.assertEqual(msg.version, "patient-data-v1")

    def test_agent_error_contract_privacy(self):
        msg = PatientDataAgent().run("req_error", {**VALID, "bmi": "PRIVATE TEST SENTINEL"})
        self.assertEqual(msg.status, "error")
        self.assertEqual(msg.payload["error_type"], "invalid_patient_data")
        self.assertFalse(msg.payload["valid"])
        self.assertNotIn("features", msg.payload)
        self.assertNotIn("PRIVATE TEST SENTINEL", str(msg.to_dict()))


if __name__ == "__main__":
    unittest.main()
