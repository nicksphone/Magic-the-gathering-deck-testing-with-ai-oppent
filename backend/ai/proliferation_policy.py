"""Public-counter preferences; unknown resource semantics remain neutral."""
from copy import deepcopy

from rules_engine.continuous import effective_toughness, effective_keywords
from rules_engine.named_counters import keyword_counter


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
            keywords = {kind: keyword_counter(kind) for kind in packet['counter_amounts'] if keyword_counter(kind)}
            if keywords:
                from rules_engine.counter_placement import put_counters
                projected = deepcopy(state)
                before = set(effective_keywords(state, card.id))
                for kind in keywords:
                    put_counters(projected, kind, packet['counter_amounts'][kind], target_card_id=card.id)
                after = set(effective_keywords(projected, card.id))
                for kind, keyword in keywords.items():
                    score -= counter_weight(kind) * packet['counter_amounts'][kind]
                    if keyword in after - before:
                        score += {'flying': 3, 'first strike': 2, 'double strike': 4,
                                  'deathtouch': 3, 'haste': 2, 'hexproof': 3,
                                  'indestructible': 4, 'lifelink': 2, 'menace': 2,
                                  'reach': 1, 'shadow': 2, 'trample': 2, 'vigilance': 2}.get(keyword, 0)
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
