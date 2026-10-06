"""Owned loopback HTTP bridge; paid path and handler-only slice stay distinct."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
TOKEN = os.environ.get('MTG_PRIVATE_CHOICE_TOKEN', '')
if (not TOKEN or os.environ.get('MTG_PRIVATE_CHOICE_ROOT') != str(ROOT)
        or (ROOT / '.git').exists() or not (ROOT / '.private-choice-owned').is_file()
        or (ROOT / '.private-choice-owned').read_text() != TOKEN
        or Path(importlib.util.find_spec('main').origin).resolve() != ROOT / 'backend/main.py'):
    raise RuntimeError('Owned source-only local loopback runtime required')
if subprocess.check_output(['stat', '-f', '-c', '%T', str(ROOT)], text=True).strip().startswith('nfs'):
    raise RuntimeError('SQLite runtime must be local, never NFS')

import main
from fastapi import HTTPException, Request
from sqlmodel import Session
from ai.agent import AIAgent
from effects.handlers import put_land_from_hand
from game_state.serializers import serialize_match_snapshot
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from tests.test_optional_land_from_hand_audit import setup

assert DATABASE_PATH.resolve() == ROOT / 'backend/mtg_lab.db'
app = main.app
LABEL = 'Synthetic canonical land-choice fixture; not a historical game.'


def authorize(request):
    if request.client.host not in {'127.0.0.1', '::1'} or request.headers.get('X-Private-Choice-Fixture') != TOKEN:
        raise HTTPException(403, 'Owned loopback fixture only')


@app.get('/fixture/private-choice/status')
def status(request: Request):
    authorize(request)
    return {'pid': os.getpid(), 'root': str(ROOT)}


@app.post('/fixture/private-choice')
def fixture(request: Request, family: str, seat: int, slice_only: bool = False):
    authorize(request)
    if family not in {'Growth Spiral', 'Arboreal Grazer'} or seat not in (1, 2):
        raise HTTPException(422, 'Declared canonical family and seat required')
    state, source, land, drawn = setup(family, seat)
    state.id = str(uuid4())
    state.log.append(LABEL)
    if slice_only:
        # Lower-level handler fixture ONLY; never claim this executed a card.
        put_land_from_hand(state, seat, {'optional': True, 'tapped': family == 'Arboreal Grazer'})
        state.log.append('Handler-slice setup; spell compiler is not exercised.')
    controller = main.MatchController(state=state, rules=RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={1: AIAgent(), 2: AIAgent()},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: [], 2: []},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(engine) as session:
        main._persist_active_match(Repository(session), controller)
    return {'id': state.id, 'source_id': source.id, 'land_id': land.id,
            'drawn_id': drawn, 'slice_only': slice_only}


@app.get('/fixture/private-choice/{identifier}/audit')
def audit(identifier: str, request: Request):
    authorize(request)
    controller = main.ACTIVE_MATCHES.get(identifier)
    if controller is None or LABEL not in controller.state.log:
        raise HTTPException(404, 'Load the owned match through its actual route first')
    with sqlite3.connect(DATABASE_PATH) as connection:
        database = '\n'.join(connection.iterdump())
    return {'pid': os.getpid(), 'state': serialize_match_snapshot(controller.state),
            'revision': controller.revision, 'controller': main._controller_snapshot(controller),
            'database_sha256': hashlib.sha256(database.encode()).hexdigest()}
