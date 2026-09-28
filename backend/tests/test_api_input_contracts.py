"""Run API tests from an isolated source copy: lifespan uses a source-local DB."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import main
from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Step, Zone
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository


@pytest.fixture
def game(monkeypatch):
    monkeypatch.setattr(main, "_hydrate_deck_cards", lambda repo, deck: [{**fallback_card_payload(item["card_name"]), **item} for item in deck])
    original = dict(main.ACTIVE_MATCHES)
    with TestClient(main.app) as client:
        deck = [{"quantity": 60, "card_name": "Island"}]
        response = client.post("/matches/start", json={"deck_a": deck, "deck_b": deck, "controller_a": "human", "controller_b": "human", "mode": "human_vs_human", "seed": 4})
        assert response.status_code == 200
        controller = main.ACTIVE_MATCHES[response.json()["id"]]
        controller.state.pregame_pending = False
        controller.state.step = Step.PRECOMBAT_MAIN
        persist(controller)
        yield client, controller
    main.ACTIVE_MATCHES.clear()
    main.ACTIVE_MATCHES.update(original)


def persist(controller):
    with Session(engine) as session:
        main._persist_active_match(Repository(session), controller)


def snapshot(controller):
    with sqlite3.connect(DATABASE_PATH) as connection:
        database = list(connection.iterdump())
    return json.dumps(serialize_match_snapshot(controller.state), sort_keys=True), deepcopy(main._controller_snapshot(controller)), database


def rejected(client, controller, action, player_id=1):
    before = snapshot(controller)
    response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": player_id, "action": action})
    assert response.status_code in (403, 422), response.text
    assert snapshot(controller) == before
    return response


@pytest.mark.parametrize("action", [
    {}, {"type": "invented_action"}, {"type": "play_land"},
    {"type": "play_land", "card_id": "stale"},
    {"type": "activate_ability", "card_id": "stale", "ability_index": "0"},
    {"type": "cast_spell", "card_id": "stale", "targets": []},
    {"type": "cast_spell", "card_id": "stale", "targets": {"x_value": -1}},
    {"type": "cast_spell", "card_id": "stale", "targets": {"target_player": 99}},
    {"type": "cast_spell", "card_id": "stale", "targets": {"top_n": 1000}},
    {"type": "cast_spell", "card_id": "stale", "targets": {"__source_card_id": "other"}},
    {"type": "block", "blocks": {"attacker": "blocker"}},
    {"type": "crew", "card_id": "stale", "crew_card_ids": [1]},
    {"type": "choose_mechanic", "card_ids": [], "choice_id": "draw"},
    {"type": "tap_lands_bulk", "land_name": "Island", "count": 0},
    {"type": "pass_priority", "extra": True},
])
def test_malformed_actions_do_not_mutate_memory_or_database(game, action):
    rejected(*game, action)


@pytest.mark.parametrize("deck", [[], [{"quantity": -1, "card_name": "Island"}], [{"card_name": "Island"}], [{"quantity": True, "card_name": "Island"}], [{"quantity": "60", "card_name": "Island"}], [{"quantity": 251, "card_name": "Island"}], [{"quantity": 60, "card_name": " "}], [{"quantity": 59, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island", "oracle_text": "Draw twenty cards."}]])
def test_bad_decks_are_rejected_before_starting_or_scheduling(game, deck):
    client, controller = game
    before = snapshot(controller)
    matches = set(main.ACTIVE_MATCHES)
    jobs = set(main.SIM_JOBS)
    for path in ("/matches/start", "/simulate/batch", "/simulate/batch/start"):
        response = client.post(path, json={"deck_a": deck, "deck_b": [{"quantity": 60, "card_name": "Island"}]})
        assert response.status_code == 422, response.text
    assert set(main.ACTIVE_MATCHES) == matches
    assert set(main.SIM_JOBS) == jobs
    assert snapshot(controller) == before


def test_explicit_sandbox_is_distinct_from_invalid_data(game):
    client, _ = game
    deck = [{"quantity": 7, "card_name": "Island"}]
    response = client.post("/matches/start", json={"deck_a": deck, "deck_b": deck, "sandbox": True})
    assert response.status_code == 200
    response = client.post("/matches/start", json={"deck_a": [], "deck_b": deck, "sandbox": True})
    assert response.status_code == 422


def test_invalid_query_and_wrong_priority_are_rejected(game):
    client, controller = game
    before = snapshot(controller)
    assert client.get(f"/matches/{controller.state.id}/legal-moves?player_id=99").status_code == 422
    assert client.get(f"/matches/{controller.state.id}/legal-moves?player_id=2").status_code == 200
    assert snapshot(controller) == before
    rejected(client, controller, {"type": "pass_priority"}, player_id=2)
    rejected(client, controller, {"type": "pass_priority"}, player_id=99)
    controller.controllers[1] = "ai"
    persist(controller)
    assert rejected(client, controller, {"type": "pass_priority"}).status_code == 403


def test_http_manual_nonland_mana_respects_priority_and_sacrifices_token(game):
    client, controller = game
    token = add_card(controller, "treasure-manual", "Treasure", Zone.BATTLEFIELD, ["Artifact", "Token"], text="{T}, Sacrifice this token: Add one mana of any color.")
    token.is_token = True
    persist(controller)
    before = snapshot(controller)
    rejected(client, controller, {"type": "tap_nonland_for_mana", "card_id": token.id, "color": "C"})
    rejected(client, controller, {"type": "tap_nonland_for_mana", "card_id": token.id, "color": "U"}, player_id=2)
    assert snapshot(controller) == before
    response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 1, "action": {"type": "tap_nonland_for_mana", "card_id": token.id, "color": "U"}})
    assert response.status_code == 200, response.text
    assert response.json()["players"]["1"]["mana_pool"]["U"] == 1
    assert token.id not in controller.state.players[1].battlefield


def add_card(controller, cid, name, zone, types, cost="", text="", power=None, toughness=None, loyalty=None, owner=1, keywords=None):
    card = CardInstance(id=cid, name=name, owner=owner, controller=owner, zone=zone, types=types, mana_cost=cost, oracle_text=text, power=power, toughness=toughness, loyalty=loyalty, summoning_sick=False, keywords=keywords or [])
    controller.state.cards[cid] = card
    getattr(controller.state.players[owner], zone.value).append(cid)
    return card


def test_failed_ability_targets_and_loyalty_costs_are_atomic(game):
    client, controller = game
    add_card(controller, "pyro", "Prodigal Pyromancer", Zone.BATTLEFIELD, ["Creature"], text="{T}: Prodigal Pyromancer deals 1 damage to any target.")
    add_card(controller, "chandra", "Chandra, Torch of Defiance", Zone.BATTLEFIELD, ["Planeswalker"], text="-3: Chandra, Torch of Defiance deals 4 damage to target creature.", loyalty=4)
    add_card(controller, "bear", "Grizzly Bears", Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2, owner=2)
    persist(controller)
    rejected(client, controller, {"type": "activate_ability", "card_id": "pyro", "ability_index": 0, "targets": {"target_card_id": "stale"}})
    rejected(client, controller, {"type": "activate_ability", "card_id": "pyro", "ability_index": 0})
    rejected(client, controller, {"type": "activate_loyalty", "card_id": "chandra", "ability_index": 0, "targets": {"target_card_id": controller.state.players[1].hand[0]}})
    assert controller.state.cards["chandra"].loyalty == 4
    assert not controller.state.cards["pyro"].tapped


@pytest.mark.parametrize("name,types,cost,text", [
    ("Ugin, the Spirit Dragon", ["Planeswalker"], "{8}", "+2: Ugin, the Spirit Dragon deals 3 damage to any target."),
    ("Prodigal Pyromancer", ["Creature"], "{2}{R}", "{T}: Prodigal Pyromancer deals 1 damage to any target."),
    ("Ravenous Chupacabra", ["Creature"], "{2}{B}{B}", "When Ravenous Chupacabra enters the battlefield, destroy target creature an opponent controls."),
])
def test_permanent_cast_does_not_require_its_later_ability_targets(game, name, types, cost, text):
    client, controller = game
    add_card(controller, "permanent", name, Zone.HAND, types, cost=cost, text=text)
    controller.state.players[1].mana_pool.update({"C": 8, "R": 1, "B": 2})
    persist(controller)
    response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 1, "action": {"type": "cast_spell", "card_id": "permanent"}})
    assert response.status_code == 200, response.text
    assert controller.state.cards["permanent"].zone == Zone.STACK
    # Targeted abilities remain separate choices when they actually trigger or
    # are activated; this test certifies cast admission, not ETB resolution.


@pytest.mark.parametrize("name,cost,text,target_name,target_types", [
    ("Beast Within", "{2}{G}", "Destroy target permanent.", "Grizzly Bears", ["Creature"]),
    ("Nature's Claim", "{G}", "Destroy target artifact or enchantment.", "Smuggler's Copter", ["Artifact"]),
    ("Stone Rain", "{2}{R}", "Destroy target land.", "Forest", ["Land"]),
])
def test_noncreature_target_surfaces_offer_and_accept_casts(game, name, cost, text, target_name, target_types):
    client, controller = game
    add_card(controller, "removal", name, Zone.HAND, ["Instant" if name != "Stone Rain" else "Sorcery"], cost, text)
    add_card(controller, "victim", target_name, Zone.BATTLEFIELD, target_types, owner=2, power=2, toughness=2)
    controller.state.players[1].mana_pool.update({"C": 3, "G": 1, "R": 1})
    persist(controller)
    moves = client.get(f"/matches/{controller.state.id}/legal-moves").json()["moves"]
    assert any(move.get("card_id") == "removal" and move["type"] == "cast_spell" for move in moves)
    response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 1, "action": {"type": "cast_spell", "card_id": "removal", "targets": {"target_card_id": "victim"}}})
    assert response.status_code == 200, response.text


def test_x_cost_failure_and_unknown_cost_face_or_zone_are_atomic(game):
    client, controller = game
    add_card(controller, "wastes", "Secure the Wastes", Zone.HAND, ["Instant"], "{X}{W}", "Create X 1/1 white Warrior creature tokens.")
    controller.state.players[1].mana_pool["W"] = 1
    persist(controller)
    rejected(client, controller, {"type": "cast_spell", "card_id": "wastes", "targets": {"x_value": 100}})
    rejected(client, controller, {"type": "cast_spell", "card_id": "wastes", "cost_choice": {"id": "free"}, "targets": {"x_value": 0}})
    rejected(client, controller, {"type": "cast_spell", "card_id": "wastes", "selected_face_index": 3, "targets": {"x_value": 0}})
    rejected(client, controller, {"type": "cast_spell", "card_id": "wastes", "from_exile": True, "targets": {"x_value": 0}})


def test_rejected_cleanup_choice_remains_pending(game):
    client, controller = game
    state = controller.state
    state.pending_mechanic_choice = {"kind": "cleanup_discard", "player_id": 1, "options": list(state.players[1].hand), "count": 1}
    persist(controller)
    cid = state.players[1].hand[0]
    rejected(client, controller, {"type": "choose_mechanic", "card_ids": [cid, cid]})
    rejected(client, controller, {"type": "choose_mechanic", "card_ids": [cid]}, player_id=2)
    rejected(client, controller, {"type": "pass_priority"})


def test_land_play_and_duplicate_submission_have_one_effect(game):
    client, controller = game
    cid = controller.state.players[1].hand[0]
    payload = {"player_id": 1, "action": {"type": "play_land", "card_id": cid}}
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: client.post(f"/matches/{controller.state.id}/action", json=payload), range(2)))
    assert sorted(response.status_code for response in results) == [200, 422]
    assert controller.state.players[1].battlefield.count(cid) == 1
    assert controller.state.players[1].lands_played_this_turn == 1


def test_illegal_filtered_blocks_do_not_commit(game):
    client, controller = game
    add_card(controller, "drake", "Wind Drake", Zone.BATTLEFIELD, ["Creature"], text="Flying", power=2, toughness=2, owner=2, keywords=["Flying"])
    add_card(controller, "bear", "Grizzly Bears", Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    state = controller.state
    state.active_player = 2
    state.step = Step.DECLARE_BLOCKERS
    state.attackers = ["drake"]
    persist(controller)
    rejected(client, controller, {"type": "block", "blocks": {"drake": ["bear"]}})


def test_missing_card_data_cannot_start_a_game_or_job(game, monkeypatch):
    client, controller = game
    monkeypatch.setattr(main, "_hydrate_deck_cards", lambda repo, deck: deck)
    deck = [{"quantity": 60, "card_name": "Island"}]
    before = snapshot(controller)
    jobs = set(main.SIM_JOBS)
    for path in ("/matches/start", "/simulate/batch", "/simulate/batch/start"):
        response = client.post(path, json={"deck_a": deck, "deck_b": deck})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "card_data_unavailable"
    assert set(main.SIM_JOBS) == jobs
    assert snapshot(controller) == before


def test_simulator_receives_the_same_hydrated_card_contract(game, monkeypatch):
    client, _ = game
    from analytics.service import AnalyticsService
    received = []
    def probe(self, deck_a, deck_b, *args, **kwargs):
        received.extend([deck_a, deck_b])
        return {"matches": 1}
    monkeypatch.setattr(AnalyticsService, "run_batch", probe)
    deck = [{"quantity": 60, "card_name": "Island"}]
    assert client.post("/simulate/batch", json={"deck_a": deck, "deck_b": deck, "matches": 1}).status_code == 200
    assert len(received) == 2
    assert all(board[0]["type_line"].startswith("Basic Land") for board in received)


def test_divided_damage_budget_is_not_a_client_parameter(game):
    client, controller = game
    add_card(controller, "pyrotechnics", "Pyrotechnics", Zone.HAND, ["Sorcery"], "{4}{R}", "Pyrotechnics deals 4 damage divided as you choose among any number of targets.")
    controller.state.players[1].mana_pool.update({"R": 5})
    persist(controller)
    for targets in ({"target_distribution": {"2": 100}}, {"x_value": 100, "target_distribution": {"2": 100}}, {"target_distribution": {"2": 4}, "divide_total": 100}, {"target_distribution": {"1": 0, "2": 4}}):
        rejected(client, controller, {"type": "cast_spell", "card_id": "pyrotechnics", "targets": targets})
    response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 1, "action": {"type": "cast_spell", "card_id": "pyrotechnics", "targets": {"target_distribution": {"2": 4}}}})
    assert response.status_code == 200, response.text
    assert controller.state.stack[-1].payload["target_distribution"] == {"2": 4}


def test_any_target_can_select_own_creature_but_not_a_hand_card(game):
    client, controller = game
    add_card(controller, "pyro", "Prodigal Pyromancer", Zone.BATTLEFIELD, ["Creature"], text="{T}: Prodigal Pyromancer deals 1 damage to any target.", power=1, toughness=1)
    add_card(controller, "bear", "Grizzly Bears", Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    persist(controller)
    rejected(client, controller, {"type": "activate_ability", "card_id": "pyro", "ability_index": 0, "targets": {"target_card_id": controller.state.players[1].hand[0]}})
    response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 1, "action": {"type": "activate_ability", "card_id": "pyro", "ability_index": 0, "targets": {"target_card_id": "bear"}}})
    assert response.status_code == 200, response.text


def test_london_mulligan_to_zero_requires_deliberate_ordered_bottoms(game):
    client, controller = game
    controller.state.pregame_pending = True
    persist(controller)
    for count in range(1, 8):
        response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 1, "action": {"type": "mulligan"}})
        assert response.status_code == 200, response.text
        assert controller.state.mulligan_count[1] == count
    rejected(client, controller, {"type": "mulligan"})
    rejected(client, controller, {"type": "keep_hand", "bottom_card_ids": []})
    ids = list(reversed(controller.state.players[1].hand))
    response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 1, "action": {"type": "keep_hand", "bottom_card_ids": ids}})
    assert response.status_code == 200, response.text
    assert controller.state.players[1].hand == []
    assert controller.state.players[1].library[:7] == ids
