"""Durable casts authorized during an effect, using ordinary announcements."""
from game_state.state import Zone


def validate_permission(state, controller, payload, *, action=None):
    """One validator binds transformed candidates and their actual admission."""
    if type(payload) is not dict or controller not in state.players:
        return False
    if 'permission_kind' not in payload:
        return _selected_trigger_target_is_current(state, controller, payload)
    if (set(payload) != {'permission_kind', 'target_card_id', 'reference', 'face_index'}
            or payload['permission_kind'] != 'battle_transformed'
            or type(payload['target_card_id']) is not str
            or type(payload['face_index']) is not int or payload['face_index'] != 1):
        return False
    reference = payload['reference']
    if (type(reference) is not dict or set(reference) != {'incarnation', 'zone_change_sequence'}
            or any(type(value) is not int or value < 0 for value in reference.values())):
        return False
    target = payload['target_card_id']; card = state.cards.get(target)
    from game_state.state import object_incarnation
    from rules_engine.card_types import is_token_card
    if (card is None or card.zone != Zone.EXILE or card.owner not in state.players
            or target not in state.players[card.owner].exile or card.exile_face_down
            or is_token_card(card) or card.layout not in {'transform', 'modal_dfc'}
            or len(card.card_faces) != 2
            or reference != {'incarnation': object_incarnation(card),
                             'zone_change_sequence': card.zone_change_sequence}):
        return False
    from rules_engine.card_faces import select_cast_face
    face = select_cast_face(card, 1, preserve_copy_effects=False)
    if 'Land' in face.types or not set(face.types).intersection(
            {'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Planeswalker', 'Sorcery'}):
        return False
    if action is not None:
        targets = action.get('targets') or {}
        if (action.get('type') != 'cast_spell' or action.get('card_id') != target
                or action.get('from_exile') is not True or action.get('from_graveyard') or action.get('from_library')
                or type(action.get('selected_face_index')) is not int or action['selected_face_index'] != 1
                or type(targets) is not dict
                or 'selected_face_index' in targets and (type(targets['selected_face_index']) is not int
                                                        or targets['selected_face_index'] != 1)
                or any(key in action for key in ('permission_kind', 'reference', 'face_index', 'effect_cast', 'suspend_cast'))):
            return False
    return True


def _permission_card(state, controller, target, payload):
    if not validate_permission(state, controller, payload):
        return None
    card = state.cards.get(target)
    if 'permission_kind' in payload:
        if target != payload['target_card_id']:
            return None
        from rules_engine.card_faces import select_cast_face
        return select_cast_face(card, 1, preserve_copy_effects=False)
    return card


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


def materialize_cast(state, controller, card_id, targets=None, *, permission=None):
    from ai.agent import AIAgent
    from ai.casting_resources import _automatic_effect_cost_scope
    permission = {'target_card_id': card_id} if permission is None else permission
    from rules_engine.action_validation import require
    card = _permission_card(state, controller, card_id, permission)
    require(card is not None, 'The effect casting permission is unavailable')
    targets = dict(targets or {})
    if '{x}' in (card.mana_cost or '').lower():
        targets['x_value'] = 0
    from rules_engine.cast_choice import available_cast_options_and_hints
    from rules_engine.move_generator import _cost_option_view
    costs, hints = available_cast_options_and_hints(state, card, controller, without_mana=True)
    with _automatic_effect_cost_scope(state, controller, card_id, permission=permission):
        return AIAgent(difficulty='strong')._materialize_action(state, {
            'type': 'cast_spell', 'card_id': card_id,
            **({'from_exile': True, 'selected_face_index': 1} if 'permission_kind' in permission
               else {'from_graveyard': True}),
            'target_hints': hints, 'targets': targets,
            'cost_options': [_cost_option_view(option, state, controller, card_id, cast_card=card)
                             for option in costs],
        }, controller, allow_zero_x=True)


def project_cast(state, controller, action, payload):
    """Check the exact effect permission and execute the announcement on a copy."""
    from ai.pending_effects import planning_copy
    from rules_engine.action_validation import require
    require(validate_permission(state, controller, payload, action=action),
            'The selected effect casting permission is no longer available')
    target = payload['target_card_id']
    require(action.get('type') == 'cast_spell' and action.get('card_id') == target,
            'This permission authorizes only the selected spell')
    transformed = 'permission_kind' in payload
    if not transformed:
        require(target in state.players[controller].graveyard and state.cards[target].zone == Zone.GRAVEYARD,
                'The selected spell is no longer in your graveyard')
        require(bool(action.get('from_graveyard')) and not action.get('from_exile') and not action.get('from_library'),
                'This permission is bound to the graveyard')
    require(not action.get('_invalid_ai_choice'), 'No supported casting choice')
    projected = planning_copy(state)
    _take_authorized_cast(projected, controller, action, payload)
    return projected


def _take_authorized_cast(state, controller, action, payload):
    from rules_engine.action_validation import require
    from rules_engine.engine import RulesEngine
    target = payload['target_card_id']
    transformed = 'permission_kind' in payload
    scope = {'effect_permission': payload} if transformed else {}
    RulesEngine().take_action(state, controller, action, reject_invalid=True, effect_cast=True, **scope)
    require(state.cards[target].zone == Zone.STACK, 'Casting requires an unsupported continuation')
    from rules_engine.targeting import stack_object_kind
    item = next(item for item in reversed(state.stack) if item.source_card_id == target and item.controller == controller
                and stack_object_kind(state, item) == 'spell')
    if payload.get('exile_after_cast'):
        item.payload['__exile_instead_of_graveyard'] = True
    origin = 'exile transformed' if transformed else 'the graveyard'
    state.log.append(f'{state.players[controller].name} casts {state.cards[target].name} from {origin} without paying its mana cost.')


def admit_cast(state, controller, action, payload):
    project_cast(state, controller, action, payload)
    _take_authorized_cast(state, controller, action, payload)


def _cast_candidates(state, controller, payload):
    if 'permission_kind' in payload:
        return [payload['target_card_id']] if validate_permission(state, controller, payload) else []
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
        payload = pending['effect_payload']
        transformed = 'permission_kind' in payload
        if not transformed and target not in state.players[player_id].graveyard:
            continue
        card = _permission_card(state, player_id, target, payload)
        if card is None:
            continue
        costs, hints = available_cast_options_and_hints(state, card, player_id, without_mana=True)
        if '{x}' in (card.mana_cost or '').lower():
            hints['x_value_max'] = 0
        if costs and has_available_targets_for_action(hints) and can_cast_in_current_timing(state, card, player_id, during_resolution=True)[0]:
            moves.append({'type': 'cast_spell', 'card_id': target, 'card_name': card.name,
                          **({'from_exile': True, 'selected_face_index': 1} if transformed else {'from_graveyard': True}),
                          'card_view': serialize_card_view(state, target, projected_card=card if transformed else None),
                          'mana_cost': '', 'cost_options': [_cost_option_view(option, state, player_id, target, cast_card=card) for option in costs],
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
        origin = 'the transformed card' if 'permission_kind' in pending['effect_payload'] else 'from the graveyard'
        state.log.append(f'{state.players[player_id].name} declines casting {origin}.')
    elif action.get('type') == 'cast_spell':
        from rules_engine.action_validation import require
        require(validate_permission(state, player_id, pending['effect_payload'], action=action),
                'The selected effect casting permission is no longer available')
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
