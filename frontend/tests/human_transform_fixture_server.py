"""Guarded canonical face positions; actual HTTP imports and local hydration."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOKEN = os.environ.get('MTG_HUMAN_TRANSFORM_TOKEN', '')
if (not TOKEN or os.environ.get('MTG_HUMAN_TRANSFORM_ROOT') != str(ROOT)
        or (ROOT / '.git').exists() or not (ROOT / '.human-transform-owned').is_file()
        or (ROOT / '.human-transform-owned').read_text() != TOKEN
        or Path(importlib.util.find_spec('main').origin).resolve() != ROOT / 'backend/main.py'):
    raise RuntimeError('Human transform fixtures require owned disposable source')

import main
from fastapi import HTTPException, Request
from sqlmodel import Session
from ai.agent import AIAgent
from card_data.hydration import hydrate_deck_cards
from card_data.sync import ScryfallSyncService
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine

assert DATABASE_PATH.resolve() == ROOT / 'backend/mtg_lab.db'
DIRECTORY = ROOT / 'backend/tests/fixtures'
FILES = ['cathar_canonical/0dbac7ce-a6fa-466e-b6ba-173cf2dec98e.json',
         'human_transform_audit/canonical.json', 'human_flow_audit/canonical.json']
PINS = {name: hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest() for name in FILES}
CATHAR = json.loads((DIRECTORY / FILES[0]).read_text())
TRANSFORM = json.loads((DIRECTORY / FILES[1]).read_text())
DELVER = TRANSFORM['Delver of Secrets // Insectile Aberration']
SUPPORT = json.loads((DIRECTORY / FILES[2]).read_text())
RAW = {row['name']: row for row in [CATHAR, DELVER, TRANSFORM['Shock'], SUPPORT['Island'], SUPPORT['Grizzly Bears']]}
assert all(row['object'] == 'card' and row['id'] and row['oracle_id'] for row in RAW.values())
LABEL = 'Canonical explicit human-transform position; not a natural game or historical repair.'
ACTION_LOG = ROOT / 'human-transform-actions.jsonl'
app = main.app


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
    if request.client.host not in {'127.0.0.1', '::1'} or request.headers.get('X-Human-Transform-Fixture') != TOKEN:
        raise HTTPException(403, 'Owned loopback fixture only')


@app.get('/fixture/human-transform/status')
def status(request: Request):
    authorize(request)
    with Session(engine) as session:
        repo = Repository(session)
        for row in RAW.values():
            if repo.get_cached_card_by_name(row['name']) is None:
                repo.upsert_card(ScryfallSyncService._normalize_payload(row, None))
    return {'pid': os.getpid(), 'source_root': str(ROOT), 'committed_fixture_sha256': PINS,
            'canonical_ids': {name: {'id': row['id'], 'oracle_id': row['oracle_id']} for name, row in RAW.items()}}


@app.post('/fixture/human-transform')
def fixture(request: Request, seat: int, scenario: str, deck_id: int):
    authorize(request)
    if seat not in (1, 2) or scenario not in {'cathar-natural', 'delver-reveal', 'delver-decline', 'delver-ineligible'}:
        raise HTTPException(422, 'Declared canonical face scenario required')
    name = CATHAR['name'] if scenario.startswith('cathar') else DELVER['name']
    with Session(engine) as session:
        repo = Repository(session)
        deck = next((deck for deck in repo.list_decks() if deck.id == deck_id), None)
        if deck is None or not deck.name.startswith('Human transform audit '):
            raise HTTPException(422, 'Use actual HTTP-imported owned deck')
        mainboard = json.loads(deck.mainboard_json)
        if {row['card_name']: row['quantity'] for row in mainboard} != {name: 2, 'Grizzly Bears': 1, 'Shock': 1, 'Island': 56}:
            raise HTTPException(422, 'Exact declared names and quantities required')
        opponent = [{'quantity': 1, 'card_name': 'Grizzly Bears'}, {'quantity': 59, 'card_name': 'Island'}]
        hydrated = hydrate_deck_cards(repo, mainboard)
        foreign_hydrated = hydrate_deck_cards(repo, opponent)
        state = MatchFactory.from_decks(hydrated if seat == 1 else foreign_hydrated,
                                       foreign_hydrated if seat == 1 else hydrated, seed=87)
        for player in state.players.values():
            player.hand.clear()
            player.library = [cid for cid, card in state.cards.items() if card.owner == player.id]
            player.mana_pool = dict.fromkeys('WUBRGC', 0)
        def move(card, zone):
            state.players[card.owner].library.remove(card.id)
            getattr(state.players[card.owner], zone.value).append(card.id)
            card.move_to_zone(zone)
        source = next(card for card in state.cards.values() if card.owner == seat
                      and card.card_faces and card.card_faces[0]['name'] == RAW[name]['card_faces'][0]['name'])
        own_bear = next(card for card in state.cards.values() if card.owner == seat and card.name == 'Grizzly Bears')
        foreign = next(card for card in state.cards.values() if card.owner == 3-seat and card.name == 'Grizzly Bears')
        move(source, Zone.HAND)
        move(own_bear, Zone.GRAVEYARD)
        move(foreign, Zone.BATTLEFIELD)
        from game_state.state import assign_static_order_on_battlefield_entry
        assign_static_order_on_battlefield_entry(state, foreign.id)
        foreign.summoning_sick = True
        private_card = next(card for card in state.cards.values()
                            if card.owner == 3-seat and card.name == 'Island')
        move(private_card, Zone.HAND)
        # Explicit controlled own top card; never policy input or historical claim.
        top = next(card for card in state.cards.values() if card.owner == seat
                   and card.name == ('Island' if scenario == 'delver-ineligible' else 'Shock'))
        state.players[seat].library.remove(top.id)
        state.players[seat].library.append(top.id)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = seat
        state.step = Step.PRECOMBAT_MAIN
        state.failed_draw_players.clear()
        state.mechanic_choice_players = {1, 2}
        state.trigger_order_choice_players = {1, 2}
        state.trigger_order_choice_required = True
        state.log.append(LABEL)
        state.players[seat].mana_pool.update(W=1, C=2) if scenario.startswith('cathar') else state.players[seat].mana_pool.update(U=1)
        controller = main.MatchController(state=state, rules=RulesEngine(),
            controllers={1: 'human', 2: 'human'}, ai={1: AIAgent(), 2: AIAgent()},
            mode='human_vs_human', deck_ids=(deck_id, None) if seat == 1 else (None, deck_id),
            mainboards={seat: mainboard, 3-seat: opponent}, sideboards={1: [], 2: []},
            game_number=1, current_game_recorded=False, match_complete=False, best_of=3)
        main.ACTIVE_MATCHES[state.id] = controller
        main._persist_active_match(repo, controller)
    return {'match': main.get_match(state.id), 'source_id': source.id,
            'source_name': name, 'source_quantity': 2, 'target_id': foreign.id, 'top_id': top.id,
            'foreign_hand_id': private_card.id, 'canonical_faces': RAW[name]['card_faces'],
            'hydrated': hydrated, 'pins': PINS, 'label': LABEL}


def owned(identifier):
    controller = main.ACTIVE_MATCHES.get(identifier)
    if controller is None or LABEL not in controller.state.log:
        raise HTTPException(404, 'Unknown owned face fixture')
    return controller


@app.get('/fixture/human-transform/{identifier}/audit')
def audit(identifier: str, request: Request):
    authorize(request)
    controller = owned(identifier)
    snapshot = serialize_match_snapshot(controller.state)
    return {'pid': os.getpid(), 'revision': controller.revision, 'snapshot': snapshot,
            'snapshot_sha256': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()}


@app.get('/fixture/human-transform/actions')
def actions(request: Request, match_id: str):
    authorize(request)
    owned(match_id)
    return [row for line in ACTION_LOG.read_text().splitlines() if (row := json.loads(line))['url'] == f'/matches/{match_id}/action'] if ACTION_LOG.exists() else []
