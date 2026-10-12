"""Trusted primitive fixtures, NOT admission of canonical Vraska's full card."""
import hashlib
import json
from pathlib import Path

from game_state.state import CardInstance, Zone
from tests.test_linked_damage_targets import raw_card

DIAGNOSTIC = {'name': 'Closed-surface loyalty destruction probe', 'mana_cost': '',
              'type_line': 'Planeswalker', 'colors': [], 'loyalty': '5',
              'oracle_text': '-3: Destroy target creature.'}


def source(state, seat=1):
    row = DIAGNOSTIC
    card = CardInstance(state.allocate_object_id(), row['name'], seat, seat,
                        Zone.BATTLEFIELD, ['Planeswalker'], oracle_text=row['oracle_text'],
                        type_line=row['type_line'], colors=row['colors'], loyalty=int(row['loyalty']))
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    return card


def artifact_creature(state, seat=1):
    path = Path(__file__).parent / 'fixtures/attached_characteristics/ornithopter.json'
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == '95f8fbf0378f3ee81838a6483669df62476253a530a96852e10784aa46ce001b'
    return raw_card(state, json.loads(data), seat, Zone.BATTLEFIELD)
