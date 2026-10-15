"""Pinned complete official facts for the day/night APNAP fixture only."""
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, Zone, _infer_keywords
from rules_engine.card_faces import apply_transform_face
from rules_engine.card_types import printed_card_types


FIXTURES = Path(__file__).parent / 'fixtures'
DIRECTORY = FIXTURES / 'day_night_apnap_canonical'
CATHAR = 'Brutal Cathar // Moonrage Brute'
SEED = FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
PROVENANCE_SHA = '179370a18fcc8d43838aeb9f3246b0dd16ef183b1397db6dccff08d9881d89fe'
SOURCES = {
    'Phyrexian Arena': ('phyrexian-arena-scryfall-raw.json',
                       '68fe7fdd9f842cc679b34fec3c69e3b2201e54e4a6e9dbd2f2f0486e43f4023f'),
    'Corruption of Towashi': ('corruption-of-towashi-scryfall-raw.json',
                              '9eecdd8eb4e08a9363414acfefae08e4cfb7180825f01a07396c7b781156d170'),
}
DISPLAY_IMAGE = 'fixture:day-night-apnap'  # Nonempty: normalization must not generate art.


def raw_card(name):
    if name == CATHAR:
        data = SEED.read_bytes()
        assert hashlib.sha256(data).hexdigest() == SEED_SHA
        rows = [json.loads(line) for line in data.splitlines()]
        matches = [row for row in rows if row.get('name') == name]
        assert len(matches) == 1
        raw = matches[0]
    else:
        file, pin = SOURCES[name]
        data = (DIRECTORY / file).read_bytes()
        assert hashlib.sha256(data).hexdigest() == pin
        raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == name
    return raw


def permanent(card_id, name, owner):
    """Construct fixture facts only: no cast, entry/transform event or stock grant."""
    cached = ScryfallSyncService._normalize_payload(raw_card(name), DISPLAY_IMAGE)
    number = lambda value: int(value) if value is not None else None
    card = CardInstance(
        card_id, cached['name'], owner, owner, Zone.BATTLEFIELD,
        types=printed_card_types(cached['type_line']), type_line=cached['type_line'],
        oracle_text=cached['oracle_text'], mana_cost=cached['mana_cost'],
        power=number(cached['power']), toughness=number(cached['toughness']),
        printed_power=cached['power'], printed_toughness=cached['toughness'],
        loyalty=number(cached['loyalty']), colors=cached['colors'].split(',') if cached['colors'] else [],
        keywords=_infer_keywords(cached['oracle_text']), image_uri=cached['image_uri'],
        layout=cached['layout'], card_faces=json.loads(cached['card_faces_json']),
    )
    if card.card_faces:
        apply_transform_face(card, 0)
    return card
