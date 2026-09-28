"""Run from an isolated source copy: API lifespan uses a source-local database."""

from sqlmodel import Session

import main
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import add_card, game, persist
from tests.test_death_replacement_canonical import LEYLINE_OF_THE_VOID_ORACLE, REST_IN_PEACE_ORACLE


def test_rest_in_peace_damage_death_and_spell_zone_survive_http_restore(game):
    client, match = game
    add_card(
        match, "rip", "Rest in Peace", Zone.BATTLEFIELD, ["Enchantment"],
        text=REST_IN_PEACE_ORACLE,
    )
    add_card(
        match, "traveler", "Doomed Traveler", Zone.BATTLEFIELD, ["Creature"],
        text="When this creature dies, create a 1/1 white Spirit creature token with flying.",
        power=1, toughness=1, owner=2,
    )
    add_card(
        match, "bolt", "Lightning Bolt", Zone.HAND, ["Instant"], cost="{R}",
        text="Lightning Bolt deals 3 damage to any target.",
    )
    match.state.players[1].mana_pool["R"] = 1
    persist(match)

    path = f"/matches/{match.state.id}/action"
    response = client.post(path, json={
        "player_id": 1,
        "action": {"type": "cast_spell", "card_id": "bolt", "targets": {"target_card_id": "traveler"}},
    })
    assert response.status_code == 200, response.text
    for _ in range(4):
        if not match.state.stack:
            break
        response = client.post(path, json={
            "player_id": match.state.priority_player,
            "action": {"type": "pass_priority"},
        })
        assert response.status_code == 200, response.text

    assert not match.state.stack
    assert match.state.cards["traveler"].zone == Zone.EXILE
    assert match.state.cards["bolt"].zone == Zone.EXILE
    assert "traveler" not in match.state.players[2].graveyard
    assert "bolt" not in match.state.players[1].graveyard
    assert not match.state.players[2].battlefield

    mid = match.state.id
    main.ACTIVE_MATCHES.pop(mid)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), mid)
    restored = main.ACTIVE_MATCHES[mid].state
    assert restored.cards["traveler"].zone == Zone.EXILE
    assert restored.cards["bolt"].zone == Zone.EXILE
    view = client.get(f"/matches/{mid}")
    assert view.status_code == 200
    assert view.json()["players"]["2"]["exile_count"] == 1


def test_rest_in_peace_entry_exiles_existing_graveyards_via_http(game):
    client, match = game
    add_card(
        match, "rip", "Rest in Peace", Zone.HAND, ["Enchantment"], cost="{1}{W}",
        text=REST_IN_PEACE_ORACLE,
    )
    buried = []
    for player in match.state.players.values():
        cid = player.hand.pop(0)
        player.graveyard.append(cid)
        match.state.cards[cid].zone = Zone.GRAVEYARD
        buried.append(cid)
    match.state.active_player = 1
    match.state.priority_player = 1
    match.state.players[1].mana_pool.update({"W": 1, "C": 1})
    persist(match)

    path = f"/matches/{match.state.id}/action"
    response = client.post(path, json={"player_id": 1, "action": {"type": "cast_spell", "card_id": "rip"}})
    assert response.status_code == 200, response.text
    for _ in range(8):
        if not match.state.stack:
            break
        response = client.post(path, json={
            "player_id": match.state.priority_player,
            "action": {"type": "pass_priority"},
        })
        assert response.status_code == 200, response.text

    assert not match.state.stack
    assert match.state.cards["rip"].zone == Zone.BATTLEFIELD
    assert all(match.state.cards[cid].zone == Zone.EXILE for cid in buried)
    assert all(not player.graveyard for player in match.state.players.values())

    mid = match.state.id
    main.ACTIVE_MATCHES.pop(mid)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), mid)
    restored = main.ACTIVE_MATCHES[mid].state
    assert all(restored.cards[cid].zone == Zone.EXILE for cid in buried)


def test_opponent_card_graveyard_replacement_survives_http_restore(game):
    client, match = game
    add_card(
        match, "leyline", "Leyline of the Void", Zone.BATTLEFIELD, ["Enchantment"],
        text=LEYLINE_OF_THE_VOID_ORACLE,
    )
    add_card(
        match, "bolt", "Lightning Bolt", Zone.HAND, ["Instant"], cost="{R}",
        text="Lightning Bolt deals 3 damage to any target.", owner=2,
    )
    match.state.players[2].mana_pool["R"] = 1
    match.state.priority_player = 2
    persist(match)

    path = f"/matches/{match.state.id}/action"
    response = client.post(path, json={
        "player_id": 2,
        "action": {"type": "cast_spell", "card_id": "bolt", "targets": {"target_player": 1}},
    })
    assert response.status_code == 200, response.text
    for _ in range(4):
        if not match.state.stack:
            break
        response = client.post(path, json={
            "player_id": match.state.priority_player,
            "action": {"type": "pass_priority"},
        })
        assert response.status_code == 200, response.text

    assert not match.state.stack
    assert match.state.cards["bolt"].zone == Zone.EXILE
    assert "bolt" in match.state.players[2].exile

    mid = match.state.id
    main.ACTIVE_MATCHES.pop(mid)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), mid)
    assert main.ACTIVE_MATCHES[mid].state.cards["bolt"].zone == Zone.EXILE
