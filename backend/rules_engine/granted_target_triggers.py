"""Closed raw quoted target-trigger grants; no card-name dispatch or state writes."""
import re
import json
from copy import deepcopy
from functools import lru_cache


_GRANT = re.compile(
    r'(All )?(Other )?(Creatures)(?: (you control|your opponents control))? have "([^"]+)"\.?',
    re.IGNORECASE,
)
_TRIGGER = re.compile(
    r'Whenever this creature becomes the target of a (spell or ability|spell|ability), (.+)',
    re.IGNORECASE,
)
_LIMIT = re.compile(r' This ability triggers only (once|twice|three times|four times|\d+ times) each turn\.$', re.IGNORECASE)
_REVEAL = re.compile(
    r"reveal the top card of your library\. If (?:it's|it is) (?:a|an) "
    r'(land|creature|artifact|enchantment|planeswalker) card, put it (onto the battlefield|into your hand)\. '
    r'Otherwise, put it into your hand\.', re.IGNORECASE,
)


@lru_cache(maxsize=1024)
def compile_granted_target_clauses(raw, source_name=''):
    """Return immutable (clauses, gaps); an unknown full-body line closes admission."""
    from rules_engine.continuous import _attached_keywords
    clauses, gaps = [], []
    for index, line in enumerate(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        grant = _GRANT.fullmatch(line)
        if grant is None:
            if _attached_keywords(line.lower().rstrip('.')) is None:
                gaps.append((index, line, 'unsupported full-body line'))
            continue
        trigger = _TRIGGER.fullmatch(grant[5])
        if trigger is None:
            gaps.append((index, line, 'unsupported granted trigger'))
            continue
        instruction = trigger[2]
        limit_match = _LIMIT.search(instruction)
        limit = None
        if limit_match:
            amount = limit_match[1].lower()
            limit = {'once': 1, 'twice': 2, 'three times': 3, 'four times': 4}.get(amount)
            if limit is None:
                limit = int(amount.split()[0])
            instruction = instruction[:limit_match.start()]
        effect = _REVEAL.fullmatch(instruction)
        if effect is None or limit == 0:
            gaps.append((index, line, 'unsupported complete granted instruction or limit'))
            continue
        scope = (grant[4] or 'all').lower()
        destination = 'battlefield' if effect[2].lower() == 'onto the battlefield' else 'hand'
        # Receipt tuple: clause ordinal, scope, other-only, event kind, limit, typed instruction.
        clauses.append((index, scope, bool(grant[2]), trigger[1].lower(), limit,
                        (effect[1].title(), destination, 'hand')))
    return tuple(clauses) if not gaps else (), tuple(gaps)


def execution_gaps(clauses):
    """Syntax descriptors are not permission to bypass unimplemented entry paths."""
    return tuple((clause[0], 'unqualified nonland battlefield entry') for clause in clauses
                 if clause[-1][1] == 'battlefield' and clause[-1][0] != 'Land')


def _reference(card):
    from game_state.state import object_incarnation
    return {'card_id': card.id, 'incarnation': object_incarnation(card),
            'zone_change_sequence': card.zone_change_sequence}


def _reference_key(reference):
    return (reference['card_id'], reference['incarnation'], reference['zone_change_sequence'])


def _reference_leaves(node):
    if isinstance(node, dict):
        if set(node) == {'card_id', 'incarnation', 'zone_change_sequence'}:
            yield node
        else:
            for value in node.values():
                yield from _reference_leaves(value)
    elif isinstance(node, list):
        for value in node:
            yield from _reference_leaves(value)


def _recipient_lki(state, card):
    from rules_engine.continuous import effective_keyword_counts, effective_power, effective_toughness
    from rules_engine.type_effects import effective_types
    from rules_engine.colors import card_color_names, card_color_symbols
    return {'name': card.name, 'oracle_text': card.oracle_text, 'controller': card.controller,
            'types': list(effective_types(state, card)), 'power': effective_power(state, card.id),
            'toughness': effective_toughness(state, card.id), 'loyalty': card.loyalty,
            'keyword_counts': effective_keyword_counts(state, card.id),
            'keywords': list(effective_keyword_counts(state, card.id)),
            'counters': dict(card.counters), 'colors': sorted(card_color_symbols(card, state)),
            'color_names': sorted(card_color_names(card, state)),
            'battlefield_incarnation': _reference(card)['incarnation'],
            'zone_change_sequence': card.zone_change_sequence,
            'effect_timestamp': card.effect_timestamp, 'was_kicked': card.was_kicked}


def _capture_grants(state, announced, references, *, stack_kind, previous_refs=()):
    """Pure PRE receipt; empty is authoritative and never a request to recapture."""
    from game_state.state import Zone
    from rules_engine.targeting import validate_announced_target_references
    from rules_engine.continuous import effective_granted_target_abilities
    validate_announced_target_references(announced, references)
    refs = {_reference_key(ref): ref for ref in _reference_leaves(references['targets'])}
    previous = {_reference_key(ref) for ref in previous_refs}
    receipts = []
    for key, reference in sorted(refs.items()):
        card = state.cards.get(key[0])
        if key in previous or card is None or card.zone != Zone.BATTLEFIELD or _reference(card) != reference:
            continue
        for grant in effective_granted_target_abilities(state, card.id):
            kind = 'spell' if stack_kind == 'spell' else 'ability'
            if grant['event_kind'] not in (kind, 'spell or ability'):
                continue
            source = state.cards[grant['grant_source_id']]
            receipts.append({'recipient_ref': reference, 'grant_source_ref': _reference(source),
                             'clause_instance': grant['clause_index'], 'trigger_controller': card.controller,
                             'recipient_source_lki': _recipient_lki(state, card),
                             'compiled_instruction': list(grant['instruction']),
                             'trigger_limit': grant['limit'], 'targeting_occurrence': None})
    return deepcopy({'status': 'captured', 'captured': True,
                     'target_refs': [refs[k] for k in sorted(refs)], 'receipts': receipts})


def _record_target_selection(state, item):
    """Actual no-cost copy/trigger target producer, not a resolution-scan fallback."""
    from rules_engine.targeting import capture_announced_target_references, stack_object_kind
    announced = item.payload.get('__announced_targets')
    if announced is None:
        announced = {key: item.payload[key] for key in ('target_card_id', 'target_player')
                     if item.payload.get(key) is not None}
    references = item.payload.get('__announced_target_references')
    if references is None:
        # Kept legacy copy targets have no recoverable identity: do not refresh them.
        if item.payload.get('__stack_copy_kind'):
            item.payload['__granted_target_capture'] = {
                'status': 'unqualified', 'captured': False,
                'reason': 'legacy_target_identity_missing'}
            return
        references = capture_announced_target_references(state, announced)
    previous = item.payload.get('__granted_target_membership', [])
    capture = _capture_grants(state, announced, references, stack_kind=stack_object_kind(state, item),
                              previous_refs=previous)
    item.payload['__announced_targets'] = deepcopy(announced)
    item.payload['__announced_target_references'] = deepcopy(references)
    if '__granted_target_membership' in item.payload and capture['target_refs'] == previous:
        return
    item.payload['__granted_target_capture'] = capture


def _publish_grants(state, item):
    """Commit occurrence/slots before APNAP or recursion; never re-query frozen receipts."""
    if '__granted_target_capture' not in item.payload:
        item.payload['__granted_target_capture'] = {
            'status': 'unqualified', 'captured': False, 'reason': 'missing_capture'}
        return []
    capture = item.payload['__granted_target_capture']
    if not isinstance(capture, dict):
        raise ValueError('Malformed granted target receipt')
    if capture.get('status') == 'unqualified':
        if (capture.get('captured') is not False or capture.get('reason') not in
                {'missing_capture', 'legacy_target_identity_missing'}):
            raise ValueError('Malformed unqualified granted target receipt')
        return []
    if capture.get('captured') is not True:
        raise ValueError('Uncaptured granted target receipt')
    if (capture.get('status', 'captured') != 'captured'
            or not isinstance(capture.get('target_refs'), list)
            or not isinstance(capture.get('receipts'), list)):
        raise ValueError('Malformed captured granted target receipt')
    if item.payload.get('__granted_target_published_capture') == capture:
        return []
    revision = item.payload.get('__granted_target_revision', -1) + 1
    occurrence = [item.id, revision]
    triggers = []
    for receipt in capture['receipts']:
        identity = [_reference_key(receipt['recipient_ref']), _reference_key(receipt['grant_source_ref']),
                    receipt['clause_instance']]
        prefix = 'granted-target:' + json.dumps([state.turn, identity], separators=(',', ':'))
        limit = receipt['trigger_limit']
        if limit is not None:
            slot = next((index for index in range(limit)
                         if f'{prefix}:{index}' not in state.trigger_once_seen_this_turn), None)
            if slot is None:
                continue
            state.trigger_once_seen_this_turn.add(f'{prefix}:{slot}')
        bound = {**deepcopy(receipt), 'targeting_occurrence': occurrence}
        triggers.append({'source_card_id': receipt['recipient_ref']['card_id'],
                         'controller': receipt['trigger_controller'], 'label': 'Granted targeting ability',
                         'effect_key': 'reveal_top_conditional',
                         'payload': {'instruction': deepcopy(receipt['compiled_instruction']),
                                     '__granted_target_receipt': bound,
                                     '__source_lki': deepcopy(receipt['recipient_source_lki'])}})
    item.payload['__granted_target_revision'] = revision
    item.payload['__granted_target_membership'] = deepcopy(capture['target_refs'])
    item.payload['__granted_target_published_capture'] = deepcopy(capture)
    return triggers
