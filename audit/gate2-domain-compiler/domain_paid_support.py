"""Exact existing paid helpers; no admission assertions or invented Oracle."""
from copy import deepcopy
import json
import os
import inventory as inv
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
PHASE = os.environ.get('ADMISSION_PHASE', 'before')
OUT = inv.ROOT.parent / 'evidence'

def position(facts, seat):
    land = facts['Forest']
    deck = [{**land, 'card_name': land['name'], 'quantity': 30}]
    state = MatchFactory.from_decks(deck, deck, seed=2331)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    for player in state.players.values():
        for cid in list(player.hand):
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()
    return state

def add(state, facts, name, seat, zone=Zone.BATTLEFIELD):
    raw = facts[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 1}], [], seed=2331)
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

def cast(state, seat, source, **targets):
    return act(state, seat, 'cast_spell', card_id=source, targets=targets)

def restore(state):
    packet = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(packet)
    assert serialize_match_snapshot(result) == packet
    return result

def resolve(state):
    assert resolve_top_of_stack(state)
    return state

def respond(state, seat):
    if state.priority_player != seat:
        state = act(state, state.priority_player, 'pass_priority')
    assert state.priority_player == seat
    return state

def receipt(label, facts, names, state, **observed):
    packet = {'case': label, 'phase': PHASE,
        'raw_sha256': {name: inv.canonical_hash(facts[name]) for name in names},
        'coverage_sha256': inv.sha(inv.ROOT / 'backend/rules_engine/coverage.py'),
        'state_sha256': inv.canonical_hash(serialize_match_snapshot(state)), 'observed': observed}
    with (OUT / (PHASE + '-' + label + '.json')).open('x') as stream:
        json.dump(packet, stream, indent=2, sort_keys=True)
