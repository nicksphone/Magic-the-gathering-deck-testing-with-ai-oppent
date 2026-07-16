from __future__ import annotations

from ai.deck_analysis import analyze_deck, guess_archetype


def test_guess_archetype_uses_curve_and_damage_density_for_burn() -> None:
    deck = [
        {"quantity": 20, "card_name": "Mountain", "card_metadata": {"name": "Mountain", "type_line": "Basic Land - Mountain", "mana_cost": ""}},
        {"quantity": 4, "card_name": "Lightning Bolt", "card_metadata": {"name": "Lightning Bolt", "type_line": "Instant", "mana_cost": "{R}", "oracle_text": "Lightning Bolt deals 3 damage to any target."}},
        {"quantity": 4, "card_name": "Lava Spike", "card_metadata": {"name": "Lava Spike", "type_line": "Sorcery", "mana_cost": "{R}", "oracle_text": "Lava Spike deals 3 damage to any target."}},
        {"quantity": 4, "card_name": "Skewer the Critics", "card_metadata": {"name": "Skewer the Critics", "type_line": "Sorcery", "mana_cost": "{2}{R}", "oracle_text": "Skewer the Critics deals 3 damage to any target."}},
        {"quantity": 28, "card_name": "Flame Rift", "card_metadata": {"name": "Flame Rift", "type_line": "Sorcery", "mana_cost": "{1}{R}", "oracle_text": "Flame Rift deals 4 damage to each player."}},
    ]

    out = analyze_deck(deck)
    assert guess_archetype(deck) in {"Burn", "Aggro"}
    assert out["avg_cmc_estimate"] <= 2.0


def test_guess_archetype_uses_metadata_for_control_shell() -> None:
    deck = [
        {"quantity": 26, "card_name": "Island", "card_metadata": {"name": "Island", "type_line": "Basic Land - Island", "mana_cost": ""}},
        {"quantity": 4, "card_name": "Counterspell", "card_metadata": {"name": "Counterspell", "type_line": "Instant", "mana_cost": "{U}{U}", "oracle_text": "Counter target spell."}},
        {"quantity": 4, "card_name": "Consider", "card_metadata": {"name": "Consider", "type_line": "Instant", "mana_cost": "{U}", "oracle_text": "Scry 1. Draw a card."}},
        {"quantity": 4, "card_name": "Memory Deluge", "card_metadata": {"name": "Memory Deluge", "type_line": "Instant", "mana_cost": "{2}{U}{U}", "oracle_text": "Draw cards."}},
        {"quantity": 4, "card_name": "Farewell", "card_metadata": {"name": "Farewell", "type_line": "Sorcery", "mana_cost": "{4}{W}{W}", "oracle_text": "Exile all creatures."}},
        {"quantity": 22, "card_name": "Mystic Sanctuary", "card_metadata": {"name": "Mystic Sanctuary", "type_line": "Land - Island", "mana_cost": ""}},
    ]

    out = analyze_deck(deck)
    assert out["primary_archetype"] in {"Control", "Counter-heavy", "Removal-heavy"}
    assert out["scores"]["Control"] >= 1
    assert out["land_count_estimate"] >= 25


def test_guess_archetype_detects_tokens_from_metadata_and_text() -> None:
    deck = [
        {"quantity": 24, "card_name": "Plains", "card_metadata": {"name": "Plains", "type_line": "Basic Land - Plains", "mana_cost": ""}},
        {"quantity": 4, "card_name": "Wedding Announcement", "card_metadata": {"name": "Wedding Announcement", "type_line": "Enchantment", "mana_cost": "{2}{W}", "oracle_text": "At the beginning of your end step, create a 1/1 white Human creature token."}},
        {"quantity": 4, "card_name": "Adeline, Resplendent Cathar", "card_metadata": {"name": "Adeline, Resplendent Cathar", "type_line": "Legendary Creature - Human Knight", "mana_cost": "{1}{W}{W}", "oracle_text": "Whenever you attack, create a 1/1 white Human creature token."}},
        {"quantity": 4, "card_name": "Intangible Virtue", "card_metadata": {"name": "Intangible Virtue", "type_line": "Enchantment", "mana_cost": "{1}{W}", "oracle_text": "Creature tokens you control get +1/+1 and have vigilance."}},
        {"quantity": 28, "card_name": "Raise the Alarm", "card_metadata": {"name": "Raise the Alarm", "type_line": "Instant", "mana_cost": "{1}{W}", "oracle_text": "Create two 1/1 white Soldier creature tokens."}},
    ]

    out = analyze_deck(deck)
    assert guess_archetype(deck) == "Tokens"
    assert out["scores"]["Tokens"] >= 1


def test_guess_archetype_reads_split_cards_from_combined_face_costs() -> None:
    deck = [
        {"quantity": 24, "card_name": "Island", "card_metadata": {"name": "Island", "type_line": "Basic Land - Island", "mana_cost": ""}},
        {
            "quantity": 4,
            "card_name": "Fire // Ice",
            "card_metadata": {
                "name": "Fire // Ice",
                "type_line": "Instant // Instant",
                "mana_cost": "",
                "card_faces": [
                    {"name": "Fire", "type_line": "Instant", "oracle_text": "Fire deals 2 damage divided as you choose among one or two targets.", "mana_cost": "{1}{R}"},
                    {"name": "Ice", "type_line": "Instant", "oracle_text": "Tap target permanent. Draw a card.", "mana_cost": "{1}{U}"},
                ],
            },
        },
        {"quantity": 4, "card_name": "Wedding Announcement", "card_metadata": {"name": "Wedding Announcement", "type_line": "Enchantment", "mana_cost": "{2}{W}", "oracle_text": "At the beginning of your end step, create a 1/1 white Human creature token."}},
        {"quantity": 28, "card_name": "Raise the Alarm", "card_metadata": {"name": "Raise the Alarm", "type_line": "Instant", "mana_cost": "{1}{W}", "oracle_text": "Create two 1/1 white Soldier creature tokens."}},
    ]

    out = analyze_deck(deck)
    assert out["face_card_count_estimate"] == 4
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
