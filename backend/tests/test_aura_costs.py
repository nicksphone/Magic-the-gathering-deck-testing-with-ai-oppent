"""Canonical target-dependent Aura casting uses real costs and public state."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.attachments import attach_if_legal, attachment_target_is_legal
from rules_engine.cast_choice import available_cast_options_and_hints, build_cast_hints
from rules_engine.continuous import effective_power, attachment_effect_warnings
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.costs import collect_cost_options, check_cost_option_available
from rules_engine.engine import RulesEngine
from rules_engine.mana import add_mana_to_pool, auto_pay_cost
from tests.test_ai_recurring_engines import add as add_card, resolve
from tests.test_restricted_mana import clean

CARDS = {r['name']: r for r in json.loads((Path(__file__).parent / 'fixtures' / 'aura_costs.json').read_text())}


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, player, zone, cards=CARDS)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def discounted(player=1, owner=None, target_player=None):
    state = clean(player)
    target = add(state, 'Colossal Dreadmaw', target_player or player)
    other = add(state, 'Llanowar Elves', player)
    source = add(state, 'Strong Back', owner or player)
    assert attach_if_legal(state, source.id, target.id)
    spell = add(state, 'Octopus Umbra', player, Zone.HAND)
    add_mana_to_pool(state, player, 'U', 2)
    return state, target, other, source, spell


def cast(state, spell, target, player=1, **extra):
    return checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': spell.id,
        'targets': {'target_card_id': target.id}, **extra})


@pytest.mark.parametrize('player', [1, 2])
def test_target_discount_reaches_legal_move_payment_and_snapshot(player):
    state, target, other, source, spell = discounted(player)
    options, hints = available_cast_options_and_hints(state, spell, player)
    assert [o.id for o in options] == ['base']
    assert hints['aura_targets'] == [{'id': target.id, 'name': target.name}]
    assert hints['aura_cost_options'] == {target.id: ['base']}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, spell, other, player)
    assert serialize_match_snapshot(state) == before
    state = cast(state, spell, target, player)
    assert state.players[player].mana_pool['U'] == 0
    assert state.cards[spell.id].zone == Zone.STACK
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[spell.id].attached_to == target.id
    assert effective_power(state, target.id) == 12
    assert effective_power(state, other.id) == 1
    assert not attachment_effect_warnings(state, source.id)


@pytest.mark.parametrize('player', [1, 2])
def test_opponent_owned_reduction_is_not_borrowed(player):
    state, target, other, source, spell = discounted(player, owner=3-player)
    assert not available_cast_options_and_hints(state, spell, player)[0]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, spell, target, player)
    assert serialize_match_snapshot(state) == before


def test_target_owned_by_opponent_can_receive_a_legal_aura_but_ai_does_not_buff_it():
    state, target, other, source, spell = discounted(target_player=2)
    options, hints = available_cast_options_and_hints(state, spell, 1)
    assert options and hints['aura_targets'][0]['id'] == target.id
    moves = RulesEngine().legal_moves(state, 1)
    ai = AIAgent(difficulty='master', archetype='Tempo')
    assert ai.choose_action(state, moves, 1).action['type'] != 'cast_spell'
    state = resolve(cast(state, spell, target))
    assert state.cards[spell.id].attached_to == target.id


def test_spell_tax_combines_with_reduction_and_colored_requirements_remain():
    state, target, _, _, spell = discounted()
    add(state, 'Thalia, Guardian of Thraben', 2)
    assert not available_cast_options_and_hints(state, spell, 1)[0]
    add_mana_to_pool(state, 1, 'C', 1)
    state = resolve(cast(state, spell, target))
    assert state.players[1].mana_pool['C'] == state.players[1].mana_pool['U'] == 0


def test_global_aura_discount_preserves_white_requirement_and_does_not_discount_artifacts():
    state = clean()
    target = add(state, 'Colossal Dreadmaw')
    add(state, 'Hero of Iroas')
    spell = add(state, 'Spirit Mantle', zone=Zone.HAND)
    assert not available_cast_options_and_hints(state, spell, 1)[0]
    artifact = add(state, 'Sol Ring', zone=Zone.HAND)
    assert not check_cost_option_available(state, 1, artifact, collect_cost_options(state, 1, artifact)[0], target_card_id=target.id)
    add_mana_to_pool(state, 1, 'W', 1)
    assert available_cast_options_and_hints(state, spell, 1)[0]
    state = resolve(cast(state, spell, target))
    assert state.players[1].mana_pool['W'] == 0


def test_global_and_targeted_reductions_stack_but_never_discount_an_activation():
    state, target, _, _, spell = discounted()
    add(state, 'Hero of Iroas')
    assert auto_pay_cost(state, 1, '{4}{U}{U}', spell_types=set(spell.types),
                         oracle_text=spell.oracle_text, source_card_id=spell.id, target_card_id=target.id)
    assert not auto_pay_cost(state, 1, '{1}', payment_kind='activation', payment_types={'Enchantment'},
                             source_card_id=spell.id, target_card_id=target.id, oracle_text=spell.oracle_text)


def test_discount_does_not_consume_artifact_only_mana():
    state, target, _, _, spell = discounted()
    source = add(state, 'Renowned Weaponsmith')
    add_mana_to_pool(state, 1, 'C', 2, source_id=source.id)
    state = resolve(cast(state, spell, target))
    assert state.players[1].mana_pool['C'] == 2
    assert state.players[1].restricted_mana_pool[0]['amount'] == 2


def test_discount_is_not_repriced_if_its_source_leaves_after_payment():
    state, target, _, source, spell = discounted()
    state = cast(state, spell, target)
    resolve_effect(state, 2, 'destroy_permanent', {'target_card_id': source.id})
    state = resolve(state)
    assert state.cards[spell.id].attached_to == target.id
    assert effective_power(state, target.id) == 8
    assert state.players[1].mana_pool['U'] == 0


def test_countered_discounted_aura_does_not_attach_or_refund_cost():
    state, target, _, _, spell = discounted()
    state = cast(state, spell, target)
    counter = add(state, 'Counterspell', 2, Zone.HAND)
    add_mana_to_pool(state, 2, 'U', 2)
    state = checked_action(state, RulesEngine(), 1, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), 2, {'type': 'cast_spell', 'card_id': counter.id,
        'targets': {'target_stack_id': state.stack[-1].id}})
    state = resolve(state)
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert state.cards[spell.id].attached_to is None
    assert state.players[1].mana_pool['U'] == 0


def test_shroud_removes_a_discounted_target_before_payment():
    state, target, _, _, spell = discounted()
    equipment = add(state, 'Lightning Greaves')
    assert attach_if_legal(state, equipment.id, target.id)
    assert not available_cast_options_and_hints(state, spell, 1)[0]


def test_escape_aura_uses_target_discount_and_preserves_additional_exile_cost():
    state, target, _, _, hand_spell = discounted()
    spell = add(state, "Mogis's Favor", zone=Zone.GRAVEYARD)
    fuel = [add(state, 'Plains', zone=Zone.GRAVEYARD).id for _ in range(2)]
    add_mana_to_pool(state, 1, 'B', 1)
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == spell.id)
    assert move['from_graveyard'] and move['target_hints']['aura_cost_options'][target.id] == ['escape']
    state = resolve(cast(state, spell, target, cost_choice={'id': 'escape'}, escape_exile_ids=fuel, from_graveyard=True))
    assert state.cards[spell.id].attached_to == target.id
    assert all(state.cards[cid].zone == Zone.EXILE for cid in fuel)
    assert state.players[1].mana_pool['B'] == 0


def test_real_impulse_draw_permission_reaches_discounted_aura_casting():
    state, target, _, _, spell = discounted()
    state.players[1].hand.remove(spell.id)
    spell.move_to_zone(Zone.LIBRARY)
    state.players[1].library.append(spell.id)
    impulse = add(state, 'Light Up the Stage', zone=Zone.HAND)
    state.players[1].mana_pool['U'] = 0
    add(state, 'Island')
    add(state, 'Island')
    add_mana_to_pool(state, 1, 'R', 3)
    state = resolve(checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': impulse.id}))
    assert state.cards[spell.id].zone == Zone.EXILE
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == spell.id)
    assert move['from_exile'] and move['target_hints']['aura_cost_options'] == {target.id: ['base']}
    state = resolve(cast(state, spell, target, from_exile=True))
    assert state.cards[spell.id].attached_to == target.id
    assert spell.id not in state.players[1].exile_play_until


def test_enchant_scope_ignores_unrelated_you_control_and_type_words():
    state = clean()
    target = add(state, 'Colossal Dreadmaw', 2)
    add(state, 'Sol Ring')
    spell = add(state, 'All That Glitters', zone=Zone.HAND)
    hints = build_cast_hints(state, spell, 1)
    assert hints['aura_targets'] == [{'id': target.id, 'name': target.name}]
    assert attachment_target_is_legal(state, spell, target.id)


def test_enchant_basic_land_control_and_union_restrictions_are_shared():
    state = clean()
    own_land = add(state, 'Plains')
    add(state, 'Plains', 2)
    creature = add(state, 'Colossal Dreadmaw')
    artifact = add(state, 'Sol Ring')
    aura = add(state, 'Ossification', zone=Zone.HAND)
    assert build_cast_hints(state, aura, 1)['aura_targets'] == [{'id': own_land.id, 'name': own_land.name}]
    assert not attachment_target_is_legal(state, aura, creature.id)
    union = add(state, 'Encrust', zone=Zone.HAND)
    assert {t['id'] for t in build_cast_hints(state, union, 1)['aura_targets']} == {creature.id, artifact.id}


def test_unknown_enchant_restrictions_do_not_broaden_into_arbitrary_targets():
    state = clean()
    land = add(state, 'Plains')
    spell = add(state, 'Chained to the Rocks', zone=Zone.HAND)
    assert 'unsupported enchant restriction' in known_unsupported_mechanics(spell.oracle_text)
    assert not attachment_target_is_legal(state, spell, land.id)
    assert not available_cast_options_and_hints(state, spell, 1)[0]


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('zone', [Zone.GRAVEYARD, Zone.EXILE])
def test_ai_preserves_source_permission_flags_in_checked_aura_action(player, zone):
    state, target, _, _, _ = discounted(player)
    name = "Mogis's Favor" if zone == Zone.GRAVEYARD else 'Octopus Umbra'
    spell = add(state, name, player, zone)
    if zone == Zone.GRAVEYARD:
        for _ in range(2):
            add(state, 'Plains', player, Zone.GRAVEYARD)
        add_mana_to_pool(state, player, 'B', 1)
    else:
        state.players[player].exile_play_until[spell.id] = state.turn
    move = next(m for m in RulesEngine().legal_moves(state, player) if m.get('card_id') == spell.id)
    decision = AIAgent(difficulty='master').choose_action(state, [move, {'type': 'pass_priority'}], player)
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['from_graveyard' if zone == Zone.GRAVEYARD else 'from_exile']
    state = resolve(checked_action(state, RulesEngine(), player, decision.action))
    assert state.cards[spell.id].attached_to == target.id


def test_aura_projection_resolves_real_heroic_trigger_before_valuing_attachment():
    state = clean()
    target = add(state, 'Hero of Iroas')
    spell = add(state, 'Spirit Mantle', zone=Zone.HAND)
    add_mana_to_pool(state, 1, 'W', 1)
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == spell.id)
    before = serialize_match_snapshot(state)
    action, gain = AIAgent(difficulty='master')._attachment_projection(state, move, 1)
    assert action and gain > 0
    assert serialize_match_snapshot(state) == before
    state = resolve(checked_action(state, RulesEngine(), 1, action))
    assert state.cards[target.id].counters['+1/+1'] == 1
    assert effective_power(state, target.id) == 4


@pytest.mark.parametrize('archetype', ['Aggro','Burn','Control','Tempo','Midrange','Ramp','Drain','Aristocrats','Tokens','Tribal'])
@pytest.mark.parametrize('negative', [False, True])
def test_shared_ai_chooses_payable_beneficial_or_harmful_attachment_without_mutation(archetype, negative):
    if negative:
        state = clean()
        target = add(state, 'Llanowar Elves', 2)
        add(state, 'Colossal Dreadmaw')
        spell = add(state, 'Dead Weight', zone=Zone.HAND)
        add_mana_to_pool(state, 1, 'B', 1)
    else:
        state, target, _, _, spell = discounted()
    ai = AIAgent(difficulty='master', archetype=archetype)
    before = serialize_match_snapshot(state)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['targets']['target_card_id'] == target.id
    assert serialize_match_snapshot(state) == before
    state = resolve(checked_action(state, RulesEngine(), 1, decision.action))
    assert state.cards[target.id].zone == Zone.GRAVEYARD if negative else effective_power(state, target.id) == 12
