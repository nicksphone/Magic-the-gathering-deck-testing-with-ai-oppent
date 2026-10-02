"""Intrinsic combat keywords use ordinary APNAP/stack and durable delayed events."""
from game_state.state import Zone, object_incarnation
from rules_engine.continuous import effective_keyword_counts


def collect_keyword_triggers(state, event, payload):
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
    if key == 'exalted_buff':
        from effects.handlers import temporary_pt_buff
        temporary_pt_buff(state, controller, {'target_card_id': cid, 'power': 1, 'toughness': 1})
    elif key == 'decayed_sacrifice':
        from effects.handlers import sacrifice
        sacrifice(state, controller, {'target_card_id': cid})
