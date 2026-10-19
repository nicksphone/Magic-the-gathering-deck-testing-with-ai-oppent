"""Fresh complete official objects for the bounded positive-fixture batch."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from card_data.sync import ScryfallSyncService
from tests.test_knowledge_ingest import _official_card


FIXTURES = Path(__file__).parent / 'fixtures'
SEED = 'knowledge_profiles/seed155-scryfall.jsonl'
CACHED_IMAGE_URI = '/card-images/card-1.jpg'  # Existing display-only test override.
PINS = {
    SEED: '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
    'canonical_hydration/valki-scryfall-raw.json': 'ae2bb42378419e9b961eff2f27c7a4c2b7b4ec4af0b72dc3ce7bf4b8a7f87f86',
    'graveyard_permissions/bala-ged-recovery.json': 'b9975731051f8b8fc6c7eeadcfa205141d50593df7c11b4609fb2b8d6344e65c',
    'combat_ability_provenance.json': '1921f7439fd82e2ec1a589db8028581933f2a9af4dcc9a978d41346b9989aa92',
    '../vraska_full/fixtures/grizzly-bears-scryfall-raw.json': '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c',
    'canonical_positive_batch/flame-rift-scryfall-raw.json': '77cfdf089faf060867ed53b1f26a53e239b94e0f107085b691a24c326bb027c3',
    'canonical_positive_batch/mystic-sanctuary-scryfall-raw.json': 'dc07c9dc5413b8d760a85766183e43a671d245bfb22cf840d9e72f5da16f0ab7',
    'canonical_positive_batch/island-sanctuary-scryfall-raw.json': 'b53aa77038055aec838b57c44b3b5aecc3e74709971a7d865178744e908cf9db',
    'canonical_positive_batch/fire-ice-scryfall-raw.json': '3edb6afa6d478f386bf6fc64e8a1bb4cc395615c824e65fe1ca9bd6cb366ab97',
    'canonical_positive_batch/old-fogey-scryfall-raw.json': '4d9c15eac7c64a8e39a84df4ba5d9eb4509cf6b43a0260015ca3fb9cc5e4fb4b',
    'canonical_positive_batch/willbender-scryfall-raw.json': 'a5ca577631beb78b60f8e1fc1744b3b454806bec1389e5631760bc02ea7d5f8d',
}
SOURCES = {
    'Valki, God of Lies // Tibalt, Cosmic Impostor': 'canonical_hydration/valki-scryfall-raw.json',
    'Bala Ged Recovery // Bala Ged Sanctuary': 'graveyard_permissions/bala-ged-recovery.json',
    'Benalish Hero': 'combat_ability_provenance.json',
    'Grizzly Bears': '../vraska_full/fixtures/grizzly-bears-scryfall-raw.json',
    **{name: 'canonical_positive_batch/' + slug + '-scryfall-raw.json' for name, slug in (
        ('Flame Rift', 'flame-rift'), ('Mystic Sanctuary', 'mystic-sanctuary'),
        ('Island Sanctuary', 'island-sanctuary'), ('Fire // Ice', 'fire-ice'),
        ('Old Fogey', 'old-fogey'), ('Willbender', 'willbender'))},
}


def raw_card(name):
    source = SOURCES.get(name, SEED)
    data = (FIXTURES / source).read_bytes()
    assert hashlib.sha256(data).hexdigest() == PINS[source]
    if source == SEED:
        # This is the actual official parent, not a fabricated front-face record.
        return _official_card('Wedding Announcement // Wedding Festivity'
                              if name == 'Wedding Announcement' else name)
    value = json.loads(data)
    rows = value if type(value) is list else [value]
    matches = [row for row in rows if row.get('name') == name]
    assert len(matches) == 1 and matches[0].get('object') == 'card'
    return matches[0]


def deck_entry(name, quantity):
    return {'quantity': quantity, 'card_name': name, 'card_metadata': raw_card(name)}


def cached_card(name):
    return SimpleNamespace(**ScryfallSyncService._normalize_payload(raw_card(name), CACHED_IMAGE_URI))
