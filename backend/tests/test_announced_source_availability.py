"""Canonical source-consumption witnesses; requires the frozen overlap fixture.

These are positive requirements, without xfails. Run before/after with identical
fixtures; expected baseline failures are evidence, not a passing qualification.
"""
import pytest

from ai.agent import AIAgent
from ai.mana_resource_policy import _can_pay
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.cast_choice import available_cast_options_and_hints, build_cast_hints
from rules_engine.costs import check_cost_option_available, collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.mana import _payment_requirements, _spell_payment_plan, can_pay_with_pool_and_lands
from rules_engine.move_generator import _cost_option_view
from tests.test_spell_cost_overlap_investigation import add, position, source_overlap, unchanged_root


ROUTES = ('planner', 'mana_affordability', 'cost_option', 'cast_options',
          'move_generation', 'ai_card_affordability', 'resource_card_affordability')


def source_position(seat, name, has_fuel=False):
    state = position(seat)
    add(state, 'Skirge Familiar', seat)
    if name == 'Village Rites':
        add(state, 'Raging Goblin', seat)
    else:
        add(state, 'Island', seat, Zone.GRAVEYARD)
    if has_fuel:
        add(state, 'Swamp', seat, Zone.HAND)
    spell = add(state, name, seat, Zone.HAND)
    return state, spell


def witness(route, state, spell, seat):
    option = next(o for o in collect_cost_options(state, seat, spell) if o.id == 'base')
    kwargs = dict(card_name=spell.name, spell_types=set(spell.types),
                  oracle_text=spell.oracle_text, source_card_id=spell.id,
                  cast_resource_card=spell)
    if route == 'planner':
        req = _payment_requirements(spell.mana_cost, False, 0, 0, 0)[0]
        return _spell_payment_plan(state, seat, req, payment_context=('spell', set(spell.types)),
                                   oracle_text=spell.oracle_text, source_card_id=spell.id,
                                   card=spell) is not None
    if route == 'mana_affordability':
        return can_pay_with_pool_and_lands(state, seat, spell.mana_cost, **kwargs)
    if route == 'cost_option':
        return check_cost_option_available(state, seat, spell, option)
    if route == 'cast_options':
        return bool(available_cast_options_and_hints(state, spell, seat)[0])
    if route == 'move_generation':
        return any(m['type'] == 'cast_spell' and m.get('card_id') == spell.id
                   for m in RulesEngine().legal_moves(state, seat))
    if route == 'ai_card_affordability':
        return AIAgent(archetype='Control', difficulty='master')._can_pay_card_cost(state, seat, spell)
    if route == 'resource_card_affordability':
        return _can_pay(state, seat, spell.mana_cost, spell)
    raise AssertionError(route)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Cling to Dust'])
@pytest.mark.parametrize('route', ROUTES)
def test_source_only_hand_has_no_cast_payment_witness(seat, name, route):
    state, spell = source_position(seat, name)
    with unchanged_root(state):
        assert not witness(route, state, spell, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Cling to Dust'])
@pytest.mark.parametrize('route', ROUTES)
def test_distinct_printed_hand_card_can_supply_mana(seat, name, route):
    state, spell = source_position(seat, name, has_fuel=True)
    with unchanged_root(state):
        assert witness(route, state, spell, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Cling to Dust'])
def test_materialized_stale_canonical_intent_is_atomically_rejected(seat, name):
    state, spell = source_position(seat, name)
    options = collect_cost_options(state, seat, spell)
    # Reuse actual presentation builders for a stale intent. Availability may
    # already refuse it after a fix; materialization is not itself admission.
    move = {'type': 'cast_spell', 'card_id': spell.id, 'card_name': spell.name,
            'mana_cost': spell.mana_cost,
            'cost_options': [_cost_option_view(o, state, seat, spell.id) for o in options],
            'target_hints': build_cast_hints(state, spell, seat)}
    with unchanged_root(state):
        action = AIAgent(archetype='Control', difficulty='master')._materialize_action(state, move, seat)
        if not action.get('_invalid_ai_choice'):
            with pytest.raises(ActionRejected):
                checked_action(state, RulesEngine(), seat, action)


@pytest.mark.parametrize('seat', [1, 2])
def test_reservation_guards_consumption_not_ordinary_tap_mana(seat):
    state = position(seat)
    forest = add(state, 'Forest', seat)
    spell = add(state, 'Crop Rotation', seat, Zone.HAND)
    with unchanged_root(state):
        assert can_pay_with_pool_and_lands(state, seat, spell.mana_cost,
            source_card_id=spell.id, cast_resource_card=spell,
            reserved_card_ids=[spell.id, forest.id])


@pytest.mark.parametrize('seat', [1, 2])
def test_nonspell_payment_keeps_legitimate_hand_discard_resource(seat):
    state = position(seat)
    add(state, 'Skirge Familiar', seat)
    card = add(state, 'Swamp', seat, Zone.HAND)
    with unchanged_root(state):
        assert can_pay_with_pool_and_lands(state, seat, '{B}',
                                          payment_kind='activation', source_card_id=card.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_major_threat_probe_cannot_use_the_threat_as_mana_fuel(seat):
    state = position(seat)
    state.turn = 5
    add(state, 'Skirge Familiar', seat)
    add(state, 'Skirge Familiar', seat, Zone.HAND)
    state.players[seat].mana_pool['C'] = 4
    with unchanged_root(state):
        assert not AIAgent(archetype='Control', difficulty='master')._can_deploy_major_threat(state, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('has_fuel', [False, True])
def test_discard_cost_and_mana_need_disjoint_hand_resources(seat, has_fuel):
    state, spell, _, _, _ = source_overlap(seat, 'Tormenting Voice', extra_fuel=has_fuel)
    option = next(o for o in collect_cost_options(state, seat, spell) if o.id == 'base')
    with unchanged_root(state):
        assert check_cost_option_available(state, seat, spell, option) == has_fuel
