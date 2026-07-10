from __future__ import annotations

from types import SimpleNamespace

from card_data.fallback_cards import fallback_card_payload
from main import _hydrate_deck_cards


def test_control_ramp_fallback_catalog_contains_core_fields() -> None:
    deluge = fallback_card_payload("Memory Deluge")
    assert deluge is not None
    assert deluge["mana_cost"] == "{2}{U}{U}"
    assert "Instant" in deluge["type_line"]

    path = fallback_card_payload("Migration Path")
    assert path is not None
    assert "Sorcery" in path["type_line"]
    assert path["mana_cost"] == "{3}{G}"


def test_hydrate_deck_cards_uses_fallback_when_cache_unavailable() -> None:
    deck = [
        {"quantity": 4, "card_name": "Memory Deluge"},
        {"quantity": 4, "card_name": "Hallowed Fountain"},
    ]
    hydrated = _hydrate_deck_cards(None, deck)
    by_name = {x["card_name"]: x for x in hydrated}
    assert by_name["Memory Deluge"]["mana_cost"] == "{2}{U}{U}"
    assert "Instant" in by_name["Memory Deluge"]["type_line"]
    assert "Land" in by_name["Hallowed Fountain"]["type_line"]


def test_hydrate_deck_cards_merges_partial_cache_rows_with_fallback() -> None:
    class FakeRepo:
        def get_cached_cards_by_names(self, names):
                return {
                    "the wandering emperor": SimpleNamespace(
                        name="The Wandering Emperor",
                        oracle_text="",
                        mana_cost=None,
                        type_line="Legendary Planeswalker",
                    power=None,
                    toughness=None,
                    image_uri=None,
                    loyalty=None,
                )
            }

    hydrated = _hydrate_deck_cards(FakeRepo(), [{"quantity": 1, "card_name": "The Wandering Emperor"}])
    card = hydrated[0]
    assert card["oracle_text"] == fallback_card_payload("The Wandering Emperor")["oracle_text"]
    assert card["mana_cost"] == fallback_card_payload("The Wandering Emperor")["mana_cost"]
    assert card["type_line"] == "Legendary Planeswalker"
