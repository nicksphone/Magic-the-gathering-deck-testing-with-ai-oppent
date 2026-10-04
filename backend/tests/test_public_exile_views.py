from fastapi.testclient import TestClient
import json
from pathlib import Path

from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from main import ACTIVE_MATCHES, MatchController, app
from rules_engine.engine import RulesEngine


def _state_with_exile():
    cards = {row['name']: row for name in ('land_types', 'public_foretell')
             for row in json.loads((Path(__file__).parent / 'fixtures' / (name + '.json')).read_text())}
    deck = [{"quantity": 58, "card_name": "Island"},
            *[{**cards[name], 'quantity': 1, 'card_name': name} for name in ('Lightning Bolt', 'Saw It Coming')]]
    state = MatchFactory.from_decks(deck, deck, seed=1023)
    visible_id = next(card.id for card in state.cards.values() if card.owner == 1 and card.name == 'Lightning Bolt')
    hidden_id = next(card.id for card in state.cards.values() if card.owner == 2 and card.name == 'Saw It Coming')
    visible = state.cards[visible_id]
    hidden = state.cards[hidden_id]
    for card in (visible, hidden):
        getattr(state.players[card.owner], card.zone.value).remove(card.id)
    visible.move_to_zone(Zone.EXILE)
    hidden.move_to_zone(Zone.EXILE)
    hidden.exile_face_down = True
    state.players[1].exile.append(visible_id)
    state.players[2].exile.append(hidden_id)
    return state, deck, visible_id, hidden_id


def test_public_exile_view_hides_face_down_card_and_survives_snapshot():
    state, _, visible_id, hidden_id = _state_with_exile()
    for current in (state, deserialize_match_snapshot(serialize_match_snapshot(state))):
        view = serialize_match(current)
        assert view["players"][1]["exile_count"] == 1
        assert [card["id"] for card in view["players"][1]["exile"]] == [visible_id]
        assert view["players"][2]["exile_count"] == 1
        assert view["players"][2]["exile"] == []
        assert "Saw It Coming" not in str(view)
        assert current.cards[hidden_id].exile_face_down
    state.cards[hidden_id].move_to_zone(Zone.HAND)
    assert not state.cards[hidden_id].exile_face_down


def test_match_http_exposes_face_up_exile_but_not_face_down_exile():
    state, deck, visible_id, _ = _state_with_exile()
    controller = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "ai"}, ai={},
        mode="player_vs_ai", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = controller
        try:
            response = client.get(f"/matches/{state.id}")
            assert response.status_code == 200
            payload = response.json()
            assert [card["id"] for card in payload["players"]["1"]["exile"]] == [visible_id]
            assert payload["players"]["2"]["exile"] == []
            assert payload["players"]["2"]["exile_count"] == 1
            assert "Counterspell" not in response.text
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
