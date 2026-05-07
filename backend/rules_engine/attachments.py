from __future__ import annotations

from game_state.state import Zone
from rules_engine.protection import protected_from_source


def is_aura(card) -> bool:
    type_line = (getattr(card, "type_line", "") or "").lower()
    return "Enchantment" in (getattr(card, "types", []) or []) and "aura" in type_line


def is_equipment(card) -> bool:
    type_line = (getattr(card, "type_line", "") or "").lower()
    return "Artifact" in (getattr(card, "types", []) or []) and "equipment" in type_line


def attach_if_legal(state, attachment_id: str, target_id: str | None) -> bool:
    if not target_id or target_id not in state.cards:
        return False
    attachment = state.cards.get(attachment_id)
    target = state.cards.get(target_id)
    if not attachment or not target:
        return False
    if target.zone != Zone.BATTLEFIELD:
        return False
    if protected_from_source(state, target_id, attachment):
        return False
    if is_aura(attachment):
        oracle = (attachment.oracle_text or "").lower()
        if "enchant creature" in oracle and "Creature" not in target.types:
            return False
        if "enchant land" in oracle and "Land" not in target.types:
            return False
    attachment.counters["__attached_to"] = 0
    setattr(attachment, "attached_to", target_id)
    return True


def attached_to(card) -> str | None:
    return getattr(card, "attached_to", None)
