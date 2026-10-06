"""Canonical singleton production; no fabricated entry or activation choices."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.test_additive_mana import ROWS, position, add, aura, activate
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands, count_untapped_lands_by_color
from rules_engine.mana_abilities import mana_ability_views
from rules_engine.mana_triggers import fixed_mana_triggers, produced_type_clauses

ROWS.update({row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/produced_type_mana.json').read_text())})
GLOBAL_SOURCES = ['Mana Flare', 'Heartbeat of Spring', 'Dictate of Karametra']
NISSA = 'Nissa, Who Shakes the World'
REFLECTION = 'Mana Reflection'
SPHERE = 'Damping Sphere'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('trigger_name', GLOBAL_SOURCES)
@pytest.mark.parametrize('route', ['activate', 'tap_land_for_mana', 'tap_lands_bulk', 'auto_pay'])
@pytest.mark.parametrize('land_name,extras,expected,snow,color,spell_name', [
    ('Forest', [], {'G': 2}, {}, 'G', 'Rampant Growth'),
    ('Island', [], {'U': 2}, {}, 'U', 'Merfolk Trickster'),
    ('Forest', [REFLECTION], {'G': 3}, {}, 'G', 'Rampant Growth'),
    ('Forest', [NISSA], {'G': 3}, {}, 'G', 'Rampant Growth'),
    ('Forest', [NISSA, REFLECTION], {'G': 4}, {}, 'G', 'Rampant Growth'),
    ('Forest', [REFLECTION, SPHERE], {'C': 2}, {}, 'C', 'Mind Stone'),
    ('Forest', [REFLECTION, SPHERE, NISSA], {'C': 2, 'G': 1}, {}, 'C', 'Matter Reshaper'),
    ('Snow-Covered Forest', [NISSA], {'G': 3}, {'G': 1}, 'G', 'Rampant Growth'),
    ('Snow-Covered Forest', [REFLECTION, NISSA], {'G': 4}, {'G': 2}, 'G', 'Rampant Growth'),
    ('Snow-Covered Forest', [REFLECTION, SPHERE, NISSA], {'C': 2, 'G': 1}, {'C': 1}, 'C', 'Matter Reshaper'),
])
def test_singleton_type_routes_casting_and_provenance_agree(seat, trigger_name, route, land_name, extras, expected, snow, color, spell_name):
    state = position(seat)
    land = add(state, land_name, seat)
    trigger = add(state, trigger_name, 3-seat)
    for name in extras:
        add(state, name, 3-seat if name == SPHERE else seat)
    spell = add(state, spell_name, seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    assert produced_type_clauses(trigger.oracle_text) == 1
    view = next(v for v in mana_ability_views(state, land) if color in v['outputs'])
    assert view['output_bundles'][color] == expected
    assert count_untapped_lands_by_color(state, seat)['ANY'] == sum(expected.values())
    cost = ''.join('{'+c+'}' for c, n in expected.items() for _ in range(n))
    assert can_pay_with_pool_and_lands(state, seat, cost)
    assert not can_pay_with_pool_and_lands(state, seat, cost+'{1}')
    if snow:
        snow_count = sum(snow.values())
        assert can_pay_with_pool_and_lands(state, seat, '{S}'*snow_count+'{1}'*(sum(expected.values())-snow_count))
        assert not can_pay_with_pool_and_lands(state, seat, '{S}'*(snow_count+1))
    assert can_pay_with_pool_and_lands(state, seat, spell.mana_cost, spell_types=set(spell.types))
    assert any(m['type'] == 'cast_spell' and m.get('card_id') == spell.id
               for m in RulesEngine().legal_moves(state, seat))
    assert serialize_match_snapshot(state) == before
    cast = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id})
    assert cast.cards[spell.id].zone == Zone.STACK
    if route == 'auto_pay':
        assert auto_pay_cost(state, seat, cost)
        assert not any(state.players[seat].mana_pool.values())
        assert not any(state.players[seat].snow_mana_pool.values())
    elif route == 'activate':
        state = activate(state, seat, land, color)
    else:
        action = {'type': route, 'color': color, **({'card_id': land.id} if route == 'tap_land_for_mana'
                  else {'land_name': land.name, 'count': 1})}
        state = checked_action(state, RulesEngine(), seat, action)
    if route != 'auto_pay':
        assert {c:n for c,n in state.players[seat].mana_pool.items() if n} == expected
        assert {c:n for c,n in state.players[seat].snow_mana_pool.items() if n} == snow
        assert not state.players[seat].restricted_mana_pool
    assert state.cards[land.id].tapped and not state.stack
    assert not state.pending_mechanic_choice and not state.pending_trigger_order
    assert not any(state.players[3-seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('trigger_name', GLOBAL_SOURCES)
def test_snow_addition_is_not_snow_and_suppression_removes_only_bonus(seat, trigger_name):
    state = position(seat)
    land = add(state, 'Snow-Covered Forest', seat)
    trigger = add(state, trigger_name, 3-seat)
    assert can_pay_with_pool_and_lands(state, seat, '{S}{G}')
    assert not can_pay_with_pool_and_lands(state, seat, '{S}{S}')
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, '{S}{G}')
    assert not any(paid.players[seat].mana_pool.values())
    resolve_effect(state, seat, 'temporary_ability_loss', {'target_card_id': trigger.id})
    assert not can_pay_with_pool_and_lands(state, seat, '{S}{G}')
    state = activate(state, seat, land, 'G')
    assert state.players[seat].mana_pool['G'] == state.players[seat].snow_mana_pool['G'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('land_name', ['Tropical Island', 'Phyrexian Tower'])
def test_unannounced_modal_type_or_departure_cost_is_not_guessed(seat, land_name):
    state = position(seat)
    land = add(state, land_name, seat)
    add(state, 'Mana Flare', seat)
    before = serialize_match_snapshot(state)
    assert fixed_mana_triggers(state, land) == []
    assert serialize_match_snapshot(state) == before
    color = 'U' if land_name == 'Tropical Island' else 'C'
    state = activate(state, seat, land, color)
    assert state.players[seat].mana_pool[color] == 1
    assert sum(state.players[seat].mana_pool.values()) == 1
    assert not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_nonland_and_nonmana_taps_do_not_trigger_global_land_production(seat):
    from rules_engine.resource_events import tap_permanents
    state = position(seat)
    creature = add(state, 'Llanowar Elves', seat)
    add(state, 'Mana Flare', seat)
    state = activate(state, seat, creature, 'G')
    assert state.players[seat].mana_pool['G'] == 1
    land = add(state, 'Forest', seat)
    pool = dict(state.players[seat].mana_pool)
    tap_permanents(state, [land.id])
    assert state.players[seat].mana_pool == pool


@pytest.mark.parametrize('seat', [1, 2])
def test_multiple_global_sources_each_add_one_not_base_amount(seat):
    state = position(seat)
    land = add(state, 'Forest', seat)
    for name in GLOBAL_SOURCES:
        add(state, name, 3-seat)
    add(state, REFLECTION, seat)
    add(state, NISSA, seat)
    assert can_pay_with_pool_and_lands(state, seat, '{G}{G}{G}{G}{G}{G}')
    assert not can_pay_with_pool_and_lands(state, seat, '{7}')
    state = activate(state, seat, land, 'G')
    assert state.players[seat].mana_pool['G'] == 6 and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_captured_produced_type_bonus_survives_trigger_departure(seat):
    from rules_engine.mana_triggers import mana_tap_scope, resolve_mana_triggers
    from rules_engine.resource_events import tap_permanents
    state = position(seat)
    land = add(state, 'Forest', seat)
    trigger = add(state, 'Mana Flare', seat)
    with mana_tap_scope(state, land) as captured:
        tap_permanents(state, [land.id])
        resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': trigger.id})
    assert len(captured) == 1
    resolve_mana_triggers(state, captured)
    assert state.players[seat].mana_pool['G'] == 1
    land.tapped = False
    assert fixed_mana_triggers(state, land) == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Utopia Sprawl', 'Verdant Haven'])
def test_absent_stored_or_unannounced_any_color_remains_unsupported(seat, name):
    state = position(seat)
    land = add(state, 'Forest', seat)
    if name == 'Utopia Sprawl':
        from rules_engine.attachments import attachment_target_is_legal
        card = add(state, name, seat, Zone.HAND)
        assert not attachment_target_is_legal(state, card, land.id)
        assert getattr(card, 'chosen_color', None) is None
    else:
        aura(state, name, seat, land)
    before = serialize_match_snapshot(state)
    assert fixed_mana_triggers(state, land) == []
    assert not can_pay_with_pool_and_lands(state, seat, '{G}{G}')
    assert serialize_match_snapshot(state) == before
    state = activate(state, seat, land, 'G')
    assert state.players[seat].mana_pool['G'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source_name,aura_name,color', [
    ('Tropical Island', 'Spreading Seas', 'U'),
    ('Llanowar Elves', 'Song of the Dryads', 'G'),
])
def test_effective_land_type_and_intrinsic_ability_determine_singleton(seat, source_name, aura_name, color):
    state = position(seat)
    source = add(state, source_name, seat)
    add(state, 'Mana Flare', 3-seat)
    aura(state, aura_name, 3-seat, source)
    assert can_pay_with_pool_and_lands(state, seat, '{'+color+'}{'+color+'}')
    state = activate(state, seat, source, color)
    assert state.players[seat].mana_pool[color] == 2
    assert not state.stack and not state.pending_mechanic_choice
