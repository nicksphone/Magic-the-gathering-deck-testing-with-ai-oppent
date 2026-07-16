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
