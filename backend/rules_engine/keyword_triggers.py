"""Intrinsic combat keywords use ordinary APNAP/stack and durable delayed events."""
from rules_engine.type_effects import effective_types
import re
from game_state.state import Zone, object_incarnation
from rules_engine.continuous import effective_keyword_counts


def collect_keyword_triggers(state, event, payload):
    if event == 'block_declared':
        return _block_keyword_triggers(state, payload)
    if event == 'begin_step' and payload.get('step') == 'end_combat':
        due = [record for record in state.delayed_triggers if record['step'] == 'end_combat']
        state.delayed_triggers = [record for record in state.delayed_triggers if record['step'] != 'end_combat']
        return [{key: value for key, value in record.items() if key != 'step'} for record in due]
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


def resolve_keyword_trigger(state, controller, key, payload):
    cid = payload['card_id']
    card = state.cards.get(cid)
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
    if key in {'exalted_buff', 'bushido_buff', 'rampage_buff', 'flanking_buff'}:
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
