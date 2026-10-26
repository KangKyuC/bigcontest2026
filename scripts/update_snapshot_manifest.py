"""Record the exact public dashboard snapshot without adding research inputs."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DASHBOARD=ROOT/'dashboard'


def main():
    files={}
    for name in ('agent.json','personas.json','policy.json'):
        payload=(DASHBOARD/'public/data'/name).read_bytes()
        files[name]={'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
    manifest={
        'version':1,
        'source_commit':'eced6914ee60d67ee769be536b2699b3ad838dde',
        'source_branch':'feat/dashboard',
        'research_snapshot_date':'2026-10-26',
        'publication_changes':'Observation labels corrected; numeric scenario outputs preserved.',
        'personas':{'total':75,'representative':5,'dong':70},
        'programs':{'gangnam':37,'chuncheon':17},
        'files':files,
        'scope':'Fictional scenarios and aggregate descriptions; no individual records, raw competition data or model binaries.',
    }
    (DASHBOARD/'snapshot-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Dashboard snapshot manifest updated.')


if __name__=='__main__':
    main()
