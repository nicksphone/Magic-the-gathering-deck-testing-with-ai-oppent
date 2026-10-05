"""Explicit activated payments use unchanged canonical cards, not board order."""
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from ai.agent import AIAgent
from tests.test_ai_search_prefix import bare_state
from tests.test_contextual_cost_prohibitions import canonical
from tests.test_linked_damage_targets import raw_card
from tests.test_ai_recurring_engines import add


def activation_card(state, name, seat, zone=Zone.BATTLEFIELD):
    raw = json.loads((Path(__file__).parent / 'fixtures/activation_payment_choices' / (name+'.json')).read_text())
    return raw_card(state, raw, seat, zone)


def position(seat, kind):
    state = bare_state(seat)
    if kind == 'sacrifice':
        source = canonical(state, 'viscera-seer', seat)
        candidates = [source, canonical(state, 'viscera-seer', seat)]
        key = 'sacrifice_card_ids'
    else:
        source = activation_card(state, 'rummaging-goblin', seat)
        candidates = [canonical(state, 'sacred-foundry', seat, Zone.HAND),
                      canonical(state, 'dismember', seat, Zone.HAND)]
        key = 'discard_card_ids'
    return state, source, candidates, key


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['sacrifice', 'discard'])
@pytest.mark.parametrize('chosen_index', [0, 1])
def test_declared_activation_resource_is_paid_instead_of_default_board_hand_order(seat, kind, chosen_index):
    state, source, cards, key = position(seat, kind)
    chosen = cards[chosen_index]
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
        'payment_choices': {key: [chosen.id]},
    })
    assert len(state.stack) == 1
    assert chosen.id in state.players[seat].graveyard
    assert cards[1-chosen_index].id not in state.players[seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['sacrifice', 'discard'])
@pytest.mark.parametrize('invalid', ['empty', 'duplicate', 'wrong_player'])
def test_invalid_selected_activation_resources_are_rejected_before_any_authoritative_mutation(seat, kind, invalid):
    state, source, cards, key = position(seat, kind)
    foreign = canonical(state, 'viscera-seer', 3-seat, Zone.BATTLEFIELD if kind == 'sacrifice' else Zone.HAND)
    ids = {'empty': [], 'duplicate': [cards[0].id, cards[0].id], 'wrong_player': [foreign.id]}[invalid]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
            'payment_choices': {key: ids},
        })
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['sacrifice', 'discard'])
def test_legal_move_exposes_actual_actor_payment_candidates_and_required_count(seat, kind):
    state, source, cards, key = position(seat, kind)
    canonical(state, 'viscera-seer', 3-seat, Zone.BATTLEFIELD if kind == 'sacrifice' else Zone.HAND)
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'activate_ability' and move.get('card_id') == source.id)
    payment = move['payment_options']
    assert set(payment[key]) == {card.id for card in cards}
    assert payment['sacrifice_creatures' if kind == 'sacrifice' else 'discard_cards'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Control', 'Tempo', 'Ramp', 'Midrange', 'Drain', 'Tokens', 'Tribal', 'Reanimator'])
def test_ai_selects_lower_value_resource_instead_of_default_source_preservation(seat, style):
    state = bare_state(seat)
    source = canonical(state, 'viscera-seer', seat)
    threat = add(state, 'Torrential Gearhulk', seat)
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'activate_ability' and move.get('card_id') == source.id)
    before = serialize_match_snapshot(state)
    action = AIAgent(archetype=style)._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    assert action['payment_choices']['sacrifice_card_ids'] == [source.id]
    paid = checked_action(state, RulesEngine(), seat, action)
    assert source.id in paid.players[seat].graveyard
    assert threat.id in paid.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_ai_does_not_sacrifice_a_creature_for_unneeded_proactive_scry(seat):
    state = bare_state(seat)
    source = canonical(state, 'viscera-seer', seat)
    add(state, 'Torrential Gearhulk', seat)
    action = AIAgent(archetype='Control').choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert not (action['type'] == 'activate_ability' and action.get('card_id') == source.id)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('chosen_index', [0, 1])
def test_artifact_sacrifice_can_choose_source_or_other_artifact_after_mana_and_tap(seat, chosen_index):
    state = bare_state(seat)
    source = activation_card(state, 'trading-post', seat)
    other = activation_card(state, 'trading-post', seat)
    state.players[seat].mana_pool = {'C': 1}
    chosen = [source, other][chosen_index]
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': source.id, 'ability_index': 3,
        'payment_choices': {'sacrifice_card_ids': [chosen.id]},
    })
    assert state.players[seat].mana_pool['C'] == 0
    assert chosen.id in state.players[seat].graveyard
    assert len(state.stack) == 1
    if chosen_index == 1:
        assert state.cards[source.id].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_mandatory_source_sacrifice_cannot_be_replaced_by_another_artifact(seat):
    state = bare_state(seat)
    fixtures = json.loads((Path(__file__).parent / 'fixtures/activation_modifiers.json').read_text())
    raw = next(card for card in fixtures if card['name'] == 'Mind Stone')
    source = raw_card(state, raw, seat, Zone.BATTLEFIELD)
    other = raw_card(state, raw, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {color: int(color == 'C') for color in 'WUBRGC'}
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'activate_ability' and move.get('card_id') == source.id)
    assert move['payment_options']['fixed_sacrifice_card_ids'] == [source.id]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'activate_ability', 'card_id': source.id,
            'ability_index': move['ability_index'],
            'payment_choices': {'sacrifice_card_ids': [other.id]},
        })
    assert serialize_match_snapshot(state) == before
    action = AIAgent(archetype='Control')._materialize_action(state, move, seat)
    assert action['payment_choices']['sacrifice_card_ids'] == [source.id]
    paid = checked_action(state, RulesEngine(), seat, action)
    assert source.id in paid.players[seat].graveyard
    assert other.id in paid.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_selected_borrowed_creature_is_paid_from_controller_to_owner_graveyard(seat):
    state = bare_state(seat)
    source = canonical(state, 'viscera-seer', seat)
    borrowed = canonical(state, 'viscera-seer', 3-seat)
    state.players[3-seat].battlefield.remove(borrowed.id)
    state.players[seat].battlefield.append(borrowed.id)
    borrowed.controller = seat
    paid = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
        'payment_choices': {'sacrifice_card_ids': [borrowed.id]},
    })
    assert borrowed.id in paid.players[3-seat].graveyard
    assert borrowed.id not in paid.players[seat].graveyard
    assert borrowed.id not in paid.players[seat].battlefield
    assert source.id in paid.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Control', 'Tempo', 'Ramp', 'Midrange', 'Drain', 'Tokens', 'Tribal', 'Reanimator'])
def test_ai_discard_payment_preserves_needed_land_instead_of_hand_order(seat, style):
    state, source, cards, _ = position(seat, 'discard')
    land, spell = cards
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'activate_ability' and move.get('card_id') == source.id)
    before = serialize_match_snapshot(state)
    action = AIAgent(archetype=style)._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    assert action['payment_choices']['discard_card_ids'] == [spell.id]
    paid = checked_action(state, RulesEngine(), seat, action)
    assert spell.id in paid.players[seat].graveyard
    assert land.id in paid.players[seat].hand
