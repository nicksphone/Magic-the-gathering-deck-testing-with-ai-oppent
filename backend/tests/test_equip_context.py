"""Canonical equip costs and 7b scope use target context, not guessed discounts."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import Zone, object_incarnation, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.attachments import attach_if_legal
from rules_engine.continuous import effective_power, effective_toughness, continuous_layer_trace, attachment_effect_warnings
from rules_engine.engine import RulesEngine
from rules_engine.mana import add_mana_to_pool, auto_pay_cost, can_pay_with_pool_and_lands
from tests.test_ai_recurring_engines import add as add_card, resolve
from tests.test_restricted_mana import clean

CARDS = {r['name']: r for r in json.loads((Path(__file__).parent / 'fixtures' / 'equip_costs.json').read_text())}


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, player, zone, cards=CARDS)
    card.summoning_sick = False
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def equip(state, source, target, player=1):
    return checked_action(state, RulesEngine(), player, {'type': 'equip', 'card_id': source.id, 'target_card_id': target.id})


@pytest.mark.parametrize('player', [1, 2])
def test_champion_discount_only_offers_the_payable_target_without_mana(player):
    state = clean(player)
    source = add(state, 'Bonesplitter', player)
    champion = add(state, 'Fervent Champion', player)
    other = add(state, 'Llanowar Elves', player)
    other.tapped = True
    moves = [m for m in RulesEngine().legal_moves(state, player) if m['type'] == 'equip']
    assert len(moves) == 1 and [t['id'] for t in moves[0]['targets']] == [champion.id]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        equip(state, source, other, player)
    assert serialize_match_snapshot(state) == before
    state = resolve(equip(state, source, champion, player))
    assert state.cards[source.id].attached_to == champion.id
    assert effective_power(state, champion.id) == 3


@pytest.mark.parametrize('owner', [1, 2])
def test_strong_back_reduces_only_its_attached_target_for_its_controller(owner):
    state = clean()
    target = add(state, 'Llanowar Elves')
    target.tapped = True
    source = add(state, 'Bonesplitter')
    aura = add(state, 'Strong Back', owner)
    assert attach_if_legal(state, aura.id, target.id)
    assert can_pay_with_pool_and_lands(state, 1, '{1}', payment_kind='activation',
        payment_types={'Artifact'}, ability_kind='equip', source_card_id=source.id,
        target_card_id=target.id) == (owner == 1)
    assert any(m['type'] == 'equip' for m in RulesEngine().legal_moves(state, 1)) == (owner == 1)
    assert attachment_effect_warnings(state, aura.id) == []


def test_global_and_targeted_generic_discounts_stack_but_not_on_other_activations():
    state = clean()
    source = add(state, 'Bonesplitter')
    target = add(state, 'Fervent Champion')
    add(state, 'Auriok Steelshaper')
    assert auto_pay_cost(state, 1, '{4}', payment_kind='activation', payment_types={'Artifact'},
                         ability_kind='equip', source_card_id=source.id, target_card_id=target.id)
    assert not auto_pay_cost(state, 1, '{1}', payment_kind='activation', payment_types={'Artifact'},
                             source_card_id=source.id, target_card_id=target.id)
    assert not auto_pay_cost(state, 1, '{W}', payment_kind='activation', payment_types={'Artifact'},
                             ability_kind='equip', source_card_id=source.id, target_card_id=target.id)


def test_target_power_reduction_is_not_an_announced_x_and_does_not_set_unattached_board_stats():
    state = clean()
    target = add(state, 'Colossal Dreadmaw')
    other = add(state, 'Llanowar Elves')
    source = add(state, 'Belt of Giant Strength')
    assert (effective_power(state, target.id), effective_power(state, other.id)) == (6, 1)
    add_mana_to_pool(state, 1, 'C', 4)
    state = resolve(equip(state, source, target))
    assert state.players[1].mana_pool['C'] == 0
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == (10, 10)
    assert effective_power(state, other.id) == 1
    assert not attachment_effect_warnings(state, source.id)
    assert any(row['layer'] == 'pt-set' for row in continuous_layer_trace(state, target.id)['applied_layers'])


def test_discount_uses_effective_power_and_discounts_do_not_consume_restricted_mana_unnecessarily():
    state = clean()
    target = add(state, 'Colossal Dreadmaw')
    source = add(state, 'Belt of Giant Strength')
    aura = add(state, 'Strong Back')
    assert attach_if_legal(state, aura.id, target.id)
    target.counters['+1/+1'] = 1
    mana_source = add(state, 'Renowned Weaponsmith')
    add_mana_to_pool(state, 1, 'C', 2, source_id=mana_source.id)
    assert effective_power(state, target.id) == 9
    state = resolve(equip(state, source, target))  # 10 - effective 9 - targeted 3 = 0.
    assert state.cards[source.id].attached_to == target.id
    assert effective_power(state, target.id) == 15  # base 10 + counter + two attached bonuses.
    assert state.players[1].mana_pool['C'] == 2
    assert state.players[1].restricted_mana_pool[0]['amount'] == 2


@pytest.mark.parametrize('name,base', [('Belt of Giant Strength', (10, 10)), ('Octopus Umbra', (8, 8))])
def test_attached_base_setters_do_not_affect_either_unrelated_board(name, base):
    state = clean()
    own = add(state, 'Llanowar Elves')
    target = add(state, 'Colossal Dreadmaw', 2)
    other = add(state, 'Llanowar Elves', 2)
    source = add(state, name)
    assert effective_power(state, own.id) == 1
    assert effective_power(state, target.id) == 6
    assert attach_if_legal(state, source.id, target.id)
    assert (effective_power(state, target.id), effective_toughness(state, target.id)) == base
    assert effective_power(state, own.id) == effective_power(state, other.id) == 1
    source.attached_to = None
    assert effective_power(state, target.id) == 6


def test_global_base_setter_and_reattachment_timestamp_keep_counters_and_identity():
    state = clean()
    target = add(state, 'Colossal Dreadmaw')
    other = add(state, 'Llanowar Elves')
    source = add(state, 'Belt of Giant Strength')
    source.counters['charge'] = 3
    assert attach_if_legal(state, source.id, target.id)
    incarnation = object_incarnation(source)
    first_timestamp = source.effect_timestamp
    assert attach_if_legal(state, source.id, target.id)
    assert source.effect_timestamp == first_timestamp
    add(state, 'Humility')
    assert effective_power(state, target.id) == effective_power(state, other.id) == 1
    assert attach_if_legal(state, source.id, other.id)
    assert effective_power(state, other.id) == 10
    assert effective_power(state, target.id) == 1
    assert source.effect_timestamp > first_timestamp
    assert object_incarnation(source) == incarnation
    assert source.counters['charge'] == 3
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert effective_power(restored, other.id) == 10
    assert object_incarnation(restored.cards[source.id]) == incarnation


def test_reattachment_does_not_fizzle_pending_equip_but_zone_change_does():
    state = clean()
    target = add(state, 'Llanowar Elves')
    other = add(state, 'Colossal Dreadmaw')
    source = add(state, 'Bonesplitter')
    add_mana_to_pool(state, 1, 'C', 1)
    state = equip(state, source, target)
    assert attach_if_legal(state, source.id, other.id)
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[source.id].attached_to == target.id
    add_mana_to_pool(state, 1, 'C', 1)
    state = equip(state, state.cards[source.id], state.cards[other.id])
    card = state.cards[source.id]
    from rules_engine.events import emit_event
    emit_event(state, 'leaves_battlefield', {'card_id': card.id, 'controller': 1})
    state.players[1].battlefield.remove(card.id)
    card.move_to_zone(Zone.EXILE)
    state.players[1].exile.append(card.id)
    state.players[1].exile.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[1].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    state = resolve(state)
    assert state.cards[source.id].attached_to != other.id


@pytest.mark.parametrize('archetype', ['Aggro', 'Burn', 'Control', 'Tempo', 'Midrange', 'Ramp', 'Drain', 'Aristocrats', 'Tokens', 'Tribal'])
def test_ai_emits_concrete_payable_equip_and_does_not_loop_on_same_target(archetype):
    state = clean()
    source = add(state, 'Bonesplitter')
    target = add(state, 'Fervent Champion')
    add(state, 'Llanowar Elves').tapped = True
    ai = AIAgent(archetype=archetype, difficulty='master')
    before = serialize_match_snapshot(state)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action == {'type': 'equip', 'card_id': source.id, 'target_card_id': target.id}
    assert serialize_match_snapshot(state) == before
    state = resolve(checked_action(state, RulesEngine(), 1, decision.action))
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action['type'] != 'equip'
