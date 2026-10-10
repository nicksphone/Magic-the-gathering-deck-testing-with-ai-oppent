from __future__ import annotations
from rules_engine.type_effects import effective_types

import re

from game_state.state import Step, Zone

_NUMBER_WORDS = {word: value for value, word in enumerate(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"))}
_LAND_GATED_COMBAT_RE = re.compile(r"\b(?:can't|cannot) (attack(?: or block)?|block) unless you control (\w+) or more lands\b", re.IGNORECASE)


def active_printed_text(state, card_id: str) -> str:
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.oracle_text import without_reminder_text
    text = without_reminder_text(getattr(state.cards[card_id], 'oracle_text', '') or '').lower()
    if not text:
        return ''
    if printed_abilities_suppressed(state, card_id):
        return ''
    return text


def _land_gate_prevents(state, card_id: str, action: str) -> bool | None:
    card = state.cards[card_id]
    for match in _LAND_GATED_COMBAT_RE.finditer(active_printed_text(state, card_id)):
        if action not in match.group(1).lower().split(" or "):
            continue
        token = match.group(2).lower()
        required = int(token) if token.isdigit() else _NUMBER_WORDS.get(token)
        if required is None:
            continue
        lands = sum(
            state.cards[cid].zone == Zone.BATTLEFIELD and "Land" in effective_types(state, state.cards[cid])
            for cid in state.players[card.controller].battlefield
        )
        return lands < required
    return None


def card_cant_attack(state, card_id: str) -> bool:
    from rules_engine.combat_constraints import combat_rule_text
    return any(re.fullmatch(r"(?:can't|cannot) attack(?: or block)?", clause)
               for clause in combat_rule_text(state, card_id).splitlines())


def card_must_attack_if_able(state, card_id: str) -> bool:
    from rules_engine.combat_constraints import combat_rule_text
    text = combat_rule_text(state, card_id)
    return any(clause in {'attacks each combat if able', 'attack each combat if able', 'must attack each combat if able'} for clause in text.splitlines())


def card_cant_block(state, card_id: str) -> bool:
    from rules_engine.continuous import has_keyword
    if has_keyword(state, card_id, 'decayed'):
        return True
    from rules_engine.combat_constraints import combat_rule_text
    return any(re.fullmatch(r"(?:can't|cannot) (?:attack or )?block", clause)
               for clause in combat_rule_text(state, card_id).splitlines())


def card_must_block_if_able(state, card_id: str) -> bool:
    from rules_engine.combat_constraints import combat_rule_text
    text = combat_rule_text(state, card_id)
    return any(clause in {'blocks each combat if able', 'block each combat if able', 'must block each combat if able'} for clause in text.splitlines())


def card_cant_attack_alone(state, card_id: str) -> bool:
    from rules_engine.combat_constraints import combat_rule_text
    return bool(re.search(r"\b(?:can't|cannot) attack(?: or block)? alone\b", combat_rule_text(state, card_id)))


def card_cant_block_alone(state, card_id: str) -> bool:
    from rules_engine.combat_constraints import combat_rule_text
    return bool(re.search(r"\b(?:can't|cannot) (?:attack or )?block alone\b", combat_rule_text(state, card_id)))


def split_second_active(state) -> bool:
    from rules_engine.targeting import stack_object_kind, stack_source_card
    from rules_engine.oracle_text import without_reminder_text

    for item in state.stack:
        if getattr(item, 'source_card_id', None) is None:
            continue
        if stack_object_kind(state, item) != 'spell':
            continue
        card = stack_source_card(state, item)
        if card is not None and (
            'split second' in {str(keyword).lower() for keyword in card.keywords}
            or any(line.strip().lower() == 'split second'
                   for line in without_reminder_text(card.oracle_text or '').splitlines())
        ):
            return True
    return False


def can_activate_in_current_timing(state, ability_text: str, player_id: int) -> bool:
    if split_second_active(state):
        return False
    text = (ability_text or "").lower()
    if "activate only as a sorcery" in text or "activate only any time you could cast a sorcery" in text:
        return (state.active_player == player_id
                and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}
                and not state.stack)
    return True


def has_global_flash_permission(state, player_id: int) -> bool:
    """Recognized unconditional static grant; not a zone or priority permission."""
    from rules_engine.continuous import _static_oracle_text, printed_abilities_suppressed

    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards.get(cid)
            if (source is None or source.zone != Zone.BATTLEFIELD
                    or source.controller != player_id
                    or printed_abilities_suppressed(state, cid)):
                continue
            if any(line.strip() == "you may cast spells as though they had flash."
                   for line in _static_oracle_text(source).splitlines()):
                return True
    return False


def can_cast_in_current_timing(state, card, player_id: int, *, during_resolution: bool = False) -> tuple[bool, str]:
    from rules_engine.graveyard_permissions import spell_cast_prohibited, graveyard_only_cast
    if spell_cast_prohibited(state, player_id, getattr(card, 'zone', None),
                             spell_types=tuple(sorted(set(effective_types(state, card))))):
        return False, 'A battlefield ability prohibits casting from this zone.'
    if getattr(card, 'zone', None) != Zone.GRAVEYARD and graveyard_only_cast(card):
        return False, 'This card may be cast only from its graveyard.'
    if split_second_active(state):
        return False, 'Split second prevents casting spells.'
    from rules_engine.alternative_casts import has_aftermath
    text = (card.oracle_text or "").lower()
    if has_aftermath(card) and card.zone != Zone.GRAVEYARD:
        return (False, "An Aftermath half can be cast only from a graveyard.")
    step = state.step
    is_active = state.active_player == player_id
    opponent_turn = state.active_player != player_id
    types = {str(value) for value in (effective_types(state, card) or [])}
    from rules_engine.loyalty_instructions import timing
    loyalty_allowed, loyalty_flash = timing(state, card, player_id)
    if not loyalty_allowed:
        return False, 'An opponent restricts casting to sorcery timing.'
    from rules_engine.oracle_text import without_reminder_text
    has_flash = ("flash" in {str(value).lower() for value in (getattr(card, "keywords", []) or [])}
                 or any(part.strip().rstrip('.') == "flash"
                        for line in without_reminder_text(text).splitlines()
                        for part in line.split(',')))
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
    if (non_instant_spell and "Instant" not in types and not has_flash
            and not during_resolution and not loyalty_flash and not has_global_flash_permission(state, player_id)):
        if not (is_active and step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and not state.stack):
            return (False, "Cast only at sorcery speed.")

    if "only during your turn" in text and not is_active:
        return (False, "Cast only during your turn.")
    if ("only during an opponent's turn" in text or "only during your opponent's turn" in text) and not opponent_turn:
        return (False, "Cast only during an opponent's turn.")
    if "only during combat" in text and not in_combat:
        return (False, "Cast only during combat.")
    if "only during combat on your turn" in text and not is_active:
        return (False, "Cast only during combat on your turn.")
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
    from rules_engine.continuous import printed_abilities_suppressed
    for pid in state.players:
        for cid in state.players[pid].battlefield:
            perm = state.cards[cid]
            if perm.zone != Zone.BATTLEFIELD:
                continue
            if printed_abilities_suppressed(state, cid):
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
