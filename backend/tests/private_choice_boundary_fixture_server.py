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


@app.get('/fixture/private-choice/{identifier}/audit')
def audit(identifier: str, request: Request):
    authorize(request)
    controller = owned(identifier)
    state = serialize_match_snapshot(controller.state)
    with sqlite3.connect(DATABASE_PATH) as connection:
        sql = '\n'.join(connection.iterdump())
    return {'pid': os.getpid(), 'state': state, 'revision': controller.revision,
            'controller': main._controller_snapshot(controller),
            'database_sha256': hashlib.sha256(sql.encode()).hexdigest()}


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
