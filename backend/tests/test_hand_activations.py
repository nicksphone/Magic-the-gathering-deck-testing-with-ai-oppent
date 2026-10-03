"""Canonical hand activations: source zone, selected card costs and actual effects."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone, StackItem
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.costs import parse_activated_cost, activated_cost_available
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.targeting import stack_object_kind
from tests.test_activation_modifiers import board, add
from tests.test_ai_recurring_engines import add as raw_add, resolve
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/hand_activations.json').read_text())}


def hand_card(state, name, seat):
    return raw_add(state, name, seat, Zone.HAND, cards=ROWS)


def channel_moves(state, seat, cid):
    return [m for m in RulesEngine().legal_moves(state, seat)
            if m['type'] == 'activate_ability' and m['card_id'] == cid]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', [name for name, row in ROWS.items() if 'Discard this card' in row['oracle_text']])
def test_self_discard_requires_its_own_hand_card_not_another_card(seat, name):
    state = board(seat)
    card = hand_card(state, name, seat)
    ability = extract_activated_abilities(card)[0]
    parsed = parse_activated_cost(ability['mana_cost'])
    assert parsed.supported and parsed.discard_source and parsed.discard_cards == 0
    assert ability['activation_zone'] == 'hand'
    state.players[seat].mana_pool.update(C=10, U=4, G=4, R=4)
    assert activated_cost_available(state, seat, card.id, ability['mana_cost'], ability_index=ability['index'])
    assert not activated_cost_available(state, 3-seat, card.id, ability['mana_cost'], ability_index=ability['index'])
    state.players[seat].hand.remove(card.id)
    card.zone = Zone.BATTLEFIELD
    state.players[seat].battlefield.append(card.id)
    hand_card(state, name, seat)  # A different copy cannot pay the first one's cost.
    assert not activated_cost_available(state, seat, card.id, ability['mana_cost'], ability_index=ability['index'])
    assert not channel_moves(state, seat, card.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_damage_channel_discards_exact_source_and_is_not_a_spell(seat):
    state = board(seat)
    card = hand_card(state, 'Twinshot Sniper', seat)
    other = hand_card(state, 'Greater Tanuki', seat)
    card.last_known_battlefield = {'power': 20, 'colors': ['B'], 'controller': 3-seat}
    state.players[seat].mana_pool.update(C=1, R=1)
    action = {'type': 'activate_ability', 'card_id': card.id, 'ability_index': 0,
              'targets': {'target_player': 3-seat}}
    assert channel_moves(state, seat, card.id)
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.cards[card.id].zone == Zone.GRAVEYARD
    assert other.id in result.players[seat].hand
    assert stack_object_kind(result, result.stack[-1]) == 'activated'
    assert '__source_lki' not in result.stack[-1].payload
    assert sum(result.players[seat].mana_pool.values()) == 0
    restored = deserialize_match_snapshot(serialize_match_snapshot(result))
    result = resolve(restored)
    assert result.players[3-seat].life == 18
    assert result.cards[card.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('ability_index', [0, 1])
def test_two_hand_modes_use_their_own_cost_target_and_effect(seat, ability_index):
    state = board(seat)
    card = hand_card(state, 'Colossal Skyturtle', seat)
    target = add(state, 'Azure Mage', seat if ability_index == 0 else 3-seat,
                 Zone.GRAVEYARD if ability_index == 0 else Zone.BATTLEFIELD)
    state.players[seat].mana_pool.update(C=2 if ability_index == 0 else 1,
                                       G=1 if ability_index == 0 else 0,
                                       U=1 if ability_index == 1 else 0)
    action = {'type': 'activate_ability', 'card_id': card.id, 'ability_index': ability_index,
              'targets': {'target_card_id': target.id}}
    result = resolve(checked_action(state, RulesEngine(), seat, action))
    assert result.cards[card.id].zone == Zone.GRAVEYARD
    assert result.cards[target.id].zone == Zone.HAND
    assert target.id in result.players[target.owner].hand
    assert sum(result.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_hand_activation_cannot_target_itself_in_graveyard_before_discard_cost(seat):
    state = board(seat)
    card = hand_card(state, 'Colossal Skyturtle', seat)
    add(state, 'Azure Mage', seat, Zone.GRAVEYARD)
    state.players[seat].mana_pool.update(C=2, G=1)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'activate_ability', 'card_id': card.id,
                       'ability_index': 0, 'targets': {'target_card_id': card.id}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_search_channel_uses_normal_search_and_tapped_entry(seat):
    state = board(seat)
    card = hand_card(state, 'Greater Tanuki', seat)
    state.players[seat].mana_pool.update(C=2, G=1)
    from rules_engine.card_types import printed_card_types
    raw = ROWS['Swamp']
    for cid in state.players[seat].library:
        state.cards[cid].type_line = raw['type_line']
        state.cards[cid].types = printed_card_types(raw['type_line'])
        state.cards[cid].oracle_text = raw['oracle_text']
    before = len(state.players[seat].library)
    result = resolve(checked_action(state, RulesEngine(), seat,
        {'type': 'activate_ability', 'card_id': card.id, 'ability_index': 0, 'targets': {}}))
    assert result.cards[card.id].zone == Zone.GRAVEYARD
    assert len(result.players[seat].library) == before-1
    lands = [result.cards[cid] for cid in result.players[seat].battlefield if 'Land' in result.cards[cid].types]
    assert len(lands) == 1 and lands[0].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_channel_can_respond_to_an_ability_not_only_a_spell(seat):
    state = board(seat)
    card = hand_card(state, 'Mirrorshell Crab', seat)
    state.players[seat].mana_pool.update(C=2, U=1)
    enemy = add(state, 'Azure Mage', 3-seat)
    item = StackItem(id=state.allocate_object_id(), source_card_id=enemy.id, controller=3-seat,
                     label='Azure Mage ability', effect_key='draw_cards', payload={'count': 1})
    state.stack.append(item)
    assert channel_moves(state, seat, card.id)
    result = resolve(checked_action(state, RulesEngine(), seat, {'type': 'activate_ability', 'card_id': card.id,
                     'ability_index': 0, 'targets': {'target_stack_id': item.id}}))
    assert not result.stack
    assert not result.players[3-seat].hand
    assert result.cards[card.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_channel_can_counter_a_canonical_trigger(seat):
    state = board(seat)
    source = hand_card(state, 'Mirrorshell Crab', seat)
    enemy = raw_add(state, 'Twinshot Sniper', 3-seat, cards=ROWS)
    item = StackItem(state.allocate_object_id(), enemy.id, 3-seat, 'Twinshot Sniper ETB',
                     'deal_damage', {'amount': 2, 'target_player': seat,
                                     '__trigger_event': 'enters_battlefield'})
    state.stack.append(item)
    state.players[seat].mana_pool.update(C=2, U=1)
    result = resolve(checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': source.id, 'ability_index': 0, 'targets': {'target_stack_id': item.id}}))
    assert result.players[seat].life == 20 and not result.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('decision', ['pay', 'decline'])
def test_counter_payment_belongs_to_target_controller_and_survives_snapshot(seat, decision):
    state = board(seat)
    card = hand_card(state, 'Mirrorshell Crab', seat)
    enemy = add(state, 'Azure Mage', 3-seat)
    state.players[seat].mana_pool.update(C=2, U=1)
    state.players[3-seat].mana_pool['C'] = 3
    state.mechanic_choice_players = {3-seat}
    item = StackItem(id=state.allocate_object_id(), source_card_id=enemy.id, controller=3-seat,
                     label='Azure Mage ability', effect_key='draw_cards', payload={'count': 1})
    state.stack.append(item)
    result = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability', 'card_id': card.id,
        'ability_index': 0, 'targets': {'target_stack_id': item.id, 'pay_unless_counter': decision != 'pay'}})
    rules = RulesEngine()
    rules.take_action(result, result.priority_player, {'type': 'pass_priority'})
    rules.take_action(result, result.priority_player, {'type': 'pass_priority'})
    assert result.pending_mechanic_choice['kind'] == 'counter_payment'
    assert result.pending_mechanic_choice['player_id'] == 3-seat
    before = serialize_match_snapshot(result)
    with pytest.raises(ActionRejected):
        checked_action(result, rules, seat, {'type': 'choose_mechanic', 'card_ids': [decision]})
    assert serialize_match_snapshot(result) == before
    restored = deserialize_match_snapshot(before)
    result = checked_action(restored, rules, 3-seat, {'type': 'choose_mechanic', 'card_ids': [decision]})
    assert not result.pending_mechanic_choice
    assert bool(result.stack) == (decision == 'pay')
    assert result.players[3-seat].mana_pool['C'] == (0 if decision == 'pay' else 3)
    result = resolve(result)
    assert len(result.players[3-seat].hand) == int(decision == 'pay')


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_card_mode_includes_noncreatures_and_excludes_other_owner(seat):
    from tests.test_counterability_scope import add_card
    state = board(seat)
    source = hand_card(state, 'Colossal Skyturtle', seat)
    target = add_card(state, 'Lightning Bolt', Zone.GRAVEYARD, seat)
    enemy = add_card(state, 'Lightning Bolt', Zone.GRAVEYARD, 3-seat)
    state.players[seat].mana_pool.update(C=2, G=1)
    moves = channel_moves(state, seat, source.id)
    assert [t['id'] for t in moves[0]['target_hints']['graveyard_card_targets']] == [target.id]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'activate_ability', 'card_id': source.id,
                       'ability_index': 0, 'targets': {'target_card_id': enemy.id}})
    assert serialize_match_snapshot(state) == before
    result = resolve(checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
                     'card_id': source.id, 'ability_index': 0, 'targets': {'target_card_id': target.id}}))
    assert result.cards[target.id].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
def test_source_discard_replacement_does_not_remove_channel_ability(seat):
    from tests.test_opening_hand import CARDS
    state = board(seat)
    raw = {'power': None, 'toughness': None, 'keywords': [], **CARDS['Leyline of the Void']}
    raw_add(state, 'Leyline of the Void', 3-seat, cards={'Leyline of the Void': raw})
    source = hand_card(state, 'Twinshot Sniper', seat)
    state.players[seat].mana_pool.update(C=1, R=1)
    result = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': source.id, 'ability_index': 0, 'targets': {'target_player': 3-seat}})
    assert result.cards[source.id].zone == Zone.EXILE
    assert stack_object_kind(result, result.stack[-1]) == 'activated'
    assert resolve(result).players[3-seat].life == 18


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Midrange'])
def test_ai_channels_counter_to_answer_lethal_stack(seat, difficulty, style):
    from ai.agent import AIAgent
    from tests.test_counterability_scope import add_card
    state = board(seat)
    source = hand_card(state, 'Mirrorshell Crab', seat)
    bolt = add_card(state, 'Lightning Bolt', Zone.STACK, 3-seat)
    state.stack.append(StackItem('bolt', bolt.id, 3-seat, bolt.name, 'deal_damage',
                                {'amount': 3, 'target_player': seat}))
    state.players[seat].life = 2
    state.players[seat].mana_pool.update(C=2, U=1)
    decision = AIAgent(archetype=style, difficulty=difficulty).choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['type'] == 'activate_ability', decision
    assert decision.action['card_id'] == source.id
    assert decision.action['targets']['target_stack_id'] == 'bolt'
    result = resolve(checked_action(state, RulesEngine(), seat, decision.action))
    assert result.players[seat].life == 2 and result.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_http_channel_restores_hand_source_and_stack_from_sqlite(game, seat):
    import main
    client, controller = game
    state = board(seat)
    state.id = controller.state.id
    controller.state = state
    source = hand_card(state, 'Twinshot Sniper', seat)
    state.players[seat].mana_pool.update(C=1, R=1)
    persist(controller)
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
              'targets': {'target_player': 3-seat}}
    rejected(client, controller, action, player_id=3-seat)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    main.ACTIVE_MATCHES.pop(state.id)
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert client.get(f'/matches/{state.id}').status_code == 200
    restored = main.ACTIVE_MATCHES[state.id].state
    assert restored.cards[source.id].zone == Zone.GRAVEYARD
    assert stack_object_kind(restored, restored.stack[-1]) == 'activated'
    for _ in range(2):
        response = client.post(f'/matches/{state.id}/action', json={
            'player_id': restored.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
        restored = main.ACTIVE_MATCHES[state.id].state
    assert restored.players[3-seat].life == 18
