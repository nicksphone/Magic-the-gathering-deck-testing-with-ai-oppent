"""Official seed-corpus rulings through real cache/knowledge persistence."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from knowledge.ingest import KnowledgeIngestor, canonical_hash
from persistence.repository import Repository
from scripts.knowledge_gap_report import knowledge_report
from scripts.sync_corpus_cards import profile_corpus

FIXTURES = Path(__file__).parent / 'fixtures/knowledge_profiles'


@pytest.fixture
def database():
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def corpus():
    raw = (FIXTURES / 'seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
    cards = [json.loads(line) for line in raw.splitlines()]
    bodies = (FIXTURES / 'seed155-rulings.jsonl').read_bytes()
    provenance = json.loads((FIXTURES / 'RULINGS_PROVENANCE.json').read_bytes())
    assert hashlib.sha256(bodies).hexdigest() == provenance['snapshot_sha256']
    pages = [json.loads(line) for line in bodies.splitlines()]
    assert len(cards) == len(pages) == 155
    assert {page['card_id'] for page in pages} == {card['id'] for card in cards}
    return cards, {page['url']: page['payload'] for page in pages}


def test_all_shipped_rulings_ingest_profile_roundtrip_and_cache_idempotently(database, monkeypatch):
    cards, pages = corpus()
    requests = []

    def respond(request):
        url = str(request.url)
        assert url in pages
        requests.append(url)
        return httpx.Response(200, json=pages[url])

    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    with Session(database) as session, httpx.Client(transport=httpx.MockTransport(respond)) as client:
        repo = Repository(session)
        ingestor = KnowledgeIngestor(repo, client)
        for card in cards:
            ingestor.sync_payload(deepcopy(card))
        assert len(requests) == len(repo.list_card_knowledge()) == len(repo.list_cards()) == 155
        names = list(json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_bytes())['cards'])
        report = knowledge_report(repo, names)
        assert report['requested_cards'] == 155
        assert report['missing_cards'] == report['rulings_pending'] == []
        assert report['rules_support_certified'] is False
        assert profile_corpus(repo, names) == {'profiled': 155, 'profiles_updated': 155, 'errors': []}
        before = {row.name: (row.id, row.updated_at, row.profiles_json) for row in repo.list_card_knowledge()}
        for card in cards:
            assert ingestor.sync_name(card['name']) == 'cached'
        assert len(requests) == 155
    with Session(database) as session:
        repo = Repository(session)
        for card in cards:
            row = repo.get_card_knowledge(card['name'])
            profile = json.loads(row.profiles_json)
            rulings = pages[card['rulings_uri']]['data']
            assert profile['card_data'] == card
            assert profile['rulings'] == rulings
            assert profile['rulings_verified'] is True
            assert profile['rulings_provenance']['complete'] is True
            assert profile['rulings_provenance']['uri'] == card['rulings_uri']
            assert profile['rulings_provenance']['sha256'] == canonical_hash(rulings)
            assert profile['card_data_sha256'] == canonical_hash(card)
            assert json.loads(repo.get_cached_card_by_name(card['name']).rulings_json) == rulings
            assert (row.id, row.updated_at, row.profiles_json) == before[row.name]
        assert profile_corpus(repo, names) == {'profiled': 155, 'profiles_updated': 0, 'errors': []}


def test_verified_empty_rulings_are_complete_not_pending(database, monkeypatch):
    cards, pages = corpus()
    card = next(card for card in cards if pages[card['rulings_uri']]['data'] == [])
    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    with Session(database) as session, httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=pages[str(request.url)]))) as client:
        repo = Repository(session)
        ingestor = KnowledgeIngestor(repo, client)
        ingestor.sync_payload(card)
        report = knowledge_report(repo, [card['name']])
        assert report['missing_cards'] == report['rulings_pending'] == []
        assert report['cards'][0]['rulings_count'] == 0
        assert ingestor.cached(card['name']) is not None


@pytest.mark.parametrize('invalid', ['oracle_identity', 'pagination_cycle'])
def test_invalid_rulings_do_not_modify_either_persisted_table(database, monkeypatch, invalid):
    cards, pages = corpus()
    card = next(card for card in cards if pages[card['rulings_uri']]['data'])
    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    bad = deepcopy(pages[card['rulings_uri']])
    if invalid == 'oracle_identity':
        bad['data'][0]['oracle_id'] = 'another-oracle-id'
    else:
        bad['has_more'] = True
        bad['next_page'] = card['rulings_uri']
    with Session(database) as session, httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=bad))) as client:
        repo = Repository(session)
        repo.upsert_card_knowledge({'name': card['name'], 'scryfall_id': card['id'],
                                   'oracle_source': 'scryfall',
                                   'profiles': {'card_data': card, 'retained': ['opaque']}})
        before = repo.get_card_knowledge(card['name']).model_dump()
        with pytest.raises(ValueError):
            KnowledgeIngestor(repo, client).sync_payload(card)
        assert repo.get_card_knowledge(card['name']).model_dump() == before
        assert repo.list_cards() == []
