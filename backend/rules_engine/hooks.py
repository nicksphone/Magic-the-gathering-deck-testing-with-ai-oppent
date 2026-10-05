from __future__ import annotations
from rules_engine.type_effects import effective_types

from dataclasses import dataclass, field
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
    spell_colors: set[str] | None = None
    spell_is_aura: bool = False
    spell_kicked: bool = False
    oracle_text: str = ""
    ability_kind: str | None = None
    ability_index: int | None = None
    source_card_id: str | None = None
    target_card_id: str | None = None
    floored_reductions: list[tuple[int, int]] = field(default_factory=list)


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
    from rules_engine.affinity import apply_affinity
    out = _apply_static_spell_taxes(context)
    out = apply_affinity(out)
    out = _apply_domain_self_discount(out)
    out = _apply_first_kicked_discount(out)
    out = _apply_equip_discounts(out)
    out = _apply_aura_discounts(out)
    from rules_engine.activation_modifiers import apply_activation_modifiers
    out = apply_activation_modifiers(out)
    for modifier in _COST_MODIFIERS:
        out = modifier(out)
    return out


def _apply_first_kicked_discount(context: CostContext) -> CostContext:
    if (context.state is None or not context.is_spell or not context.spell_kicked
            or context.state.kicked_spells_cast_this_turn.get(context.player_id, 0)):
        return context
    from rules_engine.continuous import _static_oracle_text, printed_abilities_suppressed
    for cid in context.state.players[context.player_id].battlefield:
        card = context.state.cards[cid]
        if printed_abilities_suppressed(context.state, cid):
            continue
        for amount in re.findall(r'the first kicked spell you cast each turn costs \{(\d+)\} less to cast',
                                 _static_oracle_text(card), re.I):
            context.generic_reduction += int(amount)
    return context


def equip_cost_modifier(clause: str) -> tuple[str, int] | None:
    match = re.fullmatch(r"equip abilities you activate that target (enchanted creature|this creature) cost \{(\d+)\} less to activate", clause)
    if match:
        return match.group(1), int(match.group(2))
    match = re.fullmatch(r"equip costs you pay cost \{(\d+)\} less", clause)
    return ("all", int(match.group(1))) if match else None


def aura_cost_modifier(clause: str) -> tuple[str, int] | None:
    match = re.fullmatch(r"aura spells you cast(?: that target (enchanted creature|this creature))? cost \{(\d+)\} less to cast", clause)
    return (match.group(1) or "all", int(match.group(2))) if match else None


def _apply_aura_discounts(context: CostContext) -> CostContext:
    if context.state is None or not context.is_spell:
        return context
    from rules_engine.attachments import is_aura
    from rules_engine.continuous import _static_oracle_text, printed_abilities_suppressed
    # A selected face can differ from the parent object's printed type line.
    if not context.spell_types or "Enchantment" not in context.spell_types or not (context.spell_is_aura or re.search(r"^enchant\s", context.oracle_text.lower(), re.M)):
        return context
    target = context.state.cards.get(context.target_card_id)
    for cid in context.state.players[context.player_id].battlefield:
        source = context.state.cards[cid]
        if source.controller != context.player_id or printed_abilities_suppressed(context.state, cid):
            continue
        for clause in re.split(r"[.\n]", _static_oracle_text(source)):
            modifier = aura_cost_modifier(clause.strip())
            if modifier is None:
                continue
            kind, amount = modifier
            applies = kind == "all" or (target is not None and "Creature" in effective_types(context.state, target) and (
                (kind == "enchanted creature" and is_aura(source) and source.attached_to == target.id)
                or (kind == "this creature" and source.id == target.id)))
            if applies:
                context.generic_reduction += amount
    return context


def _apply_equip_discounts(context: CostContext) -> CostContext:
    if context.state is None or context.is_spell or context.ability_kind != "equip":
        return context
    from game_state.state import Zone
    from rules_engine.continuous import _static_oracle_text, effective_power, printed_abilities_suppressed
    from rules_engine.attachments import is_aura, is_equipment
    target = context.state.cards.get(context.target_card_id)
    equipment = context.state.cards.get(context.source_card_id)
    if (target is None or target.zone != Zone.BATTLEFIELD or "Creature" not in effective_types(context.state, target)
            or equipment is None or equipment.zone != Zone.BATTLEFIELD or not is_equipment(equipment)):
        return context
    for cid in context.state.players[context.player_id].battlefield:
        source = context.state.cards[cid]
        if source.controller != context.player_id or printed_abilities_suppressed(context.state, cid):
            continue
        for clause in re.split(r"[.\n]", _static_oracle_text(source)):
            clause = clause.strip()
            modifier = equip_cost_modifier(clause)
            if modifier:
                kind, amount = modifier
                applies = (is_aura(source) and source.attached_to == target.id) if kind == "enchanted creature" else (source.id == target.id and "Creature" in effective_types(context.state, source)) if kind == "this creature" else True
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


def spell_cost_modifier(clause):
    """Recognize a whole unconditional clause; never silently drop a qualifier."""
    match = re.fullmatch(r"(?:(.+?) )?spells?((?: you| your opponents) cast)? cost \{(\d+)\} (more|less) to cast",
                         clause.strip().lower().rstrip('.'))
    if not match:
        return None
    head, tail, amount, direction = match.groups()
    head = head or ''
    scope = 'controller' if tail == ' you cast' else 'opponent' if tail else 'all'
    for prefix, legacy_scope in [("your opponents'", 'opponent'), ('your', 'controller'), ('all', 'all')]:
        if head == prefix or head.startswith(prefix+' '):
            if tail:
                return None
            scope, head = legacy_scope, head[len(prefix):].strip()
            break
    colors = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G', 'colorless': 'colorless'}
    subjects = head.split(' spells and ')
    if all(subject in colors for subject in subjects):
        return {'scope': scope, 'colors': {colors[subject] for subject in subjects},
                'amount': int(amount), 'increase': direction == 'more'}
    if head not in {'', 'noncreature', 'creature', 'artifact', 'enchantment', 'instant or sorcery', 'instant and sorcery'}:
        return None
    return {'scope': scope, 'kind': head, 'amount': int(amount), 'increase': direction == 'more'}


def _apply_static_spell_taxes(context: CostContext) -> CostContext:
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.activation_modifiers import turn_cost_taxes
    from game_state.state import Zone
    """Apply supported generic changes using the announced spell's properties."""
    if context.state is None or not context.is_spell or not context.spell_types:
        return context
    if "Land" in context.spell_types:
        return context
    increase = int(context.generic_increase)
    target_types = {str(value).lower() for value in context.spell_types}
    from rules_engine.colors import card_color_symbols
    from rules_engine.combat_constraints import static_clauses
    from rules_engine.continuous import _static_oracle_text
    from types import SimpleNamespace
    colors = context.spell_colors
    if colors is None:
        source_card = context.state.cards.get(context.source_card_id)
        colors = card_color_symbols(source_card or SimpleNamespace(mana_cost=context.mana_cost, oracle_text=context.oracle_text))
    for pid in context.state.players:
        for cid in context.state.players[pid].battlefield:
            source = context.state.cards.get(cid)
            if source is None:
                continue
            if printed_abilities_suppressed(context.state, cid):
                continue
            text = _static_oracle_text(source).lower()
            taxes = turn_cost_taxes(getattr(source, 'oracle_text', '') or '')
            if (taxes and source.zone == Zone.BATTLEFIELD
                    and context.state.active_player == source.controller and context.player_id != source.controller):
                increase += taxes[0]
            for clause in static_clauses(text):
                spec = spell_cost_modifier(clause)
                if spec is None:
                    continue
                if spec['scope'] == 'controller' and source.controller != context.player_id:
                    continue
                if spec['scope'] == 'opponent' and source.controller == context.player_id:
                    continue
                if 'colors' in spec and not (colors.intersection(spec['colors']) or not colors and 'colorless' in spec['colors']):
                    continue
                kind = spec.get('kind', '')
                if kind == "noncreature" and "creature" in target_types:
                    continue
                if kind == "creature" and "creature" not in target_types:
                    continue
                if kind == "artifact" and "artifact" not in target_types:
                    continue
                if kind == "enchantment" and "enchantment" not in target_types:
                    continue
                if kind in {"instant or sorcery", "instant and sorcery"} and not target_types.intersection({"instant", "sorcery"}):
                    continue
                if spec['increase']:
                    increase += spec['amount']
                else:
                    context.generic_reduction += spec['amount']
    context.generic_increase = increase
    return context


def apply_replacement_effects(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    ctx = ReplacementContext(event=event, payload=payload)
    for effect in _REPLACEMENT_EFFECTS:
        ctx = effect(ctx)
    return ctx.payload
