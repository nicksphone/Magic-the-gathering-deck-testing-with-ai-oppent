from __future__ import annotations

from typing import Any


FALLBACK_CARD_DATA: dict[str, dict[str, Any]] = {
    # Blue Control
    "counterspell": {"mana_cost": "{U}{U}", "type_line": "Instant", "oracle_text": "Counter target spell."},
    "consider": {"mana_cost": "{U}", "type_line": "Instant", "oracle_text": "Draw a card."},
    "memory deluge": {"mana_cost": "{2}{U}{U}", "type_line": "Instant", "oracle_text": "Draw two cards."},
    "supreme verdict": {"mana_cost": "{1}{W}{W}{U}", "type_line": "Sorcery", "oracle_text": "Destroy all creatures."},
    "the wandering emperor": {"mana_cost": "{2}{W}{W}", "type_line": "Legendary Planeswalker", "oracle_text": "+1: Gain 2 life.", "loyalty": "3"},
    "teferi, hero of dominaria": {"mana_cost": "{3}{W}{U}", "type_line": "Legendary Planeswalker", "oracle_text": "+1: Draw a card.", "loyalty": "4"},
    "shark typhoon": {"mana_cost": "{5}{U}", "type_line": "Enchantment", "oracle_text": "Whenever you cast a noncreature spell, create a token."},
    "march of otherworldly light": {"mana_cost": "{X}{W}", "type_line": "Instant", "oracle_text": "Exile target artifact, creature, or enchantment."},
    "farewell": {"mana_cost": "{4}{W}{W}", "type_line": "Sorcery", "oracle_text": "Exile all creatures."},
    "island": {"mana_cost": "", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."},
    "hallowed fountain": {"mana_cost": "", "type_line": "Land — Plains Island", "oracle_text": "{T}: Add {W} or {U}."},
    # Ramp
    "arboreal grazer": {"mana_cost": "{G}", "type_line": "Creature", "oracle_text": "When Arboreal Grazer enters, you may put a land card from your hand onto the battlefield tapped.", "power": "0", "toughness": "3"},
    "growth spiral": {"mana_cost": "{G}{U}", "type_line": "Instant", "oracle_text": "Draw a card. You may put a land card from your hand onto the battlefield."},
    "cultivate": {"mana_cost": "{2}{G}", "type_line": "Sorcery", "oracle_text": "Search your library for lands."},
    "migration path": {"mana_cost": "{3}{G}", "type_line": "Sorcery", "oracle_text": "Search your library for lands."},
    "topiary stomper": {"mana_cost": "{2}{G}", "type_line": "Creature", "oracle_text": "Vigilance.", "power": "4", "toughness": "4"},
    "nissa, who shakes the world": {"mana_cost": "{3}{G}{G}", "type_line": "Legendary Planeswalker", "oracle_text": "+1: Animate land.", "loyalty": "5"},
    "ugin, the spirit dragon": {"mana_cost": "{8}", "type_line": "Legendary Planeswalker", "oracle_text": "+2: Deal 3 damage to target.", "loyalty": "7"},
    "hydroid krasis": {"mana_cost": "{X}{G}{U}", "type_line": "Creature", "oracle_text": "Flying, trample. When cast, draw a card and gain life.", "power": "4", "toughness": "4"},
    "storm the festival": {"mana_cost": "{3}{G}{G}{G}", "type_line": "Sorcery", "oracle_text": "Look at the top cards of your library."},
    "forest": {"mana_cost": "", "type_line": "Basic Land — Forest", "oracle_text": "{T}: Add {G}."},
}


def fallback_card_payload(name: str) -> dict[str, Any] | None:
    return FALLBACK_CARD_DATA.get(name.strip().lower())
