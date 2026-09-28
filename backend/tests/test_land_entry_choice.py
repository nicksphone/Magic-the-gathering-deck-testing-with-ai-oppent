from __future__ import annotations

import pytest

from ai.agent import AIAgent
from effects.handlers import put_land_from_hand, return_permanent_from_graveyard_to_battlefield, search_library, topdeck_put_permanents_battlefield
from game_state.state import CardInstance, MatchFactory, Step, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine


FOUNDRY = {
    "quantity": 1,
    "card_name": "Sacred Foundry",
    "type_line": "Land — Mountain Plains",
    "oracle_text": "({T}: Add {R} or {W}.)\nAs this land enters, you may pay 2 life. If you don't, it enters tapped.",
}


def game():
    state = MatchFactory.from_decks([FOUNDRY, {"quantity": 59, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=14)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    cid = next(cid for cid in state.cards if state.cards[cid].name == "Sacred Foundry")
    player = state.players[1]
    if cid in player.library:
        player.library.remove(cid)
    if cid not in player.hand:
        player.hand.append(cid)
    state.cards[cid].zone = Zone.HAND
    return state, cid


def test_land_play_requires_explicit_entry_choice_and_payment_is_atomic():
    state, cid = game()
    engine = RulesEngine()
    moves = [move for move in engine.legal_moves(state, 1) if move.get("card_id") == cid and move["type"] == "play_land"]
    assert {move["entry_choice"] for move in moves} == {"tapped", "pay_two_life"}
    with pytest.raises(ActionRejected):
        checked_action(state, engine, 1, {"type": "play_land", "card_id": cid})
    assert cid in state.players[1].hand and state.players[1].life == 20
    paid = checked_action(state, engine, 1, {"type": "play_land", "card_id": cid, "entry_choice": "pay_two_life"})
    assert paid.players[1].life == 18 and not paid.cards[cid].tapped
    assert paid.players[1].lands_played_this_turn == 1
    tapped = checked_action(state, engine, 1, {"type": "play_land", "card_id": cid, "entry_choice": "tapped"})
    assert tapped.players[1].life == 20 and tapped.cards[cid].tapped


def test_land_payment_unavailable_below_two_life_and_ai_prefers_tapped_without_followup():
    state, cid = game()
    state.players[1].life = 1
    engine = RulesEngine()
    moves = [move for move in engine.legal_moves(state, 1) if move.get("card_id") == cid and move["type"] == "play_land"]
    assert [move["entry_choice"] for move in moves] == ["tapped"]
    with pytest.raises(ActionRejected):
        checked_action(state, engine, 1, {"type": "play_land", "card_id": cid, "entry_choice": "pay_two_life"})
    state.players[1].life = 20
    moves = [move for move in engine.legal_moves(state, 1) if move.get("card_id") == cid and move["type"] == "play_land"]
    assert AIAgent()._best_land_move(state, moves, 1)["entry_choice"] == "tapped"
    state.cards["bolt"] = CardInstance(id="bolt", name="Lightning Bolt", owner=1, controller=1, zone=Zone.HAND, types=["Instant"], mana_cost="{R}")
    state.players[1].hand.append("bolt")
    assert AIAgent()._best_land_move(state, moves, 1)["entry_choice"] == "pay_two_life"


def test_permitted_exile_land_play_keeps_entry_choice_and_pays_before_entry():
    state, cid = game()
    state.players[1].hand.remove(cid)
    state.players[1].exile.append(cid)
    state.players[1].exile_play_until[cid] = state.turn
    state.cards[cid].zone = Zone.EXILE
    moves = [move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == cid and move["type"] == "play_land"]
    assert {move["entry_choice"] for move in moves} == {"tapped", "pay_two_life"}
    assert all(move.get("from_exile") for move in moves)
    next_state = checked_action(state, RulesEngine(), 1, {"type": "play_land", "card_id": cid, "from_exile": True, "entry_choice": "pay_two_life"})
    assert cid in next_state.players[1].battlefield and cid not in next_state.players[1].exile
    assert next_state.players[1].life == 18 and not next_state.cards[cid].tapped


def test_effect_entry_choice_survives_snapshot_and_effect_tapped_still_applies():
    state, cid = game()
    put_land_from_hand(state, 1, {"tapped": True, "land_id": cid})
    assert state.pending_mechanic_choice["kind"] == "land_entry"
    move = RulesEngine().legal_moves(state, 1)[0]
    assert "effect still makes it tapped" in move["option_labels"]["pay_two_life"]
    assert AIAgent().choose_action(state, [move], 1).action["choice_id"] == "tapped"
    assert cid in state.players[1].hand
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    checked = checked_action(restored, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "pay_two_life"})
    assert cid in checked.players[1].battlefield
    assert checked.cards[cid].tapped and checked.players[1].life == 18
    assert checked.cards[cid].effect_timestamp > 0
    assert checked.pending_mechanic_choice is None


def test_search_and_topdeck_entries_pause_before_moving_card():
    state, cid = game()
    state.players[1].hand.remove(cid)
    state.players[1].library.append(cid)
    state.cards[cid].zone = Zone.LIBRARY
    search_library(state, 1, {"contains": "Sacred Foundry", "destination": "battlefield", "count": 1})
    assert state.pending_mechanic_choice["kind"] == "land_entry"
    assert cid in state.players[1].library
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "tapped"})
    assert cid in state.players[1].battlefield and state.cards[cid].tapped
    assert state.cards[cid].effect_timestamp > 0
    state, cid = game()
    state.players[1].hand.remove(cid)
    state.players[1].library.append(cid)
    state.cards[cid].zone = Zone.LIBRARY
    topdeck_put_permanents_battlefield(state, 1, {"top_n": 1, "max_permanents": 1, "mv_max": 0})
    assert state.pending_mechanic_choice["kind"] == "land_entry"
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "pay_two_life"})
    assert cid in state.players[1].battlefield and not state.cards[cid].tapped
    assert state.players[1].life == 18


def test_graveyard_land_return_uses_entry_choice_and_emits_entry_event():
    state, cid = game()
    state.players[1].hand.remove(cid)
    state.players[1].graveyard.append(cid)
    state.cards[cid].zone = Zone.GRAVEYARD
    return_permanent_from_graveyard_to_battlefield(state, 1, {"target_card_id": cid})
    assert state.pending_mechanic_choice["kind"] == "land_entry"
    assert cid in state.players[1].graveyard
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "tapped"})
    assert cid in state.players[1].battlefield and state.cards[cid].tapped
    assert state.cards[cid].effect_timestamp > 0


def test_two_simultaneous_land_entries_reserve_life_before_either_moves():
    deck = [{**FOUNDRY, "quantity": 2}, {"quantity": 58, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, [{"quantity": 60, "card_name": "Island"}], seed=7)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.players[1].life = 3
    ids = [cid for cid, card in state.cards.items() if card.owner == 1 and card.name == "Sacred Foundry"]
    for cid in ids:
        if cid in state.players[1].hand:
            state.players[1].hand.remove(cid)
        else:
            state.players[1].library.remove(cid)
        state.players[1].library.append(cid)
        state.cards[cid].zone = Zone.LIBRARY
    topdeck_put_permanents_battlefield(state, 1, {"top_n": 2, "max_permanents": 2, "mv_max": 0})
    assert state.pending_mechanic_choice["kind"] == "land_entry"
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "pay_two_life"})
    assert state.pending_mechanic_choice["kind"] == "land_entry"
    assert state.pending_mechanic_choice["options"] == ["tapped"]
    assert all(cid in state.players[1].library for cid in ids)
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "tapped"})
    assert all(cid in state.players[1].battlefield for cid in ids)
    assert state.players[1].life == 1
    assert sum(state.cards[cid].tapped for cid in ids) == 1


def test_life_zero_payment_waits_for_remaining_entry_choice_before_state_based_loss():
    deck = [{**FOUNDRY, "quantity": 2}, {"quantity": 58, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, [{"quantity": 60, "card_name": "Island"}], seed=9)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.players[1].life = 2
    ids = [cid for cid, card in state.cards.items() if card.owner == 1 and card.name == "Sacred Foundry"]
    for cid in ids:
        if cid in state.players[1].hand:
            state.players[1].hand.remove(cid)
        else:
            state.players[1].library.remove(cid)
        state.players[1].library.append(cid)
        state.cards[cid].zone = Zone.LIBRARY
    topdeck_put_permanents_battlefield(state, 1, {"top_n": 2, "max_permanents": 2, "mv_max": 0})
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "pay_two_life"})
    assert state.winner is None and state.pending_mechanic_choice["options"] == ["tapped"]
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "tapped"})
    assert all(cid in state.players[1].battlefield for cid in ids)
    assert state.winner == 2
