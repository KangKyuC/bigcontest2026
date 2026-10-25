# -*- coding: utf-8 -*-
"""Documented post-fit diagnostics for conflicting geographic validation results."""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
from threadpoolctl import threadpool_limits
from m3lib import HERE,CFG,dump,bootstrap_mean_ci
from train_evaluate import regression_test,save,log

def moran_permutation(values,xy,repeats=9999):
    n=len(values);dist=cdist(xy,xy);np.fill_diagonal(dist,np.inf)
    w=np.zeros((n,n));w[np.arange(n)[:,None],np.argsort(dist,axis=1)[:,:4]]=1
    w=np.maximum(w,w.T);w=w/w.sum(axis=1,keepdims=True)
    z=np.array(values)-np.mean(values)
    def calc(v):return float(n/w.sum()*(v@w@v)/(v@v)) if v@v>0 else np.nan
    observed=calc(z);rng=np.random.default_rng(CFG['seed']+7000)
    perm=np.array([calc(rng.permutation(z)) for _ in range(repeats)])
    expected=-1/(n-1)
    p=(1+np.sum(abs(perm-expected)>=abs(observed-expected)))/(repeats+1)
    return dict(moran_I=observed,expected_under_exchangeability=expected,permutation_p=float(p),permutations=repeats,
                note='Exploratory 22-dong mean residual diagnostic, symmetrized 4-nearest-neighbor graph with row-standardized weights. Exchangeability is approximate; no causal inference.')

def main():
    d=pd.read_csv(HERE/'data/model_input_primary.csv');d=d[d.model_eligible].copy()
    ref=pd.read_csv(HERE/'data/reference_non_gangnam.csv').query('window==202510')
    cen=pd.read_csv(HERE/'data/dong_observation_centroids.csv').sort_values('dong')
    rows=[]
    for k in [4,6]:
        c=cen.copy();c['spatial_block']=KMeans(n_clusters=k,n_init=30,random_state=CFG['seed']).fit_predict(c[['X','Y']])
        x=d.merge(c[['dong','spatial_block']],on='dong',validate='many_to_one')
        pred,fold=regression_test(x,ref,spatial=True)
        save(pred,f'exploratory_spatial{k}_regression.csv');save(c,f'exploratory_spatial{k}_blocks.csv')
        err=pred.groupby(['heldout_group','model']).absolute_error.mean().unstack()
        ci=bootstrap_mean_ci(err.outings-err.outings_plus_SK)
        rows.append(dict(blocks=k,role='post-fit exploratory sensitivity',mae_outings=float(pred[pred.model.eq('outings')].absolute_error.mean()),
                         mae_plus_SK=float(pred[pred.model.eq('outings_plus_SK')].absolute_error.mean()),group_mean_improvement=ci))
    pred=pd.read_csv(HERE/'results/contact_prediction_oof.csv');pred['residual']=pred.actual-pred.prediction
    spatial=[]
    for name,g in pred.groupby('model'):
        z=g.groupby('dong',as_index=False).residual.mean().merge(cen,on='dong',validate='one_to_one').sort_values('dong')
        stat=moran_permutation(z.residual.to_numpy(),z[['X','Y']].to_numpy());stat['model']=name;spatial.append(stat)
    dump(dict(post_fit=True,reason='LODO and five-block validation had different directions. No replacement of primary result.',
              additional_partitions=rows,residual_spatial_diagnostics=spatial),HERE/'results/additional_diagnostics.json')
    log('Additional diagnostics completed')

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
