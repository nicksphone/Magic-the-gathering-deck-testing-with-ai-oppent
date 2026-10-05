"""Explicit canonical Suspend positions; guarded disposable real App backend."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOKEN = os.environ.get('MTG_SUSPEND_FIXTURE_TOKEN', '')
if (not TOKEN or os.environ.get('MTG_SUSPEND_FIXTURE_ROOT') != str(ROOT)
        or (ROOT / '.git').exists() or not (ROOT / '.suspend-browser-owned').is_file()
        or (ROOT / '.suspend-browser-owned').read_text() != TOKEN
        or Path(importlib.util.find_spec('main').origin).resolve() != ROOT / 'backend/main.py'):
    raise RuntimeError('Suspend fixtures require a runner-owned disposable backend')

import main
from fastapi import HTTPException, Request
from sqlmodel import Session
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from rules_engine.suspend import instruction
from tests.test_suspend_lifecycle import CARDS, DIRECTORY, setup, test_canonical_records_and_supported_parse
from tests.test_ai_recurring_engines import add

assert DATABASE_PATH.resolve() == ROOT / 'backend/mtg_lab.db'
test_canonical_records_and_supported_parse()
app = main.app
LABEL = 'Explicit canonical Suspend UI fixture; controlled upkeep transitions, not a historical game.'
ACTION_LOG = ROOT / 'suspend-ui-actions.jsonl'


@app.middleware('http')
async def observe_actions(request: Request, call_next):
    body = json.loads(await request.body()) if request.method == 'POST' and request.url.path.endswith('/action') else None
    response = await call_next(request)
    if body is not None:
        with ACTION_LOG.open('a') as stream:
            stream.write(json.dumps({'pid': os.getpid(), 'url': request.url.path, 'body': body, 'status': response.status_code})+'\n')
    return response


def authorize(request):
    if request.client.host not in {'127.0.0.1', '::1'} or request.headers.get('X-Suspend-Fixture') != TOKEN:
        raise HTTPException(403, 'Owned loopback fixture only')


def owned(match_id, source_id):
    match = main.ACTIVE_MATCHES.get(match_id)
    if match is None or LABEL not in match.state.log:
        raise HTTPException(404, 'Unknown owned fixture')
    card = match.state.cards.get(source_id)
    if card is None or card.name not in {'Rift Bolt', 'Errant Ephemeron'} or instruction(card) is None:
        raise HTTPException(422, 'Unknown canonical source')
    return match, card


def persist(match):
    with Session(engine) as session:
        main._persist_active_match(Repository(session), match)


def audit(match, card):
    snapshot = serialize_match_snapshot(match.state)
    return {'pid': os.getpid(), 'snapshot': snapshot,
            'snapshot_sha256': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
            'source': snapshot['cards'][card.id], 'revision': match.revision}


@app.get('/fixture/suspend/status')
def status(request: Request):
    authorize(request)
    return {'pid': os.getpid(), 'source_root': str(ROOT), 'canonical_records_verified': True}


@app.post('/fixture/suspend')
def fixture(request: Request, seat: int = 1, scenario: str = 'rift-cast'):
    authorize(request)
    if seat not in (1, 2) or scenario not in {'rift-cast', 'creature-cast', 'no-target', 'decline', 'unpayable'}:
        raise HTTPException(422, 'Unknown bounded canonical scenario/seat')
    name = 'Errant Ephemeron' if scenario == 'creature-cast' else 'Rift Bolt'
    state, cid = setup(seat, name)
    state.players[seat].mana_pool = {'U': 1, 'C': 1} if name == 'Errant Ephemeron' else {'R': 1}
    if scenario == 'unpayable':
        state.players[seat].mana_pool.clear()
    if scenario == 'no-target':
        for owner in (1, 2):
            add(state, 'Ivory Mask', owner, cards=CARDS)
    state.log.append(LABEL)
    deck = [{'card_name': 'Swamp', 'quantity': 60}]
    match = main.MatchController(state=state, rules=RulesEngine(), controllers={1: 'human', 2: 'human'},
        ai={1: AIAgent(), 2: AIAgent()}, mode='human_vs_human', deck_ids=(None, None),
        mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []}, game_number=1,
        current_game_recorded=False, match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = match
    persist(match)
    return {'match': main.get_match(state.id), 'source_id': cid, 'name': name,
            'cost': instruction(state.cards[cid])[1], 'time_counters': instruction(state.cards[cid])[0],
            'provenance': json.loads((DIRECTORY / 'provenance.json').read_text()), 'fixture_label': LABEL}


@app.get('/fixture/suspend/{match_id}/audit')
def read_audit(match_id: str, source_id: str, request: Request):
    authorize(request)
    return audit(*owned(match_id, source_id))


@app.post('/fixture/suspend/{match_id}/upkeep')
def upkeep(match_id: str, source_id: str, request: Request):
    authorize(request)
    match, card = owned(match_id, source_id)
    with match.mutation_lock:
        state = match.state
        if (card.zone != Zone.EXILE or card.counters.get('time', 0) <= 0 or state.stack
                or state.pending_mechanic_choice or state.pending_trigger_order or state.pending_replacement_choice):
            raise HTTPException(422, 'Explicit upkeep fixture requires an idle suspended card')
        state.active_player = state.priority_player = card.owner
        state.step = Step.UPKEEP
        state.passed_priority.clear()
        state.log.append('Explicit fixture transition to next owner upkeep, not played intervening turns.')
        match.rules._apply_step_start_actions(state)
        match.revision += 1
        persist(match)
        return audit(match, card)


@app.post('/fixture/suspend/{match_id}/restore')
def restore(match_id: str, source_id: str, request: Request):
    authorize(request)
    match, card = owned(match_id, source_id)
    with match.mutation_lock:
        before = audit(match, card)['snapshot_sha256']
        persist(match)
        main.ACTIVE_MATCHES.pop(match_id)
        with Session(engine) as session:
            main._restore_active_matches(Repository(session), match_id)
        restored = audit(*owned(match_id, source_id))
        assert restored['snapshot_sha256'] == before
        return restored


@app.get('/fixture/suspend/actions')
def actions(request: Request, match_id: str):
    authorize(request)
    rows = [json.loads(line) for line in ACTION_LOG.read_text().splitlines()] if ACTION_LOG.exists() else []
    return [row for row in rows if row['url'] == f'/matches/{match_id}/action']
