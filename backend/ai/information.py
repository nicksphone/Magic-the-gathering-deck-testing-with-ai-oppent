"""Private decision copies; opaque objects are unknowns, not Magic card data."""
from copy import deepcopy
from collections import Counter
from types import SimpleNamespace

from game_state.state import CardInstance, Zone
from ai.pending_effects import planning_copy


INSPECTED_CHOICES = frozenset({
    'scry', 'scry_top_order', 'surveil', 'surveil_top_order', 'topdeck_bottom_order',
    'search_library', 'topdeck_put', 'topdeck_reveal_creature',
    'look_top_choose', 'look_top_select_hand', 'choose_revealed_discard', 'choose_revealed_exile',
})


def is_unknown(card):
    return bool(card is not None and (getattr(card, 'ai_unknown', False)
                or (not getattr(card, 'name', None) and not getattr(card, 'types', []))))


def decision_view(state, player_id, legal_moves):
    """Keep current authorized observations, never expose an unseen draw/reply."""
    from rules_engine.foretell import can_look
    view = planning_copy(state)
    view.starting_decks = {player_id: deepcopy(getattr(state, 'starting_decks', {}).get(player_id, []))}
    visible = {cid for player in state.players.values()
               for cid in player.battlefield + getattr(player, 'graveyard', [])}
    visible.update(state.players[player_id].hand)
    visible.update(getattr(item, 'source_card_id', getattr(item, 'card_id', None))
                   for item in getattr(state, 'stack', []))
    for player in state.players.values():
        visible.update(cid for cid in getattr(player, 'exile', [])
                       if not state.cards[cid].exile_face_down or can_look(state.cards[cid], player_id))
    choice = getattr(state, 'pending_mechanic_choice', None) or {}
    if choice.get('player_id') == player_id and choice.get('kind') in INSPECTED_CHOICES:
        visible.update(cid for cid in choice.get('options', []) if isinstance(cid, str))
    for move in legal_moves:
        cid = move.get('card_id')
        # Authoritative source actions include permitted top-library plays.
        if cid in state.cards:
            visible.add(cid)
    for cid, card in list(view.cards.items()):
        if cid in visible:
            continue
        # No name, Oracle text, face, cost, stats or retained private metadata.
        # Preserve zone membership/counts; an unknown cannot be cast as a card.
        opaque = CardInstance(cid, '', card.owner, card.controller, card.zone,
                              mana_cost=None, summoning_sick=False)
        opaque.exile_face_down = getattr(card, 'exile_face_down', False)
        opaque.ai_unknown = True
        view.cards[cid] = opaque
    view.log = ['[private trace omitted]' if line.startswith('AI TRACE ') else line
                for line in getattr(state, 'log', [])]
    view.ai_information_player = player_id
    return view, deepcopy(legal_moves)


def known_search_land_count(state, player_id, contains):
    """Estimate land availability from one's submitted list, not hidden instances.

    This is an upper bound when hidden removals occurred. Actual resolution
    still searches only the authoritative, legally inspected library options.
    """
    from card_data.fallback_cards import fallback_card_payload
    from rules_engine.oracle_effects import search_card_matches
    player = state.players[player_id]
    observed = Counter()
    for cid in player.hand + player.battlefield + player.graveyard + player.exile:
        card = state.cards[cid]
        if card.owner == player_id and not is_unknown(card):
            observed[card.printed_characteristics.get('name', card.name).casefold()] += 1
    count = 0
    for row in getattr(state, 'starting_decks', {}).get(player_id, []):
        name = row['card_name']
        metadata = row if row.get('type_line') else (fallback_card_payload(name) or {})
        type_line = str(metadata.get('type_line') or '').split('//', 1)[0].strip()
        # A printed-data descriptor, never inserted into gameplay state.
        card = SimpleNamespace(name=name, type_line=type_line, types=type_line.split(),
                               mana_cost=metadata.get('mana_cost'), colors=metadata.get('colors'),
                               oracle_text=metadata.get('oracle_text', ''))
        if 'Land' in card.types and search_card_matches(card, contains):
            available = max(0, row['quantity'] - observed[name.casefold()])
            observed[name.casefold()] = max(0, observed[name.casefold()] - row['quantity'])
            count += available
    return min(count, len(player.library))
