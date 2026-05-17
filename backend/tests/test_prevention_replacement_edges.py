from __future__ import annotations

from effects.handlers import deal_damage
from game_state.state import CardInstance, MatchFactory, Zone


def _state() -> object:
    deck = [{"quantity": 60, "card_name": "Island"}]
    return MatchFactory.from_decks(deck, deck, seed=17)


def test_global_damage_cant_be_prevented_ignores_player_shield() -> None:
    state = _state()
    state.players[2].prevent_damage_shield = 5
    eid = "eid-global-no-prevent"
    state.cards[eid] = CardInstance(
        id=eid,
        name="No Prevent",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Damage can't be prevented.",
    )
    state.players[1].battlefield.append(eid)
    before = state.players[2].life
    deal_damage(state, controller=1, payload={"target_player": 2, "amount": 3})
    assert state.players[2].life == before - 3


def test_controller_scoped_damage_cant_be_prevented_ignores_shield() -> None:
    state = _state()
    state.players[2].prevent_damage_shield = 5
    aid = "aid-scope-no-prevent"
    src = "src-bolt"
    state.cards[aid] = CardInstance(
        id=aid,
        name="Aggro Lock",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Damage that would be dealt by sources you control can't be prevented.",
    )
    state.players[1].battlefield.append(aid)
    state.cards[src] = CardInstance(
        id=src,
        name="Bolt Source",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
    )
    state.players[1].battlefield.append(src)
    before = state.players[2].life
    deal_damage(state, controller=1, payload={"target_player": 2, "amount": 2, "__source_card_id": src})
    assert state.players[2].life == before - 2
