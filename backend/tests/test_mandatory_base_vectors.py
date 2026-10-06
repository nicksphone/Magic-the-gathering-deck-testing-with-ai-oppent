"""Canonical mandatory base vectors and public before/after evidence capture."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.test_additive_mana import ROWS, add, position
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.costs import collect_cost_options, check_cost_option_available
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from rules_engine.mana_abilities import mana_ability_specs, mana_ability_views

ROWS.update({r['name']: r for r in json.loads(
    (Path(__file__).parent / 'fixtures/mandatory_base_vectors.json').read_text())})
CASES = [
    ('Simic Growth Chamber', 'Growth Spiral', {'G': 1, 'U': 1}),
    ('Gruul Turf', 'Zhur-Taa Druid', {'R': 1, 'G': 1}),
    ('Azorius Chancery', 'Watcher of the Spheres', {'W': 1, 'U': 1}),
    ('Gyre Engineer', 'Growth Spiral', {'G': 1, 'U': 1}),
]


def board(seat, case):
    source_name, spell_name, vector = case
    state = position(seat)
    source = add(state, source_name, seat)
    spell = add(state, spell_name, seat, Zone.HAND)
    return state, source, spell, vector


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', CASES)
def test_mandatory_vector_affordability_and_legal_cast(seat, case):
    state, source, spell, vector = board(seat, case)
    before = serialize_match_snapshot(state)
    payable = can_pay_with_pool_and_lands(state, seat, spell.mana_cost)
    announced = check_cost_option_available(state, seat, spell,
        collect_cost_options(state, seat, spell)[0])
    legal = RulesEngine().legal_moves(state, seat)
    assert serialize_match_snapshot(state) == before
    assert payable, 'Mandatory simultaneous base vector is unavailable'
    assert announced
    assert any(m['type'] == 'cast_spell' and m.get('card_id') == spell.id for m in legal)
    for color in vector:
        assert not can_pay_with_pool_and_lands(state, seat, '{'+color+'}{'+color+'}')
    assert can_pay_with_pool_and_lands(state, seat, '{2}')
    assert not can_pay_with_pool_and_lands(state, seat, '{3}')
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, spell.mana_cost)
    assert paid.cards[source.id].tapped
    assert not any(paid.players[seat].mana_pool.values())
    state = checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': spell.id})
    assert state.stack


ROUTES = [(case, route) for case in CASES for route in
    (['activate'] if case[0] == 'Gyre Engineer' else ['activate', 'tap', 'bulk'])]


def tap_action(state, source, route, vector):
    color = next(iter(vector))
    if route == 'activate':
        spec = next(s for s in mana_ability_specs(source, state) if s[1] == '{T}')
        return {'type': 'activate_mana_ability', 'card_id': source.id,
                'ability_index': spec[0], 'color': color}
    if route == 'tap':
        return {'type': 'tap_land_for_mana', 'card_id': source.id, 'color': color}
    return {'type': 'tap_lands_bulk', 'land_name': source.name, 'count': 1, 'color': color}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case,route', ROUTES)
def test_checked_tap_must_emit_entire_base_vector(seat, case, route):
    state, source, spell, vector = board(seat, case)
    state = checked_action(state, RulesEngine(), seat, tap_action(state, source, route, vector))
    assert {c: n for c, n in state.players[seat].mana_pool.items() if n} == vector
    assert state.cards[source.id].tapped
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source_name', ['Forest', 'Tropical Island'])
def test_single_color_and_modal_controls_do_not_become_mandatory_vectors(seat, source_name):
    state = position(seat)
    source = add(state, source_name, seat)
    before = serialize_match_snapshot(state)
    assert mana_ability_views(state, source)
    assert can_pay_with_pool_and_lands(state, seat, '{G}')
    assert not can_pay_with_pool_and_lands(state, seat, '{G}{U}')
    assert not can_pay_with_pool_and_lands(state, seat, '{G}{G}')
    assert serialize_match_snapshot(state) == before


def retain_public_repro(destination):
    results = []
    for seat in (1, 2):
        for case in CASES:
            state, source, spell, vector = board(seat, case)
            before = serialize_match_snapshot(state)
            row = {'seat': seat, 'source': source.name, 'expected_base': vector,
                   'snapshot': before, 'views': mana_ability_views(state, source),
                   'legal': RulesEngine().legal_moves(state, seat),
                   'affordable': can_pay_with_pool_and_lands(state, seat, spell.mana_cost),
                   'announced': check_cost_option_available(state, seat, spell,
                       collect_cost_options(state, seat, spell)[0]), 'attempts': []}
            assert serialize_match_snapshot(state) == before
            actions = [tap_action(state, source, route, vector) for route in
                       (['activate'] if case[0] == 'Gyre Engineer' else ['activate', 'tap', 'bulk'])]
            actions.append({'type': 'cast_spell', 'card_id': spell.id})
            for action in actions:
                trial = deepcopy(state)
                try:
                    trial = checked_action(trial, RulesEngine(), seat, action)
                    result = {'accepted': True, 'snapshot': serialize_match_snapshot(trial)}
                except Exception as error:
                    result = {'accepted': False, 'exception': type(error).__name__,
                              'message': str(error),
                              'input_unchanged': serialize_match_snapshot(trial) == before}
                row['attempts'].append({'action': action, **result})
            paid = deepcopy(state)
            row['auto_paid'] = auto_pay_cost(paid, seat, spell.mana_cost)
            row['failed_auto_pay_unchanged'] = serialize_match_snapshot(paid) == before
            results.append(row)
    Path(destination).write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    import sys
    retain_public_repro(sys.argv[1])
