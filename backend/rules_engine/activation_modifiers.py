"""Source-bound generic activation changes, shared by hints and payment."""
import re
from functools import lru_cache

from game_state.state import Zone

FLOOR = "this effect can't reduce the mana in that cost to less than one mana"


@lru_cache(maxsize=2048)
def parse_activation_modifier(clause, card_name=''):
    match = re.fullmatch(r"(.+) cost \{(\d+)\} (more|less) to activate( unless they're mana abilities)?", clause)
    if not match:
        return None
    head, amount, direction, exception = match.groups()
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
    return {'amount': int(amount), 'increase': direction == 'more', 'scope': scope,
            'subject': subject, 'nonmana': nonmana}


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
    return [clause for index, clause in enumerate(clauses)
            if re.search(r'(?:activated abilities|abilities you activate).*cost.*to activate', clause)
            and (parse_activation_modifier(clause, card_name) is None or
                 index+1 < len(clauses) and clauses[index+1].startswith("this effect can't reduce") and clauses[index+1] != FLOOR)]


def apply_activation_modifiers(context):
    if context.state is None or context.is_spell or context.ability_kind is None:
        return context
    state = context.state
    recipient = state.cards.get(context.source_card_id)
    if recipient is None:
        return context
    from rules_engine.continuous import printed_abilities_suppressed, _printed_ability_loss_sources
    from rules_engine.combat_constraints import _recipient_body
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
            if spec['increase']:
                context.generic_increase += spec['amount']
            elif spec['floor']:
                context.floored_reductions.append((spec['floor'], spec['amount']))
            else:
                context.generic_reduction += spec['amount']
    return context


def activation_cost_view(state, player_id, source_id, mana_cost, *, ability_kind='activated', x_value=0):
    from rules_engine.hooks import CostContext, apply_cost_modifiers
    from rules_engine.mana import _payment_requirements
    source = state.cards[source_id]
    context = apply_cost_modifiers(CostContext(state=state, player_id=player_id,
        card_name=source.name, mana_cost=mana_cost, is_spell=False,
        source_card_id=source_id, ability_kind=ability_kind))
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
                payment_types=set(state.cards[vehicle_id].types),
                source_card_id=vehicle_id, ability_kind='crew', excluded_sources=set(selected)):
            continue
        if power >= required:
            return selected
        if index < len(ordered):
            stack.append((index+1, power, selected))
            stack.append((index+1, power+powers[index], selected+[ordered[index]]))
    return None
