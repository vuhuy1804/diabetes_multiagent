"""Phase 6 Explanation Agent: transparent four-section educational report."""
from __future__ import annotations

from typing import Any

from core.contracts import AgentMessage
from explanation.report_builder import ReportInputError, build_report


class ExplanationAgent:
    VERSION = 'explanation-template-v1'

    def run(self, request_id: str, workflow: Any) -> AgentMessage:
        try:
            if not isinstance(workflow, AgentMessage) or request_id != workflow.request_id:
                raise ReportInputError('Request ID or Coordinator result mismatch')
            report = build_report(workflow)
        except (ReportInputError, ValueError, TypeError):
            return AgentMessage(request_id=request_id, agent='explanation', status='error',
                                payload={'error_type': 'invalid_workflow_for_explanation'},
                                evidence=[], version=self.VERSION,
                                error='Completed, consistent Coordinator result is required.')
        return AgentMessage(request_id=request_id, agent='explanation', status='ok',
                            payload={'report': {k: v for k, v in report.items() if k != 'evidence'},
                                     'report_kind': report['report_kind'], 'generation_method': report['generation_method']},
                            evidence=report['evidence'], version=self.VERSION)
