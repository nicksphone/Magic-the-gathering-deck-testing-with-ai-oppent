"""Durable casts authorized during an effect, using ordinary announcements."""
from game_state.state import Zone


def _selected_trigger_target_is_current(state, controller, payload):
    """Generic permissions stay unsealed; selected trigger objects cannot rebind."""
    markers = ('__trigger_target_choice', '__trigger_target_clause', '__trigger_event')
    selected = any(key in payload for key in markers)
    if not selected and '__trigger_target_reference' not in payload:
        return True
    if selected and not (payload.get('__trigger_target_choice') is True
            and all(isinstance(payload.get(key), str) and payload[key].strip()
                    for key in markers[1:])):
        return False
    reference = payload.get('__trigger_target_reference')
    if not (type(reference) is list and len(reference) == 2
            and all(type(value) is int and value >= 0 for value in reference)):
        return False
    target = payload.get('target_card_id')
    card = state.cards.get(target) if isinstance(target, str) else None
    from game_state.state import object_incarnation
    return (card is not None and target in state.players[controller].graveyard
            and card.zone == Zone.GRAVEYARD
            and reference == [object_incarnation(card), card.zone_change_sequence])


def materialize_cast(state, controller, card_id, targets=None):
    from ai.agent import AIAgent
    from rules_engine.cast_choice import build_cast_hints
    card = state.cards[card_id]
    targets = dict(targets or {})
    if '{x}' in (card.mana_cost or '').lower():
        targets['x_value'] = 0
    from rules_engine.cast_choice import available_cast_options_and_hints
    from rules_engine.move_generator import _cost_option_view
    costs, hints = available_cast_options_and_hints(state, card, controller, without_mana=True)
    return AIAgent(difficulty='strong')._materialize_action(state, {
        'type': 'cast_spell', 'card_id': card_id, 'from_graveyard': True,
        'target_hints': hints, 'targets': targets,
        'cost_options': [_cost_option_view(option, state, controller, card_id) for option in costs],
    }, controller, allow_zero_x=True)


def admit_cast(state, controller, action, payload):
    from ai.pending_effects import planning_copy
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import require
    require(_selected_trigger_target_is_current(state, controller, payload),
            'The selected graveyard object is no longer available')
    target = payload['target_card_id']
    require(action.get('type') == 'cast_spell' and action.get('card_id') == target,
            'This permission authorizes only the selected spell')
    require(target in state.players[controller].graveyard and state.cards[target].zone == Zone.GRAVEYARD,
            'The selected spell is no longer in your graveyard')
    require(bool(action.get('from_graveyard')) and not action.get('from_exile') and not action.get('from_library'),
            'This permission is bound to the graveyard')
    require(not action.get('_invalid_ai_choice'), 'No supported casting choice')
    rules = RulesEngine()
    projected = planning_copy(state)
    rules.take_action(projected, controller, action, reject_invalid=True, effect_cast=True)
    require(projected.cards[target].zone == Zone.STACK, 'Casting requires an unsupported continuation')
    rules.take_action(state, controller, action, reject_invalid=True, effect_cast=True)
    from rules_engine.targeting import stack_object_kind
    item = next(item for item in reversed(state.stack) if item.source_card_id == target and item.controller == controller
                and stack_object_kind(state, item) == 'spell')
    if payload.get('exile_after_cast'):
        item.payload['__exile_instead_of_graveyard'] = True
    state.log.append(f'{state.players[controller].name} casts {state.cards[target].name} from the graveyard without paying its mana cost.')


def _cast_candidates(state, controller, payload):
    if 'card_references' not in payload:
        return ([payload['target_card_id']]
                if _selected_trigger_target_is_current(state, controller, payload) else [])
    from game_state.state import object_incarnation
    from rules_engine.colors import card_color_names
    from rules_engine.type_effects import effective_types
    from rules_engine.zone_actions import is_departed_token
    return [cid for cid, reference in payload['card_references'].items()
            if cid in state.players[controller].graveyard and cid in state.cards
            and state.cards[cid].zone == Zone.GRAVEYARD
            and not is_departed_token(state.cards[cid])
            and reference == [object_incarnation(state.cards[cid]), state.cards[cid].zone_change_sequence]
            and {'Instant', 'Sorcery'} & set(effective_types(state, state.cards[cid]))
            and (payload['color'] in card_color_names(state.cards[cid], state)
                 or payload['color'] == 'colorless' and not card_color_names(state.cards[cid], state))]


def cast_moves(state, player_id):
    pending = state.pending_mechanic_choice
    if pending['player_id'] != player_id:
        return []
    moves = [{'type': 'choose_mechanic', **pending,
              'option_labels': {'decline': 'Decline casting'}}]
    from rules_engine.cast_choice import build_cast_hints, has_available_targets_for_action
    from rules_engine.cast_choice import available_cast_options_and_hints
    from rules_engine.restrictions import can_cast_in_current_timing
    from rules_engine.move_generator import _cost_option_view
    from game_state.serializers import serialize_card_view
    for target in _cast_candidates(state, player_id, pending['effect_payload']):
        if target not in state.players[player_id].graveyard:
            continue
        card = state.cards[target]
        costs, hints = available_cast_options_and_hints(state, card, player_id, without_mana=True)
        if '{x}' in (card.mana_cost or '').lower():
            hints['x_value_max'] = 0
        if costs and has_available_targets_for_action(hints) and can_cast_in_current_timing(state, card, player_id, during_resolution=True)[0]:
            moves.append({'type': 'cast_spell', 'card_id': target, 'card_name': card.name,
                          'from_graveyard': True, 'card_view': serialize_card_view(state, target),
                          'mana_cost': '', 'cost_options': [_cost_option_view(option, state, player_id, target) for option in costs],
                          'target_hints': hints})
    return moves


def finish_cast_choice(state, player_id, action):
    pending = state.pending_mechanic_choice
    if pending['player_id'] != player_id:
        return False
    if action.get('type') == 'choose_mechanic':
        if action.get('card_ids') != ['decline']:
            return False
        state.pending_mechanic_choice = None
        state.log.append(f'{state.players[player_id].name} declines casting from the graveyard.')
    elif action.get('type') == 'cast_spell':
        from rules_engine.action_validation import require
        require(_selected_trigger_target_is_current(state, player_id, pending['effect_payload']),
                'The selected graveyard object is no longer available')
        state.pending_mechanic_choice = None
        try:
            payload = pending['effect_payload']
            if 'card_references' in payload:
                require(action.get('card_id') in _cast_candidates(state, player_id, payload),
                        'The selected graveyard object is no longer permitted')
                payload = {**payload, 'target_card_id': action['card_id']}
            admit_cast(state, player_id, action, payload)
        except (ValueError, KeyError):
            state.pending_mechanic_choice = pending
            raise
        if 'card_references' in payload:
            remaining = {**pending['effect_payload'], 'card_references': {
                cid: reference for cid, reference in payload['card_references'].items()
                if cid != action['card_id']
            }}
            if _cast_candidates(state, player_id, remaining):
                state.pending_mechanic_choice = {**pending, 'effect_payload': remaining}
                state.priority_player = player_id
                state.passed_priority = set()
                return True
    else:
        return False
    from rules_engine.stack_engine import resume_paused_resolution
    resume_paused_resolution(state, pending)
    return True
