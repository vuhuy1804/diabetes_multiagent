"""Phase 1 standalone DL Agent following PDF §3 and §6 message contract."""
from __future__ import annotations

from typing import Any

from core.contracts import AgentMessage
from core.features import FeatureValidationError
from services.dl_service import DLPredictionService, ModelUnavailableError


class DLPredictionAgent:
    def __init__(self, service: DLPredictionService | None = None):
        self.service = service or DLPredictionService()

    def run(self, request_id: str, features: Any) -> AgentMessage:
        try:
            output = self.service.predict(features)
            return AgentMessage(
                request_id=request_id,
                agent="dl_prediction",
                status="ok",
                payload=output,
                evidence=[],  # Evidence belongs to later KG/RAG stage.
                version=output["model_version"],
            )
        except FeatureValidationError as exc:
            return AgentMessage(
                request_id=request_id, agent="dl_prediction", status="error",
                payload={"error_type": "invalid_features"},
                version="phase1", error=str(exc),
            )
        except ModelUnavailableError as exc:
            return AgentMessage(
                request_id=request_id, agent="dl_prediction", status="error",
                payload={"error_type": "model_unavailable"},
                version="phase1", error=str(exc),
            )
