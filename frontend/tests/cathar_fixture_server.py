"""Dedicated, guarded canonical fixtures; never import beside a normal checkout."""
import hashlib
import importlib.util
import json
import os
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOKEN = os.environ.get('MTG_CATHAR_FIXTURE_TOKEN', '')
if (not TOKEN or os.environ.get('MTG_CATHAR_FIXTURE_ROOT') != str(ROOT)
        or (ROOT / '.git').exists()
        or not (ROOT / '.cathar-browser-owned').is_file()
        or (ROOT / '.cathar-browser-owned').read_text() != TOKEN
        or Path(importlib.util.find_spec('main').origin).resolve() != ROOT / 'backend/main.py'):
    raise RuntimeError('Cathar fixtures require the runner-owned disposable backend')

import main
from fastapi import HTTPException, Request
from sqlmodel import Session
from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone, object_incarnation
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add
from tests.test_cathar_day_night_linked_exile import (
    CATHAR, FACTS, setup, return_exiled, test_cached_fixture_facts_match_provenance_backed_canonical_records,
)

assert DATABASE_PATH.resolve() == ROOT / 'backend/mtg_lab.db'
test_cached_fixture_facts_match_provenance_backed_canonical_records()
UNSUMMON = next(row for row in json.loads(
    (ROOT / 'backend/tests/fixtures/defensive_responses.json').read_text()) if row['name'] == 'Unsummon')
app = main.app
LABEL = 'Cathar actual-browser controlled fixture; not a played game or historical repair.'
ACTION_LOG = ROOT / 'cathar-ui-actions.jsonl'


@app.middleware('http')
async def observe_actions(request: Request, call_next):
    body = None
    if request.method == 'POST' and request.url.path.endswith('/action'):
        body = json.loads(await request.body())
    response = await call_next(request)
    if body is not None:
        with ACTION_LOG.open('a') as stream:
            stream.write(json.dumps({'pid': os.getpid(), 'url': request.url.path,
                                    'body': body, 'status': response.status_code}) + '\n')
    return response


def authorize(request):
    if (request.client.host not in {'127.0.0.1', '::1'}
            or request.headers.get('X-Cathar-Fixture') != TOKEN):
        raise HTTPException(403, 'Runner-owned loopback fixture only')


def owned(match_id, source_id):
    match = main.ACTIVE_MATCHES.get(match_id)
    if match is None or LABEL not in match.state.log:
        raise HTTPException(404, 'Unknown controlled fixture')
    source = match.state.cards.get(source_id)
    if source is None or not source.card_faces or source.card_faces[0]['name'] != 'Brutal Cathar':
        raise HTTPException(422, 'Expected the canonical fixture source')
    return match, source


def persist(match):
    with Session(engine) as session:
        main._persist_active_match(Repository(session), match)


def audit(match, source, target_id=None):
    snapshot = serialize_match_snapshot(match.state)
    result = {'pid': os.getpid(), 'revision': match.revision,
            'source': {'id': source.id, 'name': source.name, 'zone': source.zone.value,
                       'face': source.selected_face_index, 'power': source.power,
                       'toughness': source.toughness, 'incarnation': object_incarnation(source)},
            'linked_exiles': deepcopy(match.state.linked_exiles),
            'snapshot_sha256': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
            'snapshot': snapshot}
    if target_id is not None:
        target = match.state.cards.get(target_id)
        if target is None or target.owner == source.owner:
            raise HTTPException(422, 'Expected an opposing controlled fixture target')
        result['target'] = {'id': target.id, 'name': target.name, 'zone': target.zone.value,
                            'owner': target.owner, 'incarnation': object_incarnation(target)}
    return result


@app.get('/fixture/cathar/status')
def status(request: Request):
    authorize(request)
    return {'pid': os.getpid(), 'source_root': str(ROOT), 'canonical_faces_verified': True}


@app.get('/fixture/cathar/actions')
def actions(request: Request, match_id: str):
    authorize(request)
    rows = [json.loads(line) for line in ACTION_LOG.read_text().splitlines()] if ACTION_LOG.exists() else []
    return [row for row in rows if row['url'] == f'/matches/{match_id}/action']


@app.post('/fixture/cathar')
def fixture(request: Request, seat: int = 1, designation: str = 'day'):
    authorize(request)
    if seat not in (1, 2) or designation not in {'day', 'night'}:
        raise HTTPException(422, 'Expected a canonical day/night fixture and seat')
    state, source, targets, own_target = setup(seat, designation, human=True)
    state.mechanic_choice_players = state.replacement_choice_players = {1, 2}
    state.trigger_order_choice_players = {1, 2}
    state.log.append(LABEL)
    bounce = add(state, 'Unsummon', seat, Zone.HAND, cards={'Unsummon': UNSUMMON})
    deck = [{**deepcopy(FACTS[name]), 'card_name': name, 'quantity': count}
            for name, count in ((CATHAR, 8), ('Recruitment Officer', 8), ('Plains', 44))]
    match = main.MatchController(state=state, rules=RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={1: AIAgent(), 2: AIAgent()},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = match
    persist(match)
    return {'match': main.get_match(state.id), 'source_id': source.id,
            'target_ids': [card.id for card in targets], 'own_target_id': own_target.id,
            'bounce_id': bounce.id, 'fixture_label': LABEL}


@app.get('/fixture/cathar/{match_id}/audit')
def read_audit(match_id: str, source_id: str, request: Request, target_id: str | None = None):
    authorize(request)
    match, source = owned(match_id, source_id)
    with match.mutation_lock:
        return audit(match, source, target_id)


@app.post('/fixture/cathar/{match_id}/restore')
def restore(match_id: str, source_id: str, request: Request):
    authorize(request)
    match, source = owned(match_id, source_id)
    with match.mutation_lock:
        before = audit(match, source)['snapshot_sha256']
        main.ACTIVE_MATCHES.pop(match_id)
        with Session(engine) as session:
            main._restore_active_matches(Repository(session), match_id)
        restored, source = owned(match_id, source_id)
        result = audit(restored, source)
        assert result['snapshot_sha256'] == before
        return result


@app.post('/fixture/cathar/{match_id}/transition')
def transition(match_id: str, source_id: str, operation: str, request: Request, target_id: str | None = None):
    authorize(request)
    match, source = owned(match_id, source_id)
    with match.mutation_lock:
        state = match.state
        if source.zone != Zone.BATTLEFIELD:
            raise HTTPException(422, 'Transition requires an entered source')
        if operation in {'day', 'night'}:
            state.day_night = operation
            match.rules._transform_day_night_permanents(state, operation)
        elif operation == 'blink-at-night':
            # Explicit timing fixture, not a fabricated blink spell or game log.
            resolve_effect(state, source.owner, 'exile', {'target_card_id': source_id})
            state.day_night = 'night'
            match.rules._transform_day_night_permanents(state, 'night')
            resolve_effect(state, source.owner, 'linked_exile_return', {'returning': [{
                'card_id': source_id, 'destination': 'battlefield',
                'timestamp': object_incarnation(source)}]})
        elif operation in {'target-departure', 'target-return'}:
            # Same lifecycle path as the canonical target-blink backend contract.
            if (not state.stack or state.stack[-1].effect_key != 'exile_until_source_leaves'
                    or state.stack[-1].payload.get('source_card_id') != source_id
                    or state.stack[-1].payload.get('target_card_id') != target_id):
                raise HTTPException(422, 'Expected this source and its pending chosen target')
            target = state.cards.get(target_id)
            if target is None or target.owner == source.owner:
                raise HTTPException(422, 'Expected the opposing canonical chosen target')
            if operation == 'target-departure':
                if target.zone != Zone.BATTLEFIELD:
                    raise HTTPException(422, 'Target departure requires battlefield')
                resolve_effect(state, target.owner, 'exile', {'target_card_id': target_id})
            else:
                if target.zone != Zone.EXILE:
                    raise HTTPException(422, 'Target return requires fixture exile')
                return_exiled(state, target)
        else:
            raise HTTPException(422, 'Unknown controlled transition')
        state.log.append(f'EXPLICIT FIXTURE TRANSITION: {operation}; not a player action or historical claim.')
        match.revision += 1
        persist(match)
        return audit(match, source, target_id)
