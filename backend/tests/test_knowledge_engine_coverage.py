"""Synthetic isolated fixtures exercise reporting, not card or effect truth."""
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from scripts import knowledge_engine_coverage as coverage


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'offline.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE cardknowledge (id INTEGER PRIMARY KEY, name TEXT, scryfall_id TEXT, oracle_source TEXT, profiles_json TEXT)')
    return path


def add(path, text='Draw a card.', **changes):
    raw = {'object': 'card', 'id': 'fixture-printing', 'oracle_id': 'fixture-oracle', 'name': 'Coverage fixture',
           'type_line': 'Sorcery', 'oracle_text': text, 'layout': 'normal', 'mana_cost': '{U}',
           'cmc': 1, 'color_identity': ['U'], 'keywords': [], 'legalities': {}}
    raw.update(changes)
    profile = {'oracle_id': 'fixture-oracle', 'card_data': raw}
    with sqlite3.connect(path) as conn:
        conn.execute('INSERT INTO cardknowledge(name,scryfall_id,oracle_source,profiles_json) VALUES (?,?,?,?)',
                     ('Coverage fixture', 'fixture-printing', 'scryfall', json.dumps(profile)))


def report(path, **kwargs):
    with coverage.closing(coverage.corpus.readonly(path)) as conn:
        return coverage.coverage_report(conn, **kwargs)


def test_empty_is_deterministic_and_never_certified(database):
    one, two = report(database), report(database)
    assert one == two
    assert one['totals']['rows'] == 0
    assert one['mechanics']['supported']['cards'] is None
    assert one['rules_support_certified'] is False
    assert one['trained_competence'] == 'unknown'


def test_real_classifier_gaps_faces_and_unknown_not_supported(database):
    add(database, 'Draw a card.', card_faces=[{'name': 'Face fixture', 'type_line': 'Creature', 'oracle_text': 'Morph {2}.'}])
    result = report(database)
    assert result['totals']['known_gap_cards'] == 1
    assert result['mechanics']['unsupported']['morph']['cards'] == 1
    example = result['mechanics']['unsupported']['morph']['representatives'][0]
    assert example['oracle_id'] == 'fixture-oracle' and len(example['card_data_sha256']) == 64
    assert result['mechanics']['unknown']['role_draw']['cards'] == 1
    assert result['metadata_states']['nested_missing'] == 1
    assert result['card_type_metadata_counts_not_semantic_support'] == {'creature': 1, 'sorcery': 1}


def test_no_gap_and_empty_text_never_positive(database):
    add(database, '')
    result = report(database)
    assert result['totals']['no_known_gap_not_certified_cards'] == 1
    assert result['mechanics']['supported']['cards'] is None
    assert result['metadata_states']['empty_or_missing_text_not_absence_of_abilities'] == 1


@pytest.mark.parametrize('payload,state', [('not-json', 'profile_malformed'), ('[]', 'profile_malformed'),
                                        ('{}', 'card_data_missing_or_malformed'), (None, 'profile_missing')])
def test_malformed_missing_profiles_are_unknown(database, payload, state):
    with sqlite3.connect(database) as conn:
        conn.execute('INSERT INTO cardknowledge(profiles_json) VALUES (?)', (payload,))
    result = report(database)
    assert result['totals']['unclassifiable_cards'] == 1
    assert result['metadata_states'][state] == 1
    assert result['totals']['no_known_gap_not_certified_cards'] == 0


@pytest.mark.parametrize('changes', [{'oracle_text': None}, {'card_faces': 'invalid'}, {'keywords': [3]}, {'type_line': []}])
def test_malformed_surface_never_classified(database, changes):
    add(database, **changes)
    assert report(database)['totals']['unclassifiable_cards'] == 1


def test_nested_stale_separate_and_representatives_bounded(database):
    for _ in range(4):
        add(database, 'Morph {2}.')
    with sqlite3.connect(database) as conn:
        value = json.loads(conn.execute('SELECT profiles_json FROM cardknowledge WHERE id=1').fetchone()[0])
        value['mechanic_metadata'] = {'schema_version': -1}
        conn.execute('UPDATE cardknowledge SET profiles_json=? WHERE id=1', (json.dumps(value),))
    result = report(database, examples=1)
    assert result['metadata_states']['nested_stale_version'] == 1
    group = result['mechanics']['unsupported']['morph']
    assert group['cards'] == 4 and len(group['representatives']) == 1
    assert report(database, examples=0)['mechanics']['unsupported']['morph']['representatives'] == []
    with pytest.raises(ValueError):
        report(database, examples=11)


@pytest.mark.parametrize('cap,value', [('MAX_ROWS', 0), ('MAX_PROFILE_BYTES', 8), ('MAX_TEXT_BYTES', 8), ('MAX_FACES', 0)])
def test_resource_bounds_no_source_mutation(database, monkeypatch, cap, value):
    add(database, 'Morph {2}.', card_faces=[{'name': 'Face fixture', 'oracle_text': 'Morph {2}.'}])
    before = database.read_bytes()
    monkeypatch.setattr(coverage, cap, value)
    with pytest.raises(ValueError, match='cap'):
        report(database)
    assert database.read_bytes() == before


def test_preflight_rejects_before_fetching_profile(database, monkeypatch):
    class Source:
        def execute(self, sql):
            assert sql.startswith('SELECT count(*)')
            return self
        def fetchone(self):
            return 1, coverage.MAX_PROFILE_BYTES + 1
    with pytest.raises(ValueError, match='before payload reads'):
        coverage.coverage_report(Source())


def test_cli_deterministic_readonly_digest_and_output_collisions(database, tmp_path, monkeypatch):
    add(database, 'Morph {2}.')
    before = database.read_bytes()
    sha = coverage.corpus.file_hash(database)
    def run(out, digest=sha):
        monkeypatch.setattr(sys, 'argv', ['coverage', '--database', str(database), '--database-sha256', digest, '--out', str(out)])
        coverage.main()
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    run(a)
    run(b)
    assert a.read_bytes() == b.read_bytes()
    with pytest.raises(FileExistsError):
        run(a)
    with pytest.raises(ValueError, match='digest'):
        run(tmp_path / 'bad.json', '0' * 64)
    assert not (tmp_path / 'bad.json').exists()
    assert database.read_bytes() == before
    with coverage.closing(coverage.corpus.readonly(database)) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('DELETE FROM cardknowledge')


def test_symlink_sidecars_nfs_and_database_size_refused(database, tmp_path, monkeypatch):
    link = tmp_path / 'link.sqlite3'
    link.symlink_to(database)
    with pytest.raises(ValueError, match='symlink'):
        coverage.input_path(link)
    sidecar = Path(str(database) + '-wal')
    sidecar.symlink_to(tmp_path / 'absent')
    with pytest.raises(ValueError, match='sidecar'):
        coverage.input_path(database)
    sidecar.unlink()
    monkeypatch.setattr(coverage, 'MAX_DATABASE_BYTES', 1)
    with pytest.raises(ValueError, match='byte cap'):
        coverage.input_path(database)
    def nfs(path):
        raise ValueError('NFS refused')
    monkeypatch.setattr(coverage.corpus, 'local_path', nfs)
    with pytest.raises(ValueError, match='NFS'):
        coverage.input_path(database)


@pytest.mark.parametrize('metadata,state', [(None, 'missing'), ([], 'invalid_shape'),
    ({'schema_version': coverage.SCHEMA_VERSION, 'extractor_version': coverage.EXTRACTOR_VERSION,
      'provenance': {'input_sha256': 'wrong'}}, 'stale_input')])
def test_nested_metadata_never_supplies_semantic_support(database, metadata, state):
    add(database)
    with sqlite3.connect(database) as conn:
        p = json.loads(conn.execute('SELECT profiles_json FROM cardknowledge').fetchone()[0])
        p['mechanic_metadata'] = metadata
        conn.execute('UPDATE cardknowledge SET profiles_json=?', (json.dumps(p),))
    result = report(database)
    assert result['metadata_states']['nested_' + state] == 1
    assert result['mechanics']['supported']['cards'] is None
    assert result['mechanics']['unknown']['role_draw']['cards'] == 1


def test_output_dangling_symlink_and_part_preserved(database, tmp_path, monkeypatch):
    add(database)
    out = tmp_path / 'report.json'
    out.symlink_to(tmp_path / 'missing')
    monkeypatch.setattr(sys, 'argv', ['coverage', '--database', str(database), '--database-sha256',
                                    coverage.corpus.file_hash(database), '--out', str(out)])
    with pytest.raises(FileExistsError):
        coverage.main()
    assert out.is_symlink()
    out.unlink()
    part = tmp_path / 'report.json.part'
    part.write_text('foreign provenance')
    with pytest.raises(FileExistsError):
        coverage.main()
    assert part.read_text() == 'foreign provenance'


def test_source_changed_refuses_report(database, tmp_path, monkeypatch):
    add(database)
    out = tmp_path / 'report.json'
    actual = coverage.corpus.file_hash(database)
    calls = 0
    original = coverage.corpus.file_hash
    def hashes(path):
        nonlocal calls
        if Path(path) == database:
            calls += 1
            return actual if calls == 1 else '0' * 64
        return original(path)
    monkeypatch.setattr(coverage.corpus, 'file_hash', hashes)
    monkeypatch.setattr(sys, 'argv', ['coverage', '--database', str(database), '--database-sha256', actual, '--out', str(out)])
    with pytest.raises(ValueError, match='changed'):
        coverage.main()
    assert not out.exists()
