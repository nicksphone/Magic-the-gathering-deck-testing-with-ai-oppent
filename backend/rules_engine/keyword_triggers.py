"""Intrinsic combat keywords use ordinary APNAP/stack and durable delayed events."""
from rules_engine.type_effects import effective_types
import re
from game_state.state import Zone, object_incarnation
from rules_engine.continuous import effective_keyword_counts


def next_turn_draw_instruction(text):
    match = re.fullmatch(
        r'draw (a|one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards? '
        r"at the beginning of the next turn['\u2019]s upkeep\.?", text.strip(), re.I,
    )
    if match is None:
        return None
    from rules_engine.oracle_effects import _parse_count_token
    return {'amount': _parse_count_token(match[1])}


def schedule_next_turn_draw(state, controller, payload):
    source_id = payload.get('__source_card_id') or payload.get('source_card_id')
    source = state.cards.get(source_id)
    state.delayed_triggers.append({
        'step': 'upkeep', 'earliest_turn': state.turn + 1,
        'source_card_id': source_id, 'controller': controller,
        'label': f'{source.name if source else "Delayed"} next-turn draw',
        'effect_key': 'draw_cards', 'payload': {'amount': payload['amount'], 'target_player': controller},
    })


def collect_keyword_triggers(state, event, payload):
    if event in {'control_changed', 'leaves_battlefield'}:
        due, remaining = [], []
        for record in state.delayed_triggers:
            data = record.get('payload', {})
            card = state.cards.get(data.get('card_id'))
            matches = (record.get('condition') == 'lose_control'
                       and payload.get('card_id') == data.get('card_id')
                       and card is not None and card.zone == Zone.BATTLEFIELD
                       and object_incarnation(card) == data['incarnation']
                       and card.zone_change_sequence == data['zone_change_sequence'])
            lost = (event == 'leaves_battlefield' and card is not None
                    and card.controller == record.get('controller')
                    or event == 'control_changed'
                    and payload.get('previous_controller') == record.get('controller')
                    and payload.get('controller') != record.get('controller'))
            (due if matches and lost else remaining).append(record)
        state.delayed_triggers = remaining
        return [{key: value for key, value in record.items() if key != 'condition'}
                for record in due]
    if event == 'creature_dies':
        card = state.cards.get(payload.get('card_id'))
        if card is None or card.zone != Zone.GRAVEYARD:
            return []
        lki = card.last_known_battlefield
        if lki.get('counters', {}).get('+1/+1', 0) > 0:
            return []
        return [{
            'source_card_id': card.id,
            'controller': lki.get('controller', card.controller),
            'label': f'{lki.get("name", card.name)} undying',
            'effect_key': 'undying_return',
            'payload': {'card_id': card.id, 'incarnation': object_incarnation(card),
                        'zone_change_sequence': card.zone_change_sequence},
        } for _ in range(lki.get('keyword_counts', {}).get('undying', 0))]
    if event == 'block_declared':
        return _block_keyword_triggers(state, payload)
    if event == 'begin_step':
        due, remaining = [], []
        for record in state.delayed_triggers:
            (due if record.get('step') == payload.get('step')
             and state.turn >= record.get('earliest_turn', state.turn) else remaining).append(record)
        state.delayed_triggers = remaining
        return [{key: value for key, value in record.items() if key not in {'step', 'earliest_turn'}}
                for record in due]
    if event != 'attack_declared':
        return []
    attacker = state.cards.get(payload.get('card_id'))
    if attacker is None or attacker.zone != Zone.BATTLEFIELD or attacker.id not in state.attackers:
        return []
    reference = {'card_id': attacker.id, 'incarnation': object_incarnation(attacker)}
    triggers = [{
        'source_card_id': attacker.id, 'controller': attacker.controller,
        'label': f'{attacker.name} decayed', 'effect_key': 'decayed_attack',
        'payload': dict(reference),
    } for _ in range(effective_keyword_counts(state, attacker.id).get('decayed', 0))]
    if len(state.attackers) == 1:
        for player in state.players.values():
            for cid in player.battlefield:
                source = state.cards[cid]
                if source.controller != attacker.controller:
                    continue
                triggers.extend({
                    'source_card_id': cid, 'controller': source.controller,
                    'label': f'{source.name} exalted', 'effect_key': 'exalted_buff',
                    'payload': dict(reference),
                } for _ in range(effective_keyword_counts(state, cid).get('exalted', 0)))
    return triggers


def _block_keyword_triggers(state, payload):
    attacker = state.cards.get(payload.get('attacker_id'))
    blocker = state.cards.get(payload.get('blocker_id'))
    if attacker is None or blocker is None:
        return []
    triggers = []

    def add(source, recipient, keyword, amount, count):
        data = {'card_id': recipient.id, 'incarnation': object_incarnation(recipient), 'amount': amount}
        if keyword == 'rampage':
            data['blocker_incarnations'] = {
                bid: object_incarnation(state.cards[bid]) for bid in state.blocks.get(attacker.id, [])
            }
        triggers.extend({'source_card_id': source.id, 'controller': source.controller,
                         'label': f'{source.name} {keyword}', 'effect_key': f'{keyword}_buff',
                         'payload': dict(data)} for _ in range(count))

    for creature, first, families in (
        (attacker, payload.get('attacker_first_block', True), {'bushido', 'rampage'}),
        (blocker, payload.get('blocker_first_block', True), {'bushido'}),
    ):
        if not first:
            continue
        for keyword, count in effective_keyword_counts(state, creature.id).items():
            match = re.fullmatch(r'(bushido|rampage) (\d+)', keyword)
            if match and match[1] in families:
                add(creature, creature, match[1], int(match[2]), count)
    attacker_count = effective_keyword_counts(state, attacker.id).get('flanking', 0)
    if attacker_count and not effective_keyword_counts(state, blocker.id).get('flanking', 0):
        add(attacker, blocker, 'flanking', -1, attacker_count)
    return triggers


def schedule_control_loss_tap(state, controller, payload):
    from copy import deepcopy
    from rules_engine.action_validation import ActionRejected
    frame = payload.get('__resolving_item')
    frame_payload = frame.get('payload') if isinstance(frame, dict) else None
    receipt = frame_payload.get('__control_source_frame') if isinstance(frame_payload, dict) else None
    if (not isinstance(frame, dict) or not isinstance(receipt, dict)
            or set(receipt) != {'stack_id', 'source_card_id', 'cast_controller', 'label', 'source_reference'}
            or not isinstance(receipt.get('stack_id'), str) or not receipt['stack_id']
            or not isinstance(receipt.get('source_card_id'), str) or not receipt['source_card_id']
            or type(receipt.get('cast_controller')) is not int
            or receipt['cast_controller'] not in state.players
            or not isinstance(receipt.get('label'), str) or not receipt['label']
            or type(frame.get('controller')) is not int
            or frame.get('controller') != controller
            or frame.get('source_card_id') != receipt.get('source_card_id')
            or not isinstance(frame.get('id'), str) or not frame['id']
            or not isinstance(frame.get('label'), str) or not frame['label']
            or '__resolving_item' in frame_payload
            or ('__control_source_frame' in payload
                and payload['__control_source_frame'] != receipt)):
        raise ActionRejected('Missing or inconsistent retained control resolution frame')
    reference = receipt.get('source_reference')
    if (not isinstance(reference, dict)
            or set(reference) != {'incarnation', 'zone_change_sequence'}
            or any(type(value) is not int or value < 0 for value in reference.values())):
        raise ActionRejected('Malformed retained control source reference')
    card = state.cards[payload['target_card_id']]
    source_id = receipt['source_card_id']
    state.delayed_triggers.append({
        'condition': 'lose_control', 'source_card_id': source_id,
        'controller': controller, 'label': f"{frame['label']} delayed tap",
        'effect_key': 'control_loss_tap',
        'payload': {
            'card_id': card.id, 'incarnation': object_incarnation(card),
            'zone_change_sequence': card.zone_change_sequence,
            '__source_lki': deepcopy(payload.get('__source_lki') or {}),
            '__delayed_source_reference': deepcopy(reference),
            '__control_source_frame': deepcopy(receipt),
            '__resolving_item': deepcopy(frame),
        },
    })


def resolve_keyword_trigger(state, controller, key, payload):
    cid = payload['card_id']
    card = state.cards.get(cid)
    if key == 'undying_return':
        if (card is None or card.zone != Zone.GRAVEYARD
                or object_incarnation(card) != payload['incarnation']
                or card.zone_change_sequence != payload['zone_change_sequence']
                or card.counters.get('+1/+1', 0) > 0):
            return
        from effects.handlers import return_creature_from_graveyard_to_battlefield
        return_creature_from_graveyard_to_battlefield(state, card.owner, {
            'target_card_id': cid, 'counters': {'+1/+1': 1},
            '__graveyard_reference': {'incarnation': payload['incarnation'],
                                      'zone_change_sequence': payload['zone_change_sequence']},
        })
        return
    if key == 'decayed_attack':
        # The attack trigger creates a later, counterable trigger, even if the
        # original object has left. Its stored reference never follows a blink.
        state.delayed_triggers.append({
            'step': 'end_combat', 'source_card_id': cid, 'controller': controller,
            'label': f'{card.name if card else "Creature"} decayed sacrifice',
            'effect_key': 'decayed_sacrifice',
            'payload': {'card_id': cid, 'incarnation': payload['incarnation']},
        })
        return
    if card is None or card.zone != Zone.BATTLEFIELD or object_incarnation(card) != payload['incarnation']:
        return
    if key == 'control_loss_tap':
        if card.zone_change_sequence == payload['zone_change_sequence']:
            from effects.handlers import tap_card
            tap_card(state, controller, {'target_card_id': cid})
        return
    if key == 'referenced_pt_buff':
        if card.zone_change_sequence != payload['zone_change_sequence']:
            return
        from effects.handlers import temporary_pt_buff
        temporary_pt_buff(state, controller, {'target_card_id': cid, 'power': payload['power'],
                                             'toughness': payload['toughness']})
    elif key in {'exalted_buff', 'bushido_buff', 'rampage_buff', 'flanking_buff'}:
        from effects.handlers import temporary_pt_buff
        amount = payload.get('amount', 1)
        if key == 'rampage_buff':
            blockers = state.blocks.get(cid, []) if cid in state.attackers else []
            amount *= max(0, sum(
                bid in state.cards and state.cards[bid].zone == Zone.BATTLEFIELD
                and 'Creature' in effective_types(state, state.cards[bid])
                and state.cards[bid].controller != card.controller
                and (bid not in payload['blocker_incarnations']
                     or object_incarnation(state.cards[bid]) == payload['blocker_incarnations'][bid])
                for bid in dict.fromkeys(blockers)
            ) - 1)
        temporary_pt_buff(state, controller, {'target_card_id': cid, 'power': amount, 'toughness': amount})
    elif key == 'decayed_sacrifice':
        from effects.handlers import sacrifice
        sacrifice(state, controller, {'target_card_id': cid})
