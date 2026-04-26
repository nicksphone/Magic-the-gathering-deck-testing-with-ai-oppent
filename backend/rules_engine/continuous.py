from __future__ import annotations


def effective_power(state, card_id: str) -> int:
    card = state.cards[card_id]
    base = int(card.power or 0)
    return base + _anthem_bonus(state, card_id)


def effective_toughness(state, card_id: str) -> int:
    card = state.cards[card_id]
    base = int(card.toughness or 0)
    return base + _anthem_bonus(state, card_id)


def _anthem_bonus(state, card_id: str) -> int:
    card = state.cards[card_id]
    if "Creature" not in card.types:
        return 0
    controller = card.controller
    bonus = 0
    for src_id in state.players[controller].battlefield:
        src = state.cards.get(src_id)
        if not src:
            continue
        text = (getattr(src, "oracle_text", "") or "").lower()
        if "creatures you control get +1/+1" in text:
            bonus += 1
            continue
        if "other creatures you control get +1/+1" in text and src_id != card_id:
            bonus += 1
            continue
    return bonus

