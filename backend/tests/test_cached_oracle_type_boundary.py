"""Strict cache/transport boundaries using committed public Oracle controls."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from card_data import sync
from card_data.fallback_cards import fallback_card_payload
from card_data.hydration import ready_for_match
from tests.test_oracle_metadata_types import BAD, raw_card


REAL_CLIENT = httpx.Client
SURFACES = ['root', 'front', 'back']


class CacheRows:
    def __init__(self, row):
        self.row = row
        self.writes = []

    def get_cached_card_by_name(self, name):
        assert name == self.row.name
        return self.row

    def upsert_card(self, payload):
        self.writes.append(deepcopy(payload))
        return payload


def cached_row(raw):
    payload = sync.ScryfallSyncService._normalize_payload(raw, '/card-images/cache.svg')
    return SimpleNamespace(id='owned-public-cache', **payload)


def malformed_row(surface, bad):
    raw = raw_card('Deadly Dispute' if surface == 'root' else
                   'Bala Ged Recovery // Bala Ged Sanctuary')
    row = cached_row(raw)
    if surface == 'root':
        row.oracle_text = deepcopy(bad)
    else:
        faces = json.loads(row.card_faces_json)
        faces[0 if surface == 'front' else 1]['oracle_text'] = deepcopy(bad)
        row.card_faces_json = json.dumps(faces)
    return raw, row


def service_with_transport(monkeypatch, tmp_path, row, raw, error=None):
    # Only the external transport is substituted; all cache/domain code is native.
    media = tmp_path / 'media'
    media.mkdir()
    art = (Path(__file__).parents[1] / 'card_data/assets/generic-token-creature.svg').read_bytes()
    (media / 'cache.svg').write_bytes(art)
    monkeypatch.setattr(sync, 'CACHE_DIR', media)
    calls = []

    def transport(request):
        calls.append(str(request.url))
        if request.url.path == '/cards/named':
            if error is not None:
                raise error
            return httpx.Response(200, json=raw)
        if request.url.path.endswith('/rulings'):
            return httpx.Response(200, json={'data': []})
        assert request.url.host == 'cards.scryfall.io'
        return httpx.Response(200, content=art, headers={'content-type': 'image/svg+xml'})

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(transport), trust_env=False, **kwargs)

    monkeypatch.setattr(sync.httpx, 'Client', client)
    repo = CacheRows(row)
    return sync.ScryfallSyncService(repo), repo, calls


@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('bad', BAD)
def test_direct_cache_serialization_rejects_original_malformed_fields(monkeypatch, tmp_path, surface, bad):
    raw, row = malformed_row(surface, bad)
    service, repo, calls = service_with_transport(monkeypatch, tmp_path, row, raw)
    before = deepcopy(vars(row))
    with pytest.raises(ValueError, match='Oracle'):
        service._serialize_card(row)
    assert vars(row) == before and not repo.writes and not calls


@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('bad', BAD)
def test_malformed_cache_cannot_short_circuit_native_online_repair(monkeypatch, tmp_path, surface, bad):
    raw, row = malformed_row(surface, bad)
    service, repo, calls = service_with_transport(monkeypatch, tmp_path, row, raw)
    before = deepcopy(vars(row))
    result = service.sync_card_by_name(raw['name'])
    assert calls and calls[0].startswith(sync.SCRYFALL_NAMED_URL)
    assert len(repo.writes) == 1
    assert ready_for_match(result) is True
    canonical = sync.ScryfallSyncService._normalize_payload(raw, result['image_uri'])
    assert result['oracle_text'] == canonical['oracle_text']
    assert result['card_faces'] == json.loads(canonical['card_faces_json'])
    assert vars(row) == before


@pytest.mark.parametrize('force', [False, True])
@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('bad', BAD)
def test_transport_failure_never_falls_back_to_malformed_cache(monkeypatch, tmp_path, force, surface, bad):
    raw, row = malformed_row(surface, bad)
    error = httpx.ConnectError('Declared offline transport', request=httpx.Request('GET', sync.SCRYFALL_NAMED_URL))
    service, repo, calls = service_with_transport(monkeypatch, tmp_path, row, raw, error)
    before = deepcopy(vars(row))
    with pytest.raises(httpx.ConnectError) as caught:
        service.sync_card_by_name(raw['name'], force=force)
    assert caught.value is error
    assert len(calls) == 1 and not repo.writes and vars(row) == before


@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('bad', BAD)
def test_malformed_raw_repair_response_is_not_swallowed_or_written(monkeypatch, tmp_path, surface, bad):
    raw, row = malformed_row(surface, bad)
    malformed = deepcopy(raw)
    if surface == 'root':
        malformed['oracle_text'] = deepcopy(bad)
    else:
        malformed['card_faces'][0 if surface == 'front' else 1]['oracle_text'] = deepcopy(bad)
    service, repo, calls = service_with_transport(monkeypatch, tmp_path, row, malformed)
    with pytest.raises(ValueError, match='Oracle'):
        service.sync_card_by_name(raw['name'], force=True)
    assert calls and not repo.writes


@pytest.mark.parametrize('name', ['Deadly Dispute', 'Grizzly Bears', 'Bala Ged Recovery // Bala Ged Sanctuary'])
@pytest.mark.parametrize('oracle', ['canonical', 'absent', 'none', 'empty'])
@pytest.mark.parametrize('offline', [False, True])
def test_valid_legacy_cache_fallback_and_multiface_codec_are_preserved(monkeypatch, tmp_path, name, oracle, offline):
    raw = raw_card(name)
    row = cached_row(raw)
    if oracle == 'absent':
        del row.oracle_text
    elif oracle != 'canonical':
        row.oracle_text = None if oracle == 'none' else ''
    error = httpx.ConnectError('Declared offline transport', request=httpx.Request('GET', sync.SCRYFALL_NAMED_URL))
    service, repo, calls = service_with_transport(monkeypatch, tmp_path, row, raw, error)
    expected = service._serialize_card(row)
    before = deepcopy(vars(row))
    # For legacy incomplete multiface roots the native readiness check requests
    # repair; declared offline transport must still preserve that valid cache.
    result = service.sync_card_by_name(name, force=offline)
    assert result == expected
    assert result['oracle_text'] == (getattr(row, 'oracle_text', None) or
                                    (fallback_card_payload(name) or {}).get('oracle_text', ''))
    assert result['card_faces'] == json.loads(row.card_faces_json)
    assert (bool(calls)) is (offline or not ready_for_match(expected))
    assert vars(row) == before and not repo.writes
