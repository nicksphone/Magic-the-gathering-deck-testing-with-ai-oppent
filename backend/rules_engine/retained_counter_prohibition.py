"""Resolved all-counter prohibitions bound to continuous object incarnations."""
from copy import deepcopy

from game_state.state import Zone, allocate_effect_timestamp, object_incarnation


def reference(card):
    return {'card_id': card.id, 'incarnation': object_incarnation(card),
            'zone_change_sequence': card.zone_change_sequence}


def _valid_reference(value):
    return (isinstance(value, dict)
            and set(value) == {'card_id', 'incarnation', 'zone_change_sequence'}
            and isinstance(value['card_id'], str) and 1 <= len(value['card_id']) <= 100
            and all(type(value[key]) is int and value[key] >= 0
                    for key in ('incarnation', 'zone_change_sequence')))


def snapshot(records):
    if not isinstance(records, list):
        raise ValueError('Invalid retained counter prohibition store')
    seen = set()
    for row in records:
        if not isinstance(row, dict):
            raise ValueError('Invalid retained counter prohibition record')
        kind = row.get('target_kind')
        keys = {'version', 'origin', 'effect_id', 'trigger_controller', 'source_ref',
                'target_kind', 'created_timestamp', 'target_ref' if kind == 'card' else 'target_player'}
        if (set(row) != keys or type(row.get('version')) is not int or row['version'] != 1
                or row.get('origin') != 'resolved_counter_prohibition'
                or not isinstance(row.get('effect_id'), str) or not 1 <= len(row['effect_id']) <= 100
                or row['effect_id'] in seen
                or type(row.get('trigger_controller')) is not int or row['trigger_controller'] not in (1, 2)
                or type(row.get('created_timestamp')) is not int or row['created_timestamp'] < 0
                or not _valid_reference(row.get('source_ref'))
                or kind not in ('card', 'player')
                or kind == 'card' and not _valid_reference(row.get('target_ref'))
                or kind == 'player' and (type(row.get('target_player')) is not int or row['target_player'] not in (1, 2))):
            raise ValueError('Invalid retained counter prohibition record')
        seen.add(row['effect_id'])
    return deepcopy(records)


def current(state, ref):
    if not _valid_reference(ref):
        return False
    card = state.cards.get(ref['card_id'])
    return (card is not None and card.zone == Zone.BATTLEFIELD and reference(card) == ref
            and any(card.id in player.battlefield for player in state.players.values()))


def forbidden(state, *, target_card_id=None, target_player=None):
    for row in state.retained_counter_prohibitions:
        if not current(state, row['source_ref']):
            continue
        if row['target_kind'] == 'player':
            if target_player == row['target_player']:
                return True
        elif (target_card_id == row['target_ref']['card_id']
              and current(state, row['target_ref'])):
            return True
    return False


def resolve(state, controller, payload):
    kind = payload.get('__counter_target_kind')
    if kind == 'card':
        card = state.cards.get(payload.get('target_card_id'))
        ref = payload.get('__trigger_target_reference')
        if (card is None or card.zone != Zone.BATTLEFIELD
                or ref != [object_incarnation(card), card.zone_change_sequence]):
            return
        for key in list(card.counters):
            if not key.startswith('__') or key == '__lore':
                del card.counters[key]
        for key in list(card.counter_timestamps):
            if not key.startswith('__') or key == '__lore':
                del card.counter_timestamps[key]
        if card.loyalty is not None:
            card.loyalty = 0
        target = {'target_ref': reference(card)}
    elif kind == 'player':
        player = state.players.get(payload.get('target_player'))
        if player is None or player.id == controller:
            return
        player.counters.clear()
        player.poison = 0
        target = {'target_player': player.id}
    else:
        return
    source_ref = payload.get('__counter_source_ref')
    if current(state, source_ref):
        state.retained_counter_prohibitions.append({
            'version': 1, 'origin': 'resolved_counter_prohibition',
            'effect_id': state.allocate_object_id(), 'trigger_controller': controller,
            'source_ref': deepcopy(source_ref), 'target_kind': kind, **target,
            'created_timestamp': allocate_effect_timestamp(state),
        })
