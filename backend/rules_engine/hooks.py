from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import re


@dataclass
class CostContext:
    player_id: int
    card_name: str
    mana_cost: str
    is_spell: bool = True
    generic_reduction: int = 0
    generic_increase: int = 0
    state: Any = None
    spell_types: set[str] | None = None


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
    out = _apply_static_spell_taxes(context)
    for modifier in _COST_MODIFIERS:
        out = modifier(out)
    return out


_SPELL_TAX_RE = re.compile(
    r"(?P<scope>your opponents'|your|all)?\s*"
    r"(?P<kind>noncreature|creature|artifact|enchantment|instant or sorcery|)\s*"
    r"spells? cost \{(?P<amount>\d+)\} more to cast"
)


def _apply_static_spell_taxes(context: CostContext) -> CostContext:
    """Apply generic spell taxes from supported battlefield Oracle text."""
    if context.state is None or not context.is_spell or not context.spell_types:
        return context
    if "Land" in context.spell_types:
        return context
    increase = int(context.generic_increase)
    target_types = {str(value).lower() for value in context.spell_types}
    for pid in context.state.players:
        for cid in context.state.players[pid].battlefield:
            source = context.state.cards.get(cid)
            if source is None:
                continue
            text = (getattr(source, "oracle_text", "") or "").lower()
            for match in _SPELL_TAX_RE.finditer(text):
                scope = (match.group("scope") or "").strip()
                if scope == "your" and source.controller != context.player_id:
                    continue
                if scope == "your opponents'" and source.controller == context.player_id:
                    continue
                kind = (match.group("kind") or "").strip()
                if kind == "noncreature" and "creature" in target_types:
                    continue
                if kind == "creature" and "creature" not in target_types:
                    continue
                if kind == "artifact" and "artifact" not in target_types:
                    continue
                if kind == "enchantment" and "enchantment" not in target_types:
                    continue
                if kind == "instant or sorcery" and not target_types.intersection({"instant", "sorcery"}):
                    continue
                increase += int(match.group("amount"))
    context.generic_increase = increase
    return context


def apply_replacement_effects(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    ctx = ReplacementContext(event=event, payload=payload)
    for effect in _REPLACEMENT_EFFECTS:
        ctx = effect(ctx)
    return ctx.payload
