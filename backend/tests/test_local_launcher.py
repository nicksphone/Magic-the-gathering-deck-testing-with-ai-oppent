"""Launcher/file/lifespan contracts; no live app DB, sockets or browser."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import subprocess

import pytest
from starlette.applications import Starlette

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts/start-local.sh'


def test_launcher_executes_one_loopback_factory_worker(tmp_path):
    # A disposable script copy gets an owned built-dist fixture, not developer assets.
    root=tmp_path/'source'; (root/'scripts').mkdir(parents=True); (root/'backend').mkdir()
    (root/'frontend/dist').mkdir(parents=True); (root/'frontend/dist/index.html').write_text('<html>built</html>')
    script=root/'scripts/start-local.sh'; script.write_bytes(SCRIPT.read_bytes())
    fake=tmp_path/'python'; record=tmp_path/'argv.json'
    fake.write_text('#!'+os.sys.executable+'\nimport json,os,sys\nopen(os.environ["LAUNCH_RECORD"],"w").write(json.dumps({"argv":sys.argv[1:],"origin":os.environ["MTG_TRUSTED_ORIGINS"],"cwd":os.getcwd(),"uvicorn_env":[k for k in os.environ if k.startswith("UVICORN_")]}))\n')
    fake.chmod(0o700)
    result=subprocess.run(['bash',str(script)],env={**os.environ,'MTG_LOCAL_PYTHON':str(fake),'LAUNCH_RECORD':str(record),'WEB_CONCURRENCY':'8','UVICORN_RELOAD':'1','UVICORN_LIFESPAN':'off'},capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    row=json.loads(record.read_text()); args=row['argv']
    assert args[:4]==['-m','uvicorn','local_web:create_app','--factory']
    assert args[args.index('--workers')+1]=='1' and args[args.index('--host')+1]=='127.0.0.1'
    assert '--reload' not in args and row['origin']=='http://127.0.0.1:5173'
    assert row['uvicorn_env']==[] and args[args.index('--lifespan')+1]=='on'
    assert Path(row['cwd'])==root/'backend'


@pytest.mark.parametrize('port',['80','65536','0','not-a-port'])
def test_launcher_rejects_bad_port_before_start(port):
    result=subprocess.run(['bash',str(SCRIPT)],env={**os.environ,'MTG_LOCAL_PORT':port},capture_output=True,text=True,timeout=10)
    assert result.returncode==2 and 'port' in result.stderr.lower()


def test_combined_app_routes_and_delegates_lifespan(tmp_path):
    from local_web import build_app
    dist=tmp_path/'dist';dist.mkdir();(dist/'index.html').write_text('<html>built</html>')
    images=tmp_path/'images';images.mkdir();events=[]
    @asynccontextmanager
    async def lifespan(app):
        events.append('start');yield;events.append('stop')
    api=Starlette(lifespan=lifespan)
    app=build_app(api,dist,images)
    assert [r.path for r in app.routes]==['/api','/card-images','']
    assert app.routes[0].app is api
    async def enter():
        async with app.router.lifespan_context(app):assert events==['start']
    asyncio.run(enter())
    assert events==['start','stop']


def test_missing_or_symlinked_build_refuses(tmp_path):
    from local_web import build_app
    images=tmp_path/'images';images.mkdir();dist=tmp_path/'dist';dist.mkdir()
    with pytest.raises(ValueError,match='build'):build_app(Starlette(),dist,images)
    (dist/'index.html').write_text('built');alias=tmp_path/'alias';alias.symlink_to(dist,target_is_directory=True)
    with pytest.raises(ValueError,match='build'):build_app(Starlette(),alias,images)
