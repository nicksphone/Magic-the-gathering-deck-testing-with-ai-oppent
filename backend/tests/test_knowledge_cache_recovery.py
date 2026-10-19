"""Offline cache recovery with real repositories and existing complete official RAW."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from card_data import placeholders, sync
from card_data.tactical import canonical_tactical_tags
from knowledge.ingest import KnowledgeIngestor, SCHEMA_VERSION, canonical_hash
from knowledge.models import CardKnowledge
from persistence.models import CardCache
from persistence.repository import Repository


FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='module')
def official():
    directory = FIXTURES / 'knowledge_profiles'
    raw = (directory / 'seed155-scryfall.jsonl').read_bytes()
    pages = (directory / 'seed155-rulings.jsonl').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
    assert hashlib.sha256(pages).hexdigest() == 'f54b2bae40fffe3e1714877851bf65cbb854b551951d09cc20f7cadfb70994f9'
    cards = [json.loads(line) for line in raw.splitlines()]
    rulings = {page['card_id']: page['payload']['data']
               for page in map(json.loads, pages.splitlines())}
    assert len(cards) == len(rulings) == 155
    return cards, rulings


@pytest.fixture(params=['memory', 'file'])
def repo(request, tmp_path, monkeypatch):
    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    media = tmp_path / 'media'
    media.mkdir()
    monkeypatch.setattr(sync, 'CACHE_DIR', media)
    monkeypatch.setattr(placeholders, 'CACHE_DIR', media)
    url = 'sqlite:///:memory:' if request.param == 'memory' else 'sqlite:///' + str(tmp_path / 'owned.sqlite')
    engine = create_engine(url, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine, tables=[CardKnowledge.__table__, CardCache.__table__])
    try:
        with Session(engine) as session:
            yield Repository(session)
    finally:
        engine.dispose()


def stored(repo, raw, rulings, *, verified=True):
    profile = {
        'schema_version': SCHEMA_VERSION,
        'oracle_id': raw['oracle_id'],
        'card_data': deepcopy(raw),
        'card_data_sha256': canonical_hash(raw),
        'rulings_verified': verified,
        'rulings': deepcopy(rulings),
        'future_namespace': {'opaque': ['retain', 17]},
        **canonical_tactical_tags(raw),
    }
    return repo.upsert_card_knowledge({
        'name': raw['name'], 'scryfall_id': raw['id'], 'oracle_source': 'scryfall',
        'play_value': 7.25, 'threat_level': 2, 'etb_impact': 1.5,
        'answerable_by': ['counter'], 'cast_windows': ['instant_window'],
        'profiles': profile,
    })


def saved(repo):
    return ([row.model_dump() for row in repo.list_card_knowledge()],
            [row.model_dump() for row in repo.list_cards()])


def offline(request):
    pytest.fail('Offline cache recovery attempted HTTP: ' + str(request.url))


@pytest.mark.parametrize('entry', ['cached', 'sync_name'])
@pytest.mark.parametrize('selection', ['Lightning Bolt', 'empty', 'front', 'back'])
def test_missing_cache_recovers_offline_without_changing_knowledge(repo, official, entry, selection):
    cards, rulings = official
    if selection in {'front', 'back'}:
        raw = next(card for card in cards if card['name'].startswith('Delver of Secrets //'))
        name = raw['card_faces'][selection == 'back']['name']
    elif selection == 'empty':
        raw = next(card for card in cards if rulings[card['id']] == [])
        name = raw['name']
    else:
        raw = next(card for card in cards if card['name'] == selection)
        name = raw['name']
    row = stored(repo, raw, rulings[raw['id']])
    before = row.model_dump()
    assert repo.list_cards() == []
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        ingestor = KnowledgeIngestor(repo, client)
        result = getattr(ingestor, entry)(name)
        assert result == 'cached' if entry == 'sync_name' else result.id == row.id
        cache = repo.get_cached_card_by_name(name)
        assert cache is not None, 'Verified knowledge left its CardCache row missing'
        expected = sync.ScryfallSyncService._normalize_payload(
            raw, sync.ScryfallSyncService._extract_remote_image_uri(raw), rulings[raw['id']])
        assert {key: getattr(cache, key) for key in expected} == expected
        assert repo.get_card_knowledge(raw['name']).model_dump() == before
        stable = saved(repo)
        getattr(ingestor, entry)(name)
        assert saved(repo) == stable
    with Session(repo.session.bind) as session:
        reopened = Repository(session)
        assert reopened.get_card_knowledge(raw['name']).model_dump() == before
        assert reopened.get_cached_card_by_name(name).model_dump() == cache.model_dump()


def test_search_cached_branch_repairs_without_card_or_rulings_requests(repo, official):
    cards, rulings = official
    raw = next(card for card in cards if card['name'] == 'Farewell')
    stored(repo, raw, rulings[raw['id']])
    before = saved(repo)[0]
    requests = []

    def search(request):
        assert request.url.path == '/cards/search'
        requests.append(str(request.url))
        return httpx.Response(200, json={'object': 'list', 'data': [raw], 'has_more': False})

    with httpx.Client(transport=httpx.MockTransport(search)) as client:
        ingestor = KnowledgeIngestor(repo, client)
        assert ingestor.sync_search('exact fixture', 1) == {'synced': 0, 'cached': 1, 'errors': []}
        assert len(requests) == 1
        assert repo.get_cached_card_by_name(raw['name']) is not None
        assert saved(repo)[0] == before
        stable = saved(repo)
        assert ingestor.sync_search('exact fixture', 1) == {'synced': 0, 'cached': 1, 'errors': []}
        assert len(requests) == 2
        assert saved(repo) == stable


@pytest.mark.parametrize('invalid', [
    'manual', 'schema', 'unverified', 'truthy_verified', 'missing_raw', 'raw_list',
    'identity', 'name', 'hash', 'oracle_identity', 'oracle_text', 'faces', 'rulings',
    'ruling_identity', 'profile_list', 'profile_json',
])
def test_untrusted_or_incomplete_recovery_is_a_cache_miss_without_writes(repo, official, invalid):
    cards, rulings = official
    raw = next(card for card in cards if rulings[card['id']])
    row = stored(repo, raw, rulings[raw['id']])
    profile = json.loads(row.profiles_json)
    if invalid == 'manual':
        row.oracle_source = 'manual'
    elif invalid == 'schema':
        profile['schema_version'] = -1
    elif invalid == 'unverified':
        profile['rulings_verified'] = False
    elif invalid == 'truthy_verified':
        profile['rulings_verified'] = 'false'
    elif invalid == 'missing_raw':
        profile.pop('card_data')
    elif invalid == 'raw_list':
        profile['card_data'] = []
    elif invalid == 'identity':
        row.scryfall_id = 'not-the-stored-printing'
    elif invalid == 'name':
        profile['card_data']['name'] = 'Not the stored canonical name'
    elif invalid == 'hash':
        profile['card_data_sha256'] = '0' * 64
    elif invalid == 'oracle_identity':
        profile['oracle_id'] = 'not-the-stored-oracle'
    elif invalid == 'oracle_text':
        profile['card_data']['oracle_text'] = 17
        profile['card_data_sha256'] = canonical_hash(profile['card_data'])
    elif invalid == 'faces':
        profile['card_data']['card_faces'] = ['malformed']
        profile['card_data_sha256'] = canonical_hash(profile['card_data'])
    elif invalid == 'rulings':
        profile['rulings'] = {'not': 'a list'}
    elif invalid == 'ruling_identity':
        profile['rulings'][0]['oracle_id'] = 'not-the-stored-oracle'
    row.profiles_json = ('{' if invalid == 'profile_json' else
                         '[]' if invalid == 'profile_list' else json.dumps(profile))
    repo.session.add(row)
    repo.session.commit()
    before = saved(repo)
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        assert KnowledgeIngestor(repo, client).cached(raw['name']) is None
    assert saved(repo) == before


@pytest.mark.parametrize('name', ['Bala Ged Recovery', 'Bala Ged Sanctuary'])
def test_real_mdfc_without_verified_rulings_stays_pending_for_either_face(repo, name):
    path = FIXTURES / 'graveyard_permissions/bala-ged-recovery.json'
    data = path.read_bytes()
    provenance = json.loads(path.with_suffix('.json.provenance.json').read_text())
    assert hashlib.sha256(data).hexdigest() == provenance['sha256']
    raw = json.loads(data)
    assert raw['layout'] == 'modal_dfc'
    # This complete RAW fixture has no official rulings snapshot. Do not invent one.
    stored(repo, raw, [], verified=False)
    before = saved(repo)
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        assert KnowledgeIngestor(repo, client).cached(name) is None
    assert saved(repo) == before


@pytest.mark.parametrize('force', [False, True])
def test_missing_raw_or_force_keeps_named_resync_and_preserves_learned_fields(repo, official, force):
    cards, rulings = official
    raw = next(card for card in cards if card['name'] == 'Lightning Bolt')
    row = stored(repo, raw, rulings[raw['id']])
    profile = json.loads(row.profiles_json)
    if not force:
        profile.pop('card_data')
        row.profiles_json = json.dumps(profile)
        repo.session.add(row)
        repo.session.commit()
        repo.session.refresh(row)
    before = row.model_dump()
    requests = []

    def resync(request):
        requests.append(str(request.url))
        if request.url.path == '/cards/named':
            assert dict(request.url.params) == {'fuzzy': raw['name']}
            return httpx.Response(200, json=raw)
        assert str(request.url) == raw['rulings_uri']
        return httpx.Response(200, json={'object': 'list', 'data': rulings[raw['id']], 'has_more': False})

    with httpx.Client(transport=httpx.MockTransport(resync)) as client:
        assert KnowledgeIngestor(repo, client).sync_name(raw['name'], force=force) == 'synced'
    assert len(requests) == 2
    updated = repo.get_card_knowledge(raw['name']).model_dump()
    assert {key: value for key, value in updated.items() if key not in {'profiles_json', 'updated_at'}} == {
        key: value for key, value in before.items() if key not in {'profiles_json', 'updated_at'}}
    assert json.loads(updated['profiles_json'])['future_namespace'] == profile['future_namespace']
    assert repo.get_cached_card_by_name(raw['name']) is not None


def test_force_failure_does_not_repair_from_the_snapshot_being_refreshed(repo, official):
    cards, rulings = official
    raw = next(card for card in cards if card['name'] == 'Lightning Bolt')
    stored(repo, raw, rulings[raw['id']])
    before = saved(repo)

    def unavailable(request):
        assert request.url.path == '/cards/named'
        raise httpx.ConnectError('Deliberate offline transport', request=request)

    with httpx.Client(transport=httpx.MockTransport(unavailable)) as client:
        with pytest.raises(httpx.ConnectError):
            KnowledgeIngestor(repo, client).sync_name(raw['name'], force=True)
    assert saved(repo) == before


@pytest.mark.parametrize('missing', ['oracle_text', 'mana_cost'])
def test_incomplete_stored_surface_is_not_padded_into_a_cache_hit(repo, official, missing):
    cards, rulings = official
    raw = next(card for card in cards if card['name'] == 'Lightning Bolt')
    row = stored(repo, raw, rulings[raw['id']])
    profile = json.loads(row.profiles_json)
    profile['card_data'].pop(missing)
    profile['card_data_sha256'] = canonical_hash(profile['card_data'])
    row.profiles_json = json.dumps(profile)
    repo.session.add(row)
    repo.session.commit()
    before = saved(repo)
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        assert KnowledgeIngestor(repo, client).cached(raw['name']) is None
    assert saved(repo) == before


def test_existing_local_cache_and_verified_knowledge_are_not_rewritten(repo, official):
    cards, rulings = official
    raw = next(card for card in cards if card['name'] == 'Lightning Bolt')
    stored(repo, raw, rulings[raw['id']])
    repo.upsert_card(sync.ScryfallSyncService._normalize_payload(
        raw, '/card-images/already-downloaded.jpg', rulings[raw['id']]))
    before = saved(repo)
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        assert KnowledgeIngestor(repo, client).sync_name(raw['name']) == 'cached'
    assert saved(repo) == before


def test_all155_official_payloads_and_rulings_recover_and_repeat_in_a_new_session(repo, official):
    cards, rulings = official
    for raw in cards:
        stored(repo, raw, rulings[raw['id']])
    before = saved(repo)[0]
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        ingestor = KnowledgeIngestor(repo, client)
        for raw in cards:
            assert ingestor.sync_name(raw['name']) == 'cached'
            cache = repo.get_cached_card_by_name(raw['name'])
            assert cache is not None
            assert json.loads(cache.rulings_json) == rulings[raw['id']]
            assert json.loads(cache.card_faces_json) == sync.ScryfallSyncService._normalize_faces(raw.get('card_faces', []))
    assert len(repo.list_cards()) == 155
    assert saved(repo)[0] == before
    stable = saved(repo)
    with Session(repo.session.bind) as session, httpx.Client(transport=httpx.MockTransport(offline)) as client:
        reopened = Repository(session)
        ingestor = KnowledgeIngestor(reopened, client)
        for raw in cards:
            assert ingestor.sync_name(raw['name']) == 'cached'
        assert saved(reopened) == stable


@pytest.mark.parametrize('field,value', [
    ('type_line', 17), ('oracle_text', 17), ('mana_cost', 17), ('power', 17),
    ('toughness', 17), ('loyalty', 17), ('layout', 17), ('colors', 'UR'),
    ('legalities', []), ('image_uris', {'normal': 17}),
])
def test_dfc_malformed_consumed_root_fields_are_rejected_despite_valid_faces(repo, official, field, value):
    cards, rulings = official
    raw = next(card for card in cards if card['name'].startswith('Delver of Secrets //'))
    row = stored(repo, raw, rulings[raw['id']])
    profile = json.loads(row.profiles_json)
    profile['card_data'][field] = value
    profile['card_data_sha256'] = canonical_hash(profile['card_data'])
    row.profiles_json = json.dumps(profile)
    repo.session.add(row)
    repo.session.commit()
    before = saved(repo)
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        assert KnowledgeIngestor(repo, client).cached(raw['card_faces'][0]['name']) is None
    assert saved(repo) == before


@pytest.mark.parametrize('mode', ['absent', 'null'])
def test_dfc_root_fallback_fields_may_be_absent_or_null_without_losing_faces(repo, official, mode):
    cards, rulings = official
    raw = deepcopy(next(card for card in cards if card['name'].startswith('Delver of Secrets //')))
    for field in ('type_line', 'oracle_text', 'mana_cost', 'power', 'toughness',
                  'loyalty', 'colors', 'image_uris'):
        if mode == 'absent':
            raw.pop(field, None)
        else:
            raw[field] = None
    row = stored(repo, raw, rulings[raw['id']])
    before = row.model_dump()
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        ingestor = KnowledgeIngestor(repo, client)
        assert ingestor.sync_name(raw['card_faces'][0]['name']) == 'cached'
        cache = repo.get_cached_card_by_name(raw['name'])
        assert cache is not None
        assert cache.type_line == raw['card_faces'][0]['type_line']
        assert cache.oracle_text == raw['card_faces'][0]['oracle_text']
        assert cache.mana_cost == raw['card_faces'][0]['mana_cost']
        assert json.loads(cache.card_faces_json) == sync.ScryfallSyncService._normalize_faces(raw['card_faces'])
        assert repo.get_card_knowledge(raw['name']).model_dump() == before
        stable = saved(repo)
        assert ingestor.sync_name(raw['card_faces'][1]['name']) == 'cached'
        assert saved(repo) == stable
