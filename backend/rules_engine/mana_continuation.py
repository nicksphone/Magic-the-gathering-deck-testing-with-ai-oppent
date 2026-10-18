"""Private, data-only phases for native mana replacement choices."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps


class ManaPaymentPaused(Exception):
    """A real native choice interrupted payment; never a paid bool result."""


_SESSION = ContextVar('mana_payment_session', default=None)
_FEASIBILITY = ContextVar('mana_feasibility_trial', default=False)
_MANUAL = {'activate_mana_ability', 'tap_land_for_mana', 'tap_nonland_for_mana'}


def _reject():
    from rules_engine.action_validation import ActionRejected
    raise ActionRejected('Invalid private mana continuation')


def reference(card):
    from game_state.state import object_incarnation
    return {'card_id': card.id, 'incarnation': object_incarnation(card),
            'zone_change_sequence': card.zone_change_sequence,
            'zone': card.zone.value, 'controller': card.controller}


def _origin(state, actor, kind):
    return {'match_id': state.id, 'actor': actor, 'action_kind': kind,
            'turn': state.turn, 'step': state.step.value,
            'phase_cursor': state.phase_cursor, 'priority_player': state.priority_player}


def _stage(state):
    return {'owned': False, 'previous_enabled': state.trigger_staging,
            'previous_event': state.trigger_staging_event,
            'queue_start': len(state.staged_triggers)}


def _pending(state):
    for channel, pending in [('replacement', state.pending_replacement_choice),
                             ('mechanic', state.pending_mechanic_choice),
                             ('trigger_order', state.pending_trigger_order)]:
        if pending:
            return channel, pending
    return None, None


def _waiting(state, frames):
    channel, pending = _pending(state)
    if not pending:
        _reject()
    source = pending.get('source_card_id')
    target = pending.get('target_card_id')
    return {'frame_index': len(frames) - 1, 'channel': channel,
            'native_kind': pending.get('resume_kind') or pending.get('kind') or '',
            'event': pending.get('event'), 'player_id': pending['player_id'],
            'source': reference(state.cards[source]) if source in state.cards else None,
            'target': reference(state.cards[target]) if target in state.cards else None,
            'stack_id': pending.get('stack_id')}


def _freeze(state):
    session = _SESSION.get()
    if session is None or session['state'] is not state:
        _reject()
    value = {'version': 1, 'origin': session['origin'],
        'frames': session['frames'], 'waiting': _waiting(state, session['frames'])}
    if session.get('opaque_condition'):
        _reject()
    if session['frames'] and session['frames'][0].get('op') == 'cast':
        value = _plain(value)
    state.mana_continuation = validate(state, value)


def _plain(value):
    if type(value) in (str, int, bool, type(None)):
        return value
    if type(value) is float:
        from math import isfinite
        if isfinite(value):
            return value
    if type(value) in (list, tuple):
        return [_plain(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _plain(item) for key, item in value.items()}
    _reject()


@contextmanager
def prepared_cast(state, payer, data):
    stage = {**_stage(state), 'owned': not state.trigger_staging,
             'prefix': deepcopy(state.staged_triggers)}
    frame = {'tag': 'owner', 'op': 'cast', 'phase': 'mana', 'payer': payer,
             'stage': stage, 'data': data}
    session = _SESSION.get()
    registered = (session is not None and session['state'] is state and not session['frames']
                  and session['origin']['action_kind'] == 'cast_spell')
    if registered:
        session['frames'].append(frame)
    try:
        yield frame
    except ManaPaymentPaused:
        raise
    else:
        if registered:
            session['frames'].pop()


def cast_payment_owner(state):
    session = _SESSION.get()
    if (session is not None and session['state'] is state and len(session['frames']) == 1
            and session['frames'][0].get('op') == 'cast'):
        return session['frames'][0]
    return None


def _integer(value):
    return type(value) is int and value >= 0


def _outputs(value):
    return (type(value) is dict and all(type(c) is str and len(c) == 1
            and c in 'WUBRGC' and _integer(n) for c, n in value.items()))


def _reference_shape(state, ref):
    return (type(ref) is dict and set(ref) == {
        'card_id', 'incarnation', 'zone_change_sequence', 'zone', 'controller'}
        and type(ref['card_id']) is str and ref['card_id'] in state.cards
        and type(ref['controller']) is int and ref['controller'] in state.players
        and _integer(ref['incarnation']) and _integer(ref['zone_change_sequence'])
        and type(ref['zone']) is str and ref['zone'] in {'library', 'hand', 'battlefield',
            'graveyard', 'exile', 'stack', 'command'})


def validate(state, value, *, pending=None):
    if value is None:
        return None
    if (type(value) is not dict or set(value) != {'version', 'origin', 'frames', 'waiting'}
            or type(value['version']) is not int or value['version'] != 1):
        _reject()
    origin, frames, waiting = value['origin'], value['frames'], value['waiting']
    if (type(origin) is not dict or set(origin) != {
            'match_id', 'actor', 'action_kind', 'turn', 'step', 'phase_cursor', 'priority_player'}
            or origin['match_id'] != state.id or type(origin['actor']) is not int
            or origin['actor'] not in state.players or origin['turn'] != state.turn
            or not _integer(origin['turn']) or not _integer(origin['phase_cursor'])
            or origin['step'] != state.step.value or origin['phase_cursor'] != state.phase_cursor
            or type(origin['action_kind']) is not str or not origin['action_kind']
            or type(origin['priority_player']) is not int
            or origin['priority_player'] not in state.players
            or type(frames) is not list or len(frames) not in (2, 3)
            or type(waiting) is not dict or set(waiting) != {
                'frame_index', 'channel', 'native_kind', 'event', 'player_id',
                'source', 'target', 'stack_id'}
            or type(waiting['frame_index']) is not int
            or waiting['frame_index'] != len(frames)-1):
        _reject()
    for frame in frames:
        if type(frame) is not dict:
            _reject()
        if frame.get('tag') == 'owner':
            if frame.get('op') == 'cast':
                _validate_cast_owner(state, origin, frame)
                continue
            if (set(frame) != {'tag', 'op', 'phase', 'payer', 'stage', 'data'}
                    or frame['op'] not in {'single_mana', 'bulk_mana'}
                    or frame['phase'] != 'activation' or type(frame['payer']) is not int
                    or frame['payer'] != origin['actor']
                    or type(frame['data']) is not dict):
                _reject()
            stage = frame['stage']
            if (type(stage) is not dict or set(stage) != {
                    'owned', 'previous_enabled', 'previous_event', 'queue_start'}
                    or type(stage['owned']) is not bool or type(stage['previous_enabled']) is not bool
                    or not isinstance(stage['previous_event'], (str, type(None)))
                    or not _integer(stage['queue_start']) or stage['queue_start'] > len(state.staged_triggers)):
                _reject()
            data = frame['data']
            if (type(data.get('return_priority')) is not int
                    or data['return_priority'] != origin['priority_player']):
                _reject()
            if frame['op'] == 'single_mana':
                if (set(data) != {'route', 'source', 'return_priority', 'output'}
                        or type(data['route']) is not str or data['route'] not in _MANUAL
                        or type(data['source']) is not str or data['source'] not in state.cards
                        or not _outputs(data['output'])):
                    _reject()
            elif (set(data) != {'roster', 'requested_count', 'cursor', 'return_priority', 'label'}
                    or type(data['roster']) is not list or not _integer(data['cursor'])
                    or not _integer(data['requested_count'])
                    or data['requested_count'] != len(data['roster'])
                    or not 0 <= data['cursor'] < len(data['roster'])
                    or type(data['label']) is not str or not data['label']):
                _reject()
            if frame['op'] == 'bulk_mana':
                ids = set()
                for index, row in enumerate(data['roster']):
                    if (type(row) is not dict or set(row) != {
                            'source', 'ability_index', 'color', 'amount'}
                            or not _reference_shape(state, row['source'])
                            or row['source']['controller'] != frame['payer']
                            or row['source']['zone'] != 'battlefield'
                            or type(row['ability_index']) is not int or row['ability_index'] < 0
                            or type(row['color']) is not str or len(row['color']) != 1
                            or row['color'] not in 'WUBRGC'
                            or not _integer(row['amount']) or row['amount'] == 0
                            or row['source']['card_id'] in ids):
                        _reject()
                    ids.add(row['source']['card_id'])
                    if index >= data['cursor'] and reference(state.cards[row['source']['card_id']]) != row['source']:
                        _reject()
        elif frame.get('tag') == 'payment':
            _validate_cast_payment(state, origin, frame)
        elif frame.get('tag') == 'mana_activation':
            if (set(frame) != {'tag', 'phase', 'payer', 'source', 'ability_index',
                              'color', 'output', 'captured_bonus', 'bonus_cursor'}
                    or frame['phase'] != 'linked_damage'
                    or type(frame['payer']) is not int or frame['payer'] not in state.players
                    or type(frame['ability_index']) is not int or frame['ability_index'] < 0
                    or type(frame['color']) is not str or len(frame['color']) != 1
                    or frame['color'] not in 'WUBRGC' or not _outputs(frame['output'])
                    or type(frame['captured_bonus']) is not list
                    or type(frame['bonus_cursor']) is not int or frame['bonus_cursor'] != 0):
                _reject()
            for row in frame['captured_bonus']:
                if (type(row) not in (list, tuple) or len(row) != 5
                        or type(row[0]) is not int or row[0] not in state.players
                        or type(row[1]) is not str or row[1] not in state.cards
                        or not _integer(row[2]) or type(row[3]) is not bool
                        or not _outputs(row[4])):
                    _reject()
            ref = frame['source']
            if not _reference_shape(state, ref) or ref['controller'] != frame['payer']:
                _reject()
        else:
            _reject()
    if (frames[0]['tag'] != 'owner' or frames[-1]['tag'] != 'mana_activation'
            or frames[-1]['payer'] != origin['actor']):
        _reject()
    owner, activation_frame = frames[0], frames[-1]
    if len(frames) == 3:
        if (owner.get('op') != 'cast' or frames[1].get('tag') != 'payment'
                or origin['action_kind'] != 'cast_spell'):
            _reject()
        payment = frames[1]['data']
        contract = owner['data']['payment_contract']
        if (type(contract) is not dict or set(contract) != {
                'req', 'context', 'steps', 'reserved_card_ids', 'protected_life',
                'resource_plan', 'snow_spent'}
                or any(contract[key] != payment[key] for key in contract)):
            _reject()
        cast = owner['data']
        if (payment['protected_life'] != cast['chosen']['pay_life']
                + (cast['x_value'] if cast['chosen']['pay_life_x'] else 0)
                or (payment['resource_plan'] is not None
                    and payment['resource_plan']['source_card_id'] != cast['source']['card_id'])
                or (payment['postcondition'] is not None) != cast['has_escape_condition']):
            _reject()
        if payment['postcondition'] is not None:
            condition = payment['postcondition']
            if (condition['card_id'] != cast['source']['card_id']
                    or condition['count'] != cast['chosen']['exile_graveyard']
                    or condition['selected'] != cast['escape_selected']):
                _reject()
        step = payment['steps'][payment['cursor']]
        if (step['source'] != activation_frame['source']
                or step['ability_index'] != activation_frame['ability_index']
                or (not step['selector'].startswith('bundle:')
                    and step['selector'] != activation_frame['color'])):
            _reject()
    elif owner['op'] == 'bulk_mana':
        row = owner['data']['roster'][owner['data']['cursor']]
        base_amount = activation_frame['output'].get(row['color'], 0)
        bonus_amount = sum(bonus[4].get(row['color'], 0)
                           for bonus in activation_frame['captured_bonus']
                           if bonus[0] == owner['payer'])
        if (origin['action_kind'] != 'tap_lands_bulk'
                or row['source'] != activation_frame['source']
                or row['ability_index'] != activation_frame['ability_index']
                or row['color'] != activation_frame['color']
                or base_amount <= 0 or row['amount'] != base_amount + bonus_amount):
            _reject()
    elif owner['op'] != 'single_mana':
        _reject()
    elif (owner['data']['route'] != origin['action_kind']
            or owner['data']['source'] != activation_frame['source']['card_id']
            or owner['data']['output'] != activation_frame['output']):
        _reject()
    if reference(state.cards[activation_frame['source']['card_id']]) != activation_frame['source']:
        _reject()
    channel, current = _pending(state)
    if pending is not None:
        current, channel = pending, waiting['channel']
    if type(current) is not dict or not current:
        _reject()
    for ref in [waiting['source'], waiting['target']]:
        if ref is not None and (not _reference_shape(state, ref) or reference(state.cards[ref['card_id']]) != ref):
            _reject()
    if type(waiting['player_id']) is not int or waiting['player_id'] not in state.players:
        _reject()
    if (channel != waiting['channel'] or current.get('player_id') != waiting['player_id']
            or (current.get('resume_kind') or current.get('kind') or '') != waiting['native_kind']
            or current.get('event') != waiting['event']
            or current.get('stack_id') != waiting['stack_id']
            or current.get('source_card_id') != (waiting['source'] or {}).get('card_id')
            or current.get('target_card_id') != (waiting['target'] or {}).get('card_id')
            or frames[-1]['source']['card_id'] != current.get('source_card_id')):
        _reject()
    return deepcopy(value)


def _validate_cast_owner(state, origin, frame):
    from dataclasses import fields, MISSING
    from rules_engine.costs import CostOption
    from game_state.serializers import _card_snapshot, _card_from_snapshot
    if (set(frame) != {'tag', 'op', 'phase', 'payer', 'stage', 'data'}
            or frame['phase'] != 'mana' or type(frame['payer']) is not int
            or frame['payer'] != origin['actor'] or type(frame['data']) is not dict):
        _reject()
    stage, data = frame['stage'], frame['data']
    if (type(stage) is not dict or set(stage) != {
            'owned', 'previous_enabled', 'previous_event', 'queue_start', 'prefix'}
            or type(stage['owned']) is not bool or type(stage['previous_enabled']) is not bool
            or stage['owned'] == stage['previous_enabled']
            or not isinstance(stage['previous_event'], (str, type(None)))
            or not _integer(stage['queue_start']) or type(stage['prefix']) is not list
            or len(stage['prefix']) != stage['queue_start']
            or _plain(state.staged_triggers[:stage['queue_start']]) != stage['prefix']
            or not state.trigger_staging
            or state.trigger_staging_event != ('spell_cast' if stage['owned'] else stage['previous_event'])):
        _reject()
    if set(data) != {'source', 'chosen', 'face_card', 'printed_face_card', 'action_targets',
            'target_references', 'ward_specs', 'grant_capture', 'selected_face_index', 'x_value',
            'bestowed', 'from_graveyard', 'from_exile', 'from_library', 'effect_cast',
            'escape_ids', 'escape_selected', 'has_escape_condition', 'exile_references',
            'frozen_cost_choice', 'payment_details', 'payment_contract'}:
        _reject()
    if (not _reference_shape(state, data['source'])
            or reference(state.cards[data['source']['card_id']]) != data['source']
            or not _integer(data['x_value'])
            or data['selected_face_index'] is not None and not _integer(data['selected_face_index'])
            or any(type(data[key]) is not bool for key in ('bestowed', 'from_graveyard',
                'from_exile', 'from_library', 'effect_cast', 'has_escape_condition'))
            or sum(data[key] for key in ('from_graveyard', 'from_exile', 'from_library')) > 1
            or any(type(data[key]) is not dict for key in ('action_targets', 'target_references',
                'exile_references', 'frozen_cost_choice', 'payment_details'))
            or type(data['ward_specs']) is not list or type(data['grant_capture']) is not dict):
        _reject()
    source = data['source']['card_id']
    zone = ('graveyard' if data['from_graveyard'] else 'exile' if data['from_exile']
            else 'library' if data['from_library'] else 'hand')
    containers = (state.players.values() if data['from_exile']
                  else (state.players[frame['payer']],))
    if data['source']['zone'] != zone or not any(source in getattr(player, zone) for player in containers):
        _reject()
    for cid, ref in data['exile_references'].items():
        if (type(cid) is not str or cid not in state.cards or type(ref) is not list
                or len(ref) != 2 or any(not _integer(n) for n in ref)
                or [reference(state.cards[cid])['incarnation'],
                    state.cards[cid].zone_change_sequence] != ref):
            _reject()
    from rules_engine.targeting import validate_announced_target_references
    try:
        validate_announced_target_references(data['action_targets'], data['target_references'])
    except (KeyError, TypeError, ValueError):
        _reject()
    chosen = data['chosen']
    if type(chosen) is not dict or set(chosen) != {f.name for f in fields(CostOption)}:
        _reject()
    for field in fields(CostOption):
        value = chosen[field.name]
        expected = str if field.default is MISSING else type(field.default)
        if expected is type(None):
            expected = int if field.name in {'kicker_count', 'graveyard_permission_max_mana_value'} else str
            if value is None:
                continue
        if type(value) is not expected or expected is int and value < 0:
            _reject()
    for key in ('escape_ids', 'escape_selected'):
        ids = data[key]
        if key == 'escape_selected' and ids is None:
            continue
        if (type(ids) is not list or any(type(cid) is not str or cid not in state.cards for cid in ids)
                or len(set(ids)) != len(ids)):
            _reject()
    for key in ('face_card', 'printed_face_card'):
        raw = data[key]
        try:
            if (type(raw) is not dict or raw.get('id') != source
                    or _plain(_card_snapshot(_card_from_snapshot(raw, state.players))) != raw):
                _reject()
        except (KeyError, TypeError, ValueError, AttributeError):
            _reject()
    _plain(data)


def _validate_cast_payment(state, origin, frame):
    if (set(frame) != {'tag', 'phase', 'payer', 'data'} or frame['phase'] != 'produce'
            or type(frame['payer']) is not int or frame['payer'] != origin['actor']
            or type(frame['data']) is not dict):
        _reject()
    data = frame['data']
    if (set(data) != {'req', 'steps', 'cursor', 'in_flight', 'paid_prefix', 'resource_plan',
            'context', 'reserved_card_ids', 'protected_life', 'life_paid', 'postcondition', 'snow_spent'}
            or type(data['req']) is not dict
            or set(data['req']) != {'generic', 'W', 'U', 'B', 'R', 'G', 'C', 'S', 'life'}
            or any(not _integer(n) for n in data['req'].values())
            or not _outputs(data['snow_spent']) or sum(data['snow_spent'].values()) != data['req']['S']
            or not _integer(data['protected_life'])
            or type(data['life_paid']) is not bool or not data['life_paid']
            or type(data['in_flight']) is not bool or not data['in_flight']
            or type(data['steps']) is not list or not _integer(data['cursor'])
            or not data['cursor'] < len(data['steps'])
            or type(data['paid_prefix']) is not list or len(data['paid_prefix']) != data['cursor']
            or type(data['context']) is not list or len(data['context']) != 2
            or data['context'][0] != 'spell' or type(data['context'][1]) is not list
            or any(type(t) is not str for t in data['context'][1])
            or type(data['reserved_card_ids']) is not list
            or any(type(cid) is not str or cid not in state.cards for cid in data['reserved_card_ids'])
            or len(set(data['reserved_card_ids'])) != len(data['reserved_card_ids'])):
        _reject()
    ids = set()
    for index, step in enumerate(data['steps']):
        if (type(step) is not dict or set(step) != {'kind', 'source', 'selector',
                'ability_index', 'excluded_sources', 'amount', 'spec'}
                or type(step['kind']) is not str or step['kind'] not in {'paid', 'free'}
                or not _reference_shape(state, step['source'])
                or step['source']['controller'] != frame['payer']
                or step['source']['zone'] != 'battlefield'
                or (step['kind'] == 'free' and step['source']['card_id'] in ids)
                or type(step['selector']) is not str or not step['selector']
                or not _integer(step['amount'])
                or type(step['excluded_sources']) is not list
                or any(type(cid) is not str for cid in step['excluded_sources'])
                or step['ability_index'] is not None and not _integer(step['ability_index'])):
            _reject()
        if step['kind'] == 'free':
            ids.add(step['source']['card_id'])
        if index >= data['cursor'] and reference(state.cards[step['source']['card_id']]) != step['source']:
            _reject()
        if step['kind'] == 'paid':
            if step['ability_index'] is None or step['amount'] != 0 or step['spec'] is not None:
                _reject()
        elif index <= data['cursor']:
            if (type(step['spec']) is not list or len(step['spec']) != 3
                    or type(step['spec'][0]) is not int or step['spec'][0] != step['ability_index']
                    or any(type(s) is not str for s in step['spec'][1:]) or step['amount'] == 0):
                _reject()
        elif step['spec'] is not None or step['ability_index'] is not None or step['amount'] == 0:
            _reject()
    for index, row in enumerate(data['paid_prefix']):
        if (type(row) is not dict or set(row) != {'source', 'pool_after', 'snow_after'}
                or not _reference_shape(state, row['source'])
                or row['source'] != data['steps'][index]['source']
                or not _outputs(row['pool_after']) or not _outputs(row['snow_after'])):
            _reject()
    resource = data['resource_plan']
    if resource is not None:
        if (type(resource) is not dict or set(resource) != {'source_card_id', 'requirements',
                'remaining_items', 'delve', 'convoke', 'improvise'}
                or type(resource['source_card_id']) is not str or resource['source_card_id'] not in state.cards):
            _reject()
        for key in ('requirements', 'remaining_items'):
            if (type(resource[key]) is not list or any(type(row) is not list or len(row) != 2
                    or type(row[0]) is not str or row[0] not in data['req']
                    or not _integer(row[1]) for row in resource[key])
                    or len({row[0] for row in resource[key]}) != len(resource[key])):
                _reject()
        if (any(type(resource[key]) is not list or any(type(cid) is not str or cid not in state.cards
                    for cid in resource[key]) for key in ('delve', 'improvise'))
                or type(resource['convoke']) is not list or any(type(row) is not list or len(row) != 2
                    or type(row[0]) is not str or row[0] not in state.cards
                    or type(row[1]) is not str
                    or row[1] not in {'generic', 'W', 'U', 'B', 'R', 'G'} for row in resource['convoke'])):
            _reject()
    if data['postcondition'] is not None:
        from rules_engine.spell_cost_witness import restore_payment_condition
        try:
            condition = restore_payment_condition(data['postcondition'])
            if condition.recipe['player_id'] != frame['payer'] or condition.recipe['card_id'] not in state.cards:
                _reject()
        except (TypeError, ValueError, KeyError):
            _reject()


def action_boundary(function):
    @wraps(function)
    def run(rules, state, player_id, action, **kwargs):
        if state.mana_continuation is not None:
            validate(state, state.mana_continuation)
        existing = _SESSION.get()
        if existing is not None and existing['state'] is state:
            return function(rules, state, player_id, action, **kwargs)
        session = {'state': state, 'origin': _origin(state, player_id, action.get('type', '')), 'frames': []}
        token = _SESSION.set(session)
        if action.get('type') in _MANUAL:
            session['frames'].append({'tag': 'owner', 'op': 'single_mana',
                'phase': 'activation', 'payer': player_id, 'stage': _stage(state),
                'data': {'route': action['type'], 'source': action['card_id'],
                         'return_priority': player_id, 'output': {}}})
        try:
            try:
                result = function(rules, state, player_id, action, **kwargs)
                if state.mana_continuation is not None:
                    # The real damage batch may have queued its next replacement.
                    state.mana_continuation['waiting'] = _waiting(
                        state, state.mana_continuation['frames'])
                    validate(state, state.mana_continuation)
                return result
            except ManaPaymentPaused:
                _freeze(state)
                return None
        finally:
            _SESSION.reset(token)
    return run


@contextmanager
def activation(state, player_id, source_id, ability_index, color):
    session = _SESSION.get()
    if session is None or session['state'] is not state:
        yield None
        return
    frame = {'tag': 'mana_activation', 'phase': 'cost', 'payer': player_id,
             'source': reference(state.cards[source_id]), 'ability_index': ability_index,
             'color': color, 'output': {}, 'captured_bonus': [], 'bonus_cursor': 0}
    session['frames'].append(frame)
    try:
        yield frame
    except ManaPaymentPaused:
        raise
    else:
        session['frames'].pop()


def linked_damage(state, player_id, source_id, amount, output):
    session = _SESSION.get()
    if session is not None and session['state'] is state and session['frames']:
        frame = session['frames'][-1]
        frame.update(phase='linked_damage', output=dict(output))
        if session['frames'][0].get('op') == 'single_mana':
            session['frames'][0]['data']['output'] = dict(output)
    from effects.handlers import deal_damage_batch
    deal_damage_batch(state, player_id, {'recipients': [
        {'target_player': player_id, 'amount': amount}], '__source_card_id': source_id})
    if state.pending_replacement_choice or state.pending_mechanic_choice:
        raise ManaPaymentPaused()


def activation_outcomes(state, player_id, source_id, ability_index, selector, **context):
    """Explore real choices on a payment trial, never on an authoritative root."""
    from game_state.copying import copy_match_state
    from rules_engine.action_validation import ActionRejected
    from rules_engine.engine import RulesEngine
    from rules_engine.mana_abilities import activate_planned_mana_ability
    session = {'state': state, 'origin': _origin(state, player_id, 'activate_mana_ability'),
               'frames': [{'tag': 'owner', 'op': 'single_mana', 'phase': 'activation',
                           'payer': player_id, 'stage': _stage(state), 'data': {
                               'route': 'activate_mana_ability', 'source': source_id,
                               'return_priority': state.priority_player, 'output': {}}}]}
    token = _SESSION.set(session)
    try:
        try:
            if not activate_planned_mana_ability(state, player_id, source_id, ability_index, selector, **context):
                return
        except ManaPaymentPaused:
            _freeze(state)
    finally:
        _SESSION.reset(token)
    frontier = [(state, None)]
    while frontier:
        candidate, options = frontier[-1]
        pending = candidate.pending_replacement_choice
        if pending is None:
            frontier.pop()
            yield candidate
            continue
        if candidate.mana_continuation is None:
            frontier.pop()
            continue
        if options is None:
            options = iter(pending['options'])
            frontier[-1] = (candidate, options)
        try:
            option = next(options)
        except StopIteration:
            frontier.pop()
            continue
        branch = copy_match_state(candidate)
        purpose = _FEASIBILITY.set(True)
        try:
            RulesEngine().take_action(branch, pending['player_id'], {
                'type': 'choose_replacement', 'replacement_source_id': option['source_id']},
                reject_invalid=True)
        except ActionRejected:
            continue
        finally:
            _FEASIBILITY.reset(purpose)
        frontier.append((branch, None))


def bulk_mana(state, player_id, action):
    from rules_engine.action_validation import validate_tap
    from rules_engine.mana import land_can_produce_mana, land_mana_colors, land_mana_amount
    from rules_engine.mana_abilities import preferred_free_spec
    validate_tap(state, player_id, action)
    roster = []
    for cid in state.players[player_id].battlefield:
        card = state.cards[cid]
        if (len(roster) >= action['count'] or card.name.strip().lower() != action['land_name'].strip().lower()
                or not land_can_produce_mana(state, cid, free_only=False)):
            continue
        colors = land_mana_colors(card, state)
        if action.get('color') and action['color'] not in colors:
            continue
        color = action.get('color') or next(c for c in 'UBRGWC' if c in colors)
        amount = land_mana_amount(state, player_id, cid, color)
        spec = preferred_free_spec(state, card, color, amount, tap_only=True)
        if spec is None:
            _reject()
        roster.append({'source': reference(card), 'ability_index': spec[0],
                       'color': color, 'amount': amount})
    if len(roster) != action['count']:
        _reject()
    frame = {'tag': 'owner', 'op': 'bulk_mana', 'phase': 'activation',
             'payer': player_id, 'stage': _stage(state), 'data': {
                 'roster': roster, 'requested_count': action['count'], 'cursor': 0,
                 'return_priority': state.priority_player, 'label': action['land_name']}}
    _SESSION.get()['frames'].append(frame)
    _finish_bulk(state, frame)
    _SESSION.get()['frames'].pop()


def _finish_bulk(state, frame):
    from rules_engine.mana_abilities import activate_mana_ability
    from rules_engine.state_based_actions import apply_state_based_actions
    data = frame['data']
    while data['cursor'] < data['requested_count'] and state.winner is None:
        row = data['roster'][data['cursor']]
        card = state.cards.get(row['source']['card_id'])
        if card is None or reference(card) != row['source']:
            _reject()
        if not activate_mana_ability(state, frame['payer'], card.id, row['ability_index'], row['color']):
            _reject()
        data['cursor'] += 1
        apply_state_based_actions(state)
    if state.winner is None:
        total = sum(row['amount'] for row in data['roster'])
        color = data['roster'][-1]['color']
        state.log.append(f"{state.players[frame['payer']].name} taps {data['requested_count']}x "
                         f"{data['label']} for {total} {color}.")


def resume(state, pending):
    value = validate(state, state.mana_continuation, pending=pending)
    session = {'state': state, 'origin': value['origin'], 'frames': value['frames']}
    token = _SESSION.set(session)
    try:
        if len(value['frames']) == 3:
            _resume_prepared_cast(state, session)
            return
        from rules_engine.mana_triggers import resolve_mana_triggers
        activation_frame = session['frames'].pop()
        resolve_mana_triggers(state, activation_frame['captured_bonus'])
        owner = session['frames'][-1]
        if owner['op'] == 'bulk_mana':
            owner['data']['cursor'] += 1
            from rules_engine.state_based_actions import apply_state_based_actions
            apply_state_based_actions(state)
            _finish_bulk(state, owner)
        else:
            data = owner['data']
            if data['route'] == 'tap_land_for_mana':
                source = state.cards[data['source']]
                color = activation_frame['color']
                state.log.append(f"{state.players[owner['payer']].name} taps {source.name} for "
                                 f"{activation_frame['output'].get(color, 0)} {color}.")
        state.mana_continuation = None
        from rules_engine.state_based_actions import apply_state_based_actions
        if owner['op'] != 'bulk_mana' and not _FEASIBILITY.get():
            apply_state_based_actions(state)
        if not (state.pending_replacement_choice or state.pending_mechanic_choice or state.pending_trigger_order):
            state.priority_player = owner['data']['return_priority']
            state.passed_priority = set()
    except ManaPaymentPaused:
        _freeze(state)
    finally:
        _SESSION.reset(token)


def _resume_prepared_cast(state, session):
    from rules_engine.mana_triggers import resolve_mana_triggers
    from rules_engine.mana import _completed_cast_mana_step, _resume_cast_payment
    from rules_engine.engine import _finish_prepared_cast
    from rules_engine.state_based_actions import apply_state_based_actions
    activation_frame = session['frames'].pop()
    resolve_mana_triggers(state, activation_frame['captured_bonus'])
    owner, payment = session['frames']
    _completed_cast_mana_step(state, payment)
    if not _resume_cast_payment(state, owner, payment):
        _reject()
    session['frames'].pop()
    if reference(state.cards[owner['data']['source']['card_id']]) != owner['data']['source']:
        _reject()
    if not _finish_prepared_cast(state, owner['payer'], owner['data'], stage=owner['stage']):
        _reject()
    state.mana_continuation = None
    if not owner['data']['effect_cast'] and not _FEASIBILITY.get():
        apply_state_based_actions(state)
