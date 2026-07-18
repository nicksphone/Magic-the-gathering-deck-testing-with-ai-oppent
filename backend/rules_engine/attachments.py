from __future__ import annotations

from game_state.state import Zone
from rules_engine.protection import protected_from_source


def is_aura(card) -> bool:
    type_line = (getattr(card, "type_line", "") or "").lower()
    types = {str(value).lower() for value in (getattr(card, "types", []) or [])}
    return "enchantment" in types and "aura" in type_line


def is_equipment(card) -> bool:
    type_line = (getattr(card, "type_line", "") or "").lower()
    types = {str(value).lower() for value in (getattr(card, "types", []) or [])}
    return "artifact" in types and "equipment" in type_line


def attachment_target_is_legal(state, attachment, target_id: str | None) -> bool:
    if not target_id:
        return False
    if target_id.startswith("player:"):
        return is_aura(attachment) and "enchant player" in (attachment.oracle_text or "").lower()
    target = state.cards.get(target_id)
    if not target or target.zone != Zone.BATTLEFIELD:
        return False
    if protected_from_source(state, target_id, attachment):
        return False
    if not is_aura(attachment):
        return True
    oracle = (attachment.oracle_text or "").lower()
    target_types = {str(value).lower() for value in (getattr(target, "types", []) or [])}
    restrictions = {
        "creature": "creature" in target_types,
        "artifact": "artifact" in target_types,
        "enchantment": "enchantment" in target_types,
        "land": "land" in target_types,
        "planeswalker": "planeswalker" in target_types,
        "permanent": True,
    }
    requested = [kind for kind in restrictions if f"enchant {kind}" in oracle]
    if not requested:
        return True
    return any(restrictions[kind] for kind in requested)


def attach_if_legal(state, attachment_id: str, target_id: str | None) -> bool:
    if not target_id or target_id not in state.cards:
        return False
    attachment = state.cards.get(attachment_id)
    target = state.cards.get(target_id)
    if not attachment or not target:
        return False
    if not attachment_target_is_legal(state, attachment, target_id):
        return False
    attachment.counters["__attached_to"] = 0
    setattr(attachment, "attached_to", target_id)
    return True


def attached_to(card) -> str | None:
    return getattr(card, "attached_to", None)
