from __future__ import annotations

from effects.handlers import gain_life, lose_life
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.continuous import effective_keywords


def _basic_state():
    deck = [{"quantity": 60, "card_name": "Island"}]
    return MatchFactory.from_decks(deck, deck, seed=7)


def test_players_cant_gain_life_lock() -> None:
    state = _basic_state()
    lock_id = "lock-gain"
    state.cards[lock_id] = CardInstance(
        id=lock_id,
        name="Life Lock",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Your opponents can't gain life.",
    )
    state.players[2].battlefield.append(lock_id)
    before = state.players[1].life
    gain_life(state, controller=1, payload={"target_player": 1, "amount": 5})
    assert state.players[1].life == before


def test_players_cant_lose_life_lock() -> None:
    state = _basic_state()
    lock_id = "lock-lose"
    state.cards[lock_id] = CardInstance(
        id=lock_id,
        name="Platinum Light",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="You can't lose life.",
    )
    state.players[1].battlefield.append(lock_id)
    before = state.players[1].life
    lose_life(state, controller=2, payload={"target_player": 1, "amount": 3})
    assert state.players[1].life == before


def test_keyword_layer_grant_then_remove() -> None:
    state = _basic_state()
    c = CardInstance(
        id="c1",
        name="Bear",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        keywords=[],
        power=2,
        toughness=2,
        type_line="Creature - Bear",
    )
    grant = CardInstance(
        id="g1",
        name="Grant Aura",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures you control have flying and trample.",
    )
    remove = CardInstance(
        id="r1",
        name="Gravity Snare",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures your opponents control lose flying.",
    )
    state.cards[c.id] = c
    state.cards[grant.id] = grant
    state.cards[remove.id] = remove
    state.players[1].battlefield.extend([c.id, grant.id])
    state.players[2].battlefield.append(remove.id)

    kws = set(effective_keywords(state, c.id))
    assert "flying" not in kws
    assert "trample" in kws
