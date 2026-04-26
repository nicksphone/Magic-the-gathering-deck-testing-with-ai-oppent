from __future__ import annotations

from typing import Any

from rules_engine.protection import protection_match_reason


def validate_cast_targets(target_hints: dict[str, Any], action_targets: dict[str, Any]) -> tuple[bool, str]:
    action_targets = action_targets or {}
    modes = target_hints.get("modes") or []
    choose_two = bool(target_hints.get("choose_two_modes"))

    if choose_two:
        selected = action_targets.get("mode_texts") or []
        if len(selected) != 2:
            return False, "Exactly two modes must be selected."
        if len(set(selected)) != 2:
            return False, "Mode selections must be different."
        for mode in selected:
            if mode not in modes:
                return False, "Invalid mode selected."
    elif modes and action_targets.get("mode_text") and action_targets.get("mode_text") not in modes:
        return False, "Invalid mode selected."

    if target_hints.get("requires_x_value") and int(action_targets.get("x_value", -1) or -1) < 0:
        return False, "X value is required and must be non-negative."

    up_to = int(target_hints.get("up_to_target_count", 0) or 0)
    if up_to > 0:
        target_ids = action_targets.get("target_card_ids") or []
        if len(target_ids) > up_to:
            return False, f"Too many targets selected (max {up_to})."

    divide_total = action_targets.get("divide_total")
    distribution = action_targets.get("target_distribution") or {}
    if target_hints.get("supports_divide") and not distribution:
        return False, "A target distribution is required."
    if distribution:
        for value in distribution.values():
            if int(value) < 0:
                return False, "Distribution values must be non-negative."
    if divide_total is not None:
        try:
            expected = int(divide_total)
        except Exception:
            return False, "Invalid divide_total value."
        actual = sum(int(v) for v in distribution.values())
        if actual != expected:
            return False, "Damage/counter distribution must match divide_total."

    mode_oracle = " ".join(
        [str(action_targets.get("mode_text") or "")]
        + [str(x) for x in (action_targets.get("mode_texts") or [])]
    ).lower()
    if target_hints.get("stack_targets") and ("target spell" in mode_oracle or not mode_oracle):
        if not action_targets.get("target_stack_id"):
            return False, "A stack target is required."
    if target_hints.get("creature_targets") and ("target creature" in mode_oracle):
        if not action_targets.get("target_card_id") and not (action_targets.get("target_card_ids") or []):
            return False, "A creature target is required."
    if target_hints.get("player_targets") and ("target player" in mode_oracle or "any target" in mode_oracle):
        if action_targets.get("target_player") is None and not action_targets.get("target_card_id"):
            return False, "A player or permanent target is required."

    return True, ""


def validate_protection_targets(state, source_card, action_targets: dict[str, Any]) -> tuple[bool, str]:
    target_ids: list[str] = []
    target_card_id = action_targets.get("target_card_id")
    if target_card_id:
        target_ids.append(target_card_id)
    target_card_ids = action_targets.get("target_card_ids") or []
    target_ids.extend([cid for cid in target_card_ids if cid not in target_ids])
    for cid in target_ids:
        target = state.cards.get(cid)
        if not target:
            continue
        reason = protection_match_reason(state, cid, source_card)
        if reason is not None:
            return False, f"Target {target.name} has protection from {reason}."
    return True, ""
