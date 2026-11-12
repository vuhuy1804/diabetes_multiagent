"""Neo4j repository, Phase 2. NO fabricated graph results or clinical decisions.

Connections are lazy; .env is read on instantiation, not written to logs.
Neo4j AuraDB and local Neo4j use the same official Python driver.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


class KnowledgeDatabaseError(RuntimeError):
    """Neo4j is absent, unreachable, empty, or returned an invalid result."""


TOPICS_CYPHER = """
MATCH (t:Topic)
RETURN t.id AS id, t.name AS name, t.aliases AS aliases, t.category AS category, coalesce(t.priority, 0) AS priority
ORDER BY t.id
"""

EVIDENCE_CYPHER = """
MATCH (t:Topic)-[:HAS_FACT]->(f:Fact)-[:SUPPORTED_BY]->(s:Source)
WHERE t.id IN $topic_ids
RETURN t.id AS topic_id, t.name AS topic_name,
       f.id AS fact_id, f.text AS text,
       s.id AS source_id, s.title AS source_title,
       s.publisher AS publisher, s.url AS source_url
ORDER BY t.id, f.id
LIMIT $limit
"""

COUNTS_CYPHER = """
MATCH (t:Topic)
WITH count(t) AS topics
MATCH (f:Fact)
WITH topics, count(f) AS facts
MATCH (s:Source)
RETURN topics, facts, count(s) AS sources
"""


class Neo4jKnowledgeRepository:
    def __init__(self, env_path: Path | None = None):
        load_dotenv(env_path if env_path is not None else ROOT / '.env', override=False)
        self.uri = os.getenv('NEO4J_URI', '').strip()
        self.user = os.getenv('NEO4J_USER', os.getenv('NEO4J_USERNAME', 'neo4j')).strip()
        self.password = os.getenv('NEO4J_PASSWORD', '')
        self.database = os.getenv('NEO4J_DATABASE', 'neo4j').strip() or 'neo4j'
        self._driver = None

    def _get_driver(self):
        if not self.uri or not self.password or not self.user:
            raise KnowledgeDatabaseError('Missing Neo4j settings. Configure NEO4J_URI/USER/PASSWORD in .env.')
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(
                    self.uri, auth=(self.user, self.password),
                    connection_timeout=5.0,
                    connection_acquisition_timeout=5.0,
                )
            except Exception as exc:
                raise KnowledgeDatabaseError('Neo4j driver setup failed') from exc
        return self._driver

    def close(self):
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def verify_connectivity(self) -> None:
        try:
            self._get_driver().verify_connectivity()
        except KnowledgeDatabaseError:
            raise
        except Exception as exc:
            raise KnowledgeDatabaseError('Neo4j connectivity verification failed') from exc

    def _read(self, query: str, params: dict[str, Any] | None = None) -> list[dict]:
        try:
            from neo4j import READ_ACCESS
            with self._get_driver().session(database=self.database, default_access_mode=READ_ACCESS) as session:
                return [record.data() for record in session.run(query, **(params or {}))]
        except KnowledgeDatabaseError:
            raise
        except Exception as exc:
            raise KnowledgeDatabaseError('Neo4j read query failed') from exc

    def counts(self) -> dict[str, int]:
        rows = self._read(COUNTS_CYPHER)
        if not rows:
            return {'topics': 0, 'facts': 0, 'sources': 0}
        return {k: int(rows[0].get(k, 0)) for k in ('topics', 'facts', 'sources')}

    def readiness(self) -> str:
        if not self.uri or not self.password:
            return 'not_configured'
        try:
            self.verify_connectivity()
            counts = self.counts()
            if min(counts.values()) <= 0:
                return 'empty_knowledge_graph'
            return 'ready'
        except KnowledgeDatabaseError:
            return 'unavailable'

    def list_topics(self) -> list[dict]:
        return self._read(TOPICS_CYPHER)

    def evidence_for_topics(self, topic_ids: list[str], limit: int = 8) -> list[dict]:
        if not topic_ids:
            return []
        # Retrieve candidates PER topic, then rank by relevance in the service.
        # A large first topic must not hide facts from the second topic behind
        # a global Cypher LIMIT. The database is still read-only and parameterized.
        per_topic_limit = max(1, min(int(limit), 48))
        rows: list[dict] = []
        for topic_id in list(dict.fromkeys(topic_ids[:2])):
            rows.extend(self._read(EVIDENCE_CYPHER, {
                'topic_ids': [topic_id], 'limit': per_topic_limit,
            }))
        return rows
