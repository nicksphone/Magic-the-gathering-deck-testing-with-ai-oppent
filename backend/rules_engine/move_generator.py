from __future__ import annotations

from game_state.state import MatchState, Step, Zone
from rules_engine.cast_choice import build_cast_hints
from rules_engine.costs import check_cost_option_available, collect_cost_options
from rules_engine.mana import can_pay_with_pool_and_lands


def legal_moves(state: MatchState, player_id: int) -> list[dict]:
    if state.winner is not None:
        return []
    if state.pregame_pending:
        if player_id in state.kept_hands:
            return []
        return [
            {"type": "keep_hand"},
            {"type": "mulligan", "current_mulligans": state.mulligan_count.get(player_id, 0)},
        ]
    moves: list[dict] = [{"type": "pass_priority"}]
    player = state.players[player_id]

    if state.priority_player != player_id:
        return moves

    if state.step == Step.DECLARE_ATTACKERS and state.active_player == player_id:
        attackers = [
            cid
            for cid in player.battlefield
            if "Creature" in state.cards[cid].types
            and not state.cards[cid].tapped
            and not state.cards[cid].summoning_sick
        ]
        moves.append({"type": "attack", "options": attackers})
    if state.step == Step.DECLARE_BLOCKERS and state.active_player != player_id and state.attackers:
        blockers = [
            cid
            for cid in player.battlefield
            if "Creature" in state.cards[cid].types and not state.cards[cid].tapped
        ]
        attacker_opts = [{"id": cid, "name": state.cards[cid].name} for cid in state.attackers]
        blocker_opts = [{"id": cid, "name": state.cards[cid].name} for cid in blockers]
        moves.append({"type": "block", "attackers": attacker_opts, "blockers": blocker_opts})

    for cid in list(player.hand):
        card = state.cards[cid]
        if "Land" in card.types and player.lands_played_this_turn < 1 and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}:
            moves.append({"type": "play_land", "card_id": cid})
        elif (
            card.zone == Zone.HAND
            and _can_cast_spell(state, card, player_id)
        ):
            options = collect_cost_options(state, player_id, card)
            available_options = [o for o in options if check_cost_option_available(state, player_id, card, o)]
            if not available_options:
                continue
            moves.append(
                {
                    "type": "cast_spell",
                    "card_id": cid,
                    "card_name": card.name,
                    "mana_cost": card.mana_cost,
                    "cost_options": [
                        {
                            "id": o.id,
                            "label": o.label,
                            "mana_cost": o.mana_cost,
                            "pay_life": o.pay_life,
                            "discard_cards": o.discard_cards,
                            "sacrifice_creatures": o.sacrifice_creatures,
                        }
                        for o in available_options
                    ],
                    "target_hints": build_cast_hints(state, card, player_id),
                }
            )

    for cid in player.battlefield:
        if "Land" in state.cards[cid].types and not state.cards[cid].tapped:
            moves.append({"type": "tap_land_for_mana", "card_id": cid})
    return moves


def _can_cast_spell(state: MatchState, card, player_id: int) -> bool:
    if state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and state.active_player == player_id and not state.stack:
        return True
    if "Instant" in card.types:
        return True
    if "flash" in [k.lower() for k in card.keywords]:
        return True
    return False
