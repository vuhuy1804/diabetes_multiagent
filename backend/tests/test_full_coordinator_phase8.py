"""Full 6-Agent orchestration preserves ordering and failure awareness."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from coordinator.coordinator_agent import CoordinatorAgent
from core.contracts import AgentMessage


def completed():
    return AgentMessage('req-p8','coordinator','ok',version='coordinator-v1',payload={
        'workflow_status':'completed','report_ready':True,
        'report':{'text':'Báo cáo tiếng Việt'},'error_type':None,
        'steps':[{'agent': a, 'status':'ok','version':'v1','duration_ms':1.0}
                 for a in ('patient_data','dl_prediction','rule_based','kg_rag','explanation')],
    })


class FullCoordinatorPhase8Tests(unittest.TestCase):
    def setUp(self):
        self.coord=CoordinatorAgent(None,None,None,None,explanation_agent=None)
        self.data={'features':{'dummy':'private'},'question':'PRIVATE QUESTION',
                   'question_provided':True}

    def test_monitor_runs_after_explanation_and_append_sixth_step(self):
        monitor=MagicMock()
        monitor.run.return_value=AgentMessage('req-p8','monitoring','ok',version='monitoring-sqlite-v1',payload={'audit_written':True})
        with patch.object(self.coord,'run_with_explanation',return_value=completed()):
            output=self.coord.run_full_with_monitoring(**self.data, monitoring_agent=monitor)
        self.assertEqual(output.status,'ok')
        self.assertEqual(len(output.payload['steps']),6)
        self.assertEqual(output.payload['steps'][-1]['agent'],'monitoring')
        self.assertTrue(output.payload['audit_recorded'])
        monitor.run.assert_called_once()
        self.assertEqual(monitor.run.call_args.kwargs['request_id'],'req-p8')
        self.assertNotIn('PRIVATE QUESTION',str(monitor.run.call_args.kwargs['workflow'].payload))

    def test_monitor_storage_error_is_not_disguised(self):
        monitor=MagicMock()
        monitor.run.return_value=AgentMessage('req-p8','monitoring','error',payload={'error_type':'audit_storage_unavailable'})
        with patch.object(self.coord,'run_with_explanation',return_value=completed()):
            output=self.coord.run_full_with_monitoring(**self.data,monitoring_agent=monitor)
        self.assertEqual(output.status,'error')
        self.assertEqual(output.payload['monitoring_status'],'error')
        self.assertEqual(output.payload['workflow_status'],'partial')
        self.assertEqual(output.payload['error_type'],'audit_storage_unavailable')
        self.assertIsNotNone(output.payload['report'])

    def test_monitor_exec_exception_fail_closed(self):
        monitor=MagicMock()
        monitor.run.side_effect=RuntimeError('PRIVATE SQL CONNECTION STRING')
        with patch.object(self.coord,'run_with_explanation',return_value=completed()):
            output=self.coord.run_full_with_monitoring(**self.data,monitoring_agent=monitor)
        self.assertEqual(output.status,'error')
        self.assertNotIn('PRIVATE SQL CONNECTION STRING',str(output.to_dict()))


if __name__=='__main__':unittest.main()
