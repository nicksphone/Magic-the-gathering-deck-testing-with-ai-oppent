"""Whole-clause private top-card look, optional reveal, typed self-transform."""
import re

from game_state.state import Zone, object_incarnation
from rules_engine.card_types import CARD_TYPES
from rules_engine.oracle_text import without_reminder_text
from rules_engine.type_effects import effective_types


UPKEEP_REVEAL = re.compile(
    r'At the beginning of your upkeep, look at the top card of your library\.\s*'
    r'You may reveal that card\.\s*If an? (?P<types>[a-z ]+) card is revealed '
    r'this way, transform this (?:creature|permanent)\.', re.I)


def parse_upkeep_reveal(text):
    match = UPKEEP_REVEAL.fullmatch(without_reminder_text(text or '').strip())
    if not match:
        return None
    types = match['types'].lower().split(' or ')
    if not types or any(kind.title() not in CARD_TYPES for kind in types):
        return None
    return {'optional_reveal': True, 'required_types': [kind.title() for kind in types],
            'face_index': 1}


def begin_reveal(state, controller, payload):
    player = state.players[controller]
    if not player.library:
        return
    top_id = player.library[-1]
    top = state.cards[top_id]
    from game_state.observations import observe_cards
    observe_cards(state, [top_id], viewers=(controller,))
    state.pending_mechanic_choice = {
        'kind': 'optional_reveal', 'player_id': controller,
        'label': 'Privately inspect the top card; reveal it or decline',
        'options': ['reveal', 'decline'], 'count': 1,
        'option_labels': {'reveal': 'Reveal inspected card', 'decline': 'Decline reveal'},
        'inspected_card_ids': [top_id],
        'top_reference': [top_id, object_incarnation(top), top.zone_change_sequence],
        'effect_payload': dict(payload),
    }
    state.priority_player = controller
    state.passed_priority = set()


def finish_reveal(state, player_id, action):
    pending = state.pending_mechanic_choice
    if (not pending or pending.get('kind') != 'optional_reveal'
            or pending['player_id'] != player_id
            or action.get('type') != 'choose_mechanic'
            or action.get('card_ids') not in [['reveal'], ['decline']]):
        return False
    player = state.players[player_id]
    reference = pending['top_reference']
    top = state.cards.get(reference[0])
    if (not player.library or player.library[-1] != reference[0] or top is None
            or top.zone != Zone.LIBRARY or top.owner != player_id
            or reference != [top.id, object_incarnation(top), top.zone_change_sequence]):
        return False
    payload = pending['effect_payload']
    state.pending_mechanic_choice = None
    if action['card_ids'] == ['reveal']:
        state.log.append(f'{player.name} reveals {top.name}.')
        from game_state.observations import observe_cards
        observe_cards(state, [top.id])
        source = state.cards.get(payload.get('target_card_id'))
        source_reference = payload.get('source_reference')
        if (source is not None and source.zone == Zone.BATTLEFIELD
                and source_reference == [source.id, object_incarnation(source), source.zone_change_sequence]
                and set(payload['required_types']).intersection(effective_types(state, top))):
            from effects.registry import resolve_effect
            resolve_effect(state, player_id, 'transform_card',
                           {'target_card_id': source.id, 'face_index': payload['face_index']})
    else:
        state.log.append(f'{player.name} declines to reveal the inspected card.')
    from rules_engine.stack_engine import resume_paused_resolution
    resume_paused_resolution(state, pending)
    return True


def public_choice(pending):
    if pending and pending.get('kind') == 'exchange_energy_payment':
        from rules_engine.exchange_energy import public_choice as exchange_choice
        return exchange_choice(pending)
    if pending and pending.get('kind') == 'entry_mode':
        from rules_engine.modal_entry import view
        return view(pending)
    if pending and pending.get('kind') in {'search_library', 'optional_search'}:
        return {key: pending[key] for key in
                ('kind', 'player_id', 'label', 'count', 'min_count') if key in pending}
    if pending and pending.get('kind') == 'land_from_hand':
        return {key: pending[key] for key in ('kind', 'player_id', 'label', 'count', 'min_count')}
    if pending and pending.get('kind') == 'optional_reveal':
        return {key: pending[key] for key in ('kind', 'player_id', 'label', 'count')}
    if pending and pending.get('kind') == 'hand_top_order':
        return {key: pending[key] for key in
                ('kind', 'player_id', 'options', 'count', 'min_count', 'label',
                 'option_labels', 'option_type_lines') if key in pending}
    return pending
