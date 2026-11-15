"""Declared canonical midgame Battle goldens through real ASGI HTTP + SQLite reload.

Initial lands/creatures are fixture inputs. Cast, search, attack, block, combat
and Siege transformation use real action routes. Reload means controller
eviction and restoration from SQLite with the capacity-owned engine/pool intact.
These cases do not claim an OS-process cold start or TCP/browser transport.
"""
import pytest

from game_state.state import Step, Zone
from tests.test_battle_entry import place
from tests.test_battle_product_acceptance import battle_position
from tests.test_manual_autoplay_collision_http import install_humans, seam_api, stable


# Independent expected consequences: damage to a Battle is not player damage.
GOLDENS = {
    "partial": {"life": [20, 20], "defense": 1, "dead_attackers": 0, "dead_blockers": 0, "defeat_triggers": 0},
    "defeat": {"life": [20, 20], "defense": 0, "dead_attackers": 0, "dead_blockers": 0, "defeat_triggers": 1},
    "player": {"life": [20, 18], "defense": 3, "dead_attackers": 0, "dead_blockers": 0, "defeat_triggers": 0},
    "blocked": {"life": [20, 20], "defense": 3, "dead_attackers": 1, "dead_blockers": 1, "defeat_triggers": 0},
}


def send(api, controller, actor, action):
    revision = controller.revision
    response = api.client.post(f"/matches/{controller.state.id}/action",
        json={"player_id": actor, "action": action},
        headers={"X-Match-Revision": str(revision), "Idempotency-Key": f"golden-{revision}"})
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == controller.revision == revision + 1
    return response.json()


def advance(api, controller, predicate):
    for _ in range(64):
        if predicate(controller.state):
            return
        assert not controller.state.pending_mechanic_choice
        assert not controller.state.pending_replacement_choice
        send(api, controller, controller.state.priority_player, {"type": "pass_priority"})
    pytest.fail("HTTP Battle boundary was not reached")


def reload_http(api, controller):
    mid = controller.state.id
    before = api.client.get(f"/matches/{mid}")
    assert before.status_code == 200, before.text
    expected = stable(api, controller)
    api.main.ACTIVE_MATCHES.pop(mid)
    after = api.client.get(f"/matches/{mid}")
    assert after.status_code == 200, after.text
    restored = api.main.ACTIVE_MATCHES[mid]
    assert restored is not controller
    assert after.json() == before.json()
    assert stable(api, restored) == expected
    return restored


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("case", GOLDENS)
def test_paid_battle_http_sqlite_reload_action_golden(seam_api, seat, case):
    api = seam_api
    state, battle, attackers = battle_position(seat, extra=("Grizzly Bears",))
    blocker = place(state, 3-seat, "Grizzly Bears", Zone.BATTLEFIELD) if case == "blocked" else None
    state.mechanic_choice_players = {1, 2}
    controller = reload_http(api, install_humans(api, state, seat))
    send(api, controller, seat, {"type": "cast_spell", "card_id": battle})
    advance(api, controller, lambda s: s.pending_mechanic_choice is not None)
    controller = reload_http(api, controller)
    pending = controller.state.pending_mechanic_choice
    assert (pending["kind"], pending["player_id"], pending["count"]) == ("search_library", seat, 2)
    chosen = pending["options"][:2]
    assert len(chosen) == 2
    send(api, controller, seat, {"type": "choose_mechanic", "card_ids": chosen})
    controller = reload_http(api, controller)
    front = controller.state.cards[battle]
    assert (front.zone, front.counters["defense"], front.battle_protector) == (Zone.BATTLEFIELD, 3, 3-seat)
    assert all(controller.state.cards[cid].tapped for cid in chosen)
    view = api.client.get(f"/matches/{state.id}").json()
    shown = next(card for card in view["players"][str(seat)]["battlefield"] if card["id"] == battle)
    assert (shown["defense"], shown["battle_protector"]) == (3, 3-seat)
    advance(api, controller, lambda s: s.step == Step.DECLARE_ATTACKERS)
    menu = api.client.get(f"/matches/{state.id}/legal-moves").json()
    attack = next(move for move in menu["moves"] if move["type"] == "attack")
    assert any(target["id"] == "battle:" + battle for target in attack["defenders"])
    selected = attackers if case == "defeat" else attackers[:1]
    target = f"player:{3-seat}" if case == "player" else "battle:" + battle
    send(api, controller, seat, {"type": "attack", "attackers": selected,
                               "attack_targets": {cid: target for cid in selected}})
    controller = reload_http(api, controller)
    assert controller.state.attack_targets == {cid: target for cid in selected}
    advance(api, controller, lambda s: s.step == Step.DECLARE_BLOCKERS)
    send(api, controller, 3-seat, {"type": "block", "blocks": {selected[0]: [blocker]} if blocker else {}})
    advance(api, controller, lambda s: s.step == Step.COMBAT_DAMAGE)
    controller = reload_http(api, controller)
    s = controller.state
    actual = {"life": [s.players[seat].life, s.players[3-seat].life],
              "defense": s.cards[battle].counters.get("defense", 0),
              "dead_attackers": sum(s.cards[cid].zone == Zone.GRAVEYARD for cid in selected),
              "dead_blockers": int(blocker is not None and s.cards[blocker].zone == Zone.GRAVEYARD),
              "defeat_triggers": sum(item.effect_key == "battle_defeat" for item in s.stack)}
    assert actual == GOLDENS[case]
    if case != "defeat":
        assert s.cards[battle].zone == Zone.BATTLEFIELD
        return
    advance(api, controller, lambda s: s.pending_mechanic_choice is not None)
    controller = reload_http(api, controller)
    assert controller.state.cards[battle].zone == Zone.EXILE
    assert controller.state.pending_mechanic_choice["kind"] == "effect_cast"
    send(api, controller, seat, {"type": "cast_spell", "card_id": battle,
                               "from_exile": True, "selected_face_index": 1})
    advance(api, controller, lambda s: s.cards[battle].zone == Zone.BATTLEFIELD)
    controller = reload_http(api, controller)
    view = api.client.get(f"/matches/{state.id}").json()
    back = next(card for card in view["players"][str(seat)]["battlefield"] if card["id"] == battle)
    assert (back["name"], back["power"], back["toughness"]) == ("Awakened Skyclave", 4, 4)
    assert set(back["types"]) == {"Creature", "Land"}
    assert back.get("defense") is None and back.get("battle_protector") is None
