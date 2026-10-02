"""Private partition/order decisions resume without losing library or clauses."""
import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.scry import finish_scry
from tests.test_ai_recurring_engines import fixture


def choose(state, player, ids):
    return checked_action(state, RulesEngine(), player, {'type': 'choose_mechanic', 'card_ids': ids})


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('bottom_count', [0, 1, 3])
def test_scry_partition_and_top_order_are_atomic_and_survive_restart(player, bottom_count):
    state = fixture()
    library = list(state.players[player].library)
    resolve_effect(state, player, 'scry', {'amount': 3})
    top = state.pending_mechanic_choice['options']
    bottom = list(reversed(top[:bottom_count]))
    state = choose(state, player, bottom)
    remaining = [cid for cid in top if cid not in bottom]
    if len(remaining) > 1:
        assert state.players[player].library == library
        assert state.pending_mechanic_choice['kind'] == 'scry_top_order'
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = choose(state, player, list(reversed(remaining)))
        remaining = list(reversed(remaining))
    assert state.players[player].library == bottom + library[:-3] + list(reversed(remaining))
    assert set(state.players[player].library) == set(library)
    assert not state.pending_mechanic_choice


@pytest.mark.parametrize('ids', [None, ['invalid'], [1], ['repeat', 'repeat']])
def test_bad_scry_choices_do_not_mutate_state(ids):
    state = fixture()
    resolve_effect(state, 1, 'scry', {'amount': 2})
    before = serialize_match_snapshot(state)
    assert not finish_scry(state, 1, {'card_ids': ids})
    assert serialize_match_snapshot(state) == before


def test_wrong_owner_rejected_without_disclosing_or_mutating_top_cards():
    state = fixture()
    resolve_effect(state, 2, 'scry', {'amount': 2})
    assert RulesEngine().legal_moves(state, 1) == []
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choose(state, 1, [])
    assert serialize_match_snapshot(state) == before


def test_scry_zero_empty_and_short_library_do_not_draw_or_lose():
    state = fixture()
    before = serialize_match_snapshot(state)
    resolve_effect(state, 1, 'scry', {'amount': 0})
    assert serialize_match_snapshot(state) == before
    state.players[1].library = state.players[1].library[-1:]
    resolve_effect(state, 1, 'scry', {'amount': 4})
    assert state.pending_mechanic_choice['count'] == 1
    state = choose(state, 1, [])
    assert state.winner is None and len(state.players[1].library) == 1
    state.players[1].library.clear()
    resolve_effect(state, 1, 'scry', {'amount': 1})
    assert state.pending_mechanic_choice is None and state.winner is None


def test_scry_resumes_later_draw_exactly_once_after_reordering():
    state = fixture()
    library = list(state.players[1].library)
    resolve_effect(state, 1, 'effect_sequence', {'effects': [
        {'effect_key': 'scry', 'payload': {'amount': 2}},
        {'effect_key': 'draw_cards', 'payload': {'amount': 1}},
    ]})
    state = choose(state, 1, [])
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 1, [library[-2], library[-1]])
    assert state.players[1].hand == [library[-2]]
    assert len(state.players[1].library) == len(library)-1
    assert not state.pending_mechanic_choice


def test_ai_scry_uses_legal_inspected_choices_and_does_not_change_state():
    state = fixture()
    resolve_effect(state, 1, 'scry', {'amount': 3})
    original = serialize_match_snapshot(state)
    agent = AIAgent(difficulty='master', archetype='Control')
    decision = agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action['type'] == 'choose_mechanic'
    assert serialize_match_snapshot(state) == original
    state = choose(state, 1, decision.action['card_ids'])
    if state.pending_mechanic_choice:
        decision = agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
        state = choose(state, 1, decision.action['card_ids'])
    assert not state.pending_mechanic_choice
