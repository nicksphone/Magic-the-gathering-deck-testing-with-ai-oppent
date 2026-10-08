"""Canonical initial fixtures and checked native producers for counter tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind

HERE = Path(__file__).parent / 'fixtures/counter_native_frames'
FACTS = json.loads((HERE / 'canonical.json').read_bytes())
PROOF = json.loads((HERE / 'provenance.json').read_bytes())
for name, row in FACTS.items():
    body = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(body).hexdigest() == PROOF['cards'][name]['canonical_fullrow_sha256']


def add(state, name, seat, zone=Zone.HAND):
    raw = FACTS[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=100)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def act(state, seat, kind, **fields):
    return checked_action(state, RulesEngine(), seat, {'type': kind, **fields})


def respond(state, seat):
    if state.priority_player != seat:
        state = act(state, state.priority_player, 'pass_priority')
    assert state.priority_player == seat
    return state


def paid(state, name, seat, *, pool, **targets):
    state = respond(state, seat)
    source = add(state, name, seat)
    state.players[seat].mana_pool.update(pool)
    state = act(state, seat, 'cast_spell', card_id=source, targets=targets)
    item = next(item for item in state.stack if item.source_card_id == source)
    assert stack_object_kind(state, item) == 'spell'
    return state, source, item.id


def trigger_and_spell(*, activated=False, creature=False):
    raw = FACTS['Island']
    deck = [{**raw, 'card_name': raw['name'], 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=100)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 2
    state.active_player = state.priority_player = 1
    state.step = Step.UPKEEP
    sheoldred = add(state, 'Sheoldred, the Apocalypse', 2, Zone.BATTLEFIELD)
    ballista = add(state, 'Walking Ballista', 2, Zone.BATTLEFIELD) if activated else None
    if ballista:
        state.cards[ballista].counters['+1/+1'] = 2
    if creature:
        add(state, 'Vedalken Orrery', 2, Zone.BATTLEFIELD)
    state = act(state, 1, 'pass_priority')
    state = act(state, 2, 'pass_priority')
    trigger = next(item.id for item in state.stack if item.source_card_id == sheoldred)
    assert stack_object_kind(state, next(item for item in state.stack if item.id == trigger)) == 'triggered'
    state, bolt, spell = paid(state, 'Lightning Bolt', 2, pool={'R': 1}, target_player=1)
    if activated:
        move = next(move for move in RulesEngine().legal_moves(state, 2)
                    if move['type'] == 'activate_ability' and move.get('card_id') == ballista
                    and move.get('ability_index') == 1)
        state = act(state, 2, 'activate_ability', card_id=ballista,
                    ability_index=move['ability_index'], targets={'target_player': 1})
        assert stack_object_kind(state, state.stack[-1]) == 'activated'
    if creature:
        state, _, _ = paid(state, 'Elvish Mystic', 2, pool={'G': 1})
    return respond(state, 1)
