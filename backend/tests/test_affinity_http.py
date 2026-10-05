"""Bounded affinity HTTP regressions; run only in an isolated source copy."""
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_affinity import ROWS, add, view
from tests.test_api_input_contracts import game, persist, snapshot


def prepare(game, seat, name, artifacts, pool):
    client, controller = game
    state = controller.state
    state.active_player = state.priority_player = seat
    state.kept_hands = {1, 2}
    for player in state.players.values():
        player.mana_pool = {}
    card = add(state, name, seat, Zone.HAND, cards=ROWS)
    for _ in range(artifacts):
        add(state, "Frogmite", seat, cards=ROWS)
    state.players[seat].mana_pool = dict(pool)
    persist(controller)
    return client, controller, card


def cast_moves(client, controller, seat, card):
    response = client.get(
        f"/matches/{controller.state.id}/legal-moves", params={"player_id": seat}
    )
    assert response.status_code == 200, response.text
    assert response.json()["player_id"] == seat
    assert response.json()["revision"] == controller.revision
    return [move for move in response.json()["moves"]
            if move["type"] == "cast_spell" and move.get("card_id") == card.id]


def cast(client, controller, seat, card, key):
    return client.post(
        f"/matches/{controller.state.id}/action",
        headers={"Idempotency-Key": key, "X-Match-Revision": str(controller.revision)},
        json={"player_id": seat, "action": {
            "type": "cast_spell", "card_id": card.id, "cost_choice": {"id": "base"},
        }},
    )


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("name,artifacts,pool,spent", [
    ("Frogmite", 4, {}, 0),
    ("Frogmite", 2, {"C": 2}, 2),
    ("Thoughtcast", 4, {"U": 1}, 1),
])
def test_http_legal_affinity_move_and_checked_discounted_payment(
    game, seat, name, artifacts, pool, spent,
):
    client, controller, card = prepare(game, seat, name, artifacts, pool)
    before = snapshot(controller)
    moves = cast_moves(client, controller, seat, card)
    assert len(moves) == 1
    assert moves[0]["mana_cost"] == ROWS[name]["mana_cost"]
    assert any(option["id"] == "base" for option in moves[0]["cost_options"])
    assert snapshot(controller) == before
    revision = controller.revision

    response = cast(client, controller, seat, card, "affinity-discount")
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == controller.revision == revision + 1
    state = controller.state
    assert state.cards[card.id].zone == Zone.STACK
    assert card.id not in state.players[seat].hand
    item, = [item for item in state.stack if item.source_card_id == card.id]
    assert item.controller == seat
    assert item.payload["mana_spent"] == spent
    assert all(amount == 0 for amount in state.players[seat].mana_pool.values())
    assert all(amount == 0 for amount in response.json()["players"][str(seat)]["mana_pool"].values())
    assert state.cards[card.id].mana_cost == ROWS[name]["mana_cost"]


@pytest.mark.parametrize("seat", [1, 2])
def test_http_affinity_cannot_pay_colored_cost_and_rejection_is_atomic(game, seat):
    client, controller, card = prepare(game, seat, "Thoughtcast", 7, {"C": 9})
    before = snapshot(controller)
    revision = controller.revision
    assert not cast_moves(client, controller, seat, card)
    assert snapshot(controller) == before

    response = cast(client, controller, seat, card, "affinity-no-blue")
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "illegal_action"
    assert isinstance(detail["message"], str) and detail["message"]
    assert snapshot(controller) == before
    assert controller.revision == revision
    assert "affinity-no-blue" not in controller.mutation_receipts
    response = client.get(f"/matches/{controller.state.id}")
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == revision


@pytest.mark.parametrize("seat", [1, 2])
def test_http_persisted_restore_preserves_affinity_cost_counts_and_payment(game, seat):
    client, controller, card = prepare(game, seat, "Thoughtcast", 3, {"C": 1, "U": 1})
    state = controller.state
    for owner, zone in [(seat, Zone.HAND), (seat, Zone.GRAVEYARD),
                        (3 - seat, Zone.BATTLEFIELD)]:
        add(state, "Frogmite", owner, zone, cards=ROWS)
    # Tapped artifacts still count, including artifact tokens.
    artifact = state.cards[state.players[seat].battlefield[0]]
    artifact.tapped = True
    artifact.is_token = True
    persist(controller)
    before = serialize_match_snapshot(state)
    revision = controller.revision
    moves_before = cast_moves(client, controller, seat, card)
    assert len(moves_before) == 1
    assert view(state, card).generic_reduction == 3

    del main.ACTIVE_MATCHES[state.id]
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert restored is not controller
    assert restored.revision == revision
    assert serialize_match_snapshot(restored.state) == before
    restored_card = restored.state.cards[card.id]
    assert restored_card.mana_cost == ROWS["Thoughtcast"]["mana_cost"] == "{4}{U}"
    assert view(restored.state, restored_card).generic_reduction == 3
    assert cast_moves(client, restored, seat, restored_card) == moves_before

    response = cast(client, restored, seat, restored_card, "affinity-restored")
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == revision + 1
    item, = [item for item in restored.state.stack if item.source_card_id == card.id]
    assert restored.state.cards[card.id].zone == Zone.STACK
    assert item.payload["mana_spent"] == 2
    assert all(amount == 0 for amount in restored.state.players[seat].mana_pool.values())
    paid_snapshot = serialize_match_snapshot(restored.state)
    del main.ACTIVE_MATCHES[state.id]
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    paid = main.ACTIVE_MATCHES[state.id]
    assert paid.revision == revision + 1
    assert serialize_match_snapshot(paid.state) == paid_snapshot
    assert view(paid.state, paid.state.cards[card.id]).generic_reduction == 3
    response = client.get(f"/matches/{state.id}")
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == revision + 1


@pytest.mark.parametrize("seat", [1, 2])
def test_http_spire_golem_tapped_islands_cost_and_restore_parity(game, seat):
    client, controller, card = prepare(game, seat, "Spire Golem", 0, {"C": 3})
    state = controller.state
    islands = []
    for _ in range(3):
        cid = state.players[seat].library.pop()
        land = state.cards[cid]
        assert land.name == "Island" and "Land" in land.types
        land.move_to_zone(Zone.BATTLEFIELD)
        land.tapped = True
        state.players[seat].battlefield.append(cid)
        islands.append(cid)
    persist(controller)
    before = snapshot(controller)
    revision = controller.revision
    moves_before = cast_moves(client, controller, seat, card)
    assert len(moves_before) == 1
    assert moves_before[0]["mana_cost"] == ROWS["Spire Golem"]["mana_cost"] == "{6}"
    assert view(state, card).generic_reduction == 3
    assert snapshot(controller) == before

    del main.ACTIVE_MATCHES[state.id]
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    restored_card = restored.state.cards[card.id]
    assert snapshot(restored) == before
    assert restored_card.mana_cost == "{6}"
    assert restored.state.players[seat].mana_pool == {"C": 3}
    assert view(restored.state, restored_card).generic_reduction == 3
    assert all(restored.state.cards[cid].tapped for cid in islands)
    assert cast_moves(client, restored, seat, restored_card) == moves_before

    response = cast(client, restored, seat, restored_card, "affinity-islands")
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == revision + 1
    item, = [item for item in restored.state.stack if item.source_card_id == card.id]
    assert item.controller == seat and item.payload["mana_spent"] == 3
    assert restored.state.cards[card.id].zone == Zone.STACK
    assert restored.state.cards[card.id].mana_cost == "{6}"
    assert all(amount == 0 for amount in restored.state.players[seat].mana_pool.values())
    assert all(restored.state.cards[cid].tapped for cid in islands)
