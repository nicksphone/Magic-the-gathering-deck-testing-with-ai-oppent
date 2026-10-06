"""Explicit non-mana substitutions against a locked total casting cost.

This layer neither authorizes casting nor activates mana abilities. The casting
transaction must reserve these objects before producing and spending mana.
"""
from dataclasses import dataclass

from game_state.state import Zone
from rules_engine.colors import card_color_symbols
from rules_engine.oracle_text import without_reminder_text
from rules_engine.type_effects import effective_types
from rules_engine.zone_actions import is_departed_token


KEYWORDS = frozenset({'delve', 'convoke', 'improvise'})
COLORS = 'WUBRG'


def resource_keywords(card):
    printed = {str(keyword).lower() for keyword in getattr(card, 'keywords', [])}
    text = getattr(card, 'oracle_text', '') or ''
    if not KEYWORDS.intersection(printed) and not any(keyword in text.lower() for keyword in KEYWORDS):
        return frozenset()
    lines = set()
    for line in without_reminder_text(text).splitlines():
        parts = {part.strip().lower() for part in line.split(',')}
        if parts <= KEYWORDS:
            lines.update(parts)
    return KEYWORDS.intersection(printed | lines)


def resource_candidates(state, player_id, card):
    player = state.players[player_id]
    enabled = resource_keywords(card)
    result = {'delve': [], 'convoke': [], 'improvise': []}
    if 'delve' in enabled:
        result['delve'] = [cid for cid in player.graveyard if cid != card.id
                           and state.cards[cid].zone == Zone.GRAVEYARD
                           and state.cards[cid].owner == player_id
                           and not is_departed_token(state.cards[cid])]
    for cid in player.battlefield:
        permanent = state.cards[cid]
        if permanent.zone != Zone.BATTLEFIELD or permanent.controller != player_id or permanent.tapped:
            continue
        types = effective_types(state, permanent)
        if 'convoke' in enabled and 'Creature' in types:
            colors = card_color_symbols(permanent)
            result['convoke'].append({'card_id': cid, 'pay_as': ['generic', *[c for c in COLORS if c in colors]]})
        if 'improvise' in enabled and 'Artifact' in types:
            result['improvise'].append(cid)
    return result


@dataclass(frozen=True)
class ResourcePayment:
    source_card_id: str
    requirements: tuple
    remaining_items: tuple
    delve: tuple[str, ...]
    convoke: tuple[tuple[str, str], ...]
    improvise: tuple[str, ...]

    @property
    def remaining(self):
        return dict(self.remaining_items)

    def choice(self):
        return {'delve': list(self.delve), 'convoke': [
            {'card_id': cid, 'pay_as': color} for cid, color in self.convoke],
            'improvise': list(self.improvise)}


def resource_payment(state, player_id, card, requirements, choices, *,
                     reserved_card_ids=(), unavailable_tap_ids=(), reserved_consumption_ids=()):
    """Pure validation: substitutions never become mana or change mana value."""
    if (player_id not in state.players or not isinstance(choices, dict)
            or set(choices) - KEYWORDS or not isinstance(requirements, dict)
            or set(requirements) - {'generic', 'W', 'U', 'B', 'R', 'G', 'C', 'S', 'life'}
            or any(type(n) is not int or n < 0 for n in requirements.values())):
        return None
    selected = {keyword: choices.get(keyword, []) for keyword in KEYWORDS}
    if any(not isinstance(ids, list) for ids in selected.values()):
        return None
    if any(not isinstance(cid, str) for keyword in ('delve', 'improvise') for cid in selected[keyword]):
        return None
    if any(not isinstance(row, dict) or set(row) != {'card_id', 'pay_as'}
           or not isinstance(row['card_id'], str) or not isinstance(row['pay_as'], str)
           or row['pay_as'] not in {'generic', *COLORS}
           for row in selected['convoke']):
        return None
    candidates = resource_candidates(state, player_id, card)
    creature_colors = {row['card_id']: row['pay_as'] for row in candidates['convoke']}
    delve = selected['delve']
    improvise = selected['improvise']
    convoke = [(row['card_id'], row['pay_as']) for row in selected['convoke']]
    all_ids = [*delve, *improvise, *[cid for cid, _ in convoke]]
    if (len(all_ids) != len(set(all_ids)) or card.id in all_ids
            or set(all_ids).intersection(reserved_card_ids)
            or set(delve).intersection(reserved_consumption_ids)
            or set(improvise + [cid for cid, _ in convoke]).intersection(unavailable_tap_ids)
            or any(cid not in candidates['delve'] for cid in delve)
            or any(cid not in candidates['improvise'] for cid in improvise)
            or any(color not in creature_colors.get(cid, []) for cid, color in convoke)):
        return None
    remaining = dict(requirements)
    for key in [*[color for _, color in convoke], *['generic'] * (len(delve) + len(improvise))]:
        if remaining.get(key, 0) <= 0:
            return None
        remaining[key] -= 1
    return ResourcePayment(card.id, tuple(requirements.items()), tuple(remaining.items()),
                           tuple(delve), tuple(convoke), tuple(improvise))


def apply_resource_payment(state, player_id, card, plan):
    """Revalidate all objects before the first tap or exile, including stale plans."""
    if not isinstance(plan, ResourcePayment) or plan.source_card_id != card.id:
        return False
    current = resource_payment(state, player_id, card, dict(plan.requirements), plan.choice())
    if current != plan:
        return False
    player = state.players[player_id]
    from rules_engine.resource_events import tap_permanents
    tap_permanents(state, [cid for cid, _ in plan.convoke] + list(plan.improvise))
    for cid, _ in plan.convoke:
        state.log.append(f'{player.name} convokes with {state.cards[cid].name}.')
    for cid in plan.improvise:
        state.log.append(f'{player.name} improvises with {state.cards[cid].name}.')
    from rules_engine.resource_events import capture_graveyard_departures, emit_graveyard_departures
    departures = capture_graveyard_departures(state, plan.delve)
    for cid in plan.delve:
        player.graveyard.remove(cid)
        player.exile.append(cid)
        state.cards[cid].move_to_zone(Zone.EXILE)
        state.log.append(f'{player.name} delves {state.cards[cid].name}.')
    emit_graveyard_departures(state, departures)
    return True


def joint_resource_payment(state, player_id, card, requirements, choices, mana_planner, *,
                           reserved_consumption_ids=()):
    """Find a legal witness; this is not an AI opportunity-cost evaluator.

The callback excludes selected taps from mana sources and reserves all selected
    objects against consuming mana abilities. No branch mutates the game.
    """
    reserved_consumption_ids = frozenset(reserved_consumption_ids)

    def validate(selected):
        return resource_payment(state, player_id, card, requirements, selected,
                                reserved_consumption_ids=reserved_consumption_ids)

    def physical(plan):
        tapped = {cid for cid, _ in plan.convoke} | set(plan.improvise)
        held = tapped | set(plan.delve)
        return mana_planner(plan.remaining, tapped, held)

    if choices is not None:
        plan = validate(choices)
        if plan is None:
            return None
        mana = physical(plan)
        return (plan.remaining, plan, mana) if mana is not None else None
    candidates = resource_candidates(state, player_id, card)
    alternatives = {}
    for row in candidates['convoke']:
        alternatives.setdefault(row['card_id'], []).extend(
            ('convoke', color) for color in row['pay_as'] if color != 'generic')
        alternatives[row['card_id']].append(('convoke', 'generic'))
    for keyword in ('delve', 'improvise'):
        for cid in candidates[keyword]:
            if keyword == 'delve' and cid in reserved_consumption_ids:
                continue
            alternatives.setdefault(cid, []).append((keyword, 'generic'))
    objects = list(alternatives.items())

    def search(index, selected):
        plan = validate(selected)
        if plan is None:
            return None
        mana = physical(plan)
        if mana is not None:
            return plan.remaining, plan, mana
        if index == len(objects):
            return None
        # An optimistic bound may double-count alternatives; failure still
        # proves impossibility and avoids exponential missing-color searches.
        optimistic = plan.remaining
        for _, options in objects[index:]:
            for _, color in options:
                optimistic[color] = max(0, optimistic.get(color, 0) - 1)
        tapped = {cid for cid, _ in plan.convoke} | set(plan.improvise)
        if mana_planner(optimistic, tapped, tapped | set(plan.delve)) is None:
            return None
        cid, options = objects[index]
        for keyword, color in options:
            if plan.remaining.get(color, 0):
                value = {'card_id': cid, 'pay_as': color} if keyword == 'convoke' else cid
                branch = {key: list(values) for key, values in selected.items()}
                branch.setdefault(keyword, []).append(value)
                result = search(index + 1, branch)
                if result is not None:
                    return result
        return search(index + 1, selected)

    return search(0, {})
