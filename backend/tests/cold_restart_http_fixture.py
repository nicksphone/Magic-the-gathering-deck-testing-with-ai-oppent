"""Group-only guarded HTTP bridge, observing the unmodified native lifespan."""
import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

from tests.cold_restart_http_support import facts, file_hash, local_file, sql_hash

ROOT = Path(__file__).resolve().parents[2]
TOKEN = os.environ.get('MTG_PRIVATE_CHOICE_TOKEN', '')
DATA = Path(os.environ['MTG_COLD_RESTART_DATA'])
if (not TOKEN or os.environ.get('MTG_PRIVATE_CHOICE_ROOT') != str(ROOT)
        or os.environ.get('MTG_ISOLATED_TEST_ROOT') != str(ROOT)
        or (ROOT / '.git').exists() or (ROOT / '.private').read_text() != str(ROOT)
        or (ROOT / '.private-choice-audit-source').read_text() != str(ROOT)
        or (ROOT / '.private-choice-owned').read_text() != TOKEN
        or Path(importlib.util.find_spec('main').origin).resolve() != ROOT / 'backend/main.py'):
    raise RuntimeError('Owned source-only local loopback runtime required')
SELECTED = local_file(os.environ['MTG_DATABASE_PATH'])
assert SELECTED.parent == DATA and DATA.resolve() == DATA and not SELECTED.is_relative_to(ROOT)
assert not (ROOT / 'backend/mtg_lab.db').exists() and not (ROOT / 'backend/mtg_lab.db').is_symlink()

import main
from fastapi import HTTPException, Request
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from persistence.capacity import owner_for_engine
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_private_choice_intent_boundary import environment

assert DATABASE_PATH == SELECTED and engine.url.database == str(SELECTED)
app = main.app
LABEL = 'Owned canonical private-choice boundary position; not natural history.'
LAND_LABEL = 'Synthetic canonical land-choice fixture; not a historical game.'
BOOT = None
NATIVE_BOOTSTRAP = main.initialize_resource_capacity


def observed_bootstrap(owner, backup):
    global BOOT
    with owner.mutex:
        owner.require(ready=False)
        before = facts(SELECTED)
        NATIVE_BOOTSTRAP(owner, backup)
        owner.require()
        after = facts(SELECTED)
        BOOT = DATA / f'bootstrap-{os.getpid()}.json'
        BOOT.write_text(json.dumps({'pid': os.getpid(), 'owner_epoch': owner.epoch,
                                    'before': before, 'after': after}))


# Test-only observation, always delegating the real bootstrap under its real owner.
main.initialize_resource_capacity = observed_bootstrap


def authorize(request):
    if request.client.host not in {'127.0.0.1', '::1'} or request.headers.get('X-Private-Choice-Fixture') != TOKEN:
        raise HTTPException(403, 'Owned loopback fixture only')


def owned(identifier):
    controller = main.ACTIVE_MATCHES.get(identifier)
    if controller is None or not any(label in controller.state.log for label in (LABEL, LAND_LABEL)):
        raise HTTPException(404, 'Load the owned match through its actual route first')
    return controller


@app.get('/fixture/private-choice/status')
def status(request: Request):
    authorize(request)
    owner = owner_for_engine(engine)
    assert owner.admissions_open and owner.pid == os.getpid() and owner.path == SELECTED
    assert BOOT is not None
    for name, module in tuple(__import__('sys').modules.items()):
        if name.split('.')[0] in {'ai', 'effects', 'rules_engine', 'game_state', 'card_data', 'persistence', 'knowledge', 'tests', 'decks', 'training', 'scripts'} or name in {'main', 'api_contracts'}:
            origin = getattr(module, '__file__', None)
            if origin:
                assert Path(origin).resolve().is_relative_to(ROOT / 'backend'), (name, origin)
    return {'pid': os.getpid(), 'root': str(ROOT)}


@app.get('/fixture/private-choice/bootstrap')
def bootstrap(request: Request):
    authorize(request)
    return {'pid': os.getpid(), 'path': str(BOOT), 'sha256': file_hash(BOOT)}


@app.get('/fixture/private-choice/database')
def database(request: Request):
    authorize(request)
    owner = owner_for_engine(engine)
    with owner.mutex, owner.activity(threaded=False):
        path = DATA / f'database-{uuid4()}.json'
        path.write_text(json.dumps(facts(SELECTED)))
    return {'path': str(path), 'sha256': file_hash(path)}


@app.get('/fixture/private-choice/{identifier}/audit')
def audit(identifier: str, request: Request):
    authorize(request)
    controller = owned(identifier)
    assert not (ROOT / 'backend/mtg_lab.db').exists() and not (ROOT / 'backend/mtg_lab.db').is_symlink()
    owner = owner_for_engine(engine)
    with owner.mutex, owner.activity(threaded=False):
        stored = facts(SELECTED)
        assert len(stored['ledger']) == 1 and stored['ledger'][0]['owner_epoch'] == owner.epoch
    return {'pid': os.getpid(), 'state': serialize_match_snapshot(controller.state),
            'revision': controller.revision, 'controller': main._controller_snapshot(controller),
            'database_sha256': sql_hash(stored['sql']), 'raw_database_sha256': stored['raw_sha256'],
            'capacity_ledger': stored['ledger']}


@app.get('/fixture/private-choice/{identifier}/observe')
def observe(identifier: str, seat: int, request: Request):
    authorize(request)
    return environment(owned(identifier).state).observe(seat)


@app.post('/fixture/private-choice/{identifier}/intent')
async def intent(identifier: str, seat: int, request: Request):
    authorize(request)
    try:
        return environment(owned(identifier).state).lookup_intent(await request.json(), seat)
    except ActionRejected as exc:
        raise HTTPException(422, str(exc)) from exc


from contextlib import asynccontextmanager
import threading
from persistence import capacity

NATIVE_LIFESPAN = app.router.lifespan_context


@asynccontextmanager
async def observed_lifespan(application):
    try:
        async with NATIVE_LIFESPAN(application):
            yield
    finally:
        row = {'pid': os.getpid(), 'registered_owners': len(capacity._OWNERS),
               'pool_checkedout': engine.pool.checkedout(),
               'threads_at_lifespan_exit': [t.name for t in threading.enumerate() if t is not threading.main_thread()]}
        (DATA / f'closure-{os.getpid()}.json').write_text(json.dumps(row))
        assert row['registered_owners'] == row['pool_checkedout'] == 0


app.router.lifespan_context = observed_lifespan
