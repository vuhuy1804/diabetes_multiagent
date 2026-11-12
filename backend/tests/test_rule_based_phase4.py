"""Phase 4 deterministic rule tests; no Flask, database or model required."""
from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from agents.rule_based_agent import RuleBasedAgent  # noqa: E402
from core.features import FEATURE_NAMES  # noqa: E402
from rules.rule_engine import RULES, RuleInputError, evaluate_rules, rule_catalog  # noqa: E402

BASE = {
    'gender':'Female','age':44,'hypertension':0,'heart_disease':0,
    'smoking_history':'never','bmi':27.32,'HbA1c_level':5.0,'blood_glucose_level':110,
}
PRED = {
    'prediction':0,'model_score_class_1':0.22,'score_is_calibrated':True,
    'output_kind':'dataset_label_classification','model_version':'test-fixture-not-trained',
    'input_feature_names':list(FEATURE_NAMES),
}


def fired(features=None, prediction=None):
    result = evaluate_rules(BASE if features is None else features, PRED if prediction is None else prediction)
    return {f['rule_id'] for f in result['flags']}


class RulesUnitTests(unittest.TestCase):
    def assert_bad(self, features=None, prediction=None):
        with self.assertRaises(RuleInputError):
            evaluate_rules(BASE if features is None else features,
                           PRED if prediction is None else prediction)

    def test_no_rules_triggered(self):
        self.assertEqual(fired(), set())

    def test_hba1c_low_boundary_569(self):
        self.assertNotIn('RB001', fired({**BASE,'HbA1c_level':5.69}))

    def test_hba1c_lower_boundary_57(self):
        self.assertIn('RB001', fired({**BASE,'HbA1c_level':5.7}))

    def test_hba1c_upper_649(self):
        self.assertEqual(fired({**BASE,'HbA1c_level':6.49}), {'RB001'})

    def test_hba1c_at_65(self):
        self.assertEqual(fired({**BASE,'HbA1c_level':6.5}), {'RB002','RB006'})

    def test_glucose_199(self):
        self.assertNotIn('RB003', fired({**BASE,'blood_glucose_level':199.0}))

    def test_glucose_200(self):
        self.assertIn('RB003', fired({**BASE,'blood_glucose_level':200.0}))

    def test_no_info_smoking(self):
        self.assertEqual(fired({**BASE,'smoking_history':'No Info'}), {'RB004'})

    def test_model_class1(self):
        self.assertEqual(fired(prediction={**PRED,'prediction':1}), {'RB005'})

    def test_model_class1_hba1c_high_not_disagreement(self):
        out=fired({**BASE,'HbA1c_level':6.8}, {**PRED,'prediction':1})
        self.assertIn('RB002',out)
        self.assertIn('RB005',out)
        self.assertNotIn('RB006',out)

    def test_uncalibrated_score_flag(self):
        self.assertEqual(fired(prediction={**PRED,'score_is_calibrated':False}), {'RB007'})

    def test_all_evaluations_in_fixed_order(self):
        output=evaluate_rules(BASE,PRED)
        self.assertEqual(output['rules_evaluated'],7)
        self.assertEqual(output['triggered_rules_count'],0)
        self.assertFalse(output['review_required'])
        self.assertEqual([e['rule_id'] for e in output['evaluations']], [r.rule_id for r in RULES])

    def test_combined_review_and_evidence(self):
        feat={**BASE,'smoking_history':'No Info','HbA1c_level':6.8,'blood_glucose_level':210}
        prediction={**PRED,'score_is_calibrated':False}
        out=evaluate_rules(feat,prediction)
        self.assertEqual({f['rule_id'] for f in out['flags']}, {'RB002','RB003','RB004','RB006','RB007'})
        self.assertEqual(out['triggered_rules_count'],5)
        self.assertEqual(len(out['evidence']),5)
        self.assertTrue(out['review_required'])
        for flag in out['flags']:
            self.assertIn('criterion',flag)
            self.assertIn('source',flag)

    def test_immutability(self):
        feat=copy.deepcopy(BASE); pred=copy.deepcopy(PRED)
        feat_copy=copy.deepcopy(feat);pred_copy=copy.deepcopy(pred)
        evaluate_rules(feat,pred)
        self.assertEqual(feat,feat_copy)
        self.assertEqual(pred,pred_copy)

    def test_missing_features_invalid(self):
        self.assert_bad({k:v for k,v in BASE.items() if k!='gender'})

    def test_noncanonical_features_invalid(self):
        self.assert_bad({**BASE,'gender':' female '})

    def test_prediction_boolean_rejected(self):
        self.assert_bad(prediction={**PRED,'prediction':True})

    def test_prediction_score_nonfinite_and_out_of_range(self):
        for value in (math.nan,math.inf,-1,1.01,'0.5',True):
            with self.subTest(value=value):
                self.assert_bad(prediction={**PRED,'model_score_class_1':value})

    def test_prediction_contract_mismatch(self):
        for changed in ({'output_kind':'diagnosis'}, {'model_version':''},
                        {'input_feature_names':['age']},{'score_is_calibrated':'false'}):
            with self.subTest(changed=changed):
                self.assert_bad(prediction={**PRED,**changed})

    def test_prediction_absent(self):
        self.assert_bad(prediction={})

    def test_agent_contract_and_version(self):
        message=RuleBasedAgent().run('request_unit',BASE,PRED)
        self.assertEqual(message.status,'ok')
        self.assertEqual(message.agent,'rule_based')
        self.assertEqual(message.request_id,'request_unit')
        self.assertEqual(message.version,'edu-rule-set-v1')
        self.assertEqual(message.payload['model_version'],PRED['model_version'])

    def test_agent_errors_not_echo_patient_values(self):
        message=RuleBasedAgent().run('req', {**BASE,'bmi':'PRIVATE_TEST_SENTINEL'},PRED)
        self.assertEqual(message.status,'error')
        self.assertEqual(message.payload['error_type'],'invalid_rule_input')
        self.assertNotIn('PRIVATE_TEST_SENTINEL',repr(message.to_dict()))

    def test_catalog_has_stable_source_ids_and_no_health_data(self):
        catalog=rule_catalog()
        self.assertEqual(len(catalog),7)
        self.assertEqual([r['rule_id'] for r in catalog],[f'RB{i:03d}' for i in range(1,8)])
        for row in catalog:
            self.assertIn('source', row)
            self.assertIn('criterion',row)
            self.assertIn('severity',row)
            self.assertNotIn('observed_value',row)


if __name__ == '__main__':
    unittest.main()
