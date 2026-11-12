"""Phase 8 pure-python tests: actual SQLite transaction, metadata isolation."""
from __future__ import annotations

import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from core.contracts import AgentMessage
from agents.monitoring_agent import MonitoringAgent
from monitoring.audit_repository import AuditError, AuditRepository


def workflow(status='ok', rid='req-test-1'):
    steps = [
        {'agent': 'patient_data', 'status':'ok', 'version':'p1','duration_ms':1.0},
        {'agent': 'dl_prediction', 'status':'ok','version':'model-v1','duration_ms':12.5},
        {'agent': 'rule_based', 'status':'ok','version':'r1','duration_ms':1.5},
        {'agent': 'kg_rag', 'status':'skipped','version':'k1','duration_ms':0.0},
        {'agent': 'explanation', 'status':'ok','version':'e1','duration_ms':2.0},
    ]
    return AgentMessage(rid,'coordinator',status,version='c1',payload={
        'workflow_status':'completed' if status == 'ok' else 'failed',
        'steps':steps,'report_ready':status == 'ok',
        'question_provided':False, 'error_type':None,
        'results': {'patient_data': {'features': {'bmi': 27.32}}},
        'report': {'text': 'PRIVATE REPORT: 12345'},
        'question': 'PRIVATE QUESTION', 'patient_name':'PRIVATE PERSON',
    },evidence=[{'excerpt': 'PRIVATE EXCERPT'}])


class AuditRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dbpath = Path(self.tmp.name) / 'audit.sqlite3'
        self.repo = AuditRepository(self.dbpath)
        self.agent = MonitoringAgent(self.repo)

    def test_writes_and_reads_5_stage_metadata(self):
        result = self.agent.run(request_id='req-test-1', workflow=workflow())
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.payload['recorded_steps'], 5)
        self.assertEqual(self.repo.summary()['completed'], 1)
        self.assertEqual(self.repo.summary()['reports_ready'], 1)

    def test_audit_sqlite_does_not_contain_patient_info_or_reports(self):
        self.agent.run(request_id='req-test-1', workflow=workflow())
        dump = '\n'.join(self._dbdump())
        for secret in ('27.32','PRIVATE REPORT','PRIVATE QUESTION','PRIVATE EXCERPT','PRIVATE PERSON'):
            self.assertNotIn(secret,dump)
        self.assertIn('model-v1', dump)

    def _dbdump(self):
        with closing(sqlite3.connect(self.dbpath)) as db:
            for table in ('audit_runs','audit_steps'):
                for row in db.execute('SELECT * FROM '+table):
                    yield repr(row)

    def test_stages_are_atomic_if_request_id_duplicate(self):
        self.agent.run(request_id='req-test-1',workflow=workflow())
        second = self.agent.run(request_id='req-test-1',workflow=workflow())
        self.assertEqual(second.status, 'error')
        self.assertEqual(self.repo.summary()['total_runs'],1)
        with closing(sqlite3.connect(self.dbpath)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM audit_steps').fetchone()[0],5)

    def test_error_workflow_can_be_recorded(self):
        w=workflow('error'); w.payload['steps'][0]['status']='error'
        self.assertEqual(self.agent.run(request_id=w.request_id,workflow=w).status,'ok')
        self.assertEqual(self.repo.summary()['failed'],1)

    def test_reject_request_id_injected_values(self):
        w=workflow(rid='PRIVATE PERSON')
        result=self.agent.run(request_id=w.request_id,workflow=w)
        self.assertEqual(result.status,'error')
        self.assertFalse(self.dbpath.exists() and self.repo.summary()['total_runs'])

    def test_reject_unexpected_agent(self):
        w=workflow();w.payload['steps'][0]['agent']='PRIVATE PERSON'
        self.assertEqual(self.agent.run(request_id=w.request_id,workflow=w).status,'error')

    def test_reject_unexpected_status(self):
        w=workflow();w.payload['steps'][0]['status']='PRIVATE TEXT'
        self.assertEqual(self.agent.run(request_id=w.request_id,workflow=w).status,'error')

    def test_metadata_string_version_is_whitelisted(self):
        w=workflow();w.payload['steps'][0]['version']='PATIENT SECRET'
        self.assertEqual(self.agent.run(request_id=w.request_id,workflow=w).status,'ok')
        self.assertNotIn('PATIENT SECRET','\n'.join(self._dbdump()))

    def test_duration_is_clamped_and_nonfinite_zero(self):
        w=workflow();w.payload['steps'][0]['duration_ms']=float('inf')
        self.assertEqual(self.agent.run(request_id=w.request_id,workflow=w).status,'ok')
        self.assertEqual(self.repo.summary()['agents']['patient_data']['avg_duration_ms'],0.0)

    def test_summary_empty(self):
        self.assertEqual(self.repo.summary()['total_runs'],0)
        self.assertEqual(self.repo.summary()['agents'],{})

    def test_recent_only_metadata(self):
        self.agent.run(request_id='req-test-1',workflow=workflow())
        record=self.repo.recent(1)[0]
        self.assertEqual(record['request_id'],'req-test-1')
        self.assertNotIn('features',record)
        self.assertNotIn('question',record)

    def test_recent_invalid_limit(self):
        with self.assertRaises(AuditError):self.repo.recent(101)

    def test_invalid_retention_no_deletion(self):
        self.agent.run(request_id='req-test-1',workflow=workflow())
        with self.assertRaises(AuditError):self.repo.purge_older_than(0)
        self.assertEqual(self.repo.summary()['total_runs'],1)

    def test_purge_older_than(self):
        self.agent.run(request_id='req-test-1',workflow=workflow())
        with closing(sqlite3.connect(self.dbpath)) as db:
            with db:  # commit transaction explicitly before closing the connection
                db.execute("UPDATE audit_runs SET created_at_utc = '2020-01-01T00:00:00+00:00'")
        self.assertEqual(self.repo.purge_older_than(30),1)
        self.assertEqual(self.repo.summary()['total_runs'],0)

    def test_database_unavailable_errors_cleanly(self):
        self.dbpath.mkdir()
        self.assertEqual(self.agent.readiness(),'unavailable')
        self.assertEqual(self.agent.run(request_id='req-test-1',workflow=workflow()).status,'error')

    def test_mismatch_agent_request_id_rejected(self):
        self.assertEqual(self.agent.run(request_id='something-else', workflow=workflow()).status,'error')

    def test_readiness_ready_creates_db_without_patient_data(self):
        self.assertEqual(self.agent.readiness(),'ready')
        self.assertTrue(self.dbpath.exists())

    def test_4_steps_only_are_accepted_for_workflow(self):
        w=workflow();w.payload['steps'].pop()
        self.assertEqual(self.agent.run(request_id=w.request_id,workflow=w).status,'ok')


if __name__=='__main__':unittest.main()
