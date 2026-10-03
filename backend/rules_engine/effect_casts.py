"""Durable casts authorized during an effect, using ordinary announcements."""
from game_state.state import Zone


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


def cast_moves(state, player_id):
    pending = state.pending_mechanic_choice
    if pending['player_id'] != player_id:
        return []
    moves = [{'type': 'choose_mechanic', **pending,
              'option_labels': {'decline': 'Decline casting'}}]
    target = pending['effect_payload']['target_card_id']
    if target not in state.players[player_id].graveyard:
        return moves
    from rules_engine.cast_choice import build_cast_hints, has_available_targets_for_action
    from rules_engine.cast_choice import available_cast_options_and_hints
    from rules_engine.restrictions import can_cast_in_current_timing
    from rules_engine.move_generator import _cost_option_view
    from game_state.serializers import serialize_card_view
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
        state.pending_mechanic_choice = None
        try:
            admit_cast(state, player_id, action, pending['effect_payload'])
        except (ValueError, KeyError):
            state.pending_mechanic_choice = pending
            raise
    else:
        return False
    from rules_engine.stack_engine import resume_paused_resolution
    resume_paused_resolution(state, pending)
    return True
