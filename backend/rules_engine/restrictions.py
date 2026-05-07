from __future__ import annotations

from game_state.state import Step, Zone


def card_cant_attack(state, card_id: str) -> bool:
    card = state.cards[card_id]
    text = (card.oracle_text or "").lower()
    if "can't attack" in text or "cannot attack" in text:
        if "unless" not in text:
            return True
    return False


def card_must_attack_if_able(state, card_id: str) -> bool:
    text = (state.cards[card_id].oracle_text or "").lower()
    return "attacks each combat if able" in text or "must attack each combat if able" in text


def card_cant_block(state, card_id: str) -> bool:
    text = (state.cards[card_id].oracle_text or "").lower()
    return "can't block" in text or "cannot block" in text


def card_must_block_if_able(state, card_id: str) -> bool:
    text = (state.cards[card_id].oracle_text or "").lower()
    return "blocks each combat if able" in text or "must block each combat if able" in text


def card_cant_attack_alone(state, card_id: str) -> bool:
    text = (state.cards[card_id].oracle_text or "").lower()
    return "can't attack alone" in text or "cannot attack alone" in text


def can_cast_in_current_timing(state, card, player_id: int) -> tuple[bool, str]:
    text = (card.oracle_text or "").lower()
    step = state.step
    is_active = state.active_player == player_id
    opponent_turn = state.active_player != player_id
    in_combat = step in {
        Step.BEGIN_COMBAT,
        Step.DECLARE_ATTACKERS,
        Step.DECLARE_BLOCKERS,
        Step.COMBAT_DAMAGE,
        Step.END_COMBAT,
    }
    in_upkeep = step == Step.UPKEEP

    if "only during your turn" in text and not is_active:
        return (False, "Cast only during your turn.")
    if ("only during an opponent's turn" in text or "only during your opponent's turn" in text) and not opponent_turn:
        return (False, "Cast only during an opponent's turn.")
    if "only during combat" in text and not in_combat:
        return (False, "Cast only during combat.")
    if "only during your upkeep" in text and not (is_active and in_upkeep):
        return (False, "Cast only during your upkeep.")
    if "cast only any time you could cast a sorcery" in text:
        if not (is_active and step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and not state.stack):
            return (False, "Cast only at sorcery speed.")
    if "only during your first main phase" in text or "only during your precombat main phase" in text:
        if not (is_active and step == Step.PRECOMBAT_MAIN and not state.stack):
            return (False, "Cast only during your first main phase.")
    if "only during your postcombat main phase" in text:
        if not (is_active and step == Step.POSTCOMBAT_MAIN and not state.stack):
            return (False, "Cast only during your postcombat main phase.")

    # Static battlefield timing locks.
    for pid in state.players:
        for cid in state.players[pid].battlefield:
            perm = state.cards[cid]
            if perm.zone != Zone.BATTLEFIELD:
                continue
            ptext = (perm.oracle_text or "").lower()
            if perm.controller != player_id:
                continue
            if "you can't cast spells during combat" in ptext and in_combat:
                return (False, "You can't cast spells during combat.")
            if "you can't cast spells during your opponents' turns" in ptext and opponent_turn:
                return (False, "You can't cast spells during your opponents' turns.")
            if "you can't cast spells during your opponent's turns" in ptext and opponent_turn:
                return (False, "You can't cast spells during your opponent's turns.")

    return (True, "")
