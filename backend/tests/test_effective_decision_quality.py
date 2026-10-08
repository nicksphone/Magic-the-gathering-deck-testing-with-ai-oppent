"""Effective battlefield types in quality evidence, not AI-strength claims."""
from copy import deepcopy

import pytest

from analytics.decision_quality import _battlefield_snapshot, _lethal_attack_available, build_trace_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.type_effects import effective_types
from scripts.overnight_verbose_round_robin import battlefield_snapshot, lethal_attack_available
from tests.test_basic_land_layer_goldens import add, position, setter


def combat_position(seat, replaced):
    state = position(seat)
    attacker = add(state, 'Royal Assassin', seat)
    defender = add(state, 'Royal Assassin', 3 - seat)
    aura = setter(state, 'Song of the Dryads', seat, defender) if replaced else None
    state.step = Step.DECLARE_ATTACKERS
    state.players[3 - seat].life = 1
    state.attackers_declared = False
    return state, attacker.id, defender.id, aura.id if aura else None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
@pytest.mark.parametrize('snapshot', [_battlefield_snapshot, battlefield_snapshot])
def test_layered_trace_uses_effective_types_and_is_query_pure(seat, restored, snapshot):
    state, _, defender, _ = combat_position(seat, True)
    if restored:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    assert state.cards[defender].types == ['Creature']
    assert effective_types(state, defender) == ['Land']
    row = next(row for row in snapshot(state, 3 - seat) if row['id'] == defender)
    assert row['types'] == ['Land']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
@pytest.mark.parametrize('query', [_lethal_attack_available, lethal_attack_available])
def test_transformed_nonblocker_does_not_hide_actual_lethal(seat, restored, query):
    state, attacker, defender, _ = combat_position(seat, True)
    if restored:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    legal = RulesEngine().legal_moves(state, seat)
    actual = deepcopy(state)
    rules = RulesEngine()
    actual = checked_action(actual, rules, seat, {'type': 'attack', 'attackers': [attacker]})
    for _ in range(16):
        if actual.winner is not None:
            break
        moves = rules.legal_moves(actual, actual.priority_player)
        action = ({'type': 'block', 'blocks': {}}
                  if any(move['type'] == 'block' for move in moves)
                  else {'type': 'pass_priority'})
        actual = checked_action(actual, rules, actual.priority_player, action)
    assert actual.winner == seat
    assert query(state, seat, legal) is True
    assert state.cards[defender].types == ['Creature']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('query', [_lethal_attack_available, lethal_attack_available])
def test_real_creature_blocker_still_excludes_open_board_metric(seat, query):
    state, _, defender, _ = combat_position(seat, False)
    before = serialize_match_snapshot(state)
    assert 'Creature' in effective_types(state, defender)
    assert query(state, seat, RulesEngine().legal_moves(state, seat)) is False
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_layer_source_departure_restores_blocker_and_trace(seat):
    state, _, defender, aura = combat_position(seat, True)
    state.players[seat].battlefield.remove(aura)
    state.cards[aura].move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(aura)
    before = serialize_match_snapshot(state)
    trace = build_trace_payload(state, seat, RulesEngine().legal_moves(state, seat),
                               {'type': 'pass_priority'})
    assert trace['opp_battlefield'][0]['types'] == ['Creature']
    assert trace['lethal_attack_available'] is False
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_full_trace_records_available_lethal_without_changing_action_or_root(seat):
    state, _, defender, _ = combat_position(seat, True)
    before = serialize_match_snapshot(state)
    action = {'type': 'pass_priority'}
    trace = build_trace_payload(state, seat, RulesEngine().legal_moves(state, seat), action)
    assert trace['opp_battlefield'][0]['id'] == defender
    assert trace['opp_battlefield'][0]['types'] == ['Land']
    assert trace['lethal_attack_available'] is True
    assert trace['action'] == action
    assert action == {'type': 'pass_priority'}
    assert serialize_match_snapshot(state) == before
