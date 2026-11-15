"""A Battle synced through the card cache keeps its printed defense into a match."""
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory

PRINTING = Path(__file__).parent / 'fixtures/battle_full_printing/invasion-of-zendikar-mom-194.json'


def test_synced_battle_faces_keep_defense_for_match_start():
    raw = json.loads(PRINTING.read_text())
    printed = raw['card_faces'][0]['defense']
    normalized = ScryfallSyncService._normalize_payload(raw, 'unused:test')
    faces = json.loads(normalized['card_faces_json'])
    assert faces[0]['defense'] == printed
    assert 'defense' not in faces[1]
    deck = [{'card_name': raw['name'], 'quantity': 1, 'layout': raw['layout'],
             'type_line': normalized['type_line'], 'oracle_text': normalized['oracle_text'],
             'mana_cost': normalized['mana_cost'], 'card_faces': faces}]
    state = MatchFactory.from_decks(deck, deck, seed=7)
    front = raw['card_faces'][0]['name']
    battles = [card for card in state.cards.values() if card.name == front]
    assert battles and all(card.printed_defense == printed for card in battles)


def test_nonbattle_faces_are_unchanged():
    face = {'name': 'Front', 'mana_cost': '{1}', 'type_line': 'Creature', 'oracle_text': '',
            'power': '1', 'toughness': '1'}
    out = ScryfallSyncService._normalize_faces([face])
    assert 'defense' not in out[0]
