"""Owner/controller-bound entry choices over detached copiable projections."""
from copy import deepcopy
import re

from rules_engine.action_validation import ActionRejected
from rules_engine.loyalty_instructions import card_reference, native_frame_matches, reference_matches
from rules_engine.type_effects import effective_types

PLAN = '__entry_copy_plan'
RESERVATION = '__entry_copy_candidate'
BODY = re.compile(r'You may have this artifact enter as a copy of any artifact on the battlefield\.', re.I)


def compile_instruction(raw):
    if BODY.fullmatch(raw.strip()):
        return raw
    if re.search(r'you may have .+ enter as a copy', raw, re.I):
        raise ActionRejected('Unsupported complete as-entry copy instruction')
    return None


def _options(state):
    return [cid for seat in state.players.values() for cid in seat.battlefield
            if cid in state.cards and state.cards[cid].zone.value == 'battlefield'
            and state.cards[cid].controller == seat.id and 'Artifact' in effective_types(state, cid)]


def _frame(payload):
    return payload.get('entry_item') or payload.get('__resolving_item')


def _native_copy_candidate(frame, cid, turn):
    from game_state.state import CardInstance, Zone
    copied = frame['payload']['__copied_card']
    count = None
    if '__kicker_count' in frame['payload']:
        from rules_engine.kicker import validate_kicker_count
        count = validate_kicker_count(frame['payload']['__kicker_count'],
                                      frame['payload'].get('__kicked', False))
    return CardInstance(
        id=cid, name=copied['name'], owner=frame['controller'], controller=frame['controller'],
        zone=Zone.STACK, is_token=True, types=list(dict.fromkeys([*copied.get('types', []), 'Token'])),
        mana_cost=copied.get('mana_cost') or '', type_line=copied.get('type_line') or '',
        oracle_text=copied.get('oracle_text') or '', power=copied.get('power'),
        toughness=copied.get('toughness'), loyalty=copied.get('loyalty'),
        printed_power=copied.get('printed_power'), printed_toughness=copied.get('printed_toughness'),
        keywords=list(copied.get('keywords') or []), colors=deepcopy(copied.get('colors')),
        image_uri=copied.get('image_uri'), layout=copied.get('layout') or '',
        card_faces=deepcopy(copied.get('card_faces') or []), selected_face_index=copied.get('selected_face_index'),
        bestow_characteristics=deepcopy(copied.get('bestow_characteristics') or {}),
        summoning_sick=True, entered_turn=turn, was_kicked=bool(frame['payload'].get('__kicked')),
        kicker_count=count)


def _same_native_value(left, right):
    """Match serialized native receipts without Python's bool/int aliases."""
    import json
    try:
        return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return False


def _candidate(state, frame, receipt, *, committed=False):
    from dataclasses import asdict
    from uuid import UUID
    from rules_engine.copiable_values import values
    if (not native_frame_matches(frame, frame.get('controller') if isinstance(frame, dict) else None)
            or frame['controller'] not in state.players
            or frame['payload'].get('__stack_copy_kind') != 'spell'
            or frame['payload'].get('__source_card_id') != frame['source_card_id']
            or type(frame['payload'].get('__copied_from_stack_id')) is not str
            or frame['payload']['__copied_from_stack_id'] == frame['id']
            or type(receipt) is not dict or set(receipt) != {'card', 'allocation_next'}
            or type(receipt['allocation_next']) is not int or receipt['allocation_next'] < 2
            or not _same_native_value(frame['payload'].get(RESERVATION), receipt)
            or type(receipt['card']) is not dict or type(receipt['card'].get('id')) is not str):
        return None
    raw, counter = receipt['card'], receipt['allocation_next']
    try:
        if (str(UUID(int=counter-1)) != raw['id'] or raw['id'] in {
                frame['id'], frame['source_card_id'], frame['payload']['__copied_from_stack_id']}
                or type(raw.get('entered_turn')) is not int or raw['entered_turn'] != state.turn):
            return None
        expected = _native_copy_candidate(frame, raw['id'], raw['entered_turn'])
        values(expected)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not _same_native_value(asdict(expected), raw):
        return None
    present = state.cards.get(raw['id'])
    if committed:
        return (present if present is not None and present.zone.value == 'battlefield'
                and present.is_token is True and present.owner == present.controller == frame['controller']
                and state.players[frame['controller']].battlefield.count(present.id) == 1
                and type(present.characteristic_record) is dict
                and present.characteristic_record.get('physical') == expected.characteristic_record['physical']
                and state.next_object_id >= counter else None)
    if (state.next_object_id != counter or present is not None
            or any(item.id == raw['id'] for item in state.stack)
            or any(raw['id'] in getattr(player, zone) for player in state.players.values()
                   for zone in ('hand', 'library', 'graveyard', 'exile', 'battlefield'))):
        return None
    return expected


def _recipient(state, payload, row):
    return (_candidate(state, _frame(payload), row['candidate']) if 'candidate' in row
            else state.cards.get(row['id']))


def _row(state, card, controller, candidate=None):
    from game_state.state import object_incarnation
    return {'id': card.id, 'owner': card.owner, 'controller': controller,
            'reference': {'incarnation': object_incarnation(card), 'sequence': card.zone_change_sequence,
                          'zone': card.zone.value},
            'clause': compile_instruction(card.oracle_text),
            **({'candidate': deepcopy(candidate)} if candidate is not None else {})}


def plan_matches(state, payload):
    from rules_engine.copiable_values import values
    from rules_engine.loyalty_instructions import valid_card_reference
    plan = payload.get(PLAN)
    if (type(plan) is not dict or set(plan) != {'controller', 'frame', 'entries'}
            or not native_frame_matches(plan['frame'], plan['controller'])
            or plan['frame'] != _frame(payload) or type(plan['entries']) is not list
            or not plan['entries']):
        return False
    ids = set()
    for row in plan['entries']:
        if (type(row) is not dict or set(row) != ({'id', 'owner', 'controller', 'reference', 'clause', 'choice'}
                                                | ({'candidate'} if 'candidate' in row else set()))
                or type(row['id']) is not str or row['id'] in ids
                or type(row['owner']) is not int
                or not valid_card_reference(row['reference'])
                or type(row['controller']) is not int or row['controller'] not in state.players):
            return False
        ids.add(row['id'])
        card = _recipient(state, payload, row)
        if (card is None or {key: row[key] for key in row if key != 'choice'}
                != _row(state, card, row['controller'], row.get('candidate'))):
            return False
        if 'candidate' in row:
            if (len(plan['entries']) != 1 or card.owner != row['controller']
                    or row['controller'] != plan['controller']):
                return False
        elif card.zone.value == 'stack' and (row['controller'] != plan['frame']['controller']
                or card.id != plan['frame']['source_card_id']):
            return False
        if '__loyalty_return_context' in payload:
            from rules_engine.loyalty_instructions import return_context_matches
            context = payload['__loyalty_return_context']
            if (not return_context_matches(state, plan['controller'], payload)
                    or len(plan['entries']) != 1 or row['id'] != context['target_card_id']
                    or row['controller'] != context['controller']):
                return False
        if payload.get('__return_controller') is not None and row['controller'] != payload['__return_controller']:
            return False
        if payload.get('__graveyard_batch_plan') is not None:
            original = payload['__graveyard_batch_plan']['entries']
            expected = [r['id'] for r in original if r['admitted']]
            if [r['id'] for r in plan['entries']] != expected or row['controller'] != card.owner:
                return False
        choice = row['choice']
        if choice is None:
            continue
        if (row['clause'] is None or type(choice) is not dict
                or set(choice) != {'id', 'reference', 'values'}):
            return False
        if choice['id'] is None:
            if choice != {'id': None, 'reference': None, 'values': None}:
                return False
        elif (choice['id'] not in _options(state)
                or not reference_matches(state, choice['id'], choice['reference'])
                or choice['values'] != values(state.cards[choice['id']])):
            return False
    return True


def prepare(state, controller, cards, effect_key, payload, *, controllers, candidates=None):
    if PLAN in payload:
        if not plan_matches(state, payload):
            raise ActionRejected('Stale as-entry copy plan')
        rows = payload[PLAN]['entries']
        if [row['id'] for row in rows] != [card.id for card in cards] or any(
                controllers.get(row['id']) != row['controller'] for row in rows):
            raise ActionRejected('Incomplete as-entry copy roster')
        data = deepcopy(payload)
    else:
        rows = [{**_row(state, card, controllers[card.id], (candidates or {}).get(card.id)),
                 'choice': None} for card in cards]
        if not any(row['clause'] is not None for row in rows):
            return False
        frame = _frame(payload)
        if not native_frame_matches(frame, controller):
            raise ActionRejected('As-entry copy requires its actual resolving frame')
        data = {**deepcopy(payload), PLAN: {'controller': controller, 'frame': deepcopy(frame), 'entries': rows}}
    if not plan_matches(state, data):
        raise ActionRejected('Invalid native entry-copy recipient')
    for row in data[PLAN]['entries']:
        if row['clause'] is None or row['choice'] is not None:
            continue
        options = _options(state)
        state.pending_mechanic_choice = {'kind': 'entry_copy', 'player_id': row['controller'],
            'entry_card_id': row['id'], 'count': 1, 'min_count': 0,
            'options': options, 'label': 'You may choose an artifact to copy as this permanent enters',
            'effect_key': effect_key, 'effect_payload': data,
            'resolving_item': deepcopy(data[PLAN]['frame'])}
        state.priority_player = row['controller']
        state.passed_priority = set()
        return True
    return False


def projections(state, payload):
    from rules_engine.copiable_values import project
    if PLAN not in payload:
        return {}
    if (not plan_matches(state, payload) or any(row['clause'] is not None and row['choice'] is None
            for row in payload[PLAN]['entries'])):
        raise ActionRejected('Stale entry projection')
    return {row['id']: project(_recipient(state, payload, row), row['choice']['values'])
            for row in payload[PLAN]['entries'] if row['choice'] and row['choice']['id'] is not None}


def commit(state, payload, ids, *, recipients=None):
    from rules_engine.copiable_values import apply
    projected = projections(state, payload)
    for cid in ids:
        if cid in projected:
            target = (recipients or {}).get(cid)
            if target is None:
                target = state.cards[cid]
            apply(target, projected[cid].characteristic_record['values'], entering=True)


def choice_view(pending, actor=False):
    return {key: deepcopy(pending[key]) for key in
        ('kind', 'player_id', 'count', 'min_count', 'options', 'label') if key in pending}


def validate_land_choice(state, actor, action):
    from rules_engine.entry import land_entry_options
    pending = state.pending_mechanic_choice
    payload = pending['effect_payload']
    projected = projections(state, payload)
    cid = pending.get('entry_card_id')
    rows = payload[PLAN]['entries']
    row = next((row for row in rows if row['id'] == cid), None)
    choice = action.get('choice_id')
    if (row is None or row['controller'] != actor or pending.get('player_id') != actor
            or cid not in projected or choice not in pending.get('options', [])
            or choice not in land_entry_options(state, actor, projected[cid])):
        raise ActionRejected('Invalid retained copied-land choice')
    owners = {row['id']: row['controller'] for row in rows}
    reserved = 2 * sum(value == 'pay_two_life' and owners.get(key) == actor
                       for key, value in payload.get('__entry_choices', {}).items())
    if choice == 'pay_two_life' and state.players[actor].life-reserved < 2:
        raise ActionRejected('Unavailable reserved copied-land payment')


def selected_option(state, actor, action):
    """Pure validation shared by checked admission and the actual producer."""
    pending = state.pending_mechanic_choice
    if (not pending or pending.get('kind') != 'entry_copy' or type(actor) is not int
            or type(pending.get('player_id')) is not int or pending['player_id'] != actor
            or type(pending.get('entry_card_id')) is not str
            or not isinstance(pending.get('effect_payload'), dict)
            or not plan_matches(state, pending['effect_payload'])):
        raise ActionRejected('Invalid or stale entry-copy source')
    plan = pending['effect_payload'][PLAN]
    row = next((r for r in plan['entries'] if r['id'] == pending['entry_card_id']), None)
    if (pending.get('resolving_item') != plan['frame'] or row is None
            or row['controller'] != actor or row['choice'] is not None or row['clause'] is None
            or pending.get('options') != _options(state)):
        raise ActionRejected('Invalid entry-copy continuation')
    if (set(action) - {'type', 'choice_id', 'card_ids', 'damage_assignment'}
            or action.get('damage_assignment') is not None):
        raise ActionRejected('Unexpected entry-copy selection fields')
    selected, ids = action.get('choice_id'), action.get('card_ids')
    if selected is not None:
        if type(selected) is not str or ids is not None and (type(ids) is not list or ids):
            raise ActionRejected('Choose one entry-copy selection form')
    else:
        if ('card_ids' not in action or type(ids) is not list or len(ids) > 1
                or any(type(cid) is not str for cid in ids)):
            raise ActionRejected('Choose zero or one real entry-copy card')
        selected = ids[0] if ids else None
    if selected is not None and selected not in pending['options']:
        raise ActionRejected('Unavailable entry-copy choice')
    if selected is not None:
        from rules_engine.attachments import is_aura
        from rules_engine.copiable_values import project, values
        if is_aura(project(_recipient(state, pending['effect_payload'], row), values(state.cards[selected]))):
            raise ActionRejected('Unsupported copied Aura entry attachment preparation')
    return selected


def finish_choice(state, actor, action):
    from effects.registry import resolve_effect
    from rules_engine.copiable_values import values
    from rules_engine.stack_engine import resume_paused_resolution
    pending = state.pending_mechanic_choice
    selected = selected_option(state, actor, action)
    data = pending['effect_payload']
    plan = data[PLAN]
    updated = deepcopy(data)
    choice = {'id': selected, 'reference': card_reference(state, selected) if selected is not None else None,
              'values': values(state.cards[selected]) if selected is not None else None}
    next(r for r in updated[PLAN]['entries'] if r['id'] == pending['entry_card_id'])['choice'] = choice
    state.pending_mechanic_choice = None
    resolve_effect(state, plan['controller'], pending['effect_key'], updated)
    row = next(r for r in updated[PLAN]['entries'] if r['id'] == pending['entry_card_id'])
    if ('candidate' in row and not (state.pending_mechanic_choice or state.pending_replacement_choice)):
        if _candidate(state, updated[PLAN]['frame'], row['candidate'], committed=True) is None:
            raise ActionRejected('Copied permanent did not complete its native entry')
        pending = {**pending, 'resolving_item': None}
    resume_paused_resolution(state, pending)
    return True
