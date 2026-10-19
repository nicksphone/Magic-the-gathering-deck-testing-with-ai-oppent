"""Queued ten-case/sixteen-process real CLI gate; one serial, disposable SQLite path."""
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys

import pytest
from tests.full155_export_fixtures import inputs, sha, SEED_PATH
from scripts import export_builtin_oracle_seed as exporter

WORKER = Path(__file__).with_name('export_recovery_cli_worker.py')
PRIOR = Path(__file__).parent / 'fixtures/full155_export_audit/approved17-ledger.json'
SCRIPT = Path(exporter.__file__)


@pytest.fixture(scope='module')
def one_root():
    slot = os.environ.get('MTG_EXPORT_RECOVERY_SQL_SLOT')
    if slot == 'github-actions-isolated':
        from tests.ci_input_contracts import assert_github_owned_source
        assert_github_owned_source()
    elif slot != 'parent-approved':
        pytest.fail('Real CLI SQL gate requires a new explicit shared-slot grant')
    root = Path(os.environ['MTG_EXPORT_RECOVERY_EVIDENCE_ROOT']).resolve()
    assert root.parent == Path('/tmp') and root.name.startswith('mtg-export-recovery-CLI-')
    root.mkdir(exist_ok=False)
    assert not (root / 'owned.sqlite').exists()
    return root


def fixture(one_root, route='cache', fault='complete'):
    # A single owned DB path is re-prepared between serial cases, never during an invocation.
    db = one_root / 'owned.sqlite'
    if db.exists():
        with sqlite3.connect(db) as conn:
            conn.execute('DROP TABLE cardcache')
            conn.execute('DROP TABLE cardknowledge')
    db, options = inputs(one_root, route, fault)
    protected = [db, SEED_PATH, PRIOR, options['canonical_bulk'], options['semantic_admission']]
    with sqlite3.connect(f'file:{db.resolve()}?mode=ro', uri=True) as conn:
        sql = '\n'.join(conn.iterdump())
    return db, options, {str(p): sha(p) for p in protected}, sql


def invocation(one_root, supplied, paths, mode='none', recover=False):
    db, options, protected, sql = supplied
    if recover:
        command = [sys.executable, str(SCRIPT), '--output', str(paths[0]), '--fact-ledger', str(paths[1]),
                   '--recover-publication', '--database', str(one_root / 'absent.sqlite'),
                   '--canonical-bulk', str(one_root / 'absent-bulk'),
                   '--semantic-admission', str(one_root / 'absent-admission'),
                   '--preservation-seed', str(one_root / 'absent-seed'),
                   '--preservation-ledger', str(one_root / 'absent-ledger')]
    else:
        command = [sys.executable, str(WORKER), '--audit-fault', mode,
                   '--audit-marker', str(paths[0].parent / 'fault-marker.json'),
                   '--database', str(db), '--output', str(paths[0]), '--fact-ledger', str(paths[1])]
        for key, value in options.items():
            command += ['--' + key.replace('_', '-'), str(value)]
        command += ['--preservation-ledger', str(PRIOR), '--preservation-ledger-sha256', sha(PRIOR)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert {name: sha(Path(name)) for name in protected} == protected
    with sqlite3.connect(f'file:{db.resolve()}?mode=ro', uri=True) as conn:
        after = '\n'.join(conn.iterdump())
    assert after == sql
    with (one_root / 'invocations.jsonl').open('a') as stream:
        json.dump({'command': command, 'returncode': run.returncode, 'mode': mode, 'recovery': recover,
                   'stdout': run.stdout, 'stderr': run.stderr, 'protected_hashes': protected,
                   'SQLdump_sha256': hashlib.sha256(sql.encode()).hexdigest(), 'SQL_equal': True,
                   'source_inputs_missing_for_recovery': recover}, stream)
        stream.write('\n')
    assert not (one_root / 'absent.sqlite').exists()
    return run


def pair(one_root, label, existing):
    root = one_root / label
    root.mkdir()
    paths = [root / 'seed.json', root / 'facts.json']
    if existing:
        paths[0].write_bytes(b'opaque original user seed\xff')
        paths[1].write_bytes(b'opaque original user ledger\x00')
        for path in paths:
            path.chmod(0o640)
    return paths, [p.read_bytes() if p.exists() else None for p in paths]


@pytest.mark.parametrize('route', ['cache', 'knowledge'])
def test_real_CLI_full155_all17_repeated_byte_idempotence(one_root, route):
    supplied = fixture(one_root, route)
    paths, _ = pair(one_root, route, False)
    for repeat in range(2):
        run = invocation(one_root, supplied, paths)
        assert run.returncode == 0, run.stderr
        assert paths[0].read_bytes() == SEED_PATH.read_bytes()
        assert paths[1].read_bytes() == PRIOR.read_bytes()
    assert len(json.loads(paths[0].read_text())['cards']) == 155
    assert len(json.loads(paths[1].read_text())) == 17
    assert not exporter._journal_path(paths).exists()


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('fault', ['cache_oracle_conflict', 'bad_admission_hash'])
def test_real_CLI_admission_refusal_preserves_originals_SQL_all_inputs(one_root, existing, fault):
    supplied = fixture(one_root, fault=fault)
    paths, before = pair(one_root, f'{fault}-{existing}', existing)
    run = invocation(one_root, supplied, paths)
    assert run.returncode != 0
    assert [p.read_bytes() if p.exists() else None for p in paths] == before
    assert not exporter._journal_path(paths).exists()
    assert not list(paths[0].parent.glob('.oracle-*'))


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('mode', ['kill_after_first', 'kill_after_commit'])
def test_real_CLI_SIGKILL_then_input_independent_explicit_recovery(one_root, existing, mode):
    supplied = fixture(one_root)
    paths, before = pair(one_root, f'{mode}-{existing}', existing)
    marker = paths[0].parent / 'fault-marker.json'
    run = invocation(one_root, supplied, paths, mode)
    assert run.returncode == -signal.SIGKILL, run.stderr
    assert json.loads(marker.read_text())['boundary'] == mode
    assert exporter._journal_path(paths).exists()
    recovered = invocation(one_root, supplied, paths, recover=True)
    assert recovered.returncode == 0, recovered.stderr
    if mode == 'kill_after_first':
        assert [p.read_bytes() if p.exists() else None for p in paths] == before
    else:
        assert paths[0].read_bytes() == SEED_PATH.read_bytes()
        assert paths[1].read_bytes() == PRIOR.read_bytes()
    assert not exporter._journal_path(paths).exists()
