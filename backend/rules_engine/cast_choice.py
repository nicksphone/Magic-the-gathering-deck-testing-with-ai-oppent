from __future__ import annotations

import re
from typing import Any

from game_state.state import CardInstance, MatchState
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.targeting import validate_cast_targets

CHOOSE_TWO_RE = re.compile(r"choose two(?:\s*[—-])?", re.IGNORECASE)
FIXED_DAMAGE_RE = re.compile(r"deals?\\s+(\\d+)\\s+damage", re.IGNORECASE)
DIVIDE_RE = re.compile(r"divide[^.]*damage[^.]*among[^.]*targets", re.IGNORECASE)


def build_cast_hints(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hints = inspect_target_hints(state, card, controller, action_targets)
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
    if hints.get("up_to_target_count"):
        hints["choice_schema"]["target_card_ids"] = {"type": "array", "required": False, "max_items": hints["up_to_target_count"]}
    if hints.get("library_search"):
        search = hints["library_search"]
        hints["choice_schema"]["search_card_ids"] = {
            "type": "array",
            "required": not bool(search.get("allow_zero")),
            "max_items": int(search.get("max_count", 0) or len(search.get("candidates") or [])),
            "items": {"type": "string", "enum": [item["id"] for item in search.get("candidates", [])]},
        }
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
    search = hints.get("library_search") or {}
    if search:
        selected = action_targets.get("search_card_ids")
        if selected is None:
            selected = []
        if not isinstance(selected, list):
            return False, "Library search choices must be a list of card IDs."
        candidate_ids = {str(item.get("id")) for item in (search.get("candidates") or [])}
        if any(str(cid) not in candidate_ids for cid in selected):
            return False, "A selected library card does not match the search restriction."
        max_count = int(search.get("max_count", 0) or 0)
        if max_count and len(selected) > max_count:
            return False, f"Too many library cards selected (max {max_count})."
        if not search.get("allow_zero") and not selected and candidate_ids:
            return False, "A library card must be selected."
    topdeck = hints.get("topdeck_choice") or {}
    if topdeck:
        selected = action_targets.get("topdeck_card_ids") or []
        if not isinstance(selected, list):
            return False, "Topdeck choices must be a list of card IDs."
        candidate_ids = {str(item.get("id")) for item in (topdeck.get("candidates") or [])}
        if any(str(cid) not in candidate_ids for cid in selected):
            return False, "A selected topdeck card does not match the effect restriction."
        max_count = int(topdeck.get("max_count", 0) or 0)
        if max_count and len(selected) > max_count:
            return False, f"Too many topdeck cards selected (max {max_count})."
    top_choice = hints.get("top_choice") or {}
    if top_choice:
        candidate_ids = {str(item.get("id")) for item in (top_choice.get("candidates") or [])}
        hand_id = action_targets.get("top_choice_hand_id")
        exile_id = action_targets.get("top_choice_exile_id")
        bottom_ids = action_targets.get("top_choice_bottom_ids") or []
        if not hand_id or not exile_id or not isinstance(bottom_ids, list):
            return False, "Top-card choices require one hand card, one exile card, and an ordered bottom list."
        chosen = [str(hand_id), str(exile_id), *[str(cid) for cid in bottom_ids]]
        if len(chosen) != len(candidate_ids) or len(set(chosen)) != len(chosen) or set(chosen) != candidate_ids:
            return False, "Top-card choices must place every inspected card exactly once."
    return True, ""


def enrich_divide_total(card: CardInstance, action_targets: dict[str, Any]) -> dict[str, Any]:
    targets = dict(action_targets or {})
    if "divide_total" in targets:
        return targets
    oracle_or_mode = f"{card.oracle_text or ''} {targets.get('mode_text') or ''} {' '.join(str(x) for x in (targets.get('mode_texts') or []))}".lower()
    if not DIVIDE_RE.search(oracle_or_mode):
        return targets
    x_value = targets.get("x_value")
    if x_value is not None:
        targets["divide_total"] = int(x_value)
        return targets
    mode_text = str(targets.get("mode_text") or "")
    match = FIXED_DAMAGE_RE.search(mode_text) or FIXED_DAMAGE_RE.search(card.oracle_text or "")
    if match:
        targets["divide_total"] = int(match.group(1))
    return targets
