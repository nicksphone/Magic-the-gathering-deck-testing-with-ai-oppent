"""Printed Scryfall fixtures exercise opening actions, not invented card effects."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, Zone, pregame_actor
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.opening_hand import can_begin_on_battlefield
from rules_engine.targeting import player_target_immunity
from tests.test_api_input_contracts import game, persist, snapshot


CARDS = {row["name"]: row for row in json.loads((Path(__file__).parent / "fixtures" / "opening_hand.json").read_text())}


def opening_game(starter=1):
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck, seed=54)
    state.active_player = state.priority_player = starter
    return state


def add_opening(state, name, pid=1):
    raw = CARDS[name]
    cid = f"opening-{pid}-{len(state.cards)}"
    state.cards[cid] = CardInstance(
        id=cid, name=name, owner=pid, controller=pid, zone=Zone.HAND,
        types=[kind for kind in ("Enchantment", "Land") if kind in raw["type_line"]],
        type_line=raw["type_line"], mana_cost=raw["mana_cost"], oracle_text=raw["oracle_text"],
        colors=raw["colors"],
    )
    state.players[pid].hand.append(cid)
    return cid


def keep_both(state):
    rules = RulesEngine()
    state = checked_action(state, rules, state.active_player, {"type": "keep_hand"})
    return checked_action(state, rules, 3 - state.active_player, {"type": "keep_hand"})


@pytest.mark.parametrize("name", ["Leyline of the Void", "Leyline of Sanctity", "Leyline of Vitality", "Leyline of Anticipation"])
def test_plain_printed_opening_entries_are_available_only_after_keeps(name):
    state = opening_game()
    cid = add_opening(state, name)
    rules = RulesEngine()
    assert all(move["type"] != "choose_mechanic" for move in rules.legal_moves(state, 1))
    state = keep_both(state)
    assert state.pregame_pending
    assert cid in state.pending_mechanic_choice["options"]
    state = checked_action(state, rules, 1, {"type": "choose_mechanic", "card_ids": [cid]})
    assert not state.pregame_pending
    assert state.step.value == "upkeep"
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].effect_timestamp > 0
    assert not state.stack
    assert not any(state.players[1].mana_pool.values())


def test_starting_player_chooses_in_any_order_then_other_player_after_restore():
    state, rules = opening_game(2), RulesEngine()
    void = add_opening(state, "Leyline of the Void", 2)
    anticipation = add_opening(state, "Leyline of Anticipation", 2)
    sanctity = add_opening(state, "Leyline of Sanctity", 1)
    state = keep_both(state)
    state = checked_action(state, rules, 2, {"type": "choose_mechanic", "card_ids": [anticipation]})
    assert pregame_actor(state) == 2
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    for original in (state, restored):
        candidate = checked_action(original, rules, 2, {"type": "choose_mechanic", "card_ids": [void]})
        assert pregame_actor(candidate) == 1
        assert candidate.pending_mechanic_choice["options"] == [sanctity, "__finish_opening__"]
        final = checked_action(candidate, rules, 1, {"type": "choose_mechanic", "card_ids": [sanctity]})
        assert not final.pregame_pending
        assert player_target_immunity(final, 1, 2) == "hexproof"


def test_declining_retains_cards_and_wrong_seat_or_stale_choice_cannot_mutate():
    state, rules = opening_game(), RulesEngine()
    cid = add_opening(state, "Leyline of Sanctity")
    state = keep_both(state)
    before = serialize_match_snapshot(state)
    for pid, action in [(2, {"type": "choose_mechanic", "card_ids": [cid]}),
                        (1, {"type": "choose_mechanic", "card_ids": ["missing"]}),
                        (1, {"type": "mulligan"})]:
        with pytest.raises(ActionRejected):
            checked_action(state, rules, pid, action)
        assert serialize_match_snapshot(state) == before
    state = checked_action(state, rules, 1, {"type": "choose_mechanic", "card_ids": ["__finish_opening__"]})
    assert cid in state.players[1].hand
    assert state.cards[cid].zone == Zone.HAND
    assert player_target_immunity(state, 1, 2) is None


@pytest.mark.parametrize("name", ["Leyline of Transformation"])
def test_extra_conditions_counters_costs_and_entry_choices_are_not_assumed(name):
    state, rules = opening_game(), RulesEngine()
    cid = add_opening(state, name)
    assert not can_begin_on_battlefield(state.cards[cid])
    state = keep_both(state)
    assert state.pending_mechanic_choice["options"] == ["__finish_opening__"]
    assert "not implemented" in state.pending_mechanic_choice["label"]
    state = checked_action(state, rules, 1, {"type": "choose_mechanic", "card_ids": ["__finish_opening__"]})
    assert cid in state.players[1].hand


@pytest.mark.parametrize("style", ["Control", "Aggro", "Tempo", "Ramp", "Drain", "Tribal", "Tokens"])
def test_ai_resolves_supported_opening_choice_without_casting(style):
    state, rules = opening_game(), RulesEngine()
    cid = add_opening(state, "Leyline of Sanctity")
    state = keep_both(state)
    action = AIAgent(difficulty="master", archetype=style).choose_action(state, rules.legal_moves(state, 1), 1).action
    assert action == {"type": "choose_mechanic", "card_ids": [cid]}
    assert not checked_action(state, rules, 1, action).pregame_pending


def test_http_opening_window_survives_sqlite_restore_and_wrong_seat_rejection(game):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository

    client, controller = game
    controller.state.pregame_pending = True
    controller.state.active_player = controller.state.priority_player = 2
    cid = add_opening(controller.state, "Leyline of Sanctity", 2)
    persist(controller)
    path = f"/matches/{controller.state.id}"
    for pid in (2, 1):
        response = client.post(path + "/action", json={"player_id": pid, "action": {"type": "keep_hand"}})
        assert response.status_code == 200, response.text
    before = snapshot(controller)
    action = {"type": "choose_mechanic", "card_ids": [cid]}
    assert client.post(path + "/action", json={"player_id": 1, "action": action}).status_code == 422
    assert snapshot(controller) == before
    main.ACTIVE_MATCHES.pop(controller.state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), controller.state.id)
    assert client.get(path + "/legal-moves").json()["player_id"] == 2
    response = client.post(path + "/action", json={"player_id": 2, "action": action})
    assert response.status_code == 200, response.text
    assert not response.json()["pregame_pending"]
    assert cid in main.ACTIVE_MATCHES[controller.state.id].state.players[2].battlefield


@pytest.mark.parametrize("name", ["Leyline of Sanctity", "Gemstone Caverns"])
def test_names_only_http_start_hydrates_cached_opening_clause_without_network(monkeypatch, name):
    import main
    from fastapi.testclient import TestClient
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    from card_data.sync import ScryfallSyncService

    network_calls = []

    def no_network(*args, **kwargs):
        network_calls.append((args, kwargs))
        raise AssertionError("Opening-hand fixture must hydrate from the local cache")

    monkeypatch.setattr(ScryfallSyncService, "sync_card_by_name", no_network)
    original = dict(main.ACTIVE_MATCHES)
    try:
        with TestClient(main.app) as client:
            raw = CARDS[name]
            with Session(engine) as session:
                Repository(session).upsert_card({
                    "scryfall_id": raw["id"], "name": raw["name"], "oracle_text": raw["oracle_text"],
                    "mana_cost": raw["mana_cost"], "type_line": raw["type_line"], "layout": raw["layout"],
                    "colors": "".join(raw["colors"]), "image_uri": "/card-images/generic-token-creature.svg",
                })
            # Dense sandbox deck makes opening access deterministic; not a legal constructed list.
            deck = [{"quantity": 60, "card_name": raw["name"]}]
            response = client.post("/matches/start", json={"deck_a": deck, "deck_b": deck,
                "sandbox": True, "controller_a": "human", "controller_b": "human",
                "mode": "human_vs_human", "seed": 54})
            assert response.status_code == 200, response.text
            path = f"/matches/{response.json()['id']}"
            for pid in (1, 2):
                response = client.post(path + "/action", json={"player_id": pid, "action": {"type": "keep_hand"}})
                assert response.status_code == 200, response.text
            assert response.json()["pending_mechanic_choice"]["kind"] == "opening_hand"
            pid = 1
            if name == "Gemstone Caverns":
                response = client.post(path + "/action", json={"player_id": 1,
                    "action": {"type": "choose_mechanic", "card_ids": ["__finish_opening__"]}})
                assert response.status_code == 200, response.text
                assert response.json()["pending_mechanic_choice"]["player_id"] == 2
                pid = 2
            cid = response.json()["pending_mechanic_choice"]["options"][0]
            response = client.post(path + "/action", json={"player_id": pid,
                "action": {"type": "choose_mechanic", "card_ids": [cid]}})
            assert response.status_code == 200, response.text
            assert response.json()["players"][str(pid)]["battlefield"][0]["name"] == raw["name"]
            if name == "Gemstone Caverns":
                assert response.json()["players"][str(pid)]["battlefield"][0]["counters"]["luck"] == 1
                assert response.json()["pending_mechanic_choice"]["kind"] == "opening_hand_exile"
            assert not network_calls
    finally:
        main.ACTIVE_MATCHES.clear()
        main.ACTIVE_MATCHES.update(original)
