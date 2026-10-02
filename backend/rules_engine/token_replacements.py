"""Bounded commuting token-creation doublers, distinct from entry counters."""
import re

from game_state.state import Zone
from rules_engine.oracle_text import without_reminder_text


def token_creation_amount(state, controller, amount):
    from rules_engine.continuous import printed_abilities_suppressed
    amount = max(0, int(amount))
    if not amount:
        return 0
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards.get(cid)
            if source is None or source.zone != Zone.BATTLEFIELD:
                continue
            if printed_abilities_suppressed(state, cid):
                continue
            for line in without_reminder_text(source.oracle_text).splitlines():
                line = line.strip().lower().removesuffix('.')
                controlled = re.fullmatch(
                    r'if an effect would create one or more tokens under your control, it creates twice that many of those tokens instead'
                    r'|if one or more tokens would be created under your control, twice that many of those tokens are created instead', line)
                all_tokens = re.fullmatch(
                    r'if one or more tokens would be created, twice that many of those tokens are created instead', line)
                if all_tokens or controlled and source.controller == controller:
                    before = amount
                    amount *= 2
                    state.log.append(f'{source.name} replaces creation of {before} tokens with {amount}.')
    return amount
