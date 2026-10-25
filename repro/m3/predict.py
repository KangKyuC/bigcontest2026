# -*- coding: utf-8 -*-
"""Apply the fitted M3 model to prepared aggregate cells; no implicit raw-data joins."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from m3lib import HERE,PRIMARY,predict_bundle,dump

def predict_frame(frame,bundle):
    df=frame.copy(deep=True)
    required=['cell_id','dong','sex','age_floor','window','flow_period_start','flow_period_end','max_move_unestimated_share',*PRIMARY]
    missing=set(required)-set(df)
    if missing:raise ValueError('Missing required columns: '+str(sorted(missing)))
    if df.duplicated(['window','cell_id']).any():raise ValueError('Duplicate aggregate cell IDs')
    if not df.sex.isin(['남성','여성']).all() or not df.age_floor.isin([20,30,40,50,60]).all():raise ValueError('Unsupported sex/age category')
    if not df.dong.isin(bundle['transformer'].train_dongs_).all():raise ValueError('Model scope is the audited 22 Gangnam dongs; transfer is not validated')
    if not df.window.isin([202510,202512]).all():raise ValueError('Unsupported observation window; new-window input contract must be audited first')
    expected={202510:(202507,202509),202512:(202509,202511)}
    for w,(start,end) in expected.items():
        mask=df.window.eq(w)
        if not df.loc[mask,'flow_period_start'].eq(start).all() or not df.loc[mask,'flow_period_end'].eq(end).all():raise ValueError('Behavior and flow observation windows disagree')
    if df.max_move_unestimated_share.isna().any() or df.max_move_unestimated_share.gt(bundle['config']['quality_exclusion_unestimated_share']).any():raise ValueError('Input quality requires review before inference')
    labels,probs,density=predict_bundle(bundle,df)
    z=bundle['transformer'].transform(df)
    out=df[['cell_id','dong','sex','age_floor','window']].copy()
    out['published_type']=labels.astype(object) if bundle['adoption']['type_adopted'] else None
    out['type_adopted']=bundle['adoption']['type_adopted']
    out['diagnostic_component']=labels
    out['membership_probability']=probs.max(axis=1) if bundle['model'].n_components>1 else np.nan
    out['feature_log_density']=density
    out['window_status']=np.where(df.window.eq(202510),'primary retrospective window','overlapping sensitivity window')
    for j,f in enumerate(PRIMARY):out[f+'_score']=z[:,j]
    out['interpretation']='aggregate characteristic profile; not individual isolation risk'
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--model',type=Path,default=HERE/'models/m3_bundle.joblib');args=ap.parse_args()
    if args.output.resolve()==args.input.resolve():raise ValueError('Output must not overwrite input')
    bundle=joblib.load(args.model);df=pd.read_csv(args.input);out=predict_frame(df,bundle)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.suffix.lower()=='.json':dump(out.to_dict('records'),args.output)
    else:out.to_csv(args.output,index=False,encoding='utf-8-sig',float_format='%.12g')
    print(json.dumps(dict(rows=len(out),type_adopted=bundle['adoption']['type_adopted'],output=str(args.output)),ensure_ascii=False))

if __name__=='__main__':main()
