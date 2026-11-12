"""Phase 3 Patient Data Agent (§3, §5 and §6 of course architecture PDF).

No DB access and no prediction; can be called independently by Coordinator later.
"""
from __future__ import annotations

from typing import Any

from core.contracts import AgentMessage
from core.features import FEATURE_NAMES
from core.patient_data import PatientDataValidationError, normalize_patient_features


class PatientDataAgent:
    VERSION = "patient-data-v1"

    def run(self, request_id: str, features: Any) -> AgentMessage:
        try:
            clean, changes = normalize_patient_features(features)
        except PatientDataValidationError as exc:
            return AgentMessage(
                request_id=request_id,
                agent="patient_data",
                status="error",
                payload={
                    "valid": False,
                    "error_type": "invalid_patient_data",
                    "issues": exc.issues,
                },
                evidence=[],
                version=self.VERSION,
                error="Patient feature validation failed",
            )
        return AgentMessage(
            request_id=request_id,
            agent="patient_data",
            status="ok",
            payload={
                "valid": True,
                "features": clean,
                "feature_order": list(FEATURE_NAMES),
                "normalizations": changes,
            },
            evidence=[],
            version=self.VERSION,
        )
