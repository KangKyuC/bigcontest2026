# -*- coding: utf-8 -*-
"""Verify raw-file bytes before reproducing the published M3 run."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def verify_sources(data_root,public_only=False):
    entries=json.loads((ROOT/'data/sources.json').read_text(encoding='utf-8'))['sources']
    checks=[]
    for entry in entries:
        if public_only and entry['access']!='public':
            continue
        path=data_root/entry['path']
        exists=path.is_file()
        passed=exists and path.stat().st_size==entry['bytes'] and sha256(path)==entry['sha256']
        checks.append({'id':entry['id'],'path':entry['path'],'exists':exists,'passed':passed})
    return {'passed':bool(checks) and all(row['passed'] for row in checks),'checks':checks}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root',type=Path,default=ROOT/'data/raw')
    ap.add_argument('--public-only',action='store_true')
    args=ap.parse_args()
    result=verify_sources(args.data_root,args.public_only)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
