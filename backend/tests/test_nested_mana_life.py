"""Canonical mana life costs must not spend the outer activation's life budget."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from tests.test_ai_search_prefix import bare_state
from tests.test_life_lock_suppression import restriction
from tests.test_linked_damage_targets import raw_card
from tests.test_contextual_cost_prohibitions import canonical


def position(seat, life):
    state = bare_state(seat)
    source = restriction(state, 'erebos-god-of-the-dead', seat)
    raw = json.loads((Path(__file__).parent / 'fixtures/nested_mana_life/mana-confluence.json').read_text())
    for _ in range(2):
        raw_card(state, raw, seat, Zone.BATTLEFIELD)
    state.players[seat].life = life
    return state, source


@pytest.mark.parametrize('seat', [1, 2])
def test_mana_availability_reserves_outer_life_after_all_nested_mana_costs(seat):
    state, _ = position(seat, 3)
    before = serialize_match_snapshot(state)
    assert not can_pay_with_pool_and_lands(state, seat, '{1}{B}', reserved_life=2)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_underfunded_combined_mana_and_activation_life_cost_is_atomically_rejected(seat):
    state, source = position(seat, 3)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
        })
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_funded_combined_mana_and_activation_life_cost_actually_pays_all_four_life(seat):
    state, source = position(seat, 5)
    paid = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
    })
    assert paid.players[seat].life == 1
    assert len(paid.stack) == 1
    assert sum(paid.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('free_lands', [1, 2])
def test_activation_finds_lower_life_mana_sources_even_when_painful_sources_are_first(seat, free_lands):
    state, source = position(seat, 4)
    fixtures = json.loads((Path(__file__).parent / 'fixtures/mana_abilities.json').read_text())
    raw = next(card for card in fixtures if card['name'] == 'Swamp')
    for _ in range(free_lands):
        raw_card(state, raw, seat, Zone.BATTLEFIELD)
    paid = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
    })
    assert paid.players[seat].life == free_lands
    assert len(paid.stack) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [2, 3])
def test_generic_only_mana_payment_preserves_external_life_and_rejects_without_mutation(seat, life):
    state, _ = position(seat, life)
    fixtures = json.loads((Path(__file__).parent / 'fixtures/mana_abilities.json').read_text())
    raw_card(state, next(card for card in fixtures if card['name'] == 'Swamp'), seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{2}', reserved_life=2) == (life == 3)
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{2}', reserved_life=2) == (life == 3)
    if life == 2:
        assert serialize_match_snapshot(state) == before
    else:
        assert state.players[seat].life == 2
        assert sum(state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [3, 5])
def test_phyrexian_payment_and_mana_production_share_one_life_budget(seat, life):
    state, _ = position(seat, life)
    spell = canonical(state, 'dismember', seat, Zone.HAND)
    target = canonical(state, 'viscera-seer', 3-seat)
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, spell.mana_cost, card_name=spell.name,
                                      hybrid_choices=['B', 'P']) == (life == 5)
    assert serialize_match_snapshot(state) == before
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'targets': {'target_card_id': target.id}, 'cost_choice': {'id': 'base'},
              'hybrid_choices': ['B', 'P']}
    if life == 3:
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, action)
        assert serialize_match_snapshot(state) == before
    else:
        paid = checked_action(state, RulesEngine(), seat, action)
        assert paid.players[seat].life == 1
        assert len(paid.stack) == 1
        assert sum(paid.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [2, 3])
def test_snow_and_ordinary_mana_share_nested_life_budget(seat, life):
    state, _ = position(seat, life)
    raw = json.loads((Path(__file__).parent / 'fixtures/nested_mana_life/snow-covered-swamp.json').read_text())
    raw_card(state, raw, seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{S}{B}', reserved_life=2) == (life == 3)
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{S}{B}', reserved_life=2) == (life == 3)
    if life == 2:
        assert serialize_match_snapshot(state) == before
    else:
        assert state.players[seat].life == 2
        assert sum(state.players[seat].mana_pool.values()) == 0
        assert sum(state.players[seat].snow_mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [2, 3])
def test_paid_mana_ability_funding_preserves_outer_life_budget(seat, life):
    state = bare_state(seat)
    state.players[seat].life = life
    fixtures = json.loads((Path(__file__).parent / 'fixtures/mana_abilities.json').read_text())
    for name in ['Cabal Coffers', 'Swamp', 'Swamp', 'Swamp']:
        card = raw_card(state, next(card for card in fixtures if card['name'] == name), seat, Zone.BATTLEFIELD)
        if name == 'Swamp' and sum(state.cards[cid].name == 'Swamp' for cid in state.players[seat].battlefield) > 1:
            card.tapped = True
    raw = json.loads((Path(__file__).parent / 'fixtures/nested_mana_life/mana-confluence.json').read_text())
    raw_card(state, raw, seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{B}{B}{B}', reserved_life=2) == (life == 3)
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{B}{B}{B}', reserved_life=2) == (life == 3)
    if life == 2:
        assert serialize_match_snapshot(state) == before
    else:
        assert state.players[seat].life == 2
        assert sum(state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Control', 'Tempo', 'Ramp', 'Midrange', 'Drain', 'Tokens', 'Tribal', 'Reanimator'])
def test_ai_materializes_a_funded_nonlethal_phyrexian_payment_across_styles(seat, style):
    state, _ = position(seat, 5)
    spell = canonical(state, 'dismember', seat, Zone.HAND)
    canonical(state, 'viscera-seer', 3-seat)
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move.get('card_id') == spell.id)
    before = serialize_match_snapshot(state)
    action = AIAgent(archetype=style)._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    paid = checked_action(state, RulesEngine(), seat, action)
    assert paid.players[seat].life == 1
    assert len(paid.stack) == 1
