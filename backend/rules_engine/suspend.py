"""Bounded printed mana-cost Suspend; CR 116.2f and 702.62."""
from copy import deepcopy
from collections.abc import Mapping
import re
from types import SimpleNamespace

from game_state.state import Step, Zone
from rules_engine.oracle_text import without_reminder_text

PRINTED = re.compile(r'Suspend (\d+)[\u2014\u2013-]((?:\{(?:\d+|[WUBRGCS])\})+)\.?', re.I)


def instruction(card):
    if getattr(card, 'layout', '') not in {'', 'normal'}:
        return None
    lines = [line.strip() for line in without_reminder_text(card.oracle_text or '').splitlines()
             if re.match(r'^suspend\b', line.strip(), re.I)]
    match = PRINTED.fullmatch(lines[0]) if len(lines) == 1 else None
    if match and int(match[1]) > 0:
        return int(match[1]), match[2].upper()
    return None


def diagnostic_surface_admitted(oracle_text, metadata, *, card_name='', card_faces=None):
    """Bounded sourced diagnostic, not certification of arbitrary Suspend bodies."""
    if not isinstance(metadata, Mapping):
        return False
    sources = metadata.get('card_data_sources')
    name = metadata.get('card_name') or metadata.get('name')
    if (not isinstance(sources, list) or not sources
            or any(not isinstance(source, str) or source not in {'cache', 'local_knowledge', 'offline_seed'} for source in sources)
            or not isinstance(name, str) or not name or card_name and card_name != name
            or metadata.get('oracle_text') != oracle_text
            or not isinstance(metadata.get('layout'), str) or metadata['layout'] not in {'', 'normal'}
            or card_faces or metadata.get('card_faces')
            or metadata.get('mana_cost') is not None and not isinstance(metadata['mana_cost'], str)
            or not isinstance(metadata.get('type_line'), str)):
        return False
    from card_data.hydration import ready_for_match
    if not ready_for_match(metadata):
        return False
    card = SimpleNamespace(layout=metadata['layout'], oracle_text=oracle_text)
    if instruction(card) is None:
        return False
    lines = [line.strip() for line in without_reminder_text(oracle_text).splitlines() if line.strip()]
    body = '\n'.join(line for line in lines if not PRINTED.fullmatch(line))
    # Whole-body shapes only: recognizing a first clause must not hide later text.
    if metadata['type_line'] in {'Instant', 'Sorcery'}:
        damage = re.fullmatch(re.escape(name) + r' deals ([1-9]\d*) damage to any target\.', body)
        draw = re.fullmatch(r'Target player draws (a|one|two|three|four|five|six|seven|eight|nine|ten|[1-9]\d*) cards?\.', body)
        return bool(damage or draw)
    return bool(re.fullmatch(r'Creature(?: \u2014 [^\n]+)?', metadata['type_line'])
                and body in {'', 'Flying'}
                and all(re.fullmatch(r'\d+', str(metadata.get(key))) for key in ('power', 'toughness')))


def suspended(card):
    return card.zone == Zone.EXILE and instruction(card) is not None and card.counters.get('time', 0) > 0


def current(state, payload):
    card = state.cards.get(payload.get('card_id'))
    return card if (card is not None and card.zone == Zone.EXILE
                    and card.zone_change_sequence == payload.get('sequence')) else None


def action_options(state, player_id, card):
    if (card.zone != Zone.HAND or card.id not in state.players[player_id].hand
            or state.winner is not None or state.pregame_pending or state.priority_player != player_id
            or state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order
            or state.step == Step.UNTAP or state.step == Step.CLEANUP and not state.cleanup_repeat_required):
        return None
    parsed = instruction(card)
    if parsed is None:
        return None
    from rules_engine.restrictions import can_cast_in_current_timing
    from rules_engine.mana import can_pay_with_pool_and_lands
    if (not can_cast_in_current_timing(state, card, player_id)[0]
            or not can_pay_with_pool_and_lands(state, player_id, parsed[1], payment_kind='suspend', apply_modifiers=False)):
        return None
    return {'time_counters': parsed[0], 'mana_cost': parsed[1]}


def take_special_action(state, player_id, card_id):
    card = state.cards.get(card_id)
    options = action_options(state, player_id, card) if card else None
    if options is None:
        return False
    from rules_engine.mana import auto_pay_cost
    from game_state.state import allocate_effect_timestamp
    if not auto_pay_cost(state, player_id, options['mana_cost'], payment_kind='suspend', apply_modifiers=False):
        return False
    state.players[player_id].hand.remove(card_id)
    card.move_to_zone(Zone.EXILE)
    state.players[card.owner].exile.append(card_id)
    # This is an exiled card, not a permanent: permanent counter prohibitions
    # and replacements do not apply to this special action's counters.
    card.counters['time'] = options['time_counters']
    card.counter_timestamps['time'] = allocate_effect_timestamp(state)
    state.passed_priority.clear()
    state.priority_player = player_id
    state.log.append(f'{state.players[player_id].name} suspends {card.name} with {card.counters.get("time", 0)} time counters.')
    return True


def collect_triggers(state, event, payload):
    if event == 'begin_step' and payload.get('step') == 'upkeep':
        cards = [card for card in state.cards.values() if card.owner == payload.get('active_player') and suspended(card)]
        key = 'suspend_upkeep'
    elif event == 'time_counters_removed' and payload.get('before', 0) > 0 and payload.get('after') == 0:
        card = state.cards.get(payload.get('card_id'))
        cards = [card] if card is not None and card.zone == Zone.EXILE and instruction(card) else []
        key = 'suspend_cast_trigger'
    else:
        return []
    return [{'source_card_id': card.id, 'controller': card.owner,
             'label': f'{card.name} suspend {"upkeep" if key == "suspend_upkeep" else "cast"}',
             'effect_key': key, 'payload': {'card_id': card.id, 'sequence': card.zone_change_sequence}}
            for card in cards]


def remove_time_counters(state, card_id, amount=1):
    card = state.cards.get(card_id)
    if card is None or amount <= 0:
        return 0
    before = card.counters.get('time', 0)
    removed = min(before, amount)
    if not removed:
        return 0
    after = before - removed
    if after:
        card.counters['time'] = after
    else:
        card.counters.pop('time', None)
        card.counter_timestamps.pop('time', None)
    from rules_engine.events import emit_event
    emit_event(state, 'time_counters_removed', {'card_id': card_id, 'before': before, 'after': after})
    return removed


def resolve_trigger(state, controller, key, payload):
    card = current(state, payload)
    if card is None:
        return
    if key == 'suspend_upkeep':
        if suspended(card):
            remove_time_counters(state, card.id)
    else:
        state.pending_mechanic_choice = {
            'kind': 'suspend_cast', 'player_id': controller, 'options': ['decline'], 'count': 1,
            'label': f'Cast {card.name} without paying its mana cost, or decline',
            'suspend_payload': {'card_id': card.id, 'sequence': card.zone_change_sequence},
        }
        state.priority_player = controller
        state.passed_priority.clear()


def cast_moves(state, player_id):
    pending = state.pending_mechanic_choice
    if pending['player_id'] != player_id:
        return []
    moves = [{'type': 'choose_mechanic', **pending, 'option_labels': {'decline': 'Decline casting'}}]
    card = current(state, pending['suspend_payload'])
    if card is None:
        return moves
    from rules_engine.cast_choice import available_cast_options_and_hints, has_available_targets_for_action
    from rules_engine.restrictions import can_cast_in_current_timing
    from rules_engine.move_generator import _cost_option_view
    from game_state.serializers import serialize_card_view
    costs, hints = available_cast_options_and_hints(state, card, player_id, without_mana=True)
    if '{x}' in (card.mana_cost or '').lower():
        hints['x_value_max'] = 0
    if costs and has_available_targets_for_action(hints) and can_cast_in_current_timing(state, card, player_id, during_resolution=True)[0]:
        moves.append({'type': 'cast_spell', 'card_id': card.id, 'card_name': card.name,
                      'from_exile': True, 'card_view': serialize_card_view(state, card.id),
                      'mana_cost': '', 'cost_options': [_cost_option_view(option, state, player_id, card.id) for option in costs],
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
        state.log.append(f'{state.players[player_id].name} declines the suspended card.')
    elif action.get('type') == 'cast_spell':
        from rules_engine.action_validation import require
        from rules_engine.engine import RulesEngine
        card = current(state, pending['suspend_payload'])
        require(card is not None and action.get('card_id') == card.id and action.get('from_exile')
                and not action.get('from_graveyard') and not action.get('from_library'), 'Invalid suspend casting permission')
        candidate = deepcopy(state)
        candidate.pending_mechanic_choice = None
        rules = RulesEngine()
        rules.take_action(candidate, player_id, action, reject_invalid=True, effect_cast=True, suspend_cast=True)
        require(candidate.cards[card.id].zone == Zone.STACK, 'Suspend cast requires an unsupported continuation')
        state.pending_mechanic_choice = None
        rules.take_action(state, player_id, action, reject_invalid=True, effect_cast=True, suspend_cast=True)
        from rules_engine.type_effects import effective_types
        if 'Creature' in effective_types(state, state.cards[card.id]):
            from game_state.state import allocate_effect_timestamp
            state.cards[card.id].suspend_haste = {'controller': player_id, 'timestamp': allocate_effect_timestamp(state)}
    else:
        return False
    from rules_engine.stack_engine import resume_paused_resolution
    resume_paused_resolution(state, pending)
    return True
