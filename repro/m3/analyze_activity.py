# -*- coding: utf-8 -*-
"""Optional descriptive card/SK EDA for all 24 groups; not M3 model training."""
import argparse
import calendar
from functools import reduce
import json
from pathlib import Path
import re
import numpy as np
import pandas as pd
from verify_sources import ROOT,sha256,verify_sources

HERE=Path(__file__).resolve().parent
KEY=['region','sex','age_floor']
GROUPS={'narrow':['스포츠시설','헬스장','영화/공연'],
        'sports':['스포츠시설'],'gym':['헬스장'],'film':['영화/공연']}


def card_monthly(path,encoding='utf-8-sig',separator=','):
    parts=[]
    use=['TA_YMD','MCT_SGG_CD','MCT_RY_CD','SEX_CCD','AGE_CCD','USE_CNT','TS_AT']
    for x in pd.read_csv(path,encoding=encoding,sep=separator,usecols=use,chunksize=200000):
        x=x[x.SEX_CCD.isin(['남성','여성'])].copy()
        x['month']=pd.to_numeric(x.TA_YMD.astype(str).str[:6])
        x=x[x.month.between(202507,202512)].copy()
        x['region']=x.MCT_SGG_CD.map({'서울 강남구':'강남구','강원 춘천시':'춘천시'})
        x['sex']=x.SEX_CCD
        x['age_floor']=pd.to_numeric(x.AGE_CCD.str.extract(r'(\d+)',expand=False)).clip(upper=60)
        if x.region.isna().any() or not x.age_floor.isin([10,20,30,40,50,60]).all():
            raise ValueError('Unexpected card region or age')
        keys=['month',*KEY]
        x['transactions']=pd.to_numeric(x.USE_CNT,errors='raise')
        x['amount']=pd.to_numeric(x.TS_AT,errors='raise')
        base=x.groupby(keys)[['transactions','amount']].sum()
        for family,industries in GROUPS.items():
            base[family+'_transactions']=x[x.MCT_RY_CD.isin(industries)].groupby(keys).transactions.sum()
        parts.append(base)
    return pd.concat(parts).groupby(level=[0,1,2,3]).sum(min_count=1).reset_index()


def flow_monthly(raw):
    keys=['BLOCK_CD','X_COORD_key','Y_COORD_key'];months={};duplicate_rows=0
    for month in range(202507,202513):
        original=pd.read_csv(raw/f'contest/sk/flow_age_pop_{month}.csv',sep='|',
                             dtype={'BLOCK_CD':str},float_precision='round_trip')
        x=original.drop_duplicates().copy()
        duplicate_rows+=len(original)-len(x)
        x=x[x.BLOCK_CD.str[:5].isin(['11230','32010'])].copy()
        for coord in ['X_COORD','Y_COORD']:x[coord+'_key']=x[coord].round(6)
        if x.duplicated(keys).any():
            raise ValueError(f'Conflicting point records remain after exact-row deduplication: {month}')
        months[month]=x
    common=reduce(lambda a,b:a.merge(b,on=keys,validate='one_to_one'),[x[keys] for x in months.values()])
    out=[]
    for month,x in months.items():
        x=common.merge(x,on=keys,validate='one_to_one')
        x['region']=x.BLOCK_CD.str[:5].map({'11230':'강남구','32010':'춘천시'})
        for (region,g) in x.groupby('region'):
            for sex,prefix in [('남성','MAN'),('여성','WMAN')]:
                for age in [10,20,30,40,50,60]:
                    col=f'{prefix}_FLOW_POP_CNT_{age}'+('GU' if age==60 else 'G')
                    out.append(dict(month=month,region=region,sex=sex,age_floor=age,
                                    flow_daily_mean_sum=float(g[col].sum())))
    return pd.DataFrame(out),duplicate_rows


def contrasts(monthly):
    metrics=['transactions','narrow_transactions','sports_transactions','gym_transactions','film_transactions','weighted_flow']
    rows=[]
    for keys,g in monthly.groupby(KEY):
        b=g[g.month.isin([202507,202508])][metrics].sum(min_count=1)/62
        l=g[g.month.isin([202511,202512])][metrics].sum(min_count=1)/61
        row=dict(zip(KEY,keys))
        for f in metrics:
            label='flow' if f=='weighted_flow' else f
            row[label+'_change_pct']=float(100*(l[f]/b[f]-1)) if pd.notna(b[f]) and b[f]>0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root',type=Path,default=ROOT/'data/raw')
    ap.add_argument('--card-file',type=Path)
    args=ap.parse_args()
    card=args.card_file or args.data_root/'contest/card/신한카드_빅콘테스트2026_데이터2.csv'
    if args.card_file is None and not card.exists():card=card.with_suffix('.txt')
    known=json.loads((ROOT/'data/sources.json').read_text(encoding='utf-8'))['optional_sources']
    digest=sha256(card) if card.is_file() else None
    info=next((entry for entry in known if entry['sha256']==digest),None)
    if info is None:
        raise ValueError('Expected the verified card data2 CSV or original TXT; see data/sources.json and docs/REPRODUCE.md')
    if not verify_sources(args.data_root)['passed']:
        raise ValueError('Core source hashes must pass before optional EDA')
    flow,duplicates=flow_monthly(args.data_root)
    monthly=card_monthly(card,info['encoding'],info['delimiter']).merge(flow,on=['month',*KEY],validate='one_to_one')
    if len(monthly)!=144 or monthly[KEY].drop_duplicates().shape[0]!=24:
        raise ValueError('Expected all 24 groups x six months')
    monthly['calendar_days']=monthly.month.map(lambda m:calendar.monthrange(m//100,m%100)[1])
    monthly['weighted_flow']=monthly.flow_daily_mean_sum*monthly.calendar_days
    out=HERE/'results';out.mkdir(exist_ok=True)
    monthly.to_csv(out/'activity_monthly.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    result=contrasts(monthly)
    result.to_csv(out/'activity_contrasts.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    reference=pd.read_csv(ROOT/'results/m3_20261022/activity_contrasts.csv').set_index(KEY).sort_index()
    observed=result.set_index(KEY).sort_index()
    comparison=observed.index.equals(reference.index) and np.allclose(observed[reference.columns],reference,rtol=0,atol=1e-6,equal_nan=True)
    if not comparison:
        raise ValueError('Activity EDA differs from the preserved 24-group reference; inspect original inputs and definitions')
    audit={'groups':24,'rows':144,'scope':'all card customers, not district residents',
           'exact_duplicate_SK_rows_removed':duplicates,'card_sha256':sha256(card),
           'reference_comparison_passed':bool(comparison),'absolute_tolerance':1e-6,
           'comparison':'Jul-Aug 62 calendar days vs Nov-Dec 61 calendar days',
           'limits':['Descriptive provided-record sums; unobserved industries are not proven zero.',
                     'No weather/holiday adjustment or legacy regression confidence intervals are reproduced here.',
                     'Six-month fixed points are retrospective, not prospective validation.',
                     'Card data1, TXT copies and residence scopes are not added to the same totals.']}
    (out/'activity_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False))


if __name__=='__main__':
    main()
