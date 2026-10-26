"""Security regressions use a temporary public build and no research inputs."""
from http.client import HTTPConnection
import json
import threading
from unittest.mock import patch

import pytest
import dashboard_server as s


@pytest.fixture(scope='module')
def local_server(tmp_path_factory):
    directory=tmp_path_factory.mktemp('public-build')
    (directory/'dist').mkdir()
    (directory/'dist/index.html').write_text('public screen',encoding='utf-8')
    (directory/'secret.json').write_text('must never be served',encoding='utf-8')
    with patch.object(s,'load_data',return_value={}),patch.object(s,'DASHBOARD',directory):
        server=s.make_server(port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def request(server,method='GET',path='/',body=None,headers=None):
    connection=HTTPConnection('127.0.0.1',server.server_port,timeout=3)
    connection.request(method,path,body=body,headers=headers or {})
    response=connection.getresponse()
    result=response.status,dict(response.getheaders()),response.read()
    connection.close()
    return result


def test_public_interface_binding_is_refused():
    with pytest.raises(ValueError):
        s.make_server('0.0.0.0',0)


def test_dns_rebinding_host_is_refused(local_server):
    assert request(local_server,headers={'Host':'attacker.example'})[0]==403
    assert request(local_server,headers={'Host':f'localhost:{local_server.server_port}'})[0]==200


def test_cross_origin_read_and_write_are_refused(local_server):
    for method,path in [('GET','/'),('POST','/api/persona-check')]:
        assert request(local_server,method,path,headers={'Origin':'https://attacker.example'})[0]==403


def test_static_paths_cannot_read_outside_build(local_server):
    assert request(local_server,path='/assets/../../secret.json')[0]==404
    status,headers,body=request(local_server)
    assert status==200 and body==b'public screen'
    assert headers['X-Content-Type-Options']=='nosniff'
    assert headers['X-Frame-Options']=='DENY'


def test_json_request_sizes_and_framing_are_checked(local_server):
    path='/api/persona-check'
    assert request(local_server,'POST',path,body='{}',headers={'Content-Type':'text/plain'})[0]==415
    assert request(local_server,'POST',path,headers={'Content-Type':'application/json','Content-Length':'65537'})[0]==413
    assert request(local_server,'POST',path,body='{}',headers={'Content-Type':'application/json','Transfer-Encoding':'chunked'})[0]==400
    assert request(local_server,'POST',path,body='{',headers={'Content-Type':'application/json'})[0]==400
    with patch.object(s,'persona_check',return_value={'accepted':True}):
        status,_,body=request(local_server,'POST',path,body='{}',headers={'Content-Type':'application/json'})
        assert status==200 and json.loads(body)=={'accepted':True}
