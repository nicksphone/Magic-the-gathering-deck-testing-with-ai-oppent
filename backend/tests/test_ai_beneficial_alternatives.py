"""Canonical original spells choose beneficiaries, not hostile default targets."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_combat_stats
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_ai_recurring_engines import add
from tests.test_landfall_alternatives import position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['groundswell', 'rest-for-the-weary'])
@pytest.mark.parametrize('enhanced', [False, True])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
def test_original_alternative_targets_own_beneficiary_and_resolves(seat, name, enhanced, style):
    state, spell, own, _ = position(name, seat)
    enemy = add(state, 'Torrential Gearhulk', 3-seat)
    state.land_entries_this_turn[seat] = int(enhanced)
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'cast_spell' and m['card_id'] == spell.id)
    before = serialize_match_snapshot(state)
    action = AIAgent(archetype=style)._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    if name == 'groundswell':
        assert action['targets']['target_card_id'] == own.id
    else:
        assert action['targets']['target_player'] == seat
    state = checked_action(state, RulesEngine(), seat, action)
    assert resolve_top_of_stack(state)
    if name == 'groundswell':
        amount = 4 if enhanced else 2
        assert effective_combat_stats(state, own.id) == (5+amount, 6+amount)
        assert effective_combat_stats(state, enemy.id) == (5, 6)
    else:
        assert state.players[seat].life == (28 if enhanced else 24)
        assert state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['groundswell', 'rest-for-the-weary'])
def test_common_beneficial_polarity_does_not_guess_unknown_history(seat, name):
    state, spell, own, _ = position(name, seat)
    add(state, 'Torrential Gearhulk', 3-seat)
    state.land_entry_history_known = False
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'cast_spell' and m['card_id'] == spell.id)
    before = serialize_match_snapshot(state)
    action = AIAgent()._materialize_action(state, move, seat)
    assert action['targets'].get('target_card_id') == own.id if name == 'groundswell' else action['targets'].get('target_player') == seat
    assert serialize_match_snapshot(state) == before
