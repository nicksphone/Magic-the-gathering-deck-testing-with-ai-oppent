"""Owned canonical human-flow positions; never a production or historical fixture."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
TOKEN = os.environ.get('MTG_HUMAN_FLOW_TOKEN', '')
if (not TOKEN or os.environ.get('MTG_HUMAN_FLOW_ROOT') != str(ROOT)
        or (ROOT / '.git').exists() or not (ROOT / '.human-flow-owned').is_file()
        or (ROOT / '.human-flow-owned').read_text() != TOKEN
        or Path(importlib.util.find_spec('main').origin).resolve() != ROOT / 'backend/main.py'):
    raise RuntimeError('Human-flow fixtures require runner-owned disposable source')

import main
from fastapi import HTTPException, Request
from sqlmodel import Session
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from tests.test_spell_cost_overlap_investigation import ROWS, position, add

DIRECTORY = ROOT / 'backend/tests/fixtures/human_flow_audit'
RAW = json.loads((DIRECTORY / 'canonical.json').read_text())
PROVENANCE = json.loads((DIRECTORY / 'provenance.json').read_text())
assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == PROVENANCE['canonical_json_sha256']
assert not PROVENANCE['facts_modified'] and PROVENANCE['http_requests'] == 0
for name, pin in PROVENANCE['rows'].items():
    assert RAW[name]['id'] == pin['id'] and RAW[name]['oracle_id'] == pin['oracle_id']
ROWS.update(RAW)  # Test helper records only; raw canonical fields stay unchanged.
assert DATABASE_PATH.resolve() == ROOT / 'backend/mtg_lab.db'
app = main.app
LABEL = 'Explicit canonical human-flow audit; not a historical game.'
ACTION_LOG = ROOT / 'human-flow-actions.jsonl'


@app.middleware('http')
async def observe(request: Request, call_next):
    body = json.loads(await request.body()) if request.method == 'POST' and request.url.path.endswith('/action') else None
    response = await call_next(request)
    if body is not None:
        with ACTION_LOG.open('a') as stream:
            stream.write(json.dumps({'pid': os.getpid(), 'url': request.url.path,
                                    'body': body, 'status': response.status_code,
                                    'revision_header': request.headers.get('X-Match-Revision')}) + '\n')
    return response


def authorize(request):
    if request.client.host not in {'127.0.0.1', '::1'} or request.headers.get('X-Human-Flow-Fixture') != TOKEN:
        raise HTTPException(403, 'Owned loopback fixture only')


def owned(identifier):
    match = main.ACTIVE_MATCHES.get(identifier)
    if match is None or LABEL not in match.state.log:
        raise HTTPException(404, 'Unknown owned human-flow fixture')
    return match


@app.get('/fixture/human-flow/status')
def status(request: Request):
    authorize(request)
    return {'pid': os.getpid(), 'source_root': str(ROOT), 'canonical_provenance': PROVENANCE}


@app.post('/fixture/human-flow')
def fixture(request: Request, seat: int = 1, scenario: str = 'shark-cycle-only'):
    authorize(request)
    if seat not in (1, 2) or scenario not in {
            'shark-cycle-only', 'shark-castable', 'renewed-accept', 'renewed-decline',
            'renewed-cast', 'hangarback', 'stale-shark', 'creature-control'}:
        raise HTTPException(422, 'Declared human-flow scenario required')
    state = position(seat)
    state.id = str(uuid4())
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = dict.fromkeys('WUBRGC', 0)
    foreign = add(state, 'Grizzly Bears', 3-seat, Zone.HAND)
    draw = add(state, 'Island', seat, Zone.LIBRARY)
    add(state, 'Forest', seat, Zone.LIBRARY)
    victim = None
    if 'shark' in scenario:
        source = add(state, 'Shark Typhoon', seat, Zone.HAND)
        state.players[seat].mana_pool.update(U=1, C=5 if scenario == 'shark-castable' else 3)
    elif scenario.startswith('renewed'):
        source = add(state, 'Renewed Faith', seat, Zone.HAND)
        state.players[seat].mana_pool.update(W=1, C=2 if scenario == 'renewed-cast' else 1)
    elif scenario == 'creature-control':
        source = add(state, 'Grizzly Bears', seat, Zone.HAND)
        state.players[seat].mana_pool.update(G=1, C=1)
    else:
        source = add(state, 'Phyrexian Tower', seat)
        victim = add(state, 'Hangarback Walker', seat)
        anthem = add(state, 'Glorious Anthem', seat)
        for card in (source, victim, anthem):
            assign_static_order_on_battlefield_entry(state, card.id)
        victim.counters['+1/+1'] = 2
    state.log.append(LABEL)
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    match = main.MatchController(state=state, rules=RulesEngine(), controllers={1: 'human', 2: 'human'},
        ai={1: AIAgent(), 2: AIAgent()}, mode='human_vs_human', deck_ids=(None, None),
        mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []}, game_number=1,
        current_game_recorded=False, match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = match
    with Session(engine) as session:
        main._persist_active_match(Repository(session), match)
    return {'match': main.get_match(state.id), 'source_id': source.id,
            'victim_id': victim.id if victim else None, 'foreign_hand_id': foreign.id,
            'initial_library_ids': list(state.players[seat].library), 'label': LABEL}


@app.get('/fixture/human-flow/{identifier}/audit')
def audit(identifier: str, request: Request):
    authorize(request)
    match = owned(identifier)
    snapshot = serialize_match_snapshot(match.state)
    return {'pid': os.getpid(), 'snapshot': snapshot, 'revision': match.revision,
            'snapshot_sha256': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()}


@app.get('/fixture/human-flow/actions')
def actions(request: Request, match_id: str):
    authorize(request)
    rows = [json.loads(line) for line in ACTION_LOG.read_text().splitlines()] if ACTION_LOG.exists() else []
    return [row for row in rows if row['url'] == f'/matches/{match_id}/action']
