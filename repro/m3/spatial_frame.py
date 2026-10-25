# -*- coding: utf-8 -*-
"""Reconstruct the six-month common Gangnam observation frame from originals."""
from functools import reduce
import pandas as pd
import numpy as np
from pyproj import Transformer


def build_common_frame(raw,bridge):
    frames=[]
    keys=['BLOCK_CD','X_COORD_key','Y_COORD_key']
    for month in range(202507,202513):
        frame=pd.read_csv(raw/f'contest/sk/flow_age_pop_{month}.csv',sep='|',
                          usecols=['BLOCK_CD','X_COORD','Y_COORD'],
                          dtype={'BLOCK_CD':str},float_precision='round_trip')
        frame=frame[frame.BLOCK_CD.str[:8].isin(bridge.stat_code8)].copy()
        for coord in ['X_COORD','Y_COORD']:
            frame[coord+'_key']=frame[coord].round(6)
        if frame.duplicated(keys).any():
            raise ValueError(f'Duplicate normalized observation point in {month}')
        frames.append(frame)
    common=reduce(lambda left,right:left.merge(right[keys],on=keys,validate='one_to_one'),frames)
    if len(common)!=15178:
        raise ValueError(f'Expected 15,178 common points, got {len(common)}; source definition changed')
    common['stat_code8']=common.BLOCK_CD.str[:8]
    common=common.merge(bridge[['stat_code8','dong']],on='stat_code8',validate='many_to_one')
    transform=Transformer.from_crs(5179,4326,always_xy=True)
    lon,lat=transform.transform(common.X_COORD,common.Y_COORD)
    if not np.all((lon>126.95)&(lon<127.17)&(lat>37.40)&(lat<37.57)):
        raise ValueError('Unexpected transformed Gangnam coordinate range')
    common['longitude']=lon;common['latitude']=lat
    return common[['BLOCK_CD','X_COORD','Y_COORD','stat_code8','dong','longitude','latitude']]
