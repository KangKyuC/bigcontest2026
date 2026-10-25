# -*- coding: utf-8 -*-
"""Compare reproduced statistical outputs with the immutable published run."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from predict import predict_frame
from m3lib import HERE,dump
import joblib

ROOT=HERE.parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tolerance',type=float,default=1e-6)
    args=ap.parse_args()
    frozen=ROOT/'results/m3_20261022'
    actual=json.loads((HERE/'results/summary.json').read_text(encoding='utf-8'))
    expected=json.loads((frozen/'summary.json').read_text(encoding='utf-8'))
    checks=[]
    def check(name,ok):
        checks.append({'check':name,'passed':bool(ok)})
    for key in ['primary_candidate','rows','dongs','n_components']:
        check(key,actual[key]==expected[key])
    check('type_adopted',actual['adoption']['type_adopted']==expected['adoption']['type_adopted'])
    for key in ['exploratory_gmm_stability','kmeans_baseline_stability']:
        for field in ['oob_ari_median','oob_ari_p10','oob_ari_p90']:
            check(key+'/'+field,np.isclose(actual[key][field],expected[key][field],rtol=0,atol=args.tolerance))
    for key in ['SK_contact_mae_improvement','SK_spatial_contact_mae_improvement']:
        for field in ['mean','lower','upper']:
            check(key+'/'+field,np.isclose(actual[key][field],expected[key][field],rtol=0,atol=args.tolerance))
    for filename,keycols,numcols in [
        ('candidate_cv.csv',['candidate'],['mean','se']),
        ('contact_prediction_metrics.csv',['scheme','model'],['mae','rmse','r2']),
    ]:
        observed=pd.read_csv(HERE/'results'/filename).set_index(keycols).sort_index()
        reference=pd.read_csv(frozen/filename).set_index(keycols).sort_index()
        same_keys=observed.index.equals(reference.index)
        check(filename+'/keys',same_keys)
        check(filename+'/values',same_keys and np.allclose(observed[numcols],reference[numcols],rtol=0,atol=args.tolerance))
    inputs=pd.read_csv(HERE/'data/model_input_primary.csv')
    pred=predict_frame(inputs,joblib.load(HERE/'models/m3_bundle.joblib'))
    check('all_220_predictions_finite',len(pred)==220 and np.isfinite(pred.feature_log_density).all())
    check('no_published_risk_type',pred.published_type.isna().all())
    pred.to_csv(HERE/'results/example_predictions.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    outcome={'passed':all(row['passed'] for row in checks),'absolute_tolerance':args.tolerance,
             'reference':'results/m3_20261022','checks':checks,
             'meaning':'Numerical reproduction, not isolation-risk validation. Runtime and timestamps are excluded.'}
    dump(outcome,HERE/'results/reference_comparison.json')
    print(json.dumps({'passed':outcome['passed'],'checks':len(checks),'absolute_tolerance':args.tolerance}))
    if not outcome['passed']:
        print(json.dumps([row for row in checks if not row['passed']],ensure_ascii=False))
        raise SystemExit(1)


if __name__=='__main__':
    main()
