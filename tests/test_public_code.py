# -*- coding: utf-8 -*-
"""Data-free contract tests. These do not validate real isolation-risk accuracy."""
import json
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'repro/m3'))
from m3lib import PeerTransformer,fit_bundle,predict_bundle
from predict import predict_frame
from analyze_activity import contrasts
from verify_sources import verify_sources


def synthetic_fixture():
    rng=np.random.default_rng(1701)
    rows=[]
    for d in range(6):
        for sex in ['남성','여성']:
            for age in [20,30,40,50,60]:
                values=rng.uniform(1,30,6)
                rows.append(dict(cell_id=f'{d}_{sex}_{age}',dong=f'fixture{d}',sex=sex,age_floor=age,
                                 district='강남구',window=202510,flow_period_start=202507,flow_period_end=202509,
                                 max_move_unestimated_share=.1,contact=values[0],weekday_move=values[1],
                                 holiday_move=values[2],flow_per_point=values[3],flow_concentration=values[4],flow_change_log=values[5]/100))
    data=pd.DataFrame(rows)
    reference=data.copy();reference['district']='external fixture';reference['dong']='reference'
    bundle=fit_bundle(data,reference,'shrink_1')
    bundle.update(config={'quality_exclusion_unestimated_share':.5},adoption={'type_adopted':False})
    return data,reference,bundle


class PublicContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame,cls.reference,cls.bundle=synthetic_fixture()

    def test_k1_never_publishes_a_certain_risk_type(self):
        out=predict_frame(self.frame,self.bundle)
        self.assertTrue(out.published_type.isna().all())
        self.assertTrue(out.membership_probability.isna().all())
        self.assertTrue(np.isfinite(out.feature_log_density).all())

    def test_unseen_evaluation_values_cannot_refit_preprocessor(self):
        train=self.frame[self.frame.dong!='fixture5']
        p=PeerTransformer().fit(train,self.reference)
        before=json.dumps(p.state(),sort_keys=True)
        held=self.frame[self.frame.dong=='fixture5'].copy()
        held['flow_per_point']=1e9
        p.transform(held)
        self.assertEqual(before,json.dumps(p.state(),sort_keys=True))
        self.assertNotIn('fixture5',p.train_dongs_)

    def test_forbidden_reference_leakage_is_rejected(self):
        bad=self.reference.copy();bad.loc[0,'district']='강남구'
        with self.assertRaises(ValueError):PeerTransformer().fit(self.frame,bad)

    def test_mismatched_window_is_rejected(self):
        wrong=self.frame.copy();wrong['window']=202512
        with self.assertRaises(ValueError):predict_frame(wrong,self.bundle)

    def test_unvalidated_city_and_duplicate_rows_are_rejected(self):
        wrong=self.frame.copy();wrong.loc[0,'dong']='춘천시'
        with self.assertRaises(ValueError):predict_frame(wrong,self.bundle)
        with self.assertRaises(ValueError):predict_frame(pd.concat([self.frame,self.frame.iloc[:1]]),self.bundle)

    def test_missing_measurement_is_not_imputed_as_normal(self):
        wrong=self.frame.copy();wrong.loc[0,'contact']=np.nan
        with self.assertRaises(ValueError):predict_frame(wrong,self.bundle)

    def test_policy_assumptions_cannot_change_numeric_model(self):
        changed=self.frame.copy();changed['support_need']='not observed';changed['income']=0
        a=predict_frame(self.frame,self.bundle);b=predict_frame(changed,self.bundle)
        pd.testing.assert_frame_equal(a,b)

    def test_calendar_days_prevent_false_month_length_effects(self):
        rows=[]
        for month,days in [(202507,31),(202508,31),(202511,30),(202512,31)]:
            row=dict(region='fixture',sex='여성',age_floor=20,month=month)
            for col in ['transactions','narrow_transactions','sports_transactions','gym_transactions','film_transactions','weighted_flow']:
                row[col]=days*10
            rows.append(row)
        result=contrasts(pd.DataFrame(rows))
        self.assertTrue(np.allclose(result.filter(like='_change_pct'),0))

    def test_missing_source_fails_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            result=verify_sources(Path(directory))
            self.assertFalse(result['passed'])
            self.assertEqual(len(result['checks']),8)

    def test_frozen_metrics_preserve_primary_negative_result(self):
        summary=json.loads((ROOT/'results/m3_20261022/summary.json').read_text(encoding='utf-8'))
        self.assertFalse(summary['adoption']['type_adopted'])
        self.assertLess(summary['SK_contact_mae_improvement']['mean'],0)
        self.assertGreater(summary['SK_spatial_contact_mae_improvement']['mean'],0)
        self.assertIsNone(summary['stability']['oob_ari_median'])


if __name__=='__main__':unittest.main()
