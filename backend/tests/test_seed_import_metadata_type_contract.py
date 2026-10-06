"""Actual response fields, not UUID-based execution certification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest
from card_data.fallback_cards import FALLBACK_CARD_DATA
from card_data.hydration import ready_for_match
from card_data.sync import ScryfallSyncService
from decks.service import DeckService
from decks.builtin_decks import BUILTIN_DECKS
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client, FAMILIES


def contract(meta):
    assert isinstance(meta['scryfall_id'], str) and meta['scryfall_id']
    assert str(UUID(meta['scryfall_id'])) == meta['scryfall_id']
    assert isinstance(meta['name'], str)
    for key in ('oracle_text', 'mana_cost', 'type_line'):
        if key in meta:
            assert isinstance(meta[key], str), (meta['name'], key, meta[key])
    if 'colors' in meta:
        assert isinstance(meta['colors'], list) and all(isinstance(c, str) for c in meta['colors'])
    for key in ('power', 'toughness'):
        if key in meta:
            assert meta[key] is None or isinstance(meta[key], (str, int, float))
    if 'image_uri' in meta:
        assert meta['image_uri'] is None or isinstance(meta['image_uri'], str)
    if 'legalities' in meta:
        assert isinstance(meta['legalities'], dict) and all(isinstance(v, str) for v in meta['legalities'].values())
    for face in meta.get('card_faces', []):
        assert isinstance(face, dict)
        for key in ('name', 'mana_cost', 'oracle_text', 'type_line'):
            if key in face:
                assert isinstance(face[key], str), (meta['name'], face.get('name'), key, face[key])
        if 'image_uri' in face:
            assert face['image_uri'] is None or isinstance(face['image_uri'], str)
    return meta


@pytest.fixture(autouse=True)
def no_remote(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('No resolver sync or transport allowed')
    for name in ('sync_card_by_name', 'sync_card_from_local_knowledge'):
        monkeypatch.setattr(ScryfallSyncService, name, forbidden)
    monkeypatch.setattr('card_data.sync.get_with_backoff', forbidden)


def test_every_ready_seed_actual_projection_preserves_pinned_id_and_faces(repo):
    assert len(FALLBACK_CARD_DATA) == 155
    original = deepcopy(FALLBACK_CARD_DATA)
    before = '\n'.join(repo.session.connection().connection.driver_connection.iterdump())
    board = [{'quantity': 1, 'card_name': name} for name in sorted(FALLBACK_CARD_DATA)]
    resolved = DeckService(repo)._resolve_card_metadata(board)
    for item in resolved:
        seed = FALLBACK_CARD_DATA[item['card_name']]
        meta = contract(item['card_metadata'])
        assert meta['match_ready'] and ready_for_match(meta) and 'id' not in meta
        assert meta['scryfall_id'] == seed['scryfall_id']
        assert meta['card_data_sources'] == ['offline_seed']
        assert meta.get('card_faces') == seed.get('card_faces')
        for key in ('type_line', 'colors', 'layout'):
            assert meta.get(key) == seed.get(key)
    assert FALLBACK_CARD_DATA == original
    assert '\n'.join(repo.session.connection().connection.driver_connection.iterdump()) == before


@pytest.mark.parametrize('name,style', FAMILIES)
def test_actual_http_family_metadata_matches_complete_type_contract(repo, client, name, style):
    response = client.post('/decks/import', json={'name': name, 'source': 'user:contract', 'deck_text': BUILTIN_DECKS[name]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['archetype_guess'] == style and not result['errors']
    for item in result['resolved_mainboard_cards'] + result['resolved_sideboard_cards']:
        meta = contract(item['card_metadata'])
        assert meta['match_ready'] and 'id' not in meta
        assert meta['scryfall_id'] == FALLBACK_CARD_DATA[item['card_name']]['scryfall_id']
    assert repo.list_cards() == []


def test_actual_http_all_seed_faces_and_colors(repo, client):
    text = '\n'.join('1 ' + name for name in sorted(FALLBACK_CARD_DATA))
    response = client.post('/decks/import', json={'name': 'Pinned seed response census', 'source': 'user:contract', 'deck_text': text})
    assert response.status_code == 200, response.text
    result = response.json()
    assert not result['errors']
    assert len(result['resolved_mainboard_cards']) == 155
    for item in result['resolved_mainboard_cards']:
        contract(item['card_metadata'])
    assert repo.list_cards() == []


def test_verified_full_knowledge_faces_and_id_contract(repo, client):
    path = Path(__file__).parent / 'fixtures/queued_sequence/canonical.json'
    pin = json.loads(path.with_name('provenance.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['canonical_sha256']
    raw = json.loads(path.read_text())['Brutal Cathar // Moonrage Brute']
    repo.upsert_card_knowledge({'name': raw['name'], 'scryfall_id': raw['id'], 'oracle_source': 'scryfall',
        'profiles': {'schema_version': 1, 'card_data': raw, 'rulings_verified': False, 'rulings': []}})
    response = client.post('/decks/import', json={'name': 'Canonical face response', 'source': 'user:contract', 'deck_text': '4 ' + raw['name'] + '\n56 Island'})
    assert response.status_code == 200, response.text
    meta = contract(response.json()['resolved_mainboard_cards'][0]['card_metadata'])
    assert meta['scryfall_id'] == raw['id'] and 'id' not in meta and meta['match_ready']
    assert 'local_knowledge' in meta['card_data_sources'] and len(meta['card_faces']) == 2
    assert [f['colors'] for f in meta['card_faces']] == [f['colors'] for f in raw['card_faces']]
    assert all(isinstance(f['type_line'], str) and isinstance(f['mana_cost'], str) for f in meta['card_faces'])
    assert repo.list_cards() == []
