"""Complete loyalty combat instructions, using the ordinary trigger queue."""
import re
from copy import deepcopy


PLAYER_LOSS = r'Whenever this (?:creature|token) deals combat damage to a player, that player loses the game\.'


def compile_instruction(text, name):
    from rules_engine.loyalty_instructions import COUNT, node, number, source_matches
    retaliation = re.fullmatch(r'Until your next turn, whenever a creature deals combat damage to (.+?), '
                              r'destroy that creature\.', text, re.I)
    if retaliation and (source_matches(retaliation[1], name)
                        or name and retaliation[1].casefold() == name.split()[0].casefold()):
        return [node('combat_retaliation')]
    token = re.fullmatch(r'Create (' + COUNT + r') (\d+)/(\d+) '
                        r'(white|blue|black|red|green|colorless) ([a-z]+(?: [a-z]+)*) '
                        r'creature tokens? with "(' + PLAYER_LOSS + r')"', text, re.I)
    if token and 1 <= number(token[1]) <= 20:
        return [node('combat_loss_tokens', amount=number(token[1]), power=int(token[2]),
                     toughness=int(token[3]), color=token[4].lower(), subtype=token[5],
                     oracle_text=token[6])]
    return None


def resolve(state, controller, payload):
    from effects import handlers
    from rules_engine.loyalty_instructions import reference_matches
    kind = payload['loyalty_operation']
    if kind == 'combat_retaliation':
        state.loyalty_permissions.append({'kind': 'combat_retaliation', 'controller': controller,
            'created_turn': state.turn, 'source_reference': deepcopy(payload['source_reference'])})
    elif kind == 'combat_retaliation_destroy':
        if reference_matches(state, payload.get('target_card_id'), payload.get('target_reference')):
            handlers.destroy_permanent(state, controller, payload)
    elif kind == 'combat_loss_tokens':
        colors = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}
        handlers.create_token(state, controller, {**payload, 'name': payload['subtype'].title(),
            'type_line': 'Token Creature - ' + payload['subtype'].title(),
            'colors': [colors[payload['color']]] if payload['color'] in colors else [],
            'keywords': []})


def collect_retaliation(state, event, payload):
    from game_state.state import Zone, object_incarnation
    from rules_engine.loyalty_instructions import card_reference
    from rules_engine.type_effects import effective_types
    if event != 'combat_damage_dealt' or payload.get('amount', 0) <= 0:
        return []
    creature = state.cards.get(payload.get('source_card_id'))
    if creature is None or 'Creature' not in effective_types(state, creature):
        return []
    out = []
    for permission in state.loyalty_permissions:
        if permission.get('kind') != 'combat_retaliation':
            continue
        ref = permission['source_reference']
        source = state.cards.get(ref['id'])
        if (source is None or source.zone != Zone.BATTLEFIELD
                or object_incarnation(source) != ref['incarnation']
                or source.zone_change_sequence != ref['sequence']
                or (payload.get('target_key') != 'planeswalker:' + source.id
                    and payload.get('target_card_id') != source.id)):
            continue
        out.append({'source_card_id': source.id, 'controller': permission['controller'],
            'label': source.name + ' combat damage trigger',
            'effect_key': 'loyalty_combat_retaliation_destroy',
            'payload': {'target_card_id': creature.id,
                        'target_reference': card_reference(state, creature.id)}})
    return out
