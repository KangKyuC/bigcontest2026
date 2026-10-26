"""Check the published scenario snapshot independently of the private pipeline."""
import json
import hashlib
from urllib.parse import urlsplit

from paths import DASHBOARD


def load(name):
    return json.loads((DASHBOARD/'public/data'/name).read_text(encoding='utf-8'))


def test_snapshot_matches_published_file_fingerprints():
    manifest=json.loads((DASHBOARD/'snapshot-manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():
        payload=(DASHBOARD/'public/data'/name).read_bytes()
        assert len(payload)==expected['bytes']
        assert hashlib.sha256(payload).hexdigest()==expected['sha256']


def test_summaries_details_and_policy_counts_agree():
    agent=load('agent.json')
    people=load('personas.json')
    policy=load('policy.json')
    assert {p['id'] for p in agent['personas']}==set(people)
    assert len(people)==75
    assert sum(p['kind']=='rep' for p in people.values())==5
    for region,value in agent['regions'].items():
        regional={p['id'] for p in people.values() if p['region']==region}
        assert sum(people[id]['kind']=='dong' for id in regional)==value['scan']['found']
        for rec in policy[region]['recs']:
            assert set(rec['personas'])<=regional
            assert rec['count']==len(rec['personas'])==len(set(rec['personas']))


def test_snapshot_has_no_raw_measurements_or_personal_credentials():
    forbidden={'contact_seoul_peer_percentile','flow_per_point','flow_concentration',
               'resident_id','phone_number','api_key','access_token','password'}
    def walk(value):
        if isinstance(value,dict):
            assert not forbidden.intersection(value)
            for key,item in value.items():
                if key in ('source','url') and isinstance(item,str) and item:
                    parsed=urlsplit(item)
                    # Evidence source labels are plain Korean text; web links have a scheme.
                    if parsed.scheme:
                        assert parsed.scheme in ('https','http') and parsed.hostname
                        assert not parsed.username and not parsed.password
                walk(item)
        elif isinstance(value,list):
            for item in value:
                walk(item)
    for name in ['agent.json','personas.json','policy.json']:
        walk(load(name))


def test_risk_levels_are_explicit_scenario_rules():
    agent=load('agent.json')
    assert '가상' in agent['notice'] and '실제 주민 수' in agent['notice']
    assert all(p['level'] in (1,2,3,4) for p in load('personas.json').values())
    assert '연락·외출 예측' not in json.dumps(load('personas.json'),ensure_ascii=False)
