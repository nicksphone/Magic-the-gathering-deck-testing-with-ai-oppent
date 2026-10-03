from __future__ import annotations

import re

from game_state.state import Zone

NUMBERS = {word: index for index, word in enumerate(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"))}


def escape_cost(card) -> tuple[str, int] | None:
    match = re.search(r"\bescape\s*[\u2014-]\s*((?:\{[^}]+\})+),\s*exile (\d+|\w+) other cards? from your graveyard", card.oracle_text or "", re.IGNORECASE)
    if not match:
        return None
    amount = match.group(2).lower()
    count = int(amount) if amount.isdigit() else NUMBERS.get(amount)
    return (match.group(1), count) if count is not None else None


def flashback_cost(card) -> str | None:
    match = re.search(r"\bflashback\s+((?:\{[^}]+\})+)", card.oracle_text or "", re.IGNORECASE)
    return match.group(1) if match else None


def has_aftermath(card) -> bool:
    return bool(re.search(r"(?:^|\n)aftermath\b", card.oracle_text or "", re.IGNORECASE))


def prototype_characteristics(card) -> dict | None:
    match = re.search(r"\bprototype\s+((?:\{[^}]+\})+)\s*[\u2014-]\s*(\d+)/(\d+)", card.oracle_text or "", re.IGNORECASE)
    return {"mana_cost": match.group(1), "power": int(match.group(2)), "toughness": int(match.group(3))} if match else None


def apply_prototype(card) -> None:
    characteristics = prototype_characteristics(card)
    if characteristics is None:
        return
    characteristics.update({f'printed_{field}': str(characteristics[field]) for field in ['power', 'toughness']})
    card.printed_characteristics = {key: getattr(card, key) for key in characteristics}
    for key, value in characteristics.items():
        setattr(card, key, value)


def restore_printed_characteristics(card) -> None:
    if not card.printed_characteristics:
        return
    for key, value in card.printed_characteristics.items():
        setattr(card, key, value)
    card.printed_characteristics = {}


def validate_escape_exiles(state, player_id: int, card_id: str, count: int, selected: list | None) -> list[str] | None:
    from rules_engine.zone_actions import is_departed_token
    eligible = [cid for cid in state.players[player_id].graveyard if cid != card_id and not is_departed_token(state.cards[cid])]
    ids = eligible[:count] if selected is None else selected
    if not isinstance(ids, list) or any(not isinstance(cid, str) for cid in ids) or len(ids) != count or len(set(ids)) != count or any(cid not in eligible for cid in ids):
        return None
    return ids
