"""Observe real legacy builders before DeckService consumes their cache rows."""
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from card_data.sync import ScryfallSyncService
from decks.service import DeckService
from tests import canonical_positive_fixtures as shared
from tests import deck_service_metadata_fixtures as canonical
from tests import test_deck_service_metadata as legacy


NAMES = ('Fire // Ice', 'Secure the Wastes', 'Memnite',
         'Kazandu Mammoth // Kazandu Valley', 'Mountain', 'Island', 'Dryad Arbor')
CASES = [('display', name) for name in ('Fire // Ice', 'Island')] + [
    ('curve', name) for name in NAMES]


def archived(name):
    if name in canonical.SOURCES:
        filename, digest = canonical.SOURCES[name]
        data = (canonical.ROOT / filename).read_bytes()
        rows = [json.loads(data)]
    else:
        source = shared.SOURCES.get(name, shared.SEED)
        digest = shared.PINS[source]
        data = (shared.FIXTURES / source).read_bytes()
        rows = (list(map(json.loads, data.splitlines())) if source.endswith('.jsonl')
                else [json.loads(data)])
    assert hashlib.sha256(data).hexdigest() == digest
    matches = [row for row in rows if row.get('name') == name]
    assert len(matches) == 1 and matches[0]['object'] == 'card'
    return matches[0]


def capture_builder(case, monkeypatch):
    captured = []

    class BeforeService(Exception):
        pass

    def capture(service, *args, **kwargs):
        captured.append({name: dict(vars(row)) for name, row in service.repo._cards.items()})
        raise BeforeService

    monkeypatch.setattr(DeckService, 'import_deck_text', capture)
    with pytest.raises(BeforeService):
        if case == 'display':
            legacy.test_import_deck_text_exposes_resolved_card_metadata(monkeypatch)
        else:
            legacy.test_import_curve_and_colors_use_cached_oracle_metadata()
    assert len(captured) == 1
    return captured[0]


@pytest.mark.parametrize('case,name', CASES, ids=[case + ':' + name for case, name in CASES])
def test_actual_service_input_is_the_complete_official_cache_projection(case, name, monkeypatch):
    actual = capture_builder(case, monkeypatch)[name.lower()]
    raw = archived(name)
    image = ({'Fire // Ice': '/card-images/fire-ice.png',
              'Island': '/card-images/island.png'}[name] if case == 'display' else None)
    expected = ScryfallSyncService._normalize_payload(raw, image or '/card-images/metadata-display.svg')
    expected['image_uri'] = image
    # The in-memory repository uses the actual public identity, not a fabricated card ID.
    expected['id'] = raw['id']
    assert actual == expected, 'Actual positive cache row has handwritten or incomplete card facts'


def test_actual_service_preserves_both_complete_split_faces(monkeypatch):
    monkeypatch.setattr('card_data.display.local_image_available', lambda uri: True)
    result = DeckService(legacy._FakeRepo()).import_deck_text('Split fidelity', '4 Fire // Ice\n56 Island')
    actual = result['resolved_mainboard_cards'][0]['card_metadata']
    raw = archived('Fire // Ice')
    assert [face['name'] for face in raw['card_faces']] == ['Fire', 'Ice']
    assert actual['card_faces'] == ScryfallSyncService._normalize_faces(raw['card_faces'])
    assert len(actual['card_faces']) == 2 and actual['scryfall_id'] == raw['id']
    assert actual['legalities'] == raw['legalities']


def test_complete_raw_loader_returns_fresh_objects_without_mutating_sources():
    for name in NAMES:
        first = canonical.raw_card(name)
        second = canonical.raw_card(name)
        assert first == second == archived(name)
        assert first is not second
        first['legalities'].clear()
        first.get('card_faces', []).clear()
        first['name'] = 'mutation witness'
        assert second == canonical.raw_card(name) == archived(name)
        row = legacy._FakeCard(name)
        row.legalities_json = '{}'
        row.card_faces_json = '[]'
        fresh = legacy._FakeCard(name)
        assert json.loads(fresh.legalities_json) == archived(name)['legalities']
        assert json.loads(fresh.card_faces_json) == ScryfallSyncService._normalize_faces(
            archived(name).get('card_faces', []))


def test_intake_and_inherited_provenance_bind_full_official_bytes():
    data = (canonical.ROOT / 'PROVENANCE.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == 'c3de07a1fcfd21241bfc488edcb1e0df138f876d1016f3706737e3f6044c5d1d'
    receipt = json.loads(data)
    assert receipt['complete'] is True and receipt['oracle_modified'] is False
    assert receipt['request_budget'] == len(receipt['records']) == 2
    assert receipt['art_or_rulings_requests'] == 0
    for index, record in enumerate(receipt['records']):
        body = (canonical.ROOT / record['file']).read_bytes()
        raw = json.loads(body)
        assert record['status'] == 200 and record['response_url'] == record['url']
        assert urlsplit(record['url']).netloc == 'api.scryfall.com'
        assert parse_qs(urlsplit(record['url']).query) == {'exact': [record['requested_name']]}
        assert hashlib.sha256(body).hexdigest() == record['raw_sha256']
        assert len(body) == record['bytes'] and raw == archived(record['requested_name'])
        assert raw['name'] == record['requested_name'] and raw['id'] == record['scryfall_id']
        assert raw['oracle_id'] == record['oracle_id']
        assert record['started_utc'] and record['finished_utc'] and record['headers']
        if index:
            assert record['start_spacing_seconds'] >= .5
    seed = json.loads((shared.FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes())
    assert seed['snapshot_sha256'] == shared.PINS[shared.SEED] and seed['oracle_modified'] is False
    prior = json.loads((shared.FIXTURES / 'canonical_positive_batch/PROVENANCE.json').read_bytes())
    fire = next(record for record in prior['records'] if record['requested_name'] == 'Fire // Ice')
    assert fire['status'] == 200 and fire['raw_sha256'] == shared.PINS[shared.SOURCES['Fire // Ice']]
    assert archived('Kazandu Mammoth // Kazandu Valley')['card_faces'][1]['name'] == 'Kazandu Valley'
