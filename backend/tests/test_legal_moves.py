from __future__ import annotations

from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine


def test_generates_basic_legal_moves() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    engine = RulesEngine()
    moves = engine.legal_moves(state, state.priority_player)
    move_types = {m["type"] for m in moves}
    assert "pass_priority" in move_types
    assert "tap_land_for_mana" not in move_types


def test_land_named_card_is_not_offered_as_cast_spell_even_if_mistyped() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    engine = RulesEngine()

    cid = state.players[1].hand[0]
    state.cards[cid].name = "Forest"
    state.cards[cid].types = ["Sorcery"]  # simulate bad hydration/type inference
    state.cards[cid].type_line = ""

    moves = engine.legal_moves(state, 1)
    cast_for_cid = [m for m in moves if m.get("type") == "cast_spell" and m.get("card_id") == cid]
    land_for_cid = [m for m in moves if m.get("type") == "play_land" and m.get("card_id") == cid]
    assert cast_for_cid == []
    assert len(land_for_cid) == 1
