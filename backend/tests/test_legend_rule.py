from __future__ import annotations

from game_state.state import MatchFactory, Zone
from rules_engine.state_based_actions import apply_state_based_actions


def test_legend_rule_moves_duplicate_legendary_to_graveyard() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    first = state.players[1].hand.pop()
    second = state.players[1].hand.pop()
    for cid in (first, second):
        state.players[1].battlefield.append(cid)
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.cards[cid].name = "Sheoldred, the Apocalypse"
        state.cards[cid].type_line = "Legendary Creature — Phyrexian Praetor"
        state.cards[cid].types = ["Creature"]

    apply_state_based_actions(state)

    on_field = [cid for cid in state.players[1].battlefield if state.cards[cid].name == "Sheoldred, the Apocalypse"]
    in_grave = [cid for cid in state.players[1].graveyard if state.cards[cid].name == "Sheoldred, the Apocalypse"]
    assert len(on_field) == 1
    assert len(in_grave) == 1


def test_legend_rule_is_per_controller_not_global() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    p1 = state.players[1].hand.pop()
    p2 = state.players[2].hand.pop()
    for pid, cid in ((1, p1), (2, p2)):
        state.players[pid].battlefield.append(cid)
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.cards[cid].name = "Teferi, Hero of Dominaria"
        state.cards[cid].type_line = "Legendary Planeswalker — Teferi"
        state.cards[cid].types = ["Planeswalker"]
        state.cards[cid].loyalty = 4

    apply_state_based_actions(state)

    assert state.cards[p1].zone == Zone.BATTLEFIELD
    assert state.cards[p2].zone == Zone.BATTLEFIELD
