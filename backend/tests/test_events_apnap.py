from __future__ import annotations

from game_state.state import MatchFactory, Zone
from rules_engine.events import emit_event
from rules_engine.engine import RulesEngine


def _put_trigger_creature(state, player_id: int, oracle: str) -> str:
    p = state.players[player_id]
    cid = p.hand[0]
    p.hand.remove(cid)
    p.battlefield.append(cid)
    c = state.cards[cid]
    c.zone = Zone.BATTLEFIELD
    c.types = ["Creature"]
    c.oracle_text = oracle
    c.name = f"T{player_id}-{cid[:4]}"
    return cid


def test_apnap_trigger_order_on_shared_event() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_creature(state, 1, "Whenever a creature dies, draw a card.")
    _put_trigger_creature(state, 2, "Whenever a creature dies, draw a card.")

    emit_event(state, "creature_dies", {"card_id": "x"})
    assert len(state.stack) >= 2
    assert state.stack[0].controller == 1
    assert state.stack[1].controller == 2


def test_begin_upkeep_triggers_apply_apnap_for_each_upkeep_text() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_creature(state, 1, "At the beginning of each upkeep, draw a card.")
    _put_trigger_creature(state, 2, "At the beginning of each upkeep, draw a card.")

    emit_event(state, "begin_step", {"step": "upkeep", "active_player": 1})
    assert len(state.stack) >= 2
    assert state.stack[0].controller == 1
    assert state.stack[1].controller == 2


def test_begin_end_step_triggers_only_for_active_player_when_oracle_says_your() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_creature(state, 1, "At the beginning of your end step, draw a card.")
    _put_trigger_creature(state, 2, "At the beginning of your end step, draw a card.")

    emit_event(state, "begin_step", {"step": "end_step", "active_player": 1})
    assert len(state.stack) == 1
    assert state.stack[0].controller == 1


def test_engine_upkeep_start_enqueues_begin_step_triggers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = state.step.UNTAP
    engine = RulesEngine()

    _put_trigger_creature(state, 1, "At the beginning of your upkeep, draw a card.")
    before = len(state.stack)
    # Advance UNTAP -> UPKEEP and run step-start hook.
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.step == state.step.UPKEEP
    assert len(state.stack) >= before + 1
