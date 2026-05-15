from __future__ import annotations


def apply_damage_replacements(state, target_player: int | None, amount: int) -> int:
    out = int(amount)
    if target_player is None:
        return out
    for cid in state.players[target_player].battlefield:
        card = state.cards[cid]
        text = (card.oracle_text or "").lower()
        if "if a source would deal damage to you, prevent 1 of that damage" in text:
            out = max(0, out - 1)
    return out


def replace_gain_life(state, target_player: int, amount: int) -> tuple[str, dict] | None:
    for cid in state.players[target_player].battlefield:
        card = state.cards[cid]
        text = (card.oracle_text or "").lower()
        if "if you would gain life, draw that many cards instead" in text:
            return ("draw_cards", {"target_player": target_player, "amount": int(amount)})
    return None


def replace_draw_cards(state, target_player: int, amount: int) -> tuple[str, dict] | None:
    for cid in state.players[target_player].battlefield:
        card = state.cards[cid]
        text = (card.oracle_text or "").lower()
        if "if you would draw a card, gain 1 life instead" in text:
            return ("gain_life", {"target_player": target_player, "amount": int(amount)})
    return None


def replace_die_zone(state, controller: int, card_id: str) -> str:
    """Return destination zone for a dying creature: 'graveyard' or 'exile'."""
    for cid in state.players[controller].battlefield:
        card = state.cards[cid]
        text = (card.oracle_text or "").lower()
        if "if a creature you control would die, exile it instead" in text:
            return "exile"
    return "graveyard"
