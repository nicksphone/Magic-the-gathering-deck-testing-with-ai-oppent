"""Canonical color/type clauses must price the announced spell, not a suffix."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.costs import collect_cost_options, check_cost_option_available
from tests.test_graveyard_play_permissions import position
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_graveyard_cast_methods import RAW

DIRECTORY = Path(__file__).parent / 'fixtures/announced_costs'
ROWS = {row['name']: row for row in
        (json.loads(file.read_text()) for file in DIRECTORY.glob('*.json')
         if not file.name.endswith('.provenance.json'))}


def add(state, name, seat, zone=Zone.BATTLEFIELD, *, cards=ROWS):
    # Scryfall omits creature stat fields on noncreature cards.
    row = cards[name]
    return raw_add(state, name, seat, zone, cards={name: {
        **row, 'power': row.get('power'), 'toughness': row.get('toughness')}})


def cast(state, card, seat, **extra):
    return checked_action(state, RulesEngine(), seat,
                          {'type': 'cast_spell', 'card_id': card.id, **extra})


def test_canonical_downloads_match_provenance():
    assert len(ROWS) == 11
    for file in DIRECTORY.glob('*.json'):
        if file.name.endswith('.provenance.json'):
            continue
        provenance = json.loads(Path(str(file)+'.provenance.json').read_text())
        assert hashlib.sha256(file.read_bytes()).hexdigest() == provenance['sha256']


def test_cost_queries_accept_lightweight_views_without_oracle_metadata():
    from types import SimpleNamespace
    from rules_engine.hooks import CostContext, apply_cost_modifiers
    state = position(1)
    source = SimpleNamespace(id='lightweight', name='Forest', controller=1,
                             zone=Zone.BATTLEFIELD, types=['Land'])
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    context = apply_cost_modifiers(CostContext(player_id=1, card_name='Young Pyromancer',
        mana_cost='{1}{R}', state=state, spell_types={'Creature'}))
    assert context.generic_increase == context.generic_reduction == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_white_tax_is_not_applied_to_red_spell(seat):
    state = position(seat)
    add(state, 'Gloom', 3-seat, cards=ROWS)
    card = add(state, 'Young Pyromancer', seat, Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool = {'R': 1, 'C': 1}
    result = cast(state, card, seat)
    assert result.cards[card.id].zone == Zone.STACK
    assert next(item.payload['mana_spent'] for item in result.stack
                if item.source_card_id == card.id and 'mana_spent' in item.payload) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('owner_same', [True, False])
def test_color_discount_and_controller_scope(seat, owner_same):
    state = position(seat)
    add(state, 'Ruby Medallion', seat if owner_same else 3-seat, cards=ROWS)
    card = add(state, 'Young Pyromancer', seat, Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool = {'R': 1}
    before = serialize_match_snapshot(state)
    if owner_same:
        result = cast(state, card, seat)
        assert result.stack[-1].payload['mana_spent'] == 1
    else:
        with pytest.raises(ActionRejected):
            cast(state, card, seat)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_multicolor_familiar_clause_reduces_once_not_twice(seat):
    state = position(seat)
    add(state, 'Sunscape Familiar', seat, cards=ROWS)
    card = add(state, 'Hydroid Krasis', seat, Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool = {'G': 1, 'U': 1}
    # X=2 still requires one generic mana: being both colors is not two discounts.
    option = collect_cost_options(state, seat, card)[0]
    assert check_cost_option_available(state, seat, card, option, x_value=1)
    assert not check_cost_option_available(state, seat, card, option, x_value=2)
    result = cast(state, card, seat, targets={'x_value': 1})
    assert next(item.payload['mana_spent'] for item in result.stack
                if item.source_card_id == card.id and 'mana_spent' in item.payload) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_distinct_multicolor_clauses_stack_and_opponent_tax_applies(seat):
    state = position(seat)
    add(state, 'Grand Arbiter Augustin IV', seat, cards=ROWS)
    card = add(state, 'Reflector Mage', seat, Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool = {'W': 1, 'U': 1}
    result = cast(state, card, seat)
    assert result.stack[-1].payload['mana_spent'] == 2
    other = position(3-seat)
    add(other, 'Grand Arbiter Augustin IV', seat, cards=ROWS)
    spell = add(other, 'Young Pyromancer', 3-seat, Zone.HAND, cards=ROWS)
    other.players[3-seat].mana_pool = {'R': 1, 'C': 1}
    with pytest.raises(ActionRejected):
        cast(other, spell, 3-seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_prototype_is_colored_for_discount_checks_and_real_payment(seat):
    state = position(seat)
    add(state, 'Ugin, the Ineffable', seat, cards=ROWS)
    card = add(state, RAW['name'], seat, Zone.HAND, cards={RAW['name']: RAW})
    state.players[seat].mana_pool = {'C': 4}
    result = cast(state, card, seat, cost_choice={'id': 'base'})
    assert result.stack[-1].payload['mana_spent'] == 4
    state.players[seat].mana_pool = {'B': 1}
    option = next(cost for cost in collect_cost_options(state, seat, card) if cost.id == 'prototype')
    assert not check_cost_option_available(state, seat, card, option)
    with pytest.raises(ActionRejected):
        cast(state, card, seat, cost_choice={'id': 'prototype'})
    state.players[seat].mana_pool = {'B': 2}
    result = cast(state, card, seat, cost_choice={'id': 'prototype'})
    assert result.stack[-1].payload['mana_spent'] == 2
    restored = deserialize_match_snapshot(serialize_match_snapshot(result))
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(result)


@pytest.mark.parametrize('seat', [1, 2])
def test_suppressed_source_restores_after_cleanup(seat):
    from effects.registry import resolve_effect
    state = position(seat)
    source = add(state, 'Sunscape Familiar', seat)
    card = add(state, 'Hydroid Krasis', seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'U': 1}
    option = collect_cost_options(state, seat, card)[0]
    assert check_cost_option_available(state, seat, card, option, x_value=1)
    resolve_effect(state, 3-seat, 'temporary_ability_loss', {'target_card_id': source.id})
    assert not check_cost_option_available(state, seat, card, option, x_value=1)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine()._clear_marked_damage(state)
    assert check_cost_option_available(state, seat, state.cards[card.id], option, x_value=1)


@pytest.mark.parametrize('seat', [1, 2])
def test_tax_and_discount_combine_without_discounting_colored_symbols(seat):
    state = position(seat)
    add(state, 'Ruby Medallion', seat)
    add(state, 'Sphere of Resistance', 3-seat)
    card = add(state, 'Young Pyromancer', seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1}
    with pytest.raises(ActionRejected):
        cast(state, card, seat)
    state.players[seat].mana_pool = {'R': 1, 'C': 1}
    result = cast(state, card, seat)
    assert result.stack[-1].payload['mana_spent'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_devoid_uses_actual_color_not_mana_symbols(seat):
    rows = {row['name']: row for row in json.loads(
        (DIRECTORY.parent / 'qualified_spell_costs.json').read_text())}
    state = position(seat)
    add(state, 'Ugin, the Ineffable', seat)
    card = add(state, 'Benthic Infiltrator', seat, Zone.HAND, cards=rows)
    state.players[seat].mana_pool = {'U': 1}
    result = cast(state, card, seat)
    assert result.stack[-1].payload['mana_spent'] == 1


@pytest.mark.parametrize('clause', [
    'Red spells you cast cost {1} less to cast if you control an artifact.',
    'Blue creature spells you cast cost {1} less to cast.',
    'Colorless spells you cast cost {X} less to cast.',
    'If you gained life this turn, white spells cost {1} less to cast.',
])
def test_unknown_color_qualifiers_warn_instead_of_becoming_global(clause):
    from rules_engine.coverage import known_unsupported_mechanics
    from rules_engine.hooks import spell_cost_modifier
    assert spell_cost_modifier(clause) is None
    assert 'unsupported color-qualified spell cost' in known_unsupported_mechanics(clause)
