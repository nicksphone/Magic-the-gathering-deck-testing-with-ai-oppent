"""Additional complete official objects for the metadata fixture migration."""
import hashlib
import json
from pathlib import Path

from tests.canonical_positive_fixtures import raw_card as existing_raw_card


ROOT = Path(__file__).parent / 'fixtures/deck_service_metadata_6900'
SOURCES = {
    'Memnite': ('memnite-scryfall-raw.json',
                '7b177ce7bfcf88d3c1fb931d961ef21b8278b2d42d87c8cc60e8543708561ddf'),
    'Kazandu Mammoth // Kazandu Valley': ('kazandu-mammoth-scryfall-raw.json',
                '74e2b3ef8022a0bc21fbb033e51a41db797cd195c89feb5b4c72c5e07c0b45b8'),
}


def raw_card(name):
    if name not in SOURCES:
        return existing_raw_card(name)
    filename, digest = SOURCES[name]
    data = (ROOT / filename).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == name
    return raw
