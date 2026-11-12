"""Monitoring Agent: persist strictly scoped execution metadata (Phase 8)."""
from __future__ import annotations

from core.contracts import AgentMessage
from monitoring.audit_repository import AuditError, AuditRepository


class MonitoringAgent:
    VERSION = 'monitoring-sqlite-v1'

    def __init__(self, repository: AuditRepository | None = None):
        self.repository = repository if repository is not None else AuditRepository()

    def run(self, *, request_id: str, workflow: AgentMessage, route_kind: str = 'assess') -> AgentMessage:
        if (not isinstance(workflow, AgentMessage) or workflow.request_id != request_id
            or workflow.agent != 'coordinator' or workflow.status not in ('ok', 'error')):
            return AgentMessage(request_id, 'monitoring', 'error',
                                payload={'error_type': 'invalid_workflow_metadata'},
                                version=self.VERSION, error='Invalid Coordinator metadata')
        try:
            stored = self.repository.record(request_id, workflow.status, workflow.payload,
                                            route_kind=route_kind, coordinator_version=workflow.version)
        except AuditError:
            return AgentMessage(request_id, 'monitoring', 'error',
                                payload={'error_type': 'audit_storage_unavailable', 'audit_written': False},
                                version=self.VERSION, error='Unable to store audit metadata')
        return AgentMessage(request_id, 'monitoring', 'ok',
                            payload=stored, version=self.VERSION)

    def readiness(self) -> str:
        try:
            db = self.repository._connect()
            db.close()
            return 'ready'
        except AuditError:
            return 'unavailable'
