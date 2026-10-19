"""Canonical combined triggers: cost events, recipient scope and source LKI."""
from dataclasses import asdict

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana_abilities import mana_ability_specs
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_death_cycle_ordering_audit import (
    add, cards, cycle_position, receipt, restart)
from tests.test_death_cycle_ordering_http_audit import (
    act, drain, install, offline_client, restore)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['none', 'rip'])
def test_actual_spell_discard_cost_is_one_counter_trigger(request, seat, mode):
    state, discarded, _ = cycle_position(seat, 'Lonely Sandbar', mode)
    watcher = add(state, 'Archfiend of Ifnir', seat)
    own = add(state, 'Krosan Tusker', seat)
    opposing = add(state, 'Krosan Tusker', 3-seat)
    spell = add(state, 'Tormenting Voice', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'R': 1}
    action = cards.cast(spell, cost_choice={'id': 'base', 'discard_card_ids': [discarded.id]})
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    triggers = [item for item in paid.stack if item.source_card_id == watcher.id]
    queued = [asdict(item) for item in paid.stack]
    assert len(triggers) == 1
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    receipt(request, {'action': action, 'queued': queued,
                      'resolved': serialize_match_snapshot(paid)})
    assert paid.cards[opposing.id].counters.get('-1/-1', 0) == 1
    assert not paid.cards[own.id].counters
    assert paid.cards[discarded.id].zone == (Zone.EXILE if mode == 'rip' else Zone.GRAVEYARD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('depart', [False, True])
def test_cycle_trigger_has_no_target_and_survives_actual_source_sacrifice(request, seat, depart):
    state, source, action = cycle_position(seat, 'Lonely Sandbar')
    watcher = add(state, 'Archfiend of Ifnir', seat)
    watcher.owner = 3-seat
    own = add(state, 'Krosan Tusker', seat)
    opposing = add(state, 'Krosan Tusker', 3-seat)
    tower = add(state, 'Phyrexian Tower', seat)
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    assert len(paid.stack) == 2 and not paid.pending_trigger_order
    trigger = paid.stack[-1]
    assert not trigger.targets and trigger.payload['recipients'] == 'opponents'
    if depart:
        spec = next(spec for spec in mana_ability_specs(paid.cards[tower.id], paid)
                    if 'Sacrifice' in spec[1])
        sacrifice = {'type': 'activate_mana_ability', 'card_id': tower.id,
                     'ability_index': spec[0], 'color': 'B',
                     'payment_choices': {'sacrifice_card_ids': [watcher.id]}}
        with cards.unchanged_root(paid):
            paid = checked_action(paid, RulesEngine(), seat, sacrifice)
        assert paid.cards[watcher.id].zone == Zone.GRAVEYARD
        assert watcher.id in paid.players[3-seat].graveyard
        assert paid.cards[watcher.id].last_known_battlefield['controller'] == seat
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    receipt(request, {'departed': depart, 'resolved': serialize_match_snapshot(paid)})
    assert paid.cards[opposing.id].counters.get('-1/-1', 0) == 1
    assert not paid.cards[own.id].counters


@pytest.mark.parametrize('seat', [1, 2])
def test_independent_two_cycling_costs_each_trigger_once_not_lifetime_dedup(request, seat):
    state, first, first_action = cycle_position(seat, 'Lonely Sandbar')
    add(state, 'Archfiend of Ifnir', seat)
    opposing = add(state, 'Krosan Tusker', 3-seat)
    second = add(state, 'Lonely Sandbar', seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 2}
    for action in [first_action, {'type': 'cycle_card', 'card_id': second.id}]:
        with cards.unchanged_root(state):
            state = checked_action(state, RulesEngine(), seat, action)
        assert len(state.stack) == 2
        assert resolve_top_of_stack(state)
        assert resolve_top_of_stack(state)
    receipt(request, {'resolved': serialize_match_snapshot(state)})
    assert state.cards[opposing.id].counters.get('-1/-1', 0) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['none', 'rip', 'leyline_enemy'])
def test_actual_http_compound_self_cycling_search_and_draw(request, offline_client, seat, mode):
    state, source, action = cycle_position(seat, 'Krosan Tusker', mode)
    match = install(state, request, seat)
    response = act(offline_client, match, seat, action)
    assert response.status_code == 200, response.text
    match = restore(state.id)
    match = drain(offline_client, state.id)
    receipt(request, {'action': action, 'resolved': serialize_match_snapshot(match.state)})
    assert len(match.state.players[seat].hand) == 2
    assert len(match.state.players[seat].library) == 1
    assert not match.state.stack and not match.state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_opponent_cycling_does_not_fire_own_controller_condition(seat):
    state, source, action = cycle_position(3-seat, 'Lonely Sandbar')
    add(state, 'Archfiend of Ifnir', seat)
    opposing = add(state, 'Krosan Tusker', 3-seat)
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), 3-seat, action)
    assert len(paid.stack) == 1
    assert resolve_top_of_stack(paid)
    assert not paid.cards[opposing.id].counters


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('second_copy', [False, True])
def test_cycling_same_name_is_another_card_only_for_other_battlefield_copy(seat, second_copy):
    state, source, action = cycle_position(seat, 'Archfiend of Ifnir')
    if second_copy:
        add(state, 'Archfiend of Ifnir', seat)
    opposing = add(state, 'Krosan Tusker', 3-seat)
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    assert len(paid.stack) == (2 if second_copy else 1)
    if second_copy:
        assert resolve_top_of_stack(paid)
    assert resolve_top_of_stack(paid)
    assert paid.cards[opposing.id].counters.get('-1/-1', 0) == int(second_copy)
