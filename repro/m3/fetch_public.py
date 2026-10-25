# -*- coding: utf-8 -*-
"""Download only the two public Seoul workbooks and verify their original hashes."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from verify_sources import ROOT,sha256


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root',type=Path,default=ROOT/'data/raw')
    args=ap.parse_args()
    entries=json.loads((ROOT/'data/sources.json').read_text(encoding='utf-8'))['sources']
    for entry in entries:
        if entry['access']!='public':
            continue
        path=args.data_root/entry['path']
        if path.is_file():
            if sha256(path)!=entry['sha256']:
                raise ValueError(f'Existing file has a different hash: {path}; preserve and inspect it first')
            print(f'Already verified: {entry["path"]}',flush=True)
            continue
        request=Request(entry['download_url'],data=urlencode(entry['request_data']).encode('ascii'),
                        headers={'User-Agent':'BigContest2026-reproduction/1.0',
                                 'Referer':entry['source_url']})
        with urlopen(request,timeout=60) as response:
            payload=response.read()
        import hashlib
        if len(payload)!=entry['bytes'] or hashlib.sha256(payload).hexdigest()!=entry['sha256']:
            raise ValueError(f'Public source changed or download failed: {entry["id"]}; original bytes were not replaced')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(payload)
        print(f'Downloaded and verified: {entry["path"]}',flush=True)


if __name__=='__main__':
    main()
