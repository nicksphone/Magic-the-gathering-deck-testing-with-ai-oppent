"""Canonical joint payments must preserve the declared nonmana resources."""
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from ai.agent import AIAgent
from tests.test_activation_payment_choices import activation_card
from tests.test_ai_search_prefix import bare_state
from tests.test_linked_damage_targets import raw_card
from tests.test_contextual_cost_prohibitions import canonical


def petal(state, seat):
    raw = json.loads((Path(__file__).parent / 'fixtures/joint_activation_payment/lotus-petal.json').read_text())
    return raw_card(state, raw, seat, Zone.BATTLEFIELD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected_index', [0, 1])
def test_mana_planner_uses_other_petal_to_preserve_explicit_artifact_payment(seat, selected_index):
    state = bare_state(seat)
    source = activation_card(state, 'trading-post', seat)
    petals = [petal(state, seat), petal(state, seat)]
    selected, mana_source = petals[selected_index], petals[1-selected_index]
    before = serialize_match_snapshot(state)
    paid = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': source.id, 'ability_index': 3,
        'payment_choices': {'sacrifice_card_ids': [selected.id]},
    })
    assert serialize_match_snapshot(state) == before
    assert len(paid.stack) == 1
    assert paid.cards[source.id].tapped
    assert selected.id in paid.players[seat].graveyard
    assert mana_source.id in paid.players[seat].graveyard
    assert sum(paid.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_one_petal_cannot_pay_both_mana_and_declared_artifact_sacrifice(seat):
    state = bare_state(seat)
    source = activation_card(state, 'trading-post', seat)
    selected = petal(state, seat)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'activate_ability', 'card_id': source.id, 'ability_index': 3,
            'payment_choices': {'sacrifice_card_ids': [selected.id]},
        })
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_selected_artifact_can_tap_for_mana_before_its_sacrifice(seat):
    state = bare_state(seat)
    source = activation_card(state, 'trading-post', seat)
    fixtures = json.loads((Path(__file__).parent / 'fixtures/activation_modifiers.json').read_text())
    raw = next(card for card in fixtures if card['name'] == 'Mind Stone')
    selected = raw_card(state, raw, seat, Zone.BATTLEFIELD)
    paid = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': source.id, 'ability_index': 3,
        'payment_choices': {'sacrifice_card_ids': [selected.id]},
    })
    assert len(paid.stack) == 1
    assert selected.id in paid.players[seat].graveyard
    assert any('Mind Stone' in line and ('for C' in line or '1 C' in line) for line in paid.log)


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_resource_selection_finds_jointly_payable_source_sacrifice(seat):
    state = bare_state(seat)
    source = activation_card(state, 'trading-post', seat)
    mana_source = petal(state, seat)
    assert any(move['type'] == 'activate_ability' and move.get('card_id') == source.id
               and move.get('ability_index') == 3 for move in RulesEngine().legal_moves(state, seat))
    paid = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': source.id, 'ability_index': 3,
    })
    assert len(paid.stack) == 1
    assert source.id in paid.players[seat].graveyard
    assert mana_source.id in paid.players[seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Ramp', 'Midrange', 'Tempo'])
def test_ai_resource_selection_uses_feasible_joint_cost_not_cheapest_impossible_resource(seat, style):
    state = bare_state(seat)
    source = activation_card(state, 'trading-post', seat)
    mana_source = petal(state, seat)
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'activate_ability' and move.get('card_id') == source.id
                and move.get('ability_index') == 3)
    before = serialize_match_snapshot(state)
    action = AIAgent(archetype=style)._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    paid = checked_action(state, RulesEngine(), seat, action)
    assert len(paid.stack) == 1
    assert source.id in paid.players[seat].graveyard
    assert mana_source.id in paid.players[seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('other_creature', [False, True])
def test_mana_ability_cannot_consume_another_reserved_creature_but_can_choose_alternative(seat, other_creature):
    state = bare_state(seat)
    raw = json.loads((Path(__file__).parent / 'fixtures/joint_activation_payment/phyrexian-tower.json').read_text())
    tower = raw_card(state, raw, seat, Zone.BATTLEFIELD)
    reserved = canonical(state, 'viscera-seer', seat)
    other = canonical(state, 'viscera-seer', seat) if other_creature else None
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{B}{B}', reserved_card_ids={reserved.id}) == other_creature
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{B}{B}', reserved_card_ids={reserved.id}) == other_creature
    if other is None:
        assert serialize_match_snapshot(state) == before
    else:
        assert reserved.id in state.players[seat].battlefield
        assert other.id in state.players[seat].graveyard
        assert state.cards[tower.id].tapped
        assert state.players[seat].mana_pool['B'] == 0
