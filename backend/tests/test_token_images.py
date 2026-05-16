from __future__ import annotations

from card_data.token_images import resolve_token_image_uri
from effects.registry import resolve_effect
from game_state.state import MatchFactory


def test_resolve_token_image_uri_returns_generic_or_remote() -> None:
    uri = resolve_token_image_uri("White Soldier", 1, 1)
    assert isinstance(uri, str)
    assert uri.startswith("/card-images/") or uri.startswith("http://") or uri.startswith("https://")


def test_create_token_assigns_image_uri() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    before = len(state.players[1].battlefield)
    resolve_effect(
        state,
        1,
        "create_token",
        {"name": "White Soldier", "power": 1, "toughness": 1, "amount": 1},
    )
    created = state.players[1].battlefield[before:]
    assert len(created) == 1
    cid = created[0]
    assert state.cards[cid].image_uri

