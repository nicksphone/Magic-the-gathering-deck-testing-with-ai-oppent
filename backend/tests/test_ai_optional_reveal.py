"""AI handles offered reveal tokens rather than interpreting them as card IDs."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import checked_action
from tests.test_optional_reveal_transform import ENGINE, pending


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('eligible', [True, False])
@pytest.mark.parametrize('restore', [True, False])
def test_ai_explicit_reveal_or_decline_executes_and_preserves_library(seat, eligible, restore):
    state, source, top = pending(seat, eligible)
    if restore:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = list(state.players[seat].library)
    agent = AIAgent()
    agent.archetype = 'Tempo'
    decision = agent.choose_action(state, ENGINE.legal_moves(state, seat), seat)
    assert decision.action == {'type': 'choose_mechanic', 'card_ids': ['reveal' if eligible else 'decline']}
    state = checked_action(state, ENGINE, seat, decision.action)
    assert state.pending_mechanic_choice is None
    assert (state.cards[source].selected_face_index or 0) == (1 if eligible else 0)
    assert state.players[seat].library == before
    assert state.players[seat].library[-1] == top
