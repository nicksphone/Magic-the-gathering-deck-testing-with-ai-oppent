"""Printed life locks must follow effective abilities, including restoration."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.engine import RulesEngine
from rules_engine.replacement import pay_life, player_life_total_cant_change, player_cant_gain_life
from tests.test_ai_search_prefix import bare_state
from tests.test_life_conversion import permanent
from tests.test_linked_damage_targets import raw_card


def restriction(state, name, controller):
    raw = json.loads((Path(__file__).parent / 'fixtures/life_restriction_layers' / (name+'.json')).read_text())
    from game_state.state import Zone
    return raw_card(state, raw, controller, Zone.BATTLEFIELD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('operation', ['gain_life', 'lose_life', 'deal_damage', 'pay_life'])
def test_suppressed_printed_lock_stops_preventing_life_events(seat, restore, operation):
    state = bare_state(seat)
    source = permanent(state, 'platinum-emperion', seat)
    assert player_life_total_cant_change(state, seat)
    assert not player_life_total_cant_change(state, 3-seat)
    add_keyword_effect(state, source.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    if restore:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert not player_life_total_cant_change(state, seat)
    if operation == 'pay_life':
        assert pay_life(state, seat, 3)
    else:
        resolve_effect(state, seat, operation, {'target_player': seat, 'amount': 3})
    assert state.players[seat].life == (23 if operation == 'gain_life' else 17)
    assert state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('name', ['rampaging-ferocidon', 'erebos-god-of-the-dead'])
def test_printed_gain_prohibition_returns_when_temporary_ability_loss_expires(seat, restore, name):
    state = bare_state(seat)
    source = restriction(state, name, seat)
    assert player_cant_gain_life(state, 3-seat)
    assert player_cant_gain_life(state, seat) == (name == 'rampaging-ferocidon')
    add_keyword_effect(state, source.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    if restore:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert not player_cant_gain_life(state, seat)
    assert not player_cant_gain_life(state, 3-seat)
    resolve_effect(state, seat, 'gain_life', {'target_player': 3-seat, 'amount': 3})
    assert state.players[3-seat].life == 23
    RulesEngine()._clear_marked_damage(state)
    assert player_cant_gain_life(state, 3-seat)
    resolve_effect(state, seat, 'gain_life', {'target_player': 3-seat, 'amount': 3})
    assert state.players[3-seat].life == 23


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suppressed', [False, True])
@pytest.mark.parametrize('name', ['platinum-emperion', 'erebos-god-of-the-dead'])
def test_controller_relative_restriction_uses_current_controller_after_snapshot(seat, suppressed, name):
    state = bare_state(seat)
    source = permanent(state, name, seat) if name == 'platinum-emperion' else restriction(state, name, seat)
    if suppressed:
        add_keyword_effect(state, source.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    resolve_effect(state, 3-seat, 'change_control', {'target_card_id': source.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.cards[source.id].owner == seat
    assert state.cards[source.id].controller == 3-seat
    if suppressed:
        assert not player_cant_gain_life(state, seat)
        assert not player_cant_gain_life(state, 3-seat)
        RulesEngine()._clear_marked_damage(state)
    restricted = 3-seat if name == 'platinum-emperion' else seat
    assert player_cant_gain_life(state, restricted)
    assert not player_cant_gain_life(state, 3-restricted)


@pytest.mark.parametrize('seat', [1, 2])
def test_turn_prohibition_is_not_removed_with_printed_source_abilities(seat):
    state = bare_state(seat)
    source = restriction(state, 'rampaging-ferocidon', seat)
    add_keyword_effect(state, source.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    state.turn_cant_gain_life.add(seat)
    resolve_effect(state, seat, 'gain_life', {'amount': 3})
    resolve_effect(state, seat, 'gain_life', {'target_player': 3-seat, 'amount': 3})
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == 23


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['platinum-emperion', 'rampaging-ferocidon'])
def test_public_life_forecast_tracks_suppression_and_expiry_without_mutation(seat, name):
    from ai.life_targets import life_target_score
    state = bare_state(seat)
    source = permanent(state, name, seat) if name == 'platinum-emperion' else restriction(state, name, seat)
    assert life_target_score(state, seat, seat, 4) == 0
    add_keyword_effect(state, source.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    before = serialize_match_snapshot(state)
    assert life_target_score(state, seat, seat, 4) == 4
    assert serialize_match_snapshot(state) == before
    RulesEngine()._clear_marked_damage(state)
    assert life_target_score(state, seat, seat, 4) == 0
