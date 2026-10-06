"""Preserve a witnessed answer to a public lethal tail, not guessed replies."""
from ai.action_contract import complete_action
from ai.information import is_unknown
from ai.pending_effects import _projection_copy, _unanswered_action_outcome, settled_public_position
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine


def _response_window(state, player_id):
    # Match the existing announced-stack projection bound. A choice/loop is
    # unknown, never an invented ordering or a fabricated priority window.
    for _ in range(128):
        if (state.winner is not None or not state.stack or state.pending_trigger_order
                or state.pending_mechanic_choice or state.pending_replacement_choice):
            return None
        top = state.stack[-1]
        if top.controller != player_id:
            if state.priority_player == player_id:
                return state
        elif top.effect_key not in {'draw_cards', 'cycle_draw', 'deal_damage', 'gain_life', 'lose_life'}:
            return None
        elif any(not is_unknown(state.cards[cid]) for cid in state.players[player_id].library):
            return None
        try:
            state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
        except (ActionRejected, KeyError, StopIteration):
            return None
    return None


def _settled(state, player_id):
    if any(item.effect_key == 'noop' or any(key.startswith('__unsupported') for key in item.payload)
           for item in state.stack):
        return None
    try:
        result = settled_public_position(state, player_id)
    except (ActionRejected, KeyError, StopIteration):
        return None
    if result is None or any('Unsupported' in line or 'Oracle effect not inferred' in line for line in result.log):
        return None
    return result


def _responses(state, player_id, retained):
    threat = state.stack[-1].id
    for move in RulesEngine().legal_moves(state, player_id):
        if move['type'] not in {'cast_spell', 'activate_ability'} or move.get('card_id') not in retained:
            continue
        hints = move.get('target_hints') or {}
        targets = [{}]
        if any(target['id'] == threat for target in hints.get('stack_targets', [])):
            targets.append({'target_stack_id': threat})
        targets.extend({'target_player': target['id']} for target in hints.get('player_targets', []))
        public_cards = {target['id'] for key, values in hints.items() if key.endswith('_targets')
                        and key not in {'stack_targets', 'player_targets'} and isinstance(values, list)
                        for target in values if isinstance(target, dict) and 'id' in target
                        and target['id'] in state.cards and not is_unknown(state.cards[target['id']])}
        targets.extend({'target_card_id': cid} for cid in sorted(public_cards))
        options = move.get('cost_options', []) if move['type'] == 'cast_spell' else [None]
        for option in options:
            for selected in targets:
                intent = {**move, 'targets': selected}
                if option is not None:
                    intent['cost_choice'] = {'id': option['id']}
                try:
                    action = complete_action(intent)
                    answered = checked_action(state, RulesEngine(), player_id, action)
                except (ActionRejected, KeyError, StopIteration):
                    continue
                if any(item.effect_key == 'noop' or any(key.startswith('__unsupported') for key in item.payload)
                       for item in answered.stack):
                    continue
                # Explicit decline belongs to this existence witness only;
                # incomplete targets/modes and other choices remain unknown.
                try:
                    outcome = _unanswered_action_outcome(answered, player_id, {'type': 'pass_priority'},
                                                        own_choice_action=_decline_may)
                except (ActionRejected, KeyError, StopIteration):
                    continue
                if outcome in {'neutral', 'win'}:
                    yield action


def _decline_may(state, moves, player_id):
    return next((move for move in moves if move['type'] == 'choose_optional_effect' and not move['accept']),
                {'type': 'pass_priority'})


def preserve_lethal_response(state, choices, player_id):
    """Return decline only with a real defense certificate lost by payment.

    Other response grammars/choices remain unqualified. This is not an
    exhaustive proof that no conceivable newly drawn answer exists.
    """
    if getattr(state, 'ai_information_player', None) != player_id:
        return None
    decline = next((move for move in choices if move['type'] == 'choose_optional_effect' and not move['accept']), None)
    accept = next((move for move in choices if move['type'] == 'choose_optional_effect' and move['accept']), None)
    if decline is None or accept is None:
        return None
    item = next((item for item in state.stack if item.id == accept['stack_id']), None)
    if item is None or not item.payload.get('__optional_payment_cost'):
        return None
    try:
        no = checked_action(_projection_copy(state), RulesEngine(), player_id, decline)
        yes = checked_action(_projection_copy(state), RulesEngine(), player_id, accept)
    except ActionRejected:
        return None
    no, yes = _response_window(no, player_id), _response_window(yes, player_id)
    if no is None or yes is None or no.stack[-1].id != yes.stack[-1].id:
        return None
    unanswered = _settled(yes, player_id)
    if unanswered is None or unanswered.winner != 3-player_id:
        return None  # The reward itself may avert lethal; do not always decline.
    retained = set(state.players[player_id].hand + state.players[player_id].battlefield)
    witnesses = list(_responses(no, player_id, retained))
    if not witnesses or next(_responses(yes, player_id, retained), None) is not None:
        return None
    for action in witnesses:
        try:
            checked_action(yes, RulesEngine(), player_id, action)
        except ActionRejected:
            return decline
    return None
