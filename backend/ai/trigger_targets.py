"""Rank announced targets using an isolated, actual public trigger effect."""
from ai.heuristics import evaluate_board
from ai.pending_effects import _projection_copy
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def target_value(state, action, player_id):
    from rules_engine.action_validation import ActionRejected, checked_action
    before = evaluate_board(state, player_id)
    projected = _projection_copy(state)
    original_ids = {item.id for item in state.stack}
    try:
        projected = checked_action(projected, RulesEngine(), player_id, action)
    except (ActionRejected, StopIteration, KeyError):
        return None
    if action['type'] == 'choose_trigger_target':
        selected = next((item for item in projected.stack if item.id == action['stack_id']), None)
        if selected is None or any(item.id not in original_ids for item in projected.stack):
            return None  # Newly triggered ward/other responses are not silently removed.
        # Rank this effect, not an invented ordering of the rest of the stack.
        projected.stack = [selected]
        projected.pending_trigger_order = None
        projected.trigger_staging = False
        projected.staged_triggers = []
        if selected.payload.get('__may'):
            selected.payload.update({'__may_decided': True, '__may_choose': True})
        if not resolve_top_of_stack(projected):
            return None
    else:
        # Optional choices resolve as part of their checked action already.
        projected.stack = [item for item in projected.stack if item.id not in original_ids]
    if projected.winner is not None:
        return 1000000.0 if projected.winner == player_id else -1000000.0
    if (projected.pending_trigger_order or projected.pending_mechanic_choice
            or projected.pending_replacement_choice or projected.stack
            or any('Oracle effect not inferred' in line for line in projected.log)):
        return None
    return evaluate_board(projected, player_id) - before


def choose_target(state, choices, player_id):
    scored = [(target_value(state, action, player_id), action) for action in choices]
    known = [(value, action) for value, action in scored if value is not None]
    unknown = [action for value, action in scored if value is None]
    best = max(known, key=lambda row: row[0]) if known else None
    # Do not prefer a proved loss over an unresolved legitimate opportunity.
    if unknown and (best is None or best[0] <= 0):
        return unknown[0], False
    return (best[1], True) if best else (choices[0], False)
