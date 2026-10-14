"""NEW guarded test bridge; production action/restore routes stay unchanged."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
TOKEN = os.environ.get('MTG_PRIVATE_CHOICE_TOKEN', '')
if (not TOKEN or os.environ.get('MTG_PRIVATE_CHOICE_ROOT') != str(ROOT)
        or (ROOT / '.git').exists() or not (ROOT / '.private-choice-owned').is_file()
        or (ROOT / '.private-choice-owned').read_text() != TOKEN
        or Path(importlib.util.find_spec('main').origin).resolve() != ROOT / 'backend/main.py'):
    raise RuntimeError('Use owned source-only local test runtime')

import main
from fastapi import HTTPException, Request
from sqlmodel import Session
from ai.agent import AIAgent
from persistence.db import DATABASE_PATH, engine
from persistence.capacity import owner_for_engine
from persistence.repository import Repository
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_private_choice_intent_boundary import position, environment

assert DATABASE_PATH.resolve() == ROOT / 'backend/mtg_lab.db'
app = main.app
LABEL = 'Owned canonical private-choice boundary position; not natural history.'


def authorize(request):
    if request.client.host not in {'127.0.0.1', '::1'} or request.headers.get('X-Private-Choice-Fixture') != TOKEN:
        raise HTTPException(403, 'Owned loopback fixture only')


def owned(identifier):
    controller = main.ACTIVE_MATCHES.get(identifier)
    if controller is None or LABEL not in controller.state.log:
        raise HTTPException(404, 'Unknown owned choice fixture')
    return controller


@app.get('/fixture/private-choice/status')
def status(request: Request):
    authorize(request)
    return {'pid': os.getpid(), 'root': str(ROOT)}


@app.post('/fixture/private-choice')
def fixture(request: Request, family: str, seat: int):
    authorize(request)
    if family not in {'delver', 'officer'} or seat not in (1, 2):
        raise HTTPException(422, 'Declared canonical family and actor required')
    state, inspected, foreign = position(family, seat)
    if family == 'officer':
        state.id = str(uuid4())
    state.log.append(LABEL)
    controller = main.MatchController(state=state, rules=RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={1: AIAgent(), 2: AIAgent()},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: [], 2: []},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(engine) as session:
        main._persist_active_match(Repository(session), controller)
    return {'id': state.id, 'inspected_ids': inspected, 'foreign_hand_id': foreign}


def restart_stable_sql_fingerprint(rows, ledger, epoch):
    """Normalize only the source-bound current epoch cell, retaining all other SQL."""
    columns = ('id', 'version', 'durable_bytes', 'snapshot_rows', 'reserved_bytes',
               'reserved_snapshot_rows', 'owner_epoch')
    assert type(rows) is list and all(type(row) is str for row in rows)
    assert type(ledger) is dict and set(ledger) == set(columns)
    assert type(epoch) is str and len(epoch) == 32 and all(c in '0123456789abcdef' for c in epoch)
    assert type(ledger['owner_epoch']) is str and ledger['owner_epoch'] == epoch
    assert all(type(ledger[key]) is int and ledger[key] >= 0 for key in columns[:-1])
    assert ledger['id'] == ledger['version'] == 1
    values = ','.join(str(ledger[key]) for key in columns[:-1])
    literal = "'" + epoch + "'"
    expected = 'INSERT INTO "resourcecapacity" VALUES(' + values + ',' + literal + ');'
    capacity_rows = [row for row in rows if row.startswith('INSERT INTO "resourcecapacity"')]
    assert capacity_rows == [expected], 'Dump must bind the complete unique current capacity row'
    canonical = [row.replace(literal, "'<resourcecapacity.owner_epoch>'", 1) if row == expected else row
                 for row in rows]
    return hashlib.sha256('\n'.join(canonical).encode()).hexdigest()


@app.get('/fixture/private-choice/{identifier}/audit')
def audit(identifier: str, request: Request):
    authorize(request)
    controller = owned(identifier)
    state = serialize_match_snapshot(controller.state)
    owner = owner_for_engine(engine)
    assert owner.pid == os.getpid() and owner.path == DATABASE_PATH.resolve()
    with owner.mutex, owner.activity(threaded=False):
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            ledger = [dict(row) for row in connection.execute('SELECT * FROM resourcecapacity')]
            assert len(ledger) == 1
            rows = list(connection.iterdump())
        stable_hash = restart_stable_sql_fingerprint(rows, ledger[0], owner.epoch)
        epoch = owner.epoch
    sql = '\n'.join(rows)
    return {'pid': os.getpid(), 'state': state, 'revision': controller.revision,
            'controller': main._controller_snapshot(controller),
            'database_sha256': hashlib.sha256(sql.encode()).hexdigest(),
            'restart_stable_database_sha256': stable_hash,
            'capacity_owner_epoch': epoch, 'capacity_ledger': ledger[0]}


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
