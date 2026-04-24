from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class CostContext:
    player_id: int
    card_name: str
    mana_cost: str
    is_spell: bool = True
    generic_reduction: int = 0
    generic_increase: int = 0


@dataclass
class ReplacementContext:
    event: str
    payload: dict[str, Any]


CostModifier = Callable[[CostContext], CostContext]
ReplacementEffect = Callable[[ReplacementContext], ReplacementContext]

_COST_MODIFIERS: list[CostModifier] = []
_REPLACEMENT_EFFECTS: list[ReplacementEffect] = []


def register_cost_modifier(modifier: CostModifier) -> None:
    _COST_MODIFIERS.append(modifier)


def register_replacement_effect(effect: ReplacementEffect) -> None:
    _REPLACEMENT_EFFECTS.append(effect)


def apply_cost_modifiers(context: CostContext) -> CostContext:
    out = context
    for modifier in _COST_MODIFIERS:
        out = modifier(out)
    return out


def apply_replacement_effects(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    ctx = ReplacementContext(event=event, payload=payload)
    for effect in _REPLACEMENT_EFFECTS:
        ctx = effect(ctx)
    return ctx.payload

