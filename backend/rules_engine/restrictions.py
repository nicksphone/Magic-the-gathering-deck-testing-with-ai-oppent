from __future__ import annotations

import re

from game_state.state import Step, Zone

_NUMBER_WORDS = {word: value for value, word in enumerate(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"))}
_LAND_GATED_COMBAT_RE = re.compile(r"\b(?:can't|cannot) (attack(?: or block)?|block) unless you control (\w+) or more lands\b", re.IGNORECASE)


def _land_gate_prevents(state, card_id: str, action: str) -> bool | None:
    card = state.cards[card_id]
    for match in _LAND_GATED_COMBAT_RE.finditer(card.oracle_text or ""):
        if action not in match.group(1).lower().split(" or "):
            continue
        token = match.group(2).lower()
        required = int(token) if token.isdigit() else _NUMBER_WORDS.get(token)
        if required is None:
            continue
        lands = sum(
            state.cards[cid].zone == Zone.BATTLEFIELD and "Land" in state.cards[cid].types
            for cid in state.players[card.controller].battlefield
        )
        return lands < required
    return None


def card_cant_attack(state, card_id: str) -> bool:
    card = state.cards[card_id]
    land_gate = _land_gate_prevents(state, card_id, "attack")
    if land_gate is not None:
        return land_gate
    text = (card.oracle_text or "").lower()
    if "can't attack alone" in text or "cannot attack alone" in text:
        return False
    if "can't attack" in text or "cannot attack" in text:
        if "unless" not in text:
            return True
    return False


def card_must_attack_if_able(state, card_id: str) -> bool:
    text = (state.cards[card_id].oracle_text or "").lower()
    return "attacks each combat if able" in text or "must attack each combat if able" in text


def card_cant_block(state, card_id: str) -> bool:
    land_gate = _land_gate_prevents(state, card_id, "block")
    if land_gate is not None:
        return land_gate
    text = (state.cards[card_id].oracle_text or "").lower()
    return "can't block" in text or "cannot block" in text


def card_must_block_if_able(state, card_id: str) -> bool:
    text = (state.cards[card_id].oracle_text or "").lower()
    return "blocks each combat if able" in text or "must block each combat if able" in text


def card_cant_attack_alone(state, card_id: str) -> bool:
    text = (state.cards[card_id].oracle_text or "").lower()
    return "can't attack alone" in text or "cannot attack alone" in text


def can_activate_in_current_timing(state, ability_text: str, player_id: int) -> bool:
    text = (ability_text or "").lower()
    if "activate only as a sorcery" in text or "activate only any time you could cast a sorcery" in text:
        return (state.active_player == player_id
                and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}
                and not state.stack)
    return True


def can_cast_in_current_timing(state, card, player_id: int) -> tuple[bool, str]:
    text = (card.oracle_text or "").lower()
    if re.search(r"\baftermath\b", text) and card.zone != Zone.GRAVEYARD:
        return (False, "An Aftermath half can be cast only from a graveyard.")
    step = state.step
    is_active = state.active_player == player_id
    opponent_turn = state.active_player != player_id
    types = {str(value) for value in (getattr(card, "types", []) or [])}
    has_flash = "flash" in {str(value).lower() for value in (getattr(card, "keywords", []) or [])} or "flash" in text
    in_combat = step in {
        Step.BEGIN_COMBAT,
        Step.DECLARE_ATTACKERS,
        Step.DECLARE_BLOCKERS,
        Step.COMBAT_DAMAGE,
        Step.END_COMBAT,
    }
    in_upkeep = step == Step.UPKEEP

    # Non-instant spells and permanents use sorcery timing unless they have
    # flash. The previous implementation only handled explicit "only during"
    # clauses, which exposed ordinary sorceries/creatures as legal casts in
    # every priority window.
    non_instant_spell = bool(types & {"Sorcery", "Creature", "Artifact", "Enchantment", "Planeswalker", "Battle"})
    if non_instant_spell and "Instant" not in types and not has_flash:
        if not (is_active and step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and not state.stack):
            return (False, "Cast only at sorcery speed.")

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
