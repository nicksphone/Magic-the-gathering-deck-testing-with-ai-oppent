"""Named positive fixtures match complete archived official rows, without SQL."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import tests.test_knowledge_ingest as original


FIXTURES = Path(__file__).parent / 'fixtures'
BEARS = Path(__file__).parent / 'vraska_full/fixtures'


def archived_card(name):
    if name == 'Grizzly Bears':
        raw = (BEARS/'grizzly-bears-scryfall-raw.json').read_bytes()
        pin = '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c'
        assert hashlib.sha256(raw).hexdigest() == pin
        provenance = json.loads((BEARS/'PROVENANCE.json').read_bytes())
        assert provenance['fixture_bytes']['grizzly-bears-scryfall-raw.json'] == pin
        intake = json.loads((BEARS/'NEIGHBOR_CANONICAL_INTAKE.json').read_bytes())
        receipt = next(row for row in intake if row['name'] == name)
        assert receipt['status'] == 200 and receipt['raw_sha256'] == pin
        card = json.loads(raw)
        assert receipt['oracle_id'] == card['oracle_id']
        assert receipt['url'].startswith('https://api.scryfall.com/cards/named?exact=')
        return card
    raw = (FIXTURES/'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
    pin = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
    assert hashlib.sha256(raw).hexdigest() == pin
    provenance = json.loads((FIXTURES/'knowledge_profiles/PROVENANCE.json').read_bytes())
    assert provenance['snapshot_sha256'] == pin
    assert provenance['raw_objects'] == 155 and provenance['oracle_modified'] is False
    rows = [json.loads(line) for line in raw.splitlines()]
    return next(row for row in rows if row['name'] == name)


@pytest.mark.parametrize('name', ['Lightning Bolt', 'Island', 'Grizzly Bears',
                                 'Delver of Secrets // Insectile Aberration'])
def test_actual_positive_fixture_is_complete_archived_card(name, monkeypatch):
    expected = archived_card(name)
    bolt = original.bolt.__wrapped__()
    if name == 'Lightning Bolt':
        actual = bolt
    else:
        captured = []
        class CapturedBeforePersistence(Exception):
            pass
        def capture(repo, rows, provenance):
            captured.extend(deepcopy(rows))
            raise CapturedBeforePersistence
        monkeypatch.setattr(original, 'import_cards', capture)
        body = (original.test_bulk_retains_face_metadata_and_report_resolves_front_face
                if name.startswith('Delver')
                else original.test_bulk_only_cards_are_visible_to_completeness_and_suggestions)
        with pytest.raises(CapturedBeforePersistence):
            body(None, bolt)
        actual = next(row for row in captured if row['name'] == name)
    assert actual == expected, 'Positive fixture is not the complete pinned official object'
    assert actual['object'] == 'card' and actual['id'] and actual['oracle_id']
    assert actual['rulings_uri'].startswith('https://api.scryfall.com/cards/')
    assert actual['legalities'] == expected['legalities']
