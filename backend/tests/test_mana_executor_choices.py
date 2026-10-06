"""Actual canonical selected costs and bounded single-color filterland outputs."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.test_additive_mana import ROWS, position, add
from tests.test_produced_type_mana import ROWS as PRODUCED_ROWS
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.costs import parse_activated_cost
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from rules_engine.mana_abilities import activate_mana_ability, mana_ability_specs, mana_ability_views

ROWS.update({r['name']: r for r in json.loads(
    (Path(__file__).parent / 'fixtures/mana_executor_choices.json').read_text())})


def spec(state, source, fragment):
    return next(s for s in mana_ability_specs(source, state) if fragment in s[1])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('output', ['B', 'R'])
@pytest.mark.parametrize('payment', ['B', 'R'])
def test_graven_cairns_explicit_hybrid_and_complete_mono_output(seat, output, payment):
    state = position(seat)
    source = add(state, 'Graven Cairns', seat)
    state.players[seat].mana_pool.update(B=1, R=1)
    ability = spec(state, source, '{B/R}')
    before = serialize_match_snapshot(state)
    view = next(v for v in mana_ability_views(state, source) if v['ability_index'] == ability[0])
    assert view['outputs'] == {'B': 2, 'R': 2}
    assert view['output_bundles']['B'] == {'B': 2}
    assert view['output_bundles']['R'] == {'R': 2}
    assert {'color': 'B', 'output_bundle': {'B': 1, 'R': 1}} in view['output_options']
    assert serialize_match_snapshot(state) == before
    assert activate_mana_ability(state, seat, source.id, ability[0], output,
        hybrid_choices=[payment], payment_choices={}, output_bundle={output: 2})
    expected = {'B': 1, 'R': 1}
    expected[payment] -= 1
    expected[output] += 2
    assert state.players[seat].mana_pool['B'] == expected['B']
    assert state.players[seat].mana_pool['R'] == expected['R']
    assert state.cards[source.id].tapped
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', ['unfunded_branch', 'empty_branch', 'wrong_branch', 'wrong_count', 'not_list', 'mixed_output'])
def test_hybrid_rejection_never_falls_back_to_another_branch(seat, variant):
    state = position(seat)
    source = add(state, 'Graven Cairns', seat)
    state.players[seat].mana_pool['R'] = 1
    ability = spec(state, source, '{B/R}')
    choices = {'unfunded_branch': ['B'], 'empty_branch': [], 'wrong_branch': ['U'],
               'wrong_count': ['R', 'B'], 'not_list': 'R', 'mixed_output': ['R']}[variant]
    before = serialize_match_snapshot(state)
    assert not activate_mana_ability(state, seat, source.id, ability[0],
        'BR' if variant == 'mixed_output' else 'B', hybrid_choices=choices)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_ambiguous_manual_output_requires_bundle_but_planner_still_works(seat):
    state = position(seat)
    source = add(state, 'Graven Cairns', seat)
    state.players[seat].mana_pool['R'] = 1
    ability = spec(state, source, '{B/R}')
    before = serialize_match_snapshot(state)
    assert not activate_mana_ability(state, seat, source.id, ability[0], 'B')
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{B}{B}')


@pytest.mark.parametrize('seat', [1, 2])
def test_tower_binds_exact_other_creature_selection(seat):
    state = position(seat)
    source = add(state, 'Phyrexian Tower', seat)
    first = add(state, 'Llanowar Elves', seat)
    selected = add(state, 'Llanowar Elves', seat)
    ability = spec(state, source, 'Sacrifice')
    assert activate_mana_ability(state, seat, source.id, ability[0], 'B',
        payment_choices={'sacrifice_card_ids': [selected.id]})
    assert state.cards[first.id].zone == Zone.BATTLEFIELD
    assert state.cards[selected.id].zone == Zone.GRAVEYARD
    assert state.players[seat].mana_pool['B'] == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['missing', 'duplicate', 'foreign', 'reserved', 'unknown_key'])
def test_tower_explicit_invalid_selections_are_atomic(seat, invalid):
    state = position(seat)
    source = add(state, 'Phyrexian Tower', seat)
    creature = add(state, 'Llanowar Elves', seat)
    foreign = add(state, 'Llanowar Elves', 3-seat)
    ability = spec(state, source, 'Sacrifice')
    choices = {'missing': {}, 'duplicate': {'sacrifice_card_ids': [creature.id, creature.id]},
               'foreign': {'sacrifice_card_ids': [foreign.id]},
               'reserved': {'sacrifice_card_ids': [creature.id]},
               'unknown_key': {'wrong': [creature.id]}}[invalid]
    before = serialize_match_snapshot(state)
    assert not activate_mana_ability(state, seat, source.id, ability[0], 'B',
        payment_choices=choices, reserved_card_ids=[creature.id] if invalid == 'reserved' else [])
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_bog_witch_binds_exact_discard_and_pays_once(seat):
    state = position(seat)
    source = add(state, 'Bog Witch', seat)
    first = add(state, 'Forest', seat, Zone.HAND)
    selected = add(state, 'Island', seat, Zone.HAND)
    state.players[seat].mana_pool['B'] = 1
    ability = spec(state, source, 'Discard')
    before = serialize_match_snapshot(state)
    assert not activate_mana_ability(state, seat, source.id, ability[0], 'B', payment_choices={})
    assert serialize_match_snapshot(state) == before
    assert activate_mana_ability(state, seat, source.id, ability[0], 'B',
        payment_choices={'discard_card_ids': [selected.id]})
    assert state.cards[first.id].zone == Zone.HAND
    assert state.cards[selected.id].zone == Zone.GRAVEYARD
    assert state.players[seat].mana_pool['B'] == 3
    assert state.cards[source.id].tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('replacement', ['reflection', 'sphere'])
def test_filterland_base_replacements_are_not_flattened_choices(seat, replacement):
    state = position(seat)
    source = add(state, 'Graven Cairns', seat)
    state.players[seat].mana_pool['R'] = 1
    add(state, 'Mana Reflection' if replacement == 'reflection' else 'Damping Sphere', seat)
    ability = spec(state, source, '{B/R}')
    color = 'B'
    assert activate_mana_ability(state, seat, source.id, ability[0], color,
        hybrid_choices=['R'], output_bundle={'B': 2})
    assert state.players[seat].mana_pool.get('B' if replacement == 'reflection' else 'C') == (4 if replacement == 'reflection' else 1)
    assert not state.players[seat].mana_pool.get('R')


@pytest.mark.parametrize('seat', [1, 2])
def test_filterland_automatic_affordability_and_payment(seat):
    state = position(seat)
    source = add(state, 'Graven Cairns', seat)
    state.players[seat].mana_pool['R'] = 1
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{B}{B}')
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{B}{B}')
    assert state.cards[source.id].tapped
    assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_skirk_source_free_other_goblin_selection_is_actual_mana(seat):
    state = position(seat)
    source = add(state, 'Skirk Prospector', seat)
    selected = add(state, 'Skirk Prospector', seat)
    nongoblin = add(state, 'Llanowar Elves', seat)
    source.summoning_sick = selected.summoning_sick = True
    ability = mana_ability_specs(source, state)[0]
    assert parse_activated_cost(ability[1]).sacrifice_kind == 'subtype_goblin'
    assert mana_ability_views(state, source)
    before = serialize_match_snapshot(state)
    assert not activate_mana_ability(state, seat, source.id, ability[0], 'R',
        payment_choices={'sacrifice_card_ids': [nongoblin.id]})
    assert serialize_match_snapshot(state) == before
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, '{R}')
    assert activate_mana_ability(state, seat, source.id, ability[0], 'R',
        payment_choices={'sacrifice_card_ids': [selected.id]})
    assert state.cards[selected.id].zone == Zone.GRAVEYARD
    assert state.cards[source.id].zone == Zone.BATTLEFIELD
    assert not state.cards[source.id].tapped
    assert state.players[seat].mana_pool['R'] == 1
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,cost,mixed', [
    ('Graven Cairns', '{B/R}', {'B': 1, 'R': 1}),
    ('Flooded Grove', '{G/U}', {'G': 1, 'U': 1}),
])
@pytest.mark.parametrize('enhancement', ['none', 'reflection', 'sphere', 'aura'])
def test_complete_mixed_filterland_base_with_explicit_announcement(seat, name, cost, mixed, enhancement):
    state = position(seat)
    source = add(state, name, seat)
    payment = next(iter(mixed))
    state.players[seat].mana_pool[payment] = 1
    if enhancement == 'reflection':
        add(state, 'Mana Reflection', seat)
    if enhancement == 'sphere':
        add(state, 'Damping Sphere', seat)
    if enhancement == 'aura':
        from tests.test_additive_mana import aura
        aura(state, 'Wild Growth', 3-seat, source)
    ability = spec(state, source, cost)
    color = payment
    before = serialize_match_snapshot(state)
    view = next(v for v in mana_ability_views(state, source) if v['ability_index'] == ability[0])
    assert {'color': color, 'output_bundle': mixed} in view['output_options']
    assert serialize_match_snapshot(state) == before
    assert activate_mana_ability(state, seat, source.id, ability[0], color,
        output_bundle=mixed, hybrid_choices=[payment])
    expected = {'C': 1} if enhancement == 'sphere' else {c: n*(2 if enhancement == 'reflection' else 1) for c,n in mixed.items()}
    if enhancement == 'aura':
        expected['G'] = expected.get('G', 0)+1
    assert {c:n for c,n in state.players[seat].mana_pool.items() if n} == expected
    assert state.cards[source.id].tapped
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('bundle', [{}, {'B': True}, {'B': 0}, {'B': -1}, {'B': 100001},
    {'B': 1.0}, {'X': 2}, {1: 2}, {'B': 3}, {'B': 1, 'R': 2}])
def test_invalid_output_bundle_is_not_coerced(bundle):
    state = position(1)
    source = add(state, 'Graven Cairns', 1)
    state.players[1].mana_pool['R'] = 1
    ability = spec(state, source, '{B/R}')
    before = serialize_match_snapshot(state)
    assert not activate_mana_ability(state, 1, source.id, ability[0], 'B',
        hybrid_choices=['R'], output_bundle=bundle)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_base_anchor_is_not_final_replacement_or_bonus_color(seat):
    state = position(seat)
    source = add(state, 'Graven Cairns', seat)
    add(state, 'Damping Sphere', seat)
    state.players[seat].mana_pool['R'] = 1
    ability = spec(state, source, '{B/R}')
    before = serialize_match_snapshot(state)
    assert not activate_mana_ability(state, seat, source.id, ability[0], 'C',
        hybrid_choices=['R'], output_bundle={'B': 1, 'R': 1})
    assert serialize_match_snapshot(state) == before
    assert activate_mana_ability(state, seat, source.id, ability[0], 'B',
        hybrid_choices=['R'], output_bundle={'B': 1, 'R': 1})
    assert state.players[seat].mana_pool['C'] == 1
