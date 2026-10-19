"""Shared loyalty timing: normal main phase or a complete active printed grant."""
import re

from game_state.state import Step, Zone
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.oracle_text import without_reminder_text
from rules_engine.restrictions import split_second_active


ENTRY_TURN_PERMISSION = re.compile(
    r'as long as (?P<source>.+?) entered this turn, you may activate '
    r'(?:her|his|its|their) loyalty abilities any time you could cast an instant\.',
    re.I,
)


def can_activate_loyalty_in_current_timing(state, card, player_id):
    if (card is None or card.zone != Zone.BATTLEFIELD or card.controller != player_id
            or card.id not in state.players[player_id].battlefield
            or state.priority_player != player_id
            or printed_abilities_suppressed(state, card.id) or split_second_active(state)):
        return False
    if state.step == Step.UNTAP or (state.step == Step.CLEANUP and (
            state.cleanup_pending or not state.cleanup_repeat_required)):
        return False
    if (state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}
            and state.active_player == player_id and not state.stack):
        return True
    if card.entered_turn != state.turn:
        return False
    for line in without_reminder_text(card.oracle_text or '').splitlines():
        permission = ENTRY_TURN_PERMISSION.fullmatch(line.strip())
        if permission and permission['source'].casefold() in {
                card.name.casefold(), 'this planeswalker', 'this permanent'}:
            return True
    return False
