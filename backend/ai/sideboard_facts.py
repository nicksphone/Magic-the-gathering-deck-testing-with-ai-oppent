"""Private candidate-local sideboarding facts; never inferred from log strings."""
from collections import Counter
from copy import deepcopy


def initialize(state, inventory):
    state.sideboard_facts = {
        'version': 1, 'game_id': state.id, 'complete': False,
        'capture_version': 3, 'coverage_ok': True, 'terminal_winner': None,
        'inventory': deepcopy(inventory),
        'seats': {str(pid): {'hand_entries': {}, 'protected': [],
                            'observed_creatures': [], 'observed_creature_sources': {}} for pid in (1, 2)},
    }


def copy_facts(value, state):
    """Old absent facts stay unknown; a new malformed private snapshot rejects."""
    if value == {} and type(value) is dict:
        return {}
    base = {'version', 'game_id', 'complete', 'inventory', 'seats'}
    extra = {'capture_version', 'coverage_ok', 'terminal_winner'}
    valid = (type(value) is dict and set(value) in (base, base | extra)
        and type(value['version']) is int and value['version'] == 1
        and value['game_id'] == state.id and type(value['complete']) is bool
        and type(value['inventory']) is dict
        and type(value['seats']) is dict and set(value['seats']) == {'1', '2'})
    if not valid:
        raise ValueError('Invalid private sideboard facts')
    if set(value) == base:
        if value['complete']:
            raise ValueError('Old facts cannot certify complete capture')
    elif (type(value['capture_version']) is not int or value['capture_version'] not in (2, 3)
            or type(value['coverage_ok']) is not bool
            or value['terminal_winner'] is not None and (
                type(value['terminal_winner']) is not int or value['terminal_winner'] not in (0, 1, 2))
            or value['complete'] and (not value['coverage_ok']
                or value['terminal_winner'] is None or value['terminal_winner'] != state.winner)):
        raise ValueError('Invalid completed sideboard capture')
    counts = {1: Counter(), 2: Counter()}
    for cid, binding in value['inventory'].items():
        if (type(cid) is not str or cid not in state.cards or type(binding) is not dict
                or set(binding) != {'owner', 'stock_key'}
                or type(binding['owner']) is not int or binding['owner'] not in (1, 2)
                or binding['owner'] != state.cards[cid].owner
                or type(binding['stock_key']) is not str or not binding['stock_key'].strip()):
            raise ValueError('Invalid sideboard inventory binding')
        counts[binding['owner']][binding['stock_key']] += 1
    for pid in (1, 2):
        expected = Counter()
        rows = {}
        for row in state.starting_decks.get(pid, []):
            if (type(row.get('quantity')) is not int or row['quantity'] <= 0
                    or type(row.get('card_name')) is not str):
                raise ValueError('Invalid starting inventory')
            expected[row['card_name']] += row['quantity']
            rows[row['card_name']] = row
        if counts[pid] != expected:
            raise ValueError('Sideboard inventory does not match original stock')
        for cid, binding in value['inventory'].items():
            if binding['owner'] != pid:
                continue
            card, row = state.cards[cid], rows[binding['stock_key']]
            name = card.printed_characteristics.get('name', card.name)
            faces = row.get('card_faces') or []
            birth_name = (faces[0]['name'] if faces and row.get('layout') in {'transform', 'modal_dfc'}
                          else row['card_name'])
            if name != birth_name or card.card_faces != faces:
                raise ValueError('Sideboard stock does not match physical printed source')
        seat = value['seats'][str(pid)]
        seat_fields = {'hand_entries', 'protected', 'observed_creatures'}
        current_capture = value.get('capture_version') == 3
        if (type(seat) is not dict or set(seat) not in (
                seat_fields, seat_fields | {'observed_creature_sources'})
                or current_capture and 'observed_creature_sources' not in seat
                or type(seat['hand_entries']) is not dict):
            raise ValueError('Invalid private sideboard seat')
        for cid, sequence in seat['hand_entries'].items():
            if (cid not in value['inventory'] or value['inventory'][cid]['owner'] != pid
                    or type(sequence) is not int or sequence < 0
                    or sequence > state.cards[cid].zone_change_sequence):
                raise ValueError('Invalid original hand-entry reference')
        for key in ('protected', 'observed_creatures'):
            ids = seat[key]
            if (type(ids) is not list or any(type(cid) is not str or not cid for cid in ids)
                    or len(set(ids)) != len(ids)):
                raise ValueError('Invalid private fact identities')
            if key == 'protected' and any(cid not in value['inventory']
                    or value['inventory'][cid]['owner'] != pid for cid in ids):
                raise ValueError('Invalid protected inventory source')
        if current_capture:
            from rules_engine.card_types import CARD_TYPES
            sources = seat['observed_creature_sources']
            if type(sources) is not dict or set(sources) != set(seat['observed_creatures']):
                raise ValueError('Invalid historical creature source roster')
            for cid, source in sources.items():
                card = state.cards.get(cid)
                record = state.card_observations.get(pid, {}).get(cid)
                if (type(source) is not dict or set(source) != {
                        'cid', 'owner', 'controller', 'zone_change_sequence', 'effective_types'}
                        or card is None or source['cid'] != cid
                        or type(source['owner']) is not int or source['owner'] != card.owner
                        or type(source['controller']) is not int or source['controller'] != 3-pid
                        or type(source['zone_change_sequence']) is not int
                        or not 0 <= source['zone_change_sequence'] <= card.zone_change_sequence
                        or type(source['effective_types']) is not list
                        or any(type(kind) is not str or kind not in CARD_TYPES for kind in source['effective_types'])
                        or len(set(source['effective_types'])) != len(source['effective_types'])
                        or 'Creature' not in source['effective_types']
                        or cid not in value['inventory'] and card.is_token is not True
                        or type(record) is not dict or record.get('id') != cid
                        or record.get('owner') != source['owner']
                        or type(record.get('zone_change_sequence')) is not int
                        or not source['zone_change_sequence'] <= record['zone_change_sequence'] <= card.zone_change_sequence):
                    raise ValueError('Invalid retained public creature source')
    result = deepcopy(value)
    if result.get('capture_version') != 3:
        result['complete'] = False
        if 'capture_version' in result:
            result['coverage_ok'] = False
            result['terminal_winner'] = None
    return result


def record_event(state, event, payload):
    # Projection/rejected candidate facts cannot become live controller facts.
    facts = getattr(state, 'sideboard_facts', {})
    if not facts or facts.get('capture_version') != 3 or getattr(state, 'ai_information_player', None) is not None:
        return
    if event in {'damage_dealt', 'combat_damage_dealt'} and type(payload.get('amount')) is int and payload['amount'] > 0:
        protect_source(state, payload.get('source_card_id'))
    if event in {'discard', 'sacrifice', 'permanent_dies', 'creature_dies', 'leaves_battlefield', 'enters_graveyard'}:
        protect_source(state, payload.get('card_id'))
    if event in {'spell_cast', 'enters_battlefield'}:
        cid = payload.get('card_id')
        card = state.cards.get(cid)
        if card is None or card.exile_face_down or card.zone.value not in {'stack', 'battlefield'}:
            return
        binding = facts['inventory'].get(cid)
        if binding is None and card.is_token is not True:
            protect_source(state, cid)
            return
        if binding:
            protected = facts['seats'][str(binding['owner'])]['protected']
            if cid not in protected:
                protected.append(cid)
        from rules_engine.continuous import effective_types
        types = effective_types(state, card)
        if card.controller in (1, 2) and 'Creature' in types:
            seat = facts['seats'][str(3-card.controller)]
            observed = seat['observed_creatures']
            if cid not in observed:
                observed.append(cid)
                seat['observed_creature_sources'][cid] = {
                    'cid': cid, 'owner': card.owner, 'controller': card.controller,
                    'zone_change_sequence': card.zone_change_sequence,
                    'effective_types': list(types)}
        return
    if event != 'draw_card':
        return
    pid, cid = payload.get('player_id'), payload.get('card_id')
    binding = facts['inventory'].get(cid)
    card = state.cards.get(cid)
    if type(pid) is not int or pid not in (1, 2) or binding is None or card is None:
        facts['complete'] = False
        facts['coverage_ok'] = False
        return
    if binding['owner'] != pid or card.owner != pid or card.zone.value != 'hand':
        facts['complete'] = False
        facts['coverage_ok'] = False
        return
    facts['seats'][str(pid)]['hand_entries'].setdefault(cid, card.zone_change_sequence)


def held_unused_ids(state, player_id):
    """Candidate hand identities; caller must separately require completed coverage."""
    facts = getattr(state, 'sideboard_facts', {})
    if (not facts or type(player_id) is not int
            or player_id not in (1, 2)):
        return ()
    seat = facts['seats'][str(player_id)]
    protected_keys = {facts['inventory'][cid]['stock_key'] for cid in seat['protected']}
    result = []
    for cid in state.players[player_id].hand:
        card = state.cards[cid]
        binding = facts['inventory'].get(cid)
        if (binding and binding['owner'] == player_id and card.owner == player_id
                and card.zone.value == 'hand' and cid in seat['hand_entries']
                and seat['hand_entries'][cid] == card.zone_change_sequence
                and binding['stock_key'] not in protected_keys):
            result.append(cid)
    return tuple(result)


def protect_source(state, cid):
    facts = getattr(state, 'sideboard_facts', {})
    if not facts or facts.get('capture_version') != 3 or getattr(state, 'ai_information_player', None) is not None:
        return
    binding = facts['inventory'].get(cid)
    if binding is None:
        # A newly created token is not an original inventory unit. Its genuine
        # cast/activation/trigger producer is protected separately, never by name.
        if cid not in state.cards or state.cards[cid].is_token is not True:
            facts['coverage_ok'] = False
            facts['complete'] = False
        return
    protected = facts['seats'][str(binding['owner'])]['protected']
    if cid not in protected:
        protected.append(cid)


def record_accepted_action(before, after, player_id, action):
    """Called only after checked_action succeeds, never on a projected branch."""
    facts = getattr(after, 'sideboard_facts', {})
    if not facts or facts.get('capture_version') != 3 or getattr(after, 'ai_information_player', None) is not None:
        return
    if after is before or facts is getattr(before, 'sideboard_facts', None):
        raise ValueError('Accepted action must own its candidate facts')
    if action.get('card_id') is not None:
        protect_source(after, action['card_id'])
    for cid in action.get('attackers', []):
        protect_source(after, cid)
    for bids in action.get('blocks', {}).values():
        for cid in bids if isinstance(bids, list) else [bids]:
            protect_source(after, cid)
    if before.winner is None and type(after.winner) is int and after.winner in (0, 1, 2):
        facts['terminal_winner'] = after.winner


def seal_game(state):
    facts = getattr(state, 'sideboard_facts', {})
    if (not facts or facts.get('capture_version') != 3 or not facts.get('coverage_ok')
            or type(state.winner) is not int or facts.get('terminal_winner') != state.winner
            or getattr(state, 'ai_information_player', None) is not None):
        return False
    copy_facts(facts, state)
    facts['complete'] = True
    return True


def summary_for(state, player_id):
    """Owned history and durable authorized public observations, no enemy hand/pending."""
    facts = getattr(state, 'sideboard_facts', {})
    if type(player_id) is not int or player_id not in (1, 2) or not facts or not facts['complete']:
        return {'qualified': False}
    copy_facts(facts, state)
    from rules_engine.continuous import effective_types
    own = facts['seats'][str(player_id)]
    held = Counter(facts['inventory'][cid]['stock_key'] for cid in held_unused_ids(state, player_id))
    protected = sorted({facts['inventory'][cid]['stock_key'] for cid in own['protected']})
    observed_types = set()
    public_type_groups = []
    for record in state.card_observations.get(player_id, {}).values():
        if record.get('controller') != player_id:
            observed_types.update(record.get('types', []))
            public_type_groups.append(list(record.get('types', [])))
    return {'qualified': True, 'held_counts': dict(held), 'protected_stock': protected,
            'observed_creature_count': len(own['observed_creatures']),
            'observed_types': sorted(observed_types),
            'public_type_groups': public_type_groups,
            'own_creature_count': sum('Creature' in effective_types(state, state.cards[cid])
                for cid in state.players[player_id].battlefield)}
