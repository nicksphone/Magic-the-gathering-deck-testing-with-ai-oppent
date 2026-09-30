import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, pregame_actor
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_api_input_contracts import game, persist, snapshot


def new_game(starting_player=1):
    deck = [{"quantity": 30, "card_name": "Island"}, {"quantity": 30, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck, deck, seed=314)
    state.active_player = state.priority_player = starting_player
    return state


@pytest.mark.parametrize("starter", [1, 2])
def test_declarations_follow_starter_and_wait_before_any_redraw(starter):
    state = new_game(starter)
    rules = RulesEngine()
    other = 3 - starter
    before = serialize_match_snapshot(state)
    assert pregame_actor(state) == starter
    assert rules.legal_moves(state, other) == []
    with pytest.raises(ActionRejected):
        checked_action(state, rules, other, {"type": "mulligan"})
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, rules, starter, {"type": "mulligan"})
    assert state.mulligan_count == {1: 0, 2: 0}
    assert state.players[starter].hand == before["players"][str(starter)]["hand"]
    assert pregame_actor(state) == other
    assert rules.legal_moves(state, starter) == []
    state = checked_action(state, rules, other, {"type": "mulligan"})
    assert state.mulligan_count == {1: 1, 2: 1}
    assert not state.mulligan_declarations
    assert all(len(player.hand) == 7 for player in state.players.values())
    assert pregame_actor(state) == starter


def test_mid_round_snapshot_preserves_rng_declarations_and_next_actor():
    rules = RulesEngine()
    state = checked_action(new_game(2), rules, 2, {"type": "mulligan"})
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert pregame_actor(restored) == 1
    assert restored.mulligan_declarations == {2: "mulligan"}
    state = checked_action(state, rules, 1, {"type": "mulligan"})
    restored = checked_action(restored, rules, 1, {"type": "mulligan"})
    assert serialize_match_snapshot(state) == serialize_match_snapshot(restored)


def test_kept_player_sits_out_later_rounds_and_ordered_bottoms_are_preserved():
    rules = RulesEngine()
    state = checked_action(new_game(2), rules, 2, {"type": "mulligan"})
    state = checked_action(state, rules, 1, {"type": "keep_hand"})
    kept_hand = list(state.players[1].hand)
    state = checked_action(state, rules, 2, {"type": "mulligan"})
    assert state.mulligan_count[2] == 2
    assert state.players[1].hand == kept_hand
    assert rules.legal_moves(state, 1) == []
    bottom = list(state.players[2].hand[:2])
    state = checked_action(state, rules, 2, {"type": "keep_hand", "bottom_card_ids": bottom})
    assert not state.pregame_pending
    assert state.players[2].library[:2] == bottom
    assert len(state.players[2].hand) == 5
    assert state.active_player == 2


def test_legacy_snapshot_without_declaration_field_resumes_from_unkept_starter():
    payload = serialize_match_snapshot(new_game(2))
    payload.pop("mulligan_declarations")
    state = deserialize_match_snapshot(payload)
    assert state.mulligan_declarations == {}
    assert pregame_actor(state) == 2


def test_http_mid_round_restoration_keeps_actor_and_rejects_repeat_declaration(game):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository

    client, controller = game
    state = controller.state
    state.pregame_pending = True
    state.active_player = state.priority_player = 2
    persist(controller)
    path = f"/matches/{state.id}"
    response = client.post(path + "/action", json={"player_id": 2, "action": {"type": "mulligan"}})
    assert response.status_code == 200
    assert len(controller.state.players[2].hand) == 7
    assert controller.state.mulligan_count[2] == 0
    before = snapshot(controller)
    response = client.post(path + "/action", json={"player_id": 2, "action": {"type": "mulligan"}})
    assert response.status_code == 422
    assert snapshot(controller) == before
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert restored.state.mulligan_declarations == {2: "mulligan"}
    assert client.get(path + "/legal-moves").json()["player_id"] == 1
    assert client.get(path + "/legal-moves", params={"player_id": 2}).json()["moves"] == []
    response = client.post(path + "/action", json={"player_id": 1, "action": {"type": "keep_hand"}})
    assert response.status_code == 200
    assert restored.state.mulligan_count[2] == 1
    assert restored.state.mulligan_declarations == {}
    assert client.get(path + "/legal-moves").json()["player_id"] == 2
