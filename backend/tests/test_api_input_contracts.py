"""Run API tests from an isolated source copy: lifespan uses a source-local DB."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import main
from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, StackItem, Step, Zone
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
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
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
    for path in ("/matches/start", "/simulate/batch", "/simulate/batch/start", "/simulate/batch/preflight"):
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


def test_life_cost_counterspell_exposes_typed_stack_target_and_payment_trigger(game):
    client, controller = game
    state = controller.state
    add_card(
        controller, "font", "Font of Agonies", Zone.BATTLEFIELD, ["Enchantment"],
        text="Whenever you pay life, put that many blood counters on this enchantment.",
    )
    add_card(
        controller, "boon", "Withering Boon", Zone.HAND, ["Instant"], "{1}{B}",
        "As an additional cost to cast this spell, pay 3 life.\nCounter target creature spell.",
    )
    bear = CardInstance(
        "bear", "Grizzly Bears", 2, 2, Zone.STACK, ["Creature"],
        mana_cost="{1}{G}", power=2, toughness=2,
    )
    state.cards[bear.id] = bear
    state.stack.append(StackItem("bear-spell", bear.id, 2, bear.name, "noop", {}))
    state.players[1].mana_pool.update({"B": 1, "C": 1})
    persist(controller)

    match_id = state.id
    moves_response = client.get(f"/matches/{match_id}/legal-moves?player_id=1")
    assert moves_response.status_code == 200
    move = next(move for move in moves_response.json()["moves"] if move.get("card_id") == "boon" and move["type"] == "cast_spell")
    assert [item["id"] for item in move["target_hints"]["stack_targets"]] == ["bear-spell"]

    response = client.post(
        f"/matches/{match_id}/action",
        json={"player_id": 1, "action": {"type": "cast_spell", "card_id": "boon", "targets": {"target_stack_id": "bear-spell"}}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["players"]["1"]["life"] == 17
    assert [item["label"] for item in body["stack"]] == ["Grizzly Bears", "Withering Boon", "Font of Agonies trigger"]


def test_x_cost_failure_and_unknown_cost_face_or_zone_are_atomic(game):
    client, controller = game
    add_card(controller, "wastes", "Secure the Wastes", Zone.HAND, ["Instant"], "{X}{W}", "Create X 1/1 white Warrior creature tokens.")
    controller.state.players[1].mana_pool["W"] = 1
    persist(controller)
    rejected(client, controller, {"type": "cast_spell", "card_id": "wastes", "targets": {"x_value": 100}})
    rejected(client, controller, {"type": "cast_spell", "card_id": "wastes", "cost_choice": {"id": "free"}, "targets": {"x_value": 0}})
    rejected(client, controller, {"type": "cast_spell", "card_id": "wastes", "selected_face_index": 3, "targets": {"x_value": 0}})
    rejected(client, controller, {"type": "cast_spell", "card_id": "wastes", "from_exile": True, "targets": {"x_value": 0}})


def test_variable_additional_life_x_cast_is_validated_and_persisted(game):
    client, controller = game
    state = controller.state
    add_card(controller, "deluge", "Toxic Deluge", Zone.HAND, ["Sorcery"], "{2}{B}",
             "As an additional cost to cast this spell, pay X life.\nAll creatures get -X/-X until end of turn.")
    state.players[1].mana_pool.update({"C": 2, "B": 1})
    persist(controller)
    url = f"/matches/{state.id}"
    move = next(item for item in client.get(f"{url}/legal-moves?player_id=1").json()["moves"]
                if item.get("card_id") == "deluge")
    assert move["target_hints"]["requires_x_value"]
    assert move["cost_options"][0]["pay_life_x"]
    rejected(client, controller, {"type": "cast_spell", "card_id": "deluge"})
    rejected(client, controller, {"type": "cast_spell", "card_id": "deluge", "targets": {"x_value": 21}})
    response = client.post(f"{url}/action", json={"player_id": 1, "action": {
        "type": "cast_spell", "card_id": "deluge", "targets": {"x_value": 2},
    }})
    assert response.status_code == 200, response.text
    assert response.json()["players"]["1"]["life"] == 18
    assert controller.state.stack[-1].effect_key == "temporary_pt_buff_all"


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
    for path in ("/matches/start", "/simulate/batch", "/simulate/batch/start", "/simulate/batch/preflight"):
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


def test_simulation_preflight_reports_known_gap_without_starting_job(game, monkeypatch):
    client, _ = game
    from analytics.schemas import BatchSimulationRequest

    def hydrated(repo, entries):
        del repo
        name = entries[0].card_name
        return [{"quantity": 60, "card_name": name, "type_line": "Creature — Human Wizard" if name == "Willbender" else "Basic Land — Island",
                 "oracle_text": "Morph {1}{U}" if name == "Willbender" else "{T}: Add {U}."}]

    monkeypatch.setattr(main, "_validated_deck_cards", hydrated)
    jobs = set(main.SIM_JOBS)
    deck_a = [{"quantity": 60, "card_name": "Willbender"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    response = client.post("/simulate/batch/preflight", json={"deck_a": deck_a, "deck_b": deck_b})

    assert response.status_code == 200, response.text
    assert response.json()["known_unsupported_cards"] == [
        {"deck": "A", "card_name": "Willbender", "mechanics": ["morph"]}
    ]
    assert set(main.SIM_JOBS) == jobs
    assert BatchSimulationRequest.model_validate({"deck_a": deck_a, "deck_b": deck_b, "difficulty": "master_plus"}).difficulty == "master_plus"


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
        if count == 1:
            assert controller.state.mulligan_count[1] == 0
            response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 2, "action": {"type": "keep_hand"}})
            assert response.status_code == 200, response.text
        assert controller.state.mulligan_count[1] == count
        ids = list(reversed(controller.state.players[1].hand[:count]))
        rejected(client, controller, {"type": "keep_hand"})
        response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 1, "action": {"type": "choose_mechanic", "card_ids": ids}})
        assert response.status_code == 200, response.text
        assert len(controller.state.players[1].hand) == 7 - count
    rejected(client, controller, {"type": "mulligan"})
    response = client.post(f"/matches/{controller.state.id}/action", json={"player_id": 1, "action": {"type": "keep_hand"}})
    assert response.status_code == 200, response.text
    assert controller.state.players[1].hand == []
    assert controller.state.players[1].library[:7] == ids
