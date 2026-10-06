"""Bounded ordered counter allocations with explicitly different recipients."""
import re

from rules_engine.oracle_text import without_reminder_text
from rules_engine.spell_cost_clauses import NUMBERS


def ordered_counter_allocations(text):
    clauses = re.split(r',\s*(?:and\s+)?', without_reminder_text(text).lower().strip().rstrip('.'))
    if len(clauses) < 2:
        return None
    amounts = []
    counter = None
    ordinals = ['second', 'third', 'fourth', 'fifth', 'sixth']
    for index, clause in enumerate(clauses):
        recipient = 'target creature' if index == 0 else (
            '(?:another target creature|a second target creature)' if index == 1
            else 'a ' + ordinals[index-1] + ' target creature' if index <= len(ordinals) else '')
        if not recipient:
            return None
        match = re.fullmatch(('put ' if index == 0 else '')
                             + r'(a|an|one|two|three|four|five|six|\d+) ([+-]\d+/[+-]\d+) counters? on '
                             + recipient, clause)
        if match is None or counter is not None and counter != match[2]:
            return None
        counter = match[2]
        amount = int(match[1]) if match[1].isdigit() else 1 if match[1] in {'a', 'an'} else NUMBERS[match[1]]
        amounts.append(amount)
    return {'amounts': amounts, 'counter': counter}


def ordered_creature_modifiers(text):
    """Separate P/T targeting instances; recipients need not be distinct."""
    from rules_engine.oracle_effects import parse_temporary_target_buff
    clauses = [clause.strip() for clause in re.split(r'[.\n]', without_reminder_text(text).lower())
               if clause.strip()]
    if len(clauses) < 2:
        return None
    modifiers = [parse_temporary_target_buff(clause) for clause in clauses]
    if any(not clause.startswith('target creature gets ') or modifier is None
           or modifier['keywords'] for clause, modifier in zip(clauses, modifiers)):
        return None
    return modifiers


def _copy_candidates(state, copied, index):
    from game_state.state import object_incarnation
    from rules_engine.oracle_effects import inspect_target_hints
    from rules_engine.targeting import (stack_source_card, validate_cast_targets,
                                       validate_hexproof_shroud_targets, validate_protection_targets)
    card = stack_source_card(state, copied)
    if card is None:
        return {}
    hints = inspect_target_hints(state, card, copied.controller, copied.payload.get('__announced_targets') or {})
    hints.pop('required_distinct_target_count', None)
    hints.pop('required_target_instance_count', None)
    packet = copied.payload['effects'][index]['payload']
    candidates = {}
    for candidate in hints.get('creature_targets', []):
        cid = candidate['id']
        selected = {'target_card_id': cid}
        if (validate_cast_targets(hints, selected)[0]
                and validate_hexproof_shroud_targets(state, copied.controller, selected, card)[0]
                and validate_protection_targets(state, card, selected)[0]):
            target = state.cards[cid]
            unchanged = (cid == packet['target_card_id']
                         and object_incarnation(target) == packet['__target_incarnation']
                         and target.zone_change_sequence == packet['__target_zone_sequence'])
            if not unchanged:
                candidates[cid] = candidate.get('name') or cid
    return candidates


def _distinct_copy_can_finish(state, copied, index, cid):
    """Allow swaps, but never offer a prefix with no legal completion."""
    if not copied.payload.get('__ordered_distinct_targets'):
        return True
    ids = copied.payload['__announced_targets']['target_card_ids']
    prefix = set(ids[:index])
    if cid in prefix:
        return False
    prefix.add(cid)
    # Matching permits keeping an old illegal target, not selecting it anew.
    slots = {slot: ({ids[slot]} | set(_copy_candidates(state, copied, slot))) - prefix
             for slot in range(index+1, len(ids))}
    assigned = {}
    def match(slot, seen):
        for candidate in sorted(slots[slot]):
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate not in assigned or match(assigned[candidate], seen):
                assigned[candidate] = slot
                return True
        return False
    return all(match(slot, set()) for slot in slots)


def offer_ordered_copy_target_choice(state, copied, index=0):
    ids = (copied.payload.get('__announced_targets') or {}).get('target_card_ids') or []
    effects = copied.payload.get('effects') or []
    if not ids or len(ids) != len(effects):
        return
    for slot in range(index, len(ids)):
        options = ['keep'] if _distinct_copy_can_finish(state, copied, slot, ids[slot]) else []
        labels = {'keep': f'Keep {state.cards[ids[slot]].name if ids[slot] in state.cards else ids[slot]}'}
        for cid, name in _copy_candidates(state, copied, slot).items():
            if _distinct_copy_can_finish(state, copied, slot, cid):
                option = f'target_card_id:{cid}'
                options.append(option)
                labels[option] = name
        if options != ['keep']:
            state.pending_mechanic_choice = {
                'kind': 'copy_target', 'player_id': copied.controller, 'count': 1,
                'stack_id': copied.id, 'ordered_target_index': slot,
                'target_slot_number': slot+1, 'options': options, 'option_labels': labels,
                'label': f'Choose target {slot+1} for {copied.label} or keep its target',
            }
            return


def choose_ordered_copy_target(state, copied, pending, chosen):
    from game_state.state import object_incarnation
    index = pending['ordered_target_index']
    ids = copied.payload['__announced_targets']['target_card_ids']
    if index >= len(ids):
        return False
    cid = ids[index] if chosen == 'keep' else chosen.removeprefix('target_card_id:')
    if (chosen != 'keep' and cid not in _copy_candidates(state, copied, index)
            or not _distinct_copy_can_finish(state, copied, index, cid)):
        return False
    if chosen != 'keep':
        target = state.cards[cid]
        packet = copied.payload['effects'][index]['payload']
        packet.update(target_card_id=cid, __target_incarnation=object_incarnation(target),
                      __target_zone_sequence=target.zone_change_sequence)
        ids[index] = cid
        if '__announced_target_references' in copied.payload:
            from rules_engine.targeting import replace_announced_target_reference
            copied.payload['__announced_target_references'] = replace_announced_target_reference(
                state, copied.payload['__announced_target_references'],
                copied.payload['__announced_targets'], [('target_card_ids', index)])
        copied.targets = list(ids)
        state.log.append(f'{state.players[copied.controller].name} changes a target of {copied.label}.')
    state.pending_mechanic_choice = None
    offer_ordered_copy_target_choice(state, copied, index+1)
    return True
