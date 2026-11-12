"""SQLite audit of *metadata only* for the classroom MAS.

No patient features, prompts, evidence excerpts, report text, or raw exception
messages are stored. Use a private local directory; do not publish the .sqlite3.
"""
from __future__ import annotations

import math
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALID_AGENT = {'patient_data', 'dl_prediction', 'rule_based', 'kg_rag', 'explanation'}
VALID_STATUS = {'ok', 'error', 'skipped'}
VALID_WORKFLOW = {'completed', 'partial', 'failed'}
VALID_ROUTE = {'report', 'assess'}
_SAFE_TEXT = re.compile(r'^[a-zA-Z0-9_.:-]{1,80}$')


class AuditError(Exception):
    """Failure safe to expose as a generic audit error (never raw SQL message)."""


def _safe_token(value: Any, default: str = 'unknown') -> str:
    """Whitelist machine tokens, do not accidentally persist user text."""
    return value if isinstance(value, str) and _SAFE_TEXT.fullmatch(value) else default


def _safe_duration(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return 0.0
    return round(min(max(float(value), 0.0), 3_600_000.0), 3) if math.isfinite(value) else 0.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class AuditRepository:
    def __init__(self, path: str | Path | None = None):
        value = path if path is not None else os.getenv('AUDIT_DB_PATH', 'outputs/audit.sqlite3')
        self.path = Path(value)
        if not self.path.is_absolute():
            self.path = PROJECT_ROOT / self.path

    def _connect(self) -> sqlite3.Connection:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, timeout=3.0)
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=3000')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS audit_runs (
                    request_id TEXT PRIMARY KEY,
                    created_at_utc TEXT NOT NULL,
                    route_kind TEXT NOT NULL,
                    result_status TEXT NOT NULL,
                    workflow_status TEXT NOT NULL,
                    report_ready INTEGER NOT NULL,
                    question_provided INTEGER NOT NULL,
                    coordinator_version TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    total_agent_duration_ms REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_steps (
                    request_id TEXT NOT NULL REFERENCES audit_runs(request_id) ON DELETE CASCADE,
                    stage_index INTEGER NOT NULL,
                    agent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    error_type TEXT NOT NULL,
                    PRIMARY KEY(request_id, stage_index)
                );
                CREATE INDEX IF NOT EXISTS idx_audit_runs_utc ON audit_runs(created_at_utc);
            ''')
            db.row_factory = sqlite3.Row
            return db
        except (sqlite3.Error, OSError) as exc:
            raise AuditError('Could not initialize audit database') from exc

    def record(self, request_id: str, result_status: str, payload: dict, *,
               route_kind: str, coordinator_version: str) -> dict:
        if (not isinstance(request_id, str) or not _SAFE_TEXT.fullmatch(request_id)
            or result_status not in ('ok', 'error')
            or route_kind not in VALID_ROUTE or not isinstance(payload, dict)
            or payload.get('workflow_status') not in VALID_WORKFLOW):
            raise AuditError('Invalid workflow metadata contract')
        steps = payload.get('steps')
        if not isinstance(steps, list) or not 4 <= len(steps) <= 5:
            raise AuditError('Invalid step trace')
        clean = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict) or step.get('agent') not in VALID_AGENT or step.get('status') not in VALID_STATUS:
                raise AuditError('Invalid step metadata')
            clean.append((request_id, i, step['agent'], step['status'],
                          _safe_token(step.get('version')), _safe_duration(step.get('duration_ms')),
                          _safe_token(step.get('error_type'), 'none')))
        total = round(sum(step[5] for step in clean), 3)
        row = (request_id, _utc_now(), route_kind, result_status,
               payload['workflow_status'], int(payload.get('report_ready') is True),
               int(payload.get('question_provided') is True), _safe_token(coordinator_version),
               _safe_token(payload.get('error_type'), 'none'), total)
        db = self._connect()
        try:
            with db:
                db.execute('''INSERT INTO audit_runs
                    (request_id,created_at_utc,route_kind,result_status,workflow_status,
                     report_ready,question_provided,coordinator_version,error_type,total_agent_duration_ms)
                     VALUES (?,?,?,?,?,?,?,?,?,?)''', row)
                db.executemany('''INSERT INTO audit_steps
                    (request_id,stage_index,agent,status,version,duration_ms,error_type)
                    VALUES (?,?,?,?,?,?,?)''', clean)
        except sqlite3.Error as exc:
            raise AuditError('Audit write failed') from exc
        finally:
            db.close()
        return {'request_id': request_id, 'recorded_steps': len(clean), 'audit_written': True}

    def summary(self) -> dict:
        db = self._connect()
        try:
            rows = db.execute('''SELECT result_status,workflow_status,report_ready,total_agent_duration_ms
                                  FROM audit_runs''').fetchall()
            steps = db.execute('''SELECT agent,status,duration_ms FROM audit_steps''').fetchall()
            per = {}
            for s in steps:
                item = per.setdefault(s['agent'], {'total': 0, 'ok': 0, 'error': 0, 'skipped': 0, 'total_duration_ms': 0.0})
                item['total'] += 1
                item[s['status']] += 1
                item['total_duration_ms'] += s['duration_ms']
            for v in per.values():
                v['avg_duration_ms'] = round(v.pop('total_duration_ms') / v['total'], 3)
            return {
                'total_runs': len(rows),
                'completed': sum(row['workflow_status'] == 'completed' for row in rows),
                'partial': sum(row['workflow_status'] == 'partial' for row in rows),
                'failed': sum(row['workflow_status'] == 'failed' for row in rows),
                'reports_ready': sum(row['report_ready'] for row in rows),
                'avg_agent_duration_ms': round(sum(row['total_agent_duration_ms'] for row in rows) / len(rows), 3) if rows else 0.0,
                'agents': per,
                'contains_patient_data': False,
            }
        except sqlite3.Error as exc:
            raise AuditError('Audit summary failed') from exc
        finally:
            db.close()

    def recent(self, limit: int = 10) -> list[dict]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise AuditError('Invalid limit')
        db = self._connect()
        try:
            rows = db.execute('''SELECT request_id,created_at_utc,route_kind,result_status,workflow_status,
                                      report_ready,coordinator_version,error_type,total_agent_duration_ms
                                 FROM audit_runs ORDER BY created_at_utc DESC,request_id DESC LIMIT ?''', (limit,)).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            raise AuditError('Audit read failed') from exc
        finally:
            db.close()

    def purge_older_than(self, days: int) -> int:
        if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 3650:
            raise AuditError('Retention days must be between 1 and 3650')
        threshold = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec='milliseconds')
        db = self._connect()
        try:
            with db:
                cursor = db.execute('DELETE FROM audit_runs WHERE created_at_utc < ?', (threshold,))
            return cursor.rowcount
        except sqlite3.Error as exc:
            raise AuditError('Audit retention cleanup failed') from exc
        finally:
            db.close()
