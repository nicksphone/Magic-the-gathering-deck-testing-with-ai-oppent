"""Strict desired runtime assertions for separately owned missing dependencies.

These ordinary failures are preserved, not skipped or treated as resolver passes.
"""
import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action
from rules_engine.stack_engine import resolve_top_of_stack
from effects.handlers import search_library
from tests.test_linked_damage_targets import raw_card
from tests.test_targeted_search_resolver_contract import position, raw, restore


@pytest.mark.parametrize('seat', [1, 2])
def test_search_public_prompt_must_not_disclose_private_library(seat):
    state, payload = position(seat)
    owner = 3-seat
    search_library(state, seat, {**payload, 'target_player': owner})
    pending = serialize_match(state)['pending_mechanic_choice']
    assert set(pending) <= {'kind', 'player_id', 'label', 'count', 'min_count'}


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_fertilids_favor_requires_complete_compiler(seat):
    state, _ = position(seat)
    state.priority_player = seat
    card = raw_card(state, raw('fertilids-favor'), seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 4}
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': card.id,
        'targets': {'target_player': 3-seat, 'target_card_ids': []}})
    assert state.stack[-1].effect_key == 'effect_sequence'
    assert [e['effect_key'] for e in state.stack[-1].payload['effects']] == ['search_library', 'add_counters']
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['player_id'] == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_fertilid_activation_must_offer_targeted_search(seat):
    state, _ = position(seat)
    state.priority_player = seat
    card = raw_card(state, raw('fertilid'), seat, Zone.BATTLEFIELD)
    card.counters = {'+1/+1': 2}
    state.players[seat].mana_pool = {'G': 2}
    assert any(m.get('type') == 'activate_ability' and m.get('card_id') == card.id
               for m in RulesEngine().legal_moves(state, seat))
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': card.id, 'ability_index': 0,
        'targets': {'target_player': 3-seat}})
    assert state.cards[card.id].counters == {'+1/+1': 1}
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['player_id'] == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_own_search_must_retain_genuine_shuffle_cause(seat, monkeypatch):
    state, payload = position(seat)
    # Restore the actual paid stack item, unchanged; unlike ownership unit tests,
    # resolve through production transport rather than supplying a frame to handler.
    from game_state.state import StackItem
    state.stack.append(StackItem(**payload['__resolving_item']))
    seen = []
    import rules_engine.events as events
    emit = events.emit_event

    def spy(current, event, data):
        if event == 'shuffle':
            seen.append(data)
        return emit(current, event, data)

    monkeypatch.setattr(events, 'emit_event', spy)
    assert not resolve_top_of_stack(state)
    state = checked_action(restore(state), RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': []})
    assert len(seen) == 1 and seen[0]['cause'] is not None
    assert seen[0]['cause']['stack_id'] == payload['__resolving_item']['id']
