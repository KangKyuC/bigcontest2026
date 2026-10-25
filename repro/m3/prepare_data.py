# -*- coding: utf-8 -*-
"""Build M3's auditable aggregate inputs. Reads original sources; fits no models."""
from pathlib import Path
import argparse
import calendar
import hashlib
import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DATA=HERE/'data'
CONFIG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
FIELDS={
    '총인구수':'provided_population',
    '평균 통화대상자 수':'contact',
    '평균 문자대상자 수':'sms_contact',
    '평일 총 이동 횟수':'weekday_move',
    '휴일 총 이동 횟수 평균':'holiday_move',
    '평일 총 이동 거리 합계':'weekday_distance',
    '휴일 총 이동 거리 합계':'holiday_distance',
    '집 추정 위치 평일 총 체류시간':'weekday_home_seconds',
    '집 추정 위치 휴일 총 체류시간':'holiday_home_seconds',
    '평일 총 이동 횟수 미추정 인구수':'weekday_unestimated',
    '휴일 이동 미추정 인구수':'holiday_unestimated',
    '평균 근무시간 평균':'work_minutes',
    '평균 출근 소요시간 평균':'commute_minutes',
    '근무시간 미추정 인구수':'work_unestimated',
    '출근 소요시간 미추정 인구수':'commute_unestimated',
}
MEASURES=['contact','sms_contact','weekday_move','holiday_move','weekday_distance','holiday_distance','weekday_home_seconds','holiday_home_seconds','work_minutes','commute_minutes']

def dump(obj,path):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def csv(df,name):
    df.to_csv(DATA/name,index=False,encoding='utf-8-sig',float_format='%.12g')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=ROOT/'data/raw')
    args=parser.parse_args()
    raw=args.data_root.resolve()
    from verify_sources import verify_sources
    verification=verify_sources(raw)
    if not verification['passed']:
        raise ValueError('Source verification failed: '+json.dumps(verification,ensure_ascii=False))
    DATA.mkdir(exist_ok=True)
    checks=[]; sources=[]
    def check(name,condition,detail=None):
        checks.append(dict(check=name,passed=bool(condition),detail=detail))
        if not condition:
            dump(checks,DATA/'input_checks.json')
            raise AssertionError(f'{name}: {detail}')
    def register(path,role):
        try: relative=path.relative_to(ROOT).as_posix()
        except ValueError: relative=path.relative_to(raw).as_posix()
        sources.append(dict(path=relative,sha256=sha(path),bytes=path.stat().st_size,role=role))
    bridge_path=HERE/'assets/gangnam_dong_codes.csv'
    bridge=pd.read_csv(bridge_path,dtype={'seoul_code7':str,'stat_code8':str,'admin_code':str})
    register(bridge_path,'official dong correspondence, reused')
    check('official_22_dong_unique',len(bridge)==22 and bridge.seoul_code7.nunique()==22)
    all_native=[]; all_coarse=[]
    for window in [202510,202512]:
        path=raw/f'public/seoul_citizen_{window}.xlsx'
        print(f'Read citizen source {window}',flush=True)
        register(path,'Seoul original 29-info workbook')
        x=pd.read_excel(path,usecols=['행정동코드','자치구','행정동','성별','연령대',*FIELDS])
        x=x.rename(columns={'행정동코드':'seoul_code7','자치구':'district','행정동':'dong','성별':'sex_code','연령대':'age5',**FIELDS})
        x['seoul_code7']=x.seoul_code7.astype(str);x['sex']=x.sex_code.map({1:'남성',2:'여성'});x['window']=window
        for f in FIELDS.values(): x[f]=pd.to_numeric(x[f],errors='coerce')
        x['dong']=x.dong.replace({'일원2동':'개포3동'})
        x['age_floor']=np.where(x.age5>=60,60,(x.age5//10)*10)
        for kind in ['weekday','holiday','work','commute']:
            x[kind+'_unestimated_share']=x[kind+'_unestimated']/x.provided_population
        check(f'citizen_{window}_complete_keys',len(x)==10176 and not x.duplicated(['seoul_code7','sex','age5']).any())
        check(f'citizen_{window}_positive_population',x.provided_population.gt(0).all())
        gn=x[x.district.eq('강남구')]
        check(f'citizen_{window}_gangnam_528',len(gn)==528 and gn.seoul_code7.nunique()==22)
        for f in ['weekday_unestimated_share','holiday_unestimated_share']:
            check(f'citizen_{window}_{f}_range',gn[f].between(0,1).all(),{'max':float(gn[f].max())})
        all_native.append(x)
        recs=[]
        for keys,g in x.groupby(['window','district','seoul_code7','dong','sex','age_floor'],sort=True):
            row=dict(zip(['window','district','seoul_code7','dong','sex','age_floor'],keys))
            expected=4 if row['age_floor']==60 else 2
            check_name=f"{window}/{row['seoul_code7']}/{row['sex']}/{row['age_floor']}"
            if len(g)!=expected: raise AssertionError(check_name)
            row['native_strata']=len(g);row['provided_population']=float(g.provided_population.sum())
            for f in MEASURES:
                valid=g[f].notna().all()
                row[f]=float(g[f].mean()) if valid else np.nan
                # Population-weighted estimates are only a sensitivity approximation.
                row[f+'_population_weighted']=float(np.average(g[f],weights=g.provided_population)) if valid else np.nan
            for kind in ['weekday','holiday','work','commute']:
                row[kind+'_unestimated_share']=float(g[kind+'_unestimated'].sum()/g.provided_population.sum())
                row[kind+'_unestimated_max5']=float(g[kind+'_unestimated_share'].max())
            recs.append(row)
        c=pd.DataFrame(recs)
        check(f'citizen_{window}_4240_aggregate_cells',len(c)==4240 and len(c[c.district.eq('강남구')])==220)
        all_coarse.append(c)
    native=pd.concat(all_native,ignore_index=True);public=pd.concat(all_coarse,ignore_index=True)
    csv(native,'citizen_native_selected.csv');csv(public,'citizen_age_standardized.csv')
    reference=public[~public.district.eq('강남구')].copy()
    check('reference_has_no_gangnam',len(reference)==8040 and reference.district.ne('강남구').all())
    csv(reference,'reference_non_gangnam.csv')

    # Rebuild the frame from the six originals. No legacy CSV or DuckDB is required.
    from spatial_frame import build_common_frame
    points=build_common_frame(raw,bridge)
    csv(points,'common_observation_frame.csv')
    for coord in ['X_COORD','Y_COORD']:points[coord+'_key']=points[coord].round(6)
    key=['BLOCK_CD','X_COORD_key','Y_COORD_key']
    check('common_point_keys_unique',len(points)==15178 and not points.duplicated(key).any())
    p=points.sort_values(key).reset_index(drop=True)
    adult_cols=[(sex,a,f'{prefix}_FLOW_POP_CNT_{a}'+('GU' if a==60 else 'G')) for sex,prefix in [('남성','MAN'),('여성','WMAN')] for a in [20,30,40,50,60]]
    raw_months={};monthly=[]
    for month in range(202507,202513):
        path=raw/f'contest/sk/flow_age_pop_{month}.csv';register(path,'contest original age-flow CSV')
        x=pd.read_csv(path,sep='|',dtype={'BLOCK_CD':str},float_precision='round_trip')
        check(f'flow_{month}_required_columns',set(['STD_YM','BLOCK_CD','X_COORD','Y_COORD']+[f for _,_,f in adult_cols]).issubset(x.columns))
        x=x[x.BLOCK_CD.str[:8].isin(bridge.stat_code8)].copy()
        for coord in ['X_COORD','Y_COORD']:x[coord+'_key']=x[coord].round(6)
        check(f'flow_{month}_raw_unique_normalized',not x.duplicated(key).any())
        check(f'flow_{month}_month_match',pd.to_numeric(x.STD_YM).eq(month).all())
        z=p[key+['dong']].merge(x[key+[f for _,_,f in adult_cols]],on=key,how='left',validate='one_to_one',sort=False)
        check(f'flow_{month}_common_full_coverage',len(z)==15178 and z[[f for _,_,f in adult_cols]].notna().all().all())
        check(f'flow_{month}_nonnegative',z[[f for _,_,f in adult_cols]].ge(0).all().all())
        raw_months[month]=z
        for dong,g in z.groupby('dong',sort=True):
            for sex,age,f in adult_cols:
                monthly.append(dict(dong=dong,month=month,sex=sex,age_floor=age,recorded_flow=float(g[f].sum()),observed_points=len(g)))
        print(f'Read SK {month}: {len(x)} raw Gangnam points, {len(z)} common points',flush=True)
    monthly=pd.DataFrame(monthly);csv(monthly,'sk_monthly_adults.csv')
    check('raw_SK_1320_unique_adult_month_cells',len(monthly)==1320 and not monthly.duplicated(['dong','month','sex','age_floor']).any())
    flow_records=[]
    for window,months in CONFIG['windows'].items():
        window=int(window);days={m:calendar.monthrange(m//100,m%100)[1] for m in months};total_days=sum(days.values())
        for sex,age,f in adult_cols:
            vals=sum(raw_months[m][f].to_numpy()*days[m] for m in months)/total_days
            temp=p[['dong']].copy();temp['value']=vals
            temp['start']=raw_months[months[0]][f].to_numpy();temp['end']=raw_months[months[-1]][f].to_numpy()
            for dong,g in temp.groupby('dong',sort=True):
                v=g.value.to_numpy();n=len(v);total=float(v.sum());weights=v/total if total>0 else np.zeros_like(v)
                start=float(g.start.mean());end=float(g.end.mean())
                flow_records.append(dict(window=window,dong=dong,sex=sex,age_floor=age,
                    flow_period_start=months[0],flow_period_end=months[-1],flow_period_days=total_days,
                    recorded_flow_daily=total,observed_points=n,flow_per_point=total/n,
                    flow_concentration=float(n*np.sum(weights**2)) if total>0 else np.nan,
                    flow_top10pct_share=float(np.sort(weights)[-int(np.ceil(n*.1)):].sum()) if total>0 else np.nan,
                    flow_change_log=float(np.log1p(end)-np.log1p(start)),flow_start_per_point=start,flow_end_per_point=end))
    flows=pd.DataFrame(flow_records);csv(flows,'sk_window_features.csv')
    centroids=p.groupby('dong',as_index=False).agg(X=('X_COORD','mean'),Y=('Y_COORD','mean'),longitude=('longitude','mean'),latitude=('latitude','mean'),observed_points=('BLOCK_CD','size'))
    csv(centroids,'dong_observation_centroids.csv')
    gn=public[public.district.eq('강남구')].merge(flows,on=['window','dong','sex','age_floor'],validate='one_to_one',how='outer',indicator=True)
    check('new_join_440_one_to_one',len(gn)==440 and gn['_merge'].eq('both').all())
    gn=gn.drop(columns='_merge').merge(bridge[['dong','stat_code8','admin_code']],on='dong',validate='many_to_one')
    gn['cell_id']=gn.seoul_code7+'_'+gn.sex.map({'남성':'M','여성':'F'})+'_'+gn.age_floor.astype(str)
    gn['cohort']=gn.sex+'_'+gn.age_floor.astype(str)
    gn['max_move_unestimated_share']=gn[['weekday_unestimated_max5','holiday_unestimated_max5']].max(axis=1)
    gn['quality_warning']=gn.max_move_unestimated_share>CONFIG['quality_warning_unestimated_share']
    gn['model_eligible']=gn[CONFIG['primary_features']].notna().all(axis=1) & (gn.max_move_unestimated_share<=CONFIG['quality_exclusion_unestimated_share'])
    gn=gn.sort_values(['window','cell_id']).reset_index(drop=True)
    csv(gn,'model_input_all_windows.csv')
    csv(gn[gn.window.eq(202510)],'model_input_primary.csv')
    csv(gn[gn.window.eq(202512)],'model_input_sensitivity.csv')
    for window,months in CONFIG['windows'].items():
        z=gn[gn.window.eq(int(window))]
        check(f'window_{window}_flow_alignment',z.flow_period_start.eq(months[0]).all() and z.flow_period_end.eq(months[-1]).all())
    correction=dict(old_table='Both windows had July-September SK values. Kept original file unchanged.',
                    new_table='October uses July-September; December uses September-November.',
                    changed_december_cells=220,
                    december_max_absolute_change=2864.7033803153317,
                    status='Historical audit result from 2026-10-22; legacy comparison is not rerun. New window alignment is tested above.')
    dump(correction,DATA/'prior_window_correction.json')
    qa=[]
    for w,g in gn.groupby('window'):
        for f in CONFIG['primary_features']+['max_move_unestimated_share','sms_contact']:
            qa.append(dict(window=int(w),feature=f,rows=len(g),missing=int(g[f].isna().sum()),minimum=float(g[f].min()),maximum=float(g[f].max())))
    csv(pd.DataFrame(qa),'feature_quality.csv')
    dump(checks,DATA/'input_checks.json')
    dump(dict(created_at_utc=datetime.now(timezone.utc).isoformat(),config_sha256=sha(HERE/'config.json'),
              protocol_sha256=sha(HERE/'분석계약.md'),sources=sources,
              final_rows=gn.groupby('window').size().to_dict(),eligible_rows=gn.groupby('window').model_eligible.sum().astype(int).to_dict(),
              quality_warning_rows=gn.groupby('window').quality_warning.sum().astype(int).to_dict(),
              reference_dongs_per_window=402,unit='aggregate cell, not a person',correction=correction),DATA/'input_manifest.json')
    print(json.dumps(dict(rows=len(gn),eligible=gn.groupby('window').model_eligible.sum().to_dict(),quality_warning=gn.groupby('window').quality_warning.sum().to_dict(),checks=len(checks),correction=correction),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
