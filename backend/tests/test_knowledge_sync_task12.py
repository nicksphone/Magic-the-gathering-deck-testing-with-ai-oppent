"""Task1.2 request/clock controls plus genuine stored-fixture roundtrips.

All HTTP uses MockTransport. Clock payloads and deliberately malformed surface
variants are protocol fixtures, not newly sourced card facts. Tests requesting
repo use the unchanged memory/owned-file SQLite fixture; this module is not an
entirely SQL-free cohort.
"""
from copy import deepcopy
import json

import httpx
import pytest

from knowledge.ingest import API, KnowledgeIngestor
from tests.test_knowledge_cache_recovery import official, repo, saved, stored


@pytest.mark.parametrize('force', [False, True])
def test_named_request_is_fuzzy_only_with_exact_original_input(official, monkeypatch, force):
    cards, _ = official
    raw = next(card for card in cards if card['name'] == 'Lightning Bolt')
    requested, urls, payloads = '  LIGHTNING BOLT  ', [], []

    def handle(request):
        urls.append(request)
        return httpx.Response(200, json=deepcopy(raw))

    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        ingestor = KnowledgeIngestor(None, client)
        monkeypatch.setattr(ingestor, 'cached', lambda name: None)
        monkeypatch.setattr(ingestor, 'sync_payload', lambda value: payloads.append(deepcopy(value)))
        assert ingestor.sync_name(requested, force=force) == 'synced'
    assert len(urls) == 1
    assert urls[0].url.path == '/cards/named'
    assert dict(urls[0].url.params) == {'fuzzy': requested}
    assert payloads == [raw]


@pytest.mark.parametrize('requested', ['Definitely Unknown Corpus Card', 'Lightning Blt', 'Lightning'])
@pytest.mark.parametrize('force', [False, True])
def test_fuzzy_response_cannot_satisfy_a_different_requested_name(official, monkeypatch, requested, force):
    cards, _ = official
    raw = next(card for card in cards if card['name'] == 'Lightning Bolt')
    payloads, requests = [], []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=deepcopy(raw))

    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        ingestor = KnowledgeIngestor(None, client)
        monkeypatch.setattr(ingestor, 'cached', lambda name: None)
        monkeypatch.setattr(ingestor, 'sync_payload', lambda value: payloads.append(value))
        with pytest.raises(ValueError):
            ingestor.sync_name(requested, force=force)
    assert payloads == []  # Rejected before rulings fetch or any payload write.
    assert len(requests) == 1


@pytest.mark.parametrize('invalid_surface', ['art_series', 'Card', 'missing_face'])
def test_only_real_face_aliases_bind_a_fuzzy_response(official, monkeypatch, invalid_surface):
    cards, _ = official
    raw = deepcopy(next(card for card in cards if card['name'].startswith('Delver of Secrets //')))
    requested = raw['card_faces'][1]['name']
    if invalid_surface == 'art_series':
        raw['layout'] = 'art_series'
    elif invalid_surface == 'Card':
        raw['type_line'] = 'Card'
    else:
        raw['card_faces'] = []
    payloads = []
    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=raw))) as client:
        ingestor = KnowledgeIngestor(None, client)
        monkeypatch.setattr(ingestor, 'cached', lambda name: None)
        monkeypatch.setattr(ingestor, 'sync_payload', lambda value: payloads.append(value))
        with pytest.raises(ValueError):
            ingestor.sync_name(requested)
    assert payloads == []


@pytest.mark.parametrize('path,interval,floor', [
    ('/cards/named', 0.12, 0.5), ('/cards/search', 0.12, 0.5),
    ('/cards/protocol/rulings', 0.12, 0.25), ('/cards/protocol/rulings', 0.0, 0.25),
    ('/cards/protocol/rulings', 0.35, 0.35), ('/cards/named', 0.75, 0.75),
    ('/cards/search', 0.75, 0.75), ('/bulk-data', 0.12, 0.25),
])
def test_endpoint_floor_is_completion_to_next_request(monkeypatch, path, interval, floor):
    clock, sleeps, started = [100.0], [], []

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    def handle(request):
        started.append(clock[0])
        clock[0] += 0.04
        return httpx.Response(200, json={'protocol_clock_only': True})

    monkeypatch.setattr('knowledge.ingest.time.monotonic', lambda: clock[0])
    monkeypatch.setattr('knowledge.ingest.time.sleep', sleep)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        ingestor = KnowledgeIngestor(None, client, interval=interval)
        ingestor._last_request = clock[0]
        for _ in range(2):
            assert ingestor._get(API + path) == {'protocol_clock_only': True}
    assert sleeps == pytest.approx([floor, floor])
    assert started == pytest.approx([100.0 + floor, 100.04 + 2 * floor])


def test_failed_request_keeps_the_all_endpoint_spacing_floor(monkeypatch):
    clock, sleeps, started = [100.0], [], []

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    def handle(request):
        started.append(clock[0])
        clock[0] += 0.04
        return httpx.Response(503 if len(started) == 1 else 200, json={})

    monkeypatch.setattr('knowledge.ingest.time.monotonic', lambda: clock[0])
    monkeypatch.setattr('knowledge.ingest.time.sleep', sleep)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        ingestor = KnowledgeIngestor(None, client)
        ingestor._last_request = clock[0]
        with pytest.raises(httpx.HTTPStatusError):
            ingestor._get(API + '/cards/protocol/rulings')
        assert ingestor._get(API + '/cards/protocol/rulings') == {}
    assert sleeps == pytest.approx([0.25, 0.25])
    assert started == pytest.approx([100.25, 100.54])


def test_longer_429_retry_after_remains_unchanged(monkeypatch):
    sleeps = []
    monkeypatch.setattr('knowledge.ingest.time.monotonic', lambda: 100.0)
    monkeypatch.setattr('knowledge.ingest.time.sleep', sleeps.append)
    replies = iter([httpx.Response(429, headers={'Retry-After': '45'}), httpx.Response(200, json={})])
    with httpx.Client(transport=httpx.MockTransport(lambda request: next(replies))) as client:
        ingestor = KnowledgeIngestor(None, client)
        ingestor._last_request = 100.0
        assert ingestor._get(API + '/cards/named') == {}
    assert sleeps == [0.5, 45.0]


@pytest.mark.parametrize('surface', ['canonical', 'front', 'back'])
def test_official_cold_face_and_canonical_sync_repeat_without_requests(official, repo, surface):
    cards, rulings = official
    raw = next(card for card in cards if card['name'].startswith('Delver of Secrets //'))
    requested = raw['name'] if surface == 'canonical' else raw['card_faces'][0 if surface == 'front' else 1]['name']
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.path == '/cards/named':
            assert dict(request.url.params) == {'fuzzy': requested}
            return httpx.Response(200, json=deepcopy(raw))
        assert str(request.url) == raw['rulings_uri']
        return httpx.Response(200, json={'object': 'list', 'data': rulings[raw['id']], 'has_more': False})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        ingestor = KnowledgeIngestor(repo, client)
        assert ingestor.sync_name(requested) == 'synced'
        assert len(requests) == 2
        before = saved(repo)
        for alias in [raw['name'], *(face['name'] for face in raw['card_faces'])]:
            assert ingestor.sync_name(alias) == 'cached'
        assert saved(repo) == before
        assert len(requests) == 2


def test_forced_official_refresh_preserves_learned_fields_and_future_namespace(official, repo):
    cards, rulings = official
    raw = next(card for card in cards if card['name'] == 'Lightning Bolt')
    row = stored(repo, raw, rulings[raw['id']])
    before = row.model_dump()
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == '/cards/named':
            assert dict(request.url.params) == {'fuzzy': raw['name']}
            return httpx.Response(200, json=deepcopy(raw))
        assert str(request.url) == raw['rulings_uri']
        return httpx.Response(200, json={'object': 'list', 'data': rulings[raw['id']], 'has_more': False})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        ingestor = KnowledgeIngestor(repo, client)
        assert ingestor.sync_name(raw['name'], force=True) == 'synced'
        assert ingestor.sync_name(raw['name']) == 'cached'
    after = repo.get_card_knowledge(raw['name']).model_dump()
    assert len(calls) == 2
    assert {key: value for key, value in after.items() if key not in {'profiles_json', 'updated_at'}} == {
        key: value for key, value in before.items() if key not in {'profiles_json', 'updated_at'}}
    assert json.loads(after['profiles_json'])['future_namespace'] == json.loads(before['profiles_json'])['future_namespace']
    assert json.loads(after['profiles_json'])['card_data'] == raw


@pytest.mark.parametrize('status', [404, 503])
def test_failed_forced_lookup_cannot_repair_or_mutate_existing_rows(official, repo, status):
    cards, rulings = official
    raw = next(card for card in cards if card['name'] == 'Lightning Bolt')
    stored(repo, raw, rulings[raw['id']])
    before = saved(repo)
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(status)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            KnowledgeIngestor(repo, client).sync_name(raw['name'], force=True)
    assert len(requests) == 1
    assert saved(repo) == before
