# -*- coding: utf-8 -*-
"""Download only the two public Seoul workbooks and verify their original hashes."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,HTTPRedirectHandler,build_opener
from verify_sources import ROOT,sha256


def validate_download_url(url):
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or parsed.hostname!='datafile.seoul.go.kr'
            or parsed.port not in (None,443) or parsed.username or parsed.password):
        raise ValueError('Public downloads must use the official Seoul HTTPS host')
    return url


def public_target(data_root,entry):
    root=data_root.resolve()
    relative=Path(entry['path'])
    target=(root/relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(root) or target==root:
        raise ValueError('Public source path must stay inside the selected data root')
    return target


class SeoulRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_download_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root',type=Path,default=ROOT/'data/raw')
    args=ap.parse_args()
    entries=json.loads((ROOT/'data/sources.json').read_text(encoding='utf-8'))['sources']
    for entry in entries:
        if entry['access']!='public':
            continue
        path=public_target(args.data_root,entry)
        if path.is_file():
            if sha256(path)!=entry['sha256']:
                raise ValueError(f'Existing file has a different hash: {path}; preserve and inspect it first')
            print(f'Already verified: {entry["path"]}',flush=True)
            continue
        request=Request(validate_download_url(entry['download_url']),data=urlencode(entry['request_data']).encode('ascii'),
                        headers={'User-Agent':'BigContest2026-reproduction/1.0',
                                 'Referer':entry['source_url']})
        with build_opener(SeoulRedirectHandler()).open(request,timeout=60) as response:
            payload=response.read(entry['bytes']+1)
        import hashlib
        if len(payload)!=entry['bytes'] or hashlib.sha256(payload).hexdigest()!=entry['sha256']:
            raise ValueError(f'Public source changed or download failed: {entry["id"]}; original bytes were not replaced')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(payload)
        print(f'Downloaded and verified: {entry["path"]}',flush=True)


if __name__=='__main__':
    main()
