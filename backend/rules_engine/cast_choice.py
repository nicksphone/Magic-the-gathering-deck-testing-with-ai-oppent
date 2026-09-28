from __future__ import annotations

import re
from copy import copy
from typing import Any

from game_state.state import CardInstance, MatchState
from rules_engine.oracle_effects import DIVIDE_RE, inspect_target_hints
from rules_engine.targeting import validate_cast_targets

CHOOSE_TWO_RE = re.compile(r"choose two(?:\s*[—-])?", re.IGNORECASE)
FIXED_DAMAGE_RE = re.compile(r"deals?\s+(\d+)\s+damage", re.IGNORECASE)


def build_cast_hints(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    types = set(getattr(card, "types", []) or [])
    if types.intersection({"Creature", "Artifact", "Enchantment", "Planeswalker", "Battle", "Land"}) and not types.intersection({"Instant", "Sorcery"}):
        from rules_engine.attachments import is_aura
        if not is_aura(card):
            # This is a permanent spell, not one of its later abilities.
            # Preserve mana/face choices without borrowing ability targets.
            card = copy(card)
            card.oracle_text = ""
    hints = inspect_target_hints(state, card, controller, action_targets)
    hints["action_has_target_text"] = "target" in (card.oracle_text or "").lower()
    hints.setdefault("choice_schema", {})
    face_names = hints.get("face_names") or []
    if face_names:
        hints["choice_schema"]["selected_face_index"] = {
            "type": "integer",
            "required": False,
            "minimum": 0,
            "maximum": max(0, len(face_names) - 1),
        }
    if CHOOSE_TWO_RE.search(card.oracle_text or ""):
        hints["choose_two_modes"] = True
    if hints.get("modes"):
        if hints.get("choose_two_modes"):
            hints["choice_schema"]["mode_texts"] = {"type": "array", "required": True, "min_items": 2, "max_items": 2, "enum": hints["modes"]}
        else:
            hints["choice_schema"]["mode_text"] = {"type": "string", "required": False, "enum": hints["modes"]}
    if hints.get("requires_x_value"):
        hints["choice_schema"]["x_value"] = {"type": "integer", "required": True, "minimum": 0}
    if hints.get("player_targets"):
        hints["choice_schema"]["target_player"] = {"type": "integer", "required": False}
    if hints.get("creature_targets"):
        hints["choice_schema"]["target_card_id"] = {"type": "string", "required": False}
    if hints.get("permanent_targets"):
        hints["choice_schema"]["target_card_id"] = {"type": "string", "required": False}
    if hints.get("graveyard_creature_targets"):
        hints["choice_schema"]["target_card_id"] = {"type": "string", "required": False}
    if hints.get("aura_targets"):
        hints["choice_schema"]["target_card_id"] = {
            "type": "string",
            "required": True,
            "enum": [item["id"] for item in hints["aura_targets"]],
        }
    if hints.get("stack_targets"):
        hints["choice_schema"]["target_stack_id"] = {"type": "string", "required": False}
    if hints.get("unless_payment"):
        hints["choice_schema"]["pay_unless_counter"] = {"type": "boolean", "required": False}
    hints["choice_schema"]["replacement_source_id"] = {
        "type": "string",
        "required": False,
        "description": "Optional replacement-effect source ID returned by the replacement-options API.",
    }
    if hints.get("up_to_target_count"):
        hints["choice_schema"]["target_card_ids"] = {"type": "array", "required": False, "max_items": hints["up_to_target_count"]}
    return hints


def validate_cast_choice(hints: dict[str, Any], action_targets: dict[str, Any]) -> tuple[bool, str]:
    ok, err = validate_cast_targets(hints, action_targets)
    if not ok:
        return ok, err
    face_names = hints.get("face_names") or []
    if face_names and action_targets.get("selected_face_index") is not None:
        try:
            selected = int(action_targets.get("selected_face_index"))
        except Exception:
            return False, "Selected face index must be a valid integer."
        if selected < 0 or selected >= len(face_names):
            return False, "Selected face index is out of range."
    if hints.get("library_search") and action_targets.get("search_card_ids") is not None:
        return False, "Library cards are chosen when the search resolves, not when it is cast."
    if hints.get("topdeck_choice") and action_targets.get("topdeck_card_ids") is not None:
        return False, "Topdeck cards are chosen when the effect resolves, not when it is cast."
    if hints.get("top_choice") and any(action_targets.get(key) is not None for key in ("top_choice_hand_id", "top_choice_exile_id", "top_choice_bottom_ids")):
        return False, "Top-card choices are made when the effect resolves, not when it is cast."
    return True, ""


def enrich_divide_total(card: CardInstance, action_targets: dict[str, Any]) -> dict[str, Any]:
    targets = dict(action_targets or {})
    oracle_or_mode = f"{card.oracle_text or ''} {targets.get('mode_text') or ''} {' '.join(str(x) for x in (targets.get('mode_texts') or []))}".lower()
    if not DIVIDE_RE.search(oracle_or_mode):
        return targets
    x_value = targets.get("x_value")
    if x_value is not None and re.search(r"\bdeals?\s+x\s+damage", oracle_or_mode):
        targets["divide_total"] = int(x_value)
        return targets
    mode_text = str(targets.get("mode_text") or "")
    match = FIXED_DAMAGE_RE.search(mode_text) or FIXED_DAMAGE_RE.search(card.oracle_text or "")
    if match:
        targets["divide_total"] = int(match.group(1))
    return targets
