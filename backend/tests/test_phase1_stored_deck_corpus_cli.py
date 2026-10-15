"""Owned-file SQL/MockTransport acceptance; no games, rules certificate or live intake."""
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import httpx
import pytest
from sqlmodel import Session, create_engine

from knowledge.ingest import KnowledgeIngestor
from persistence import db
from persistence.repository import Repository
from scripts import knowledge_gap_report as gap
from scripts import sync_corpus_cards as sync
from tests import test_knowledge_rulings_corpus as official


def persisted_rows(engine):
    with Session(engine) as session:
        repo = Repository(session)
        return tuple(sorted((row.model_dump() for row in values), key=lambda row: row['id'])
                     for values in (repo.list_decks(), repo.list_cards(), repo.list_card_knowledge()))


@pytest.mark.parametrize('casefold_duplicates', [False, True], ids=['canonical', 'casefold-duplicates'])
def test_stored_main_and_side_cli_roundtrip(tmp_path, monkeypatch, capsys, casefold_duplicates):
    cards, pages = official.corpus()
    raw_by_alias = {name.casefold(): raw for raw in cards
                    for name in [raw['name'], *(face['name'] for face in raw.get('card_faces', []))]}
    defaults = {item['name'] for item in gap.collect_corpus().values()}
    default_ids = {raw_by_alias[name.casefold()]['id'] for name in defaults}
    assert len(defaults) == len(default_ids) == 149
    main_name, side_name = 'Farewell', 'Supreme Verdict'
    assert all(name.casefold() not in {s.casefold() for s in defaults} for name in (main_name, side_name))
    assert all(name.casefold() in raw_by_alias for name in (main_name, side_name))

    sql_root = Path(os.environ.get('PHASE1_OWN_SQL_ROOT', str(tmp_path))).resolve()
    filename = sql_root / ('casefold.sqlite' if casefold_duplicates else 'canonical.sqlite')
    assert not filename.exists()
    engine = create_engine('sqlite:///' + str(filename))
    created_engines = [engine]
    real_create_engine, real_client = sync.create_engine, httpx.Client
    requests = []

    def respond(request):
        assert len(requests) < 160, 'Finite per-case MockTransport request bound'
        url = str(request.url)
        requests.append(url)
        if request.url.path == '/cards/named':
            assert request.url.host == 'api.scryfall.com'
            assert set(request.url.params) == {'exact'}
            body = raw_by_alias[request.url.params['exact'].casefold()]
        else:
            assert url in pages
            body = pages[url]
        return httpx.Response(200, json=deepcopy(body))

    def tracked_engine(url, *args, **kwargs):
        assert url == 'sqlite:///' + str(filename)
        selected = real_create_engine(url, *args, **kwargs)
        created_engines.append(selected)
        return selected

    def mock_client(*args, **kwargs):
        assert 'transport' not in kwargs
        return real_client(*args, transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(gap, 'engine', engine)
    monkeypatch.setattr(sync, 'create_engine', tracked_engine)
    monkeypatch.setattr(sync.httpx, 'Client', mock_client)
    try:
        db.init_db()  # Real schema path, redirected to this owned engine; no default DB.
        with Session(engine) as session, real_client(transport=httpx.MockTransport(respond)) as client:
            repo = Repository(session)
            ingestor = KnowledgeIngestor(repo, client)
            for raw in cards:
                if raw['id'] in default_ids:
                    ingestor.sync_payload(deepcopy(raw))
            main = [{'quantity': 1, 'card_name': main_name}, {'quantity': 59, 'card_name': 'Island'}]
            side = [{'quantity': 1, 'card_name': side_name}, {'quantity': 14, 'card_name': 'Island'}]
            if casefold_duplicates:
                main = [{'quantity': 1, 'card_name': main_name},
                        {'quantity': 1, 'card_name': main_name.upper()}, {'quantity': 58, 'card_name': 'Island'}]
                side = [{'quantity': 1, 'card_name': side_name},
                        {'quantity': 1, 'card_name': side_name.lower()}, {'quantity': 13, 'card_name': 'Island'}]
            stored = repo.save_deck('Owned canonical stored corpus', 'unit-acceptance', main, side, 'Control')
            assert json.loads(stored.mainboard_json) == main
            assert json.loads(stored.sideboard_json) == side
            assert sum(row['quantity'] for row in main) == 60
            assert sum(row['quantity'] for row in side) == 15
            assert len(repo.list_cards()) == len(repo.list_card_knowledge()) == 149

        def report_gap(label):
            before = persisted_rows(engine)
            output = tmp_path / (label + '.json')
            monkeypatch.setattr(sys, 'argv', ['knowledge_gap_report', '--require-rulings',
                '--image-cache-dir', str(tmp_path), '--out', str(output)])
            rc = gap.main()
            value = json.loads(output.read_bytes())
            assert json.loads(capsys.readouterr().out) == value
            assert persisted_rows(engine) == before
            assert value['rules_support_certified'] is False
            return rc, value

        rc, before = report_gap('before')
        assert rc == 1
        assert {name.casefold() for name in before['missing_cards']} == {main_name.casefold(), side_name.casefold()}
        assert before['requested_cards'] == 151  # Casefold aliases are the same requested canonical card.
        assert len({row['name'].casefold() for row in before['cards']}) == len(before['cards'])
        calls_before = len(requests)

        def sync_cli(label):
            output = tmp_path / (label + '.json')
            monkeypatch.setattr(sys, 'argv', ['sync_corpus_cards', '--database', str(filename), '--out', str(output)])
            rc = sync.main()
            capsys.readouterr()
            value = json.loads(output.read_bytes())
            assert rc == 0 and value['errors'] == []
            return value

        summary = sync_cli('first-sync')
        assert summary['synced'] == 2
        assert len(requests) - calls_before == 4  # Two named records and their two official rulings lists.
        requested = Counter(httpx.URL(url).params['exact'].casefold() for url in requests[calls_before:]
                            if httpx.URL(url).path == '/cards/named')
        assert requested == Counter({main_name.casefold(): 1, side_name.casefold(): 1})
        rc, after = report_gap('after')
        assert rc == 0 and after['missing_cards'] == after['rulings_pending'] == []
        assert after['requested_cards'] == after['coverage']['knowledge_present'] == after['coverage']['cached'] == 151
        with Session(engine) as session:
            repo = Repository(session)
            assert len(repo.list_card_knowledge()) == len(repo.list_cards()) == 151
            for name in (main_name, side_name):
                profile = json.loads(repo.get_card_knowledge(name).profiles_json)
                raw = raw_by_alias[name.casefold()]
                assert profile['card_data'] == raw
                assert profile['rulings'] == pages[raw['rulings_uri']]['data']
                assert profile['rulings_verified'] is True
        stable, request_count = persisted_rows(engine), len(requests)
        repeat = sync_cli('repeat-sync')
        assert repeat['synced'] == 0
        assert len(requests) == request_count
        assert persisted_rows(engine) == stable
    finally:
        for selected in created_engines:
            selected.dispose()


def test_first_spelling_preserved_and_distinct_printed_face_aliases_remain_distinct(tmp_path):
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel
    cards, _ = official.corpus()
    aliases = {name for raw in cards for name in [raw['name'], *(face['name'] for face in raw.get('card_faces', []))]}
    assert {'Farewell', 'Brazen Borrower', 'Petty Theft'} <= aliases
    names = ['farewell', 'Farewell', 'FAREWELL', 'Brazen Borrower', 'Petty Theft', 'BRAZEN BORROWER']
    before = deepcopy(names)
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            repo = Repository(session)
            result = gap.knowledge_report(repo, names, image_cache_dir=tmp_path)
            assert [card['name'] for card in result['cards']] == ['Brazen Borrower', 'farewell', 'Petty Theft']
            assert result['requested_cards'] == 3
            assert result['missing_cards'] == ['Brazen Borrower', 'farewell', 'Petty Theft']
            assert repo.list_cards() == repo.list_card_knowledge() == []
            assert result['rules_support_certified'] is False
        assert names == before
    finally:
        engine.dispose()
