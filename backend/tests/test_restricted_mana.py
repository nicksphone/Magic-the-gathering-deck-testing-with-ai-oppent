"""Actual Oracle restrictions survive floating, costs, expiry and snapshots."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import Zone, Step
from game_state.state import assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_match
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.costs import activated_cost_available, apply_activated_costs
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_power, effective_toughness, effective_keywords, continuous_layer_trace
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands, add_mana_to_pool
from tests.test_ai_recurring_engines import fixture, add as add_card, resolve


CARDS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures' / 'restricted_mana.json').read_text())}


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, player, zone, cards=CARDS)
    card.summoning_sick = False
    return card


def clean(player=1):
    state = fixture()
    state.active_player = state.priority_player = player
    for seat in state.players.values():
        seat.mana_pool.clear()
        seat.snow_mana_pool.clear()
    return state


def tap(state, source, color):
    return checked_action(state, RulesEngine(), source.controller,
                          {'type': 'tap_nonland_for_mana', 'card_id': source.id, 'color': color})


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('floating', [False, True])
def test_artifact_only_mana_does_not_pay_instant_or_mutate_rejected_state(player, floating):
    state = clean(player)
    source = add(state, 'Renowned Weaponsmith', player)
    add(state, 'Forest', player)
    target = add(state, 'Sol Ring', 3 - player)
    spell = add(state, 'Naturalize', player, Zone.HAND)
    if floating:
        state = tap(state, source, 'C')
    before = serialize_match_snapshot(state)
    assert not can_pay_with_pool_and_lands(state, player, spell.mana_cost, spell_types=set(spell.types))
    assert not any(m.get('card_id') == spell.id and m['type'] == 'cast_spell' for m in RulesEngine().legal_moves(state, player))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': spell.id,
                                                    'targets': {'target_card_id': target.id}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('name,color,kind,types', [
    ('Renowned Weaponsmith', 'C', 'spell', {'Artifact'}),
    ('Renowned Weaponsmith', 'C', 'activation', {'Artifact'}),
    ('Somberwald Sage', 'G', 'spell', {'Creature'}),
    ('Somberwald Sage', 'G', 'spell', {'Artifact', 'Creature'}),
])
def test_eligible_floating_units_remain_restricted_after_source_leaves(name, color, kind, types):
    state = clean()
    source = add(state, name)
    state = tap(state, source, color)
    source = state.cards[source.id]
    state.players[1].battlefield.remove(source.id)
    source.move_to_zone(Zone.GRAVEYARD)
    state.players[1].graveyard.append(source.id)
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(before)
    assert auto_pay_cost(restored, 1, '{1}', payment_kind=kind, payment_types=types)
    leftover = 1 if name == 'Renowned Weaponsmith' else 2
    assert restored.players[1].mana_pool[color] == leftover
    assert restored.players[1].restricted_mana_pool[0]['amount'] == leftover
    assert not auto_pay_cost(restored, 1, '{1}', payment_kind='other')
    assert not auto_pay_cost(restored, 1, '{1}', spell_types={'Instant'})
    assert serialize_match_snapshot(state) == before


def test_creature_cast_mana_cannot_pay_creature_abilities():
    state = clean()
    source = add(state, 'Somberwald Sage')
    creature = add(state, 'Myr Galvanizer')
    assert can_pay_with_pool_and_lands(state, 1, '{3}', spell_types={'Creature'})
    assert not activated_cost_available(state, 1, creature.id, '{1}, {T}')
    state = tap(state, source, 'G')
    assert not activated_cost_available(state, 1, creature.id, '{1}, {T}')
    assert not auto_pay_cost(state, 1, '{1}', payment_kind='activation', payment_types={'Creature'})


def test_actual_creature_cast_uses_ready_restricted_sources():
    state = clean()
    source = add(state, 'Somberwald Sage')
    spell = add(state, 'Steel Leaf Champion', zone=Zone.HAND)
    state = resolve(checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': spell.id, 'targets': {}}))
    assert state.cards[source.id].tapped
    assert state.cards[spell.id].zone == Zone.BATTLEFIELD
    assert not state.players[1].restricted_mana_pool


def test_actual_artifact_cast_preserves_unrestricted_pool_when_color_is_shared():
    state = clean()
    source = add(state, 'Renowned Weaponsmith')
    state = tap(state, source, 'C')
    add_mana_to_pool(state, 1, 'C', 1)
    spell = add(state, 'Sol Ring', zone=Zone.HAND)
    state = resolve(checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': spell.id, 'targets': {}}))
    assert state.players[1].mana_pool['C'] == 2
    assert state.players[1].restricted_mana_pool[0]['amount'] == 1
    state.cards[spell.id].tapped = True
    assert auto_pay_cost(state, 1, '{1}', payment_kind='other')
    assert state.players[1].mana_pool['C'] == 1
    assert state.players[1].restricted_mana_pool[0]['amount'] == 1
    assert not auto_pay_cost(state, 1, '{1}', payment_kind='other')


def test_actual_artifact_activation_uses_cost_context_without_spell_tax():
    state = clean()
    source = add(state, 'Renowned Weaponsmith')
    artifact = add(state, 'Basalt Monolith')
    artifact.tapped = True
    add_mana_to_pool(state, 1, 'C', 1)
    assert activated_cost_available(state, 1, artifact.id, '{3}')
    assert apply_activated_costs(state, 1, artifact.id, '{3}')
    assert state.cards[source.id].tapped
    assert state.players[1].mana_pool['C'] == 0
    assert not state.players[1].restricted_mana_pool


def test_artifact_cycling_and_equipment_receive_activation_context():
    state = clean()
    add(state, 'Renowned Weaponsmith')
    hollow = add(state, 'Hollow One', zone=Zone.HAND)
    assert any(m['type'] == 'cycle_card' and m['card_id'] == hollow.id for m in RulesEngine().legal_moves(state, 1))
    state = resolve(checked_action(state, RulesEngine(), 1, {'type': 'cycle_card', 'card_id': hollow.id}))
    assert state.cards[hollow.id].zone == Zone.GRAVEYARD
    assert not state.players[1].restricted_mana_pool
    add(state, 'Renowned Weaponsmith')
    equipment = add(state, 'Bonesplitter')
    creature = add(state, 'Llanowar Elves')
    state = checked_action(state, RulesEngine(), 1, {'type': 'equip', 'card_id': equipment.id, 'target_card_id': creature.id})
    assert state.stack[-1].effect_key == 'equip_attachment'
    assert state.cards[equipment.id].attached_to is None
    state = resolve(state)
    assert state.cards[equipment.id].attached_to == creature.id
    assert state.players[1].restricted_mana_pool[0]['amount'] == 1


def test_snow_provenance_is_independent_of_restriction_and_ordinary_credit():
    state = clean()
    add(state, 'Renowned Weaponsmith')
    snow = add(state, 'Boreal Druid')
    details = {}
    assert auto_pay_cost(state, 1, '{S}{2}', spell_types={'Artifact'}, payment_details=details)
    assert state.cards[snow.id].tapped
    assert details['snow_mana_spent'] == 1
    assert not state.players[1].restricted_mana_pool
    assert state.players[1].mana_pool.get('C') == 0


def test_pool_expiry_and_legacy_snapshot_compatibility():
    state = clean()
    source = add(state, 'Renowned Weaponsmith')
    state = tap(state, source, 'C')
    snapshot = serialize_match_snapshot(state)
    assert snapshot['players']['1']['restricted_mana_pool']
    assert serialize_match(state)['players'][1]['restricted_mana_pool'] == state.players[1].restricted_mana_pool
    legacy = serialize_match_snapshot(clean())
    legacy['players']['1'].pop('restricted_mana_pool')
    assert deserialize_match_snapshot(legacy).players[1].restricted_mana_pool == []
    RulesEngine()._clear_mana_pools(state)
    assert not state.players[1].restricted_mana_pool
    assert not any(state.players[1].mana_pool.values())


@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Control', 'Tempo', 'Midrange', 'Ramp', 'Drain', 'Aristocrats', 'Tokens', 'Tribal'])
def test_ai_does_not_invent_payable_restricted_mana(style):
    state = clean()
    source = add(state, 'Renowned Weaponsmith')
    add(state, 'Forest')
    add(state, 'Sol Ring', 2)
    spell = add(state, 'Naturalize', zone=Zone.HAND)
    state = tap(state, source, 'C')
    before = serialize_match_snapshot(state)
    legal = RulesEngine().legal_moves(state, 1)
    decision = AIAgent(archetype=style).choose_action(state, legal, 1)
    assert not (decision.action['type'] == 'cast_spell' and decision.action.get('card_id') == spell.id)
    assert serialize_match_snapshot(state) == before


def equip_state():
    state = clean()
    source = add(state, 'Renowned Weaponsmith')
    equipment = add(state, 'Bonesplitter')
    creature = add(state, 'Llanowar Elves')
    state = checked_action(state, RulesEngine(), 1, {'type': 'equip', 'card_id': equipment.id, 'target_card_id': creature.id})
    assert state.stack[-1].effect_key == 'equip_attachment'
    assert state.cards[source.id].tapped
    assert state.cards[equipment.id].attached_to is None
    return state, equipment.id, creature.id


def test_equip_priority_counter_response_and_paid_cost_remain():
    state, equipment, creature = equip_state()
    assert state.priority_player == 1
    state = checked_action(state, RulesEngine(), 1, {'type': 'pass_priority'})
    counter = add(state, 'Stifle', 2, Zone.HAND)
    add_mana_to_pool(state, 2, 'U', 1)
    state = checked_action(state, RulesEngine(), 2, {'type': 'cast_spell', 'card_id': counter.id,
                                                  'targets': {'target_stack_id': state.stack[-1].id}})
    state = resolve(state)
    assert state.cards[equipment].attached_to is None
    assert state.players[1].mana_pool['C'] == 1
    assert state.players[1].restricted_mana_pool[0]['amount'] == 1


def test_equip_removal_response_and_snapshot_revalidation():
    state, equipment, creature = equip_state()
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 1, {'type': 'pass_priority'})
    removal = add(state, 'Lightning Bolt', 2, Zone.HAND)
    add_mana_to_pool(state, 2, 'R', 1)
    state = checked_action(state, RulesEngine(), 2, {'type': 'cast_spell', 'card_id': removal.id,
                                                  'targets': {'target_card_id': creature}})
    state = resolve(state)
    assert state.cards[creature].zone == Zone.GRAVEYARD
    assert state.cards[equipment].attached_to is None


@pytest.mark.parametrize('which', ['source', 'target'])
def test_equipping_does_not_attach_a_returned_incarnation(which):
    state, equipment, creature = equip_state()
    cid = equipment if which == 'source' else creature
    card = state.cards[cid]
    state.players[1].battlefield.remove(cid)
    card.move_to_zone(Zone.GRAVEYARD)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[1].battlefield.append(cid)
    assign_static_order_on_battlefield_entry(state, cid)
    state = resolve(state)
    assert state.cards[equipment].attached_to is None


def test_equip_rechecks_target_controller_after_activation():
    state, equipment, creature = equip_state()
    state.players[1].battlefield.remove(creature)
    state.players[2].battlefield.append(creature)
    state.cards[creature].controller = 2
    state = resolve(state)
    assert state.cards[equipment].attached_to is None


def test_equip_legality_does_not_offer_shroud_or_animated_equipment():
    state = clean()
    equipment = add(state, 'Bonesplitter')
    own = add(state, 'Llanowar Elves')
    enemy = add(state, 'Llanowar Elves', 2)
    caryatid = add(state, 'Sylvan Caryatid')
    greaves = add(state, 'Lightning Greaves')
    greaves.attached_to = own.id
    add_mana_to_pool(state, 1, 'C', 2)
    moves = [m for m in RulesEngine().legal_moves(state, 1) if m['type'] == 'equip' and m['card_id'] == equipment.id]
    assert moves and {t['id'] for t in moves[0]['targets']} == {caryatid.id}
    before = serialize_match_snapshot(state)
    for target in (own.id, enemy.id):
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 1, {'type': 'equip', 'card_id': equipment.id, 'target_card_id': target})
        assert serialize_match_snapshot(state) == before
    equipment.types.append('Creature')  # A type-changing effect, not a new card definition.
    assert not any(m['type'] == 'equip' and m['card_id'] == equipment.id for m in RulesEngine().legal_moves(state, 1))


@pytest.mark.parametrize('name,delta,keywords', [
    ('Bonesplitter', (2, 0), set()), ('Lightning Greaves', (0, 0), {'haste', 'shroud'}),
    ('Rancor', (2, 0), {'trample'}), ('Shadowspear', (1, 1), {'trample', 'lifelink'}),
    ('Unholy Strength', (2, 1), set()),
])
def test_attached_buffs_and_keywords_follow_attachment_not_controller(name, delta, keywords):
    state = clean()
    target = add(state, 'Llanowar Elves', 2)
    other = add(state, 'Llanowar Elves')
    attachment = add(state, name)
    attachment.attached_to = target.id
    before = serialize_match_snapshot(state)
    for candidate in (state, deserialize_match_snapshot(before)):
        assert effective_power(candidate, target.id) == 1 + delta[0]
        assert effective_toughness(candidate, target.id) == 1 + delta[1]
        assert keywords <= set(effective_keywords(candidate, target.id))
        assert effective_power(candidate, other.id) == 1
        assert not keywords.intersection(effective_keywords(candidate, other.id))
        assert continuous_layer_trace(candidate, target.id)['applied_layers']
    assert serialize_match_snapshot(state) == before
    attachment.attached_to = None
    assert effective_power(state, target.id) == 1
    assert not keywords.intersection(effective_keywords(state, target.id))


@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Control', 'Tempo', 'Midrange', 'Ramp', 'Drain', 'Aristocrats', 'Tokens', 'Tribal'])
def test_ai_reserves_restricted_source_only_for_a_payable_postcombat_spell(style):
    state = clean()
    source = add(state, 'Renowned Weaponsmith')
    for _ in range(4):
        add(state, 'Forest')
    add(state, 'Wurmcoil Engine', zone=Zone.HAND)
    state.step = Step.DECLARE_ATTACKERS
    before = serialize_match_snapshot(state)
    ai = AIAgent(archetype=style)
    assert ai._choose_attackers(state, [source.id], 1) == []
    assert serialize_match_snapshot(state) == before
    state.players[1].hand.clear()
    add(state, 'Naturalize', zone=Zone.HAND)
    add(state, 'Sol Ring', 2)
    assert ai._choose_attackers(state, [source.id], 1) == [source.id]
