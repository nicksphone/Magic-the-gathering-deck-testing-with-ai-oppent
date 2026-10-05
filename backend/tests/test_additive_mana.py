"""Real Oracle rows on public board positions, never altered cards or decks."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchState, PlayerState, Step, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.attachments import attach_if_legal
from rules_engine.card_types import printed_card_types
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands, mana_source_outputs, count_untapped_lands_by_color
from rules_engine.mana_abilities import mana_ability_views
from rules_engine.mana_triggers import fixed_mana_clauses

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/additive_mana.json').read_text())}


def position(seat):
    return MatchState(id='canonical-additive-mana', players={
        n: PlayerState(id=n, name=f'Player {n}') for n in (1, 2)}, cards={}, stack=[],
        active_player=seat, priority_player=seat, step=Step.PRECOMBAT_MAIN,
        pregame_pending=False, kept_hands={1, 2}, turn=5)


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    raw = ROWS[name]
    card = CardInstance(id=state.allocate_object_id(), name=name, owner=seat, controller=seat,
        zone=zone, types=printed_card_types(raw['type_line']), type_line=raw['type_line'],
        oracle_text=raw['oracle_text'], mana_cost=raw['mana_cost'], colors=raw['colors'],
        power=int(raw['power']) if raw.get('power') is not None else None,
        toughness=int(raw['toughness']) if raw.get('toughness') is not None else None,
        loyalty=int(raw['loyalty']) if raw.get('loyalty') is not None else None,
        summoning_sick=False)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def aura(state, name, seat, target):
    card = add(state, name, seat)
    assert attach_if_legal(state, card.id, target.id)
    return card


def activate(state, seat, card, color, index=None):
    views = mana_ability_views(state, card)
    view = next(view for view in views if color in view['outputs'] and (index is None or view['ability_index'] == index))
    return checked_action(state, RulesEngine(), seat, {'type': 'activate_mana_ability',
        'card_id': card.id, 'ability_index': view['ability_index'], 'color': color})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source,color,enhancers,reflection,expected', [
    ('Forest', 'G', ['Nissa, Who Shakes the World'], False, {'G': 2}),
    ('Tropical Island', 'U', ['Nissa, Who Shakes the World'], False, {'U': 1, 'G': 1}),
    ('Island', 'U', ['Wild Growth'], False, {'U': 1, 'G': 1}),
    ('Island', 'U', ['Overgrowth'], False, {'U': 1, 'G': 2}),
    ('Tropical Island', 'U', ['Wild Growth', 'Overgrowth', 'Nissa, Who Shakes the World'], False, {'U': 1, 'G': 4}),
    ('Forest', 'G', ['Nissa, Who Shakes the World'], True, {'G': 3}),
    ('Tropical Island', 'U', ['Nissa, Who Shakes the World'], True, {'U': 2, 'G': 1}),
    ('Island', 'U', ['Wild Growth', 'Overgrowth'], True, {'U': 2, 'G': 3}),
])
def test_fixed_additions_are_separate_bundles_not_replacement_multiplication(seat, source, color, enhancers, reflection, expected):
    state = position(seat)
    land = add(state, source, seat)
    for name in enhancers:
        if name in {'Wild Growth', 'Overgrowth'}:
            aura(state, name, 3-seat, land)
        else:
            add(state, name, seat)
    if reflection:
        add(state, 'Mana Reflection', seat)
    before = serialize_match_snapshot(state)
    view = next(v for v in mana_ability_views(state, land) if color in v['outputs'])
    assert view['output_bundles'][color] == expected
    assert count_untapped_lands_by_color(state, seat)['ANY'] == sum(expected.values())
    assert serialize_match_snapshot(state) == before
    state = activate(state, seat, land, color)
    assert {c: n for c, n in state.players[seat].mana_pool.items() if n} == expected
    assert not state.stack and not state.pending_trigger_order and not state.pending_mechanic_choice
    assert not any(state.players[3-seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['activate', 'tap_land_for_mana', 'tap_lands_bulk', 'auto_pay'])
def test_all_tap_and_payment_callers_agree_on_mixed_output(seat, route):
    state = position(seat)
    land = add(state, 'Tropical Island', seat)
    add(state, 'Nissa, Who Shakes the World', seat)
    spell = add(state, 'Growth Spiral', seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, spell.mana_cost)
    assert not can_pay_with_pool_and_lands(state, seat, '{U}{U}')
    moves = RulesEngine().legal_moves(state, seat)
    assert any(m['type'] == 'cast_spell' and m.get('card_id') == spell.id for m in moves)
    assert serialize_match_snapshot(state) == before
    if route == 'auto_pay':
        assert auto_pay_cost(state, seat, spell.mana_cost)
        assert not any(state.players[seat].mana_pool.values())
    elif route == 'activate':
        state = activate(state, seat, land, 'U')
    else:
        action = {'type': route, 'color': 'U', **({'card_id': land.id} if route == 'tap_land_for_mana'
                    else {'land_name': land.name, 'count': 1})}
        state = checked_action(state, RulesEngine(), seat, action)
    if route != 'auto_pay':
        assert state.players[seat].mana_pool['U'] == state.players[seat].mana_pool['G'] == 1
    assert state.cards[land.id].tapped and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_effective_forest_subtype_and_printed_source_suppression(seat):
    state = position(seat)
    land = add(state, 'Island', seat)
    nissa = add(state, 'Nissa, Who Shakes the World', seat)
    assert not can_pay_with_pool_and_lands(state, seat, '{U}{G}')
    add(state, 'Yavimaya, Cradle of Growth', 3-seat)
    assert can_pay_with_pool_and_lands(state, seat, '{U}{G}')
    resolve_effect(state, 3-seat, 'temporary_ability_loss', {'target_card_id': nissa.id})
    assert not can_pay_with_pool_and_lands(state, seat, '{U}{G}')
    assert mana_source_outputs(state, seat, land.id) == {'G': 1, 'U': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_type_replacement_controller_and_aura_scope(seat):
    state = position(seat)
    land = add(state, 'Forest', seat)
    nissa = add(state, 'Nissa, Who Shakes the World', seat)
    aura(state, 'Spreading Seas', 3-seat, land)
    assert mana_source_outputs(state, seat, land.id) == {'U': 1}
    growth = aura(state, 'Wild Growth', 3-seat, land)
    assert can_pay_with_pool_and_lands(state, seat, '{U}{G}')
    resolve_effect(state, seat, 'temporary_ability_loss', {'target_card_id': growth.id})
    assert not can_pay_with_pool_and_lands(state, seat, '{U}{G}')
    other = add(state, 'Forest', seat)
    state.players[seat].battlefield.remove(nissa.id)
    state.players[3-seat].battlefield.append(nissa.id)
    nissa.controller = 3-seat
    assert mana_source_outputs(state, seat, other.id) == {'G': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_snow_mana_provenance_belongs_to_each_producing_ability(seat):
    state = position(seat)
    land = add(state, 'Snow-Covered Forest', seat)
    add(state, 'Nissa, Who Shakes the World', seat)
    assert can_pay_with_pool_and_lands(state, seat, '{S}{G}')
    assert not can_pay_with_pool_and_lands(state, seat, '{S}{S}')
    planned = deepcopy(state)
    assert auto_pay_cost(planned, seat, '{S}{G}')
    assert not any(planned.players[seat].mana_pool.values())
    state = activate(state, seat, land, 'G')
    assert state.players[seat].mana_pool['G'] == 2
    assert state.players[seat].snow_mana_pool['G'] == 1
    assert auto_pay_cost(state, seat, '{S}{G}')
    assert state.players[seat].mana_pool['G'] == state.players[seat].snow_mana_pool['G'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_tap_sickness_and_nonmana_tap_are_not_bonus_mana(seat):
    from rules_engine.resource_events import tap_permanents
    state = position(seat)
    source = add(state, 'Vesper Ghoul', seat)
    add(state, 'Leyline of Abundance', seat)
    source.summoning_sick = True
    assert not mana_ability_views(state, source)
    assert not can_pay_with_pool_and_lands(state, seat, '{G}')
    source.summoning_sick = False
    before_life = state.players[seat].life
    state = activate(state, seat, source, 'U')
    assert state.players[seat].life == before_life-1
    assert state.players[seat].mana_pool['G'] == state.players[seat].mana_pool['U'] == 1
    assert not mana_ability_views(state, state.cards[source.id])
    land = add(state, 'Forest', seat)
    add(state, 'Nissa, Who Shakes the World', seat)
    before_pool = state.players[seat].mana_pool.copy()
    tap_permanents(state, [land.id])
    assert state.players[seat].mana_pool == before_pool


@pytest.mark.parametrize('seat', [1, 2])
def test_captured_trigger_survives_tap_and_sacrifice_source_cost(seat):
    state = position(seat)
    thrull = add(state, 'Basal Thrull', seat)
    add(state, 'Leyline of Abundance', seat)
    assert can_pay_with_pool_and_lands(state, seat, '{B}{B}{G}')
    planned = deepcopy(state)
    assert auto_pay_cost(planned, seat, '{B}{B}{G}')
    assert not any(planned.players[seat].mana_pool.values())
    state = activate(state, seat, thrull, 'B')
    assert state.cards[thrull.id].zone == Zone.GRAVEYARD
    assert state.players[seat].mana_pool['G'] == 1
    assert state.players[seat].mana_pool['B'] == 2
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_non_tap_sacrifice_mana_does_not_trigger_leyline(seat):
    state = position(seat)
    pet = add(state, 'Blood Pet', seat)
    add(state, 'Leyline of Abundance', seat)
    add(state, 'Mana Reflection', seat)
    state = activate(state, seat, pet, 'B')
    assert state.cards[pet.id].zone == Zone.GRAVEYARD
    assert state.players[seat].mana_pool['B'] == 1
    assert not state.players[seat].mana_pool.get('G') and not state.stack


@pytest.mark.parametrize('name', ['Verdant Haven', 'Utopia Sprawl', 'Mana Flare'])
def test_unsupported_choice_or_produced_type_variants_are_not_guessed(name):
    assert fixed_mana_clauses(ROWS[name]['oracle_text']) == ()


@pytest.mark.parametrize('seat', [1, 2])
def test_departed_trigger_source_and_reentered_tap_object_do_not_leave_stale_bonuses(seat):
    from rules_engine.mana_triggers import mana_tap_scope, resolve_mana_triggers
    from rules_engine.resource_events import tap_permanents
    from game_state.state import object_incarnation
    state = position(seat)
    land = add(state, 'Forest', seat)
    nissa = add(state, 'Nissa, Who Shakes the World', seat)
    with mana_tap_scope(state, land) as captured:
        tap_permanents(state, [land.id])
        resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': nissa.id})
    assert len(captured) == 1
    resolve_mana_triggers(state, captured)
    assert state.players[seat].mana_pool['G'] == 1
    land.tapped = False
    assert mana_source_outputs(state, seat, land.id) == {'G': 1}
    add(state, 'Nissa, Who Shakes the World', seat)
    previous = object_incarnation(land)
    with mana_tap_scope(state, land) as stale:
        # The same card identifier now denotes a new battlefield object.
        land.battlefield_incarnation = previous + 100
        tap_permanents(state, [land.id])
    assert stale == []


@pytest.mark.parametrize('seat', [1, 2])
def test_unsupported_color_choice_aura_never_fabricates_bonus_mana(seat):
    state = position(seat)
    land = add(state, 'Island', seat)
    aura(state, 'Verdant Haven', seat, land)
    assert not can_pay_with_pool_and_lands(state, seat, '{U}{G}')
    state = activate(state, seat, land, 'U')
    assert state.players[seat].mana_pool['U'] == 1
    assert not state.players[seat].mana_pool.get('G')


@pytest.mark.parametrize('seat', [1, 2])
def test_tick512_ugin_is_announced_payable_legal_and_really_paid(seat):
    from rules_engine.costs import collect_cost_options, check_cost_option_available
    state = deserialize_match_snapshot(json.loads((Path(__file__).parent / 'fixtures/additive_mana_tick512.json').read_text()))
    if seat == 1:
        state.players = {3-pid: player for pid, player in state.players.items()}
        for pid, player in state.players.items():
            player.id = pid
        for card in state.cards.values():
            card.owner, card.controller = 3-card.owner, 3-card.controller
        state.active_player, state.priority_player = 3-state.active_player, 3-state.priority_player
    ugin = next(state.cards[cid] for cid in state.players[seat].hand if state.cards[cid].name == 'Ugin, the Spirit Dragon')
    before = serialize_match_snapshot(state)
    assert count_untapped_lands_by_color(state, seat)['ANY'] == 11
    assert can_pay_with_pool_and_lands(state, seat, ugin.mana_cost)
    option = collect_cost_options(state, seat, ugin)[0]
    assert check_cost_option_available(state, seat, ugin, option)
    legal = RulesEngine().legal_moves(state, seat)
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == ugin.id for move in legal)
    assert serialize_match_snapshot(state) == before
    RulesEngine().take_action(state, seat, {'type': 'cast_spell', 'card_id': ugin.id}, reject_invalid=True)
    assert state.cards[ugin.id].zone == Zone.STACK
    assert any(item.source_card_id == ugin.id for item in state.stack)
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield
               if 'Land' in state.cards[cid].types) == 4


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source,reflection,color,expected,cost,rejected', [
    ('Forest', False, 'G', {'G': 2}, '{G}{G}', '{C}{G}'),
    ('Forest', True, 'C', {'C': 1, 'G': 1}, '{C}{G}', '{G}{G}'),
    ('Tropical Island', False, 'U', {'U': 1, 'G': 1}, '{U}{G}', '{U}{U}'),
    ('Tropical Island', True, 'C', {'C': 1, 'G': 1}, '{C}{G}', '{U}{G}'),
    ('Llanowar Elves', True, 'G', {'G': 2}, '{G}{G}', '{3}'),
])
def test_sphere_replaces_land_base_not_trigger_or_nonforest_creature(seat, source, reflection, color, expected, cost, rejected):
    state = position(seat)
    card = add(state, source, seat)
    add(state, 'Nissa, Who Shakes the World', seat)
    sphere = add(state, 'Damping Sphere', 3-seat)
    if reflection:
        add(state, 'Mana Reflection', seat)
    assert can_pay_with_pool_and_lands(state, seat, cost)
    assert not can_pay_with_pool_and_lands(state, seat, rejected)
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, cost)
    assert not any(paid.players[seat].mana_pool.values())
    tapped = activate(state, seat, card, color)
    assert {c: n for c, n in tapped.players[seat].mana_pool.items() if n} == expected
    assert not tapped.stack
    if reflection and source == 'Forest':
        resolve_effect(state, seat, 'temporary_ability_loss', {'target_card_id': sphere.id})
        assert can_pay_with_pool_and_lands(state, seat, '{G}{G}{G}')


@pytest.mark.parametrize('seat', [1, 2])
def test_bonus_does_not_inherit_base_spending_restriction(seat):
    state = position(seat)
    card = add(state, 'Renowned Weaponsmith', seat)
    add(state, 'Leyline of Abundance', seat)
    assert can_pay_with_pool_and_lands(state, seat, '{G}', spell_types={'Instant'})
    assert not can_pay_with_pool_and_lands(state, seat, '{C}', spell_types={'Instant'})
    assert can_pay_with_pool_and_lands(state, seat, '{2}{G}', spell_types={'Artifact'})
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, '{G}', spell_types={'Instant'})
    assert paid.players[seat].mana_pool['C'] == 2
    assert sum(lot['amount'] for lot in paid.players[seat].restricted_mana_pool) == 2
    assert not auto_pay_cost(paid, seat, '{1}', spell_types={'Instant'})
    tapped = activate(state, seat, card, 'C')
    assert tapped.players[seat].mana_pool['G'] == 1
    assert tapped.players[seat].mana_pool['C'] == 2
    assert {lot['color'] for lot in tapped.players[seat].restricted_mana_pool} == {'C'}


@pytest.mark.parametrize('seat', [1, 2])
def test_same_color_bonus_remains_independently_unrestricted(seat):
    state = position(seat)
    sage = add(state, 'Somberwald Sage', seat)
    add(state, 'Leyline of Abundance', seat)
    assert can_pay_with_pool_and_lands(state, seat, '{G}', spell_types={'Instant'})
    assert not can_pay_with_pool_and_lands(state, seat, '{G}{G}', spell_types={'Instant'})
    assert can_pay_with_pool_and_lands(state, seat, '{G}{G}{G}{G}', spell_types={'Creature'})
    planned = deepcopy(state)
    assert auto_pay_cost(planned, seat, '{G}', spell_types={'Instant'})
    # Automatic payment may choose another base color; all base units stay restricted.
    assert sum(planned.players[seat].mana_pool.values()) == 3
    assert sum(lot['amount'] for lot in planned.players[seat].restricted_mana_pool) == 3
    state = activate(state, seat, sage, 'G')
    assert state.players[seat].mana_pool['G'] == 4
    assert auto_pay_cost(state, seat, '{G}', spell_types={'Instant'})
    assert state.players[seat].mana_pool['G'] == 3
    assert sum(lot['amount'] for lot in state.players[seat].restricted_mana_pool) == 3
    assert not auto_pay_cost(state, seat, '{G}', spell_types={'Instant'})


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_base_mana_can_activate_only_with_positive_triggered_bundle(seat):
    from rules_engine.action_validation import ActionRejected
    state = position(seat)
    sage = add(state, 'Gyre Sage', seat)
    action = {'type': 'tap_nonland_for_mana', 'card_id': sage.id, 'color': 'G'}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    add(state, 'Leyline of Abundance', seat)
    assert can_pay_with_pool_and_lands(state, seat, '{G}')
    state = checked_action(state, RulesEngine(), seat, action)
    assert state.cards[sage.id].tapped
    assert state.players[seat].mana_pool['G'] == 1
