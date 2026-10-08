from __future__ import annotations
from rules_engine.type_effects import effective_types

import re

from game_state.state import Zone, assign_effect_timestamp, object_incarnation
from rules_engine.protection import protected_from_source
from rules_engine.oracle_text import without_reminder_text


def enchant_restriction(oracle_text: str):
    """Parse only the enchant instruction, never unrelated ability wording."""
    match = re.search(r"^enchant ([^\n]+)", (oracle_text or "").lower(), re.M)
    if not match:
        return None
    line = match[1].strip().removesuffix('.')
    if len(line) > 512:
        return None
    kind = r'(?:artifact creature|creature|artifact|enchantment|land|planeswalker|permanent)'
    return re.fullmatch(r'(?:(basic|nonbasic|nonland|noncreature) )?(' + kind
                        + r')(?:(?:, (?:or )?| or )(' + kind
                        + r'(?:(?:, (?:or )?| or )' + kind + r'){0,5}))?'
                        + r'(?: (you control|an opponent controls|your opponent controls))?', line)


def is_aura(card, state=None) -> bool:
    from rules_engine.bestow import is_bestowed
    if is_bestowed(card) and state is None:
        return True
    type_line, types = _attachment_characteristics(card, state)
    return "enchantment" in types and "aura" in type_line


def is_equipment(card, state=None) -> bool:
    type_line, types = _attachment_characteristics(card, state)
    return "artifact" in types and "equipment" in type_line


def is_fortification(card, state=None) -> bool:
    type_line, types = _attachment_characteristics(card, state)
    return "artifact" in types and "fortification" in type_line


def _attachment_characteristics(card, state):
    from rules_engine.land_types import effective_type_line
    line = effective_type_line(state, card) if state is not None else getattr(card, 'type_line', '') or ''
    types = effective_types(state, card) if state is not None else getattr(card, 'types', []) or []
    return line.lower(), {str(value).lower() for value in types}


def attachment_target_is_legal(state, attachment, target_id: str | None) -> bool:
    aura = is_aura(attachment, state)
    equipment = is_equipment(attachment, state)
    fortification = is_fortification(attachment, state)
    if not (aura or equipment or fortification):
        return False
    if not target_id:
        return False
    if target_id.startswith("player:"):
        return aura and "enchant player" in (attachment.oracle_text or "").lower()
    target = state.cards.get(target_id)
    if not target or target.zone != Zone.BATTLEFIELD:
        return False
    if (equipment or fortification) and ("Creature" in effective_types(state, attachment)
            or ("Creature" if equipment else "Land") not in effective_types(state, target)):
        return False
    if protected_from_source(state, target_id, attachment):
        return False
    if not aura:
        return True
    from rules_engine.bestow import is_bestowed
    if is_bestowed(attachment):
        return 'Creature' in effective_types(state, target)
    raw = attachment.oracle_text
    source = state.cards.get(attachment.id)
    # Same-surface compiler proxies may have stripped unknown parentheses.
    # Do not substitute an unrelated selected face or ability surface.
    if source is not None:
        normalized = without_reminder_text(raw or '').strip().casefold()
        if without_reminder_text(source.oracle_text or '').strip().casefold() == normalized:
            raw = source.oracle_text
        else:
            # Permanent-cast proxies retain only the normalized enchant instruction.
            lines = {line.strip() for line in (source.oracle_text or '').splitlines()
                     if re.match(r'^enchant ', line, re.I)
                     and without_reminder_text(line).strip().casefold() == normalized}
            if len(lines) == 1:
                raw = next(iter(lines))
            elif len(lines) > 1:
                return False
    restriction = enchant_restriction(raw)
    if restriction is None:
        return False
    target_types = {str(value).lower() for value in (effective_types(state, target) or [])}
    quality, subject, alternative, control = restriction.groups()
    if control == "you control" and target.controller != attachment.controller:
        return False
    if control in {"an opponent controls", "your opponent controls"} and target.controller == attachment.controller:
        return False
    basic = bool(re.search(r"\bbasic\b", (target.type_line or "").lower()))
    if ((quality == "basic" and not basic) or (quality == "nonbasic" and basic)
            or (quality == "nonland" and "land" in target_types)
            or (quality == "noncreature" and "creature" in target_types)):
        return False
    def matches(kind):
        return kind == "permanent" or (kind == "artifact creature" and {"artifact", "creature"} <= target_types) or kind in target_types
    return matches(subject) or bool(alternative and any(
        matches(kind) for kind in re.split(r', (?:or )?| or ', alternative)))


def attach_if_legal(state, attachment_id: str, target_id: str | None) -> bool:
    if not target_id or target_id not in state.cards:
        return False
    attachment = state.cards.get(attachment_id)
    target = state.cards.get(target_id)
    if not attachment or not target:
        return False
    if not attachment_target_is_legal(state, attachment, target_id):
        return False
    if attachment.attached_to == target_id:
        return True
    attachment.battlefield_incarnation = object_incarnation(attachment)
    assign_effect_timestamp(state, attachment_id)
    attachment.counters["__attached_to"] = 0
    setattr(attachment, "attached_to", target_id)
    return True


def attached_to(card) -> str | None:
    return getattr(card, "attached_to", None)
