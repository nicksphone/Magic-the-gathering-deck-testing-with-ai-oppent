"""Fixed owned read-only child: actual cold ASGI GET, without app lifespan."""
import json
import os
from pathlib import Path
import sys

# The archived launcher used to supply these protections before importing main.
database = Path(os.environ.get('MTG_DATABASE_PATH', Path(__file__).parents[1] / 'mtg_lab.db')).resolve()


def require_readonly_database(value):
    value = str(value)
    if not value.startswith('file:') or '?' not in value:
        raise RuntimeError('Cold worker requires an explicit read-only SQLite URI')
    filename, query = value[5:].split('?', 1)
    path = Path(filename)
    if not path.is_absolute() or path.resolve() != path or path != database:
        raise RuntimeError('Cold worker cannot access a foreign SQLite path')
    parameters = query.split('&')
    if parameters.count('mode=ro') != 1 or any(part not in {'mode=ro', 'uri=true'} for part in parameters):
        raise RuntimeError('Cold worker cannot write SQLite')


def audit(event, args):
    if event == 'sqlite3.connect':
        require_readonly_database(args[0])
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo', 'socket.sendto',
                 'socket.sendmsg', 'socket.gethostbyname', 'socket.gethostbyaddr',
                 'socket.getnameinfo', 'subprocess.Popen',
                 'os.system', 'os.posix_spawn', 'os.exec', 'os.fork', 'os.forkpty'}:
        raise RuntimeError('Cold worker cannot use network or launch another process')


sys.addaudithook(audit)
import sqlite3
import sqlite3.dbapi2
import _sqlite3

native_connect = sqlite3.connect


def readonly_connect(value, *args, **kwargs):
    require_readonly_database(value)
    if kwargs.get('uri') is not True:
        raise RuntimeError('Cold worker requires uri=True')
    return native_connect(value, *args, **kwargs)


for module in (sqlite3, sqlite3.dbapi2, _sqlite3):
    module.connect = readonly_connect

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

import main
from game_state.serializers import serialize_match_snapshot
from persistence.db import DATABASE_PATH
from persistence.repository import Repository

assert DATABASE_PATH.resolve() == database
assert not main.ACTIVE_MATCHES
engine = create_engine('sqlite:///file:' + str(DATABASE_PATH) + '?mode=ro&uri=true')
main.engine = engine
def repo():
    with Session(engine) as session:
        yield Repository(session)
main.app.dependency_overrides[main.get_repo] = repo
client = TestClient(main.app, raise_server_exceptions=True)
try:
    result = client.get('/matches/' + sys.argv[-1])
    assert result.status_code == 200, result.text
    match = main.ACTIVE_MATCHES[sys.argv[-1]]
    print(json.dumps({'view': result.json(), 'snapshot': serialize_match_snapshot(match.state),
                      'controller': main._controller_snapshot(match)}))
finally:
    client.close()
    main.app.dependency_overrides.clear()
    engine.dispose()
