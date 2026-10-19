"""Declared canonical data acceptance; real owned SQL and in-process CLI only."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from card_data.hydration import hydrate_deck_cards
from card_data.seed_cards import seed_card_payload
from knowledge.ingest import KnowledgeIngestor, canonical_hash
from persistence import db
from persistence.repository import Repository
from scripts import knowledge_gap_report as gap
from scripts import oracle_corpus_report as corpus
from scripts import sync_corpus_cards as sync
from tests.test_knowledge_rulings_corpus import corpus as official_corpus


FIXTURES = Path(__file__).parent / 'fixtures'
SEED = Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json'
TEXT_FIELDS = ('oracle_text', 'mana_cost', 'type_line', 'power', 'toughness', 'loyalty')


def official():
    cards, pages = official_corpus()
    provenance = json.loads((FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes())
    assert provenance['snapshot_sha256'] == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
    assert provenance['oracle_modified'] is False and provenance['response_statuses'] == [200, 200, 200]
    aliases = {}
    for raw in cards:
        for name in [raw['name'], *(face['name'] for face in raw.get('card_faces', []))]:
            key = name.casefold()
            assert key not in aliases or aliases[key] == raw
            aliases[key] = raw
    return cards, pages, aliases


def rows(engine):
    with Session(engine) as session:
        repo = Repository(session)
        return tuple(sorted((row.model_dump() for row in values), key=lambda row: row['id'])
                     for values in (repo.list_decks(), repo.list_cards(), repo.list_card_knowledge()))


@contextmanager
def owned_database(tmp_path, monkeypatch, filename=None):
    url = 'sqlite:///:memory:' if filename is None else 'sqlite:///' + str(tmp_path / filename)
    engine = create_engine(url, poolclass=StaticPool)
    created = [engine]
    real_engine, real_client = sync.create_engine, httpx.Client
    cards, pages, aliases = official()
    requests = []

    def respond(request):
        assert len(requests) < 400, 'Finite complete-fixture request bound'
        assert request.url.scheme == 'https' and request.url.host == 'api.scryfall.com'
        requests.append(str(request.url))
        if request.url.path == '/cards/named':
            assert set(request.url.params) == {'fuzzy'}
            raw = aliases.get(request.url.params['fuzzy'].strip().casefold())
            return httpx.Response(404) if raw is None else httpx.Response(200, json=deepcopy(raw))
        assert str(request.url) in pages
        return httpx.Response(200, json=deepcopy(pages[str(request.url)]))

    def selected_engine(selected, *args, **kwargs):
        assert filename is not None and selected == url
        result = real_engine(selected, *args, **kwargs)
        created.append(result)
        return result

    def selected_client(*args, **kwargs):
        assert 'transport' not in kwargs
        return real_client(*args, transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(gap, 'engine', engine)
    monkeypatch.setattr(sync, 'create_engine', selected_engine)
    monkeypatch.setattr(sync.httpx, 'Client', selected_client)
    try:
        SQLModel.metadata.create_all(engine)
        with real_client(transport=httpx.MockTransport(respond)) as client:
            yield engine, client, cards, pages, aliases, requests
    finally:
        for selected in created:
            selected.dispose()


def prime(engine, client, cards, names):
    wanted = {name.casefold() for name in names}
    with Session(engine) as session:
        ingestor = KnowledgeIngestor(Repository(session), client)
        for raw in cards:
            aliases = {raw['name'].casefold(), *(face['name'].casefold() for face in raw.get('card_faces', []))}
            if wanted.intersection(aliases):
                ingestor.sync_payload(deepcopy(raw))


def report_cli(engine, tmp_path, monkeypatch, capsys, label):
    before = rows(engine)
    output = tmp_path / (label + '.json')
    monkeypatch.setattr(sys, 'argv', ['knowledge_gap_report', '--require-rulings',
                                    '--image-cache-dir', str(tmp_path), '--out', str(output)])
    status = gap.main()
    value = json.loads(output.read_bytes())
    assert json.loads(capsys.readouterr().out) == value
    assert rows(engine) == before
    assert value['rules_support_certified'] is False
    return status, value


def sync_cli(filename, tmp_path, monkeypatch, capsys, label):
    output = tmp_path / (label + '.json')
    monkeypatch.setattr(sys, 'argv', ['sync_corpus_cards', '--database', str(filename), '--out', str(output)])
    status = sync.main()
    capsys.readouterr()
    return status, json.loads(output.read_bytes())


def copy_builtin(monkeypatch, name):
    original = corpus.BUILTIN_DECKS
    before = deepcopy(original)
    copied = deepcopy(original)
    key = next(iter(copied))
    copied[key] += '\n1 ' + name + '\n'
    monkeypatch.setattr(corpus, 'BUILTIN_DECKS', copied)
    assert sync.collect_corpus is gap.collect_corpus is corpus.collect_corpus
    assert original == before and copied is not original
    return original, before


def assert_canonical(repo, raw, pages):
    row = repo.get_card_knowledge(raw['name'])
    cache = repo.get_cached_card_by_name(raw['name'])
    profile = json.loads(row.profiles_json)
    rulings = pages[raw['rulings_uri']]['data']
    assert row.scryfall_id == cache.scryfall_id == raw['id']
    assert row.oracle_source == 'scryfall'
    assert profile['oracle_id'] == raw['oracle_id']
    assert profile['card_data'] == raw
    assert profile['card_data_sha256'] == canonical_hash(raw)
    assert profile['rulings_verified'] is True
    assert profile['rulings'] == json.loads(cache.rulings_json) == rulings
    assert profile['rulings_provenance']['complete'] is True
    assert profile['rulings_provenance']['source'] == 'scryfall'
    assert profile['rulings_provenance']['uri'] == raw['rulings_uri']
    assert profile['rulings_provenance']['sha256'] == canonical_hash(rulings)
    front = (raw.get('card_faces') or [{}])[0]
    for key in TEXT_FIELDS:
        expected = raw.get(key) or front.get(key)
        if key in ('oracle_text', 'mana_cost', 'type_line'):
            expected = expected or ''
        assert getattr(cache, key) == expected, (raw['name'], key)
    assert cache.layout == raw.get('layout', '')
    assert cache.colors == ','.join(raw.get('colors') or front.get('colors', []))
    assert json.loads(cache.legalities_json) == raw.get('legalities', {})
    faces = json.loads(cache.card_faces_json)
    assert [face['name'] for face in faces] == [face['name'] for face in raw.get('card_faces', [])]
    for actual, expected in zip(faces, raw.get('card_faces', [])):
        for key in ('name', *TEXT_FIELDS, 'colors'):
            assert actual.get(key) == expected.get(key), (raw['name'], expected['name'], key)


def test_copied_builtin_unknown_name_fails_without_fabricated_sync(tmp_path, monkeypatch, capsys):
    defaults = [entry['name'] for entry in corpus.collect_corpus().values()]
    unknown = 'Phase1 Definitely Nonexistent Canonical Card'
    assert unknown.casefold() not in {name.casefold() for name in defaults}
    with owned_database(tmp_path, monkeypatch, 'builtin-fake.sqlite') as data:
        engine, client, cards, pages, aliases, requests = data
        assert unknown.casefold() not in aliases
        prime(engine, client, cards, defaults)
        assert report_cli(engine, tmp_path, monkeypatch, capsys, 'baseline')[0] == 0
        original, before = copy_builtin(monkeypatch, unknown)
        status, missing = report_cli(engine, tmp_path, monkeypatch, capsys, 'fake-missing')
        assert status == 1 and missing['missing_cards'] == [unknown]
        stable, count = rows(engine), len(requests)
        status, summary = sync_cli(tmp_path / 'builtin-fake.sqlite', tmp_path, monkeypatch, capsys, 'fake-sync')
        assert status == 1 and summary['synced'] == 0
        assert [error['name'] for error in summary['errors']] == [unknown]
        assert len(requests) == count + 1
        assert dict(httpx.URL(requests[-1]).params) == {'fuzzy': unknown}
        assert rows(engine) == stable
        assert report_cli(engine, tmp_path, monkeypatch, capsys, 'fake-after')[0] == 1
        with Session(engine) as session:
            repo = Repository(session)
            assert repo.get_card_knowledge(unknown) is None
            assert repo.get_cached_card_by_name(unknown) is None
        assert original == before


def test_copied_builtin_real_unsynced_name_cli_sync_passes_and_repeats_offline(tmp_path, monkeypatch, capsys):
    defaults = [entry['name'] for entry in corpus.collect_corpus().values()]
    name = 'Farewell'
    assert name.casefold() not in {value.casefold() for value in defaults}
    with owned_database(tmp_path, monkeypatch, 'builtin-real.sqlite') as data:
        engine, client, cards, pages, aliases, requests = data
        prime(engine, client, cards, defaults)
        original, before = copy_builtin(monkeypatch, name)
        status, missing = report_cli(engine, tmp_path, monkeypatch, capsys, 'real-missing')
        assert status == 1 and missing['missing_cards'] == [name]
        count = len(requests)
        status, summary = sync_cli(tmp_path / 'builtin-real.sqlite', tmp_path, monkeypatch, capsys, 'real-sync')
        assert status == 0 and summary['synced'] == 1 and summary['errors'] == []
        assert len(requests) == count + 2
        assert dict(httpx.URL(requests[count]).params) == {'fuzzy': name}
        assert requests[count + 1] == aliases[name.casefold()]['rulings_uri']
        status, complete = report_cli(engine, tmp_path, monkeypatch, capsys, 'real-after')
        assert status == 0 and complete['missing_cards'] == complete['rulings_pending'] == []
        assert complete['coverage']['cached'] == complete['coverage']['knowledge_present'] == len(defaults) + 1
        with Session(engine) as session:
            repo = Repository(session)
            assert_canonical(repo, aliases[name.casefold()], pages)
            row = repo.get_card_knowledge(name)
            profile = json.loads(row.profiles_json)
            profile['future_namespace'] = {'opaque': [1, None, {'retain': True}]}
            row.profiles_json = json.dumps(profile, sort_keys=True)
            row.play_value, row.threat_level, row.etb_impact = 7.25, 2, 1.5
            row.answerable_by_json, row.cast_windows_json = '["counter"]', '["instant_window"]'
            session.add(row)
            session.commit()
        stable, count = rows(engine), len(requests)
        status, repeat = sync_cli(tmp_path / 'builtin-real.sqlite', tmp_path, monkeypatch, capsys, 'real-repeat')
        assert status == 0 and repeat['synced'] == 0 and repeat['errors'] == []
        assert len(requests) == count
        assert rows(engine) == stable
        assert original == before


def test_declared_corpus_aliases_join_full_canonical_cache_knowledge_and_rulings(tmp_path, monkeypatch, capsys):
    with owned_database(tmp_path, monkeypatch) as data:
        engine, client, cards, pages, aliases, requests = data
        prime(engine, client, cards, [raw['name'] for raw in cards])
        with Session(engine) as session:
            repo = Repository(session)
            repo.save_deck('Declared canonical corpus', 'unit-acceptance',
                           [{'quantity': 1, 'card_name': 'Farewell'}, {'quantity': 1, 'card_name': 'FAREWELL'},
                            {'quantity': 4, 'card_name': 'Delver of Secrets'}, {'quantity': 54, 'card_name': 'Island'}],
                           [{'quantity': 1, 'card_name': 'Supreme Verdict'},
                            {'quantity': 1, 'card_name': 'Insectile Aberration'}, {'quantity': 13, 'card_name': 'Island'}], 'Control')
            requested = [row['name'] for row in corpus.collect_corpus().values()]
            for deck in repo.list_decks():
                for board in (deck.mainboard_json, deck.sideboard_json):
                    requested.extend(row['card_name'] for row in json.loads(board))
            for name in requested:
                raw = aliases[name.casefold()]
                assert repo.get_card_knowledge(name).scryfall_id == raw['id']
                assert repo.get_cached_card_by_name(name).scryfall_id == raw['id']
                assert_canonical(repo, raw, pages)
            assert len(repo.list_cards()) == len(repo.list_card_knowledge()) == len(cards) == 155
            assert sum(len(pages[raw['rulings_uri']]['data']) for raw in cards) == 443
            assert sum(pages[raw['rulings_uri']]['data'] == [] for raw in cards) == 35
        stable, count = rows(engine), len(requests)
        status, report = report_cli(engine, tmp_path, monkeypatch, capsys, 'declared-join')
        assert status == 0 and report['missing_cards'] == report['rulings_pending'] == []
        assert {row['name'].casefold() for row in report['cards']} == {name.casefold() for name in requested}
        assert all(row['cached'] and row['knowledge_present'] and row['rulings_verified'] for row in report['cards'])
        assert len(requests) == count and rows(engine) == stable


def test_offline_seed_and_real_hydration_projection_reconcile_with_canonical_rows(tmp_path, monkeypatch):
    protected = [SEED, *(FIXTURES / 'knowledge_profiles' / name for name in
                         ('seed155-scryfall.jsonl', 'seed155-rulings.jsonl', 'PROVENANCE.json', 'RULINGS_PROVENANCE.json')),
                 FIXTURES / 'builtin_face_colors/reviewed_admission.json',
                 FIXTURES / 'full155_export_audit/approved17-ledger.json',
                 FIXTURES / 'builtin_face_colors/canonical.jsonl']
    before = {path: path.read_bytes() for path in protected}
    assert hashlib.sha256(before[SEED]).hexdigest() == '9296ec1b24654374aaca985b92dc4c3b62a93e6fd024afcd6b4acd61a6007037'
    seed = json.loads(before[SEED])['cards']
    admission = json.loads(before[protected[-3]])
    ledger = json.loads(before[protected[-2]])
    admitted_raw = {raw['id']: raw for raw in map(json.loads, before[protected[-1]].splitlines())}
    with owned_database(tmp_path, monkeypatch) as data:
        engine, client, cards, pages, aliases, requests = data
        assert len(seed) == len(cards) == 155
        assert {aliases[name.casefold()]['name'] for name in seed} == {raw['name'] for raw in cards}
        for name, printed in seed.items():
            raw = aliases[name.casefold()]
            front = (raw.get('card_faces') or [{}])[0]
            assert seed_card_payload(name) == printed
            assert printed['name'] == raw['name']
            seed_layout = printed['layout']
            if not seed_layout and not raw.get('card_faces'):
                seed_layout = 'normal'
            assert seed_layout == raw['layout']
            physical = front if raw.get('layout') in {'modal_dfc', 'transform', 'adventure', 'reversible_card'} else raw
            for key in TEXT_FIELDS:
                if key in printed:
                    assert printed[key] == (physical.get(key) or ('' if key in ('oracle_text', 'mana_cost', 'type_line') else None)), (name, key)
            if 'colors' in printed:
                assert printed['colors'] == (raw.get('colors') or front.get('colors', [])), name
            assert len(printed.get('card_faces', [])) == len(raw.get('card_faces', []))
            for index, (face, full) in enumerate(zip(printed.get('card_faces', []), raw.get('card_faces', []))):
                for key, value in face.items():
                    if key == 'colors' and 'colors' not in full:
                        proof = [row for row in admission if row['scryfall_id'] == raw['id'] and row['face_index'] == index]
                        retained = [row for row in ledger if row['scryfall_id'] == raw['id'] and row.get('face_index') == index]
                        assert len(proof) == len(retained) == 1
                        assert proof[0]['fact_kind'] == retained[0]['fact_kind'] == 'derived_rule_fact'
                        assert value == proof[0]['colors'] == retained[0]['colors']
                        original_raw = admitted_raw[raw['id']]
                        assert original_raw['card_faces'][index] == full
                        raw_hash = hashlib.sha256(json.dumps(original_raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
                        assert proof[0]['raw_sha256'] == retained[0]['raw_sha256'] == raw_hash
                    else:
                        assert value == full.get(key), (name, index, key)
        board = [{'quantity': 1, 'card_name': name} for name in seed]
        with Session(engine) as session:
            repo = Repository(session)
            empty = rows(engine)
            offline = hydrate_deck_cards(repo, deepcopy(board))
            for entry in offline:
                printed = seed[entry['card_name']]
                assert entry['card_data_sources'] == ['offline_seed']
                assert entry['scryfall_id'] == printed['scryfall_id']
                assert entry['layout'] == printed['layout']
                for key in TEXT_FIELDS:
                    if key in printed:
                        assert entry.get(key) == printed[key], (entry['card_name'], key)
                assert entry.get('card_faces', []) == printed.get('card_faces', [])
            assert rows(engine) == empty
        prime(engine, client, cards, [raw['name'] for raw in cards])
        stable, count = rows(engine), len(requests)
        def no_network(*args, **kwargs):
            pytest.fail('Canonical offline hydration attempted a new request')
        monkeypatch.setattr('card_data.sync.get_with_backoff', no_network)
        with Session(engine) as session:
            repo = Repository(session)
            actual = hydrate_deck_cards(repo, deepcopy(board))
            assert len(actual) == len(seed)
            for entry in actual:
                raw = aliases[entry['card_name'].casefold()]
                assert_canonical(repo, raw, pages)
                front = (raw.get('card_faces') or [{}])[0]
                physical = front if raw.get('layout') in {'modal_dfc', 'transform', 'adventure', 'reversible_card'} else raw
                for key in TEXT_FIELDS:
                    expected = physical.get(key)
                    if key in ('oracle_text', 'mana_cost', 'type_line'):
                        expected = expected or ''
                    if expected is not None:
                        assert entry.get(key) == expected, (entry['card_name'], key)
                assert entry['scryfall_id'] == raw['id']
                assert entry['layout'] == raw['layout']
                assert entry['card_data_sources'] == ['offline_seed', 'local_knowledge', 'cache']
                assert [face['name'] for face in entry.get('card_faces', [])] == [face['name'] for face in raw.get('card_faces', [])]
                for actual_face, raw_face in zip(entry.get('card_faces', []), raw.get('card_faces', [])):
                    for key in (*TEXT_FIELDS, 'colors'):
                        assert actual_face.get(key) == raw_face.get(key), (entry['card_name'], raw_face['name'], key)
                colors = physical.get('colors')
                if colors is None:
                    colors = raw.get('colors') or front.get('colors') or []
                if raw.get('layout') == 'split':
                    colors = sorted({color for face in raw['card_faces'] for color in face.get('colors', [])})
                assert entry['colors'] == colors, entry['card_name']
        assert len(requests) == count and rows(engine) == stable
    assert {path: path.read_bytes() for path in protected} == before
