"""Private, ordered library choices with one final atomic reordering."""
import re

from game_state.state import Zone


def cast_surveillance_clause(line):
    match = re.fullmatch(r'whenever you cast (a spell|a noncreature spell), surveil (\d+)\.', line.strip().lower())
    return int(match[2]) if match else None


def surveil_payoff(line):
    """Recognize complete payoff clauses; never promote arbitrary conditions."""
    match = re.fullmatch(r'whenever you surveil( for the first time each turn)?, (.+)\.', line.strip().lower())
    if not match:
        return None
    body = match[2]
    counter = re.fullmatch(r'put (a|one|\d+) \+1/\+1 counters? on this creature', body)
    if counter:
        return {'kind': 'counter', 'amount': int(counter[1]) if counter[1].isdigit() else 1, 'once': bool(match[1])}
    if re.fullmatch(r"return this (?:creature|artifact|enchantment|permanent) to its owner's hand", body):
        return {'kind': 'return', 'once': bool(match[1])}
    drain = re.fullmatch(r'this (?:creature|artifact|enchantment|permanent) deals (\d+) damage to each opponent and you gain (\d+) life', body)
    if drain:
        return {'kind': 'drain', 'damage': int(drain[1]), 'life': int(drain[2]), 'once': bool(match[1])}
    return None


def scry(state, controller, payload):
    _inspect(state, controller, payload, 'scry')


def surveil(state, controller, payload):
    _inspect(state, controller, payload, 'surveil')


def _inspect(state, controller, payload, kind):
    amount = max(0, int(payload.get('amount', 0)))
    library = state.players[controller].library
    top = library[-amount:] if amount else []
    if not top:
        if kind == 'surveil' and amount:
            from rules_engine.events import emit_event
            emit_event(state, 'surveilled', {'player_id': controller, 'amount': amount, 'inspected': 0})
        return
    state.pending_mechanic_choice = {
        'kind': kind, 'player_id': controller, 'controller': controller,
        'options': list(reversed(top)), 'count': len(top), 'min_count': 0,
        'top_ids': list(top), 'amount': amount,
        'label': ('Choose any cards for your graveyard, bottommost first; choose none to keep all'
                  if kind == 'surveil' else 'Choose any cards to put on the bottom, bottommost first; choose none to keep all'),
    }
    state.priority_player = controller
    state.passed_priority = set()


def finish_scry(state, player_id, action):
    pending = state.pending_mechanic_choice
    ids = action.get('card_ids')
    if (pending['player_id'] != player_id or not isinstance(ids, list)
            or any(not isinstance(cid, str) for cid in ids) or len(set(ids)) != len(ids)
            or any(cid not in pending['options'] for cid in ids)):
        return False
    library = state.players[player_id].library
    top = pending['top_ids']
    if (library[-len(top):] != top or any(cid not in state.cards or state.cards[cid].zone != Zone.LIBRARY for cid in top)):
        return False
    surveilling = pending['kind'] in {'surveil', 'surveil_top_order'}
    if pending['kind'] in {'scry', 'surveil'}:
        retained = [cid for cid in reversed(top) if cid not in ids]
        if len(retained) > 1:
            state.pending_mechanic_choice = {
                **pending, 'kind': 'surveil_top_order' if surveilling else 'scry_top_order', 'options': retained,
                'count': len(retained), 'min_count': len(retained), 'bottom_ids': list(ids),
                'label': 'Order the remaining cards, topmost first',
            }
            return True
        bottom = ids
        ordered_top = retained
    else:
        if set(ids) != set(pending['options']):
            return False
        bottom = pending['bottom_ids']
        ordered_top = ids
    library[:] = [*library[:-len(top)], *reversed(ordered_top)]
    if surveilling:
        from rules_engine.zone_actions import put_into_graveyard
        for cid in bottom:
            put_into_graveyard(state, cid)
    else:
        library[:0] = bottom
    state.pending_mechanic_choice = None
    state.log.append(f'{state.players[player_id].name} surveils {len(top)}, choosing {len(bottom)} for the graveyard.'
                     if surveilling else f'{state.players[player_id].name} scries {len(top)}, putting {len(bottom)} on the bottom.')
    from rules_engine.events import emit_event
    emit_event(state, 'surveilled' if surveilling else 'scried', {
        'player_id': player_id, 'amount': pending.get('amount', len(top)), 'inspected': len(top),
    })
    from rules_engine.stack_engine import resume_paused_resolution
    resume_paused_resolution(state, pending)
    return True
