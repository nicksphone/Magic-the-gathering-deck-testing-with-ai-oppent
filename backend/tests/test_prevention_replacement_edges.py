from __future__ import annotations

from effects.registry import resolve_effect
from effects.handlers import deal_damage
from rules_engine import combat
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack


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


def test_replacement_effect_logs_redirection() -> None:
    state = _state()
    repl_id = "repl-draw"
    state.cards[repl_id] = CardInstance(
        id=repl_id,
        name="Life to Knowledge",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would gain life, draw that many cards instead.",
    )
    state.players[1].battlefield.append(repl_id)
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "gain_life", {"amount": 2})
    assert len(state.players[1].hand) == before + 2
    assert any("replacement effect applied: gain_life -> draw_cards" in line.lower() for line in state.log)


def test_optional_stack_effect_can_be_declined() -> None:
    state = _state()
    source = state.players[1].hand[0]
    state.players[1].hand.remove(source)
    state.cards[source].zone = Zone.STACK
    add_to_stack(
        state,
        source,
        1,
        "Optional Charm",
        "gain_life",
        {"target_player": 1, "amount": 3, "__may": True, "__may_choose": False},
    )
    before = state.players[1].life
    resolve_top_of_stack(state)
    assert state.players[1].life == before
    assert any("declines optional effect" in line.lower() for line in state.log)


def test_combat_damage_ignores_prevention_when_source_says_cant_be_prevented() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = state.players[1].hand.pop()
    state.players[1].battlefield.append(atk)
    state.cards[atk].zone = Zone.BATTLEFIELD
    state.cards[atk].types = ["Creature"]
    state.cards[atk].power = 3
    state.cards[atk].toughness = 3
    state.cards[atk].summoning_sick = False
    state.cards[atk].oracle_text = "Damage can't be prevented."

    state.players[2].prevent_damage_shield = 5
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}

    before = state.players[2].life
    combat.combat_damage(state)
    assert state.players[2].life == before - 3
