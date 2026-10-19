"""Full committed official RAW; runtime poses move physical cards, never their facts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from game_state.state import CardInstance, MatchFactory, Zone, _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_types import printed_card_types


SEED = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
WIRE = SEED.read_bytes()
assert hashlib.sha256(WIRE).hexdigest() == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
ROWS = {row['name']: row for row in map(json.loads, WIRE.splitlines())}
ADMITTED = ('Leyline Binding', 'Herd Migration', 'Plains', 'Island', 'Swamp', 'Forest',
            "Jetmir's Garden", "Raffine's Tower", 'Tropical Island', 'Temple Garden',
            'Waterlogged Grove')


def raw(name):
    assert name in ADMITTED
    row = deepcopy(ROWS[name])
    assert row['object'] == 'card' and row['name'] == name and len(row) > 30
    return row


def deck(name, quantity):
    return {**raw(name), 'card_name': name, 'quantity': quantity}


def card(name, **physical):
    assert set(physical) <= {'id', 'owner', 'controller', 'zone', 'tapped'}
    row = raw(name)
    kinds = printed_card_types(row['type_line'])
    return CardInstance(name=name, types=kinds, mana_cost=row['mana_cost'],
        oracle_text=row['oracle_text'], type_line=row['type_line'],
        power=_infer_power(name, row.get('power'), kinds),
        toughness=_infer_toughness(name, row.get('toughness'), kinds),
        printed_power=row.get('power'), printed_toughness=row.get('toughness'),
        loyalty=int(row['loyalty']) if row.get('loyalty') is not None else None,
        colors=row['colors'], keywords=_infer_keywords(row['oracle_text']),
        layout=row['layout'], card_faces=row.get('card_faces', []), **physical)


def complete_state(basic, other, *, spell, lands):
    names = (spell, *lands)
    return MatchFactory.from_decks(
        [deck(basic, 60 - len(names)), *[deck(name, 1) for name in names]],
        [deck(other, 60)])


def put_in_hand(state, name):
    player = state.players[1]
    found = next(cid for cid in player.hand + player.library if state.cards[cid].name == name)
    if found in player.hand:
        index = player.hand.index(found)
        player.hand[0], player.hand[index] = player.hand[index], player.hand[0]
    else:
        index = player.library.index(found)
        prior = player.hand[0]
        player.hand[0], player.library[index] = found, prior
        state.cards[found].zone, state.cards[prior].zone = Zone.HAND, Zone.LIBRARY


def library_card(state, name):
    player = state.players[1]
    found = next(cid for cid in player.library + player.hand if state.cards[cid].name == name)
    if found in player.hand:
        index = player.hand.index(found)
        prior = player.library[-1]
        player.hand[index], player.library[-1] = prior, found
        state.cards[prior].zone, state.cards[found].zone = Zone.HAND, Zone.LIBRARY
    player.library.remove(found)
    return found
