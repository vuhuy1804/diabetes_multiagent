"""Phase 8 Flask contract tests. No live model or Neo4j is required."""
from __future__ import annotations

import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from app import create_app
from api import routes
from agents.monitoring_agent import MonitoringAgent
from monitoring.audit_repository import AuditRepository
from core.contracts import AgentMessage

FEATURES={'gender':'Female','age':44,'hypertension':0,'heart_disease':0,
          'smoking_history':'never','bmi':27.32,'HbA1c_level':5.7,'blood_glucose_level':140}
PAYLOAD={'features':FEATURES,'question':'Bệnh tiểu đường có mấy loại chính?'}


def result(rid='req-monitor-api',status='ok',error_type=None):
    steps=[{'agent':agent,'status':'ok','duration_ms':1.5,'version':'test-v1'}
           for agent in ['patient_data','dl_prediction','rule_based','kg_rag','explanation']]
    if status=='error':
        steps[0]['status']='error'
        for s in steps[1:]:s['status']='skipped'
    return AgentMessage(rid,'coordinator',status,version='c1',payload={
        'workflow_status':'completed' if status=='ok' else 'failed',
        'steps':steps,'report_ready':status=='ok','question_provided':True,
        'knowledge_status':'ok' if status=='ok' else 'skipped',
        'error_type':error_type,'report':{'text':'Báo cáo tiếng Việt'} if status=='ok' else None,
        'results':{'patient_data':{'features':FEATURES},'dl_prediction':{'prediction':1}},
    })


class MonitoringApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'test.sqlite3'
        self.monitor=MonitoringAgent(AuditRepository(self.path))
        self.client=create_app().test_client()
        self.patch=patch.object(routes,'_monitor_agent',self.monitor)
        self.patch.start();self.addCleanup(self.patch.stop)

    def test_assess_six_stage_success(self):
        with patch.object(routes._coordinator,'run_with_explanation',return_value=result()):
            resp=self.client.post('/api/assess',json=PAYLOAD)
        self.assertEqual(resp.status_code,200)
        body=resp.get_json()
        self.assertEqual(body['payload']['monitoring_status'],'ok')
        self.assertEqual(len(body['payload']['steps']),6)
        self.assertEqual(body['payload']['steps'][-1]['agent'],'monitoring')
        self.assertTrue(body['payload']['audit_recorded'])
        self.assertEqual(self.monitor.repository.summary()['total_runs'],1)

    def test_report_legacy_five_steps_but_is_audited(self):
        with patch.object(routes._coordinator,'run_with_explanation',return_value=result()):
            resp=self.client.post('/api/report/generate',json=PAYLOAD)
        self.assertEqual(resp.status_code,200)
        self.assertEqual(len(resp.get_json()['payload']['steps']),5)
        self.assertTrue(resp.get_json()['payload']['audit_recorded'])
        self.assertEqual(self.monitor.repository.recent()[0]['route_kind'],'report')

    def test_invalid_payload_does_not_trigger_audit(self):
        with patch.object(routes._coordinator,'run_with_explanation') as mock:
            resp=self.client.post('/api/assess',json={**PAYLOAD,'report':{'fake':True}})
        self.assertEqual(resp.status_code,400)
        mock.assert_not_called()
        self.assertEqual(self.monitor.repository.summary()['total_runs'],0)

    def test_invalid_array(self):
        self.assertEqual(self.client.post('/api/assess',json=[]).status_code,400)

    def test_malformed_json(self):
        self.assertEqual(self.client.post('/api/assess',data='broken',content_type='text/plain').status_code,400)

    def test_invalid_data_records_failure_and_returns_400(self):
        with patch.object(routes._coordinator,'run_with_explanation',return_value=result(status='error',error_type='invalid_patient_data')):
            resp=self.client.post('/api/assess',json=PAYLOAD)
        self.assertEqual(resp.status_code,400)
        self.assertEqual(resp.get_json()['payload']['monitoring_status'],'ok')
        self.assertEqual(self.monitor.repository.summary()['failed'],1)

    def test_audit_down_returns_503_not_fake_success(self):
        directory=Path(self.tmp.name)/'is_directory';directory.mkdir()
        broken=MonitoringAgent(AuditRepository(directory))
        with patch.object(routes,'_monitor_agent',broken),patch.object(routes._coordinator,'run_with_explanation',return_value=result()):
            resp=self.client.post('/api/assess',json=PAYLOAD)
        self.assertEqual(resp.status_code,503)
        self.assertEqual(resp.get_json()['payload']['monitoring_status'],'error')
        self.assertFalse(resp.get_json()['payload']['audit_recorded'])

    def test_legacy_report_storage_error_disclosed_without_losing_report(self):
        directory=Path(self.tmp.name)/'is_directory';directory.mkdir()
        broken=MonitoringAgent(AuditRepository(directory))
        with patch.object(routes,'_monitor_agent',broken),patch.object(routes._coordinator,'run_with_explanation',return_value=result()):
            resp=self.client.post('/api/report/generate',json=PAYLOAD)
        self.assertEqual(resp.status_code,200)
        self.assertTrue(resp.get_json()['payload']['report_ready'])
        self.assertEqual(resp.get_json()['payload']['monitoring_status'],'error')
        self.assertFalse(resp.get_json()['payload']['audit_recorded'])

    def test_health_monitoring_ready_and_phase8(self):
        with patch.object(routes._kg_service,'readiness',return_value='ready'),patch.object(routes._dl_service,'readiness',return_value='ready'):
            body=self.client.get('/api/health').get_json()
        self.assertEqual(body['phase'],'8-monitoring-evaluation')
        self.assertEqual(body['integrations']['monitoring'],'ready')

    def test_agent_catalog_monitoring_ready_optional_rl_unimplemented(self):
        agents=self.client.get('/api/agents/status').get_json()['agents']
        states={a['agent']:a['status'] for a in agents}
        self.assertEqual(states['monitoring'],'ready')
        self.assertEqual(states['rl'],'not_implemented')

    def test_audit_never_stores_personal_values(self):
        with patch.object(routes._coordinator,'run_with_explanation',return_value=result()):
            self.client.post('/api/assess',json=PAYLOAD)
        with closing(sqlite3.connect(self.path)) as db:
            dump='\n'.join(str(r) for t in ('audit_runs','audit_steps')
                           for r in db.execute('SELECT * FROM '+t))
        self.assertNotIn('27.32',dump)
        self.assertNotIn('Bệnh tiểu đường có mấy loại chính?',dump)
        self.assertNotIn('Báo cáo tiếng Việt',dump)

    def test_windows_powershell_51_compatible_json(self):
        with patch.object(routes._coordinator,'run_with_explanation',return_value=result()):
            resp=self.client.post('/api/assess',json=PAYLOAD)
        resp.data.decode('ascii')
        self.assertIn('Báo cáo tiếng Việt',resp.get_json()['payload']['report']['text'])


if __name__ == '__main__':unittest.main()
