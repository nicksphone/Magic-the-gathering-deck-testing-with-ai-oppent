"""Closed self-entry exchange, conditional energy, and retained-object payment."""
import re

from game_state.state import Zone, object_incarnation
from rules_engine.oracle_text import without_reminder_text


KEY = 'exchange_energy_payment'
LIMIT = 1_000_000
BODY = re.compile(
    r'(?P<clause>When this (?:creature|permanent) enters, exchange control of this '
    r'(?:creature|permanent) and target creature an opponent controls\.\s*'
    r'If you do, you get (?P<energy>(?:\{E\})+), then sacrifice that creature '
    r'unless you pay an amount of \{E\} equal to its mana value\.)', re.I)
KEYWORDS = re.compile(r'Flying, hexproof from activated and triggered abilities', re.I)


def bounded(value):
    return type(value) is int and 0 <= value <= LIMIT


def compile_instruction(card, controller):
    text = without_reminder_text(card.oracle_text or '').strip()
    if not re.search(r'exchange control of this (?:creature|permanent)', text, re.I):
        return None
    lines = text.splitlines()
    if len(lines) == 2 and KEYWORDS.fullmatch(lines[0].strip()):
        text = lines[1].strip()
    match = BODY.fullmatch(text)
    if not match or type(controller) is not int or controller not in (1, 2):
        return 'noop', {'__unsupported_instruction': card.oracle_text}
    amount = len(re.findall(r'\{E\}', match['energy'], re.I))
    ref = [card.id, object_incarnation(card), card.zone_change_sequence]
    if not bounded(amount) or not all(bounded(value) for value in ref[1:]):
        return 'noop', {'__unsupported_instruction': card.oracle_text}
    return KEY, {'__exchange_phase': 'exchange', '__exchange_controller': controller,
                 '__exchange_source_reference': ref, 'energy_amount': amount,
                 '__trigger_full_clause': match['clause']}


def current(state, cid, reference):
    card = state.cards.get(cid)
    return (card is not None and card.zone == Zone.BATTLEFIELD
            and type(reference) is list and len(reference) == 2
            and all(bounded(value) for value in reference)
            and reference == [object_incarnation(card), card.zone_change_sequence]
            and type(card.controller) is int and card.controller in state.players
            and cid in state.players[card.controller].battlefield)


def public_choice(pending):
    return {key: pending[key] for key in
            ('kind', 'player_id', 'options', 'count', 'label', 'option_labels')}


def resolve(state, controller, payload):
    from effects.handlers import change_control
    from rules_engine.counter_placement import put_counters
    from rules_engine.counter_replacements import counter_effect_amount
    from rules_engine.events import emit_event
    from rules_engine.mana import mana_value
    phase = payload.get('__exchange_phase')
    actor = controller if phase == 'exchange' else payload.get('__exchange_controller')
    amount = payload.get('energy_amount')
    if (type(controller) is not int or type(actor) is not int or actor not in state.players or actor != controller
            or not bounded(amount) or not bounded(state.players[actor].counters.get('energy', 0))):
        return
    if phase == 'exchange':
        payload = {**payload, '__exchange_controller': actor}
    target_id = payload.get('__exchange_target_id', payload.get('target_card_id'))
    target_ref = payload.get('__trigger_target_reference')
    if phase == 'exchange':
        ref = payload.get('__exchange_source_reference')
        if (type(ref) is not list or len(ref) != 3 or not isinstance(ref[0], str)
                or ref[0] == target_id or not current(state, ref[0], ref[1:])
                or not current(state, target_id, target_ref)):
            return
        source, target = state.cards[ref[0]], state.cards[target_id]
        old_source, old_target = source.controller, target.controller
        if old_source == old_target or old_target == actor:
            return
        payload = {**payload, '__exchange_target_id': target_id}
        # Validate both objects before either control change; no partial exchange.
        change_control(state, actor, {'target_card_id': source.id, 'new_controller': old_target})
        change_control(state, actor, {'target_card_id': target.id, 'new_controller': old_source})
        payload = {**payload, '__exchange_phase': 'energy'}
        phase = 'energy'
    if phase != 'energy':
        return
    requested = payload.get('amount', amount)
    if not bounded(requested):
        return
    amount = counter_effect_amount(state, actor, KEY, {
        **payload, 'target_card_id': None, 'target_player': actor, 'counter': 'energy', 'amount': requested})
    if amount is None:
        return
    if not bounded(amount) or state.players[actor].counters.get('energy', 0) + amount > LIMIT:
        return
    placed = put_counters(state, 'energy', amount, target_player=actor)
    if placed:
        emit_event(state, 'player_counters_added', {
            'player_id': actor, 'controller': actor, 'counter': 'energy', 'amount': placed})
    if not current(state, target_id, target_ref):
        return
    cost = mana_value(state.cards[target_id].mana_cost or '')
    if not bounded(cost):
        return
    options = ['pay', 'decline'] if state.players[actor].counters.get('energy', 0) >= cost else ['decline']
    state.pending_mechanic_choice = {
        'kind': KEY, 'player_id': actor, 'controller': actor, 'options': options,
        'count': 1, 'label': 'Pay energy or sacrifice the exchanged creature',
        'option_labels': {'pay': f'Pay {cost} energy', 'decline': 'Decline energy payment; sacrifice'},
        'effect_payload': {**payload, '__exchange_phase': 'payment', 'energy_cost': cost}}
    state.priority_player = actor
    state.passed_priority = set()


def finish(state, player_id, action):
    from effects.handlers import sacrifice
    from rules_engine.stack_engine import resume_paused_resolution
    pending = state.pending_mechanic_choice
    if (not pending or pending.get('kind') != KEY or type(player_id) is not int
            or pending.get('player_id') != player_id or action.get('type') != 'choose_mechanic'
            or action.get('choice_id') not in pending['options']):
        return False
    payload = pending['effect_payload']
    cost = payload.get('energy_cost')
    balance = state.players[player_id].counters.get('energy', 0)
    if (payload.get('__exchange_phase') != 'payment' or type(payload.get('__exchange_controller')) is not int
            or payload.get('__exchange_controller') != player_id
            or not bounded(cost) or not bounded(balance)):
        return False
    target_id = payload.get('__exchange_target_id', payload.get('target_card_id'))
    same = current(state, target_id, payload.get('__trigger_target_reference'))
    state.pending_mechanic_choice = None
    if same:
        if action['choice_id'] == 'pay' and balance >= cost:
            state.players[player_id].counters['energy'] = balance - cost
            state.log.append(f'{state.players[player_id].name} pays {cost} energy.')
        else:
            sacrifice(state, player_id, {'target_card_id': target_id})
    resume_paused_resolution(state, pending)
    return True
