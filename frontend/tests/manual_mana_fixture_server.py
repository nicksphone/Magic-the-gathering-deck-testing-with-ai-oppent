"""Explicit source-grounded manual mana positions, isolated real HTTP/App only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
TOKEN = os.environ.get('MTG_MANA_FIXTURE_TOKEN', '')
if (not TOKEN or os.environ.get('MTG_MANA_FIXTURE_ROOT') != str(ROOT)
        or (ROOT / '.git').exists() or not (ROOT / '.mana-browser-owned').is_file()
        or (ROOT / '.mana-browser-owned').read_text() != TOKEN
        or Path(importlib.util.find_spec('main').origin).resolve() != ROOT / 'backend/main.py'):
    raise RuntimeError('Manual mana fixtures require a runner-owned disposable backend')

import main
from fastapi import HTTPException, Request
from sqlmodel import Session
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from tests.test_mana_executor_choices import ROWS, position, add
from tests.test_mandatory_base_vectors import ROWS as VECTOR_ROWS

assert DATABASE_PATH.resolve() == ROOT / 'backend/mtg_lab.db'
app = main.app
LABEL = 'Explicit canonical mana UI position; not a historical game.'
ACTION_LOG = ROOT / 'manual-mana-actions.jsonl'


@app.middleware('http')
async def observe(request: Request, call_next):
    body = json.loads(await request.body()) if request.method == 'POST' and request.url.path.endswith('/action') else None
    response = await call_next(request)
    if body is not None:
        with ACTION_LOG.open('a') as stream:
            stream.write(json.dumps({'pid': os.getpid(), 'url': request.url.path, 'body': body, 'status': response.status_code})+'\n')
    return response


def authorize(request):
    if request.client.host not in {'127.0.0.1', '::1'} or request.headers.get('X-Mana-Fixture') != TOKEN:
        raise HTTPException(403, 'Owned loopback fixture only')


def persist(match):
    with Session(engine) as session:
        main._persist_active_match(Repository(session), match)


def owned(identifier):
    match = main.ACTIVE_MATCHES.get(identifier)
    if match is None or LABEL not in match.state.log:
        raise HTTPException(404, 'Unknown owned fixture')
    return match


def audit(match):
    snapshot = serialize_match_snapshot(match.state)
    return {'pid': os.getpid(), 'snapshot': snapshot,
            'snapshot_sha256': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
            'revision': match.revision}


@app.get('/fixture/manual-mana/status')
def status(request: Request):
    authorize(request)
    return {'pid': os.getpid(), 'source_root': str(ROOT)}


@app.post('/fixture/manual-mana')
def fixture(request: Request, seat: int = 1, scenario: str = 'tower'):
    authorize(request)
    names = {'tower': 'Phyrexian Tower', 'witch': 'Bog Witch', 'cairns': 'Graven Cairns',
             'grove': 'Flooded Grove', 'reflection': 'Graven Cairns', 'sphere': 'Graven Cairns', 'plain': 'Island',
             'mixed-preset': 'Gyre Engineer', 'mixed-sphere-preset': 'Simic Growth Chamber', 'land-preset': 'Island'}
    if seat not in (1, 2) or scenario not in names:
        raise HTTPException(422, 'Unknown bounded canonical scenario')
    state = position(seat)
    state.id = str(uuid4())
    source = add(state, names[scenario], seat)
    hand = [add(state, name, seat, Zone.HAND) for name in ('Forest', 'Island')]
    creatures = [add(state, 'Raging Goblin', seat) for _ in range(2)]
    foreign_hand = add(state, 'Island', 3-seat, Zone.HAND)
    foreign_creature = add(state, 'Raging Goblin', 3-seat)
    state.players[seat].mana_pool = dict.fromkeys('WUBRGC', 0)
    if scenario not in {'tower', 'plain', 'mixed-preset', 'mixed-sphere-preset', 'land-preset'}:
        state.players[seat].mana_pool['G' if scenario == 'grove' else 'B'] = 1
    if scenario == 'reflection':
        add(state, 'Mana Reflection', seat)
    if scenario in {'sphere', 'mixed-sphere-preset'}:
        add(state, 'Damping Sphere', seat)
    state.log.append(LABEL)
    moves = RulesEngine().legal_moves(state, seat)
    move = next(m for m in moves if m['type'] == 'activate_mana_ability' and m['card_id'] == source.id
                and (m['cost_text'] == '{T}' if scenario in {'plain', 'mixed-preset', 'mixed-sphere-preset', 'land-preset'} else m['cost_text'] != '{T}'))
    target = {'B': 2} if scenario == 'tower' else {'B': 3} if scenario == 'witch' else {'U': 1} if scenario in {'plain', 'land-preset'} else {'G': 1, 'U': 1} if scenario in {'grove', 'mixed-preset', 'mixed-sphere-preset'} else {'B': 1, 'R': 1}
    output = next(o for o in move['output_options'] if o['output_bundle'] == target)
    expected = {'C': 1} if scenario in {'sphere', 'mixed-sphere-preset'} else {'B': 2, 'R': 2} if scenario == 'reflection' else target
    deck = [{'card_name': 'Swamp', 'quantity': 60}]
    match = main.MatchController(state=state, rules=RulesEngine(), controllers={1: 'human', 2: 'human'},
        ai={1: AIAgent(), 2: AIAgent()}, mode='human_vs_human', deck_ids=(None, None),
        mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []}, game_number=1,
        current_game_recorded=False, match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = match
    persist(match)
    selected = hand[1].id if scenario == 'witch' else creatures[1].id if scenario == 'tower' else None
    return {'match': main.get_match(state.id), 'source_id': source.id, 'name': source.name,
            'ability_index': move['ability_index'], 'output': output, 'expected_pool': expected,
            'selected_id': selected, 'unselected_id': hand[0].id if scenario == 'witch' else creatures[0].id,
            'foreign_hand_id': foreign_hand.id, 'foreign_creature_id': foreign_creature.id,
            'branch': 'G' if scenario == 'grove' else 'B', 'canonical_source': ROWS[source.name], 'label': LABEL}


@app.get('/fixture/manual-mana/{identifier}/audit')
def read_audit(identifier: str, request: Request):
    authorize(request)
    return audit(owned(identifier))


@app.post('/fixture/manual-mana/{identifier}/restore')
def restore(identifier: str, request: Request):
    authorize(request)
    match = owned(identifier)
    with match.mutation_lock:
        before = audit(match)['snapshot_sha256']
        persist(match)
        main.ACTIVE_MATCHES.pop(identifier)
        with Session(engine) as session:
            main._restore_active_matches(Repository(session), identifier)
        restored = audit(owned(identifier))
        assert restored['snapshot_sha256'] == before
        return restored


@app.get('/fixture/manual-mana/actions')
def actions(request: Request, match_id: str):
    authorize(request)
    rows = [json.loads(line) for line in ACTION_LOG.read_text().splitlines()] if ACTION_LOG.exists() else []
    return [row for row in rows if row['url'] == f'/matches/{match_id}/action']
