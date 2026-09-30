"""Canonical scaling sources share actual output across payment and views."""
import json
from pathlib import Path

import pytest

from ai.heuristics import repeatable_mana_value
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_card_view
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.continuous import effective_power
from rules_engine.engine import RulesEngine
from rules_engine.mana import nonland_mana_outputs, repeatable_nonland_mana_outputs, can_pay_with_pool_and_lands
from tests.test_ai_recurring_engines import fixture, add as add_card, resolve


CARDS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures' / 'variable_mana.json').read_text())}


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, player, zone, cards=CARDS)
    card.summoning_sick = False
    return card


def clean():
    state = fixture()
    for player in state.players.values():
        player.mana_pool.clear()
        player.snow_mana_pool.clear()
    return state


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name,expected', [('Elvish Archdruid', 2), ('Priest of Titania', 3), ('Circle of Dreams Druid', 3)])
def test_count_scope_and_live_board_changes(name, expected, player):
    state = clean()
    source = add(state, name, player)
    add(state, 'Llanowar Elves', player)
    bear = add(state, 'Grizzly Bears', player)
    add(state, 'Llanowar Elves', 3 - player)
    add(state, 'Forest', player)
    before = serialize_match_snapshot(state)
    assert nonland_mana_outputs(state, source.id, source) == {'G': expected}
    assert repeatable_nonland_mana_outputs(source) == {}  # no fabricated stateless quantity
    assert repeatable_nonland_mana_outputs(source, state=state) == {'G': expected}
    assert repeatable_mana_value(state, source.id) == expected * 2
    view = serialize_card_view(state, source.id)
    assert view['mana_source_amounts'] == {'G': expected}
    restored = deserialize_match_snapshot(before)
    assert nonland_mana_outputs(restored, source.id, restored.cards[source.id]) == {'G': expected}
    assert serialize_match_snapshot(state) == before
    state.players[player].battlefield.remove(bear.id)
    bear.move_to_zone(Zone.GRAVEYARD)
    state.players[player].graveyard.append(bear.id)
    assert nonland_mana_outputs(state, source.id, source) == {'G': expected - (name == 'Circle of Dreams Druid')}


@pytest.mark.parametrize('name', ['Viridian Joiner', 'Marwyn, the Nurturer'])
def test_effective_source_power_not_symbol_count_or_base_stat(name):
    state = clean()
    source = add(state, name)
    source.counters['+1/+1'] = 3
    add(state, 'Elvish Archdruid')
    expected = effective_power(state, source.id)
    assert expected == source.power + 4
    before = serialize_match_snapshot(state)
    assert nonland_mana_outputs(state, source.id, source) == {'G': expected}
    assert repeatable_nonland_mana_outputs(source, state=state) == {'G': expected}
    assert serialize_match_snapshot(state) == before
    source.counters['-1/-1'] = 20
    assert nonland_mana_outputs(state, source.id, source) == {}


def test_counter_zero_is_not_free_mana_and_current_counters_control_quantity():
    state = clean()
    source = add(state, 'Gyre Sage')
    assert nonland_mana_outputs(state, source.id, source) == {}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'tap_nonland_for_mana', 'card_id': source.id, 'color': 'G'})
    assert serialize_match_snapshot(state) == before
    source.counters['+1/+1'] = 4
    state = checked_action(state, RulesEngine(), 1, {'type': 'tap_nonland_for_mana', 'card_id': source.id, 'color': 'G'})
    assert state.players[1].mana_pool == {'G': 4}
    assert not state.stack
    assert state.cards[source.id].tapped
    assert nonland_mana_outputs(state, source.id, state.cards[source.id]) == {}
    assert repeatable_nonland_mana_outputs(state.cards[source.id], state=state) == {'G': 4}


def test_automatic_payment_uses_entire_dynamic_output_and_retains_excess():
    state = clean()
    source = add(state, 'Elvish Archdruid')
    add(state, 'Llanowar Elves').tapped = True
    add(state, 'Priest of Titania').tapped = True
    add(state, 'Circle of Dreams Druid').tapped = True
    spell = add(state, 'Steel Leaf Champion', zone=Zone.HAND)
    assert nonland_mana_outputs(state, source.id, source) == {'G': 4}
    assert can_pay_with_pool_and_lands(state, 1, spell.mana_cost)
    state = resolve(checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': spell.id, 'targets': {}}))
    assert state.cards[source.id].tapped
    assert state.players[1].mana_pool.get('G') == 1
    assert state.cards[spell.id].zone == Zone.BATTLEFIELD


def test_tapping_and_sickness_still_gate_scaling_sources():
    state = clean()
    source = add(state, 'Elvish Archdruid')
    add(state, 'Llanowar Elves')
    source.summoning_sick = True
    assert nonland_mana_outputs(state, source.id, source) == {}
    assert repeatable_nonland_mana_outputs(source, state=state) == {'G': 2}
    source.summoning_sick = False
    source.tapped = True
    assert nonland_mana_outputs(state, source.id, source) == {}


def test_unhandled_color_dependent_output_is_not_approximated_as_one():
    state = clean()
    source = add(state, 'Bloom Tender')
    assert nonland_mana_outputs(state, source.id, source) == {}
    assert repeatable_nonland_mana_outputs(source, state=state) == {}


@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Control', 'Tempo', 'Midrange', 'Ramp', 'Drain', 'Aristocrats', 'Tokens', 'Tribal'])
def test_scaling_resource_reservation_reaches_each_style_without_hidden_hand(style):
    state = clean()
    source = add(state, 'Elvish Archdruid')
    add(state, 'Llanowar Elves').tapped = True
    add(state, 'Priest of Titania').tapped = True
    add(state, 'Steel Leaf Champion', zone=Zone.HAND)
    state.step = Step.DECLARE_ATTACKERS
    before = serialize_match_snapshot(state)
    agent = AIAgent(archetype=style)
    assert agent._choose_attackers(state, [source.id], 1) == []
    assert serialize_match_snapshot(state) == before
    add(state, 'Wurmcoil Engine', 2, Zone.HAND)
    assert agent._choose_attackers(state, [source.id], 1) == []
