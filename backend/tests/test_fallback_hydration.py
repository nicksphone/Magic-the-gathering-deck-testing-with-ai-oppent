from __future__ import annotations

from types import SimpleNamespace

from card_data.fallback_cards import fallback_card_payload
from main import _hydrate_deck_cards


def test_control_ramp_fallback_catalog_contains_core_fields() -> None:
    deluge = fallback_card_payload("Memory Deluge")
    assert deluge is not None
    assert deluge["mana_cost"] == "{2}{U}{U}"
    assert "Instant" in deluge["type_line"]

    clarion = fallback_card_payload("Clarion Spirit")
    assert clarion is not None
    assert "second spell" in clarion["oracle_text"]

    path = fallback_card_payload("Migration Path")
    assert path is not None
    assert "Sorcery" in path["type_line"]
    assert path["mana_cost"] == "{3}{G}"

    claim = fallback_card_payload("Claim the Firstborn")
    assert claim is not None
    assert "Gain control" in claim["oracle_text"]

    company = fallback_card_payload("Collected Company")
    assert company is not None
    assert "top six cards" in company["oracle_text"]

    fable = fallback_card_payload("Fable of the Mirror Breaker")
    assert fable is not None
    assert "Goblin Shaman token" in fable["oracle_text"]

    delver = fallback_card_payload("Delver of Secrets // Insectile Aberration")
    assert delver is not None
    assert "transform Delver of Secrets" in delver["oracle_text"]


def test_hydrate_deck_cards_uses_fallback_when_cache_unavailable() -> None:
    deck = [
        {"quantity": 4, "card_name": "Memory Deluge"},
        {"quantity": 4, "card_name": "Hallowed Fountain"},
        {"quantity": 2, "card_name": "Clarion Spirit"},
    ]
    hydrated = _hydrate_deck_cards(None, deck)
    by_name = {x["card_name"]: x for x in hydrated}
    assert by_name["Memory Deluge"]["mana_cost"] == "{2}{U}{U}"
    assert "Instant" in by_name["Memory Deluge"]["type_line"]
    assert "Land" in by_name["Hallowed Fountain"]["type_line"]
    assert "second spell" in by_name["Clarion Spirit"]["oracle_text"]


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


def test_hydrate_deck_cards_uses_face_image_when_root_image_missing() -> None:
    class FakeRepo:
        def get_cached_cards_by_names(self, names):
            del names
            return {
                "delver of secrets": SimpleNamespace(
                    name="Delver of Secrets // Insectile Aberration",
                    oracle_text="Flying",
                    mana_cost="{U}",
                    type_line="Creature — Human Wizard",
                    power="1",
                    toughness="1",
                    image_uri=None,
                    card_faces_json='[{"name":"Delver of Secrets","image_uri":"/card-images/delver-front.png"},{"name":"Insectile Aberration","image_uri":"/card-images/delver-back.png"}]',
                    loyalty=None,
                )
            }

    hydrated = _hydrate_deck_cards(FakeRepo(), [{"quantity": 1, "card_name": "Delver of Secrets"}])
    assert hydrated[0]["image_uri"] == "/card-images/delver-front.png"
