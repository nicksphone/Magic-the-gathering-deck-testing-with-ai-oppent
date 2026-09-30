"""Ward is a response-able triggered resolution cost, not a casting tax."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.handlers import copy_spell, destroy_permanent
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.ward import parse_ward_cost, ward_instances, payment_cards, mark_stack_targets
from tests.test_ai_recurring_engines import add as add_card
from tests.test_restricted_mana import clean

CARDS = {r['name']: r for r in json.loads((Path(__file__).parent / 'fixtures' / 'ward.json').read_text())}
for row in CARDS.values():
    for field in ('power', 'toughness', 'keywords', 'colors'):
        row.setdefault(field, None)


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, player, Zone.HAND if zone == Zone.STACK else zone, cards=CARDS)
    if zone == Zone.STACK:
        state.players[player].hand.remove(card.id)
        card.move_to_zone(Zone.STACK)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    card.summoning_sick = False
    return card


def resolve(state):
    completed = resolve_top_of_stack(state)
    assert completed or (state.pending_mechanic_choice and state.pending_mechanic_choice['kind'] == 'ward_payment')
    return True


def cast_at(name='Tolarian Terror', player=1, spell='Lightning Bolt', mana=None):
    state = clean(player)
    target = add(state, name, 3-player)
    source = add(state, spell, player, Zone.HAND)
    state.players[player].mana_pool.update(mana or {'R': 1})
    state = checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': source.id,
                         'targets': {'target_card_id': target.id}})
    return state, target.id, source.id


def choose(state, ids, player=None):
    return checked_action(state, RulesEngine(), player or state.pending_mechanic_choice['player_id'],
                          {'type': 'choose_mechanic', 'card_ids': ids})


@pytest.mark.parametrize('player', [1, 2])
def test_spell_is_cast_without_ward_mana_then_countered_on_decline(player):
    state, target, spell = cast_at(player=player)
    assert len(state.stack) == 2 and state.stack[-1].effect_key == 'ward_payment'
    assert state.cards[spell].zone == Zone.STACK and state.cards[target].zone == Zone.BATTLEFIELD
    assert resolve(state)
    assert state.pending_mechanic_choice['options'] == ['decline']
    state = choose(state, ['decline'])
    assert not state.stack and state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('player', [1, 2])
def test_mana_payment_deferred_and_snapshot_resumable(player):
    state, _, spell = cast_at(player=player, mana={'R': 1, 'G': 2})
    assert state.players[player].mana_pool['G'] == 2
    assert resolve(state)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choose(state, ['pay'], 3-player)
    assert serialize_match_snapshot(state) == before
    state = deserialize_match_snapshot(before)
    state = choose(state, ['pay'])
    assert state.players[player].mana_pool.get('G', 0) == 0
    assert len(state.stack) == 1 and state.cards[spell].zone == Zone.STACK
    assert resolve(state)


def test_stifle_can_counter_ward_without_countering_original_spell():
    state, _, spell = cast_at(mana={'R': 1, 'U': 1})
    ward_id = state.stack[-1].id
    stifle = add(state, 'Stifle', 1, Zone.HAND)
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': stifle.id,
                         'targets': {'target_stack_id': ward_id}})
    assert resolve(state)
    assert [i.source_card_id for i in state.stack] == [spell]
    assert resolve(state) and not state.pending_mechanic_choice


@pytest.mark.parametrize('name,cost', [('Sedgemoor Witch', 3), ('Phyrexian Fleshgorger', 7)])
@pytest.mark.parametrize('departed', [False, True])
def test_life_payment_uses_resolution_power_or_last_known_information(name, cost, departed):
    state, target, _ = cast_at(name)
    if name == 'Phyrexian Fleshgorger':
        state.cards[target].counters['+1/+1'] = 2
        cost += 2
    if departed:
        destroy_permanent(state, 1, {'target_card_id': target})
    assert resolve(state)
    assert state.pending_mechanic_choice['ward_cost']['amount'] == cost
    state = choose(state, ['pay'])
    assert state.players[1].life == 20-cost


def test_discard_payment_requires_deliberate_card_selection_and_resume():
    state, _, _ = cast_at('Graveyard Trespasser')
    first = add(state, 'Island', 1, Zone.HAND)
    second = add(state, 'Counterspell', 1, Zone.HAND)
    assert resolve(state)
    state = choose(state, ['pay'])
    assert state.pending_mechanic_choice['kind'] == 'ward_cost_cards'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, [second.id])
    assert second.id in state.players[1].graveyard and first.id in state.players[1].hand
    assert len(state.stack) == 1


@pytest.mark.parametrize('name,cost,eligible', [
    ('Vein Ripper', 'sacrifice a creature', 'Grizzly Bears'),
    ('Sauron, the Dark Lord', 'sacrifice a legendary artifact or legendary creature', 'Svyelun of Sea and Sky'),
    ('Valgavoth, Terror Eater', 'sacrifice three nonland permanents', 'Sol Ring'),
])
def test_sacrifice_payment_enforces_actual_qualifications_and_count(name, cost, eligible):
    state, _, _ = cast_at(name)
    required = parse_ward_cost(cost)['amount']
    cards = [add(state, eligible) for _ in range(required)]
    land = add(state, 'Forest')
    assert land.id not in payment_cards(state, 1, parse_ward_cost(cost))
    assert resolve(state)
    state = choose(state, ['pay'])
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choose(state, [land.id]*required)
    assert serialize_match_snapshot(state) == before
    state = choose(state, [c.id for c in cards])
    assert all(c.id not in state.players[1].battlefield for c in cards)
    assert len(state.stack) == (2 if name == 'Vein Ripper' else 1)
    if name == 'Vein Ripper':
        assert state.stack[-1].payload['__trigger_event'] == 'creature_dies'


def test_granted_ward_multiplicity_and_no_friendly_target_trigger():
    state = clean()
    target = add(state, 'Merfolk of the Pearl Trident', 2)
    add(state, 'Svyelun of Sea and Sky', 2)
    armor = add(state, 'Leather Armor', 2)
    armor.attached_to = target.id
    assert ward_instances(state, target) == ['{1}', '{1}']
    source = add(state, 'Lightning Bolt', 1, Zone.STACK)
    add_to_stack(state, source.id, 1, source.name, 'deal_damage',
                 {'amount': 3, 'target_card_id': target.id, '__announced_targets': {'target_card_id': target.id}})
    assert len(state.stack) == 3
    state = clean()
    target = add(state, 'Tolarian Terror', 1)
    source = add(state, 'Lightning Bolt', 1, Zone.STACK)
    add_to_stack(state, source.id, 1, source.name, 'deal_damage', {'__announced_targets': {'target_card_id': target.id}})
    assert len(state.stack) == 1


def test_targeted_ability_and_copied_spell_get_ward_once_each():
    state = clean()
    target = add(state, 'Tolarian Terror', 2)
    source = add(state, 'Lightning Bolt', 1, Zone.BATTLEFIELD)
    ability = add_to_stack(state, source.id, 1, 'Targeted ability fixture', 'deal_damage',
                           {'amount': 3, 'target_card_id': target.id, '__announced_targets': {'target_card_id': target.id}}, is_spell=False)
    assert state.stack[-1].effect_key == 'ward_payment'
    assert resolve(state)
    state = choose(state, ['decline'])
    assert not state.stack and state.cards[source.id].zone == Zone.BATTLEFIELD
    state, _, _ = cast_at(mana={'R': 1, 'C': 4})
    original = state.stack[0]
    copy_spell(state, 1, {'target_stack_id': original.id})
    copied = next(i for i in state.stack if i.payload.get('__stack_copy_kind'))
    # Copy-target choice defaults to keep; entry hook runs after copy maker finishes.
    if state.pending_mechanic_choice:
        state = choose(state, ['keep'])
        copied = next(i for i in state.stack if i.payload.get('__stack_copy_kind'))
    mark_stack_targets(state, copied)
    count = len([i for i in state.stack if i.effect_key == 'ward_payment'])
    mark_stack_targets(state, copied)
    assert len([i for i in state.stack if i.effect_key == 'ward_payment']) == count == 2


@pytest.mark.parametrize('player', [1, 2])
def test_real_activated_ability_triggers_ward_and_survives_being_countered(player):
    state = clean(player)
    source = add(state, 'Prodigal Pyromancer', player)
    target = add(state, 'Tolarian Terror', 3-player)
    state = checked_action(state, RulesEngine(), player, {'type': 'activate_ability',
                         'card_id': source.id, 'ability_index': 0, 'targets': {'target_card_id': target.id}})
    assert state.cards[source.id].tapped and len(state.stack) == 2
    assert resolve(state)
    state = choose(state, ['decline'])
    assert not state.stack and state.cards[source.id].zone == Zone.BATTLEFIELD


def test_divided_spell_triggers_once_per_protected_target_not_damage_point():
    state = clean()
    first = add(state, 'Tolarian Terror', 2)
    second = add(state, 'Tolarian Terror', 2)
    source = add(state, 'Pyrotechnics', 1, Zone.HAND)
    state.players[1].mana_pool.update(R=1, G=4)
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source.id,
                         'targets': {'target_distribution': {first.id: 3, second.id: 1}}})
    assert len(state.stack) == 3
    assert {i.source_card_id for i in state.stack[1:]} == {first.id, second.id}


def test_restricted_artifact_mana_cannot_pay_ward():
    state, _, _ = cast_at()
    add(state, 'Renowned Weaponsmith')
    assert resolve(state)
    assert state.pending_mechanic_choice['options'] == ['decline']


@pytest.mark.parametrize('human', [False, True])
def test_targeted_entry_trigger_gets_ward_before_priority_returns(human):
    state = clean()
    target = add(state, 'Tolarian Terror', 2)
    source = add(state, 'Ravenous Chupacabra', 1, Zone.HAND)
    state.players[1].mana_pool.update(B=2, C=2)
    state.trigger_order_choice_required = human
    state.trigger_order_choice_players = {1, 2}
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source.id})
    state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    if human:
        assert state.pending_trigger_order['phase'] == 'targets'
        state = checked_action(state, RulesEngine(), 1, {'type': 'choose_trigger_target',
                             'stack_id': state.pending_trigger_order['current_stack_id'], 'target_card_id': target.id})
    assert len(state.stack) == 2 and state.stack[-1].effect_key == 'ward_payment'
    assert not state.trigger_staging


def test_real_copy_spell_places_new_ward_above_copy_after_target_choice():
    state, _, _ = cast_at(mana={'R': 1, 'U': 2, 'C': 4})
    original = state.stack[0]
    source = add(state, 'Twincast', 1, Zone.HAND)
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source.id,
                         'targets': {'target_stack_id': original.id}})
    state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    if state.pending_mechanic_choice:
        assert state.pending_mechanic_choice['kind'] == 'copy_target'
        state = choose(state, ['keep'])
    assert len([i for i in state.stack if i.effect_key == 'ward_payment']) == 2
    assert state.stack[-1].effect_key == 'ward_payment'


def test_unsupported_ward_cost_is_explicit_in_preflight():
    from rules_engine.coverage import known_unsupported_mechanics
    assert 'unsupported ward cost' in known_unsupported_mechanics('Ward {X}')


@pytest.mark.parametrize('archetype', ['Aggro', 'Burn', 'Control', 'Tempo', 'Midrange', 'Ramp', 'Drain', 'Tokens', 'Tribal', 'Reanimator'])
def test_ai_pays_for_profitable_removal_without_mutating_original(archetype):
    state, _, _ = cast_at('Sedgemoor Witch')
    assert resolve(state)
    before = serialize_match_snapshot(state)
    move = AIAgent('master', archetype).choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
    assert move == {'type': 'choose_mechanic', 'card_ids': ['pay']}
    assert serialize_match_snapshot(state) == before


def test_ai_declines_lethal_life_payment_and_uncounterable_spell():
    state, _, _ = cast_at('Sedgemoor Witch')
    state.players[1].life = 3
    assert resolve(state)
    assert AIAgent('master').choose_action(state, RulesEngine().legal_moves(state, 1), 1).action['card_ids'] == ['decline']
    state, target, _ = cast_at('Graveyard Trespasser', spell='Abrupt Decay', mana={'B': 1, 'G': 1})
    add(state, 'Island', 1, Zone.HAND)
    assert resolve(state)
    move = AIAgent('master').choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
    assert move['card_ids'] == ['decline']
    state = choose(state, ['decline'])
    assert resolve(state)
    assert state.cards[target].zone == Zone.GRAVEYARD
