"""Source-bound generic activation changes, shared by hints and payment."""
from rules_engine.type_effects import effective_types
import re
from functools import lru_cache

from game_state.state import Zone

FLOOR = "this effect can't reduce the mana in that cost to less than one mana"


@lru_cache(maxsize=2048)
def ability_cost_modifier(text):
    match = re.search(r"\bthis ability costs \{(\d+)\} less to activate (.+?)\.$", text.lower().strip())
    if not match:
        return None
    bases = {
        'for each other artifact you control': 'other_artifacts',
        'for each creature card in your graveyard': 'graveyard_creatures',
        'for each +1/+1 counter on creatures you control': 'creature_counters',
        'if you control a legendary creature': 'legendary_creature',
        'for each legendary creature you control': 'legendary_creatures',
        'if you control a creature with a +1/+1 counter on it': 'counter_creature',
        'during your turn': 'controller_turn',
    }
    basis = bases.get(match[2])
    if basis is None or 'this ability costs' in text[:match.start()].lower():
        return None
    return {'amount': int(match[1]), 'basis': basis, 'effect_text': text[:match.start()].strip()}


def ability_cost_reduction(state, source, spec):
    player = state.players[source.controller]
    creatures = [state.cards[cid] for cid in player.battlefield
                 if state.cards[cid].zone == Zone.BATTLEFIELD and 'Creature' in effective_types(state, state.cards[cid])]
    basis = spec['basis']
    if basis == 'other_artifacts':
        units = sum(cid != source.id and state.cards[cid].zone == Zone.BATTLEFIELD
                    and 'Artifact' in effective_types(state, state.cards[cid]) for cid in player.battlefield)
    elif basis == 'graveyard_creatures':
        units = sum(state.cards[cid].zone == Zone.GRAVEYARD and 'Creature' in effective_types(state, state.cards[cid])
                    and not state.cards[cid].is_token for cid in player.graveyard)
    elif basis == 'creature_counters':
        units = sum(max(0, card.counters.get('+1/+1', 0)) for card in creatures)
    elif basis == 'legendary_creature':
        units = any('Legendary' in (card.type_line or '').split() for card in creatures)
    elif basis == 'legendary_creatures':
        units = sum('Legendary' in (card.type_line or '').split() for card in creatures)
    elif basis == 'counter_creature':
        units = any(card.counters.get('+1/+1', 0) > 0 for card in creatures)
    elif basis == 'controller_turn':
        units = state.active_player == source.controller
    else:
        raise AssertionError(f'Unhandled activation discount: {basis}')
    return units * spec['amount']


@lru_cache(maxsize=2048)
def parse_activation_modifier(clause, card_name=''):
    power = re.fullmatch(r"(.+), where x is (.+)'s power", clause)
    if power:
        reference = power[2]
        name = card_name.lower()
        if not name or not (name == reference or name.startswith(reference + ' ') or name.startswith(reference + ',')):
            return None
        clause = power[1]
    match = re.fullmatch(r"(.+) cost \{(\d+|x)\} (more|less) to activate( unless they're mana abilities)?", clause)
    if not match:
        return None
    head, amount, direction, exception = match.groups()
    if (amount == 'x') != bool(power) or power and direction != 'less':
        return None
    scope, subject, nonmana = 'all', None, bool(exception)
    if head == 'activated abilities':
        pass
    elif head in {"abilities you activate", "abilities you activate that aren't mana abilities"}:
        scope, nonmana = 'controller', bool(exception) or "aren't mana abilities" in head
    else:
        recipient = re.fullmatch(r'activated abilities of (.+)', head)
        possessive = re.fullmatch(r"(.+)'s activated abilities", head)
        subject = recipient[1] if recipient else possessive[1] if possessive else None
        from rules_engine.combat_constraints import _supported_combat_subject
        if subject is None or not _supported_combat_subject(subject, card_name):
            return None
    return {'amount': 'source_power' if power else int(amount), 'increase': direction == 'more', 'scope': scope,
            'subject': subject, 'nonmana': nonmana}


@lru_cache(maxsize=2048)
def turn_cost_taxes(oracle):
    """Recognize a complete paired spell/ability tax, not fragments of triggers."""
    from rules_engine.oracle_text import without_reminder_text
    for line in without_reminder_text(oracle or '').lower().splitlines():
        match = re.fullmatch(
            r"during your turn, spells your opponents cast cost \{(\d+)\} more to cast "
            r"and abilities your opponents activate cost \{(\d+)\} more to activate"
            r"( unless they're mana abilities)?\.?", line.strip())
        if match:
            return int(match[1]), int(match[2]), bool(match[3])
    return None


def modifier_specs(oracle, card_name=''):
    from rules_engine.combat_constraints import static_clauses
    clauses = static_clauses(oracle)
    for index, clause in enumerate(clauses):
        spec = parse_activation_modifier(clause, card_name)
        if spec:
            if index+1 < len(clauses) and clauses[index+1].startswith("this effect can't reduce") and clauses[index+1] != FLOOR:
                continue
            yield {**spec, 'clause': clause, 'floor': 1 if not spec['increase']
                   and index+1 < len(clauses) and clauses[index+1] == FLOOR else 0}


def activation_modifier_gaps(oracle, card_name=''):
    from rules_engine.combat_constraints import static_clauses
    clauses = static_clauses(oracle)
    gaps = [clause for index, clause in enumerate(clauses)
            if re.search(r'(?:activated abilities|abilities you activate).*cost.*to activate', clause)
            and (parse_activation_modifier(clause, card_name) is None or
                 index+1 < len(clauses) and clauses[index+1].startswith("this effect can't reduce") and clauses[index+1] != FLOOR)]
    from rules_engine.oracle_text import without_reminder_text
    for line in without_reminder_text(oracle or '').lower().splitlines():
        if 'cost' in line and 'to activate' in line and (
                line.startswith('during ') and turn_cost_taxes(line) is None or
                'this ability costs' in line and (':' not in line or
                    ability_cost_modifier(line.split(':', 1)[1].strip()) is None or
                    'add ' in line.split(':', 1)[1])):
            gaps.append(line)
    return gaps


def apply_activation_modifiers(context):
    if context.state is None or context.is_spell or context.ability_kind is None:
        return context
    state = context.state
    recipient = state.cards.get(context.source_card_id)
    if recipient is None:
        return context
    from rules_engine.continuous import printed_abilities_suppressed, _printed_ability_loss_sources
    from rules_engine.combat_constraints import _recipient_body
    from rules_engine.continuous import effective_power
    if context.ability_kind == 'activated' and context.ability_index is not None:
        from rules_engine.oracle_effects import extract_activated_abilities
        ability = next((item for item in extract_activated_abilities(recipient)
                        if item['index'] == context.ability_index), None)
        if (ability and ability.get('cost_modifier') and recipient.controller == context.player_id
                and not printed_abilities_suppressed(state, recipient.id)):
            context.generic_reduction += ability_cost_reduction(state, recipient, ability['cost_modifier'])
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards[cid]
            taxes = turn_cost_taxes(getattr(source, 'oracle_text', '') or '')
            if (taxes and source.zone == Zone.BATTLEFIELD and state.active_player == source.controller
                    and context.player_id != source.controller
                    and not (taxes[2] and context.ability_kind == 'mana')
                    and not printed_abilities_suppressed(state, cid)):
                context.generic_increase += taxes[1]
    sources = [(state.cards[cid], tuple(modifier_specs(state.cards[cid].oracle_text, state.cards[cid].name)))
               for player in state.players.values() for cid in player.battlefield
               if 'to activate' in getattr(state.cards[cid], 'oracle_text', '').lower()
               and state.cards[cid].zone == Zone.BATTLEFIELD]
    sources = [(source, specs) for source, specs in sources if specs]
    if not sources:
        return context
    losses = _printed_ability_loss_sources(state)
    for source, specs in sources:
        if printed_abilities_suppressed(state, source.id, losses=losses):
            continue
        for spec in specs:
            if spec['nonmana'] and context.ability_kind == 'mana':
                continue
            if spec['scope'] == 'controller' and source.controller != context.player_id:
                continue
            if spec['subject'] and (recipient.zone != Zone.BATTLEFIELD or _recipient_body(
                    state, source, recipient, f"{spec['subject']} can't attack") is None):
                continue
            amount = max(0, effective_power(state, source.id)) if spec['amount'] == 'source_power' else spec['amount']
            if spec['increase']:
                context.generic_increase += amount
            elif spec['floor']:
                context.floored_reductions.append((spec['floor'], amount))
            else:
                context.generic_reduction += amount
    return context


def activation_cost_view(state, player_id, source_id, mana_cost, *, ability_kind='activated', x_value=0, ability_index=None):
    from rules_engine.hooks import CostContext, apply_cost_modifiers
    from rules_engine.mana import _payment_requirements
    source = state.cards[source_id]
    context = apply_cost_modifiers(CostContext(state=state, player_id=player_id,
        card_name=source.name, mana_cost=mana_cost, is_spell=False,
        source_card_id=source_id, ability_kind=ability_kind, ability_index=ability_index))
    return {'printed_mana_cost': mana_cost, 'generic_increase': context.generic_increase,
            'generic_reduction': context.generic_reduction, 'floored_reductions': context.floored_reductions,
            'requirements': _payment_requirements(mana_cost, False, x_value, context.generic_reduction,
                context.generic_increase, floored_reductions=context.floored_reductions)}


def payable_crew_group(state, player_id, vehicle_id, required, candidates):
    from rules_engine.continuous import effective_power
    from rules_engine.mana import can_pay_with_pool_and_lands
    ordered = sorted(candidates, key=lambda cid: (-effective_power(state, cid), cid))
    powers = [max(0, effective_power(state, cid)) for cid in ordered]
    tails = [sum(powers[index:]) for index in range(len(powers)+1)]
    stack = [(0, 0, [])]
    while stack:
        index, power, selected = stack.pop()
        if power+tails[index] < required:
            continue
        if not can_pay_with_pool_and_lands(state, player_id, '', payment_kind='activation',
                payment_types=set(effective_types(state, state.cards[vehicle_id])),
                source_card_id=vehicle_id, ability_kind='crew', excluded_sources=set(selected)):
            continue
        if power >= required:
            return selected
        if index < len(ordered):
            stack.append((index+1, power, selected))
            stack.append((index+1, power+powers[index], selected+[ordered[index]]))
    return None
