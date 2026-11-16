"""Real ASGI routing/static responses with an inert API, never application SQL."""
from contextlib import asynccontextmanager

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from local_web import build_app


@pytest.fixture
def client(tmp_path):
    dist=tmp_path/'dist';(dist/'assets').mkdir(parents=True)
    (dist/'index.html').write_text('<html>built frontend</html>')
    (dist/'assets/app.js').write_text('console.log("built")')
    (dist/'.env').write_text('not served')
    images=tmp_path/'images';images.mkdir();(images/'token.svg').write_text('<svg></svg>')
    events=[]
    @asynccontextmanager
    async def lifespan(api):
        events.append('start');yield;events.append('stop')
    async def health(request):
        return JSONResponse({'ok':True,'root_path':request.scope['root_path']})
    async def echo(request):
        return JSONResponse(await request.json())
    api=Starlette(routes=[Route('/health',health),Route('/echo',echo,methods=['POST'])],lifespan=lifespan)
    with TestClient(build_app(api,dist,images)) as value:
        assert events==['start']
        yield value
    assert events==['start','stop']


@pytest.mark.parametrize('path,accept,status,body',[
    ('/','text/html',200,'built frontend'),
    ('/assets/app.js','*/*',200,'console.log'),
    ('/matches/fixture','text/html',200,'built frontend'),
    ('/assets/missing.js','text/html',404,None),
    ('/.env','text/html',404,None),
    ('/api/missing','text/html',404,None),
])
def test_static_navigation_and_reserved_paths(client,path,accept,status,body):
    response=client.get(path,headers={'Accept':accept})
    assert response.status_code==status
    if body:assert body in response.text
    else:assert 'built frontend' not in response.text and 'not served' not in response.text


def test_api_get_and_post_preserve_prefix_and_body(client):
    assert client.get('/api/health').json()=={'ok':True,'root_path':'/api'}
    assert client.post('/api/echo',json={'action':'fixture'}).json()=={'action':'fixture'}


def test_media_has_own_route(client):
    response=client.get('/card-images/token.svg')
    assert response.status_code==200 and response.text=='<svg></svg>'
    assert 'image/svg+xml' in response.headers['content-type']
