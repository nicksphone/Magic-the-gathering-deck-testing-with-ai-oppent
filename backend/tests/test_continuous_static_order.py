from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.continuous import effective_keywords


def _state() -> object:
    deck = [{"quantity": 60, "card_name": "Island"}]
    return MatchFactory.from_decks(deck, deck, seed=23)


def test_continuous_uses_static_order_for_grant_remove() -> None:
    state = _state()

    target = CardInstance(
        id="t",
        name="Soldier",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        type_line="Creature - Human Soldier",
    )
    grant = CardInstance(
        id="g",
        name="Grant",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures you control have flying.",
        static_order=1,
    )
    remove = CardInstance(
        id="r",
        name="Remove",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures your opponents control lose flying.",
        static_order=2,
    )
    state.cards[target.id] = target
    state.cards[grant.id] = grant
    state.cards[remove.id] = remove
    state.players[1].battlefield.extend([target.id, grant.id])
    state.players[2].battlefield.append(remove.id)

    kws = set(effective_keywords(state, target.id))
    assert "flying" not in kws

    # Swap ordering so grant applies after remove.
    grant.static_order = 3
    remove.static_order = 2
    kws2 = set(effective_keywords(state, target.id))
    assert "flying" in kws2
