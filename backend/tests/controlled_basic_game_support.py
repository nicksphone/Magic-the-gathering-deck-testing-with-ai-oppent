"""Uncaptured births for six explicit synthetic basic-land fixture templates."""
from copy import deepcopy
import random
import uuid

from game_state import state as states


_TEMPLATES = [
    {'quantity': 60, 'card_name': name}
    for name in ('Forest', 'Island', 'Swamp', 'Mountain')
] + [
    {'quantity': 60, 'card_name': 'Forest', 'type_line': 'Basic Land - Forest',
     'oracle_text': '{T}: Add {G}.'},
    {'quantity': 60, 'card_name': 'Island', 'type_line': 'Basic Land - Island'},
]


def controlled_basic_game(deck_a, deck_b, player_a_name='Player A',
                          player_b_name='Player B', seed=None):
    """Preserve the old board/RNG, without ever capturing synthetic stock."""
    for deck in (deck_a, deck_b):
        if (type(deck) is not list or len(deck) != 1 or type(deck[0]) is not dict
                or any(type(key) is not str for key in deck[0])
                or type(deck[0].get('quantity')) is not int
                or any(type(value) is not str for key, value in deck[0].items()
                       if key != 'quantity') or deck[0] not in _TEMPLATES):
            raise ValueError('Unknown controlled basic-land template')
    if seed is not None and type(seed) is not int:
        raise ValueError('Controlled seed must be an integer or None')
    players = {1: states.PlayerState(1, player_a_name), 2: states.PlayerState(2, player_b_name)}
    rng = random.Random(seed) if seed is not None else random
    cards = {}
    for pid, deck in ((1, deck_a), (2, deck_b)):
        expanded = [deck[0]] * 60
        rng.shuffle(expanded)
        for index, row in enumerate(expanded, 1):
            cid = f'p{pid}-{index:03d}'
            cards[cid] = states.CardInstance(
                id=cid, name=row['card_name'], owner=pid, controller=pid,
                zone=states.Zone.LIBRARY, types=['Land'], summoning_sick=False,
                oracle_text=row.get('oracle_text', ''), type_line=row.get('type_line', ''),
                instance_order=index)
            players[pid].library.append(cid)
    state = states.MatchState(id=str(uuid.uuid4()), players=players, cards=cards, stack=[])
    state.starting_decks = {1: deepcopy(deck_a), 2: deepcopy(deck_b)}
    state.rng = rng if seed is not None else random.Random()
    for pid in (1, 2):
        for _ in range(7):
            states.draw_card(state, pid)
    state.log.append('Game start. Both players draw 7 and decide on London mulligans.')
    return state
