"""Static restrictions on whether a player may draw a card."""

from rules_engine.oracle_text import without_reminder_text


def can_draw_card(state, player_id: int) -> bool:
    from rules_engine.continuous import printed_abilities_suppressed
    if state.pregame_pending:
        return True
    draws = state.draws_this_turn.get(player_id, 0)
    for player in state.players.values():
        for cid in player.battlefield:
            card = state.cards[cid]
            if printed_abilities_suppressed(state, cid):
                continue
            text = without_reminder_text(card.oracle_text or "").lower()
            if "each player can't draw more than one card each turn" in text and draws >= 1:
                return False
            if card.controller != player_id and "each opponent can't draw more than one card each turn" in text and draws >= 1:
                return False
    return True
