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
EXTRA_SCRY = re.compile(r'^(.*?)\s+If this spell was foretold, (scry \d+)\.$', re.I | re.S)
TOKEN_INSTEAD = re.compile(r'^(Create (?:a|an|one) (.+?))\.\s*'
                           r'If this spell was foretold, create X of those tokens instead\.$', re.I | re.S)


def spell_variants(text):
    """Recognize complete clauses; never strip an unrecognized conditional."""
    if 'was foretold' not in text.lower():
        return None
    body = '\n'.join(line for line in without_reminder_text(text).splitlines()
                     if not PRINTED.fullmatch(line.strip())).strip()
    if match := EXTRA_SCRY.fullmatch(body):
        if 'foretell' in match[1].lower() or 'foretold' in match[1].lower():
            return None
        return match[1], match[1] + '\n' + match[2] + '.'
    if match := TOKEN_INSTEAD.fullmatch(body):
        return match[1] + '.', 'Create X ' + match[2] + '.'
    return None


def resolution_text(card, text):
    variants = spell_variants(text)
    if variants:
        return variants[int(bool(getattr(card, 'was_foretold', False) or record(card)))]
    return text


def reveal_at_game_end(state):
    if state.winner is None:
        return
    cards = sorted((card for card in state.cards.values() if record(card)),
                   key=lambda card: (card.foretell_record['order'], card.id))
    for card in cards:
        if not card.foretell_record.get('revealed_at_game_end'):
            card.foretell_record['revealed_at_game_end'] = True
            actor = state.players[card.foretell_record['player_id']]
            state.log.append(f'{actor.name} reveals foretold {card.name} at game end.')


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
    data = getattr(card, 'foretell_record', {})
    return data if (getattr(card, 'zone', None) == Zone.EXILE and getattr(card, 'exile_face_down', False)
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
                                                   for reduction in data['granted_reductions']
                                                   if card.mana_cost]))


def created_clauses(text, name):
    if 'becomes foretold' not in text.lower():
        return []
    reference = r'(?:this creature|' + re.escape(name) + r')'
    out = []
    for line in without_reminder_text(text).splitlines():
        hand = re.fullmatch(r'whenever ' + reference + r' enters(?: the battlefield)? or attacks, '
            r'draw a card, then exile a card from your hand face down\. It becomes foretold\. '
            r'Its foretell cost is its mana cost reduced by \{(\d+)\}\.', line.strip(), re.I)
        damage = re.fullmatch(r'whenever ' + reference + r' deals damage, exile '
            r'(?:it|' + reference + r') face down\. It becomes foretold\.', line.strip(), re.I)
        if hand:
            out.append({'kind': 'hand', 'line': line.strip(), 'reduction': int(hand[1])})
        elif damage:
            out.append({'kind': 'self', 'line': line.strip()})
    return out


def without_created_clauses(text, name):
    recognized = {clause['line'] for clause in created_clauses(text, name)}
    return '\n'.join(line for line in text.splitlines() if line.strip() not in recognized) if recognized else text


def _created_triggers(state, event, payload):
    if event not in {'enters_battlefield', 'attack_declared', 'damage_dealt', 'combat_damage_dealt'}:
        return []
    from rules_engine.continuous import printed_abilities_suppressed
    from game_state.state import object_incarnation
    cid = payload.get('source_card_id') if 'damage' in event else payload.get('card_id')
    card = state.cards.get(cid)
    if (card is None or card.zone != Zone.BATTLEFIELD
            or 'becomes foretold' not in (card.oracle_text or '').lower()
            or printed_abilities_suppressed(state, cid)):
        return []
    out = []
    for clause in created_clauses(card.oracle_text, card.name):
        if clause['kind'] == 'hand' and event in {'enters_battlefield', 'attack_declared'}:
            key, data = 'effect_sequence', {'effects': [
                {'effect_key': 'draw_cards', 'payload': {'amount': 1}},
                {'effect_key': 'foretell_from_hand', 'payload': {'reduction': clause['reduction']}},
            ]}
        elif clause['kind'] == 'self' and 'damage' in event and payload.get('amount', 0) > 0:
            key, data = 'foretell_self', {'card_id': cid, 'incarnation': object_incarnation(card),
                                        'sequence': card.zone_change_sequence}
        else:
            continue
        out.append({'source_card_id': cid, 'controller': card.controller,
                    'label': f'{card.name} effect-created foretell', 'effect_key': key, 'payload': data})
    return out


def mark_foretold(state, card, player_id, fixed_costs, reductions, *, origin):
    card.exile_face_down = True
    card.foretell_record = {'player_id': player_id, 'turn': state.turn, 'origin': origin,
                           'sequence': card.zone_change_sequence, 'order': allocate_effect_timestamp(state),
                           'fixed_costs': fixed_costs, 'granted_reductions': reductions}


def resolve_hand(state, controller, payload):
    options = list(state.players[controller].hand)
    if options and state.winner is None:
        state.pending_mechanic_choice = {'kind': 'foretell_from_hand', 'player_id': controller,
            'options': options, 'count': 1, 'min_count': 1, 'reduction': payload['reduction'],
            'label': 'Exile a card from your hand face down; it becomes foretold'}
        state.priority_player = controller
        state.passed_priority.clear()


def finish_hand_choice(state, player_id, action):
    from rules_engine.stack_engine import resume_paused_resolution
    pending = state.pending_mechanic_choice
    ids = action.get('card_ids')
    if (pending['player_id'] != player_id or not isinstance(ids, list) or len(ids) != 1
            or ids[0] not in pending['options'] or ids[0] not in state.players[player_id].hand):
        return False
    card = state.cards[ids[0]]
    if card.zone != Zone.HAND:
        return False
    state.pending_mechanic_choice = None
    state.players[player_id].hand.remove(card.id)
    card.move_to_zone(Zone.EXILE)
    state.players[card.owner].exile.append(card.id)
    mark_foretold(state, card, card.owner, PRINTED.findall(without_reminder_text(card.oracle_text)),
                  [pending['reduction']], origin='effect')
    state.log.append(f'{state.players[player_id].name} exiles a hand card face down; it becomes foretold.')
    resume_paused_resolution(state, pending)
    return True


def resolve_self(state, controller, payload):
    from game_state.state import object_incarnation
    from effects.handlers import exile_permanent
    card = state.cards.get(payload['card_id'])
    if (card is None or card.zone != Zone.BATTLEFIELD or object_incarnation(card) != payload['incarnation']
            or card.zone_change_sequence != payload['sequence']):
        return
    exile_permanent(state, controller, {'target_card_id': card.id})
    if card.zone == Zone.EXILE:
        mark_foretold(state, card, card.owner, PRINTED.findall(without_reminder_text(card.oracle_text)),
                      [], origin='effect')


def collect_foretell_triggers(state, event, payload):
    if event != 'foretell':
        return _created_triggers(state, event, payload)
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
    mark_foretold(state, card, player_id, options['fixed_costs'], options['granted_reductions'], origin='special_action')
    state.foretells_this_turn[player_id] = state.foretells_this_turn.get(player_id, 0) + 1
    state.passed_priority.clear()
    state.log.append(f'{state.players[player_id].name} foretells a card face down.')
    from rules_engine.events import emit_event
    emit_event(state, 'foretell', {'player_id': player_id, 'card_id': card_id})
    return True
