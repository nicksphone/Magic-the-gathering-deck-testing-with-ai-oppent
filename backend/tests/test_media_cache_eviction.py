"""Offline presentation repair, never canonical-art fabrication or state repair."""
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest
from sqlmodel import Session

from card_data import token_images
from card_data.display import select_display_image_uri
from card_data.placeholders import CACHE_DIR, ensure_placeholder_image
from card_data.sync import ScryfallSyncService
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, snapshot
from tests.test_canonical_token_descriptors import RAW
from tests.test_selected_mana_http import restart


@pytest.mark.parametrize('seat', [1, 2])
def test_memoized_token_eviction_http_root_and_restore(game, seat):
    client, controller = game
    controller.state.priority_player = seat
    uri = token_images.resolve_token_image_uri('Phyrexian Golem', 3, 3)
    target = CACHE_DIR / Path(uri).name
    shipped = Path(__file__).parents[1] / 'card_data/assets/generic-token-creature.svg'
    assert target.read_bytes() == shipped.read_bytes()
    before = snapshot(controller)
    target.unlink()
    assert client.get(uri).status_code == 404
    assert token_images.resolve_token_image_uri('Phyrexian Golem', 3, 3) == uri
    assert client.get(uri).content == shipped.read_bytes()
    assert client.get(uri).status_code == 200
    assert snapshot(controller) == before
    # Persisted state predates this presentation-only priority adjustment.
    controller.state.priority_player = 1
    from tests.test_api_input_contracts import persist
    persist(controller)
    before = snapshot(controller)
    restored = restart(controller.state.id)
    assert snapshot(restored) == before
    assert client.get(uri).status_code == 200


@pytest.mark.parametrize('kind', ['placeholder', 'unavailable_canonical'])
def test_per_card_eviction_http_preserves_cached_facts_and_game(game, kind):
    client, controller = game
    raw = deepcopy(RAW['Blade Splicer'])
    if kind == 'placeholder':
        uri = ensure_placeholder_image(raw['name'], raw['type_line'])
        (CACHE_DIR / Path(uri).name).unlink()
    else:
        uri = '/card-images/' + raw['id'] + '-evicted.jpg'
        assert not (CACHE_DIR / Path(uri).name).exists()
    with Session(engine) as session:
        row = Repository(session).upsert_card(ScryfallSyncService._normalize_payload(raw, uri))
        identity = row.id
    before = snapshot(controller)
    assert client.get(uri).status_code == 404
    response = client.get('/cards')
    assert response.status_code == 200
    card = next(card for card in response.json() if card['id'] == identity)
    fallback = card['image_uri']
    assert '/placeholder-' in fallback
    image = client.get(fallback)
    assert image.status_code == 200
    assert b'Local placeholder art' in image.content
    assert card['oracle_text'] == raw['oracle_text']
    assert snapshot(controller) == before
    assert snapshot(restart(controller.state.id)) == before
    assert client.get('/cards').json() == response.json()
    assert client.get(fallback).content == image.content
    if kind == 'unavailable_canonical':
        assert client.get(uri).status_code == 404
        assert not (CACHE_DIR / Path(uri).name).exists()


def test_stale_indexed_token_does_not_recreate_canonical_art(monkeypatch, tmp_path):
    monkeypatch.setattr(token_images, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(token_images, '_INDEX_FILE', tmp_path / 'token-index.json')
    key = ('phyrexian golem', 3, 3)
    index = tmp_path / 'token-index.json'
    index.write_text(json.dumps({token_images._index_key(key): 'token-evicted.jpg'}))
    before = index.read_bytes()
    monkeypatch.setitem(token_images._TOKEN_IMAGE_CACHE, key, '/card-images/token-evicted.jpg')
    def forbidden(*args, **kwargs):
        raise AssertionError('Gameplay resolver must not search Scryfall')
    monkeypatch.setattr(token_images, '_search_scryfall_token_image', forbidden)
    assert token_images.resolve_token_image_uri('Phyrexian Golem', 3, 3) == '/card-images/generic-token-creature.svg'
    assert not (tmp_path / 'token-evicted.jpg').exists()
    assert index.read_bytes() == before


def test_face_uri_selection_and_input_immutability():
    raw = deepcopy(RAW['Blade Splicer'])
    raw['image_uri'] = '/card-images/absent-root.jpg'
    # Transport metadata only: no new face Oracle or invented card identity.
    raw['card_faces'] = [{'image_uri': '/card-images/absent-face.jpg'},
                         {'image_uri': 'https://cards.scryfall.io/example-unfetched.jpg'}]
    before = deepcopy(raw)
    assert select_display_image_uri(raw, name=raw['name'], type_line=raw['type_line']) == raw['card_faces'][1]['image_uri']
    assert raw == before


def test_local_availability_rejects_missing_nested_and_accepts_query():
    from card_data.placeholders import local_image_available
    uri = ensure_placeholder_image(RAW['Blade Splicer']['name'], RAW['Blade Splicer']['type_line'])
    assert local_image_available(uri + '?v=1#art')
    assert not local_image_available('/card-images/../assets/generic-token-creature.svg')
    assert not local_image_available('/card-images/absent.jpg')


def test_uncached_explicit_sync_failure_stays_visible(monkeypatch):
    class EmptyRepository:
        def get_cached_card_by_name(self, name):
            return None
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr('card_data.sync.get_with_backoff', unavailable)
    with pytest.raises(httpx.ConnectError, match='offline'):
        ScryfallSyncService(EmptyRepository()).sync_card_by_name(RAW['Blade Splicer']['name'])
