"""Import DB_diabet.cypher / inspect Neo4j / query grounded evidence.

Run from project root:
  python backend/scripts/neo4j_cli.py check
  python backend/scripts/neo4j_cli.py seed
  python backend/scripts/neo4j_cli.py query "Tiểu đường có mấy loại?"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from agents.kg_rag_agent import KGRAGAgent  # noqa: E402
from services.knowledge_service import KnowledgeRetrievalService  # noqa: E402
from services.neo4j_service import KnowledgeDatabaseError, Neo4jKnowledgeRepository, ROOT  # noqa: E402

SEED_PATH = ROOT / 'data/knowledge/DB_diabet.cypher'


def statements(raw: str) -> list[str]:
    """Parse only our generated one-statement-per-line demo script.

    Reject multiline/complex statements instead of pretending to implement Cypher parser.
    """
    queries = []
    for lineno, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        if not line.endswith(';'):
            raise ValueError(f'Invalid statement on line {lineno} (missing final ;)')
        # Semicolons inside Cypher single-quoted strings are data, not query delimiters.
        # Do not accept multiple Cypher statements on one line.
        in_string = False
        escaped = False
        separators = []
        for pos, char in enumerate(line):
            if escaped:
                escaped = False
                continue
            if char == "\\" and in_string:
                escaped = True
                continue
            if char == "'":
                in_string = not in_string
                continue
            if char == ';' and not in_string:
                separators.append(pos)
        if in_string or escaped or separators != [len(line)-1]:
            raise ValueError(f'Invalid statement on line {lineno} (multiple statements or unterminated string)')
        query = line[:-1].strip()
        if not (query.startswith('MERGE ') or query.startswith('MATCH ') or query.startswith('CREATE CONSTRAINT ')):
            raise ValueError(f'Not an allowed demo seed statement on line {lineno}')
        queries.append(query)
    if not queries:
        raise ValueError('Empty DB_diabet.cypher script')
    return queries


def seed(repo: Neo4jKnowledgeRepository) -> dict:
    queries = statements(SEED_PATH.read_text(encoding='utf-8'))
    # Restrict seed to the chosen Neo4j database; MERGE makes this idempotent.
    try:
        driver = repo._get_driver()
        with driver.session(database=repo.database) as session:
            for query in queries:
                session.run(query).consume()   # Consume to expose all Neo4j errors immediately.
        return repo.counts()
    except KnowledgeDatabaseError:
        raise
    except Exception as exc:
        raise KnowledgeDatabaseError('Failed importing DB_diabet.cypher into Neo4j') from exc


def main() -> int:
    p = argparse.ArgumentParser(description='Phase 2 Neo4j demo KG CLI')
    p.add_argument('command', choices=['check','seed','query'])
    p.add_argument('question', nargs='?')
    args = p.parse_args()
    repo = Neo4jKnowledgeRepository()
    try:
        if args.command == 'check':
            state = repo.readiness()
            print(json.dumps({'readiness': state, 'counts': repo.counts() if state == 'ready' else None}, ensure_ascii=False, indent=2))
            return 0 if state == 'ready' else 2
        if args.command == 'seed':
            repo.verify_connectivity()
            counts = seed(repo)
            print(json.dumps({'seed': 'ok', 'counts': counts, 'readiness': repo.readiness()}, ensure_ascii=False, indent=2))
            return 0
        if not args.question:
            p.error('query needs question, for example: query "Tiểu đường có mấy loại?"')
        message = KGRAGAgent(KnowledgeRetrievalService(repo)).run('req_phase2_cli', args.question)
        print(json.dumps(message.to_dict(), ensure_ascii=False, indent=2))
        return 0 if message.status == 'ok' else 2
    except KnowledgeDatabaseError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    finally:
        repo.close()


if __name__ == '__main__':
    raise SystemExit(main())
