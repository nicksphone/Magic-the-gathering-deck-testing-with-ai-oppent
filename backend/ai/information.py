"""Private decision copies; opaque objects are unknowns, not Magic card data."""
from copy import deepcopy
from collections import Counter
from math import comb
from types import SimpleNamespace

from game_state.state import CardInstance, Zone
from ai.pending_effects import planning_copy


INSPECTED_CHOICES = frozenset({
    'library_top_order', 'library_order_shuffle', 'library_shuffle',
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
    memo = {}
    deck_lists = getattr(state, 'starting_decks', None)
    if deck_lists is not None:
        memo[id(deck_lists)] = {player_id: deepcopy(deck_lists.get(player_id, []))}
    observations = getattr(state, 'card_observations', None)
    visible = {cid for player in state.players.values()
               for cid in player.battlefield + getattr(player, 'graveyard', [])}
    visible.update(state.players[player_id].hand)
    visible.update(cid for cid in getattr(state, 'emblems', []) if cid in state.cards
                   and state.cards[cid].zone == Zone.COMMAND)
    # A resolving spell leaves the stack queue while an owned choice is pending,
    # but its source remains a public stack-zone card until resolution completes.
    visible.update(cid for cid, card in state.cards.items() if getattr(card, 'zone', None) == Zone.STACK)
    for player in state.players.values():
        visible.update(cid for cid in getattr(player, 'exile', [])
                       if not state.cards[cid].exile_face_down or can_look(state.cards[cid], player_id))
    choice = getattr(state, 'pending_mechanic_choice', None) or {}
    if choice.get('player_id') == player_id and choice.get('kind') in INSPECTED_CHOICES:
        visible.update(cid for cid in choice.get('options', []) if isinstance(cid, str))
        visible.update(cid for cid in choice.get('inspected_card_ids', []) if isinstance(cid, str))
    for move in legal_moves:
        cid = move.get('card_id')
        # Authoritative source actions include permitted top-library plays.
        if cid in state.cards:
            visible.add(cid)
    from game_state.observations import remembered_hand_card
    remembered = {cid: known for cid, card in state.cards.items()
                  if cid not in visible and (known := remembered_hand_card(state, player_id, card)) is not None}
    if observations is not None:
        memo[id(observations)] = {player_id: {
            cid: deepcopy(record) for cid, record in observations.get(player_id, {}).items()
            if cid in visible or cid in remembered}}
    for cid, card in state.cards.items():
        if cid in visible:
            continue
        known = remembered.get(cid)
        if known is not None:
            memo[id(card)] = known
            memo[id(card.__dict__)] = known.__dict__
            continue
        # No name, Oracle text, face, cost, stats or retained private metadata.
        # Preserve zone membership/counts; an unknown cannot be cast as a card.
        opaque = CardInstance(cid, '', card.owner, card.controller, card.zone,
                              mana_cost=None, summoning_sick=False)
        opaque.exile_face_down = getattr(card, 'exile_face_down', False)
        opaque.ai_unknown = True
        memo[id(card)] = opaque
        memo[id(card.__dict__)] = opaque.__dict__
    log = getattr(state, 'log', None)
    if isinstance(log, list):
        memo[id(log)] = ['[private trace omitted]' if line.startswith('AI TRACE ') else line for line in log]
    # Seed deepcopy before traversal: private metadata is never copied at all.
    view = planning_copy(state, memo=memo)
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
    from rules_engine.card_types import is_token_card
    for card in state.cards.values():
        if (card.owner == player_id and card.zone != Zone.LIBRARY
                and not is_token_card(card) and not is_unknown(card)):
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


def draw_resource_forecast(state, player_id, draws):
    """Own-list exchangeable prior, or None when known inventory cannot reconcile.

    Never inspect library card instances or transfer opposing deck knowledge.
    Probabilities describe unknown draws, not executable projected card objects.
    """
    from card_data.fallback_cards import fallback_card_payload
    from rules_engine.card_types import is_token_card
    if getattr(state, 'ai_information_player', None) != player_id:
        return None
    rows = getattr(state, 'starting_decks', {}).get(player_id, [])
    if not rows or draws < 0:
        return None
    remaining = Counter()
    land_names = set()
    descriptors = {}
    for row in rows:
        name = row['card_name'].casefold()
        metadata = row if row.get('type_line') else fallback_card_payload(row['card_name'])
        if not metadata or not metadata.get('type_line'):
            return None
        # Face choices need their own resource model; do not guess their value.
        if '//' in metadata['type_line'] or metadata.get('layout', 'normal') not in {'', 'normal'}:
            return None
        remaining[name] += row['quantity']
        descriptor = {'mana_cost': metadata.get('mana_cost', ''),
                      'type_line': metadata['type_line'],
                      'oracle_text': metadata.get('oracle_text', ''),
                      'power': metadata.get('power'), 'toughness': metadata.get('toughness')}
        if name in descriptors and descriptors[name] != descriptor:
            return None
        descriptors[name] = descriptor
        if 'Land' in metadata['type_line'].split():
            land_names.add(name)
    for card in state.cards.values():
        if card.owner != player_id or is_token_card(card):
            continue
        if card.zone == Zone.LIBRARY:
            # An authorized known top/search candidate violates exchangeability.
            # Its conditioned/order-aware model is separate unfinished work.
            if not is_unknown(card):
                return None
            continue
        if is_unknown(card):
            return None
        name = card.printed_characteristics.get('name', card.name).casefold()
        remaining[name] -= 1
    population = len(state.players[player_id].library)
    if any(count < 0 for count in remaining.values()) or sum(remaining.values()) != population or draws > population:
        return None
    lands = sum(remaining[name] for name in land_names)
    expected = draws * lands / population if population else 0.0
    probability = 1 - comb(population-lands, draws)/comb(population, draws) if draws else 0.0
    return {'population': population, 'remaining_lands': lands,
            'expected_lands': expected, 'expected_nonlands': draws-expected,
            'probability_land': probability,
            'inventory': [{'count': count, **descriptors[name]}
                          for name, count in remaining.items() if count],
            'nonland_inventory': [{'count': count, **descriptors[name]}
                                  for name, count in remaining.items() if count and name not in land_names]}


def topdeck_deployment_value(state, player_id):
    """Exchangeable own-list expectation, never hypothetical blockers or ETBs."""
    from ai.heuristics import _noncreature_value
    from rules_engine.mana import mana_value
    from rules_engine.graveyard_permissions import _clauses
    from rules_engine.continuous import printed_abilities_suppressed
    effects = {'topdeck_put_creatures_battlefield', 'topdeck_put_permanents_battlefield'}
    items = [item for item in state.stack if item.controller == player_id and item.effect_key in effects]
    # Multiple library-changing effects need a conditioned joint prior.
    if len(items) != 1 or any(item.effect_key not in effects | {'counter_spell', 'counter_ability'}
                              for item in state.stack):
        return 0.0
    prior = draw_resource_forecast(state, player_id, 0)
    if prior is None or not prior['population']:
        return 0.0
    item = items[0]
    payload = item.payload
    n = prior['population']
    draws = min(n, max(0, int(payload.get('top_n', 0))))
    cap = max(0, int(payload.get('max_creatures', payload.get('max_permanents', 0))))
    if not draws or not cap:
        return 0.0
    clauses = {clause for player in state.players.values() for cid in player.battlefield
               if not printed_abilities_suppressed(state, cid) for clause in _clauses(state.cards[cid])}
    values = Counter()
    for row in prior['inventory']:
        types = set(row['type_line'].split('//', 1)[0].split('\u2014', 1)[0].split())
        if not types & {'Creature', 'Artifact', 'Enchantment', 'Land', 'Planeswalker'}:
            continue
        if item.effect_key == 'topdeck_put_creatures_battlefield' and 'Creature' not in types:
            continue
        if payload.get('allowed_type') and payload['allowed_type'] not in types:
            continue
        mv = mana_value(row['mana_cost'] or '', is_land='Land' in types)
        if payload.get('mv_max') is not None and mv > payload['mv_max']:
            continue
        if any(f"{kind} cards in graveyards and libraries {verb} enter the battlefield." in clauses
               for kind in (['nonland permanent'] if 'Land' not in types else [])
               + (['creature'] if 'Creature' in types else []) for verb in ("can't", 'cannot')):
            continue
        if 'Creature' in types:
            try:
                value = max(0, int(row['power'])) * 1.35 + max(0, int(row['toughness'])) * .55 + .25
            except (TypeError, ValueError):
                continue
        elif 'Land' in types:
            lands = sum('Land' in state.cards[cid].types for cid in state.players[player_id].battlefield)
            value = 1.0 if lands < 4 else .12
        else:
            value = _noncreature_value(SimpleNamespace(types=list(types), **row))
        values[max(0, value)] += row['count']
    # Integrate survival counts: exact expected sum of the best capped hits,
    # including whiffs, without enumerating hands or consulting library order.
    result = 0.0
    hits = 0
    levels = sorted(values, reverse=True) + [0.0]
    denominator = comb(n, draws)
    for index, value in enumerate(levels[:-1]):
        hits += values[value]
        expected = sum(min(cap, k) * comb(hits, k) * comb(n-hits, draws-k) / denominator
                       for k in range(max(0, draws-(n-hits)), min(draws, hits)+1))
        result += (value-levels[index+1]) * expected
    return .95 * result
