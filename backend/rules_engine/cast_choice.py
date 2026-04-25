from __future__ import annotations

import re
from typing import Any

from game_state.state import CardInstance, MatchState
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.targeting import validate_cast_targets

CHOOSE_TWO_RE = re.compile(r"choose two", re.IGNORECASE)
FIXED_DAMAGE_RE = re.compile(r"deals?\\s+(\\d+)\\s+damage", re.IGNORECASE)
DIVIDE_RE = re.compile(r"divide[^.]*damage[^.]*among[^.]*targets", re.IGNORECASE)


def build_cast_hints(state: MatchState, card: CardInstance, controller: int) -> dict[str, Any]:
    hints = inspect_target_hints(state, card, controller)
    hints.setdefault("choice_schema", {})
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
    if hints.get("stack_targets"):
        hints["choice_schema"]["target_stack_id"] = {"type": "string", "required": False}
    if hints.get("up_to_target_count"):
        hints["choice_schema"]["target_card_ids"] = {"type": "array", "required": False, "max_items": hints["up_to_target_count"]}
    return hints


def validate_cast_choice(hints: dict[str, Any], action_targets: dict[str, Any]) -> tuple[bool, str]:
    return validate_cast_targets(hints, action_targets)


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
