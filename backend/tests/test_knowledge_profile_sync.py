"""Data-layer wiring controls; no SQL/network or playing-strength certificate."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import sync_corpus_cards as sync


def canonical(name):
    filename = {
        'Lightning Bolt': 'lightning-bolt.json',
        'Grizzly Bears': 'grizzly-bears-scryfall-raw.json',
    }[name]
    return json.loads((Path(__file__).parent / 'vraska_full/fixtures' / filename).read_text())


def row(name):
    raw = canonical(name)
    return SimpleNamespace(
        name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall',
        play_value=None, threat_level=None, etb_impact=None,
        answerable_by_json='[]', cast_windows_json='[]',
        profiles_json=json.dumps({
            'card_data': raw, 'rulings_verified': True, 'rulings': [],
            'future_metadata': {'retained': [1, 2]},
        }),
    )


class Repository:
    def __init__(self, rows):
        self.rows = {value.name.casefold(): value for value in rows}
        self.writes = []

    def get_card_knowledge_by_names(self, names):
        return {name.casefold(): self.rows[name.casefold()]
                for name in names if name.casefold() in self.rows}

    def upsert_card_knowledge(self, payload):
        self.writes.append(deepcopy(payload))
        value = self.rows[payload['name'].casefold()]
        for key in ('play_value', 'threat_level', 'etb_impact'):
            setattr(value, key, payload[key])
        for key in ('profiles', 'answerable_by', 'cast_windows'):
            setattr(value, key + '_json', json.dumps(payload[key]))
        return value


@pytest.fixture
def profile_api(monkeypatch):
    calls = []
    derived = SimpleNamespace(play_value=3.0, threat_level=1, etb_impact=None,
                              answerable_by=('exile_target',),
                              cast_windows=('main_phase',))

    def derive(raw, corpus=(), *, archetype=None):
        calls.append((deepcopy(raw), deepcopy(corpus), archetype))
        return derived

    def merge(existing, result):
        assert result is derived
        copied = deepcopy(existing)
        copied['tactical_profile'] = {'version': 1, 'heuristic': True}
        return copied

    monkeypatch.setattr(sync, 'derive_profile', derive, raising=False)
    monkeypatch.setattr(sync, 'merge_profile_payload', merge, raising=False)
    return calls


def function():
    value = getattr(sync, 'profile_corpus', None)
    assert callable(value), 'sync --profile needs the data-layer profiling path'
    return value


def test_profile_writes_preserve_complete_canonical_metadata(profile_api):
    rows = [row('Lightning Bolt'), row('Grizzly Bears')]
    repo = Repository(rows)
    before = {value.name: json.loads(value.profiles_json) for value in rows}
    result = function()(repo, ['Lightning Bolt', 'Grizzly Bears'])
    assert result == {'profiled': 2, 'profiles_updated': 2, 'errors': []}
    assert len(repo.writes) == len(profile_api) == 2
    for payload in repo.writes:
        original = before[payload['name']]
        assert payload['profiles'] == {**original, 'tactical_profile': {'version': 1, 'heuristic': True}}
        assert payload['scryfall_id'] == original['card_data']['id']
        assert payload['oracle_source'] == 'scryfall'
        assert payload['play_value'] == 3.0 and payload['threat_level'] == 1
        assert payload['etb_impact'] is None
        assert payload['answerable_by'] == ['exile_target']
        assert payload['cast_windows'] == ['main_phase']


@pytest.mark.parametrize('invalid', ['manual', 'wrong_id', 'bad_json', 'missing_raw'])
def test_invalid_canonical_row_is_not_overwritten(profile_api, invalid):
    value = row('Lightning Bolt')
    if invalid == 'manual':
        value.oracle_source = 'manual'
    elif invalid == 'wrong_id':
        value.scryfall_id = 'not-the-canonical-id'
    elif invalid == 'bad_json':
        value.profiles_json = '{'
    else:
        value.profiles_json = '{}'
    repo = Repository([value])
    before = deepcopy(vars(value))
    result = function()(repo, ['Lightning Bolt'])
    assert result['profiled'] == result['profiles_updated'] == 0
    assert len(result['errors']) == 1
    assert result['errors'][0]['name'] == 'Lightning Bolt'
    assert not repo.writes and not profile_api and vars(value) == before


def test_duplicates_and_unchanged_profiles_do_not_repeat_writes(profile_api):
    repo = Repository([row('Lightning Bolt')])
    first = function()(repo, ['Lightning Bolt', 'lightning bolt', 'Lightning Bolt'])
    assert first == {'profiled': 1, 'profiles_updated': 1, 'errors': []}
    second = function()(repo, ['Lightning Bolt'])
    assert second == {'profiled': 1, 'profiles_updated': 0, 'errors': []}
    assert len(repo.writes) == 1


def test_missing_requested_card_is_reported_not_silently_ignored(profile_api):
    repo = Repository([row('Lightning Bolt')])
    result = function()(repo, ['Lightning Bolt', 'Missing Canonical Card'])
    assert result['profiled'] == result['profiles_updated'] == 1
    assert [error['name'] for error in result['errors']] == ['Missing Canonical Card']
    assert len(repo.writes) == 1


def test_selected_context_is_forwarded_without_mutating_inputs(profile_api):
    repo = Repository([row('Lightning Bolt')])
    corpus = [{'quantity': 4, 'card_metadata': canonical('Lightning Bolt')}]
    original = deepcopy(corpus)
    result = function()(repo, ['Lightning Bolt'], corpus=corpus, archetype='Burn')
    assert result['errors'] == []
    assert profile_api[0][1:] == (original, 'Burn') and corpus == original


@pytest.fixture
def cli_repository(monkeypatch):
    repo = Repository([row('Lightning Bolt')])
    repo.list_decks = lambda: []
    repo.list_card_knowledge = lambda: list(repo.rows.values())
    events = []

    class Scope:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Ingestor:
        def __init__(self, repository, client):
            assert repository is repo

        def sync_name(self, name, force):
            events.append(name)
            return 'cached'

    monkeypatch.setattr(sync, 'init_db', lambda: None)
    monkeypatch.setattr(sync, 'Session', lambda *args: Scope())
    monkeypatch.setattr(sync.httpx, 'Client', lambda **kwargs: Scope())
    monkeypatch.setattr(sync, 'Repository', lambda session: repo)
    monkeypatch.setattr(sync, 'KnowledgeIngestor', Ingestor)
    monkeypatch.setattr(sync, 'collect_corpus', lambda: {'bolt': {'name': 'Lightning Bolt'}})
    return repo, events


def test_cli_profile_flag_uses_repository_after_canonical_sync(monkeypatch, profile_api, capsys, cli_repository):
    repo, events = cli_repository
    monkeypatch.setattr('sys.argv', ['sync_corpus_cards', '--profile'])
    assert sync.main() == 0
    assert events == ['Lightning Bolt'] and len(repo.writes) == 1
    assert '"profiled": 1' in capsys.readouterr().out


def test_unflagged_cli_keeps_original_summary_and_does_not_profile(monkeypatch, profile_api, capsys, cli_repository):
    repo, events = cli_repository
    monkeypatch.setattr('sys.argv', ['sync_corpus_cards'])
    assert sync.main() == 0
    assert events == ['Lightning Bolt'] and not repo.writes and not profile_api
    assert capsys.readouterr().out.endswith(json.dumps({
        'synced': 0, 'cached': 1, 'errors': [],
        'knowledge_rows': 1, 'requested_corpus_cards': 1,
    }, indent=2, sort_keys=True) + '\n')


def test_cli_deck_context_uses_real_quantities_and_existing_archetype_analysis(monkeypatch, profile_api, cli_repository):
    repo, events = cli_repository
    deck = SimpleNamespace(name='Chosen Context', mainboard_json=json.dumps([
        {'card_name': 'Lightning Bolt', 'quantity': 4},
    ]), sideboard_json='[]')
    repo.list_decks = lambda: [deck]
    seen = []

    def archetype(context):
        seen.append(deepcopy(context))
        return 'Burn'

    monkeypatch.setattr('ai.deck_analysis.guess_archetype', archetype)
    monkeypatch.setattr('sys.argv', ['sync_corpus_cards', '--profile', '--profile-deck', 'Chosen Context'])
    assert sync.main() == 0
    assert events == ['Lightning Bolt']
    expected = [{'quantity': 4, 'card_metadata': canonical('Lightning Bolt')}]
    assert seen == [expected] and profile_api[0][1:] == (expected, 'Burn')


def test_bad_deck_context_does_not_write_a_mislabelled_profile(monkeypatch, profile_api, cli_repository):
    repo, _ = cli_repository
    monkeypatch.setattr('sys.argv', ['sync_corpus_cards', '--profile', '--profile-deck', 'Not Stored'])
    assert sync.main() == 1
    assert not repo.writes and not profile_api


def test_profile_deck_requires_profile_flag_before_database_initialization(monkeypatch, profile_api, capsys):
    initialized = []
    monkeypatch.setattr(sync, 'init_db', lambda: initialized.append(True))
    monkeypatch.setattr('sys.argv', ['sync_corpus_cards', '--profile-deck', 'Chosen Context'])
    with pytest.raises(SystemExit) as rejected:
        sync.main()
    assert rejected.value.code == 2 and not initialized
    assert '--profile-deck requires --profile' in capsys.readouterr().err


@pytest.mark.parametrize('quantity', [-1, 1001, True, 1.5, '4', 0])
def test_deck_quantity_is_rejected_before_archetype_expansion(monkeypatch, profile_api, cli_repository, quantity):
    repo, _ = cli_repository
    repo.list_decks = lambda: [SimpleNamespace(name='Bad Context',
        mainboard_json=json.dumps([{'card_name': 'Lightning Bolt', 'quantity': quantity}]),
        sideboard_json='[]')]
    analyzed = []
    monkeypatch.setattr('ai.deck_analysis.guess_archetype', lambda values: analyzed.append(values) or 'Burn')
    monkeypatch.setattr('sys.argv', ['sync_corpus_cards', '--profile', '--profile-deck', 'Bad Context'])
    assert sync.main() == 1
    assert not analyzed and not profile_api and not repo.writes


@pytest.mark.parametrize('entries', [[], [{'card_name': 'Lightning Bolt', 'quantity': 1}] * 1025])
def test_empty_or_oversized_deck_context_is_rejected_before_analysis(monkeypatch, profile_api, cli_repository, entries):
    repo, _ = cli_repository
    repo.list_decks = lambda: [SimpleNamespace(name='Bad Context',
        mainboard_json=json.dumps(entries), sideboard_json='[]')]
    analyzed = []
    monkeypatch.setattr('ai.deck_analysis.guess_archetype', lambda values: analyzed.append(values) or 'Burn')
    monkeypatch.setattr('sys.argv', ['sync_corpus_cards', '--profile', '--profile-deck', 'Bad Context'])
    assert sync.main() == 1
    assert not analyzed and not profile_api and not repo.writes
