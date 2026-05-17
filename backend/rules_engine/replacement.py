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


def damage_cant_be_prevented(state, source_card_id: str | None = None, target_player: int | None = None, target_card_id: str | None = None) -> bool:
    for pid in state.players:
        for cid in state.players[pid].battlefield:
            card = state.cards[cid]
            text = (card.oracle_text or "").lower()
            if "damage can't be prevented" in text or "damage cannot be prevented" in text:
                return True
            if source_card_id and source_card_id in state.cards:
                source = state.cards[source_card_id]
                if source.controller == card.controller and (
                    "damage that would be dealt by sources you control can't be prevented" in text
                    or "damage that would be dealt by sources you control cannot be prevented" in text
                ):
                    return True
    return False


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


def player_cant_gain_life(state, target_player: int) -> bool:
    for pid in state.players:
        for cid in state.players[pid].battlefield:
            card = state.cards[cid]
            text = (card.oracle_text or "").lower()
            if "players can't gain life" in text or "players cannot gain life" in text:
                return True
            if card.controller == target_player:
                continue
            if "your opponents can't gain life" in text or "your opponents cannot gain life" in text:
                return True
            if "your opponent can't gain life" in text or "your opponent cannot gain life" in text:
                return True
    return False


def player_cant_lose_life(state, target_player: int) -> bool:
    for pid in state.players:
        for cid in state.players[pid].battlefield:
            card = state.cards[cid]
            text = (card.oracle_text or "").lower()
            if "players can't lose life" in text or "players cannot lose life" in text:
                return True
            if card.controller == target_player and ("you can't lose life" in text or "you cannot lose life" in text):
                return True
            if card.controller != target_player and (
                "your opponents can't lose life" in text
                or "your opponents cannot lose life" in text
                or "your opponent can't lose life" in text
                or "your opponent cannot lose life" in text
            ):
                return True
    return False
