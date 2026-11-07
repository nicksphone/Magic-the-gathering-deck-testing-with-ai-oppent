from __future__ import annotations

from copy import deepcopy

import pytest

from ai.deck_analysis import analyze_deck, guess_archetype
from tests.canonical_positive_fixtures import deck_entry
from training.environment import _deck


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


@pytest.mark.parametrize(("name", "expected"), [
    ("Mono Red Aggro", "Burn"),
    ("White Weenie", "Tokens"),
    ("Blue Control", "Control"),
    ("Dimir Control", "Control"),
    ("Burn", "Burn"),
    ("Midrange", "Midrange"),
    ("Ramp", "Ramp"),
    ("Drain Deck", "Drain"),
    ("Tokens", "Tokens"),
    ("Tribal", "Tribal"),
    ("Tempo", "Tempo"),
])
def test_builtin_complete_metadata_distinguishes_plan_from_support_cards(name, expected):
    # Use the same shipped metadata loader as native gameplay, not the deck label.
    deck = _deck(name)
    before = deepcopy(deck)
    assert guess_archetype(deck) == expected
    assert deck == before


@pytest.mark.parametrize("land_count", [22, 27, 30])
def test_midrange_spell_curve_is_not_diluted_by_lands(land_count):
    deck = [row for row in _deck("Midrange") if row["card_name"] not in
            {"Forest", "Swamp", "Mountain", "Bayou", "Badlands", "Taiga"}]
    deck.append(deck_entry("Forest", land_count))
    assert guess_archetype(deck) == "Midrange"


def test_curve_prior_uses_spells_but_preserves_full_deck_average_metric():
    deck = [deck_entry("Island", 40), deck_entry("Counterspell", 4),
            deck_entry("Memory Deluge", 4), deck_entry("Torrential Gearhulk", 4)]
    analysis = analyze_deck(deck)
    assert analysis["primary_archetype"] == "Control"
    assert analysis["scores"].get("Aggro", 0) == 0
    assert analysis["scores"]["Ramp"] == 2
    assert analysis["avg_cmc_estimate"] == round(48 / 52, 3)


def test_midrange_classification_ignores_row_order_and_quantity_splitting():
    deck = _deck("Midrange")
    expected = analyze_deck(deck)
    split = [dict(row, quantity=1) for row in reversed(deck)
             for _ in range(row["quantity"])]
    assert analyze_deck(split) == expected
    assert expected["primary_archetype"] == "Midrange"


@pytest.mark.parametrize(("name", "cost", "ramp_score"), [
    ("Bala Ged Recovery // Bala Ged Sanctuary", 3, 1),
    ("Fire // Ice", 4, 2),
    ("Bonecrusher Giant // Stomp", 3, 1),
])
def test_spell_curve_prior_preserves_physical_card_face_cost_rules(name, cost, ramp_score):
    analysis = analyze_deck([deck_entry("Island", 40), deck_entry(name, 4)])
    assert analysis["land_count_estimate"] == 40
    assert analysis["avg_cmc_estimate"] == round(cost * 4 / 44, 3)
    assert analysis["scores"].get("Aggro", 0) == 0
    assert analysis["scores"]["Ramp"] == ramp_score


def test_balanced_midrange_curve_starts_at_two_mana_per_spell():
    deck = [deck_entry(name, quantity) for name, quantity in [
        ("Forest", 24), ("Llanowar Elves", 4), ("Tarmogoyf", 4),
        ("Bloodtithe Harvester", 4), ("Sheoldred, the Apocalypse", 4),
        ("Fatal Push", 4), ("Abrupt Decay", 4),
        ("Fable of the Mirror-Breaker // Reflection of Kiki-Jiki", 4),
        ("Grizzly Bears", 4), ("Consider", 4),
    ]]
    at_boundary = analyze_deck(deck)
    cheaper = [deck_entry("Thalia, Guardian of Thraben", 4)
               if row["card_name"] == "Sheoldred, the Apocalypse" else row for row in deck]
    below_boundary = analyze_deck(cheaper)
    assert at_boundary["avg_cmc_estimate"] == 1.2  # 72 mana / 36 spells = 2.
    assert below_boundary["avg_cmc_estimate"] == round(64 / 60, 3)
    assert at_boundary["scores"]["Midrange"] == below_boundary["scores"]["Midrange"] + 2
