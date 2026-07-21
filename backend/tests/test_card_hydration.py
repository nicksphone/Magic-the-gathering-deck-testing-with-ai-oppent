from __future__ import annotations

from types import SimpleNamespace

from card_data.hydration import hydrate_deck_cards
from game_state.state import MatchFactory


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
