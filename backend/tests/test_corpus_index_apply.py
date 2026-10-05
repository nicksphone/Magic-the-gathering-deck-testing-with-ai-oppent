"""Explicit offline targets only; no app lifespan, shared DB or source network."""
import gzip
import json
from pathlib import Path
import shutil
import sqlite3
import sys

import pytest
from sqlmodel import Session, create_engine

from scripts import corpus_knowledge_readiness as corpus
from scripts.sync_all_card_knowledge import import_cards
from persistence.repository import Repository
from tests.test_corpus_knowledge_readiness import sources


@pytest.fixture
def application(sources):
    database, raw, args = sources
    second = {**raw, 'id': 'printing2', 'oracle_id': 'oracle2', 'name': 'Second'}
    engine = create_engine(f'sqlite:///{database}')
    with Session(engine) as session:
        import_cards(Repository(session), [second], {'source': 'scryfall'})
    engine.dispose()
    with sqlite3.connect(database) as conn:
        conn.execute('CREATE TABLE game_probe (value TEXT)')
        conn.execute("INSERT INTO game_probe VALUES ('retain gameplay data')")
    with gzip.open(args.cards, 'wt') as stream:
        stream.write(json.dumps(raw) + '\n' + json.dumps(second) + '\n')
    args.cards_sha256 = corpus.file_hash(args.cards)
    args.batch_artifact = True
    artifacts = []
    with corpus.readonly(database) as source:
        for number in range(2):
            args.out = database.parent / f'artifact-{number}.jsonl.gz'
            prepared = corpus.prepare(source, args)
            receipt = corpus.validate_artifact(source, args.out, database.parent / 'validation.db',
                reuse=number > 0, snapshot=prepared['provenance']['snapshot'], full_audit=False)
            receipt_path = args.out.with_name(args.out.name + '.receipt.json')
            corpus.publish_json(receipt_path, receipt)
            artifacts.append({'artifact': str(args.out), 'sha256': corpus.file_hash(args.out),
                'validation_receipt': str(receipt_path), 'receipt_sha256': corpus.file_hash(receipt_path),
                'rows': 1, 'source_snapshot_sha256': receipt['source_snapshot_sha256']})
    args.database = database
    args.target = database.parent / 'offline-target.sqlite3'
    shutil.copy2(database, args.target)
    args.target_sha256 = corpus.file_hash(args.target)
    args.index = database.parent / 'index.json'
    corpus.publish_json(args.index, {'artifacts': artifacts, 'validated_unique_rows': 2, 'duplicate_rows': 0, 'live_imported_rows': 0})
    args.index_sha256 = corpus.file_hash(args.index)
    args.card_refresh = args.card_refresh_sha256 = None
    args.out = database.parent / 'application-report.json'
    return args


def apply(args):
    with corpus.readonly(args.database) as source:
        return corpus.apply_index(source, args)


def revise_index(args, mutate):
    value = json.loads(args.index.read_text())
    mutate(value)
    args.index.write_text(json.dumps(value))
    args.index_sha256 = corpus.file_hash(args.index)


def rewrite_artifact(args, position, mutate):
    index = json.loads(args.index.read_text())
    entry = index['artifacts'][position]
    artifact = Path(entry['artifact'])
    with gzip.open(artifact, 'rt') as stream:
        records = [json.loads(line) for line in stream]
    mutate(records)
    with gzip.open(artifact, 'wt') as stream:
        for record in records:
            stream.write(json.dumps(record) + '\n')
    entry['sha256'] = corpus.file_hash(artifact)
    receipt = Path(entry['validation_receipt'])
    value = json.loads(receipt.read_text())
    value['artifact_sha256'] = entry['sha256']
    receipt.write_text(json.dumps(value))
    entry['receipt_sha256'] = corpus.file_hash(receipt)
    args.index.write_text(json.dumps(index))
    args.index_sha256 = corpus.file_hash(args.index)


def test_apply_index_atomic_profiles_only_and_source_immutable(application):
    args = application
    before = corpus.file_hash(args.database)
    with corpus.readonly(args.database) as conn:
        original = [dict(row) for row in conn.execute('SELECT * FROM cardknowledge ORDER BY id')]
        schema = list(conn.execute('SELECT sql FROM sqlite_master ORDER BY name'))
    result = apply(args)
    assert result['applied_rows'] == 2 and result['artifacts_verified'] == 2
    assert result['sqlite_transaction_committed'] and result['complete_row_hashes_verified']
    assert result['cardcache_and_game_table_writes'] == result['live_imported_rows'] == 0
    assert result['trained_competence'] == 'unknown'
    assert corpus.file_hash(args.database) == before
    with corpus.readonly(args.target) as conn:
        after = [dict(row) for row in conn.execute('SELECT * FROM cardknowledge ORDER BY id')]
        assert [tuple(row) for row in conn.execute('SELECT sql FROM sqlite_master ORDER BY name')] == [tuple(row) for row in schema]
        assert conn.execute('SELECT value FROM game_probe').fetchone()[0] == 'retain gameplay data'
        assert conn.execute('SELECT count(*) FROM cardcache').fetchone()[0] == 0
    for old, new in zip(original, after, strict=True):
        assert {key: value for key, value in old.items() if key != 'profiles_json'} == {key: value for key, value in new.items() if key != 'profiles_json'}
        assert json.loads(old['profiles_json'])['tactical_tags'] == json.loads(new['profiles_json'])['tactical_tags']
        assert json.loads(new['profiles_json'])['rulings_verified']
    with pytest.raises(ValueError, match='exact digest-pinned'):
        apply(args)


@pytest.mark.parametrize('kind', ['same', 'hardlink', 'symlink', 'parent_symlink', 'missing', 'changed', 'foreign_game', 'sidecar', 'broken_journal', 'live_name', 'nfs'])
def test_refuses_unsafe_or_changed_targets_without_writes(application, monkeypatch, kind):
    args = application
    protected = args.target
    before = protected.read_bytes()
    if kind == 'same':
        args.target = args.database
    elif kind in {'hardlink', 'symlink'}:
        path = protected.with_name('alias.sqlite3')
        if kind == 'hardlink':
            path.hardlink_to(protected)
        else:
            path.symlink_to(protected)
        args.target = path
    elif kind == 'parent_symlink':
        alias = protected.parent / 'alias-dir'
        alias.symlink_to(protected.parent, target_is_directory=True)
        args.target = alias / protected.name
    elif kind == 'missing':
        args.target = protected.with_name('missing.sqlite3')
    elif kind in {'changed', 'foreign_game'}:
        with sqlite3.connect(protected) as conn:
            conn.execute("UPDATE cardknowledge SET play_value=99" if kind == 'changed' else "UPDATE game_probe SET value='foreign'")
        before = protected.read_bytes()
        args.target_sha256 = corpus.file_hash(protected)
    elif kind == 'sidecar':
        Path(str(protected) + '-wal').write_bytes(b'unrelated checkpoint evidence')
    elif kind == 'broken_journal':
        Path(str(protected) + '-journal').symlink_to(protected.parent / 'foreign-missing-file')
    elif kind == 'live_name':
        args.target = protected.with_name('mtg_lab.db')
        shutil.copy2(protected, args.target)
    else:
        import subprocess
        original = subprocess.check_output
        monkeypatch.setattr(subprocess, 'check_output', lambda command, **kw: 'nfs\n' if str(protected) in command else original(command, **kw))
    with pytest.raises(ValueError):
        apply(args)
    assert protected.read_bytes() == before


@pytest.mark.parametrize('kind', ['index_digest', 'artifact_digest', 'receipt_digest', 'receipt_committed', 'snapshot', 'before_profile', 'after_profile', 'duplicate', 'missing_row', 'tags', 'nonowned', 'provenance'])
def test_bad_index_or_payload_cannot_partially_apply(application, kind):
    args = application
    before = args.target.read_bytes()
    if kind == 'index_digest':
        args.index_sha256 = 'wrong'
    elif kind in {'artifact_digest', 'receipt_digest', 'snapshot', 'missing_row'}:
        def mutate(value):
            if kind == 'missing_row':
                value['artifacts'].pop()
            else:
                value['artifacts'][1][{'artifact_digest': 'sha256', 'receipt_digest': 'receipt_sha256', 'snapshot': 'source_snapshot_sha256'}[kind]] = 'wrong'
        revise_index(args, mutate)
    elif kind == 'receipt_committed':
        index = json.loads(args.index.read_text())
        entry = index['artifacts'][1]
        receipt = Path(entry['validation_receipt'])
        value = json.loads(receipt.read_text())
        value['sqlite_transaction_committed'] = False
        receipt.write_text(json.dumps(value))
        revise_index(args, lambda value: value['artifacts'][1].update(receipt_sha256=corpus.file_hash(receipt)))
    else:
        def mutate(records):
            patch = records[1]
            if kind == 'before_profile':
                patch['before_profile_sha256'] = 'wrong'
            elif kind == 'after_profile':
                patch['after_profile_sha256'] = 'wrong'
            elif kind == 'duplicate':
                with gzip.open(json.loads(args.index.read_text())['artifacts'][0]['artifact'], 'rt') as stream:
                    next(stream)
                    records[1] = json.loads(next(stream))
            else:
                if kind == 'tags':
                    patch['profile']['tactical_tags'] = ['invented']
                elif kind == 'nonowned':
                    patch['profile']['hand_authored_numeric_score'] = 99
                else:
                    patch['profile']['rulings_provenance']['sha256'] = 'wrong'
                patch['after_profile_sha256'] = corpus.canonical_hash(patch['profile'])
        rewrite_artifact(args, 1, mutate)
    with pytest.raises(ValueError):
        apply(args)
    assert args.target.read_bytes() == before


def test_mid_transaction_failure_rolls_back_all_rows(application, monkeypatch):
    args = application
    before = args.target.read_bytes()
    original = corpus.canonical_hash
    seen = 0
    def fail(value):
        nonlocal seen
        if isinstance(value, dict) and 'profiles_json' in value and json.loads(value['profiles_json']).get('rulings_verified'):
            seen += 1
            if seen == 3:  # two staged rows, then first post-update row
                raise RuntimeError('injected failure after all SQL updates')
        return original(value)
    monkeypatch.setattr(corpus, 'canonical_hash', fail)
    with pytest.raises(RuntimeError, match='injected failure'):
        apply(args)
    assert args.target.read_bytes() == before
    assert not Path(str(args.target) + '-journal').exists()


@pytest.mark.parametrize('statement', ["UPDATE game_probe SET value='bad'", 'UPDATE cardknowledge SET play_value=99', "UPDATE cardknowledge SET profiles_json='{}' WHERE id!=NEW.id", "INSERT INTO cardcache (name) VALUES ('bad')"])
def test_trigger_side_effects_are_denied_and_transaction_rolled_back(application, statement):
    args = application
    with sqlite3.connect(args.database) as conn:
        conn.execute(f'CREATE TRIGGER forbidden AFTER UPDATE OF profiles_json ON cardknowledge BEGIN {statement}; END')
    shutil.copy2(args.database, args.target)
    args.target_sha256 = corpus.file_hash(args.target)
    before = args.target.read_bytes()
    with pytest.raises(sqlite3.DatabaseError):
        apply(args)
    assert args.target.read_bytes() == before


def test_existing_report_and_part_collisions_refuse_before_target_writes(application):
    args = application
    before = args.target.read_bytes()
    args.out.write_text('retain other report')
    with pytest.raises(FileExistsError):
        apply(args)
    args.out.unlink()
    part = args.out.with_name(args.out.name + '.part')
    part.symlink_to(args.database)
    with pytest.raises(FileExistsError):
        apply(args)
    assert args.target.read_bytes() == before


def test_cli_requires_explicit_target_and_pin(application, monkeypatch):
    args = application
    monkeypatch.setattr(sys, 'argv', ['corpus', 'apply-index', '--database', str(args.database), '--out', str(args.out)])
    with pytest.raises(SystemExit):
        corpus.main()


def test_cli_reports_committed_but_unpublished_result_truthfully(application, monkeypatch):
    args = application
    monkeypatch.setattr(sys, 'argv', ['corpus', 'apply-index', '--database', str(args.database), '--target', str(args.target),
        '--target-sha256', args.target_sha256, '--index', str(args.index), '--index-sha256', args.index_sha256, '--out', str(args.out)])
    monkeypatch.setattr(corpus, 'publish_json', lambda *a: (_ for _ in ()).throw(OSError('report filesystem failure')))
    with pytest.raises(RuntimeError, match='transaction committed but report publication failed'):
        corpus.main()
    with corpus.readonly(args.target) as target:
        assert all(json.loads(row[0])['rulings_verified'] for row in target.execute('SELECT profiles_json FROM cardknowledge'))


def test_target_change_between_preflight_and_open_refuses_without_repair(application, monkeypatch):
    args = application
    original = sqlite3.connect
    def concurrent_change(database, *a, **kw):
        if str(database) == args.target.as_uri() + '?mode=rw':
            with original(args.target) as competing:
                competing.execute('UPDATE cardknowledge SET play_value=88')
        return original(database, *a, **kw)
    monkeypatch.setattr(corpus.sqlite3, 'connect', concurrent_change)
    with pytest.raises(ValueError, match='changed before exclusive transaction'):
        apply(args)
    with corpus.readonly(args.target) as target:
        assert all(row[0] == 88 and not json.loads(row[1]).get('rulings_verified') for row in target.execute('SELECT play_value,profiles_json FROM cardknowledge'))


def test_index_change_after_updates_rolls_back_before_commit(application, monkeypatch):
    args = application
    before = args.target.read_bytes()
    original = corpus.canonical_hash
    seen = 0
    def mutate_index(value):
        nonlocal seen
        if isinstance(value, dict) and 'profiles_json' in value and json.loads(value['profiles_json']).get('rulings_verified'):
            seen += 1
            if seen == 3:
                args.index.write_text(args.index.read_text() + ' ')
        return original(value)
    monkeypatch.setattr(corpus, 'canonical_hash', mutate_index)
    with pytest.raises(ValueError, match='changed during application'):
        apply(args)
    assert args.target.read_bytes() == before


def replace_compressed(application, payload):
    index = json.loads(application.index.read_text())
    entry = index['artifacts'][1]
    artifact = Path(entry['artifact'])
    artifact.write_bytes(payload)
    entry['sha256'] = corpus.file_hash(artifact)
    receipt = Path(entry['validation_receipt'])
    value = json.loads(receipt.read_text())
    value['artifact_sha256'] = entry['sha256']
    receipt.write_text(json.dumps(value))
    entry['receipt_sha256'] = corpus.file_hash(receipt)
    application.index.write_text(json.dumps(index))
    application.index_sha256 = corpus.file_hash(application.index)


@pytest.mark.parametrize('kind', ['index', 'receipt', 'compressed'])
def test_default_input_byte_caps_refuse_before_any_target_mutation(application, kind):
    args = application
    before = args.target.read_bytes()
    if kind == 'index':
        with args.index.open('wb') as stream:
            stream.truncate(corpus.MAX_INDEX_BYTES + 1)
        args.index_sha256 = corpus.file_hash(args.index)
    elif kind == 'receipt':
        index = json.loads(args.index.read_text())
        receipt = Path(index['artifacts'][1]['validation_receipt'])
        with receipt.open('wb') as stream:
            stream.truncate(corpus.MAX_RECEIPT_BYTES + 1)
        revise_index(args, lambda value: value['artifacts'][1].update(receipt_sha256=corpus.file_hash(receipt)))
    else:
        replace_compressed(args, b'')
        index = json.loads(args.index.read_text())
        artifact = Path(index['artifacts'][1]['artifact'])
        with artifact.open('wb') as stream:
            stream.truncate(corpus.MAX_COMPRESSED_ARTIFACT_BYTES + 1)
        digest = corpus.file_hash(artifact)
        receipt = Path(index['artifacts'][1]['validation_receipt'])
        value = json.loads(receipt.read_text())
        value['artifact_sha256'] = digest
        receipt.write_text(json.dumps(value))
        revise_index(args, lambda value: value['artifacts'][1].update(sha256=digest, receipt_sha256=corpus.file_hash(receipt)))
    with pytest.raises(ValueError, match='byte cap'):
        apply(args)
    assert args.target.read_bytes() == before


@pytest.mark.parametrize('kind', ['huge_manifest', 'huge_row', 'truncated_gzip', 'truncated_rows', 'extra_row', 'extra_member', 'artifact_total', 'aggregate_total', 'stage_total'])
def test_compressed_malicious_and_resource_exhaustion_inputs_do_not_mutate_target(application, monkeypatch, kind):
    args = application
    before = args.target.read_bytes()
    entry = json.loads(args.index.read_text())['artifacts'][1]
    data = Path(entry['artifact']).read_bytes()
    plain = gzip.decompress(data)
    manifest, row = plain.splitlines(keepends=True)
    if kind == 'huge_manifest':
        data = gzip.compress(b' ' * (corpus.MAX_ARTIFACT_LINE_BYTES + 1) + b'\n' + row)
    elif kind == 'huge_row':
        data = gzip.compress(manifest + b' ' * (corpus.MAX_ARTIFACT_LINE_BYTES + 1) + b'\n')
    elif kind == 'truncated_gzip':
        data = data[:-7]
    elif kind == 'truncated_rows':
        data = gzip.compress(manifest)
    elif kind == 'extra_row':
        data = gzip.compress(plain + b' ' * (corpus.MAX_ARTIFACT_LINE_BYTES + 1))
    elif kind == 'extra_member':
        data += gzip.compress(b' ' * (corpus.MAX_ARTIFACT_LINE_BYTES + 1))
    elif kind == 'artifact_total':
        monkeypatch.setattr(corpus, 'MAX_ARTIFACT_EXPANDED_BYTES', len(plain) - 1)
    elif kind == 'aggregate_total':
        first = json.loads(args.index.read_text())['artifacts'][0]
        total = len(gzip.decompress(Path(first['artifact']).read_bytes())) + len(plain)
        monkeypatch.setattr(corpus, 'MAX_TOTAL_EXPANDED_BYTES', total - 1)
    else:
        monkeypatch.setattr(corpus, 'MAX_STAGE_BYTES', 1)
    replace_compressed(args, data)
    with pytest.raises((ValueError, EOFError, gzip.BadGzipFile)):
        apply(args)
    assert args.target.read_bytes() == before


@pytest.mark.parametrize('kind', ['entries', 'source_rows', 'source_profile', 'self_claimed_rows'])
def test_independent_cardinality_and_source_caps(application, monkeypatch, kind):
    args = application
    before = args.target.read_bytes()
    if kind == 'entries':
        revise_index(args, lambda value: value.update(artifacts=[value['artifacts'][0]] * (corpus.MAX_INDEX_ENTRIES + 1)))
    elif kind == 'source_rows':
        monkeypatch.setattr(corpus, 'MAX_SOURCE_ROWS', 1)
    elif kind == 'source_profile':
        monkeypatch.setattr(corpus, 'MAX_SOURCE_PROFILE_BYTES', 1)
    else:
        revise_index(args, lambda value: value['artifacts'][0].update(rows=501))
    with pytest.raises(ValueError, match='cap|bounds'):
        apply(args)
    assert args.target.read_bytes() == before


def test_binary_readline_has_explicit_line_or_remaining_budget_bound(monkeypatch):
    data = gzip.compress(b'{}\n{}\n' + b'x' * 100000)
    original = corpus.gzip.open
    calls = []
    class CheckedStream:
        def __enter__(self):
            self.stream = original(__import__('io').BytesIO(data), 'rb')
            return self
        def __exit__(self, *args):
            self.stream.close()
        def readline(self, size):
            assert 0 < size <= corpus.MAX_ARTIFACT_LINE_BYTES + 1
            calls.append(('readline', size))
            return self.stream.readline(size)
        def read(self, size):
            assert size == 1
            calls.append(('read', size))
            return self.stream.read(size)
    monkeypatch.setattr(corpus.gzip, 'open', lambda *a, **kw: CheckedStream())
    with pytest.raises(ValueError, match='exceeds indexed row'):
        list(corpus.bounded_artifact_lines(data, 1, {'expanded': 0}))
    assert [name for name, _ in calls] == ['readline', 'readline', 'read']


@pytest.mark.parametrize('kind', ['packet', 'response'])
def test_refresh_evidence_is_bounded_before_legacy_validator(application, kind):
    args = application
    before = args.target.read_bytes()
    packet = args.database.parent / 'refresh-packet.json'
    if kind == 'packet':
        with packet.open('wb') as stream:
            stream.truncate(corpus.MAX_REFRESH_BYTES + 1)
    else:
        response = args.database.parent / 'refresh-response.json'
        with response.open('wb') as stream:
            stream.truncate(corpus.MAX_REFRESH_BYTES + 1)
        packet.write_text(json.dumps({'response_archive': str(response), 'provenance': {'archive_sha256': corpus.file_hash(response)}}))
    args.card_refresh = packet
    args.card_refresh_sha256 = corpus.file_hash(packet)
    with pytest.raises(ValueError, match='byte cap'):
        apply(args)
    assert args.target.read_bytes() == before
