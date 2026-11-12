"""KG/RAG Agent, Phase 2. Uses actual Neo4j-backed retrieval, retains citations."""
from __future__ import annotations

from typing import Any

from core.contracts import AgentMessage
from services.knowledge_service import KnowledgeQueryError, KnowledgeRetrievalService
from services.neo4j_service import KnowledgeDatabaseError


class KGRAGAgent:
    def __init__(self, service: KnowledgeRetrievalService | None = None):
        self.service = service or KnowledgeRetrievalService()

    def run(self, request_id: str, question: Any) -> AgentMessage:
        try:
            result = self.service.query(question)
            # All evidence must be retained from the same retrieval snapshot.
            # The service returns it in the internal evidence field added below.
            records = result.pop('_evidence', [])
            return AgentMessage(request_id=request_id, agent='kg_rag', status='ok',
                                payload=result, evidence=records, version='demo-kg-v1.3-p1')
        except KnowledgeQueryError as exc:
            return AgentMessage(request_id=request_id, agent='kg_rag', status='error',
                                payload={'error_type':'invalid_question'}, version='phase2', error=str(exc))
        except KnowledgeDatabaseError:
            return AgentMessage(request_id=request_id, agent='kg_rag', status='error',
                                payload={'error_type':'neo4j_unavailable'}, version='phase2',
                                error='Neo4j could not be reached or queried. Check configuration and database status.')
