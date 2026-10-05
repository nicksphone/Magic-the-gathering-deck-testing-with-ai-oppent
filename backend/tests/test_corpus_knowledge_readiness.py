"""No shared fixtures, application import, source network, or live DB writes."""
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine

from knowledge.ingest import KnowledgeIngestor, canonical_hash
from persistence.repository import Repository
from scripts import corpus_knowledge_readiness as corpus
from scripts.sync_all_card_knowledge import import_cards


@pytest.fixture
def sources(tmp_path):
    raw = {'object': 'card', 'id': 'printing', 'oracle_id': 'oracle', 'name': 'Vanilla', 'type_line': 'Creature', 'oracle_text': '', 'mana_cost': '{1}{G}', 'power': '2', 'toughness': '2', 'cmc': 2, 'color_identity': ['G'], 'keywords': [], 'layout': 'normal', 'legalities': {'modern': 'legal'}, 'rulings_uri': 'https://api.scryfall.com/cards/printing/rulings'}
    database = tmp_path / 'source.db'
    engine = create_engine(f'sqlite:///{database}')
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        repo = Repository(session)
        import_cards(repo, [raw], {'source': 'scryfall', 'updated_at': '2026-09-27'})
        row = repo.get_card_knowledge('Vanilla')
        row.play_value = 7.25
        session.add(row)
        session.commit()
    engine.dispose()
    cards = tmp_path / 'cards.jsonl.gz'
    rulings = tmp_path / 'rulings.jsonl.gz'
    with gzip.open(cards, 'wt') as output:
        output.write(json.dumps(raw) + '\n')
    with gzip.open(rulings, 'wt') as output:
        output.write('')
    manifest = tmp_path / 'rulings.manifest.json'
    manifest.write_text(json.dumps({'type': 'rulings', 'updated_at': '2026-10-05T09:00:00Z', 'jsonl_download_uri': 'https://data.scryfall.io/rulings/test.jsonl.gz'}))
    args = SimpleNamespace(cards=cards, cards_sha256=corpus.file_hash(cards), cards_manifest=None, rulings=rulings, rulings_sha256=corpus.file_hash(rulings), rulings_manifest=manifest, state=tmp_path / 'state.db', limit=1, out=tmp_path / 'artifact.jsonl.gz')
    return database, raw, args


def test_report_separates_unknown_rulings_scores_and_competence(sources):
    database, raw, _ = sources
    before = corpus.file_hash(database)
    with corpus.readonly(database) as conn:
        report = corpus.audit(conn)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('DELETE FROM cardknowledge')
    card = report['cards'][0]
    assert not card['fact_gaps'] and card['canonical_admissible'] and card['match_metadata_ready']
    assert card['rulings_status'] == 'pending' and card['rulings_count'] is None
    assert not card['source_record_evidence']
    assert card['tactical_tags'] == 'current'
    assert card['engine_support'] == 'not_certified' and card['trained_competence'] == 'unknown'
    assert corpus.file_hash(database) == before


def test_prepare_resumes_and_validate_preserves_source_and_numeric_values(sources):
    database, raw, args = sources
    before = corpus.file_hash(database)
    with corpus.readonly(database) as conn:
        first = corpus.prepare(conn, args)
        args.out = args.out.with_name('resumed.jsonl.gz')
        second = corpus.prepare(conn, args)
        assert first['processed_this_run'] == 1 and first['patches'] == 1
        assert second['processed_this_run'] == 0 and second['patches'] == 1
        result = corpus.validate_artifact(conn, args.out, database.parent / 'scratch.db')
    assert result['validated_import_rows'] == 1
    card = result['after']['cards'][0]
    assert card['rulings_status'] == 'verified_empty' and card['source_record_evidence']
    with corpus.readonly(database.parent / 'scratch.db') as conn:
        row = conn.execute('SELECT play_value,profiles_json FROM cardknowledge').fetchone()
        assert row[0] == 7.25
        assert json.loads(row[1])['card_data'] == raw
    assert corpus.file_hash(database) == before
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='already exist'):
        corpus.validate_artifact(conn, args.out, database)


def test_source_mismatch_and_resume_change_fail_closed(sources):
    database, raw, args = sources
    args.cards_sha256 = 'bad'
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='SHA256 mismatch'):
        corpus.prepare(conn, args)
    args.cards_sha256 = corpus.file_hash(args.cards)
    with corpus.readonly(database) as conn:
        corpus.prepare(conn, args)
    args.rulings = args.rulings_sha256 = None
    args.out = args.out.with_name('changed-inputs.jsonl.gz')
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='Resume inputs changed'):
        corpus.prepare(conn, args)


def test_face_and_characteristic_gaps_do_not_treat_vanilla_empty_as_missing(sources):
    _, raw, _ = sources
    assert corpus.fact_gaps(raw) == []
    assert 'card_faces_count' in corpus.fact_gaps({**raw, 'layout': 'transform'})
    assert 'power' in corpus.fact_gaps({**raw, 'power': None})
    face = {key: value for key, value in raw.items() if key not in {'oracle_text', 'power'}}
    assert {'face:0:oracle_text', 'face:0:power'} <= set(corpus.fact_gaps({**raw, 'layout': 'transform', 'card_faces': [face, raw]}))


@pytest.mark.parametrize('bad', [ {'object': 'list', 'data': [], 'has_more': True, 'next_page': 'https://api.scryfall.com/cards/printing/rulings'}, {'object': 'list', 'data': [{'object': 'ruling', 'oracle_id': 'wrong', 'source': 'wotc', 'published_at': '2026-01-01', 'comment': 'text'}], 'has_more': False}, {'object': 'list', 'data': []} ])
def test_invalid_rulings_never_write_knowledge_or_cache(tmp_path, sources, bad):
    _, raw, _ = sources
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session, httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=bad))) as client:
        repo = Repository(session)
        with pytest.raises(ValueError):
            KnowledgeIngestor(repo, client).sync_payload(raw)
        assert repo.list_card_knowledge() == [] and repo.list_cards() == []


def test_artifact_tamper_never_leaves_a_validated_scratch(sources):
    database, raw, args = sources
    with corpus.readonly(database) as conn:
        corpus.prepare(conn, args)
    with gzip.open(args.out, 'rt') as stream:
        header, patch = [json.loads(line) for line in stream]
    patch['profile']['card_data']['oracle_text'] = 'invented facts'
    patch['after_profile_sha256'] = canonical_hash(patch['profile'])
    with gzip.open(args.out, 'wt') as stream:
        stream.write(json.dumps(header) + '\n' + json.dumps(patch) + '\n')
    scratch = database.parent / 'scratch.db'
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='non-owned'):
        corpus.validate_artifact(conn, args.out, scratch)
    assert not scratch.exists()


def test_tags_and_independent_metadata_versions_preserved_by_default(sources):
    database, _, args = sources
    with sqlite3.connect(database) as conn:
        profile = json.loads(conn.execute('SELECT profiles_json FROM cardknowledge').fetchone()[0])
        profile.update({'tactical_tags': ['metadata-agent-role'], 'tactical_provenance': {'version': 'independent-v9'}})
        conn.execute('UPDATE cardknowledge SET profiles_json=?', (json.dumps(profile),))
    with corpus.readonly(database) as conn:
        corpus.prepare(conn, args)
        result = corpus.validate_artifact(conn, args.out, database.parent / 'scratch.db')
    with corpus.readonly(database.parent / 'scratch.db') as conn:
        after = json.loads(conn.execute('SELECT profiles_json FROM cardknowledge').fetchone()[0])
    assert after['tactical_tags'] == ['metadata-agent-role']
    assert after['tactical_provenance'] == {'version': 'independent-v9'}
    assert result['validated_import_rows'] == 1


def test_changed_live_snapshot_rejects_import_instead_of_clobbering(sources):
    database, _, args = sources
    with corpus.readonly(database) as conn:
        corpus.prepare(conn, args)
    with sqlite3.connect(database) as conn:
        conn.execute('UPDATE cardknowledge SET play_value=9.5')
    scratch = database.parent / 'scratch.db'
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='different canonical snapshot'):
        corpus.validate_artifact(conn, args.out, scratch)
    assert not scratch.exists()


def test_limit_is_actual_examined_record_count_and_resume_is_bounded(sources):
    database, raw, args = sources
    second = {**raw, 'id': 'printing2', 'oracle_id': 'oracle2', 'name': 'Second'}
    engine = create_engine(f'sqlite:///{database}')
    with Session(engine) as session:
        import_cards(Repository(session), [second], {'source': 'scryfall'})
    engine.dispose()
    with gzip.open(args.cards, 'wt') as stream:
        stream.write(json.dumps(raw) + '\n' + json.dumps(second) + '\n')
    args.cards_sha256 = corpus.file_hash(args.cards)
    with corpus.readonly(database) as conn:
        first = corpus.prepare(conn, args)
        args.out = args.out.with_name('bounded-second.jsonl.gz')
        second_run = corpus.prepare(conn, args)
    assert first['processed_this_run'] == 1 and first['remaining'] == 1
    assert second_run['processed_this_run'] == 1 and second_run['remaining'] == 0
    assert second_run['patches'] == 2


def test_tag_refresh_requires_matching_implementation_pin(sources):
    database, _, args = sources
    args.refresh_tags_sha256 = 'not-the-current-implementation'
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='Tag implementation hash mismatch'):
        corpus.prepare(conn, args)


def test_named_endpoint_throttle_and_429_floor(monkeypatch, sources):
    _, raw, _ = sources
    sleeps = []
    monkeypatch.setattr('knowledge.ingest.time.sleep', sleeps.append)
    monkeypatch.setattr('knowledge.ingest.time.monotonic', lambda: 1)
    replies = iter([httpx.Response(429, headers={'Retry-After': '0'}), httpx.Response(200, json=raw)])
    with httpx.Client(transport=httpx.MockTransport(lambda request: next(replies))) as client:
        ingestor = KnowledgeIngestor(None, client)
        ingestor._last_request = 1
        assert ingestor._get('https://api.scryfall.com/cards/named')['name'] == raw['name']
    assert sleeps == [0.5, 30.0]


def test_name_collision_admission_is_not_mislabeled_nonplayable(sources):
    database, raw, _ = sources
    variant = {**raw, 'id': 'variant-printing', 'oracle_id': 'variant-oracle'}
    engine = create_engine(f'sqlite:///{database}')
    with Session(engine) as session:
        import_cards(Repository(session), [variant], {'source': 'scryfall'})
    engine.dispose()
    with corpus.readonly(database) as conn:
        report = corpus.audit(conn)
    assert report['totals']['canonical_identity'] == 2
    assert report['totals']['playable_but_not_admissible'] == 1
    assert report['totals']['canonical_not_admissible'] == 1
    assert report['totals']['nonplayable'] == 0


def test_nested_metadata_absence_and_staleness_are_separate_from_rulings(sources):
    database, raw, _ = sources
    metadata = {'schema_version': 1, 'extractor_version': 'canonical-tactical-surface-v1', 'provenance': {'input_sha256': canonical_hash(raw)}}
    assert corpus.mechanic_status({}, canonical_hash(raw)) == 'missing'
    assert corpus.mechanic_status({'mechanic_metadata': metadata}, canonical_hash(raw)) == 'current_input_version_not_semantics'
    assert corpus.mechanic_status({'mechanic_metadata': metadata}, 'changed-input') == 'stale_input'
    assert corpus.mechanic_status({'mechanic_metadata': {**metadata, 'schema_version': 0}}, canonical_hash(raw)) == 'stale_version'
    with corpus.readonly(database) as conn:
        before = corpus.audit(conn)
    with sqlite3.connect(database) as conn:
        profile = json.loads(conn.execute('SELECT profiles_json FROM cardknowledge').fetchone()[0])
        profile['mechanic_metadata'] = metadata
        conn.execute('UPDATE cardknowledge SET profiles_json=?', (json.dumps(profile),))
    with corpus.readonly(database) as conn:
        after = corpus.audit(conn)
    assert before['cards'][0]['rulings_status'] == after['cards'][0]['rulings_status'] == 'pending'
    assert after['totals']['mechanic_metadata_current_input_version_not_semantics'] == 1


def test_default_audit_and_prepare_never_call_additive_metadata_wrapper(monkeypatch, sources):
    import card_data.tactical
    monkeypatch.setattr(card_data.tactical, 'canonical_tactical_tags', lambda *a: pytest.fail('Unbounded nested extraction'))
    database, _, args = sources
    with sqlite3.connect(database) as conn:
        profile = json.loads(conn.execute('SELECT profiles_json FROM cardknowledge').fetchone()[0])
        profile.pop('mechanic_metadata', None)
        conn.execute('UPDATE cardknowledge SET profiles_json=?', (json.dumps(profile),))
    with corpus.readonly(database) as conn:
        corpus.audit(conn)
        corpus.prepare(conn, args)
    with gzip.open(args.out, 'rt') as stream:
        next(stream)
        profile = json.loads(next(stream))['profile']
    assert 'mechanic_metadata' not in profile


def test_reviewed_b_materialization_is_explicit_and_bounded(sources):
    module = pytest.importorskip('knowledge.mechanic_metadata')
    database, raw, args = sources
    with sqlite3.connect(database) as conn:
        profile = json.loads(conn.execute('SELECT profiles_json FROM cardknowledge').fetchone()[0])
        profile.pop('mechanic_metadata', None)
        conn.execute('UPDATE cardknowledge SET profiles_json=?', (json.dumps(profile),))
    args.materialize_mechanics_version = 'canonical-tactical-surface-v1'
    args.limit = 501
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='bounded to 500'):
        corpus.prepare(conn, args)
    args.limit = 1
    with corpus.readonly(database) as conn:
        result = corpus.prepare(conn, args)
        validated = corpus.validate_artifact(conn, args.out, database.parent / 'scratch.db')
    assert result['processed_this_run'] == 1 and validated['validated_import_rows'] == 1
    with gzip.open(args.out, 'rt') as stream:
        next(stream)
        profile = json.loads(next(stream))['profile']
    assert profile['mechanic_metadata'] == module.mechanic_metadata(raw)
    assert profile['mechanic_metadata']['provenance']['verification'] == 'not_performed'
    assert profile['rulings_verified'] is True


@pytest.mark.parametrize('kind', ['file', 'symlink', 'broken_symlink', 'part'])
def test_json_publication_refuses_existing_outputs_and_symlinks(tmp_path, kind):
    source = tmp_path / 'source-archive.json'
    source.write_text('preserve source bytes')
    out = tmp_path / 'report.json'
    if kind == 'file':
        out.write_text('preserve report')
    elif kind == 'symlink':
        out.symlink_to(source)
    elif kind == 'broken_symlink':
        out.symlink_to(tmp_path / 'missing-target')
    else:
        out.with_name(out.name + '.part').write_text('preserve unfinished work')
    with pytest.raises(FileExistsError):
        corpus.publish_json(out, {'replacement': True})
    assert source.read_text() == 'preserve source bytes'
    if kind == 'file':
        assert out.read_text() == 'preserve report'
    if kind == 'part':
        assert out.with_name(out.name + '.part').read_text() == 'preserve unfinished work'


def test_existing_summary_blocks_prepare_before_checkpoint_changes(sources):
    database, _, args = sources
    summary = args.out.with_suffix(args.out.suffix + '.summary.json')
    summary.write_text('unrelated report')
    with corpus.readonly(database) as conn, pytest.raises(FileExistsError):
        corpus.prepare(conn, args)
    assert not args.state.exists() and not args.out.exists()
    assert summary.read_text() == 'unrelated report'


@pytest.mark.parametrize('collision', ['archive', 'manifest', 'part', 'symlink'])
def test_fetch_rulings_does_not_replace_existing_sources(monkeypatch, tmp_path, collision):
    archive = tmp_path / 'rulings-test.jsonl.gz'
    path = archive if collision in {'archive', 'symlink'} else archive.with_name(archive.name + ('.manifest.json' if collision == 'manifest' else '.part'))
    other = tmp_path / 'other-source'
    other.write_bytes(b'public source evidence')
    if collision == 'symlink':
        path.symlink_to(other)
    else:
        path.write_bytes(b'original')
    requests = []
    def handle(request):
        requests.append(str(request.url))
        assert request.url.host == 'api.scryfall.com'
        return httpx.Response(200, json={'type': 'rulings', 'updated_at': '2026-10-05T09:00:00Z', 'jsonl_download_uri': 'https://data.scryfall.io/rulings-test.jsonl.gz'})
    client = httpx.Client(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(corpus.httpx, 'Client', lambda **kwargs: client)
    with pytest.raises(FileExistsError):
        corpus.fetch_rulings(tmp_path)
    assert len(requests) == 1
    assert other.read_bytes() == b'public source evidence'
    if collision != 'symlink':
        assert path.read_bytes() == b'original'


def test_atomic_publish_collision_preserves_other_writer(monkeypatch, tmp_path):
    out = tmp_path / 'report.json'
    def concurrent_link(source, target):
        target.write_text('other writer won')
        raise FileExistsError('collision')
    monkeypatch.setattr(corpus.os, 'link', concurrent_link)
    with pytest.raises(FileExistsError):
        corpus.publish_json(out, {'our_data': True})
    assert out.read_text() == 'other writer won'
    assert not out.with_name(out.name + '.part').exists()


def test_audit_version_migration_is_explicit_and_keeps_old_config(sources):
    database, _, args = sources
    with corpus.readonly(database) as conn:
        corpus.prepare(conn, args)
    with sqlite3.connect(args.state) as state:
        config = json.loads(state.execute('SELECT json FROM config').fetchone()[0])
        config['audit_tags_implementation_sha256'] = 'old-audit-only-version'
        state.execute('UPDATE config SET json=?', (json.dumps(config, sort_keys=True),))
    args.out = args.out.with_name('resume-version.jsonl.gz')
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='Resume inputs changed'):
        corpus.prepare(conn, args)
    args.resume_audit_version_change = True
    with corpus.readonly(database) as conn:
        result = corpus.prepare(conn, args)
    assert result['processed_this_run'] == 0
    with sqlite3.connect(args.state) as state:
        old = json.loads(state.execute('SELECT json FROM config_history').fetchone()[0])
    assert old['audit_tags_implementation_sha256'] == 'old-audit-only-version'


def test_reused_validation_checks_preconditions_and_replay_is_idempotent(sources):
    database, _, args = sources
    with corpus.readonly(database) as conn:
        result = corpus.prepare(conn, args)
        snapshot = result['provenance']['snapshot']
        scratch = database.parent / 'validation.db'
        first = corpus.validate_artifact(conn, args.out, scratch, snapshot=snapshot, full_audit=False)
        replay = corpus.validate_artifact(conn, args.out, scratch, reuse=True, snapshot=snapshot, full_audit=False)
    assert first['validated_import_rows'] == replay['validated_import_rows'] == 1
    assert replay['stored_row_hashes_verified']


def test_writable_sqlite_symlink_is_rejected(tmp_path):
    original = tmp_path / 'original.db'
    sqlite3.connect(original).close()
    link = tmp_path / 'checkpoint.db'
    link.symlink_to(original)
    with pytest.raises(ValueError, match='symlinks'):
        corpus.local_path(link)


def test_campaign_seeds_resumed_checkpoint_and_publishes_bounded_deltas(sources):
    database, raw, args = sources
    second = {**raw, 'id': 'printing2', 'oracle_id': 'oracle2', 'name': 'Second'}
    engine = create_engine(f'sqlite:///{database}')
    with Session(engine) as session:
        import_cards(Repository(session), [second], {'source': 'scryfall'})
    engine.dispose()
    with gzip.open(args.cards, 'wt') as stream:
        stream.write(json.dumps(raw) + '\n' + json.dumps(second) + '\n')
    args.cards_sha256 = corpus.file_hash(args.cards)
    with corpus.readonly(database) as conn:
        corpus.prepare(conn, args)
    args.seed_artifact = args.out
    args.seed_artifact_sha256 = corpus.file_hash(args.out)
    args.database = database
    args.out = database.parent / 'campaign'
    args.scratch = database.parent / 'campaign-validation.db'
    args.resume_campaign = False
    args.refresh_tags_sha256 = args.materialize_mechanics_version = args.card_refresh = args.card_refresh_sha256 = None
    with corpus.readonly(database) as conn:
        corpus.campaign(conn, args)
    final = json.loads((args.out / 'campaign-summary.json').read_text())
    assert final['processed_unique'] == final['validated_unique'] == 2
    assert final['outstanding_unprocessed'] == final['refused'] == final['live_imported_rows'] == 0
    batches = list(args.out.glob('batch-*.jsonl.gz'))
    assert len(batches) == 1
    with gzip.open(batches[0], 'rt') as stream:
        assert len(list(stream)) == 2  # manifest plus one newly processed row
    with corpus.readonly(database) as conn, pytest.raises(FileExistsError):
        corpus.campaign(conn, args)


@pytest.fixture
def campaign_sources(sources):
    database, raw, args = sources
    second = {**raw, 'id': 'printing2', 'oracle_id': 'oracle2', 'name': 'Second'}
    engine = create_engine(f'sqlite:///{database}')
    with Session(engine) as session:
        import_cards(Repository(session), [second], {'source': 'scryfall'})
    engine.dispose()
    with gzip.open(args.cards, 'wt') as stream:
        stream.write(json.dumps(raw) + '\n' + json.dumps(second) + '\n')
    args.cards_sha256 = corpus.file_hash(args.cards)
    with corpus.readonly(database) as conn:
        corpus.prepare(conn, args)
    args.seed_artifact = args.out
    args.seed_artifact_sha256 = corpus.file_hash(args.out)
    args.database = database
    args.out = database.parent / 'campaign'
    args.scratch = database.parent / 'campaign-validation.db'
    args.resume_campaign = False
    args.refresh_tags_sha256 = args.materialize_mechanics_version = args.card_refresh = args.card_refresh_sha256 = None
    return database, args


class SimulatedCampaignCrash(BaseException):
    pass


@pytest.mark.parametrize('boundary', ['after_config', 'after_baseline', 'before_seed_receipt', 'after_seed_receipt', 'before_batch_receipt', 'after_batch_receipt', 'after_batch_summary'])
def test_campaign_recovers_interrupted_publication_without_replacing_evidence(campaign_sources, monkeypatch, boundary):
    database, args = campaign_sources
    before = corpus.file_hash(database)
    original = corpus.publish_json
    names = {'config': 'run-config.json', 'baseline': 'baseline-readiness.json', 'seed_receipt': 'seed-validation.json',
             'batch_receipt': 'batch-00001.jsonl.gz.validated.json', 'batch_summary': 'batch-00001.jsonl.gz.summary.json'}
    when, label = boundary.split('_', 1)
    def crash(path, value):
        if Path(path).name == names[label] and when == 'before':
            raise SimulatedCampaignCrash(boundary)
        original(path, value)
        if Path(path).name == names[label] and when == 'after':
            raise SimulatedCampaignCrash(boundary)
    monkeypatch.setattr(corpus, 'publish_json', crash)
    with corpus.readonly(database) as conn, pytest.raises(SimulatedCampaignCrash):
        corpus.campaign(conn, args)
    preserved = {path: path.read_bytes() for path in args.out.iterdir() if path.is_file()}
    monkeypatch.setattr(corpus, 'publish_json', original)
    args.resume_campaign = True
    with corpus.readonly(database) as conn:
        corpus.campaign(conn, args)
    assert all(path.read_bytes() == content for path, content in preserved.items())
    assert (args.out / 'baseline-readiness.json').is_file()
    assert (args.out / 'seed-validation.json').is_file()
    final = json.loads((args.out / 'campaign-summary.json').read_text())
    assert final['validated_unique'] == final['all_row_full_profile_equality_verified'] == 2
    assert final['delivered_artifact_checkpoint_profile_rows_verified'] == 2
    assert corpus.file_hash(database) == before


@pytest.mark.parametrize('kind', ['empty', 'foreign', 'foreign_owner'])
def test_resume_refuses_unowned_or_foreign_scratch_without_writes(campaign_sources, monkeypatch, kind):
    database, args = campaign_sources
    original = corpus.publish_json
    def crash(path, value):
        original(path, value)
        if Path(path).name == 'run-config.json':
            raise SimulatedCampaignCrash()
    monkeypatch.setattr(corpus, 'publish_json', crash)
    with corpus.readonly(database) as conn, pytest.raises(SimulatedCampaignCrash):
        corpus.campaign(conn, args)
    with sqlite3.connect(args.scratch) as scratch:
        if kind == 'foreign':
            scratch.execute('CREATE TABLE unrelated (value TEXT)')
            scratch.execute("INSERT INTO unrelated VALUES ('must retain')")
        if kind == 'foreign_owner':
            scratch.execute('CREATE TABLE corpus_campaign_owner (json TEXT)')
            scratch.execute('INSERT INTO corpus_campaign_owner VALUES (?)', (json.dumps({'foreign': True}),))
    before = args.scratch.read_bytes()
    monkeypatch.setattr(corpus, 'publish_json', original)
    args.resume_campaign = True
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='ownership|different campaign'):
        corpus.campaign(conn, args)
    assert args.scratch.read_bytes() == before


@pytest.mark.parametrize('target', ['scratch_profile', 'checkpoint_payload', 'artifact', 'receipt'])
def test_delivered_equality_rejects_tampering_before_resume_can_repair(campaign_sources, monkeypatch, target):
    database, args = campaign_sources
    original = corpus.publish_json
    def crash(path, value):
        original(path, value)
        if Path(path).name == 'batch-00001.jsonl.gz.summary.json':
            raise SimulatedCampaignCrash()
    monkeypatch.setattr(corpus, 'publish_json', crash)
    with corpus.readonly(database) as conn, pytest.raises(SimulatedCampaignCrash):
        corpus.campaign(conn, args)
    if target == 'scratch_profile':
        with sqlite3.connect(args.scratch) as scratch:
            row_id, encoded = scratch.execute('SELECT id,profiles_json FROM cardknowledge ORDER BY id LIMIT 1').fetchone()
            profile = json.loads(encoded)
            profile['rulings_provenance']['updated_at'] = 'tampered but generic audit still verified'
            scratch.execute('UPDATE cardknowledge SET profiles_json=? WHERE id=?', (json.dumps(profile), row_id))
    elif target == 'checkpoint_payload':
        with sqlite3.connect(args.state) as state:
            row_id, encoded = state.execute('SELECT id,patch FROM completed ORDER BY id LIMIT 1').fetchone()
            patch = json.loads(encoded)
            patch['profile']['unexpected_metadata'] = 'tampered'
            state.execute('UPDATE completed SET patch=? WHERE id=?', (json.dumps(patch), row_id))
    elif target == 'artifact':
        with (args.out / 'batch-00001.jsonl.gz').open('ab') as stream:
            stream.write(b'tampered')
    else:
        receipt = args.out / 'seed-validation.json'
        value = json.loads(receipt.read_text())
        value['artifact_sha256'] = 'tampered'
        receipt.write_text(json.dumps(value))
    scratch_before = args.scratch.read_bytes()
    monkeypatch.setattr(corpus, 'publish_json', original)
    args.resume_campaign = True
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='mismatch|no longer match'):
        corpus.campaign(conn, args)
    assert args.scratch.read_bytes() == scratch_before
    assert not (args.out / 'campaign-summary.json').exists()


def test_missing_committed_scratch_is_not_silently_recreated(campaign_sources, monkeypatch):
    database, args = campaign_sources
    original = corpus.publish_json
    def crash(path, value):
        original(path, value)
        if Path(path).name == 'seed-validation.json':
            raise SimulatedCampaignCrash()
    monkeypatch.setattr(corpus, 'publish_json', crash)
    with corpus.readonly(database) as conn, pytest.raises(SimulatedCampaignCrash):
        corpus.campaign(conn, args)
    args.scratch.rename(args.scratch.with_suffix('.preserved'))
    monkeypatch.setattr(corpus, 'publish_json', original)
    args.resume_campaign = True
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='scratch is missing'):
        corpus.campaign(conn, args)
    assert not args.scratch.exists()


def test_final_all_profile_check_catches_tamper_that_generic_readiness_misses(campaign_sources, monkeypatch):
    database, args = campaign_sources
    original = corpus.publish_json
    def tamper(path, value):
        original(path, value)
        if Path(path).name == 'batch-00001.jsonl.gz.summary.json':
            with sqlite3.connect(args.scratch) as scratch:
                row_id, encoded = scratch.execute('SELECT id,profiles_json FROM cardknowledge ORDER BY id LIMIT 1').fetchone()
                profile = json.loads(encoded)
                profile['card_data_provenance']['updated_at'] = 'undetected-by-generic-readiness'
                scratch.execute('UPDATE cardknowledge SET profiles_json=? WHERE id=?', (json.dumps(profile), row_id))
    monkeypatch.setattr(corpus, 'publish_json', tamper)
    with corpus.readonly(database) as conn, pytest.raises(ValueError, match='full-profile'):
        corpus.campaign(conn, args)
    assert not (args.out / 'campaign-summary.json').exists()
