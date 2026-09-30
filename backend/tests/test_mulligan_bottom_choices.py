import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import pregame_actor
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_mulligan_rounds import new_game


def redraw_both():
    state, rules = new_game(2), RulesEngine()
    state = checked_action(state, rules, 2, {"type": "mulligan"})
    return checked_action(state, rules, 1, {"type": "mulligan"})


def test_required_bottom_choices_block_next_round_and_survive_restore():
    state, rules = redraw_both(), RulesEngine()
    assert pregame_actor(state) == 2
    before = serialize_match_snapshot(state)
    for action in ({"type": "keep_hand"}, {"type": "mulligan"}, {"type": "choose_mechanic", "card_ids": []}):
        with pytest.raises(ActionRejected):
            checked_action(state, rules, 2, action)
        assert serialize_match_snapshot(state) == before
    selected = state.players[2].hand[:1]
    state = checked_action(state, rules, 2, {"type": "choose_mechanic", "card_ids": selected})
    assert len(state.players[2].hand) == 6
    assert state.players[2].library[:1] == selected
    assert state.pending_mechanic_choice["player_id"] == 1
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    selected = state.players[1].hand[:1]
    state = checked_action(state, rules, 1, {"type": "choose_mechanic", "card_ids": selected})
    restored = checked_action(restored, rules, 1, {"type": "choose_mechanic", "card_ids": selected})
    assert serialize_match_snapshot(state) == serialize_match_snapshot(restored)
    assert state.pending_mechanic_choice is None
    assert pregame_actor(state) == 2
    state = checked_action(state, rules, 2, {"type": "keep_hand"})
    state = checked_action(state, rules, 1, {"type": "keep_hand"})
    assert not state.pregame_pending
    assert all(len(player.hand) == 6 for player in state.players.values())


@pytest.mark.parametrize("style", ["Control", "Aggro", "Ramp", "Tempo", "Drain", "Tribal", "Tokens"])
def test_ai_resolves_bottom_choice_before_deciding_to_keep_or_mulligan(style):
    state, rules = redraw_both(), RulesEngine()
    ai = AIAgent(difficulty="master", archetype=style)
    for pid in (2, 1):
        action = ai.choose_action(state, rules.legal_moves(state, pid), pid).action
        assert action["type"] == "choose_mechanic"
        assert len(action["card_ids"]) == 1
        state = checked_action(state, rules, pid, action)
    assert state.mulligan_bottomed == {1: 1, 2: 1}


def test_legacy_unbottomed_snapshot_does_not_silently_drop_selection():
    state, rules = new_game(), RulesEngine()
    state.mulligan_count[1] = 1
    payload = serialize_match_snapshot(state)
    payload.pop("mulligan_bottomed")
    state = deserialize_match_snapshot(payload)
    selected = state.players[1].hand[:1]
    state = checked_action(state, rules, 1, {"type": "keep_hand", "bottom_card_ids": selected})
    assert state.players[1].library[:1] == selected
    assert len(state.players[1].hand) == 6
