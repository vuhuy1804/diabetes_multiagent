"""Phase 8 offline functional evaluation tests (no live database or model)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from core.contracts import AgentMessage
from evaluation.evaluator import EvaluationError, load_cases, evaluate_cases


class EvaluationTests(unittest.TestCase):
    def test_load_fixture_five_cases(self):
        cases=load_cases(BACKEND.parent/'data/samples/evaluation_phase8_cases.json')
        self.assertEqual(len(cases),5)
        self.assertEqual(len({c['case_id'] for c in cases}),5)

    def test_all_expectations_mocked(self):
        cases = [
            {'case_id':'good', 'request':{'features':{'secret':'PRIVATE VALUE'}},'expect':{'status':'ok','report_ready':True}},
            {'case_id':'bad', 'request':{'features':{}},'expect':{'status':'error','error_type':'invalid_patient_data'}}
        ]
        def run(req):
            success=bool(req['features'])
            return AgentMessage('x','coordinator','ok' if success else 'error',payload={
                'report_ready':success, 'error_type':None if success else 'invalid_patient_data',
                'steps':[{'agent':'patient_data','status':'ok' if success else 'error'}]})
        metrics=evaluate_cases(cases,run)
        self.assertEqual(metrics['total_cases'],2)
        self.assertEqual(metrics['passed'],2)
        self.assertEqual(metrics['pass_rate'],1.0)
        self.assertNotIn('PRIVATE VALUE', json.dumps(metrics))

    def test_detect_failing_expectation(self):
        cases=[{'case_id':'bad','request':{},'expect':{'status':'ok'}}]
        metrics=evaluate_cases(cases,lambda _:AgentMessage('x','coordinator','error'))
        self.assertEqual(metrics['failed'],1)
        self.assertFalse(metrics['cases'][0]['passed'])

    def test_runner_exception_does_not_expose_raw_message(self):
        cases=[{'case_id':'error','request':{},'expect':{'status':'error','error_type':'evaluation_runner_error'}}]
        def run(_):raise ValueError('PRIVATE RECORD')
        metrics=evaluate_cases(cases,run)
        self.assertEqual(metrics['passed'],1)
        self.assertNotIn('PRIVATE RECORD',str(metrics))

    def test_bad_runner_result_fails(self):
        cases=[{'case_id':'error','request':{},'expect':{'status':'error','error_type':'evaluation_runner_error'}}]
        self.assertEqual(evaluate_cases(cases, lambda _:None)['passed'],1)

    def test_load_reject_duplicate_id(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'scenarios.json';p.write_text(json.dumps([
                {'case_id':'dup','request':{},'expect':{'status':'ok'}},
                {'case_id':'dup','request':{},'expect':{'status':'ok'}}]),encoding='utf-8')
            with self.assertRaises(EvaluationError):load_cases(p)

    def test_load_reject_extra_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'scenarios.json';p.write_text(json.dumps([
                {'case_id':'x','request':{'features':{},'prediction':{'secret':'z'}},'expect':{'status':'ok'}}]),encoding='utf-8')
            with self.assertRaises(EvaluationError):load_cases(p)

    def test_empty_cases_raise(self):
        with self.assertRaises(EvaluationError):evaluate_cases([],lambda x:None)

    def test_evaluation_kind_not_accuracy(self):
        result=evaluate_cases([{'case_id':'ok','request':{},'expect':{'status':'ok'}}],
            lambda _:AgentMessage('x','coordinator','ok'))
        self.assertNotIn('clinical_accuracy',result)
        self.assertIn('not_clinical_accuracy',result['evaluation_kind'])


if __name__=='__main__':unittest.main()
