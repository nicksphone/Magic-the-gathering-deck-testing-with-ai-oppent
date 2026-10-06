"""Independent final tier: manual nonland vectors and exactly-once resource use."""
from unittest.mock import patch
import json
from pathlib import Path

import pytest

from tests.test_base_vector_boundaries import ROWS, add, position, pool
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana_abilities import mana_ability_specs
from rules_engine import resource_events


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('color', ['G', 'U'])
def test_manual_nonland_explicit_selector_emits_complete_vector_once(seat, color):
    state = position(seat)
    source = add(state, 'Gyre Engineer', seat)
    spec = next(s for s in mana_ability_specs(source, state) if s[1] == '{T}')
    before = serialize_match_snapshot(state)
    with patch.object(resource_events, 'tap_permanents', wraps=resource_events.tap_permanents) as tapped:
        result = checked_action(state, RulesEngine(), seat, {
            'type': 'activate_mana_ability', 'card_id': source.id,
            'ability_index': spec[0], 'color': color, 'output_bundle': {'G': 1, 'U': 1}})
    assert pool(result, seat) == {'G': 1, 'U': 1}
    assert sum(source.id in call.args[1] for call in tapped.call_args_list) == 1
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_cost_paid_vector_taps_source_exactly_once(seat):
    state = position(seat)
    source = add(state, 'Crystal Quarry', seat)
    state.players[seat].mana_pool['C'] = 5
    spec = next(s for s in mana_ability_specs(source, state) if s[1] == '{5}, {T}')
    before = serialize_match_snapshot(state)
    with patch.object(resource_events, 'tap_permanents', wraps=resource_events.tap_permanents) as tapped:
        result = checked_action(state, RulesEngine(), seat, {
            'type': 'activate_mana_ability', 'card_id': source.id,
            'ability_index': spec[0], 'color': 'R'})
    assert pool(result, seat) == {c: 1 for c in 'WUBRG'}
    assert sum(source.id in call.args[1] for call in tapped.call_args_list) == 1
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_failed_native_vector_cast_does_not_tap_or_spend(seat):
    ROWS['Merfolk Trickster'] = next(row for row in json.loads(
        (Path(__file__).parent / 'fixtures/produced_type_mana.json').read_text())
        if row['name'] == 'Merfolk Trickster')
    state = position(seat)
    source = add(state, 'Simic Growth Chamber', seat)
    spell = add(state, 'Merfolk Trickster', seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id})
    assert serialize_match_snapshot(state) == before
    assert not state.cards[source.id].tapped
