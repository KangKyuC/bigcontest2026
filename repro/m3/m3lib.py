# -*- coding: utf-8 -*-
"""M3 preprocessing, density models, grouped selection and inference helpers."""
from pathlib import Path
import json
import warnings
import numpy as np
import pandas as pd
from scipy.stats import multivariate_normal
from sklearn.mixture import GaussianMixture
from sklearn.covariance import LedoitWolf
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.model_selection import GroupKFold
from sklearn.exceptions import ConvergenceWarning

HERE=Path(__file__).resolve().parent
CFG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
PRIMARY=CFG['primary_features']

def jsonable(x):
    if isinstance(x,dict): return {str(k):jsonable(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)): return [jsonable(v) for v in x]
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.bool_,)): return bool(x)
    if isinstance(x,(float,np.floating)): return float(x) if np.isfinite(x) else None
    if isinstance(x,Path):return str(x)
    return x

def dump(x,path):
    Path(path).write_text(json.dumps(jsonable(x),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def cohort(df):return df.sex.astype(str)+'_'+df.age_floor.astype(str)

def block_of(f):
    if f in ['contact','sms_contact']:return 'contact'
    if f.startswith('flow_'):return 'place'
    return 'outings'

def numeric_features(df,features):
    absent=set(features)-set(df)
    if absent:raise ValueError('Missing feature columns: '+str(sorted(absent)))
    a=df[features].to_numpy(dtype=float,copy=True)
    if not np.isfinite(a).all():raise ValueError('Missing/non-finite features must not be imputed as normal values')
    for j,f in enumerate(features):
        if f in CFG['log1p_features']:
            if np.any(a[:,j]<0):raise ValueError(f'Negative level: {f}')
            a[:,j]=np.log1p(a[:,j])
    return a

class PeerTransformer:
    """Centers external behavior against non-Gangnam peers; SK against training peers.

    All scale parameters are fit only on the passed training rows. Blocks have
    equal Euclidean expected dimension, not equal GMM likelihood weighting.
    """
    def __init__(self,features=None,scale='robust',adjust_age=True,block_weight=True):
        self.features=list(features or PRIMARY);self.scale=scale
        self.adjust_age=adjust_age;self.block_weight=block_weight

    def fit(self,train,reference):
        self.train_dongs_=sorted(train.dong.unique().tolist())
        self.center_map_={};self.global_center_={}
        a=numeric_features(train,self.features);groups=cohort(train).to_numpy()
        if reference.district.eq('강남구').any():raise ValueError('External reference includes Gangnam')
        refgroups=cohort(reference).to_numpy()
        for j,f in enumerate(self.features):
            is_external=not f.startswith('flow_')
            values=numeric_features(reference,[f])[:,0] if is_external else a[:,j]
            gs=refgroups if is_external else groups
            valid=np.isfinite(values)
            self.global_center_[f]=float(np.median(values[valid])) if self.adjust_age else 0.
            self.center_map_[f]={g:float(np.median(values[(gs==g)&valid])) for g in sorted(set(gs))} if self.adjust_age else {}
        centered=self._center(train,a)
        self.scaler_=RobustScaler(quantile_range=(25,75)) if self.scale=='robust' else StandardScaler()
        self.scaler_.fit(centered)
        sizes={b:sum(block_of(f)==b for f in self.features) for b in set(map(block_of,self.features))}
        self.weights_=np.array([1/np.sqrt(sizes[block_of(f)]) if self.block_weight else 1. for f in self.features])
        self.log_jacobian_=float(np.log(self.weights_/self.scaler_.scale_).sum())
        self.train_feature_low_=np.quantile(a,.01,axis=0);self.train_feature_high_=np.quantile(a,.99,axis=0)
        return self

    def _center(self,df,a):
        groups=cohort(df).to_numpy()
        centers=np.column_stack([[self.center_map_[f].get(g,self.global_center_[f]) for g in groups] for f in self.features])
        return a-centers

    def transform(self,df):
        a=numeric_features(df,self.features)
        return self.scaler_.transform(self._center(df,a))*self.weights_

    def state(self):
        return jsonable(dict(features=self.features,scale=self.scale,adjust_age=self.adjust_age,block_weight=self.block_weight,
            center_map=self.center_map_,global_center=self.global_center_,scaler_center=getattr(self.scaler_,'center_',getattr(self.scaler_,'mean_',None)),
            scaler_scale=self.scaler_.scale_,block_weights=self.weights_,log_jacobian=self.log_jacobian_,train_dongs=self.train_dongs_))

class ShrinkGaussian:
    n_components=1
    def fit(self,z):
        self.cov_model_=LedoitWolf().fit(z);self.mean_=self.cov_model_.location_;self.cov_=self.cov_model_.covariance_
        self.converged_=True;return self
    def score_samples(self,z):return np.atleast_1d(multivariate_normal.logpdf(z,mean=self.mean_,cov=self.cov_,allow_singular=False))
    def predict(self,z):return np.zeros(len(z),dtype=int)
    def predict_proba(self,z):return np.ones((len(z),1))

def candidates():return ['diag_1','shrink_1']+[f'diag_{k}' for k in CFG['candidate_k'] if k>1]

def complexity(name):return 0 if name=='diag_1' else 1 if name=='shrink_1' else int(name.split('_')[1])

def fit_density(z,name,seed=None,n_init=None):
    if name=='shrink_1':return ShrinkGaussian().fit(z)
    k=int(name.split('_')[1])
    model=GaussianMixture(n_components=k,covariance_type='diag',reg_covar=CFG['gmm_reg_covar'],
                         n_init=n_init or CFG['gmm_n_init'],max_iter=CFG['gmm_max_iter'],random_state=CFG['seed'] if seed is None else seed)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',ConvergenceWarning);model.fit(z)
    model.warning_messages_=[str(w.message) for w in caught]
    if not model.converged_:raise RuntimeError(f'{name} failed to converge')
    return model

def group_splits(df,n=None,seed=None):
    splitter=GroupKFold(n_splits=min(n or CFG['inner_folds'],df.dong.nunique()),shuffle=True,
                        random_state=CFG['seed'] if seed is None else seed)
    return list(splitter.split(df,groups=df.dong))

def choose_candidate(train,reference,features=None,scale='robust',adjust_age=True,seed=None):
    fs=list(features or PRIMARY);names=candidates();rows=[];folds=group_splits(train,seed=seed)
    for fold,(it,iv) in enumerate(folds):
        tr=train.iloc[it];va=train.iloc[iv]
        assert set(tr.dong).isdisjoint(set(va.dong))
        prep=PeerTransformer(fs,scale=scale,adjust_age=adjust_age).fit(tr,reference)
        z=prep.transform(tr);v=prep.transform(va)
        for name in names:
            mod=fit_density(z,name,seed=seed)
            score=float(np.mean(mod.score_samples(v))+prep.log_jacobian_)
            rows.append(dict(fold=fold,candidate=name,heldout_log_density=score,train_rows=len(tr),test_rows=len(va),
                             test_dongs='|'.join(sorted(va.dong.unique()))))
    table=pd.DataFrame(rows)
    summary=table.groupby('candidate').heldout_log_density.agg(['mean','std','count']).reset_index()
    summary['se']=summary['std']/np.sqrt(summary['count']);summary['complexity']=summary.candidate.map(complexity)
    best=summary.sort_values('mean',ascending=False).iloc[0]
    cutoff=float(best['mean']-best['se'])
    selected=summary[summary['mean']>=cutoff].sort_values(['complexity','mean'],ascending=[True,False]).iloc[0].candidate
    summary['within_one_se']=summary['mean']>=cutoff;summary['selected']=summary.candidate.eq(selected)
    return str(selected),summary,table

def fit_bundle(df,reference,name,features=None,scale='robust',adjust_age=True,seed=None):
    prep=PeerTransformer(features,scale=scale,adjust_age=adjust_age).fit(df,reference)
    mod=fit_density(prep.transform(df),name,seed=seed)
    return dict(transformer=prep,model=mod,candidate=name,features=prep.features)

def predict_bundle(bundle,df):
    z=bundle['transformer'].transform(df);mod=bundle['model']
    return mod.predict(z),mod.predict_proba(z),mod.score_samples(z)+bundle['transformer'].log_jacobian_

def bootstrap_mean_ci(values,seed=None,repeats=None):
    a=np.asarray(values,dtype=float);a=a[np.isfinite(a)]
    if not len(a):return dict(mean=None,lower=None,upper=None,n=0)
    rng=np.random.default_rng(CFG['seed'] if seed is None else seed)
    draws=a[rng.integers(0,len(a),size=(repeats or CFG['ci_repeats'],len(a)))].mean(axis=1)
    return dict(mean=float(a.mean()),lower=float(np.quantile(draws,.025)),upper=float(np.quantile(draws,.975)),n=len(a),
                interpretation='percentile interval resampling fixed held-out group errors; not all training uncertainty')

def feature_contrasts(bundle,df):
    """Exact additive log posterior odds vs second component for diagonal GMM."""
    model=bundle['model'];prep=bundle['transformer'];z=prep.transform(df)
    if not isinstance(model,GaussianMixture) or model.n_components<2:return pd.DataFrame()
    probs=model.predict_proba(z);order=np.argsort(-probs,axis=1);rows=[]
    for i,row in df.reset_index(drop=True).iterrows():
        a,b=order[i,:2]
        v1=model.covariances_[a];v2=model.covariances_[b]
        parts=-.5*(np.log(v1/v2)+(z[i]-model.means_[a])**2/v1-(z[i]-model.means_[b])**2/v2)
        intercept=float(np.log(model.weights_[a]/model.weights_[b]))
        log_odds=float(intercept+parts.sum())
        # Log posterior odds from score components avoids numerical probability underflow.
        scores=model._estimate_weighted_log_prob(z[i:i+1])[0]
        if not np.isclose(log_odds,scores[a]-scores[b],atol=1e-8):raise AssertionError('Explanation does not sum to component log odds')
        rec=dict(cell_id=row.cell_id,component=int(a),comparison_component=int(b),posterior=float(probs[i,a]),prior_log_odds=intercept,component_log_odds=log_odds)
        rec.update({f:float(parts[j]) for j,f in enumerate(prep.features)})
        rows.append(rec)
    return pd.DataFrame(rows)
