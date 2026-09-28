"""Public views must not expose an AI opponent's hidden cards."""

from fastapi.testclient import TestClient

from game_state.serializers import serialize_match
from game_state.state import MatchFactory, Step
from main import ACTIVE_MATCHES, MatchController, _serialize_match_controller, app
from rules_engine.engine import RulesEngine


def test_public_match_and_legal_moves_hide_ai_hand_without_mutating_state():
    deck = [{"quantity": 60, "card_name": "Mountain", "type_line": "Basic Land - Mountain"}]
    state = MatchFactory.from_decks(deck, deck, seed=31)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    controller = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "ai"}, ai={},
        mode="player_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = controller
        try:
            public = client.get(f"/matches/{state.id}")
            assert public.status_code == 200
            players = public.json()["players"]
            assert len(players["1"]["hand"]) == players["1"]["hand_count"] == 7
            assert players["2"]["hand"] == []
            assert players["2"]["hand_count"] == 7
            assert len(state.players[2].hand) == 7
            assert len(serialize_match(state)["players"][2]["hand"]) == 7

            state.priority_player = 2
            moves = client.get(f"/matches/{state.id}/legal-moves")
            assert moves.status_code == 200
            assert moves.json()["player_id"] == 2
            assert moves.json()["moves"] == []
            forbidden = client.get(f"/matches/{state.id}/legal-moves?player_id=2")
            assert forbidden.status_code == 403
            assert forbidden.json()["detail"]["code"] == "ai_controlled_seat"
            assert client.get(f"/matches/{state.id}/legal-moves?player_id=1").status_code == 200

            controller.controllers[1] = "ai"
            spectator = _serialize_match_controller(controller)
            assert spectator["players"][1]["hand"] == []
            assert spectator["players"][2]["hand"] == []
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
