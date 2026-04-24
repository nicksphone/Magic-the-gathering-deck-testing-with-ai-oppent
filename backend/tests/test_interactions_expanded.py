from __future__ import annotations

from effects.registry import resolve_effect
from game_state.state import MatchFactory


def test_effect_sequence_resolves_all_clauses() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1_before = state.players[1].life
    p2_before = state.players[2].life
    hand_before = len(state.players[1].hand)

    resolve_effect(
        state,
        1,
        "effect_sequence",
        {
            "effects": [
                {"effect_key": "lose_life", "payload": {"target_player": 2, "amount": 3}},
                {"effect_key": "gain_life", "payload": {"amount": 3}},
                {"effect_key": "draw_cards", "payload": {"amount": 1}},
            ]
        },
    )

    assert state.players[2].life == p2_before - 3
    assert state.players[1].life == p1_before + 3
    assert len(state.players[1].hand) == hand_before + 1


def test_discard_effect_targets_specified_player() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p2_hand_before = len(state.players[2].hand)

    resolve_effect(state, 1, "discard_cards", {"target_player": 2, "amount": 2})

    assert len(state.players[2].hand) == p2_hand_before - 2
    assert len(state.players[2].graveyard) >= 2


def test_create_token_respects_amount_and_keywords() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    battlefield_before = len(state.players[1].battlefield)
    resolve_effect(
        state,
        1,
        "create_token",
        {"name": "Soldier", "power": 1, "toughness": 1, "amount": 2, "keywords": ["vigilance"]},
    )
    created = state.players[1].battlefield[battlefield_before:]
    assert len(created) == 2
    assert all(state.cards[cid].name == "Soldier" for cid in created)
    assert all("vigilance" in state.cards[cid].keywords for cid in created)
