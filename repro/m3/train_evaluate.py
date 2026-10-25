# -*- coding: utf-8 -*-
"""Fit and evaluate M3 with nested dong holdouts, spatial sensitivity and OOB stability."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import sys
import time
import joblib
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.linear_model import Ridge
from sklearn.metrics import adjusted_rand_score, silhouette_score, mean_absolute_error, mean_squared_error, r2_score
from threadpoolctl import threadpool_limits
from m3lib import (HERE,CFG,PRIMARY,PeerTransformer,choose_candidate,fit_bundle,predict_bundle,bootstrap_mean_ci,
                   feature_contrasts,group_splits,cohort,dump,jsonable,numeric_features,fit_density)

DATA=HERE/'data';RESULT=HERE/'results';MODELS=HERE/'models'

def save(df,name):df.to_csv(RESULT/name,index=False,encoding='utf-8-sig',float_format='%.12g')

def log(s):
    msg=datetime.now(timezone.utc).isoformat()+' '+s
    print(msg,flush=True)
    with (RESULT/'run.log').open('a',encoding='utf-8') as f:f.write(msg+'\n')

def nested_density(df,ref,spatial=False):
    if spatial:
        splits=[(np.flatnonzero(df.spatial_block.to_numpy()!=g),np.flatnonzero(df.spatial_block.to_numpy()==g),f'block_{g}') for g in sorted(df.spatial_block.unique())]
    else:
        splits=[(np.flatnonzero(df.dong.to_numpy()!=g),np.flatnonzero(df.dong.to_numpy()==g),g) for g in sorted(df.dong.unique())]
    rows=[];selection=[];audit=[]
    for fold,(it,iv,name) in enumerate(splits):
        tr=df.iloc[it].copy();va=df.iloc[iv].copy()
        selected,scores,_=choose_candidate(tr,ref,seed=CFG['seed']+fold)
        bundle=fit_bundle(tr,ref,selected,seed=CFG['seed']+fold)
        _,_,density=predict_bundle(bundle,va)
        prep=bundle['transformer'];z=prep.transform(tr);v=prep.transform(va)
        shrink=fit_density(z,'shrink_1');diag=fit_density(z,'diag_1')
        ds=shrink.score_samples(v)+prep.log_jacobian_;dd=diag.score_samples(v)+prep.log_jacobian_
        for j,r in enumerate(va.itertuples()):
            rows.append(dict(cell_id=r.cell_id,dong=r.dong,cohort=r.cohort,fold=fold,heldout_group=name,selected=selected,
                selected_log_density=float(density[j]),shrink_log_density=float(ds[j]),diag1_log_density=float(dd[j])))
        selection.append(dict(fold=fold,heldout_group=name,selected=selected,train_rows=len(tr),test_rows=len(va),
                              inner_best=scores.sort_values('mean',ascending=False).iloc[0].candidate))
        audit.append(dict(stage='nested_spatial' if spatial else 'nested_dong',fold=fold,train_dongs=sorted(tr.dong.unique()),test_dongs=sorted(va.dong.unique()),disjoint=set(tr.dong).isdisjoint(set(va.dong))))
        log(f"Nested {'spatial' if spatial else 'dong'} {fold+1}/{len(splits)}: {name}, selected {selected}")
    return pd.DataFrame(rows),pd.DataFrame(selection),audit

def stability(df,ref,bundle,name,km_k=None):
    rng=np.random.default_rng(CFG['seed']+903)
    dongs=np.array(sorted(df.dong.unique()));n=len(df)
    if km_k is None:
        labels,_,_=predict_bundle(bundle,df);k=bundle['model'].n_components
    else:
        prep=PeerTransformer().fit(df,ref);km=KMeans(n_clusters=km_k,n_init=CFG['kmeans_n_init'],random_state=CFG['seed']).fit(prep.transform(df))
        labels=km.predict(prep.transform(df));k=km_k
    counts=np.zeros((n,k));reps=[];density_draws=np.full((CFG['bootstrap_repeats'],n),np.nan)
    for rep in range(CFG['bootstrap_repeats']):
        sample=rng.choice(dongs,size=len(dongs),replace=True)
        train=pd.concat([df[df.dong.eq(g)] for g in sample],ignore_index=True)
        inbag=df.dong.isin(sample).to_numpy();oob=~inbag
        if oob.sum()<2:continue
        try:
            if km_k is None:
                b=fit_bundle(train,ref,name,seed=CFG['seed']+1000+rep)
                pred,_,_=predict_bundle(b,df)
                density_draws[rep,oob]=predict_bundle(b,df.loc[oob])[2]
            else:
                pr=PeerTransformer().fit(train,ref)
                m=KMeans(n_clusters=km_k,n_init=CFG['kmeans_n_init'],random_state=CFG['seed']+1000+rep).fit(pr.transform(train))
                pred=m.predict(pr.transform(df))
            # Align names on in-bag cells only; OOB ARI itself is permutation invariant.
            mat=np.zeros((k,k));np.add.at(mat,(pred[inbag],labels[inbag]),1)
            ii,jj=linear_sum_assignment(-mat);mapping=dict(zip(ii,jj));aligned=np.array([mapping.get(x,x) for x in pred])
            counts[np.flatnonzero(oob),aligned[oob]]+=1
            reps.append(dict(rep=rep,status='ok',oob_dongs=int(df.loc[oob,'dong'].nunique()),oob_rows=int(oob.sum()),
                             oob_ari=float(adjusted_rand_score(labels[oob],pred[oob])),all_ari=float(adjusted_rand_score(labels,pred)),
                             oob_named_agreement=float(np.mean(labels[oob]==aligned[oob]))))
        except Exception as e:
            reps.append(dict(rep=rep,status='failed',error=f'{type(e).__name__}: {e}'))
        if (rep+1)%50==0:log(f'Stability {name} {rep+1}/{CFG["bootstrap_repeats"]}')
    tab=pd.DataFrame(reps);ok=tab[tab.status.eq('ok')]
    denom=counts.sum(axis=1)
    probs=np.divide(counts,denom[:,None],out=np.zeros_like(counts),where=denom[:,None]>0)
    cell=pd.DataFrame(dict(cell_id=df.cell_id,full_component=labels,oob_repeats=denom.astype(int),
                           oob_assignment_agreement=probs[np.arange(n),labels] if k>1 else np.full(n,np.nan)))
    if km_k is None:
        cell['oob_log_density_q05']=np.nanquantile(density_draws,.05,axis=0)
        cell['oob_log_density_q50']=np.nanquantile(density_draws,.5,axis=0)
        cell['oob_log_density_q95']=np.nanquantile(density_draws,.95,axis=0)
    for c in range(k):cell[f'oob_component_{c}_fraction']=probs[:,c]
    stats=dict(candidate=name,n_components=k,successful_repeats=len(ok),failed_repeats=int(tab.status.ne('ok').sum()),
               oob_ari_median=float(ok.oob_ari.median()) if len(ok) and k>1 else None,
               oob_ari_p10=float(ok.oob_ari.quantile(.1)) if len(ok) and k>1 else None,
               oob_ari_p90=float(ok.oob_ari.quantile(.9)) if len(ok) and k>1 else None,
               median_cell_assignment_agreement=float(cell.oob_assignment_agreement.median()) if k>1 else None,
               type_stability_applicable=k>1,
               note='K=1 label agreement is tautologically perfect and is not reported as evidence of type stability.' if k==1 else 'OOB dong reassignment stability; not accuracy against isolation ground truth.')
    return tab,cell,stats

def ridge_design(train,test,ref,features):
    levels=[f'{sex}_{age}' for sex in ['남성','여성'] for age in [20,30,40,50,60]]
    def dummies(x):return (cohort(x).to_numpy()[:,None]==np.array(levels[1:])[None,:]).astype(float)
    a=dummies(train);b=dummies(test)
    if features:
        pr=PeerTransformer(features,block_weight=False).fit(train,ref)
        a=np.column_stack([a,pr.transform(train)]);b=np.column_stack([b,pr.transform(test)])
    return a,b

def regression_test(df,ref,spatial=False):
    specs={'demographics':[], 'outings':['weekday_move','holiday_move'],
           'outings_plus_SK':['weekday_move','holiday_move','flow_per_point','flow_concentration','flow_change_log']}
    gs=df.spatial_block if spatial else df.dong
    rows=[];foldrows=[]
    for fold,g in enumerate(sorted(gs.unique())):
        tr=df[gs.ne(g)];va=df[gs.eq(g)]
        inner=group_splits(tr,seed=CFG['seed']+fold)
        for name,features in specs.items():
            errs={a:[] for a in CFG['ridge_alphas']}
            for it,iv in inner:
                ti=tr.iloc[it];vi=tr.iloc[iv];x,z=ridge_design(ti,vi,ref,features)
                for alpha in errs:
                    reg=Ridge(alpha=alpha).fit(x,ti.contact)
                    errs[alpha].append(mean_absolute_error(vi.contact,np.maximum(0,reg.predict(z))))
            alpha=min(errs,key=lambda a:(np.mean(errs[a]),-a))
            x,z=ridge_design(tr,va,ref,features);reg=Ridge(alpha=alpha).fit(x,tr.contact)
            yhat=np.maximum(0,reg.predict(z))
            for j,r in enumerate(va.itertuples()):
                rows.append(dict(cell_id=r.cell_id,dong=r.dong,cohort=r.cohort,fold=fold,heldout_group=str(g),
                                 model=name,alpha=alpha,actual=r.contact,prediction=float(yhat[j]),absolute_error=float(abs(yhat[j]-r.contact))))
            foldrows.append(dict(fold=fold,heldout_group=str(g),model=name,alpha=alpha,mae=float(np.mean(abs(yhat-va.contact.to_numpy())))))
        if (fold+1)%5==0 or spatial:log(f"Ridge {'spatial' if spatial else 'dong'} {fold+1}/{gs.nunique()}")
    return pd.DataFrame(rows),pd.DataFrame(foldrows)

def sensitivity(df,late,ref,bundle,labels):
    name=bundle['candidate'];rows=[]
    primary_z=pd.DataFrame(bundle['transformer'].transform(df),columns=bundle['features'],index=df.cell_id)
    specs=[('standard_scaling',df,ref,PRIMARY,'standard',True),('without_age_adjustment',df,ref,PRIMARY,'robust',False),
           ('add_SMS',df,ref,PRIMARY+['sms_contact'],'robust',True)]
    for f in PRIMARY:specs.append(('drop_'+f,df,ref,[q for q in PRIMARY if q!=f],'robust',True))
    weighted=df.copy();weighted_ref=ref.copy()
    for f in ['contact','weekday_move','holiday_move']:
        weighted[f]=weighted[f+'_population_weighted'];weighted_ref[f]=weighted_ref[f+'_population_weighted']
    specs.append(('approx_population_weighted',weighted,weighted_ref,PRIMARY,'robust',True))
    specs.append(('replace_moves_with_distances',df,ref,['contact','weekday_distance','holiday_distance','flow_per_point','flow_concentration','flow_change_log'],'robust',True))
    highq=df[~df.quality_warning].copy();specs.append(('lower_unestimated_only',highq,ref,PRIMARY,'robust',True))
    for variant,tr,rr,features,scale,adj in specs:
        try:
            b=fit_bundle(tr,rr,name,features=features,scale=scale,adjust_age=adj)
            pp,_,_=predict_bundle(b,tr)
            base=pd.Series(labels,index=df.cell_id).loc[tr.cell_id].to_numpy()
            zz=pd.DataFrame(b['transformer'].transform(tr),columns=features,index=tr.cell_id)
            common=[f for f in features if f in PRIMARY]
            rho=[spearmanr(primary_z.loc[tr.cell_id,f],zz[f]).statistic for f in common]
            rows.append(dict(variant=variant,status='ok',rows=len(tr),ari_to_primary=float(adjusted_rand_score(base,pp)) if bundle['model'].n_components>1 else np.nan,
                             common_feature_score_spearman_median=float(np.median(rho)),common_feature_score_spearman_min=float(np.min(rho)),candidate=name,
                             note='fixed selected complexity; descriptive perturbation, not independent validation'))
        except Exception as e:rows.append(dict(variant=variant,status='unavailable',error=str(e)))
    both=df[['cell_id']].merge(late,on='cell_id',validate='one_to_one')
    pred,probs,_=predict_bundle(bundle,both)
    rho=[spearmanr(df[f],both[f]).statistic for f in PRIMARY]
    rows.append(dict(variant='Dec_window_frozen_model_reference',status='ok',rows=len(both),ari_to_primary=float(adjusted_rand_score(labels,pred)) if bundle['model'].n_components>1 else np.nan,
                     exact_same_component_fraction=float(np.mean(labels==pred)) if bundle['model'].n_components>1 else np.nan,
                     common_feature_score_spearman_median=float(np.median(rho)),common_feature_score_spearman_min=float(np.min(rho)),candidate=name,note='Sep-Nov vs Jul-Sep overlaps. No future-validation claim.'))
    return pd.DataFrame(rows),pd.DataFrame(dict(cell_id=both.cell_id,primary_component=labels,later_component=pred,later_max_posterior=probs.max(axis=1)))

def make_profiles(df,ref,bundle,stability_cells,adoption,late_labels):
    labels,probs,density=predict_bundle(bundle,df);pr=bundle['transformer'];z=pr.transform(df)
    result=df.copy();result['candidate_component']=labels
    has_types=bundle['model'].n_components>1
    result['max_component_probability']=probs.max(axis=1) if has_types else np.nan
    result['component_entropy']=-np.sum(probs*np.log(np.maximum(probs,1e-300)),axis=1) if has_types else np.nan
    result['type_adopted']=adoption['type_adopted'];result['model_output']='aggregate characteristic profile'
    result['low_membership_certainty']=(probs.max(axis=1)<CFG['adoption']['soft_assignment_review_probability']) if has_types else True
    result['feature_log_density']=density
    a=numeric_features(df,PRIMARY)
    result['outside_training_central_range_features']=((a<pr.train_feature_low_)|(a>pr.train_feature_high_)).sum(axis=1)
    for j,f in enumerate(PRIMARY):result['scaled_'+f]=z[:,j]
    for f in ['contact','weekday_move','holiday_move']:
        positions=[]
        for r in df.itertuples():
            values=ref[(ref.sex==r.sex)&(ref.age_floor==r.age_floor)][f].to_numpy()
            val=getattr(r,f)
            positions.append(float((np.sum(values<val)+.5*np.sum(values==val))/len(values)))
        result[f+'_seoul_peer_percentile']=positions
    result['low_contact_and_outings_aggregate']=(result.contact_seoul_peer_percentile<=.25)&(result.weekday_move_seoul_peer_percentile<=.25)&(result.holiday_move_seoul_peer_percentile<=.25)
    result=result.merge(stability_cells,on='cell_id',validate='one_to_one').merge(late_labels,on='cell_id',validate='one_to_one')
    # Candidate component is diagnostic unless all adoption gates pass.
    queries=[]
    for r in result.itertuples():
        q=['해당 지역·연령에서 관계형성 지원을 원하는 수요가 실제로 있는지 확인']
        if r.contact_seoul_peer_percentile<=.25:q.append('전화번호 연락 지표와 실제 도움·교류 관계의 차이를 확인')
        if min(r.weekday_move_seoul_peer_percentile,r.holiday_move_seoul_peer_percentile)<=.25:q.append('근거리 외출 누락·이동제약·지역 활동기회 중 어떤 설명이 맞는지 확인')
        q.append('필요가 별도로 확인되면 같은 기능 사업의 회차·장소·시간·접촉방식·대안을 대조')
        queries.append(dict(cell_id=r.cell_id,unit='administrative-dong x sex x age aggregate',
            observed=dict(region='강남구',dong=r.dong,sex=r.sex,age_band_lower=int(r.age_floor),age_band_upper=None if r.age_floor==60 else int(r.age_floor+9),
                          behavior_window=[202507,202509],contact_index=r.contact,weekday_move_index=r.weekday_move,holiday_move_index=r.holiday_move,
                          flow_per_observed_point=r.flow_per_point,flow_concentration=r.flow_concentration,
                          contact_peer_percentile=r.contact_seoul_peer_percentile),
            model=dict(type_adopted=adoption['type_adopted'],published_type=int(r.candidate_component) if adoption['type_adopted'] else None,
                       diagnostic_component=int(r.candidate_component),membership_probability=r.max_component_probability,
                       oob_assignment_agreement=r.oob_assignment_agreement,probability_meaning='mixture component membership, never isolation probability'),
            policy_assumptions=dict(support_need=None,exact_age=None,household_type=None,income=None,available_times=None,participation_intent=None),
            investigation_questions=q,individual_risk=None,eligibility_decision=None,
            limitations=['Aggregate means do not describe a single person.','Policy eligibility must be evaluated separately.','No actual service demand or policy effect estimated.']))
    dump(queries,RESULT/'policy_handoff.json')
    return result

def main():
    RESULT.mkdir(exist_ok=True);MODELS.mkdir(exist_ok=True)
    start=time.time();(RESULT/'run.log').write_text('',encoding='utf-8')
    cfgbytes=(HERE/'config.json').read_bytes();(RESULT/'config_used.json').write_bytes(cfgbytes)
    dump(dict(started_at_utc=datetime.now(timezone.utc).isoformat(),config_sha256=hashlib.sha256(cfgbytes).hexdigest(),
              protocol_sha256=hashlib.sha256((HERE/'분석계약.md').read_bytes()).hexdigest(),python=sys.version,
              packages={n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','scikit-learn','joblib','threadpoolctl']},model_training=True),RESULT/'run_manifest.json')
    df=pd.read_csv(DATA/'model_input_primary.csv');df=df[df.model_eligible].copy().reset_index(drop=True)
    late=pd.read_csv(DATA/'model_input_sensitivity.csv');late=late[late.model_eligible].copy()
    ref=pd.read_csv(DATA/'reference_non_gangnam.csv');ref=ref[ref.window.eq(202510)].copy()
    centers=pd.read_csv(DATA/'dong_observation_centroids.csv').sort_values('dong')
    skm=KMeans(n_clusters=CFG['spatial_blocks'],n_init=30,random_state=CFG['seed']).fit(centers[['X','Y']])
    centers['spatial_block']=skm.labels_;save(centers,'spatial_blocks.csv')
    df=df.merge(centers[['dong','spatial_block']],on='dong',validate='many_to_one')
    log(f'Main data: {len(df)} cells / {df.dong.nunique()} dongs; reference {len(ref)} cells')
    chosen,cv,cvfold=choose_candidate(df,ref)
    save(cv,'candidate_cv.csv');save(cvfold,'candidate_cv_folds.csv')
    bundle=fit_bundle(df,ref,chosen);labels,probs,_=predict_bundle(bundle,df)
    dump(bundle['transformer'].state(),MODELS/'preprocessing.json')
    log(f'Primary candidate selected by inner grouped CV: {chosen}')
    z=bundle['transformer'].transform(df)
    fits=[];kmresults=[]
    for name in cv.candidate:
        m=fit_density(z,name);labs=m.predict(z)
        fits.append(dict(candidate=name,n_components=m.n_components,train_log_density=float(np.mean(m.score_samples(z))+bundle['transformer'].log_jacobian_),
                         bic=float(m.bic(z)) if hasattr(m,'bic') else np.nan,
                         silhouette=float(silhouette_score(z,labs)) if 1<len(set(labs))<len(z) else np.nan,
                         smallest_component=int(pd.Series(labs).value_counts().min())))
    save(pd.DataFrame(fits),'candidate_fit_diagnostics.csv')
    for k in [2,3,4,5]:
        km=KMeans(n_clusters=k,n_init=CFG['kmeans_n_init'],random_state=CFG['seed']).fit(z)
        kmresults.append(dict(k=k,silhouette=float(silhouette_score(z,km.labels_)),inertia=float(km.inertia_),ari_to_gmm=float(adjusted_rand_score(labels,km.labels_))))
    km_table=pd.DataFrame(kmresults);save(km_table,'kmeans_baselines.csv')
    nested,selection,audit=nested_density(df,ref)
    save(nested,'nested_dong_predictions.csv');save(selection,'nested_dong_selection.csv')
    spatial,spselection,spaudit=nested_density(df,ref,spatial=True)
    save(spatial,'nested_spatial_predictions.csv');save(spselection,'nested_spatial_selection.csv');dump(audit+spaudit,RESULT/'split_audit.json')
    group=nested.groupby('dong')[['selected_log_density','shrink_log_density','diag1_log_density']].mean()
    ci=bootstrap_mean_ci(group.selected_log_density-group.shrink_log_density)
    spatialgroup=spatial.groupby('heldout_group')[['selected_log_density','shrink_log_density']].mean()
    spatialci=bootstrap_mean_ci(spatialgroup.selected_log_density-spatialgroup.shrink_log_density)
    boot,cells,bstats=stability(df,ref,bundle,chosen)
    save(boot,'bootstrap_dong_stability.csv');save(cells,'bootstrap_cell_stability.csv')
    multi=cv[cv.candidate.isin(['diag_2','diag_3','diag_4','diag_5'])].sort_values('mean',ascending=False).iloc[0].candidate
    exploratory=fit_bundle(df,ref,multi)
    eb,ec,es=stability(df,ref,exploratory,multi)
    save(eb,'exploratory_gmm_bootstrap.csv');save(ec,'exploratory_gmm_cell_stability.csv')
    explain=feature_contrasts(exploratory,df)
    if len(explain):save(explain,'exploratory_gmm_feature_explanations.csv')
    exploratory['status']='exploratory diagnostic; not the selected or adopted model';joblib.dump(exploratory,MODELS/'exploratory_gmm.joblib')
    km_k=int(km_table.sort_values('silhouette',ascending=False).iloc[0].k)
    kb,kc,ks=stability(df,ref,bundle,'kmeans_'+str(km_k),km_k=km_k)
    save(kb,'kmeans_bootstrap_stability.csv');save(kc,'kmeans_cell_stability.csv')
    ablation=[]
    for label,features in [('behavior_only',['contact','weekday_move','holiday_move']),('SK_only',['flow_per_point','flow_concentration','flow_change_log'])]:
        choice,ac,af=choose_candidate(df,ref,features=features)
        b=fit_bundle(df,ref,choice,features=features);ll,_,_=predict_bundle(b,df)
        ablation.append(dict(block=label,selected=choice,features=features,ari_to_full=float(adjusted_rand_score(labels,ll)) if bundle['model'].n_components>1 else None,note='Density/BIC across feature spaces are not compared. Changed partition is not demonstrated benefit. K=1 comparison is not interpreted.'))
        save(ac,label+'_candidate_cv.csv')
    dump(ablation,RESULT/'block_ablation.json')
    sens,later=sensitivity(df,late,ref,bundle,labels)
    save(sens,'sensitivity.csv');save(later,'overlapping_window_comparison.csv')
    rpred,rfold=regression_test(df,ref);spred,sfold=regression_test(df,ref,spatial=True)
    save(rpred,'contact_prediction_oof.csv');save(rfold,'contact_prediction_fold_errors.csv')
    save(spred,'contact_prediction_spatial_oof.csv');save(sfold,'contact_prediction_spatial_fold_errors.csv')
    performance=[]
    for scheme,p in [('dong',rpred),('spatial',spred)]:
        for model,g in p.groupby('model'):
            performance.append(dict(scheme=scheme,model=model,mae=mean_absolute_error(g.actual,g.prediction),rmse=np.sqrt(mean_squared_error(g.actual,g.prediction)),r2=r2_score(g.actual,g.prediction)))
    save(pd.DataFrame(performance),'contact_prediction_metrics.csv')
    errors=rpred.groupby(['dong','model']).absolute_error.mean().unstack()
    delta=errors.outings-errors.outings_plus_SK
    regci=bootstrap_mean_ci(delta)
    sperrors=spred.groupby(['heldout_group','model']).absolute_error.mean().unstack()
    spregci=bootstrap_mean_ci(sperrors.outings-sperrors.outings_plus_SK)
    subgroup=rpred.groupby(['cohort','model']).absolute_error.agg(['mean','count']).reset_index();save(subgroup,'contact_prediction_cohort_errors.csv')
    size=pd.DataFrame(dict(component=labels,dong=df.dong)).groupby('component').agg(cells=('dong','size'),dongs=('dong','nunique')).reset_index()
    save(size,'component_coverage.csv')
    criteria={
      'selected_more_than_one_component':bundle['model'].n_components>1,
      'nested_gain_over_shrink_lower_ci_above_zero':ci['lower']>0,
      'oob_ari_median':bstats['oob_ari_median'] is not None and bstats['oob_ari_median']>=CFG['adoption']['bootstrap_oob_ari_median_min'],
      'oob_ari_lower_tail':bstats['oob_ari_p10'] is not None and bstats['oob_ari_p10']>=CFG['adoption']['bootstrap_oob_ari_p10_min'],
      'min_type_cells':int(size.cells.min())>=CFG['adoption']['min_cells_per_type'],
      'min_type_dongs':int(size.dongs.min())>=CFG['adoption']['min_dongs_per_type'],
      'bootstrap_fits_converged':bstats['failed_repeats']==0}
    adoption=dict(type_adopted=all(criteria.values()),criteria=criteria,
                   output_if_not_adopted='Continuous aggregate characteristic profiles; component labels remain exploratory.',
                   threshold_status='Prespecified engineering adoption rules; not universally validated statistical cutoffs.')
    result_summary=dict(primary_candidate=chosen,rows=len(df),dongs=df.dong.nunique(),n_components=bundle['model'].n_components,
                        density_gain_vs_shrink=ci,spatial_density_gain_vs_shrink=spatialci,stability=bstats,exploratory_gmm_stability=es,kmeans_baseline_stability=ks,
                        SK_contact_mae_improvement=regci,SK_spatial_contact_mae_improvement=spregci,
                        regression_metrics=performance,adoption=adoption,fit_seconds=time.time()-start,
                        interpretation='No individual isolation labels, risk probability, causal effects or policy-demand ground truth.')
    dump(result_summary,RESULT/'summary.json')
    bundle.update(config=CFG,adoption=adoption,model_version='M3-1.0',training_cell_ids=df.cell_id.tolist(),scope='Gangnam adult aggregate profiles',
                  input_sha256=hashlib.sha256((DATA/'model_input_primary.csv').read_bytes()).hexdigest())
    joblib.dump(bundle,MODELS/'m3_bundle.joblib')
    reloaded=joblib.load(MODELS/'m3_bundle.joblib')
    pred2,probs2,d2=predict_bundle(reloaded,df)
    assert np.array_equal(labels,pred2) and np.allclose(probs,probs2,atol=1e-12)
    profile=make_profiles(df,ref,bundle,cells,adoption,later);save(profile,'group_profiles.csv')
    contrasts=feature_contrasts(bundle,df)
    if len(contrasts):save(contrasts,'component_feature_explanations.csv')
    prototype=profile.groupby('candidate_component')[PRIMARY+['contact_seoul_peer_percentile','weekday_move_seoul_peer_percentile','holiday_move_seoul_peer_percentile']].agg(['mean','median'])
    prototype.columns=['__'.join(c) for c in prototype.columns];save(prototype.reset_index(),'component_profiles.csv')
    correlations=[]
    for i,f in enumerate(PRIMARY):
        for j,g in enumerate(PRIMARY):
            if i<j:correlations.append(dict(feature1=f,feature2=g,spearman_raw=spearmanr(df[f],df[g]).statistic,spearman_transformed=spearmanr(z[:,i],z[:,j]).statistic))
    save(pd.DataFrame(correlations),'feature_dependence.csv')
    log('Completed: '+json.dumps(jsonable(result_summary),ensure_ascii=False))

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
