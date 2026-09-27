from __future__ import annotations

import json
from types import SimpleNamespace

from card_data.hydration import hydrate_deck_cards
from game_state.state import CardInstance, MatchFactory, Zone
from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.continuous import effective_power, effective_toughness


def test_live_hydration_matches_diagnostic_faces_and_preserves_zero_stats():
    import main
    faces = [{"name": "Brutal Cathar", "type_line": "Creature - Human Soldier Werewolf", "power": "2", "toughness": "2"},
             {"name": "Moonrage Brute", "type_line": "Creature - Werewolf", "power": "3", "toughness": "3"}]
    row = SimpleNamespace(name="Brutal Cathar", oracle_text="Daybound", mana_cost="{2}{W}", type_line=faces[0]["type_line"], power=0, toughness=2, loyalty=None, image_uri="/card-images/cathar.jpg", card_faces_json=json.dumps(faces))
    repo = SimpleNamespace(get_cached_cards_by_names=lambda names: {"brutal cathar": row})
    deck = [{"quantity": 60, "card_name": row.name}]
    live = main._hydrate_deck_cards(repo, deck)
    assert live == hydrate_deck_cards(repo, deck)
    assert live[0]["power"] == 0
    state = deserialize_match_snapshot(serialize_match_snapshot(MatchFactory.from_decks(live, live, seed=4)))
    view = serialize_match(state)["players"][1]["hand"][0]
    assert view["card_faces"] == faces
    assert view["selected_face_index"] is None


def test_public_card_view_matches_combat_and_preserves_base_after_reload():
    deck = [{"quantity": 60, "card_name": "Grizzly Bears", "type_line": "Creature - Bear", "power": 2, "toughness": 2}]
    state = MatchFactory.from_decks(deck, deck, seed=1)
    cid = state.players[1].hand.pop()
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.counters = {"+1/+1": 1, "__eot_power": 2, "__damage_marked": 1}
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    view = serialize_match(restored)["players"][1]["battlefield"][0]
    assert (view["power"], view["toughness"]) == (effective_power(restored, cid), effective_toughness(restored, cid)) == (5, 3)
    assert (view["base_power"], view["base_toughness"]) == (2, 2)
    assert view["damage_marked"] == 1
    assert view["counters"]["+1/+1"] == 1
    assert (card.power, card.toughness) == (2, 2)
    anthem = CardInstance(id="anthem", name="Glorious Anthem", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Enchantment"], oracle_text="Creatures you control get +1/+1.")
    restored.cards[anthem.id] = anthem
    restored.players[1].battlefield.append(anthem.id)
    view = serialize_match(restored)["players"][1]["battlefield"][0]
    assert (view["power"], view["toughness"]) == (6, 4)
    from rules_engine.engine import RulesEngine
    RulesEngine()._clear_marked_damage(restored)
    view = serialize_match(restored)["players"][1]["battlefield"][0]
    assert (view["power"], view["toughness"], view["damage_marked"]) == (4, 4, 0)


def test_characteristic_stats_and_unknown_stats_are_not_fabricated():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=1)
    cid = state.players[1].library.pop()
    state.players[1].graveyard.append(cid)
    state.cards[cid].zone = Zone.GRAVEYARD
    goyf = CardInstance(id="goyf", name="Tarmogoyf", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"], oracle_text="Tarmogoyf's power is equal to the number of card types among cards in all graveyards and its toughness is equal to that number plus 1.")
    unknown = CardInstance(id="unknown", name="Wood Elemental", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"])
    state.cards.update({goyf.id: goyf, unknown.id: unknown})
    state.players[1].battlefield.extend([goyf.id, unknown.id])
    views = serialize_match(state)["players"][1]["battlefield"]
    assert (views[0]["power"], views[0]["toughness"]) == (1, 2)
    assert (views[1]["power"], views[1]["toughness"]) == (None, None)


def test_generic_token_art_installs_from_tracked_asset_with_empty_cache(tmp_path, monkeypatch):
    import card_data.placeholders as placeholders
    import card_data.token_images as tokens
    monkeypatch.setattr(placeholders, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(tokens, "_search_scryfall_token_image", lambda *args: None)
    tokens._TOKEN_IMAGE_CACHE.clear()
    assert tokens.resolve_token_image_uri("Soldier", 1, 1) == "/card-images/generic-token-creature.svg"
    assert (tmp_path / "generic-token-creature.svg").read_text().startswith("<svg")
    tokens._TOKEN_IMAGE_CACHE.clear()


def test_http_start_exposes_cached_faces_and_transformed_snapshot(monkeypatch):
    import main
    from fastapi.testclient import TestClient
    from effects.handlers import transform_card
    faces = [{"name": "Brutal Cathar", "type_line": "Creature - Human Soldier Werewolf", "power": "2", "toughness": "2", "oracle_text": "Daybound"},
             {"name": "Moonrage Brute", "type_line": "Creature - Werewolf", "power": "3", "toughness": "3", "oracle_text": "First strike\nNightbound"}]
    row = SimpleNamespace(name="Brutal Cathar", oracle_text="Daybound", mana_cost="{2}{W}", type_line=faces[0]["type_line"], power="2", toughness="2", loyalty=None, image_uri="/card-images/cathar.jpg", card_faces_json=json.dumps(faces))
    repo = SimpleNamespace(get_cached_cards_by_names=lambda names: {"brutal cathar": row})
    monkeypatch.setitem(main.app.dependency_overrides, main.get_repo, lambda: repo)
    monkeypatch.setattr(main, "_persist_active_match", lambda *args: None)
    deck = [{"quantity": 60, "card_name": "Brutal Cathar"}]
    client = TestClient(main.app)
    response = client.post("/matches/start", json={"deck_a": deck, "deck_b": deck, "seed": 5})
    assert response.status_code == 200
    mid = response.json()["id"]
    try:
        assert response.json()["players"]["1"]["hand"][0]["card_faces"] == faces
        state = main.ACTIVE_MATCHES[mid].state
        cid = state.players[1].hand.pop()
        state.players[1].battlefield.append(cid)
        state.cards[cid].zone = Zone.BATTLEFIELD
        transform_card(state, 1, {"target_card_id": cid, "face_index": 1})
        main.ACTIVE_MATCHES[mid].state = deserialize_match_snapshot(serialize_match_snapshot(state))
        view = client.get(f"/matches/{mid}").json()["players"]["1"]["battlefield"][0]
        assert view["name"] == "Moonrage Brute"
        assert (view["power"], view["toughness"]) == (3, 3)
        assert view["card_faces"] == faces
    finally:
        main.ACTIVE_MATCHES.pop(mid, None)
