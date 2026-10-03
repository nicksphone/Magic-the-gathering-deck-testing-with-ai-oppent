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


def forecast_draw_count(state, player_id: int, count: int) -> int:
    """Count default-order draws, capped at the first empty-library attempt.

    Only public library size is inspected. Optional dredge choices and downstream
    draw triggers are not projected; this is not a full resolution simulation.
    """
    from copy import copy
    from rules_engine.replacement import replace_draw_cards, replace_gain_life, player_cant_gain_life

    projection = copy(state)
    projection.log = []
    projection.draws_this_turn = dict(state.draws_this_turn)
    projection.draws_in_current_draw_step = dict(state.draws_in_current_draw_step)
    library_size = len(state.players[player_id].library)
    draws = 0

    def visit(key, amount, used):
        nonlocal draws
        if amount <= 0 or draws > library_size:
            return
        if key == 'draw_cards':
            for _ in range(amount):
                if draws > library_size or not can_draw_card(projection, player_id):
                    break
                replacement = replace_draw_cards(projection, player_id, 1, used_source_ids=used)
                if replacement is not None:
                    next_key, payload = replacement
                    visit(next_key, payload['amount'], payload.get('__used_replacement_source_ids', []))
                    continue
                draws += 1
                if not projection.pregame_pending:
                    projection.draws_this_turn[player_id] = projection.draws_this_turn.get(player_id, 0) + 1
                if getattr(projection.step, 'value', projection.step) == 'draw' and projection.active_player == player_id:
                    projection.draws_in_current_draw_step[player_id] = projection.draws_in_current_draw_step.get(player_id, 0) + 1
        elif key == 'gain_life' and not player_cant_gain_life(projection, player_id):
            replacement = replace_gain_life(projection, player_id, amount, used_source_ids=used)
            if replacement is not None:
                next_key, payload = replacement
                visit(next_key, payload['amount'], payload.get('__used_replacement_source_ids', []))

    visit('draw_cards', max(0, int(count)), [])
    return draws
