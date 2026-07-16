from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


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


def test_mana_ability_oracle_marks_land_playable_when_type_metadata_missing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    engine = RulesEngine()

    cid = state.players[1].hand[0]
    state.cards[cid].name = "Misty Bog"
    state.cards[cid].types = []  # simulate bad hydration/type inference
    state.cards[cid].type_line = ""
    state.cards[cid].mana_cost = ""
    state.cards[cid].oracle_text = "{T}: Add {B}."

    moves = engine.legal_moves(state, 1)
    play_land = [m for m in moves if m.get("type") == "play_land" and m.get("card_id") == cid]
    cast_spell = [m for m in moves if m.get("type") == "cast_spell" and m.get("card_id") == cid]
    assert len(play_land) == 1
    assert cast_spell == []

    engine.take_action(state, 1, {"type": "play_land", "card_id": cid})
    assert cid in state.players[1].battlefield
    assert cid not in state.players[1].hand


def test_mana_creature_is_not_misclassified_as_land_from_oracle_text() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    engine = RulesEngine()

    cid = state.players[1].hand[0]
    state.cards[cid].name = "Llanowar Elves"
    state.cards[cid].types = []  # simulate incomplete metadata
    state.cards[cid].type_line = ""
    state.cards[cid].mana_cost = "{G}"
    state.cards[cid].oracle_text = "{T}: Add {G}."

    moves = engine.legal_moves(state, 1)
    play_land = [m for m in moves if m.get("type") == "play_land" and m.get("card_id") == cid]
    assert play_land == []


def test_no_second_land_move_same_turn_even_if_land_counter_desynced() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    engine = RulesEngine()

    first = state.players[1].hand[0]
    second = state.players[1].hand[1]
    state.cards[first].name = "Forest"
    state.cards[first].types = ["Land"]
    state.cards[second].name = "Forest"
    state.cards[second].types = ["Land"]

    engine.take_action(state, 1, {"type": "play_land", "card_id": first})
    assert state.players[1].lands_played_this_turn == 1
    assert state.players[1].last_land_play_turn == state.turn

    # Simulate counter drift bug elsewhere; turn-level invariant should still block.
    state.players[1].lands_played_this_turn = 0
    moves = engine.legal_moves(state, 1)
    second_land_moves = [m for m in moves if m.get("type") == "play_land" and m.get("card_id") == second]
    assert second_land_moves == []


def test_second_land_is_legal_when_effect_allows_two_land_plays() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    engine = RulesEngine()

    # Stage a synthetic static effect allowing two extra land plays.
    effect_id = state.players[1].library.pop()
    state.players[1].battlefield.append(effect_id)
    effect = state.cards[effect_id]
    effect.types = ["Enchantment"]
    effect.name = "Wayward Surge"
    effect.oracle_text = "You may play two additional lands on each of your turns."

    first = state.players[1].hand[0]
    second = state.players[1].hand[1]
    state.cards[first].types = ["Land"]
    state.cards[first].name = "Forest"
    state.cards[second].types = ["Land"]
    state.cards[second].name = "Forest"

    engine.take_action(state, 1, {"type": "play_land", "card_id": first})
    moves = engine.legal_moves(state, 1)
    second_land_moves = [m for m in moves if m.get("type") == "play_land" and m.get("card_id") == second]
    assert len(second_land_moves) == 1


def test_additional_land_effect_text_allows_second_land_same_turn() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    engine = RulesEngine()

    # Stage an "Exploration"-style static effect in battlefield.
    effect_id = state.players[1].library.pop()
    state.players[1].battlefield.append(effect_id)
    effect = state.cards[effect_id]
    effect.types = ["Enchantment"]
    effect.name = "Exploration"
    effect.oracle_text = "You may play an additional land on each of your turns."

    first = state.players[1].hand[0]
    second = state.players[1].hand[1]
    state.cards[first].types = ["Land"]
    state.cards[first].name = "Forest"
    state.cards[second].types = ["Land"]
    state.cards[second].name = "Forest"

    engine.take_action(state, 1, {"type": "play_land", "card_id": first})
    moves = engine.legal_moves(state, 1)
    second_land_moves = [m for m in moves if m.get("type") == "play_land" and m.get("card_id") == second]
    assert len(second_land_moves) == 1


def test_non_active_player_cannot_get_play_land_legal_move() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 2
    engine = RulesEngine()

    cid = state.players[2].hand[0]
    state.cards[cid].types = ["Land"]
    state.cards[cid].name = "Island"

    moves = engine.legal_moves(state, 2)
    assert all(m.get("type") != "play_land" for m in moves)


def test_engine_rejects_play_land_when_player_is_not_active() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 2
    engine = RulesEngine()

    cid = state.players[2].hand[0]
    state.cards[cid].types = ["Land"]
    state.cards[cid].name = "Forest"

    before_hand = list(state.players[2].hand)
    engine.take_action(state, 2, {"type": "play_land", "card_id": cid})
    assert state.players[2].hand == before_hand
    assert cid not in state.players[2].battlefield


def test_recruitment_officer_style_activated_ability_is_legal_and_resolves() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.battlefield = []
    for _ in range(4):
        cid = p1.library.pop()
        p1.battlefield.append(cid)
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.cards[cid].types = ["Land"]
        state.cards[cid].name = "Forest"
    officer_id = p1.library.pop()
    officer = state.cards[officer_id]
    officer.zone = Zone.BATTLEFIELD
    officer.types = ["Creature"]
    officer.name = "Recruitment Officer"
    officer.oracle_text = "{4}: Look at the top four cards of your library. You may reveal a creature card with power 2 or less from among them and put it into your hand."
    p1.battlefield.append(officer_id)
    top_id = p1.library[-1]
    state.cards[top_id].types = ["Creature"]
    state.cards[top_id].power = 2
    state.cards[top_id].name = "Recruitable Creature"

    moves = RulesEngine().legal_moves(state, 1)
    ability_moves = [m for m in moves if m.get("type") == "activate_ability" and m.get("card_id") == officer_id]
    assert len(ability_moves) == 1
    RulesEngine().take_action(state, 1, ability_moves[0])
    assert state.stack and state.stack[-1].effect_key == "topdeck_reveal_creature_to_hand"
    resolve_top_of_stack(state)
    assert top_id in p1.hand
