# -*- coding: utf-8 -*-
"""Meaningful data-contract, leakage, serialization and inference regression checks."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from m3lib import HERE,CFG,PRIMARY,PeerTransformer,fit_bundle,predict_bundle,feature_contrasts,dump
from predict import predict_frame

def main():
    checks=[]
    def check(name,passed,detail=None):
        checks.append(dict(name=name,passed=bool(passed),detail=detail))
        if not passed:raise AssertionError(name)
    def rejects(name,fn):
        try:fn()
        except ValueError:check(name,True);return
        check(name,False)
    df=pd.read_csv(HERE/'data/model_input_primary.csv');late=pd.read_csv(HERE/'data/model_input_sensitivity.csv')
    ref=pd.read_csv(HERE/'data/reference_non_gangnam.csv').query('window==202510')
    bundle=joblib.load(HERE/'models/m3_bundle.joblib')
    check('two_unique_220_cell_windows',len(df)==len(late)==220 and not df.cell_id.duplicated().any() and set(df.cell_id)==set(late.cell_id))
    check('source_audits_all_passed',all(r['passed'] for r in json.loads((HERE/'data/input_checks.json').read_text(encoding='utf-8'))))
    check('reference_excludes_target_district',ref.district.ne('강남구').all() and ref.seoul_code7.nunique()==402)
    check('all_nested_outer_splits_disjoint',all(r['disjoint'] and not(set(r['train_dongs'])&set(r['test_dongs'])) for r in json.loads((HERE/'results/split_audit.json').read_text(encoding='utf-8'))))
    raw_before=df.copy(deep=True)
    tr=df[df.dong.ne('수서동')];te=df[df.dong.eq('수서동')]
    prep=PeerTransformer().fit(tr,ref);state=prep.state()
    extreme=te.copy();extreme[PRIMARY]=1e7
    prep.transform(extreme)
    check('heldout_transform_does_not_refit_preprocessing',state==prep.state())
    check('heldout_dong_absent_from_fitted_preprocessor','수서동' not in prep.train_dongs_)
    prep.transform(df);check('numeric_transforms_do_not_mutate_inputs',df.equals(raw_before))
    labels,probs,density=predict_bundle(bundle,df)
    check('finite_density_and_probability_simplex',np.isfinite(density).all() and np.isfinite(probs).all() and np.allclose(probs.sum(axis=1),1))
    pred=predict_frame(df,bundle)
    check('CLI_interface_matches_saved_model',np.array_equal(labels,pred.diagnostic_component) and np.allclose(density,pred.feature_log_density))
    check('unadopted_types_not_published',bundle['adoption']['type_adopted'] or pred.published_type.isna().all())
    if bundle['model'].n_components==1:check('single_component_not_presented_as_100pct_certainty',pred.membership_probability.isna().all())
    rejects('missing_feature_rejected',lambda:predict_frame(df.drop(columns='contact'),bundle))
    broken=df.copy();broken.loc[0,'contact']=np.nan
    rejects('missing_value_not_zero_imputed',lambda:predict_frame(broken,bundle))
    wrong=late.copy();wrong['flow_period_start']=202507;wrong['flow_period_end']=202509
    rejects('mismatched_time_window_rejected',lambda:predict_frame(wrong,bundle))
    other=df.copy();other.loc[0,'dong']='춘천시'
    rejects('unvalidated_city_transfer_rejected',lambda:predict_frame(other,bundle))
    duplicate=pd.concat([df,df.iloc[:1]],ignore_index=True)
    rejects('duplicate_unit_rejected',lambda:predict_frame(duplicate,bundle))
    age=df.copy();age.loc[0,'age_floor']=10
    rejects('unsupported_under20_rejected',lambda:predict_frame(age,bundle))
    lowq=df.copy();lowq.loc[0,'max_move_unestimated_share']=.7
    rejects('insufficient_measurement_rejected',lambda:predict_frame(lowq,bundle))
    actual=pd.read_csv(HERE/'results/group_profiles.csv')
    check('profile_values_reproduce_input',np.allclose(actual.sort_values('cell_id')[PRIMARY],df.sort_values('cell_id')[PRIMARY]))
    check('policy_handoff_contains_no_inferred_need_or_risk',all(r['individual_risk'] is None and r['eligibility_decision'] is None and all(v is None for v in r['policy_assumptions'].values()) for r in json.loads((HERE/'results/policy_handoff.json').read_text(encoding='utf-8'))))
    # Test the explanatory identity even when the production model has K=1.
    exploratory=joblib.load(HERE/'models/exploratory_gmm.joblib');explain=feature_contrasts(exploratory,df)
    check('additive_component_explanations_sum',len(explain)==220 and np.allclose(explain[PRIMARY].sum(axis=1)+explain.prior_log_odds,explain.component_log_odds,atol=1e-8))
    for file in ['nested_dong_predictions.csv','nested_spatial_predictions.csv']:
        a=pd.read_csv(HERE/'results'/file);check(file+'_one_oof_prediction_per_cell',len(a)==220 and a.cell_id.nunique()==220)
    for file in ['contact_prediction_oof.csv','contact_prediction_spatial_oof.csv']:
        a=pd.read_csv(HERE/'results'/file);check(file+'_paired_identical_cells',a.groupby('model').cell_id.nunique().eq(220).all() and not a.duplicated(['cell_id','model']).any())
    output=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),checks=checks,passed=all(r['passed'] for r in checks),
                note='Engineering and statistical-design safeguards; not validation of isolation diagnosis.')
    dump(output,HERE/'results/validation.json')
    print(json.dumps(dict(passed=output['passed'],checks=len(checks)),ensure_ascii=False))

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
