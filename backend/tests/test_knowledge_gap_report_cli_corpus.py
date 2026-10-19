"""Supplemental actual CLI/corpus controls; separate from the frozen132-case cohort."""
import json
from copy import deepcopy
import pytest
from scripts import knowledge_gap_report as gap
from tests import test_knowledge_gap_report_fields as fields
knowledge = fields.knowledge
report = fields.report
field = fields.field
Rows = fields.Rows

@pytest.mark.parametrize('container', ['absent', 'empty'])
def test_declared_multiface_missing_surfaces_remain_unavailable(container):
    row = knowledge(text='A nonblank wrapper is not a selected face')
    profile = json.loads(row.profiles_json)
    profile['card_data']['layout'] = 'transform'
    if container == 'empty':
        profile['card_data']['card_faces'] = []
    row.profiles_json = json.dumps(profile)
    card = report(Rows([row]))['cards'][0]
    assert field(card, 'oracle_text_blank') is None


@pytest.mark.parametrize('kind, expected', [('verified_empty', 0), ('unverified', 1),
    ('manual', 1), ('missing', 1), ('truthy_false', 1)])
def test_actual_cli_exit_policy_on_real_prepared_repository(tmp_path, monkeypatch, capsys, kind, expected):
    import sys
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine
    from persistence.repository import Repository
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            repo = Repository(session)
            if kind != 'missing':
                repo.upsert_card_knowledge({'name': 'Vanilla', 'oracle_source':
                    'manual' if kind == 'manual' else 'scryfall', 'profiles': {
                    'card_data': {'name': 'Vanilla', 'oracle_id': 'oracle', 'oracle_text': ''},
                    'rulings_verified': 'false' if kind == 'truthy_false' else kind != 'unverified',
                    'rulings': []}})
            before = [row.model_dump() for row in repo.list_card_knowledge()]
        monkeypatch.setattr(gap, 'engine', engine)
        monkeypatch.setattr(gap, 'init_db', lambda: SQLModel.metadata.create_all(engine))
        monkeypatch.setattr(gap, 'collect_corpus', lambda: {'fixture': {'name': 'Vanilla'}})
        output = tmp_path / 'coverage.json'
        monkeypatch.setattr(sys, 'argv', ['knowledge_gap_report', '--require-rulings',
            '--image-cache-dir', str(tmp_path), '--out', str(output)])
        assert gap.main() == expected
        value = json.loads(output.read_text())
        assert json.loads(capsys.readouterr().out) == value
        assert value['coverage']['cached'] == 0
        assert value['rules_support_certified'] is False
        assert str(tmp_path) not in json.dumps(value)
        with Session(engine) as session:
            assert [row.model_dump() for row in Repository(session).list_card_knowledge()] == before
    finally:
        engine.dispose()


def test_actual_155_official_rows_and_current_corpus_cli_fields(tmp_path, monkeypatch, capsys):
    import sys
    import httpx
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine
    from persistence.repository import Repository
    from knowledge.ingest import KnowledgeIngestor
    from tests import test_knowledge_rulings_corpus as official

    cards, pages = official.corpus()  # Existing pinned complete public intake, not normalized/fabricated RAW.
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    requests = []
    def respond(request):
        assert str(request.url) in pages
        requests.append(str(request.url))
        return httpx.Response(200, json=pages[str(request.url)])
    try:
        with Session(engine) as session, httpx.Client(transport=httpx.MockTransport(respond)) as client:
            repo = Repository(session)
            ingestor = KnowledgeIngestor(repo, client)
            for raw in cards:
                ingestor.sync_payload(deepcopy(raw))
            assert len(requests) == len(repo.list_cards()) == len(repo.list_card_knowledge()) == 155
            before = ([row.model_dump() for row in repo.list_cards()],
                      [row.model_dump() for row in repo.list_card_knowledge()])
            all_rows = gap.knowledge_report(repo, [card['name'] for card in cards], image_cache_dir=tmp_path)
            assert all_rows['requested_cards'] == 155
            assert all_rows['missing_cards'] == all_rows['rulings_pending'] == []
            assert all_rows['coverage']['knowledge_present'] == all_rows['coverage']['cached'] == 155
            assert sum(row['rulings_count'] == 0 for row in all_rows['cards']) == 35
            assert all(row['oracle_source'] == 'scryfall' for row in all_rows['cards'])
            assert all_rows['coverage']['local_image'] == 0  # No downloaded art in this bound root.
            expected_names = {item['name'] for item in gap.collect_corpus().values()}
        monkeypatch.setattr(gap, 'engine', engine)
        monkeypatch.setattr(gap, 'init_db', lambda: SQLModel.metadata.create_all(engine))
        monkeypatch.setattr(sys, 'argv', ['knowledge_gap_report', '--require-rulings',
            '--image-cache-dir', str(tmp_path), '--out', str(tmp_path / 'actual-corpus.json')])
        assert gap.main() == 0
        cli = json.loads(capsys.readouterr().out)
        assert cli['requested_cards'] == len(expected_names)
        assert {row['name'] for row in cli['cards']} == expected_names
        assert cli['missing_cards'] == cli['rulings_pending'] == []
        assert all(row['cached'] and row['knowledge_present'] for row in cli['cards'])
        assert str(tmp_path) not in json.dumps(cli)
        with Session(engine) as session:
            repo = Repository(session)
            assert ([row.model_dump() for row in repo.list_cards()],
                    [row.model_dump() for row in repo.list_card_knowledge()]) == before
    finally:
        engine.dispose()
