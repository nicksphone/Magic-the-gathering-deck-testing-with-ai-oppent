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
    oracle_text: str = ""
    ability_kind: str | None = None
    source_card_id: str | None = None
    target_card_id: str | None = None


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
    out = _apply_domain_self_discount(out)
    out = _apply_equip_discounts(out)
    for modifier in _COST_MODIFIERS:
        out = modifier(out)
    return out


def equip_cost_modifier(clause: str) -> tuple[str, int] | None:
    match = re.fullmatch(r"equip abilities you activate that target (enchanted creature|this creature) cost \{(\d+)\} less to activate", clause)
    if match:
        return match.group(1), int(match.group(2))
    match = re.fullmatch(r"equip costs you pay cost \{(\d+)\} less", clause)
    return ("all", int(match.group(1))) if match else None


def _apply_equip_discounts(context: CostContext) -> CostContext:
    if context.state is None or context.is_spell or context.ability_kind != "equip":
        return context
    from game_state.state import Zone
    from rules_engine.continuous import _static_oracle_text, effective_power
    from rules_engine.attachments import is_aura, is_equipment
    target = context.state.cards.get(context.target_card_id)
    equipment = context.state.cards.get(context.source_card_id)
    if (target is None or target.zone != Zone.BATTLEFIELD or "Creature" not in target.types
            or equipment is None or equipment.zone != Zone.BATTLEFIELD or not is_equipment(equipment)):
        return context
    for cid in context.state.players[context.player_id].battlefield:
        source = context.state.cards[cid]
        if source.controller != context.player_id:
            continue
        for clause in re.split(r"[.\n]", _static_oracle_text(source)):
            clause = clause.strip()
            modifier = equip_cost_modifier(clause)
            if modifier:
                kind, amount = modifier
                applies = (is_aura(source) and source.attached_to == target.id) if kind == "enchanted creature" else (source.id == target.id and "Creature" in source.types) if kind == "this creature" else True
                if applies:
                    context.generic_reduction += amount
    if re.search(r"^equip (?:\{[^}]+\})+\. this ability costs \{x\} less to activate, where x is the power of the creature it targets\.$",
                 (equipment.oracle_text or "").lower(), re.M):
        context.generic_reduction += max(0, effective_power(context.state, target.id))
    return context


_DOMAIN_DISCOUNT_RE = re.compile(
    r"this spell costs \{(\d+)\} less to cast for each basic land type among lands you control",
    re.IGNORECASE,
)


def _apply_domain_self_discount(context: CostContext) -> CostContext:
    if context.state is None or not context.is_spell or not context.oracle_text:
        return context
    match = _DOMAIN_DISCOUNT_RE.search(context.oracle_text)
    if match:
        from rules_engine.domain import basic_land_type_count
        context.generic_reduction += int(match.group(1)) * basic_land_type_count(context.state, context.player_id)
    return context


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
