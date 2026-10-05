"""Shared targetless tap-mana instructions, readiness and immediate activation."""
from dataclasses import dataclass
from functools import lru_cache

from game_state.state import Zone
from rules_engine.type_effects import effective_types
from rules_engine.mana_restrictions import UNFILTERED, ability_spending_rule, eligible


@dataclass(frozen=True)
class PaidManaStep:
    source_id: str
    ability_index: int
    color: str
    excluded_sources: frozenset[str]


@lru_cache(maxsize=8192)
def _printed_specs(name, type_line, oracle_text, is_land):
    from rules_engine.oracle_effects import ACTIVATED_ABILITY_RE
    from rules_engine.oracle_text import without_reminder_text
    from rules_engine.mana import _land_colors, DUAL_LAND_NAME_COLORS
    rows = []
    for index, match in enumerate(ACTIVATED_ABILITY_RE.finditer(without_reminder_text(oracle_text))):
        cost, effect = match[1].strip(), match[2].strip()
        if '{T}' in cost.upper() and 'target' not in effect.lower() and not any(
                word in (cost + ' ' + effect).lower() for word in ('library', 'libraries', 'draw ', 'mill ')) and (
                effect.lower().startswith('add ') or effect.lower().startswith('choose a color. add ')):
            rows.append((index, cost, effect))
    # Basic land subtypes grant intrinsic abilities even with reminder text removed.
    if is_land:
        colors = _land_colors('', type_line, '', fallback=False)
        if not colors and not oracle_text and name.lower().removeprefix('snow-covered ') in {'plains', 'island', 'swamp', 'mountain', 'forest'}:
            colors = _land_colors(name, '', '', fallback=False)
        # Preserve only the existing exact-name dual fallback for absent metadata.
        if not colors and not oracle_text and not type_line:
            colors = DUAL_LAND_NAME_COLORS.get(name.strip().lower(), set())
        if colors:
            for color in sorted(colors):
                effect = 'Add {' + color + '}.'
                if not any(cost == '{T}' and printed == effect for _, cost, printed in rows):
                    rows.append((max((row[0] for row in rows), default=-1) + 1, '{T}', effect))
    return tuple(rows)


def mana_ability_specs(card, state=None, *, entering=False):
    from rules_engine.land_types import effective_type_line, printed_land_abilities_lost
    line = getattr(card, 'type_line', '') or ''
    rows = _printed_specs(getattr(card, 'name', ''), line,
                          getattr(card, 'oracle_text', '') or '', 'Land' in effective_types(state, card))
    current = effective_type_line(state, card, entering=entering)
    lost = printed_land_abilities_lost(state, card, entering=entering)
    if not lost and current == line:
        return rows
    rows = [] if lost else list(rows)
    for _, cost, effect in _printed_specs('', current, '', 'Land' in effective_types(state, card)):
        if not any(existing_cost == cost and existing_effect == effect
                   for _, existing_cost, existing_effect in rows):
            rows.append((max((row[0] for row in rows), default=-1) + 1, cost, effect))
    return tuple(rows)


def ability_outputs(state, card, spec):
    import re
    from rules_engine.mana import _nonland_mana_effect_outputs, _counter_mana_replacement
    _, _, effect = spec
    rule = ability_spending_rule(spec)
    if rule and rule.get('unsupported'):
        return {}
    if rule is not None and not rule.get('unsupported'):
        effect = re.sub(r'\.\s*Spend this mana only to [^.]+\.$', '', effect, flags=re.I)
    replacement = _counter_mana_replacement(card.name, card.oracle_text or '')
    if replacement and effect.lower().startswith(f'add {{{replacement[0].lower()}}}. if '):
        effect = 'Add one mana of any color' if card.counters.get(replacement[1], 0) > 0 else f'Add {{{replacement[0]}}}'
    return multiplied_outputs(state, card, _nonland_mana_effect_outputs(effect, state=state, card=card))


def mana_multiplier_clause(text):
    import re
    match = re.fullmatch(r'if you tap a permanent for mana, it produces (twice|three times) as much of that mana instead\.', text.strip().lower())
    return (2 if match[1] == 'twice' else 3) if match else None


def multiplied_outputs(state, card, outputs):
    from rules_engine.continuous import printed_abilities_suppressed
    multiplier = 1
    for cid in state.players[card.controller].battlefield:
        source = state.cards[cid]
        source_multiplier = 1
        for line in (source.oracle_text or '').splitlines():
            source_multiplier *= mana_multiplier_clause(line) or 1
        if source_multiplier != 1 and not printed_abilities_suppressed(state, cid):
            multiplier *= source_multiplier
    return {color: amount * multiplier for color, amount in outputs.items()}


def source_ready(state, card):
    from rules_engine.continuous import printed_abilities_suppressed, has_keyword
    return (card.zone == Zone.BATTLEFIELD and not card.tapped
            and not printed_abilities_suppressed(state, card.id, include_land_types=False)
            and ('Creature' not in effective_types(state, card) or not card.summoning_sick
                 or has_keyword(state, card.id, 'haste')))


def free_outputs(state, card, *, ignore_readiness=False, payment_context=UNFILTERED, reserved_card_ids=(), protected_life=0):
    from rules_engine.mana import mana_activation_is_free
    from rules_engine.costs import activated_cost_available, parse_activated_cost
    if not ignore_readiness and not source_ready(state, card):
        return {}
    outputs = {}
    for spec in mana_ability_specs(card, state):
        if payment_context is not UNFILTERED and not eligible(ability_spending_rule(spec), payment_context):
            continue
        cost = parse_activated_cost(spec[1])
        if not cost.supported or not mana_activation_is_free(state, card.id, cost.mana_cost):
            continue
        if (not ignore_readiness or reserved_card_ids or protected_life) and not activated_cost_available(state, card.controller, card.id, spec[1], ability_kind='mana', ability_index=spec[0], unavailable_resources=reserved_card_ids, protected_life=protected_life):
            continue
        for color, amount in ability_outputs(state, card, spec).items():
            if amount > 0:
                outputs[color] = max(outputs.get(color, 0), amount)
    return outputs


def tap_only_outputs(state, card, *, ignore_readiness=False):
    from rules_engine.costs import ActivatedCost, parse_activated_cost
    from rules_engine.continuous import printed_abilities_suppressed
    if printed_abilities_suppressed(state, card.id, include_land_types=False) or (not ignore_readiness and not source_ready(state, card)):
        return {}
    outputs = {}
    for spec in mana_ability_specs(card, state):
        if parse_activated_cost(spec[1]) == ActivatedCost(tap_source=True):
            for color, amount in ability_outputs(state, card, spec).items():
                if amount > 0:
                    outputs[color] = max(outputs.get(color, 0), amount)
    return outputs


def paid_candidates(state, player_id, excluded_sources=(), *, payment_context=UNFILTERED):
    from rules_engine.costs import ActivatedCost, parse_activated_cost
    from rules_engine.mana import mana_activation_is_free
    for cid in state.players[player_id].battlefield:
        card = state.cards[cid]
        if cid in excluded_sources or not source_ready(state, card):
            continue
        for spec in mana_ability_specs(card, state):
            if payment_context is not UNFILTERED and not eligible(ability_spending_rule(spec), payment_context):
                continue
            cost = parse_activated_cost(spec[1])
            if cost != ActivatedCost(mana_cost=cost.mana_cost, tap_source=True):
                continue
            if mana_activation_is_free(state, cid, cost.mana_cost):
                continue
            for color, amount in ability_outputs(state, card, spec).items():
                if amount > 0:
                    yield cid, spec, color


def activate_mana_ability(state, player_id, source_id, ability_index, color, *, excluded_sources=(), reserved_card_ids=(), protected_life=0):
    from rules_engine.costs import ActivatedCost, parse_activated_cost, apply_activated_costs
    from rules_engine.mana import auto_pay_cost, add_mana_to_pool
    card = state.cards.get(source_id)
    if card is None or card.controller != player_id or source_id not in state.players[player_id].battlefield or not source_ready(state, card):
        return False
    spec = next((row for row in mana_ability_specs(card, state) if row[0] == ability_index), None)
    if spec is None or color not in ability_outputs(state, card, spec):
        return False
    cost = parse_activated_cost(spec[1])
    if cost == ActivatedCost(mana_cost=cost.mana_cost, tap_source=True):
        if not auto_pay_cost(state, player_id, cost.mana_cost, payment_kind='activation',
                payment_types=set(effective_types(state, card)), card_name=card.name,
                source_card_id=source_id, ability_kind='mana', ability_index=ability_index,
                excluded_sources=set(excluded_sources) | {source_id}, reserved_card_ids=reserved_card_ids, protected_life=protected_life):
            return False
        from rules_engine.resource_events import tap_permanents
        tap_permanents(state, [source_id])
    elif not apply_activated_costs(state, player_id, source_id, spec[1], ability_kind='mana', ability_index=ability_index, unavailable_resources=reserved_card_ids, protected_life=protected_life):
        return False
    # Amounts are determined after costs, including any resource departures.
    amount = ability_outputs(state, card, spec).get(color, 0)
    add_mana_to_pool(state, player_id, color, amount, source_id=source_id, ability_effect=spec[2])
    state.log.append(f'{state.players[player_id].name} activates {card.name} for {amount} {color}.')
    return True


def mana_ability_views(state, card):
    from rules_engine.costs import activated_cost_available
    if not source_ready(state, card):
        return []
    return [{'ability_index': spec[0], 'cost_text': spec[1], 'outputs': outputs,
             'label': f'{spec[1]}: {spec[2]}'}
            for spec in mana_ability_specs(card, state)
            if (outputs := ability_outputs(state, card, spec))
            and activated_cost_available(state, card.controller, card.id, spec[1], ability_kind='mana', ability_index=spec[0])]


def preferred_free_spec(state, card, color, amount, *, payment_context=UNFILTERED, tap_only=False, reserved_card_ids=(), protected_life=0):
    """Preserve the selected ability's rule; prefer unrestricted tied outputs."""
    from rules_engine.costs import ActivatedCost, parse_activated_cost, activated_cost_available
    from rules_engine.mana import mana_activation_is_free
    candidates = []
    for spec in mana_ability_specs(card, state):
        cost = parse_activated_cost(spec[1])
        if not cost.supported or (tap_only and cost != ActivatedCost(tap_source=True)):
            continue
        if not tap_only and not mana_activation_is_free(state, card.id, cost.mana_cost):
            continue
        rule = ability_spending_rule(spec)
        if payment_context is not UNFILTERED and not eligible(rule, payment_context):
            continue
        if not activated_cost_available(state, card.controller, card.id, spec[1],
                ability_kind='mana', ability_index=spec[0], unavailable_resources=reserved_card_ids, protected_life=protected_life):
            continue
        if ability_outputs(state, card, spec).get(color) == amount:
            candidates.append(spec)
    return min(candidates, key=lambda spec: (parse_activated_cost(spec[1]).pay_life, ability_spending_rule(spec) is not None, spec[0]), default=None)


def free_output_life_cost(state, card, color, amount, *, payment_context=UNFILTERED,
                          reserved_card_ids=(), protected_life=0):
    from rules_engine.costs import parse_activated_cost
    if 'life' not in (card.oracle_text or '').lower():
        return 0
    spec = preferred_free_spec(state, card, color, amount, payment_context=payment_context,
                              reserved_card_ids=reserved_card_ids, protected_life=protected_life)
    return parse_activated_cost(spec[1]).pay_life if spec is not None else float('inf')
