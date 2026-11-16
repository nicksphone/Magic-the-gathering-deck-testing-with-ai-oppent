"""Owned file-lock enforcement and inert launcher contracts, not LAN/TLS proof."""
import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest
from sqlmodel import create_engine

from persistence.capacity import DatabaseOwner
from tests.temporary_characteristics_http_fixture import owned_database, source_default_identity

ROOT = Path(__file__).resolve().parents[2]


def test_second_process_cannot_own_same_database_until_first_releases(tmp_path):
    before_default = source_default_identity()
    database = tmp_path/'owned.sqlite3'
    engine = create_engine('sqlite:///'+str(database))
    with owned_database(engine) as owner:
        before = database.read_bytes()
        lock_identity = owner.lock_path.stat()
        code = '''from pathlib import Path
import sys
from sqlmodel import create_engine
from persistence.capacity import DatabaseOwner
engine=create_engine('sqlite:///'+sys.argv[1])
try:
    owner=DatabaseOwner(engine).acquire()
except BlockingIOError:
    print('BLOCKED')
else:
    owner.close()
    raise SystemExit(8)
'''
        result = subprocess.run([sys.executable,'-B','-c',code,str(database)],
                                cwd=ROOT/'backend',capture_output=True,text=True,timeout=15)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == 'BLOCKED'
        owner.require()
        assert database.read_bytes() == before
        current = owner.lock_path.stat()
        assert (current.st_dev,current.st_ino) == (lock_identity.st_dev,lock_identity.st_ino)
    # Persistent lock files are not stale by age/PID; release the lock, don't delete it.
    assert owner.lock_path.exists()
    new_engine = create_engine('sqlite:///'+str(database))
    successor = DatabaseOwner(new_engine).acquire()
    successor.require(ready=False)
    successor.close()
    assert source_default_identity() == before_default


def test_default_operator_command_fixes_one_loopback_worker():
    tree = ast.parse((ROOT/'ops/caddy/run.py').read_text())
    commands = [n.value for n in ast.walk(tree) if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='command' for t in n.targets)
                and isinstance(n.value,ast.List)
                and any(isinstance(v,ast.Constant) and v.value=='uvicorn' for v in n.value.elts)]
    assert len(commands) == 1
    command = eval(compile(ast.Expression(commands[0]),'<operator command>','eval'),
                   {'str':str,'config':{'python':'python','backend_port':18444}})
    assert command.count('--workers') == 1 and command[command.index('--workers')+1] == '1'
    assert command[command.index('--host')+1] == '127.0.0.1'
    assert '--reload' not in command


@pytest.mark.parametrize('concurrency',['1','8'])
def test_learned_operator_ignores_worker_environment(monkeypatch,concurrency):
    spec = importlib.util.spec_from_file_location('single_operator_entry',ROOT/'backend/operator_start.py')
    entry = importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
    monkeypatch.setenv('WEB_CONCURRENCY',concurrency)
    monkeypatch.setenv('UVICORN_WORKERS',concurrency)
    app = ModuleType('main'); app.app=object(); app.configure_new_match_policy=lambda binding:None
    uvicorn = ModuleType('uvicorn'); calls=[]; uvicorn.run=lambda *args,**kw:calls.append((args,kw))
    monkeypatch.setitem(sys.modules,'main',app); monkeypatch.setitem(sys.modules,'uvicorn',uvicorn)
    monkeypatch.setattr(entry,'load_binding',lambda *a:object())
    assert entry.main(['--checkpoint','/not-opened','--checkpoint-sha256','a'*64,'--host','127.0.0.1','--port','18444']) == 0
    assert len(calls)==1 and calls[0][1]['workers']==1 and calls[0][1]['host']=='127.0.0.1'
    assert calls[0][1].get('reload',False) is False


def test_packaged_proxy_has_one_auth_identity_before_all_routes():
    text=(ROOT/'ops/caddy/Caddyfile').read_text()
    assert text.count('basic_auth {')==1
    # Environment substitutions contain braces, so check the complete auth block.
    assert 'basic_auth {\n\t\t\t{env.MTG_AUTH_USER} {env.MTG_AUTH_HASH}\n\t\t}' in text
    assert text.index('basic_auth {') < text.index('handle_path /api/*') < text.index('file_server')
