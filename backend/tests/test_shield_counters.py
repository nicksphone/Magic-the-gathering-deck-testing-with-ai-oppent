"""Canonical counter consequences; fixture boards are not invented deck cards."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from effects.handlers import deal_damage
from game_state.state import Zone, Step
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.counter_placement import put_counters
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.combat import _mark_creature_damage, _deal_unblocked_damage
from rules_engine.replacement import replacement_options
from tests.test_named_counters import CARDS as NAMED, add as named_add
from tests.test_ai_recurring_engines import fixture, add as raw_add
from tests.test_api_input_contracts import game


CARDS = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/shield_counters.json').read_text())}


def add(state, name, player=1):
    return raw_add(state, name, player, cards=CARDS)


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('amount', [0, 1, 5])
def test_damage_consumes_one_per_event_not_per_point_or_per_counter(player, amount):
    state = fixture()
    bear = named_add(state, player=player)
    put_counters(state, 'shield', 3, target_card_id=bear.id)
    stamp = bear.counter_timestamps['shield']
    assert deal_damage(state, 3-player, {'target_card_id': bear.id, 'amount': amount}) == 0
    assert bear.counters['shield'] == (2 if amount else 3)
    assert bear.counter_timestamps['shield'] == stamp
    assert '__damage_marked' not in bear.counters
    assert bear.zone == Zone.BATTLEFIELD
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.cards[bear.id].counters == bear.counters


def test_unpreventable_damage_spends_only_one_shield_and_numeric_prevention_is_not_spent():
    state = fixture()
    bear = named_add(state)
    put_counters(state, 'shield', 3, target_card_id=bear.id)
    bear.counters['__prevent_damage_shield'] = 10
    state.turn_damage_cant_be_prevented = True
    assert deal_damage(state, 2, {'target_card_id': bear.id, 'amount': 1}) == 1
    assert bear.counters['shield'] == 2
    assert bear.counters['__prevent_damage_shield'] == 10
    assert bear.counters['__damage_marked'] == 1


@pytest.mark.parametrize('effect', ['destroy_permanent', 'destroy_all_creatures'])
def test_effect_destruction_spends_one_shield_but_indestructible_spends_none(effect):
    state = fixture()
    shielded = named_add(state)
    protected = named_add(state, player=2)
    vulnerable = named_add(state)
    for card in (shielded, protected):
        put_counters(state, 'shield', 2, target_card_id=card.id)
    put_counters(state, 'indestructible', 1, target_card_id=protected.id)
    for card in (shielded, protected, vulnerable):
        resolve_effect(state, 1, effect, {'target_card_id': card.id})
        if effect == 'destroy_all_creatures':
            break
    assert shielded.zone == protected.zone == Zone.BATTLEFIELD
    assert shielded.counters['shield'] == 1
    assert protected.counters['shield'] == 2
    assert vulnerable.zone == Zone.GRAVEYARD
    resolve_effect(state, 1, 'destroy_permanent', {'target_card_id': shielded.id})
    assert 'shield' not in shielded.counters and 'shield' not in shielded.counter_timestamps
    resolve_effect(state, 1, 'destroy_permanent', {'target_card_id': shielded.id})
    assert shielded.zone == Zone.GRAVEYARD


@pytest.mark.parametrize('effect', ['destroy_all_artifacts', 'destroy_all_enchantments', 'destroy_all_artifacts_and_enchantments'])
def test_mass_noncreature_destruction_has_same_shield_and_indestructible_checks(effect):
    state = fixture()
    name = "Urza's Armor" if effect == 'destroy_all_artifacts' else 'Lashknife Barrier'
    shielded = add(state, name)
    protected = add(state, name, 2)
    vulnerable = add(state, name)
    for card in (shielded, protected):
        put_counters(state, 'shield', 2, target_card_id=card.id)
    put_counters(state, 'indestructible', 1, target_card_id=protected.id)
    resolve_effect(state, 1, effect, {})
    assert shielded.zone == protected.zone == Zone.BATTLEFIELD
    assert shielded.counters['shield'] == 1 and protected.counters['shield'] == 2
    assert vulnerable.zone == Zone.GRAVEYARD


@pytest.mark.parametrize('reason', ['zero', 'lethal', 'deathtouch', 'sacrifice', 'exile'])
def test_shields_do_not_stop_non_effect_destruction_or_other_zone_changes(reason):
    state = fixture()
    bear = named_add(state)
    put_counters(state, 'shield', 2, target_card_id=bear.id)
    if reason == 'sacrifice':
        resolve_effect(state, 1, 'sacrifice', {'target_card_id': bear.id})
    elif reason == 'exile':
        resolve_effect(state, 2, 'exile', {'target_card_id': bear.id})
    else:
        bear.counters[{'zero':'__eot_toughness', 'lethal':'__damage_marked', 'deathtouch':'__deathtouch_damaged'}[reason]] = -2 if reason == 'zero' else 2
        apply_state_based_actions(state)
    assert bear.zone == (Zone.EXILE if reason == 'exile' else Zone.GRAVEYARD)
    assert 'shield' not in bear.counters and 'shield' not in bear.counter_timestamps


def test_noncreature_damage_and_off_battlefield_attempt():
    state = fixture()
    armor = add(state, "Urza's Armor")
    put_counters(state, 'shield', 1, target_card_id=armor.id)
    assert deal_damage(state, 2, {'target_card_id': armor.id, 'amount': 4}) == 0
    assert 'shield' not in armor.counters
    armor.move_to_zone(Zone.HAND)
    armor.counters['shield'] = 1
    assert deal_damage(state, 2, {'target_card_id': armor.id, 'amount': 4}) == 0
    assert armor.counters['shield'] == 1


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('choice', ['shield', 'reduction'])
def test_affected_player_can_preserve_shield_by_reducing_damage_to_zero_and_resume(player, choice):
    state = fixture()
    state.replacement_choice_required = True
    state.replacement_choice_players = {player}
    bear = named_add(state, player=player)
    barrier = add(state, 'Lashknife Barrier', player)
    put_counters(state, 'shield', 2, target_card_id=bear.id)
    add_to_stack(state, 'canonical-damage-fixture', 3-player, 'Damage fixture', 'deal_damage',
                 {'target_card_id': bear.id, 'amount': 1}, is_spell=False)
    assert not resolve_top_of_stack(state)
    pending = state.pending_replacement_choice
    assert pending['player_id'] == player
    ids = {o['source_id'] for o in pending['options']}
    shield = f'shield-counter:{bear.id}'
    assert ids == {shield, barrier.id}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), player,
        {'type':'choose_replacement', 'replacement_source_id':shield if choice == 'shield' else barrier.id})
    assert not state.pending_replacement_choice and not state.stack
    assert state.cards[bear.id].counters['shield'] == (1 if choice == 'shield' else 2)
    assert '__damage_marked' not in state.cards[bear.id].counters


def test_human_damage_chain_never_reapplies_reduction_and_spends_shield_once():
    state = fixture()
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    bear = named_add(state)
    barrier = add(state, 'Lashknife Barrier')
    put_counters(state, 'shield', 3, target_card_id=bear.id)
    add_to_stack(state, 'canonical-damage-fixture', 2, 'Damage fixture', 'deal_damage',
                 {'target_card_id':bear.id, 'amount':5}, is_spell=False)
    assert not resolve_top_of_stack(state)
    state = checked_action(state, RulesEngine(), 1,
        {'type':'choose_replacement', 'replacement_source_id':barrier.id})
    assert state.pending_replacement_choice['amount'] == 4
    assert [o['source_id'] for o in state.pending_replacement_choice['options']] == [f'shield-counter:{bear.id}']
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 1,
        {'type':'choose_replacement', 'replacement_source_id':f'shield-counter:{bear.id}'})
    assert not state.pending_replacement_choice and not state.stack
    assert state.cards[bear.id].counters['shield'] == 2


def test_damage_reduction_is_not_prevention_and_can_precede_shield_when_unpreventable():
    state = fixture()
    bear = named_add(state)
    barrier = add(state, 'Lashknife Barrier')
    put_counters(state, 'shield', 2, target_card_id=bear.id)
    state.turn_damage_cant_be_prevented = True
    assert {o['source_id'] for o in replacement_options(state,'damage_to_permanent',target_card_id=bear.id)} == {barrier.id, f'shield-counter:{bear.id}'}
    assert deal_damage(state, 2, {'target_card_id':bear.id, 'amount':1, '__replacement_source_id':barrier.id}) == 0
    assert bear.counters['shield'] == 2


@pytest.mark.parametrize('unpreventable', [False, True])
def test_combat_shield_stops_damage_results_unless_unpreventable(unpreventable):
    state = fixture()
    bear = named_add(state)
    source = add(state, 'Questing Beast', 2) if unpreventable else named_add(state, player=2)
    put_counters(state, 'shield', 3, target_card_id=bear.id)
    assert _mark_creature_damage(state, bear.id, 1, deathtouch=True, source_id=source.id) == (1 if unpreventable else 0)
    assert bear.counters['shield'] == 2
    assert bool(bear.counters.get('__deathtouch_damaged')) == unpreventable
    assert bool(bear.counters.get('__damage_marked')) == unpreventable


def test_damage_reduction_does_not_apply_to_noncreature_permanents():
    state = fixture()
    add(state, 'Lashknife Barrier')
    armor = add(state, "Urza's Armor")
    assert deal_damage(state, 2, {'target_card_id':armor.id, 'amount':1}) == 1


def test_ai_chooses_free_reduction_before_shield_without_mutating_hidden_state():
    from ai.agent import AIAgent
    state = fixture()
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    bear = named_add(state)
    barrier = add(state, 'Lashknife Barrier')
    put_counters(state, 'shield', 2, target_card_id=bear.id)
    add_to_stack(state, 'canonical-damage-fixture', 2, 'Damage fixture', 'deal_damage',
                 {'target_card_id':bear.id, 'amount':1}, is_spell=False)
    assert not resolve_top_of_stack(state)
    before = serialize_match_snapshot(state)
    move = AIAgent('master').choose_action(state, RulesEngine().legal_moves(state,1), 1).action
    assert move['replacement_source_id'] == barrier.id
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, move)
    assert state.cards[bear.id].counters['shield'] == 2


def test_combat_only_override_leaves_other_controllers_and_noncombat_damage_preventable():
    state = fixture()
    beast = add(state, 'Questing Beast', 2)
    source = named_add(state, player=2)
    bear = named_add(state)
    put_counters(state, 'shield', 3, target_card_id=bear.id)
    assert deal_damage(state,2,{'target_card_id':bear.id,'amount':1,'__source_card_id':source.id}) == 0
    assert bear.counters['shield'] == 2
    assert _mark_creature_damage(state,bear.id,1,source_id=source.id) == 1
    assert bear.counters['shield'] == 1
    put_counters(state,'shield',1,target_card_id=beast.id)
    assert _mark_creature_damage(state,beast.id,1,source_id=bear.id) == 0
    assert 'shield' not in beast.counters


def test_combat_and_spell_damage_to_planeswalker_use_the_same_counter_effect():
    from game_state.state import CardInstance
    from rules_engine.card_types import printed_card_types
    seed = json.loads((Path(__file__).parent.parent/'card_data/builtin_oracle_seed.json').read_text())['cards']['Ugin, the Spirit Dragon']
    state = fixture()
    ugin = CardInstance(id=state.allocate_object_id(),name=seed['name'],owner=1,controller=1,
        zone=Zone.BATTLEFIELD, types=printed_card_types(seed['type_line']),type_line=seed['type_line'],
        mana_cost=seed['mana_cost'],oracle_text=seed['oracle_text'],loyalty=int(seed['loyalty']))
    state.cards[ugin.id] = ugin
    state.players[1].battlefield.append(ugin.id)
    source = named_add(state,player=2)
    put_counters(state,'shield',2,target_card_id=ugin.id)
    assert _deal_unblocked_damage(state,f'planeswalker:{ugin.id}',5,source.id) == 0
    assert ugin.loyalty == 7 and ugin.counters['shield'] == 1
    assert deal_damage(state,2,{'target_card_id':ugin.id,'amount':5}) == 0
    assert ugin.loyalty == 7 and 'shield' not in ugin.counters
    assert _deal_unblocked_damage(state,f'planeswalker:{ugin.id}',5,source.id) == 5
    assert ugin.loyalty == 2


def test_actual_noncombat_damage_preserves_deathtouch_after_shield_is_gone():
    state = fixture()
    bear = named_add(state)
    source = add(state, 'Questing Beast', 2)
    put_counters(state,'shield',1,target_card_id=bear.id)
    payload = {'target_card_id':bear.id,'amount':1,'__source_card_id':source.id}
    assert deal_damage(state,2,payload) == 0
    assert bear.zone == Zone.BATTLEFIELD and '__deathtouch_damaged' not in bear.counters
    assert deal_damage(state,2,payload) == 1
    assert bear.zone == Zone.GRAVEYARD


def test_natural_blocked_combat_protection_uses_both_shield_counters():
    from rules_engine.combat import declare_attackers, declare_blockers, begin_combat_damage
    state = fixture()
    attacker = named_add(state)
    blocker = named_add(state,player=2)
    for card in (attacker,blocker):
        put_counters(state,'shield',2,target_card_id=card.id)
    state.step = Step.DECLARE_ATTACKERS
    declare_attackers(state,[attacker.id])
    state.step = Step.DECLARE_BLOCKERS
    declare_blockers(state,{attacker.id:blocker.id})
    state.step = Step.COMBAT_DAMAGE
    begin_combat_damage(state)
    apply_state_based_actions(state)
    for card in (attacker,blocker):
        assert card.zone == Zone.BATTLEFIELD
        assert card.counters['shield'] == 1
        assert '__damage_marked' not in card.counters


def test_multiple_blockers_are_one_simultaneous_shield_event():
    from rules_engine.combat import declare_attackers, declare_blockers, begin_combat_damage
    state = fixture()
    attacker = named_add(state)
    blockers = [named_add(state,player=2) for _ in range(2)]
    put_counters(state,'shield',1,target_card_id=attacker.id)
    state.step = Step.DECLARE_ATTACKERS
    declare_attackers(state,[attacker.id])
    state.step = Step.DECLARE_BLOCKERS
    declare_blockers(state,{attacker.id:[c.id for c in blockers]})
    state.step = Step.COMBAT_DAMAGE
    begin_combat_damage(state)
    apply_state_based_actions(state)
    assert attacker.zone == Zone.BATTLEFIELD
    assert 'shield' not in attacker.counters and '__damage_marked' not in attacker.counters
    assert sum('removes a shield counter' in line for line in state.log) == 1


def test_first_strike_and_regular_damage_are_distinct_shield_events():
    from rules_engine.combat import declare_attackers, declare_blockers, begin_combat_damage, finish_combat_damage
    state = fixture()
    attacker = named_add(state)
    blockers = [named_add(state,player=2) for _ in range(2)]
    put_counters(state,'first strike',1,target_card_id=blockers[0].id)
    put_counters(state,'shield',2,target_card_id=attacker.id)
    state.step = Step.DECLARE_ATTACKERS
    declare_attackers(state,[attacker.id])
    state.step = Step.DECLARE_BLOCKERS
    declare_blockers(state,{attacker.id:[c.id for c in blockers]})
    state.step = Step.COMBAT_DAMAGE
    begin_combat_damage(state)
    assert attacker.counters['shield'] == 1
    finish_combat_damage(state)
    apply_state_based_actions(state)
    assert attacker.zone == Zone.BATTLEFIELD
    assert 'shield' not in attacker.counters and '__damage_marked' not in attacker.counters
    assert sum('removes a shield counter' in line for line in state.log) == 2


@pytest.mark.parametrize('player', [1, 2])
def test_http_virtual_shield_choice_survives_sqlite_restore_and_rejects_wrong_owner(game, player):
    from sqlmodel import Session
    import main
    from game_state.state import CardInstance
    from persistence.db import engine
    from persistence.repository import Repository
    from tests.test_api_input_contracts import persist, snapshot
    client, match = game
    state = match.state
    bear = named_add(state,player=player)
    barrier = add(state,'Lashknife Barrier',player)
    put_counters(state,'shield',2,target_card_id=bear.id)
    actor = 3-player
    seed = json.loads((Path(__file__).parent.parent/'card_data/builtin_oracle_seed.json').read_text())['cards']['Lightning Bolt']
    bolt = CardInstance(id=state.allocate_object_id(),name=seed['name'],owner=actor,controller=actor,
        zone=Zone.HAND,types=['Instant'],type_line=seed['type_line'],mana_cost=seed['mana_cost'],oracle_text=seed['oracle_text'])
    state.cards[bolt.id] = bolt
    state.players[actor].hand.append(bolt.id)
    state.players[actor].mana_pool['R'] = 1
    state.priority_player = actor
    persist(match)
    path = f'/matches/{state.id}/action'
    response = client.post(path,json={'player_id':actor,'action':{'type':'cast_spell','card_id':bolt.id,'targets':{'target_card_id':bear.id}}})
    assert response.status_code == 200, response.text
    for _ in range(4):
        if match.state.pending_replacement_choice:
            break
        response = client.post(path,json={'player_id':match.state.priority_player,'action':{'type':'pass_priority'}})
        assert response.status_code == 200, response.text
    assert match.state.pending_replacement_choice['player_id'] == player
    before = snapshot(match)
    response = client.post(path,json={'player_id':actor,'action':{'type':'choose_replacement','replacement_source_id':barrier.id}})
    assert response.status_code in (403,422)
    assert snapshot(match) == before
    response = client.post(path,json={'player_id':player,'action':{'type':'choose_replacement','replacement_source_id':barrier.id}})
    assert response.status_code == 200, response.text
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session),state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert restored.state.pending_replacement_choice['amount'] == 2
    shield_id = f'shield-counter:{bear.id}'
    response = client.get(f'/matches/{state.id}/legal-moves?player_id={player}')
    assert response.status_code == 200
    assert [m['replacement_source_id'] for m in response.json()['moves']] == [shield_id]
    response = client.post(path,json={'player_id':player,'action':{'type':'choose_replacement','replacement_source_id':shield_id}})
    assert response.status_code == 200, response.text
    assert not restored.state.stack and not restored.state.pending_replacement_choice
    assert restored.state.cards[bear.id].counters['shield'] == 1
    assert restored.state.cards[bolt.id].zone == Zone.GRAVEYARD
