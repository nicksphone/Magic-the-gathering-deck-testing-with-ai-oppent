"""Resolution-created fixed mana payments at the controller's next upkeep."""
import re


KEY = 'deferred_upkeep_payment'
MANA = r'(?:\{(?:0|[1-9]\d*|[WUBRGC])\})+'
TAIL = re.compile(
    r'(?P<immediate>.+?\.)\s+At the beginning of your next upkeep, pay '
    r'(?P<cost>' + MANA + r")\.\s+If you don['\u2019]t, you lose the game\.?",
    re.I | re.S,
)


def compile_instruction(text):
    text = text or ''
    if not re.search(r'at the beginning of your next upkeep,\s*pay\b', text, re.I):
        return None
    match = TAIL.fullmatch(text.strip())
    if match is None:
        return {'__unsupported_instruction': text}
    immediate = match['immediate'].strip()
    # The legacy search compiler accepts substrings. Admit this complete search
    # sentence here so an unknown immediate tail cannot disappear before the debt.
    if 'search your library' in immediate.lower() and not re.fullmatch(
            r'Search your library for a (?:white|blue|black|red|green) creature card, '
            r'reveal it, put it into your hand, then shuffle\.', immediate, re.I):
        return {'__unsupported_instruction': text}
    return {'immediate_text': immediate, 'mana_cost': match['cost'].upper()}


def valid_cost(cost):
    return isinstance(cost, str) and re.fullmatch(MANA, cost) is not None


def schedule(state, controller, payload):
    from rules_engine.events import trigger_source_reference
    cost = payload.get('mana_cost')
    if type(controller) is not int or controller not in state.players or not valid_cost(cost):
        return
    source_id = payload.get('__source_card_id') or payload.get('source_card_id')
    source = state.cards.get(source_id)
    state.delayed_triggers.append({
        'step': 'upkeep', 'earliest_turn': state.turn + 1, 'active_player': controller,
        'source_card_id': source_id, 'controller': controller,
        'label': f'{source.name if source else "Delayed"} upkeep payment',
        'effect_key': KEY, 'payload': {'mana_cost': cost,
            '__trigger_source_reference': trigger_source_reference(state, source_id, payload)},
    })


def can_pay(state, player, cost):
    from rules_engine.mana import can_pay_with_pool_and_lands
    return can_pay_with_pool_and_lands(
        state, player, cost, payment_kind='effect', apply_modifiers=False)


def resolve(state, controller, payload):
    cost = payload.get('mana_cost')
    if type(controller) is not int or controller not in state.players or not valid_cost(cost):
        return
    state.pending_mechanic_choice = {
        'kind': KEY, 'player_id': controller, 'count': 1,
        'options': ['pay', 'decline'] if can_pay(state, controller, cost) else ['decline'],
        'label': f'Pay {cost} or lose the game',
        'option_labels': {'pay': f'Pay {cost}', 'decline': 'Decline payment; lose the game'},
        'effect_payload': {'mana_cost': cost},
    }
    state.priority_player = controller
    state.passed_priority = set()


def public_choice(pending):
    return {key: pending[key] for key in
            ('kind', 'player_id', 'options', 'count', 'label', 'option_labels')}


def finish(state, player, action):
    from effects.handlers import player_loses_game
    from rules_engine.mana import auto_pay_cost
    from rules_engine.stack_engine import resume_paused_resolution
    pending = state.pending_mechanic_choice
    ids = action.get('card_ids')
    if (not pending or pending.get('kind') != KEY or type(player) is not int
            or pending.get('player_id') != player or action.get('type') != 'choose_mechanic'
            or not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str)
            or ids[0] not in pending['options']):
        return False
    cost = pending.get('effect_payload', {}).get('mana_cost')
    if not valid_cost(cost):
        return False
    if ids == ['pay']:
        if not can_pay(state, player, cost) or not auto_pay_cost(
                state, player, cost, payment_kind='effect', apply_modifiers=False):
            return False
        state.log.append(f'{state.players[player].name} pays {cost} for the delayed upkeep ability.')
    else:
        player_loses_game(state, player, {'target_player': player})
    state.pending_mechanic_choice = None
    resume_paused_resolution(state, pending)
    return True
