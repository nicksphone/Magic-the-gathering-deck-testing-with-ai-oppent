from __future__ import annotations

from ai.deck_analysis import analyze_deck, guess_archetype
from tests.canonical_positive_fixtures import deck_entry


def test_guess_archetype_uses_curve_and_damage_density_for_burn() -> None:
    deck = [
        deck_entry("Mountain", 20),
        deck_entry("Lightning Bolt", 4),
        deck_entry("Lava Spike", 4),
        deck_entry("Skewer the Critics", 4),
        deck_entry("Flame Rift", 28),
    ]

    out = analyze_deck(deck)
    assert guess_archetype(deck) in {"Burn", "Aggro"}
    assert out["avg_cmc_estimate"] <= 2.0


def test_guess_archetype_uses_metadata_for_control_shell() -> None:
    deck = [
        deck_entry("Island", 26),
        deck_entry("Counterspell", 4),
        deck_entry("Consider", 4),
        deck_entry("Memory Deluge", 4),
        deck_entry("Farewell", 4),
        deck_entry("Mystic Sanctuary", 22),
    ]

    out = analyze_deck(deck)
    assert out["primary_archetype"] in {"Control", "Counter-heavy", "Removal-heavy"}
    assert out["scores"]["Control"] >= 1
    assert out["land_count_estimate"] >= 25


def test_deck_land_count_ignores_mana_creatures_and_land_text() -> None:
    deck = [
        deck_entry("Forest", 1),
        deck_entry("Llanowar Elves", 1),
        deck_entry("Island Sanctuary", 1),
        deck_entry("Growth Spiral", 1),
    ]
    assert analyze_deck(deck)["land_count_estimate"] == 1


def test_modal_back_face_types_do_not_distort_front_face_deck_shape() -> None:
    names = (
        "Valki, God of Lies // Tibalt, Cosmic Impostor",
        "Delver of Secrets // Insectile Aberration",
        "Bala Ged Recovery // Bala Ged Sanctuary",
    )
    deck = [deck_entry("Forest", 4)]
    deck.extend(deck_entry(name, 4) for name in names)
    analysis = analyze_deck(deck)
    assert analysis["land_count_estimate"] == 4
    assert analysis["creature_density_estimate"] == 0.5
    assert analysis["split_card_count_estimate"] == 0
    assert analysis["avg_cmc_estimate"] == 1.5
    assert analysis["scores"].get("Burn", 0) >= 1


def test_guess_archetype_detects_tokens_from_metadata_and_text() -> None:
    deck = [
        deck_entry("Plains", 24),
        deck_entry("Wedding Announcement", 4),
        deck_entry("Adeline, Resplendent Cathar", 4),
        deck_entry("Intangible Virtue", 4),
        deck_entry("Raise the Alarm", 28),
    ]

    out = analyze_deck(deck)
    assert guess_archetype(deck) == "Tokens"
    assert out["scores"]["Tokens"] >= 1


def test_guess_archetype_reads_split_cards_from_combined_face_costs() -> None:
    deck = [
        deck_entry("Island", 24),
        deck_entry("Fire // Ice", 4),
        deck_entry("Wedding Announcement", 4),
        deck_entry("Raise the Alarm", 28),
    ]

    out = analyze_deck(deck)
    assert out["face_card_count_estimate"] == 8
    assert out["split_card_count_estimate"] == 4
    assert out["avg_cmc_estimate"] > 0.2
    assert guess_archetype(deck) == "Tokens"


def test_guess_archetype_uses_primary_face_cost_for_non_split_face_cards() -> None:
    deck = [
        {"quantity": 56, "card_name": "Island", "card_metadata": {"name": "Island", "type_line": "Basic Land - Island", "mana_cost": ""}},
        {
            "quantity": 4,
            "card_name": "Modal Utility",
            "card_metadata": {
                "name": "Modal Utility",
                "type_line": "Creature",
                "mana_cost": "",
                "card_faces": [
                    {"name": "Creature Form", "type_line": "Creature", "oracle_text": "Create a token.", "mana_cost": "{2}{G}"},
                    {"name": "Spell Form", "type_line": "Instant", "oracle_text": "Draw a card.", "mana_cost": "{1}{U}"},
                ],
            },
        },
    ]

    out = analyze_deck(deck)
    assert out["face_card_count_estimate"] == 4
    assert out["split_card_count_estimate"] == 0
    assert out["avg_cmc_estimate"] == 0.2
