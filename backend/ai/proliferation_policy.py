"""Public-counter preferences; unknown resource semantics remain neutral."""
from rules_engine.continuous import effective_toughness


def counter_weight(kind, *, player=False):
    if player:
        return {'poison': -8, 'energy': 1, 'experience': 2, 'rad': -2}.get(kind, 0)
    return {'+1/+1': 2, '-1/-1': -2, 'loyalty': 3, 'lore': 1,
            'shield': 2, 'stun': -3, 'flying': 1, 'trample': 1}.get(kind, 0)


def preferred_recipients(state, controller, available):
    selected = []
    for option, packet in available.items():
        player = packet.get('target_player')
        score = sum(counter_weight(kind, player=player is not None) * amount
                    for kind, amount in packet['counter_amounts'].items())
        if player is not None:
            target = state.players[player]
            if 'poison' in packet['counter_amounts'] and target.poison >= 9:
                score = -10000
            friendly = player == controller
        else:
            card = state.cards[packet['target_card_id']]
            friendly = card.controller == controller
            if '-1/-1' in packet['counter_amounts'] and 'Creature' in card.types:
                damage = int(card.counters.get('__damage_marked', 0))
                delta = packet['counter_amounts'].get('+1/+1', 0) - packet['counter_amounts']['-1/-1']
                if effective_toughness(state, card.id) + delta - damage <= 0:
                    score -= 20
        if not friendly:
            score = -score
        if score > 0:
            selected.append(option)
    return selected
