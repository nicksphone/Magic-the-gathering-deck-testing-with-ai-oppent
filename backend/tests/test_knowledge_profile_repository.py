"""Real repository roundtrips on an isolated, disposable in-memory database."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from persistence.repository import Repository
from scripts.sync_corpus_cards import profile_corpus


@pytest.fixture
def database():
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def raw(name):
    filename = {'Lightning Bolt': 'lightning-bolt.json',
                'Grizzly Bears': 'grizzly-bears-scryfall-raw.json'}[name]
    return json.loads((Path(__file__).parent / 'vraska_full/fixtures' / filename).read_text())


def payload(name):
    card = raw(name)
    return {'name': name, 'scryfall_id': card['id'], 'oracle_source': 'scryfall',
            'profiles': {'card_data': card, 'rulings_verified': True, 'rulings': [],
                         'future_namespace': {'preserve': [1, 2]}}}


def test_profiles_survive_new_session_and_identical_run_keeps_timestamps(database):
    names = ['Lightning Bolt', 'Grizzly Bears']
    originals = {name: deepcopy(payload(name)['profiles']) for name in names}
    with Session(database) as session:
        repo = Repository(session)
        for name in names:
            repo.upsert_card_knowledge(payload(name))
        assert profile_corpus(repo, names) == {'profiled': 2, 'profiles_updated': 2, 'errors': []}
        before = {}
        for name in names:
            value = repo.get_card_knowledge(name)
            profile = json.loads(value.profiles_json)
            assert {key: profile[key] for key in originals[name]} == originals[name]
            assert value.scryfall_id == originals[name]['card_data']['id']
            assert value.oracle_source == 'scryfall'
            assert value.play_value == profile['tactical_profile']['play_value']
            assert value.threat_level == profile['tactical_profile']['threat_level']
            assert json.loads(value.answerable_by_json) == profile['tactical_profile']['answerable_by']
            assert json.loads(value.cast_windows_json) == profile['tactical_profile']['cast_windows']
            before[name] = (value.id, value.updated_at, value.profiles_json)
    with Session(database) as session:
        repo = Repository(session)
        assert profile_corpus(repo, names) == {'profiled': 2, 'profiles_updated': 0, 'errors': []}
        for name in names:
            value = repo.get_card_knowledge(name)
            assert (value.id, value.updated_at, value.profiles_json) == before[name]


@pytest.mark.parametrize('invalid', ['identity', 'opaque_namespace'])
def test_invalid_row_is_unchanged_in_real_repository(database, invalid):
    entry = payload('Lightning Bolt')
    if invalid == 'identity':
        entry['scryfall_id'] = 'different-from-canonical'
    else:
        entry['profiles']['tactical_profile'] = ['opaque', 'future', 'data']
    with Session(database) as session:
        repo = Repository(session)
        value = repo.upsert_card_knowledge(entry)
        before = (value.id, value.updated_at, value.profiles_json,
                  value.scryfall_id, value.play_value, value.threat_level)
        result = profile_corpus(repo, ['Lightning Bolt'])
        assert result['profiled'] == result['profiles_updated'] == 0
        assert len(result['errors']) == 1
    with Session(database) as session:
        value = Repository(session).get_card_knowledge('Lightning Bolt')
        assert (value.id, value.updated_at, value.profiles_json,
                value.scryfall_id, value.play_value, value.threat_level) == before


def test_all_155_shipped_names_profile_and_roundtrip_canonical_data(database):
    folder = Path(__file__).parent / 'fixtures/knowledge_profiles'
    data = (folder / 'seed155-scryfall.jsonl').read_bytes()
    provenance = json.loads((folder / 'PROVENANCE.json').read_bytes())
    assert hashlib.sha256(data).hexdigest() == provenance['snapshot_sha256']
    cards = [json.loads(line) for line in data.splitlines()]
    assert len(cards) == len({card['id'] for card in cards}) == 155
    seed = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_text())['cards']
    assert len(seed) == 155
    expected = {card['name']: card for card in cards}
    with Session(database) as session:
        repo = Repository(session)
        for card in cards:
            repo.upsert_card_knowledge({
                'name': card['name'], 'scryfall_id': card['id'], 'oracle_source': 'scryfall',
                'profiles': {'card_data': card, 'rulings_verified': False, 'rulings': [],
                             'source_uri': card['uri'], 'future_metadata': {'preserved': True}},
            })
        result = profile_corpus(repo, list(seed))
        assert result == {'profiled': 155, 'profiles_updated': 155, 'errors': []}
    with Session(database) as session:
        repo = Repository(session)
        rows = repo.list_card_knowledge()
        assert len(rows) == 155
        for value in rows:
            profile = json.loads(value.profiles_json)
            assert profile['card_data'] == expected[value.name]
            assert profile['source_uri'] == expected[value.name]['uri']
            assert profile['future_metadata'] == {'preserved': True}
            assert profile['rulings_verified'] is False and profile['rulings'] == []
            assert value.scryfall_id == expected[value.name]['id']
            assert value.play_value == profile['tactical_profile']['play_value']
            assert value.threat_level == profile['tactical_profile']['threat_level']
        assert profile_corpus(repo, list(seed)) == {'profiled': 155, 'profiles_updated': 0, 'errors': []}
