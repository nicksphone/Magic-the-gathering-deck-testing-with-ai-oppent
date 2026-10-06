"""Canonical AI spell payments, public reservations and immediate admission."""
from copy import deepcopy

import pytest

from tests.test_mana_executor_choices import ROWS, position, add
from ai.agent import AIAgent
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['resource', 'hybrid', 'reservation'])
def test_actual_ai_spell_cast_uses_internal_mana_plan(seat, family):
    state = position(seat)
    for _ in range(5):
        add(state, 'Forest', seat, Zone.LIBRARY)
    if family == 'resource':
        source = add(state, 'Skirk Prospector', seat)
        victim = add(state, 'Raging Goblin', seat)
        spell = add(state, 'Shock', seat, Zone.HAND)
    elif family == 'hybrid':
        source = add(state, 'Flooded Grove', seat)
        state.players[seat].mana_pool['G'] = 1
        spell = add(state, 'Growth Spiral', seat, Zone.HAND)
    else:
        source = add(state, 'Phyrexian Tower', seat)
        add(state, 'Raging Goblin', seat)
        add(state, 'Raging Goblin', seat)
        spell = add(state, 'Village Rites', seat, Zone.HAND)
    engine = RulesEngine()
    legal = engine.legal_moves(state, seat)
    assert any(m['type'] == 'cast_spell' and m.get('card_id') == spell.id for m in legal)
    assert not any(m['type'] == 'activate_ability' and m.get('card_id') == source.id for m in legal)
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Control', difficulty='master').choose_action(state, legal, seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'cast_spell', decision
    assert decision.action['card_id'] == spell.id
    result = checked_action(state, engine, seat, decision.action)
    assert result.stack and result.cards[spell.id].zone == Zone.STACK
    if family == 'hybrid':
        assert result.cards[source.id].tapped
    else:
        assert any(result.cards[cid].zone == Zone.GRAVEYARD for cid in state.players[seat].battlefield)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_source_free_goblin_mana_repeats_only_while_actual_resources_remain(seat):
    state = position(seat)
    source = add(state, 'Skirk Prospector', seat)
    source.tapped = True
    source.summoning_sick = True
    held = add(state, 'Raging Goblin', seat)
    other = add(state, 'Raging Goblin', seat)
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{R}{R}{R}')
    assert not can_pay_with_pool_and_lands(state, seat, '{R}{R}{R}{R}')
    assert can_pay_with_pool_and_lands(state, seat, '{R}{R}', reserved_card_ids=[held.id])
    assert not can_pay_with_pool_and_lands(state, seat, '{R}{R}{R}', reserved_card_ids=[held.id])
    assert serialize_match_snapshot(state) == before
    paid = deepcopy(state)
    assert auto_pay_cost(paid, seat, '{R}{R}', reserved_card_ids=[held.id])
    assert paid.cards[held.id].zone == Zone.BATTLEFIELD
    assert paid.cards[other.id].zone == Zone.GRAVEYARD
    assert paid.cards[source.id].zone == Zone.GRAVEYARD
    assert not paid.stack and not paid.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_supplied_additional_cost_reservation_is_honored_by_mana_executor(seat):
    state = position(seat)
    source = add(state, 'Phyrexian Tower', seat)
    held = add(state, 'Raging Goblin', seat)
    fuel = add(state, 'Raging Goblin', seat)
    spell = add(state, 'Village Rites', seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, spell.mana_cost,
        reserved_card_ids=[held.id], oracle_text=spell.oracle_text)
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, spell.mana_cost,
        reserved_card_ids=[held.id], oracle_text=spell.oracle_text)
    assert state.cards[held.id].zone == Zone.BATTLEFIELD
    assert state.cards[fuel.id].zone == Zone.GRAVEYARD
    assert state.cards[source.id].tapped
