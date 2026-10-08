"""Shared targetless mana instructions, readiness and immediate activation."""
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
    from rules_engine.costs import parse_activated_cost
    from rules_engine.oracle_effects import ACTIVATED_ABILITY_RE
    from rules_engine.oracle_text import without_reminder_text
    from rules_engine.mana import _land_colors, DUAL_LAND_NAME_COLORS
    rows = []
    for index, match in enumerate(ACTIVATED_ABILITY_RE.finditer(without_reminder_text(oracle_text))):
        cost, effect = match[1].strip(), match[2].strip()
        parsed = parse_activated_cost(cost)
        if parsed.supported and (parsed.tap_source or parsed.sacrifice_source
                or parsed.sacrifice_creatures or parsed.discard_cards) and 'target' not in effect.lower() and not any(
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


def _raw_output_vectors(state, card, spec):
    import re
    from rules_engine.costs import parse_activated_cost
    from rules_engine.mana import _nonland_mana_effect_outputs, _counter_mana_replacement, fixed_mana_vector, fixed_mana_alternatives
    _, _, effect = spec
    rule = ability_spending_rule(spec)
    if rule and rule.get('unsupported'):
        return []
    if rule is not None and not rule.get('unsupported'):
        effect = re.sub(r'\.\s*Spend this mana only to [^.]+\.$', '', effect, flags=re.I)
    replacement = _counter_mana_replacement(card.name, card.oracle_text or '')
    if replacement and effect.lower().startswith(f'add {{{replacement[0].lower()}}}. if '):
        effect = 'Add one mana of any color' if card.counters.get(replacement[1], 0) > 0 else f'Add {{{replacement[0]}}}'
    vector = fixed_mana_vector(effect)
    alternatives = fixed_mana_alternatives(effect)
    if alternatives is not None:
        return [dict(v) for v in alternatives]
    raw = vector if vector is not None else _nonland_mana_effect_outputs(effect, state=state, card=card)
    return [raw] if vector is not None else [{c: n} for c, n in raw.items()]


def _replace_base(state, card, spec, vector):
    from rules_engine.costs import parse_activated_cost
    return multiplied_outputs(state, card, vector) if parse_activated_cost(spec[1]).tap_source else dict(vector)


def _base_choices(state, card, spec):
    """Internal selectors bind a raw choice, not a flattened component maximum."""
    raw = _raw_output_vectors(state, card, spec)
    options = {}
    for base in raw:
        output = _replace_base(state, card, spec, base)
        selectors = list(output)
        if len(raw) > 1 and len(output) > 1:
            selectors = ['bundle:' + ','.join(f'{c}={n}' for c, n in sorted(base.items()))]
        for selector in selectors:
            options[selector] = (base, output)
    return options


def base_output_options(state, card, spec):
    return {selector: output for selector, (_, output) in _base_choices(state, card, spec).items()}


def advertised_output_options(state, card, spec):
    result = []
    for base in _raw_output_vectors(state, card, spec):
        if not base or any(n <= 0 for n in base.values()):
            continue
        for color in base:
            row = {'color': color, 'output_bundle': dict(base)}
            if row not in result:
                result.append(row)
    return result


def ability_outputs(state, card, spec):
    """Compatibility display of component maxima, not a payment representation."""
    outputs = {}
    for vector in base_output_options(state, card, spec).values():
        for color, amount in vector.items():
            outputs[color] = max(outputs.get(color, 0), amount)
    return outputs


@lru_cache(maxsize=8192)
def _native_vector_text(text):
    from rules_engine.oracle_effects import ACTIVATED_ABILITY_RE
    from rules_engine.oracle_text import without_reminder_text
    from rules_engine.mana import fixed_mana_vector, fixed_mana_alternatives
    from rules_engine.costs import parse_activated_cost
    for match in ACTIVATED_ABILITY_RE.finditer(without_reminder_text(text)):
        alternatives = fixed_mana_alternatives(match[2].strip())
        cost = parse_activated_cost(match[1].strip())
        if (len(fixed_mana_vector(match[2].strip()) or {}) > 1
                or alternatives and any(len(v) > 1 for v in alternatives)
                or cost.supported and (cost.sacrifice_creatures or cost.discard_cards or cost.discard_source)):
            return True
    return False


def needs_mana_bundles(state):
    from rules_engine.mana_triggers import has_fixed_mana_triggers
    return has_fixed_mana_triggers(state) or any(
        _native_vector_text(state.cards[cid].oracle_text or '')
        for player in state.players.values() for cid in player.battlefield)


@lru_cache(maxsize=8192)
def _fixed_only_mana_text(text):
    from rules_engine.oracle_effects import ACTIVATED_ABILITY_RE
    from rules_engine.oracle_text import without_reminder_text
    from rules_engine.costs import parse_activated_cost
    from rules_engine.mana import fixed_mana_vector
    return all((match := ACTIVATED_ABILITY_RE.fullmatch(line.strip()))
               and parse_activated_cost(match[1]).supported
               and fixed_mana_vector(match[2]) is not None
               for line in without_reminder_text(text).strip().splitlines())


def proven_missing_fixed_color(state, player_id, req, payment_context):
    """Negative proof only: complex boards keep the authoritative search."""
    from rules_engine.mana import fixed_mana_vector
    from rules_engine.mana_restrictions import available_pool
    pool, _ = available_pool(state.players[player_id], payment_context)
    missing = {c for c in 'WUBRGC' if req.get(c, 0) > pool.get(c, 0)}
    if not missing or state.stack or state.delayed_triggers or state.staged_triggers:
        return False
    possible = set()
    for player in state.players.values():
        for cid in player.battlefield:
            card = state.cards[cid]
            # Departures can unlock layered/granted production or mana triggers.
            if (card.type_effects or card.keyword_effects or card.base_stat_effects
                    or not _fixed_only_mana_text(card.oracle_text or '')):
                return False
            if card.controller == player_id:
                for spec in mana_ability_specs(card, state):
                    vector = fixed_mana_vector(spec[2])
                    if vector is None:
                        return False
                    possible.update(vector)
    return bool(missing - possible)


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
    outputs = {color: amount * multiplier for color, amount in outputs.items()}
    # Replacement applies to the land's production, never to another source's trigger.
    if outputs and sum(outputs.values()) >= 2 and 'Land' in effective_types(state, card):
        clause = 'if a land is tapped for two or more mana, it produces {c} instead of any other type and amount.'
        for player in state.players.values():
            for cid in player.battlefield:
                source = state.cards[cid]
                if (clause in (source.oracle_text or '').lower().splitlines()
                        and not printed_abilities_suppressed(state, cid)):
                    return {'C': 1}
    return outputs


def source_ready(state, card, spec=None):
    from rules_engine.paid_triggers import resolution_mana_ability_allowed
    if not resolution_mana_ability_allowed(state, card, spec):
        return False
    from rules_engine.continuous import printed_abilities_suppressed, has_keyword
    from rules_engine.costs import parse_activated_cost
    needs_tap = spec is None or parse_activated_cost(spec[1]).tap_source
    return (card.zone == Zone.BATTLEFIELD
            and not printed_abilities_suppressed(state, card.id, include_land_types=False)
            and (not needs_tap or (not card.tapped
                 and ('Creature' not in effective_types(state, card) or not card.summoning_sick
                      or has_keyword(state, card.id, 'haste')))))


def free_outputs(state, card, *, ignore_readiness=False, payment_context=UNFILTERED, reserved_card_ids=(), protected_life=0):
    if needs_mana_bundles(state):
        outputs = {}
        for _, _, bundle, _, _ in free_mana_options(state, card,
                ignore_readiness=ignore_readiness, payment_context=payment_context,
                reserved_card_ids=reserved_card_ids, protected_life=protected_life):
            for color, amount in bundle.items():
                outputs[color] = max(outputs.get(color, 0), amount)
        return outputs
    from rules_engine.mana import mana_activation_is_free
    from rules_engine.costs import activated_cost_available, parse_activated_cost
    outputs = {}
    for spec in mana_ability_specs(card, state):
        if not ignore_readiness and not source_ready(state, card, spec):
            continue
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
    from rules_engine.paid_triggers import resolution_mana_ability_allowed
    if printed_abilities_suppressed(state, card.id, include_land_types=False) or (not ignore_readiness and not source_ready(state, card)):
        return {}
    outputs = {}
    for spec in mana_ability_specs(card, state):
        if parse_activated_cost(spec[1]) == ActivatedCost(tap_source=True):
            if not resolution_mana_ability_allowed(state, card, spec):
                continue
            for color, bundle, _ in _output_options(state, card, spec, UNFILTERED):
                amount = bundle.get(color, 0)
                if amount > 0:
                    outputs[color] = max(outputs.get(color, 0), amount)
    return outputs


def paid_candidates(state, player_id, excluded_sources=(), *, payment_context=UNFILTERED, include_free=False):
    from rules_engine.costs import ActivatedCost, parse_activated_cost
    from rules_engine.mana import mana_activation_is_free
    bundled = needs_mana_bundles(state)
    for cid in state.players[player_id].battlefield:
        card = state.cards[cid]
        if cid in excluded_sources:
            continue
        for spec in mana_ability_specs(card, state):
            if (payment_context is not UNFILTERED and not eligible(ability_spending_rule(spec), payment_context)
                    and not has_additional_output(state, card, spec)):
                continue
            cost = parse_activated_cost(spec[1])
            if not source_ready(state, card, spec):
                continue
            tap_only = cost == ActivatedCost(mana_cost=cost.mana_cost, tap_source=True)
            self_sacrifice = cost.supported and cost.sacrifice_source
            changing_cost = cost.sacrifice_creatures or cost.discard_cards or cost.discard_source
            if not (tap_only or self_sacrifice or cost.supported and changing_cost):
                continue
            if not include_free and mana_activation_is_free(state, cid, cost.mana_cost) and not (bundled and changing_cost):
                continue
            for color, bundle, _ in _output_options(state, card, spec, payment_context):
                if sum(bundle.values()) > 0:
                    yield cid, spec, color


def activate_mana_ability(state, player_id, source_id, ability_index, color, *, payment_choices=None, hybrid_choices=None, output_bundle=None, excluded_sources=(), reserved_card_ids=(), protected_life=0):
    from rules_engine.mana_triggers import mana_tap_scope, resolve_mana_triggers
    card = state.cards.get(source_id)
    if card is None:
        return False
    with mana_tap_scope(state, card) as captured:
        result = _activate_mana_ability(state, player_id, source_id, ability_index, color,
            payment_choices=payment_choices, hybrid_choices=hybrid_choices, output_bundle=output_bundle,
            excluded_sources=excluded_sources, reserved_card_ids=reserved_card_ids, protected_life=protected_life)
    if result:
        resolve_mana_triggers(state, captured)
    return result


def _activate_mana_ability(state, player_id, source_id, ability_index, color, *, payment_choices=None, hybrid_choices=None, output_bundle=None, excluded_sources=(), reserved_card_ids=(), protected_life=0):
    from rules_engine.costs import ActivatedCost, parse_activated_cost, apply_activated_costs, activated_cost_selection
    from rules_engine.mana import auto_pay_cost, add_mana_to_pool
    card = state.cards.get(source_id)
    if card is None or card.controller != player_id or source_id not in state.players[player_id].battlefield:
        return False
    spec = next((row for row in mana_ability_specs(card, state) if row[0] == ability_index), None)
    if spec is None or not source_ready(state, card, spec):
        return False
    if output_bundle is not None and (not isinstance(output_bundle, dict)
            or not 1 <= len(output_bundle) <= 6
            or any(not isinstance(c, str) or len(c) != 1 or c not in 'WUBRGC'
                   or type(n) is not int or not 1 <= n <= 100000 for c, n in output_bundle.items())):
        return False
    raw = _raw_output_vectors(state, card, spec)
    choices = [i for i, base in enumerate(raw)
               if (color in _replace_base(state, card, spec, base) if output_bundle is None
                   else base == output_bundle and base.get(color, 0) > 0)]
    # Legacy color-only replacement selection may collapse equivalent base choices.
    unique = {tuple(sorted((_replace_base(state, card, spec, raw[i])
                           if output_bundle is None else raw[i]).items())) for i in choices}
    if len(unique) != 1:
        return False
    selected_index = choices[0]
    cost = parse_activated_cost(spec[1])
    if hybrid_choices is not None and (not isinstance(hybrid_choices, list)
            or any(not isinstance(choice, str) for choice in hybrid_choices)):
        return False
    if payment_choices is not None:
        if not isinstance(payment_choices, dict):
            return False
        # Explicit resource choices never fill in missing other-card selections.
        for key, count in [('discard_card_ids', cost.discard_cards),
                           ('sacrifice_card_ids', cost.sacrifice_creatures - int(cost.sacrifice_source))]:
            if count > 0 and not isinstance(payment_choices.get(key), list):
                return False
        if activated_cost_selection(state, player_id, source_id, cost,
                payment_choices, reserved_card_ids) is None:
            return False
    if cost == ActivatedCost(mana_cost=cost.mana_cost, tap_source=True):
        if not auto_pay_cost(state, player_id, cost.mana_cost, hybrid_choices=hybrid_choices, payment_kind='activation',
                payment_types=set(effective_types(state, card)), card_name=card.name,
                source_card_id=source_id, ability_kind='mana', ability_index=ability_index,
                excluded_sources=set(excluded_sources) | {source_id}, reserved_card_ids=reserved_card_ids, protected_life=protected_life):
            return False
        from rules_engine.resource_events import tap_permanents
        tap_permanents(state, [source_id])
    elif not apply_activated_costs(state, player_id, source_id, spec[1], hybrid_choices=hybrid_choices, payment_choices=payment_choices, ability_kind='mana', ability_index=ability_index, unavailable_resources=reserved_card_ids, protected_life=protected_life):
        return False
    # Amounts are determined after costs, including any resource departures.
    from rules_engine.events import _departed_card_view
    departed = _departed_card_view(state, source_id)
    current = _raw_output_vectors(state, departed, spec)
    if selected_index >= len(current):
        return False
    vector = _replace_base(state, departed, spec, current[selected_index])
    for component, amount in vector.items():
        add_mana_to_pool(state, player_id, component, amount, source_id=source_id, ability_effect=spec[2])
    state.log.append(f'{state.players[player_id].name} activates {card.name} for '
                     + ', '.join(f'{amount} {component}' for component, amount in vector.items()) + '.')
    return True


def activate_planned_mana_ability(state, player_id, source_id, ability_index, selector, **context):
    """Bind the planner's complete choice without inferring a manual selection."""
    card = state.cards[source_id]
    spec = next((s for s in mana_ability_specs(card, state) if s[0] == ability_index), None)
    if spec is None:
        return False
    choice = _base_choices(state, card, spec).get(selector)
    if choice is None:
        return False
    base, output = choice
    if not output:
        return False
    bundle = base if len(_raw_output_vectors(state, card, spec)) > 1 else None
    anchors = base if bundle is not None else output
    color = selector if selector in anchors else next(iter(anchors))
    return activate_mana_ability(state, player_id, source_id, ability_index, color,
        output_bundle=bundle, **context)


def _activation_choice_hints(state, card, spec):
    from rules_engine.costs import activated_cost_candidates, parse_activated_cost
    from rules_engine.mana import hybrid_payment_symbols
    cost = parse_activated_cost(spec[1])
    candidates = activated_cost_candidates(state, card.controller, card.id, cost)
    hybrid = hybrid_payment_symbols(cost.mana_cost)
    discard = max(0, candidates['discard_cards'] - len(candidates['fixed_discard_card_ids']))
    sacrifice = max(0, candidates['sacrifice_creatures'] - len(candidates['fixed_sacrifice_card_ids']))
    return {'activation_costs': candidates, 'hybrid_symbols': hybrid,
            'required_choices': {'payment_choices': bool(discard or sacrifice),
                'hybrid_choices': bool(hybrid), 'discard_card_count': discard,
                'sacrifice_card_count': sacrifice, 'hybrid_choice_count': len(hybrid)}}


def mana_ability_views(state, card):
    from rules_engine.costs import activated_cost_available
    return [{'ability_index': spec[0], 'cost_text': spec[1], 'outputs': outputs,
             **_activation_choice_hints(state, card, spec),
             'output_options': advertised_output_options(state, card, spec),
             'base_output_bundles': list({tuple(sorted(row['output_bundle'].items())):
                 row['output_bundle'] for row in advertised_output_options(state, card, spec)}.values()),
             **({'output_bundles': output_bundles(state, card, spec)}
                if has_additional_output(state, card, spec)
                or any(len(v) > 1 for v in base_output_options(state, card, spec).values())
                or (len(outputs) > 1 and any(n > 1 for n in outputs.values())) else {}),
             'label': f'{spec[1]}: {spec[2]}'}
            for spec in mana_ability_specs(card, state)
            if source_ready(state, card, spec) and (outputs := ability_outputs(state, card, spec))
            and activated_cost_available(state, card.controller, card.id, spec[1], ability_kind='mana', ability_index=spec[0])]


def has_additional_output(state, card, spec):
    from rules_engine.costs import parse_activated_cost
    from rules_engine.mana_triggers import fixed_mana_triggers
    return parse_activated_cost(spec[1]).tap_source and bool(fixed_mana_triggers(state, card))


def output_bundles(state, card, spec, *, payment_context=UNFILTERED):
    return {color: bundle for color, bundle, _ in _output_options(state, card, spec, payment_context)}


def _output_options(state, card, spec, payment_context):
    from rules_engine.costs import parse_activated_cost
    from rules_engine.mana_triggers import fixed_mana_triggers
    from rules_engine.mana import is_snow_source
    bonuses = fixed_mana_triggers(state, card) if parse_activated_cost(spec[1]).tap_source else []
    base_usable = payment_context is UNFILTERED or eligible(ability_spending_rule(spec), payment_context)
    result = []
    for color, vector in base_output_options(state, card, spec).items():
        bundle = dict(vector) if base_usable else {}
        snow = dict(vector) if base_usable and is_snow_source(card) else {}
        for pid, _, _, source_snow, outputs in bonuses:
            if pid != card.controller:
                continue
            for extra_color, extra in outputs.items():
                bundle[extra_color] = bundle.get(extra_color, 0) + extra
                if source_snow:
                    snow[extra_color] = snow.get(extra_color, 0) + extra
        result.append((color, bundle, snow))
    return result


def free_mana_options(state, card, *, ignore_readiness=False, payment_context=UNFILTERED,
                      reserved_card_ids=(), protected_life=0):
    from rules_engine.costs import activated_cost_available, parse_activated_cost
    from rules_engine.mana import mana_activation_is_free
    options = []
    for spec in mana_ability_specs(card, state):
        cost = parse_activated_cost(spec[1])
        if not ignore_readiness and not source_ready(state, card, spec):
            continue
        if not cost.supported or not mana_activation_is_free(state, card.id, cost.mana_cost):
            continue
        if (not ignore_readiness or reserved_card_ids or protected_life) and not activated_cost_available(
                state, card.controller, card.id, spec[1], ability_kind='mana', ability_index=spec[0],
                unavailable_resources=reserved_card_ids, protected_life=protected_life):
            continue
        for color, bundle, snow in _output_options(state, card, spec, payment_context):
            if sum(bundle.values()) > 0:
                options.append((spec, color, bundle, snow, cost.pay_life))
    return options


def preferred_free_spec(state, card, color, amount, *, payment_context=UNFILTERED, tap_only=False, reserved_card_ids=(), protected_life=0):
    """Preserve the selected ability's rule; prefer unrestricted tied outputs."""
    from rules_engine.costs import ActivatedCost, parse_activated_cost, activated_cost_available
    from rules_engine.mana import mana_activation_is_free
    candidates = []
    for spec in mana_ability_specs(card, state):
        cost = parse_activated_cost(spec[1])
        if not source_ready(state, card, spec):
            continue
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
        if output_bundles(state, card, spec).get(color, {}).get(color) == amount:
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
