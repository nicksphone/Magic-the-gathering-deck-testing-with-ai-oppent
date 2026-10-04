"""Offline canonical setup and real checked-action evidence (no engine mocks)."""
import json
import os
from copy import deepcopy
from pathlib import Path

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine

ROWS = {r['name']: r for r in json.loads((Path(__file__).parents[1] / 'fixtures/regression_agent_wave2/cards.json').read_text())}
SEED = 731
RULES = RulesEngine()


def entry(name, quantity=1):
    from types import SimpleNamespace
    from card_data.sync import ScryfallSyncService
    from card_data.hydration import hydrate_deck_cards
    row = SimpleNamespace(**ScryfallSyncService._normalize_payload(ROWS[name], None))
    # Offline repository adapter only; production sync normalization, hydration,
    # factory, rules, payment, AI, and serializers all remain real.
    repo = SimpleNamespace(get_cached_cards_by_names=lambda names: {name.lower(): row})
    return hydrate_deck_cards(repo, [{'card_name': name, 'quantity': quantity}])[0]


def position(seat=1):
    # Bounded positions, not proposed competitive decks. Library filler is real.
    state = MatchFactory.from_decks([entry('Mountain', 20)], [entry('Island', 20)], seed=SEED)
    state.id = 'wave2-seed-731'
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.turn = 5
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.mana_pool = {c: 0 for c in 'WUBRGC'}
    return state


def add(state, name, seat=1, zone=Zone.HAND):
    # Factory owns canonical face/type/printed-characteristic hydration.
    sample = MatchFactory.from_decks([entry(name, 8)], [], seed=SEED)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
        card.summoning_sick = False
    return card


def moves(state, card):
    return [m for m in RULES.legal_moves(state, card.controller) if m.get('card_id') == card.id]


def record(label, state, **extra):
    path = os.environ.get('WAVE2_TRACE')
    if path:
        with open(path, 'a') as handle:
            handle.write(json.dumps({'test': os.environ.get('PYTEST_CURRENT_TEST', ''), 'label': label,
                'seed': SEED, 'snapshot': serialize_match_snapshot(state), **extra}, sort_keys=True) + '\n')


def cast(state, card, targets=None, **extra):
    payload = {'type': 'cast_spell', 'card_id': card.id, **extra}
    if targets is not None:
        payload['targets'] = targets
    record('announcement', state, legal_moves=moves(state, card), action=payload)
    result = checked_action(state, RULES, card.controller, payload)
    record('paid', result)
    return result


def reject(state, seat, payload):
    before = serialize_match_snapshot(state)
    record('rejection-before', state, action=payload)
    caught = None
    try:
        result = checked_action(state, RULES, seat, payload)
    except ActionRejected as error:
        caught = error
        result = None
    # Check all serialized fields even if the expected rejection did not occur.
    assert serialize_match_snapshot(state) == before
    record('rejection-after', state, rejected=bool(caught), result=serialize_match_snapshot(result) if result else None)
    assert caught is not None, 'Illegal announcement was accepted'


def resume(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def settle(state):
    for _ in range(32):
        if not state.stack:
            record('resolved', state)
            return state
        assert state.pending_mechanic_choice is None, state.pending_mechanic_choice
        state = checked_action(state, RULES, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Stack did not settle in 32 checked priority passes')
