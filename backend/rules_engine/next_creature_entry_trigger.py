"""Closed next-cast instructions; durable notes and real spell-frame bindings."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import re

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.card_types import CREATURE_SUBTYPES

NOTE_KIND = 'native_noted_creature_type_history'
BIND_KEY = 'bind_creature_spell_entry_counter'
ANY = 'When you next cast a creature spell this turn, that creature enters with an additional +1/+1 counter on it.'
NOTED = "Note a creature type that hasn't been noted for this Saga. When you next cast a creature spell of that type this turn, that creature enters with an additional +1/+1 counter on it."


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def compile_instruction(text, source_oracle=None):
    body = re.sub(r'\s+', ' ', text or '').strip()
    normalized = body.casefold()
    if normalized not in {ANY.casefold(), NOTED.casefold()} and source_oracle:
        from rules_engine.oracle_effects import extract_saga_chapters
        # An anchor heading is not a rules prefix: it must belong to an actual chapter.
        if any(re.sub(r'\s+', ' ', ch['text']).strip().casefold() == body.casefold()
               for ch in extract_saga_chapters(source_oracle)):
            heading = re.fullmatch(r"[A-Za-z][A-Za-z '\-]+ \u2014 (.+)", body)
            if heading:
                normalized = heading[1].casefold()
    if normalized not in {ANY.casefold(), NOTED.casefold()}:
        return None
    return {'version': 1, 'body': body.casefold(), 'filter': 'noted_type' if normalized == NOTED.casefold() else 'any_creature'}


def reference(card):
    return {'card_id': card.id, 'incarnation': object_incarnation(card),
            'zone_change_sequence': card.zone_change_sequence, 'zone': card.zone.value}


def creation_matches(record):
    from effects.handlers import retained_next_creature_entry_origin
    native = record.get('__native_next_cast')
    origin = record.get('__entry_origin')
    if not isinstance(native, dict) or not isinstance(origin, dict):
        return False
    publication = origin.get('publication', {})
    instruction = compile_instruction(publication.get('clause'), publication.get('oracle_text'))
    if instruction != native.get('instruction') or instruction is None:
        return False
    controller = record.get('controller')
    frame = origin.get('frame', {})
    position = origin.get('child_position')
    rebuilt = retained_next_creature_entry_origin(None, controller, {
        '__resolving_item': frame, '__one_shot_child_position': position,
        'counter': '+1/+1', 'amount': 1})
    return (rebuilt == origin and native.get('id') == f"{frame.get('id')}:{position}"
            and record.get('amount') == 1 and record.get('counter') == '+1/+1'
            and type(native.get('turn')) is int and record.get('expires_turn') == native['turn'] + 1
            and native.get('filter') in (None, *CREATURE_SUBTYPES))


def history_key(origin):
    pub = origin['publication']
    return {'source': {'card_id': pub['source_card_id'], **pub['reference']},
            'link': digest(NOTED.casefold())}


def history(state, key):
    rows = [row for row in state.delayed_triggers if row.get('kind') == NOTE_KIND
            and row.get('key') == key]
    if len(rows) > 1:
        raise ActionRejected('Duplicate native type-note history')
    if not rows:
        return []
    row = rows[0]
    if (set(row) != {'kind', 'version', 'key', 'noted'} or row['version'] != 1
            or not isinstance(row['noted'], list) or row['noted'] != sorted(set(row['noted']))
            or any(value not in CREATURE_SUBTYPES for value in row['noted'])):
        raise ActionRejected('Malformed native type-note history')
    return list(row['noted'])


def arm(state, controller, payload):
    from effects.handlers import retained_next_creature_entry_origin
    origin = retained_next_creature_entry_origin(state, controller, payload)
    if origin is None:
        raise ActionRejected('Native next-cast instruction needs its real creation frame')
    pub = origin['publication']
    instruction = compile_instruction(pub.get('clause'), pub.get('oracle_text'))
    if instruction != payload.get('__native_next_instruction') or instruction is None:
        raise ActionRejected('Unknown complete native next-cast instruction')
    record = {'controller': controller, 'counter': '+1/+1', 'amount': 1,
              'source_card_id': pub['source_card_id'], 'expires_turn': state.turn + 1,
              '__entry_origin': origin, '__native_next_cast': {
                  'id': f"{origin['frame']['id']}:{origin['child_position']}",
                  'instruction': instruction, 'turn': state.turn, 'filter': None}}
    if instruction['filter'] == 'noted_type':
        key = history_key(origin)
        noted = history(state, key)
        options = sorted(CREATURE_SUBTYPES - set(noted))
        if not options:
            return
        state.pending_mechanic_choice = {
            'kind': 'note_creature_type', 'player_id': controller, 'controller': controller,
            'options': ['creature-type:' + value for value in options], 'count': 1,
            'label': 'Note a creature type', 'record': record, 'history_key': key, 'history_before': noted}
        state.priority_player = controller
        state.passed_priority = set()
    else:
        state.pending_entry_counters.append(record)


def note_view(pending):
    return {'type': 'choose_mechanic', 'kind': 'note_creature_type',
            'player_id': pending['player_id'], 'options': list(pending['options']), 'count': 1,
            'label': pending['label'], 'option_labels': {
                value: value.removeprefix('creature-type:').title() for value in pending['options']},
            'option_type_lines': {}}


def finish_note(state, player_id, action):
    from rules_engine.stack_engine import resume_paused_resolution
    pending = state.pending_mechanic_choice
    if not pending or pending.get('kind') != 'note_creature_type':
        return False
    record = pending.get('record', {})
    choice = action.get('choice_id')
    if (pending.get('player_id') != player_id or record.get('controller') != player_id
            or not creation_matches(record) or record['__native_next_cast']['instruction']['filter'] != 'noted_type'
            or pending.get('history_key') != history_key(record['__entry_origin'])
            or pending.get('resolving_item') != record['__entry_origin']['frame']
            or history(state, pending['history_key']) != pending.get('history_before')
            or pending.get('options') != ['creature-type:' + value for value in
                sorted(CREATURE_SUBTYPES - set(pending['history_before']))]
            or choice not in pending['options']):
        raise ActionRejected('Invalid native creature-type choice or retained frame')
    chosen = choice.removeprefix('creature-type:')
    row = {'kind': NOTE_KIND, 'version': 1, 'key': deepcopy(pending['history_key']),
           'noted': sorted([*pending['history_before'], chosen])}
    state.delayed_triggers = [r for r in state.delayed_triggers
        if not (r.get('kind') == NOTE_KIND and r.get('key') == pending['history_key'])] + [row]
    record = deepcopy(record)
    record['__native_next_cast']['filter'] = chosen
    state.pending_entry_counters.append(record)
    state.pending_mechanic_choice = None
    resume_paused_resolution(state, pending)
    return True


def collect_cast(state, payload):
    from rules_engine.type_effects import effective_types
    from rules_engine.library_permissions import creature_types
    stack_id = payload.get('source_stack_id')
    item = next((item for item in state.stack if item.id == stack_id), None)
    card = state.cards.get(payload.get('source_card_id'))
    if (item is None or card is None or card.zone != Zone.STACK
            or item.source_card_id != card.id or item.controller != payload.get('controller')
            or item.payload != payload.get('stack_payload') or 'Creature' not in effective_types(state, card)):
        return []
    cast = {'stack_id': item.id, 'reference': reference(card), 'owner': card.owner,
            'controller': item.controller}
    triggers, remaining = [], []
    for record in state.pending_entry_counters:
        native = record.get('__native_next_cast')
        if native is None:
            remaining.append(record)
            continue
        if not creation_matches(record):
            raise ActionRejected('Malformed native waiting packet')
        if native['instruction']['filter'] == 'noted_type' and native['filter'] is None:
            raise ActionRejected('Unchosen noted type cannot arm a native trigger')
        matches = (record['controller'] == item.controller and native['turn'] == state.turn
                   and (native['filter'] is None or native['filter'] in creature_types(card, state)))
        if not matches:
            remaining.append(record)
            continue
        triggers.append({'source_card_id': record['source_card_id'], 'controller': record['controller'],
            'label': 'Next creature spell entry effect', 'effect_key': BIND_KEY,
            'payload': {'__native_creation': deepcopy(record), '__native_cast': cast,
                        '__trigger_full_clause': record['__entry_origin']['publication']['clause']}})
    # The next qualifying cast, not an eventual entry, consumes the native occurrence.
    state.pending_entry_counters = remaining
    return triggers


def publication(item):
    data = item.payload
    return {'stack_id': item.id, 'controller': item.controller,
            'source_pre': deepcopy(data['__native_creation']['__entry_origin']['publication']),
            'cast': deepcopy(data['__native_cast'])}


def binding_matches(binding):
    frame = binding.get('frame', {})
    data = frame.get('payload', {})
    record = data.get('__native_creation', {})
    return (frame.get('effect_key') == BIND_KEY and creation_matches(record)
            and frame.get('controller') == record.get('controller')
            and frame.get('source_card_id') == record.get('source_card_id')
            and isinstance(frame.get('id'), str) and bool(frame['id'])
            and data.get('__native_publication') == {
                'stack_id': frame['id'], 'controller': frame['controller'],
                'source_pre': record['__entry_origin']['publication'], 'cast': data.get('__native_cast')})


def bind(state, controller, payload):
    frame = payload.get('__resolving_item')
    binding = {'frame': deepcopy(frame)} if isinstance(frame, dict) else {}
    if (not binding_matches(binding) or frame['controller'] != controller
            or any(payload.get(key) != frame['payload'].get(key) for key in
                   ('__native_creation', '__native_cast', '__native_publication'))):
        raise ActionRejected('Invalid real native delayed binding frame')
    cast = frame['payload']['__native_cast']
    spell = next((item for item in state.stack if item.id == cast['stack_id']), None)
    card = state.cards.get(cast['reference']['card_id'])
    if (spell is None or card is None or card.zone != Zone.STACK or reference(card) != cast['reference']
            or spell.source_card_id != card.id or spell.controller != cast['controller']):
        return
    values = spell.payload.setdefault('__native_next_entry_bindings', [])
    if any(value['frame']['id'] == frame['id'] for value in values):
        raise ActionRejected('Duplicate native binding frame')
    values.append(binding)


def entry_receipt(state, frame):
    values = frame.get('payload', {}).get('__native_next_entry_bindings', [])
    if not values:
        return None
    card = state.cards.get(frame.get('source_card_id'))
    if card is None or card.zone != Zone.STACK:
        return False
    ids = []
    for binding in values:
        if not binding_matches(binding):
            return False
        bind_frame = binding['frame']
        cast = bind_frame['payload']['__native_cast']
        if (cast != {'stack_id': frame['id'], 'reference': reference(card),
                     'owner': card.owner, 'controller': frame['controller']}
                or bind_frame['id'] in ids):
            return False
        ids.append(bind_frame['id'])
    return {'kind': 'native_spell_bound', 'frame_id': frame['id'],
            'reference': reference(card), 'bindings': deepcopy(values), 'legacy': None,
            'source_id': ids[0] + ':entry-producer'}


def entry_options(state, controller, payload, used, legacy_options):
    receipt = payload['__next_entry_counter']
    expected = entry_receipt(state, payload.get('entry_item', {}))
    if not expected or {**receipt, 'legacy': None} != expected:
        return None
    options = []
    if receipt['legacy']:
        legacy = legacy_options(state, controller, {**payload,
            '__next_entry_counter': receipt['legacy']}, used)
        if legacy is None:
            return None
        options.extend(legacy)
    if payload.get('counter', '+1/+1') != '+1/+1':
        return options
    for binding in receipt['bindings']:
        source_id = binding['frame']['id'] + ':entry-producer'
        if source_id not in used:
            options.append({'source_id': source_id, 'name': 'Cast-bound entry instruction',
                'operation': 'add', 'operand': 1, 'clause': None,
                'instruction_ref': digest(binding), 'entry_producer': True, 'next_entry_producer': True})
    return options
