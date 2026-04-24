from __future__ import annotations

from game_state.state import MatchState, Zone


def apply_state_based_actions(state: MatchState) -> None:
    for pid, player in state.players.items():
        if player.life <= 0:
            state.winner = 1 if pid == 2 else 2
            state.log.append(f"{player.name} has 0 or less life and loses.")

    for cid, card in list(state.cards.items()):
        if "Creature" in card.types and card.zone == Zone.BATTLEFIELD and card.toughness is not None and card.toughness <= 0:
            pstate = state.players[card.controller]
            if cid in pstate.battlefield:
                pstate.battlefield.remove(cid)
                pstate.graveyard.append(cid)
                card.zone = Zone.GRAVEYARD
                state.log.append(f"State-based action: {card.name} dies due to 0 toughness.")
