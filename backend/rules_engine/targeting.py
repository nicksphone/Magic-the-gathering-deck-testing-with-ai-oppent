from __future__ import annotations

from typing import Any


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

    return True, ""
