from __future__ import annotations

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone


def test_match_snapshot_round_trip_preserves_rules_state() -> None:
    deck = [
        {"quantity": 4, "card_name": "Island", "type_line": "Basic Land — Island", "mana_cost": ""},
        {"quantity": 56, "card_name": "Delver of Secrets", "type_line": "Creature — Human Wizard", "mana_cost": "{U}"},
    ]
    original = MatchFactory.from_decks(deck, deck, seed=1234)
    original.turn = 7
    original.step = Step.PRECOMBAT_MAIN
    original.players[1].life = 13
    original.players[1].mana_pool["U"] = 2
    original.passed_priority = {1}
    original.log.append("Snapshot boundary")

    restored = deserialize_match_snapshot(serialize_match_snapshot(original))

    assert restored.id == original.id
    assert restored.turn == 7
    assert restored.step == Step.PRECOMBAT_MAIN
    assert restored.players[1].life == 13
    assert restored.players[1].mana_pool["U"] == 2
    assert restored.passed_priority == {1}
    assert restored.log[-1] == "Snapshot boundary"
    assert [restored.cards[cid].name for cid in restored.players[1].hand] == [
        original.cards[cid].name for cid in original.players[1].hand
    ]
    assert all(card.zone in Zone for card in restored.cards.values())


def test_match_snapshot_round_trip_preserves_rng_sequence() -> None:
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land — Island"}]
    original = MatchFactory.from_decks(deck, deck, seed=91)
    restored = deserialize_match_snapshot(serialize_match_snapshot(original))

    assert original.rng.random() == restored.rng.random()
    assert original.rng.randrange(1000) == restored.rng.randrange(1000)
