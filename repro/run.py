# -*- coding: utf-8 -*-
"""Run raw preparation, training, evaluation, inference and numerical comparison."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
M3=ROOT/'repro/m3'
STAGES={
    'prepare':'prepare_data.py',
    'train':'train_evaluate.py',
    'diagnostics':'additional_diagnostics.py',
    'validate':'validate_model.py',
    'report':'build_deliverables.py',
    'compare':'compare_reference.py',
}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root',type=Path,default=ROOT/'data/raw')
    ap.add_argument('--stages',default='prepare,train,diagnostics,validate,compare',
                    help='Ordered comma-separated stages. Add report after installing requirements-report.txt.')
    args=ap.parse_args()
    selected=args.stages.split(',')
    if any(stage not in STAGES for stage in selected):
        ap.error('Unknown stage; choose '+','.join(STAGES))
    env=os.environ.copy()
    env['PYTHONIOENCODING']='utf-8'
    env['OMP_NUM_THREADS']='1';env['OPENBLAS_NUM_THREADS']='1';env['MKL_NUM_THREADS']='1'
    for stage in selected:
        command=[sys.executable,str(M3/STAGES[stage])]
        if stage=='prepare':
            command+=['--data-root',str(args.data_root.resolve())]
        print(f'Running {stage}',flush=True)
        subprocess.run(command,cwd=ROOT,env=env,check=True)
    print('Selected reproduction stages completed.',flush=True)


if __name__=='__main__':
    main()
