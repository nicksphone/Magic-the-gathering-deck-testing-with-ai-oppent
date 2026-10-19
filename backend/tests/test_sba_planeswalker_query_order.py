"""Canonical planeswalker cheap-filter ordering; controlled mutation seams labelled."""
from copy import deepcopy
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine import state_based_actions as sba
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.query_context import query_cache
from rules_engine.type_effects import effective_types
from tests.test_basic_land_hooks import cast_song
from tests.test_basic_land_layer_goldens import position


SEED = Path(__file__).resolve().parents[1] / 'card_data/builtin_oracle_seed.json'
ROWS = json.loads(SEED.read_text())['cards']
CHEAP_FIRST = ('card.zone == Zone.BATTLEFIELD and card.loyalty is not None and card.loyalty <= 0 '
               'and "Planeswalker" in effective_types(state, card)')
TYPE_FIRST = ('"Planeswalker" in effective_types(state, card) and card.zone == Zone.BATTLEFIELD '
              'and card.loyalty is not None and card.loyalty <= 0')


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    row = ROWS[name]
    sample = MatchFactory.from_decks([{**row, 'card_name': name, 'quantity': 1}], [], seed=17)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    assert card.oracle_text == row['oracle_text']
    return card


def reference_function():
    # Restore only the original pure-query condition, retaining every other SBA.
    source = inspect.getsource(sba._apply_state_based_actions_once)
    source = source.replace(CHEAP_FIRST, TYPE_FIRST)
    namespace = dict(sba.__dict__)
    exec(compile(source, '<reference type-first SBA>', 'exec'), namespace)
    return namespace['_apply_state_based_actions_once']


def reference_once(state):
    reference_function()(state)


def compare(state, callback=None):
    original = deepcopy(state)
    candidate = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_match_snapshot(candidate) == serialize_match_snapshot(original)
    original_emit = sba.emit_event
    original_grave = sba.put_into_graveyard
    events = []

    def run(current, function):
        seen = []

        def emit(root, event, payload):
            assert query_cache(root) is None, 'No query reuse across events/callbacks'
            seen.append((event, deepcopy(payload)))
            result = original_emit(root, event, payload)
            if callback is not None:
                callback(root, event, payload)
            return result

        def grave(root, cid):
            assert query_cache(root) is None, 'No query reuse across departure/replacement'
            return original_grave(root, cid)

        with patch.object(sba, 'emit_event', emit), patch.object(sba, 'put_into_graveyard', grave):
            function(current)
        assert query_cache(current) is None
        events.append(seen)

    run(original, reference_once)
    run(candidate, sba._apply_state_based_actions_once)
    assert serialize_match_snapshot(candidate) == serialize_match_snapshot(original)
    assert events[0] == events[1]
    restored = deserialize_match_snapshot(serialize_match_snapshot(candidate))
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(candidate)
    before = serialize_match_snapshot(state)
    sba.apply_state_based_actions(restored)
    sba.apply_state_based_actions(candidate)
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(candidate)
    assert serialize_match_snapshot(state) == before
    return candidate, events[1]


@pytest.mark.parametrize('seat', [1, 2])
def test_only_zero_loyalty_battlefield_cards_reach_planeswalker_type_query(seat):
    state = position(seat)
    add(state, 'Forest', seat)
    add(state, 'Teferi, Hero of Dominaria', seat)
    offboard = add(state, 'Ugin, the Spirit Dragon', seat, Zone.GRAVEYARD)
    offboard.loyalty = 0  # Controlled stopped-state loyalty, not a cast episode.
    calls = []
    original_types = sba.effective_types

    def types(root, card):
        if inspect.currentframe().f_back.f_code.co_name == '_apply_state_based_actions_once':
            calls.append(card.id)
        return original_types(root, card)

    before = serialize_match_snapshot(state)
    with patch.object(sba, 'effective_types', types):
        sba._apply_state_based_actions_once(state)
    assert calls == []
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Teferi, Hero of Dominaria', 'Nissa, Who Shakes the World'])
@pytest.mark.parametrize('loyalty', [0, -1])
def test_canonical_dead_planeswalkers_keep_actual_events_and_snapshot(seat, name, loyalty):
    state = position(seat)
    card = add(state, name, seat)
    card.loyalty = loyalty  # Controlled exact SBA boundary, not invented Oracle.
    candidate, events = compare(state)
    assert candidate.cards[card.id].zone == Zone.GRAVEYARD
    assert card.id in candidate.players[seat].graveyard
    assert [event for event, payload in events if payload['card_id'] == card.id] == ['leaves_battlefield', 'permanent_dies']


@pytest.mark.parametrize('seat', [1, 2])
def test_controlled_order_and_controller_change_keep_owner_destination(seat):
    state = position(seat)
    first = add(state, 'Teferi, Hero of Dominaria', seat)
    second = add(state, 'Nissa, Who Shakes the World', 3-seat)
    first.loyalty = second.loyalty = 0

    def callback(root, event, payload):
        # Controlled callback boundary, not a claimed canonical death trigger.
        if event == 'leaves_battlefield' and payload['card_id'] == first.id:
            resolve_effect(root, seat, 'change_control', {'target_card_id': second.id, 'new_controller': seat})

    candidate, events = compare(state, callback)
    departures = [(payload['card_id'], payload['controller']) for event, payload in events if event == 'leaves_battlefield']
    assert departures == [(first.id, seat), (second.id, seat)]
    assert second.id in candidate.players[3-seat].graveyard
    assert second.id not in candidate.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_song_resolution_hides_zero_loyalty_planeswalker_until_source_departure(seat):
    state = position(seat)
    walker = add(state, 'Teferi, Hero of Dominaria', seat)
    state = cast_song(state, walker.id, seat)
    song = next(card for card in state.cards.values() if card.name == 'Song of the Dryads')
    state.cards[walker.id].loyalty = 0  # Controlled boundary after legal Song resolution.
    hidden, _ = compare(state)
    assert hidden.cards[walker.id].zone == Zone.BATTLEFIELD
    assert effective_types(hidden, walker.id) == ['Land']
    resolve_effect(hidden, seat, 'destroy_permanent', {'target_card_id': song.id})
    restored, _ = compare(hidden)
    assert restored.cards[walker.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_type_source_departure_callback_refreshes_later_card_in_same_loop(seat):
    state = position(seat)
    first = add(state, 'Nissa, Who Shakes the World', seat)
    later = add(state, 'Teferi, Hero of Dominaria', 3-seat)
    # Own active seat legally casts Song targeting the opponent's walker.
    state = cast_song(state, later.id, seat)
    song = next(card for card in state.cards.values() if card.name == 'Song of the Dryads')
    state.cards[first.id].loyalty = state.cards[later.id].loyalty = 0

    def callback(root, event, payload):
        # Controlled callback, real destruction handler; no fabricated card trigger.
        if event == 'leaves_battlefield' and payload['card_id'] == first.id:
            resolve_effect(root, seat, 'destroy_permanent', {'target_card_id': song.id})

    candidate, events = compare(state, callback)
    assert candidate.cards[song.id].zone == Zone.GRAVEYARD
    assert candidate.cards[later.id].zone == Zone.GRAVEYARD
    assert [payload['card_id'] for event, payload in events if event == 'leaves_battlefield'] == [first.id, later.id]


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_replacement_keeps_dead_walker_exile_and_no_die_event(seat):
    state = position(seat)
    add(state, 'Rest in Peace', 3-seat)
    walker = add(state, 'Teferi, Hero of Dominaria', seat)
    walker.loyalty = 0  # Controlled SBA boundary, canonical replacement text unchanged.
    candidate, events = compare(state)
    assert candidate.cards[walker.id].zone == Zone.EXILE
    assert walker.id in candidate.players[seat].exile
    assert [event for event, payload in events if payload['card_id'] == walker.id] == ['leaves_battlefield']


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_canonical_loyalty_payment_departure_keeps_stack_ability_and_full_state(seat):
    state = position(seat)
    source = add(state, 'Ugin, the Spirit Dragon', seat)
    victim = add(state, 'Nissa, Who Shakes the World', 3-seat)
    offered = RulesEngine().legal_moves(state, seat)
    move = next(move for move in offered if move['type'] == 'activate_loyalty'
                and move['card_id'] == source.id and move.get('ability_x_cost'))
    action = {'type': 'activate_loyalty', 'card_id': source.id,
              'ability_index': move['ability_index'], 'targets': {'x_value': source.loyalty}}
    baseline = deepcopy(state)
    candidate = deepcopy(state)
    old = reference_function()

    def run(current):
        before = serialize_match_snapshot(current)
        current = checked_action(current, RulesEngine(), seat, action)
        assert serialize_match_snapshot(state) == before
        assert current.cards[source.id].zone == Zone.GRAVEYARD
        assert current.stack and current.stack[-1].source_card_id == source.id
        at_departure = serialize_match_snapshot(current)
        current = deserialize_match_snapshot(at_departure)
        assert serialize_match_snapshot(current) == at_departure
        for _ in range(8):
            if not current.stack:
                break
            before = serialize_match_snapshot(current)
            result = checked_action(current, RulesEngine(), current.priority_player, {'type': 'pass_priority'})
            assert serialize_match_snapshot(current) == before
            current = result
        assert not current.stack
        assert current.cards[victim.id].zone == Zone.EXILE
        return current, at_departure

    with patch.object(sba, '_apply_state_based_actions_once', old):
        baseline, old_departure = run(baseline)
    candidate, new_departure = run(candidate)
    assert old_departure == new_departure
    assert serialize_match_snapshot(candidate) == serialize_match_snapshot(baseline)
