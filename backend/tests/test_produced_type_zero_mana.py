"""No produced type exists at zero; another source's bonus is not land production."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.test_produced_type_mana import ROWS, position, add, aura, activate
from game_state.serializers import serialize_match_snapshot
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from rules_engine.mana_triggers import fixed_mana_triggers

ROWS.update({row['name']:row for row in json.loads(
    (Path(__file__).parent / 'fixtures/produced_type_zero_mana.json').read_text())})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('context', ['zero', 'other_source_bonus', 'nonzero'])
def test_produced_type_requires_positive_base_production(seat, context):
    state = position(seat)
    land = add(state, 'Tolarian Academy', seat)
    flare = add(state, 'Mana Flare', 3-seat)
    if context == 'other_source_bonus':
        aura(state, 'Wild Growth', 3-seat, land)
    elif context == 'nonzero':
        add(state, 'Mind Stone', seat)
    before = serialize_match_snapshot(state)
    captured = fixed_mana_triggers(state, land)
    flare_rows = [row for row in captured if row[1] == flare.id]
    assert bool(flare_rows) == (context == 'nonzero')
    assert can_pay_with_pool_and_lands(state, seat, '{U}{U}') == (context == 'nonzero')
    assert not can_pay_with_pool_and_lands(state, seat, '{U}{U}{U}')
    assert can_pay_with_pool_and_lands(state, seat, '{G}') == (context == 'other_source_bonus')
    assert not can_pay_with_pool_and_lands(state, seat, '{G}{G}')
    paid = deepcopy(state)
    cost = '{G}' if context == 'other_source_bonus' else '{U}{U}'
    assert auto_pay_cost(paid, seat, cost) == (context != 'zero')
    assert serialize_match_snapshot(state) == before
    state = activate(state, seat, land, 'U')
    assert state.players[seat].mana_pool.get('U', 0) == (2 if context == 'nonzero' else 0)
    assert state.players[seat].mana_pool.get('G', 0) == (1 if context == 'other_source_bonus' else 0)
    assert not state.stack and not state.pending_mechanic_choice
    assert not any(state.players[seat].snow_mana_pool.values())
