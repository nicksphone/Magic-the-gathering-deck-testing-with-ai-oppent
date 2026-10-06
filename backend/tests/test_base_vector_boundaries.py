"""Canonical vector replacements, costs, provenance and rejection controls."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.test_mandatory_base_vectors import CASES, board
from tests.test_additive_mana import ROWS, add, aura, position
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands, mana_source_capacity
from rules_engine.mana_abilities import base_output_options, mana_ability_specs, mana_ability_views
from rules_engine.mana_triggers import fixed_mana_triggers

ROWS.update({r['name']: r for r in json.loads(
    (Path(__file__).parent / 'fixtures/base_vector_controls.json').read_text())})


def pool(state, seat):
    return {c: n for c, n in state.players[seat].mana_pool.items() if n}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', CASES)
@pytest.mark.parametrize('reflection,sphere,bonus', [
    (False, False, False), (True, False, False), (False, True, False),
    (True, True, False), (False, True, True), (True, False, True),
])
def test_vector_replacement_then_separate_bonus(seat, case, reflection, sphere, bonus):
    state, source, spell, base = board(seat, case)
    is_land = 'Land' in source.types
    if reflection:
        add(state, 'Mana Reflection', seat)
    if sphere:
        add(state, 'Damping Sphere', 3-seat)
    if bonus:
        if is_land:
            aura(state, 'Wild Growth', 3-seat, source)
        else:
            add(state, 'Leyline of Abundance', seat)
    expected = {'C': 1} if sphere and is_land else {c: n*(2 if reflection else 1) for c, n in base.items()}
    if bonus:
        expected['G'] = expected.get('G', 0)+1
    cost = ''.join(('{'+c+'}')*n for c, n in expected.items())
    before = serialize_match_snapshot(state)
    assert mana_source_capacity(state, source.id) == sum(expected.values())
    assert can_pay_with_pool_and_lands(state, seat, cost)
    assert not can_pay_with_pool_and_lands(state, seat, cost+'{1}')
    spec = next(s for s in mana_ability_specs(source, state) if s[1] == '{T}')
    vectors = base_output_options(state, source, spec)
    selector = next(iter(vectors))
    assert serialize_match_snapshot(state) == before
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, cost)
    assert not pool(paid, seat)
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_mana_ability', 'card_id': source.id,
        'ability_index': spec[0], 'color': selector})
    assert pool(state, seat) == expected
    assert state.cards[source.id].tapped
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reflection', [False, True])
def test_paid_five_color_base_pays_cost_and_taps_once(seat, reflection):
    state = position(seat)
    source = add(state, 'Crystal Quarry', seat)
    state.players[seat].mana_pool['C'] = 5
    if reflection:
        add(state, 'Mana Reflection', seat)
    spec = next(s for s in mana_ability_specs(source, state) if s[1] == '{5}, {T}')
    cost = '{W}{U}{B}{R}{G}'
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, cost)
    assert serialize_match_snapshot(state) == before
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, cost)
    assert pool(paid, seat) == ({c: 1 for c in 'WUBRG'} if reflection else {})
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_mana_ability', 'card_id': source.id,
        'ability_index': spec[0], 'color': 'U'})
    assert pool(state, seat) == {c: 2 if reflection else 1 for c in 'WUBRG'}
    assert state.cards[source.id].tapped
    assert sum('activates Crystal Quarry' in line for line in state.log) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_self_sacrifice_vector_survives_cost_departure(seat):
    state = position(seat)
    source = add(state, 'Composite Golem', seat)
    source.summoning_sick = True
    source.tapped = True
    add(state, 'Mana Reflection', seat)
    add(state, 'Leyline of Abundance', seat)
    cost = '{W}{U}{B}{R}{G}'
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, cost)
    assert not can_pay_with_pool_and_lands(state, seat, cost+'{1}')
    assert serialize_match_snapshot(state) == before
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, cost)
    assert paid.cards[source.id].zone == Zone.GRAVEYARD
    assert not pool(paid, seat)
    view = mana_ability_views(state, source)[0]
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_mana_ability', 'card_id': source.id,
        'ability_index': view['ability_index'], 'color': 'G'})
    assert pool(state, seat) == {c: 1 for c in 'WUBRG'}
    assert state.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('failure', ['tapped', 'wrong_controller', 'wrong_color', 'unfunded_cost', 'sick', 'suppressed'])
def test_rejected_vector_actions_are_atomic(seat, failure):
    state = position(seat)
    name = 'Crystal Quarry' if failure == 'unfunded_cost' else 'Gyre Engineer'
    source = add(state, name, seat)
    spec = next(s for s in mana_ability_specs(source, state) if
                s[1] == ('{5}, {T}' if failure == 'unfunded_cost' else '{T}'))
    if failure == 'tapped':
        source.tapped = True
    if failure == 'sick':
        source.summoning_sick = True
    if failure == 'suppressed':
        add(state, 'Dress Down', 3-seat)
    before = serialize_match_snapshot(state)
    with pytest.raises(Exception):
        checked_action(state, RulesEngine(), 3-seat if failure == 'wrong_controller' else seat, {
            'type': 'activate_mana_ability', 'card_id': source.id,
            'ability_index': spec[0], 'color': 'W' if failure == 'wrong_color' else 'U'})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_snow_modal_base_is_not_summed_for_sphere(seat):
    state = position(seat)
    source = add(state, 'Frost Marsh', seat)
    add(state, 'Damping Sphere', 3-seat)
    add(state, 'Mana Flare', seat)
    before = serialize_match_snapshot(state)
    assert not fixed_mana_triggers(state, source)
    assert can_pay_with_pool_and_lands(state, seat, '{S}')
    assert not can_pay_with_pool_and_lands(state, seat, '{S}{S}')
    assert not can_pay_with_pool_and_lands(state, seat, '{U}{B}')
    assert serialize_match_snapshot(state) == before
    view = mana_ability_views(state, source)[0]
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_mana_ability', 'card_id': source.id,
        'ability_index': view['ability_index'], 'color': 'U'})
    assert pool(state, seat) == {'U': 1}
    assert state.players[seat].snow_mana_pool.get('U') == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reflection,sphere', [(False, False), (True, False), (True, True)])
def test_restricted_base_and_same_color_unrestricted_bonus(seat, reflection, sphere):
    state = position(seat)
    source = add(state, "Mishra's Workshop", seat)
    add(state, 'Mana Flare', 3-seat)
    if reflection:
        add(state, 'Mana Reflection', seat)
    if sphere:
        add(state, 'Damping Sphere', 3-seat)
    base = 1 if sphere else 6 if reflection else 3
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{C}', spell_types={'Instant'})
    assert not can_pay_with_pool_and_lands(state, seat, '{C}{C}', spell_types={'Instant'})
    assert can_pay_with_pool_and_lands(state, seat, '{'+str(base+1)+'}', spell_types={'Artifact'})
    assert serialize_match_snapshot(state) == before
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, '{C}', spell_types={'Instant'})
    assert pool(paid, seat) == {'C': base}
    assert sum(lot['amount'] for lot in paid.players[seat].restricted_mana_pool) == base


@pytest.mark.parametrize('seat', [1, 2])
def test_unsupported_generic_spending_restriction_is_not_discarded(seat):
    state = position(seat)
    source = add(state, 'Jegantha, the Wellspring', seat)
    before = serialize_match_snapshot(state)
    assert not mana_ability_views(state, source)
    assert not can_pay_with_pool_and_lands(state, seat, '{W}{U}{B}{R}{G}')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reflection', [False, True])
def test_modal_artifact_stays_alternative_not_rg_vector(seat, reflection):
    state = position(seat)
    source = add(state, 'Firewild Borderpost', seat)
    if reflection:
        add(state, 'Mana Reflection', seat)
    # Native mandatory production elsewhere selects the bundle planner globally.
    add(state, 'Simic Growth Chamber', seat).tapped = True
    cost = '{G}{G}' if reflection else '{G}'
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, cost)
    assert not can_pay_with_pool_and_lands(state, seat, '{R}{G}')
    assert serialize_match_snapshot(state) == before
    view = mana_ability_views(state, source)[0]
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_mana_ability', 'card_id': source.id,
        'ability_index': view['ability_index'], 'color': 'G'})
    assert pool(state, seat) == {'G': 2 if reflection else 1}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('sphere', [False, True])
def test_produced_type_trigger_requires_proven_post_replacement_singleton(seat, sphere):
    state = position(seat)
    source = add(state, 'Simic Growth Chamber', seat)
    flare = add(state, 'Mana Flare', 3-seat)
    if sphere:
        add(state, 'Damping Sphere', seat)
    captured = [r for r in fixed_mana_triggers(state, source) if r[1] == flare.id]
    assert bool(captured) == sphere
    view = mana_ability_views(state, source)[0]
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_mana_ability', 'card_id': source.id,
        'ability_index': view['ability_index'], 'color': 'C' if sphere else 'U'})
    assert pool(state, seat) == ({'C': 2} if sphere else {'G': 1, 'U': 1})
    assert not state.pending_mechanic_choice and not state.stack
