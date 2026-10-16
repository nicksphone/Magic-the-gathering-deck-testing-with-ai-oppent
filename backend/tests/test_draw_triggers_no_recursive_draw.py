from __future__ import annotations

from dataclasses import replace

from game_state.state import MatchFactory, Zone
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack
from tests.canonical_positive_fixtures import raw_card


def _put_static_permanent_with_oracle(state, player_id: int, name: str) -> str:
    p = state.players[player_id]
    cid = p.hand[0]
    p.hand.remove(cid)
    p.battlefield.append(cid)
    c = state.cards[cid]
    raw = raw_card(name)
    materialized = MatchFactory.from_decks(
        [{**raw, 'quantity': 8, 'card_name': raw['name']}], [], seed=0)
    # Full printed facts for a trusted static pose, not a cast or entry event.
    template = next(card for card in materialized.cards.values() if card.zone == Zone.LIBRARY)
    state.cards[cid] = replace(
        template, id=cid, owner=c.owner, controller=c.controller, zone=Zone.BATTLEFIELD,
        instance_order=c.instance_order, zone_change_sequence=c.zone_change_sequence,
        summoning_sick=c.summoning_sick)
    return cid


def test_sheoldred_you_draw_trigger_gains_life_not_draw() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    _put_static_permanent_with_oracle(
        state,
        1,
        "Sheoldred, the Apocalypse",
    )

    hand_before = len(state.players[1].hand)
    life_before = state.players[1].life
    emit_event(state, "draw_card", {"player_id": 1, "card_id": "x"})
    assert state.stack[-1].effect_key == "gain_life"
    resolve_top_of_stack(state)
    assert state.players[1].life == life_before + 2
    assert len(state.players[1].hand) == hand_before


def test_sheoldred_opponent_draw_trigger_loses_life() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    _put_static_permanent_with_oracle(
        state,
        1,
        "Sheoldred, the Apocalypse",
    )

    life_before = state.players[2].life
    emit_event(state, "draw_card", {"player_id": 2, "card_id": "y"})
    assert state.stack[-1].effect_key == "lose_life"
    resolve_top_of_stack(state)
    assert state.players[2].life == life_before - 2
