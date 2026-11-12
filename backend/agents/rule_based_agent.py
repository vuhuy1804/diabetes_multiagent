"""Phase 4 Rule-Based Agent, standalone until Phase 5 Coordinator."""
from __future__ import annotations

from typing import Any

from core.contracts import AgentMessage
from rules.rule_engine import RULE_SET_VERSION, RuleInputError, evaluate_rules


class RuleBasedAgent:
    VERSION = RULE_SET_VERSION

    def run(self, request_id: str, features: Any, prediction: Any) -> AgentMessage:
        try:
            output = evaluate_rules(features, prediction)
        except RuleInputError as exc:
            return AgentMessage(
                request_id=request_id, agent='rule_based', status='error',
                payload={'error_type': 'invalid_rule_input'},
                version=self.VERSION, error=str(exc), evidence=[],
            )
        return AgentMessage(
            request_id=request_id, agent='rule_based', status='ok',
            payload={key: value for key, value in output.items() if key != 'evidence'},
            evidence=output['evidence'], version=self.VERSION,
        )
