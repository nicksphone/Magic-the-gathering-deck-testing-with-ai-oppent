"""Shared classification for AI decision-trace diagnostics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


MEANINGFUL_ACTION_TYPES = frozenset(
    {
        "play_land",
        "cast_spell",
        "activate_ability",
        "activate_loyalty",
        "cycle_card",
        "equip",
        "attack",
        "block",
    }
)


def is_actionable_move(move: Mapping[str, object]) -> bool:
    """Exclude pass and restricted UI placeholders from legal-action diagnostics."""
    move_type = str(move.get("type") or "")
    return bool(move_type) and move_type != "pass_priority" and not move_type.endswith("_restricted")


def has_actionable_move(moves: Iterable[Mapping[str, object]]) -> bool:
    return any(is_actionable_move(move) for move in moves)


def is_meaningful_move(move: Mapping[str, object]) -> bool:
    """Identify actions that change resources, board state, or combat decisions."""
    return is_actionable_move(move) and str(move.get("type") or "") in MEANINGFUL_ACTION_TYPES


def has_meaningful_move(moves: Iterable[Mapping[str, object]]) -> bool:
    return any(is_meaningful_move(move) for move in moves)


def decision_reason_code(
    action: Mapping[str, object],
    reasoning: str,
    *,
    legal_non_pass: bool,
    meaningful_non_pass: bool,
    active_player: int | None,
    player_id: int,
    step: object,
    stack_empty: bool,
) -> str:
    """Normalize free-form AI reasoning into stable analytics labels.

    The text remains in the trace for review. These labels are intentionally
    conservative: a main-phase pass with options is only called a hold when
    the AI explanation indicates interaction or response preservation.
    """
    action_type = str(action.get("type") or "")
    step_name = str(step or "").split(".")[-1].lower()
    text = str(reasoning or "").lower()

    if action_type == "pass_priority":
        if not legal_non_pass:
            return "pass_no_action"
        if not meaningful_non_pass:
            return "pass_nonmeaningful_option"
        if step_name in {"precombat_main", "postcombat_main"} and active_player == player_id and stack_empty:
            if any(token in text for token in ("hold", "interaction", "response", "counter", "instant")):
                return "hold_up_interaction"
            return "pass_with_meaningful_option"
        return "pass_response_window"

    keyword_labels = (
        (("mulligan", "keep hand"), "opening_hand"),
        (("land development", "reliable land", "land drop"), "land_development"),
        (("stabilization", "stabilize", "remove pressure"), "stabilize"),
        (("stack", "threatening stack", "interaction"), "stack_interaction"),
        (("card advantage", "draw"), "card_advantage"),
        (("closure", "conversion", "inevitability", "proactive"), "proactive_conversion"),
        (("stall",), "anti_stall"),
        (("combat", "attack", "block"), "combat_plan"),
        (("strategic planner", "best line"), "strategic_line"),
    )
    for keywords, label in keyword_labels:
        if any(keyword in text for keyword in keywords):
            return label
    return action_type or "unknown"
