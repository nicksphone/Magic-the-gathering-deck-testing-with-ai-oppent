"""Private, ordered library choices with one final atomic reordering."""


def scry(state, controller, payload):
    amount = max(0, int(payload.get('amount', 0)))
    library = state.players[controller].library
    top = library[-amount:] if amount else []
    if not top:
        return
    state.pending_mechanic_choice = {
        'kind': 'scry', 'player_id': controller, 'controller': controller,
        'options': list(reversed(top)), 'count': len(top), 'min_count': 0,
        'top_ids': list(top),
        'label': 'Choose any cards to put on the bottom, bottommost first; choose none to keep all',
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
    if library[-len(top):] != top:
        return False
    if pending['kind'] == 'scry':
        retained = [cid for cid in reversed(top) if cid not in ids]
        if len(retained) > 1:
            state.pending_mechanic_choice = {
                **pending, 'kind': 'scry_top_order', 'options': retained,
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
    library[:] = [*bottom, *library[:-len(top)], *reversed(ordered_top)]
    state.pending_mechanic_choice = None
    state.log.append(f'{state.players[player_id].name} scries {len(top)}, putting {len(bottom)} on the bottom.')
    from rules_engine.events import emit_event
    emit_event(state, 'scried', {'player_id': player_id, 'amount': len(top)})
    from rules_engine.stack_engine import resume_paused_resolution
    resume_paused_resolution(state, pending)
    return True
