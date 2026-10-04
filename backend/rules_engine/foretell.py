"""Foretell special actions and durable, source-independent exile permissions."""
import re

from game_state.state import Step, Zone, allocate_effect_timestamp
from rules_engine.oracle_text import without_reminder_text


PRINTED = re.compile(r'^foretell\s+((?:\{[^{}]+\})+)\s*\.?$', re.I | re.M)
GRANT = re.compile(r'each nonland card in your hand( without foretell)? has foretell\. '
                   r'its foretell cost is equal to its mana cost reduced by \{(\d+)\}\.', re.I)
MODIFIER = re.compile(r"foretelling cards from your hand costs \{(\d+)\} less "
                      r"and can be done on any player's turn\.", re.I)
FIRST = re.compile(r'the first card you foretell each turn costs \{0\} to foretell\.', re.I)


def _sources(state, player_id):
    from rules_engine.continuous import printed_abilities_suppressed, _static_oracle_text
    sources = []
    for player in state.players.values():
        for cid in player.battlefield:
            card = state.cards[cid]
            if card.controller != player_id:
                continue
            text = _static_oracle_text(card)
            if 'foretell' in text.lower() and not printed_abilities_suppressed(state, cid):
                sources.append(text)
    return sources


def hand_costs(state, card, player_id):
    if card.id not in state.players[player_id].hand or card.zone != Zone.HAND:
        return [], []
    fixed = list(dict.fromkeys(PRINTED.findall(without_reminder_text(card.oracle_text))))
    grants = [clause for text in _sources(state, player_id) for clause in GRANT.finditer(text)]
    if not grants:
        return fixed, []
    reductions = []
    from rules_engine.type_effects import effective_types
    if 'Land' not in effective_types(state, card):
        for clause in grants:
            if clause[1] and fixed:
                continue
            reductions.append(int(clause[2]))
    return fixed, list(dict.fromkeys(reductions))


def action_cost(state, player_id):
    sources = _sources(state, player_id)
    modifiers = [int(match[1]) for text in sources for match in MODIFIER.finditer(text)]
    if state.active_player != player_id and not modifiers:
        return None
    first_free = not state.foretells_this_turn.get(player_id, 0) and any(FIRST.search(text) for text in sources)
    return '{' + str(0 if first_free else max(0, 2 - sum(modifiers))) + '}'


def action_options(state, player_id, card):
    if (state.winner is not None or state.pregame_pending or state.priority_player != player_id
            or state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order
            or state.step == Step.UNTAP or state.step == Step.CLEANUP and not state.cleanup_repeat_required):
        return None
    fixed, reductions = hand_costs(state, card, player_id)
    if not fixed and not reductions:
        return None
    price = action_cost(state, player_id)
    from rules_engine.mana import can_pay_with_pool_and_lands
    if price is None or not can_pay_with_pool_and_lands(state, player_id, price,
                                                       payment_kind='foretell', apply_modifiers=False):
        return None
    return {'mana_cost': price, 'fixed_costs': fixed, 'granted_reductions': reductions}


def record(card):
    data = card.foretell_record
    return data if (card.zone == Zone.EXILE and card.exile_face_down
                    and data.get('sequence') == card.zone_change_sequence) else {}


def can_look(card, player_id):
    return record(card).get('player_id') == player_id


def cast_permission(state, player_id, card):
    data = record(card)
    return bool(data and data['player_id'] == player_id and state.turn > data['turn'])


def _reduced_cost(cost, reduction):
    symbols = re.findall(r'\{([^{}]+)\}', cost or '')
    numeric = sum(int(symbol) for symbol in symbols if symbol.isdigit())
    others = ''.join('{' + symbol + '}' for symbol in symbols if not symbol.isdigit())
    generic = max(0, numeric - reduction)
    return ('{' + str(generic) + '}' if generic or not others else '') + others


def cast_costs(state, card, player_id):
    if not cast_permission(state, player_id, card):
        return []
    data = record(card)
    return list(dict.fromkeys(data['fixed_costs'] + [_reduced_cost(card.mana_cost, reduction)
                                                   for reduction in data['granted_reductions']]))


def collect_foretell_triggers(state, event, payload):
    if event != 'foretell':
        return []
    from rules_engine.continuous import printed_abilities_suppressed
    from game_state.state import object_incarnation
    out = []
    for player in state.players.values():
        for cid in player.battlefield:
            card = state.cards[cid]
            if card.controller != payload.get('player_id') or printed_abilities_suppressed(state, cid):
                continue
            pattern = (r'whenever you foretell a card, (?:this creature|' + re.escape(card.name)
                       + r') gets ([+-]\d+)/([+-]\d+) until end of turn\.')
            for match in re.finditer(pattern, without_reminder_text(card.oracle_text), re.I):
                out.append({'source_card_id': cid, 'controller': card.controller,
                            'label': f'{card.name} foretell reward', 'effect_key': 'referenced_pt_buff',
                            'payload': {'card_id': cid, 'incarnation': object_incarnation(card),
                                        'zone_change_sequence': card.zone_change_sequence,
                                        'power': int(match[1]), 'toughness': int(match[2])}})
    return out


def take_special_action(state, player_id, card_id):
    card = state.cards.get(card_id)
    options = action_options(state, player_id, card) if card else None
    if options is None:
        return False
    from rules_engine.mana import auto_pay_cost
    previous_staging = state.trigger_staging, state.trigger_staging_event
    state.trigger_staging = True
    state.trigger_staging_event = 'foretell'
    if not auto_pay_cost(state, player_id, options['mana_cost'], payment_kind='foretell', apply_modifiers=False):
        state.trigger_staging, state.trigger_staging_event = previous_staging
        return False
    state.players[player_id].hand.remove(card_id)
    card.move_to_zone(Zone.EXILE)
    state.players[card.owner].exile.append(card_id)
    card.exile_face_down = True
    card.foretell_record = {'player_id': player_id, 'turn': state.turn,
                           'sequence': card.zone_change_sequence, 'order': allocate_effect_timestamp(state),
                           'fixed_costs': options['fixed_costs'], 'granted_reductions': options['granted_reductions']}
    state.foretells_this_turn[player_id] = state.foretells_this_turn.get(player_id, 0) + 1
    state.passed_priority.clear()
    state.log.append(f'{state.players[player_id].name} foretells a card face down.')
    from rules_engine.events import emit_event
    emit_event(state, 'foretell', {'player_id': player_id, 'card_id': card_id})
    return True
