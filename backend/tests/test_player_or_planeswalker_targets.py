from __future__ import annotations

import pytest

from card_data.fallback_cards import fallback_card_payload
from game_state.state import CardInstance, Zone
from rules_engine.prevention import add_card_prevention_shield
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import single_player_permanent_alternative
from tests.test_api_input_contracts import game, persist, snapshot


@pytest.fixture(params=[
    ("Lava Spike", "{R}", "Lava Spike deals 3 damage to target player or planeswalker."),
    ("Skullcrack", "{1}{R}", "Players can't gain life this turn. Damage can't be prevented this turn. Skullcrack deals 3 damage to target player or planeswalker."),
])
def spell_data(request):
    return request.param


def test_alternative_parser_excludes_qualified_and_multiple_targets() -> None:
    assert single_player_permanent_alternative("Deal 3 damage to target player or planeswalker.")
    assert single_player_permanent_alternative("Deal 3 damage to target player or creature that player controls.") is None
    assert single_player_permanent_alternative("Deal 3 damage to target player or planeswalker and target creature.") is None


def _setup(game, spell_data):
    client, match = game
    state = match.state
    name, mana_cost, oracle_text = spell_data
    state.players[1].mana_pool["R"] = 2
    spike = CardInstance(
        id="burn-spell", name=name, owner=1, controller=1, zone=Zone.HAND,
        types=["Instant"] if name == "Skullcrack" else ["Sorcery"],
        type_line="Instant" if name == "Skullcrack" else "Sorcery — Arcane",
        mana_cost=mana_cost, oracle_text=oracle_text,
    )
    walker = CardInstance(
        id="teferi", name="Teferi, Hero of Dominaria", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Planeswalker"], type_line="Legendary Planeswalker — Teferi",
        loyalty=4, oracle_text=fallback_card_payload("Teferi, Hero of Dominaria")["oracle_text"],
    )
    state.cards.update({spike.id: spike, walker.id: walker})
    state.players[1].hand.append(spike.id)
    state.players[2].battlefield.append(walker.id)
    persist(match)
    return client, match, spike, walker


@pytest.mark.parametrize("target,expected_life,expected_loyalty", [
    ({"target_player": 2}, 17, 4),
    ({"target_card_id": "teferi"}, 20, 1),
])
def test_damage_spell_can_target_player_or_planeswalker(game, spell_data, target, expected_life, expected_loyalty) -> None:
    client, match, spike, walker = _setup(game, spell_data)
    url = f"/matches/{match.state.id}"
    move = next(m for m in client.get(f"{url}/legal-moves").json()["moves"] if m.get("card_id") == spike.id and m["type"] == "cast_spell")
    assert move["target_hints"]["single_target_alternative"] is True
    assert {item["id"] for item in move["target_hints"]["planeswalker_targets"]} == {walker.id}
    response = client.post(f"{url}/action", json={"player_id": 1, "action": {"type": "cast_spell", "card_id": spike.id, "targets": target}})
    assert response.status_code == 200, response.text
    assert resolve_top_of_stack(match.state)
    assert match.state.players[2].life == expected_life
    assert match.state.cards[walker.id].loyalty == expected_loyalty


@pytest.mark.parametrize("targets", [
    {"target_player": 2, "target_card_id": "teferi"},
    {"target_card_id": "p1-001"},
])
def test_damage_spell_rejects_multiple_or_unavailable_targets_without_mutation(game, spell_data, targets) -> None:
    client, match, spike, _ = _setup(game, spell_data)
    before = snapshot(match)
    response = client.post(f"/matches/{match.state.id}/action", json={"player_id": 1, "action": {"type": "cast_spell", "card_id": spike.id, "targets": targets}})
    assert response.status_code == 422, response.text
    assert snapshot(match) == before


def test_planeswalker_damage_respects_prevention_and_cant_prevent(game, spell_data) -> None:
    client, match, spell, walker = _setup(game, spell_data)
    add_card_prevention_shield(walker, 2)
    persist(match)
    response = client.post(f"/matches/{match.state.id}/action", json={
        "player_id": 1,
        "action": {"type": "cast_spell", "card_id": spell.id, "targets": {"target_card_id": walker.id}},
    })
    assert response.status_code == 200, response.text
    assert resolve_top_of_stack(match.state)
    assert match.state.cards[walker.id].loyalty == (1 if spell.name == "Skullcrack" else 3)
