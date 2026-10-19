"""Complete entry-emblem grammar and durable source-linked exile permissions."""
from copy import deepcopy
import re

from game_state.state import Zone, object_incarnation

KIND = 'source_linked_exile'
ENTRY = re.compile(r'As (.+?) enters(?: the battlefield)?, you get an emblem with "'
                   r'(You may play cards exiled with (.+?), and you may spend mana '
                   r'as though it were mana of any color to cast those spells\.)"\.?', re.I)


def entry_instruction(line, name):
    from rules_engine.loyalty_instructions import source_matches
    match = ENTRY.fullmatch(line)
    if match and source_matches(match[1], name) and source_matches(match[3], name):
        return match[2]
    return None


def reference(card):
    return {'id': card.id, 'incarnation': object_incarnation(card),
            'sequence': card.zone_change_sequence}


def commit_entry(state, card):
    from rules_engine.closed_loyalty import compile_body
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.loyalty_instructions import resolve
    if card.zone != Zone.BATTLEFIELD or 'Planeswalker' not in card.types:
        return
    if printed_abilities_suppressed(state, card.id):
        return
    program = compile_body(card.oracle_text, card.name)
    if program is None:
        return
    source = reference(card)
    for index, line in enumerate(program['companions']):
        text = entry_instruction(line, card.name)
        if text is None or any(row.get('kind') == KIND and row['source'] == source
                               and row['clause_index'] == index for row in state.loyalty_permissions):
            continue
        resolve(state, card.controller, {'loyalty_operation': 'emblem', 'text': text})
        clauses = [ability['text'] for ability in program['abilities'] if any(
            step['effect_key'] == 'loyalty_source_exile' for step in ability['instructions'])]
        state.loyalty_permissions.append({'kind': KIND, 'emblem_id': state.emblems[-1],
            'controller': card.controller, 'source': deepcopy(source), 'clause_index': index,
            'exile_clauses': clauses, 'cards': []})


def permissions(state, player_id, card_id):
    from rules_engine.zone_actions import is_token_card
    card = state.cards.get(card_id)
    if (card is None or card.zone != Zone.EXILE or is_token_card(card)
            or card.id not in state.players[card.owner].exile):
        return []
    ref = reference(card)
    return [row for row in state.loyalty_permissions if row.get('kind') == KIND
            and row.get('controller') == player_id and ref in row.get('cards', [])
            and (emblem := state.cards.get(row.get('emblem_id'))) is not None
            and emblem.zone == Zone.COMMAND and emblem.id in state.emblems]


def candidates(state, player_id):
    return [cid for cid in state.cards if permissions(state, player_id, cid)]


def mana_requirements(state, player_id, card_id, requirements, payment_kind):
    if payment_kind != 'spell' or not permissions(state, player_id, card_id):
        return requirements
    result = dict(requirements)
    # Substitute only mana spending, after any convoke/delve/improvise choices.
    for color in 'WUBRG':
        result['generic'] += result.get(color, 0)
        result[color] = 0
    return result


def execute(state, controller, payload):
    from effects import handlers
    selection = payload['selection']
    if selection == 'libraries':
        cohort = [cid for player in state.players.values()
                  for cid in player.library[-payload['amount']:]]
    elif selection == 'graveyards':
        cohort = [cid for player in state.players.values() for cid in player.graveyard]
    elif selection == 'target':
        cohort = [payload['target_card_id']]
    else:
        raise ValueError('Unknown compiled source-exile selection')
    before = {cid: reference(state.cards[cid]) for cid in cohort}
    if selection == 'graveyards':
        handlers.exile_all_graveyards(state, controller, payload)
    elif selection == 'target':
        handlers.exile_permanent(state, controller, payload)
    else:
        for cid in cohort:
            card = state.cards[cid]
            state.players[card.owner].library.remove(cid)
            state.players[card.owner].exile.append(cid)
            card.move_to_zone(Zone.EXILE)
            state.log.append(f'{card.name} is exiled.')
    moved = [reference(state.cards[cid]) for cid in cohort
             if state.cards[cid].zone == Zone.EXILE
             and cid in state.players[state.cards[cid].owner].exile
             and state.cards[cid].zone_change_sequence == before[cid]['sequence'] + 1]
    for row in state.loyalty_permissions:
        if (row.get('kind') == KIND and row['source'] == payload['source_reference']
                and payload['loyalty_clause'] in row['exile_clauses']):
            row['cards'].extend(ref for ref in moved if ref not in row['cards'])
