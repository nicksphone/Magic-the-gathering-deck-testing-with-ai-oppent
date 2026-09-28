"""Static restrictions on whether a player may draw a card."""

from rules_engine.oracle_text import without_reminder_text


def can_draw_card(state, player_id: int) -> bool:
    if state.pregame_pending:
        return True
    draws = state.draws_this_turn.get(player_id, 0)
    for player in state.players.values():
        for cid in player.battlefield:
            card = state.cards[cid]
            text = without_reminder_text(card.oracle_text or "").lower()
            if "each player can't draw more than one card each turn" in text and draws >= 1:
                return False
            if card.controller != player_id and "each opponent can't draw more than one card each turn" in text and draws >= 1:
                return False
    return True
