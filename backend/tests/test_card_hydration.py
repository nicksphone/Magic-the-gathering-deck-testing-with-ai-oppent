from __future__ import annotations

from types import SimpleNamespace

from card_data.hydration import hydrate_deck_cards
from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from game_state.state import MatchFactory
from rules_engine.colors import card_color_names


class _Repo:
    def __init__(self, rows: list[object]) -> None:
        self.rows = {str(row.name).lower(): row for row in rows}

    def get_cached_cards_by_names(self, names: list[str]) -> dict[str, object]:
        return {name.lower(): self.rows[name.lower()] for name in names if name.lower() in self.rows}


def test_hydration_preserves_cached_noncreature_type_before_match_factory() -> None:
    row = SimpleNamespace(
        name="Skewer the Critics",
        oracle_text="Skewer the Critics deals 3 damage to any target.",
        mana_cost="{2}{R}",
        type_line="Sorcery",
        power=None,
        toughness=None,
        loyalty=None,
        image_uri="/card-images/skewer.jpg",
        card_faces_json="[]",
    )
    deck = [{"quantity": 1, "card_name": "Skewer the Critics"}]

    hydrated = hydrate_deck_cards(_Repo([row]), deck)
    state = MatchFactory.from_decks(hydrated + [{"quantity": 59, "card_name": "Mountain", "type_line": "Basic Land — Mountain"}], hydrated)
    skewer = next(card for card in state.cards.values() if card.name == "Skewer the Critics")

    assert hydrated[0]["type_line"] == "Sorcery"
    assert skewer.types == ["Sorcery"]
    assert skewer.power is None
    assert skewer.toughness is None


def test_match_factory_does_not_invent_stats_for_unknown_cards() -> None:
    deck = [{"quantity": 1, "card_name": "Unknown Card", "type_line": "Enchantment"}]

    state = MatchFactory.from_decks(deck, deck)
    unknown = next(card for card in state.cards.values() if card.name == "Unknown Card")

    assert unknown.types == ["Enchantment"]
    assert unknown.power is None
    assert unknown.toughness is None


def test_cached_hybrid_colors_survive_live_hydration_and_snapshot() -> None:
    row = SimpleNamespace(
        name="Figure of Destiny", oracle_text="{R/W}: This creature becomes a Kithkin Spirit.",
        mana_cost="{R/W}", type_line="Creature — Kithkin", colors="R,W",
        power="1", toughness="1", loyalty=None, image_uri=None, card_faces_json="[]",
    )
    hydrated = hydrate_deck_cards(_Repo([row]), [{"quantity": 1, "card_name": "Figure of Destiny"}])
    state = MatchFactory.from_decks(hydrated, hydrated, seed=7)
    figure = next(card for card in state.cards.values() if card.name == "Figure of Destiny")

    assert hydrated[0]["colors"] == ["R", "W"]
    assert card_color_names(figure) == {"red", "white"}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_card_view(state, figure.id)["colors"] == ["R", "W"]


def test_missing_color_metadata_uses_hybrid_cost_but_devoid_is_colorless() -> None:
    figure = SimpleNamespace(mana_cost="{R/W}", oracle_text="", colors=None, card_faces=[])
    guide = SimpleNamespace(mana_cost="{2}{U}", oracle_text="Devoid (This card has no color.)", colors=None, card_faces=[])

    assert card_color_names(figure) == {"red", "white"}
    assert card_color_names(guide) == set()


def test_selected_modal_face_uses_its_own_canonical_colors() -> None:
    card = SimpleNamespace(
        name="Valki, God of Lies // Tibalt, Cosmic Impostor", colors=None, mana_cost="{1}{B}",
        card_faces=[{"colors": ["B"]}, {"colors": ["B", "R"]}], selected_face_index=0,
    )

    assert card_color_names(card) == {"black"}
    card.selected_face_index = 1
    assert card_color_names(card) == {"black", "red"}
