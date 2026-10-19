"""File-only recovery acceptance, not immediate atomic pair visibility."""
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

import pytest
from scripts import export_builtin_oracle_seed as exporter

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / 'scripts/export_builtin_oracle_seed.py'
SEED = BACKEND / 'card_data/builtin_oracle_seed.json'
LEDGER = Path(__file__).parent / 'fixtures/full155_export_audit/approved17-ledger.json'


def setup_pair(root, existing=True, separate=False):
    paths = [root / 'seed.json', root / 'facts.json']
    if separate:
        (root / 'other').mkdir()
        paths[1] = root / 'other/facts.json'
    new = [SEED.read_bytes(), LEDGER.read_bytes()]
    old = [b'opaque previous user seed\x00\xff', b'opaque previous ledger\xff']
    if existing:
        for path, raw in zip(paths, old):
            path.write_bytes(raw)
            path.chmod(0o640)
    return paths, new, old if existing else [None, None]


def snapshot(paths):
    return [(path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) if path.exists() else None for path in paths]


def journal(paths):
    return exporter._journal_path(paths)


def run_recovery(paths):
    command = [sys.executable, str(SCRIPT), '--output', str(paths[0]), '--fact-ledger', str(paths[1]),
               '--recover-publication', '--database', str(paths[0].parent / 'missing.sqlite'),
               '--canonical-bulk', str(paths[0].parent / 'missing-bulk'),
               '--semantic-admission', str(paths[0].parent / 'missing-admission'),
               '--preservation-seed', str(paths[0].parent / 'missing-seed'),
               '--preservation-ledger', str(paths[0].parent / 'missing-ledger')]
    return subprocess.run(command, capture_output=True, text=True, timeout=20)


def kill_publication(paths, boundary):
    # Run the actual helper in a fresh process; only the process-boundary fault is injected.
    code = '''
import json, os, signal, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from scripts import export_builtin_oracle_seed as e
paths = [Path(p) for p in sys.argv[2:4]]
boundary = sys.argv[4]
marker = paths[0].parent / 'kill-marker.json'
def die(stage):
    with marker.open('w') as stream:
        json.dump({'stage': stage, 'pid': os.getpid()}, stream)
        stream.flush(); os.fsync(stream.fileno())
    os.kill(os.getpid(), signal.SIGKILL)
replace = e.os.replace
count = 0
def replacement(source, dest):
    global count
    result = replace(source, dest)
    if Path(dest) in paths:
        count += 1
        if boundary == 'after_first' and count == 1: die(boundary)
        if boundary == 'after_second' and count == 2: die(boundary)
    return result
e.os.replace = replacement
append = e._append_record
commit_written = False
def record(fd, data):
    global commit_written
    if boundary == 'torn_commit' and 'committed' in data:
        os.write(fd, b'{"payload":'); os.fsync(fd); die(boundary)
    append(fd, data)
    if 'committed' in data: commit_written = True
    if boundary == 'prepared' and 'version' in data: die(boundary)
    if boundary == 'committed' and 'committed' in data: die(boundary)
e._append_record = record
sync = e._sync_directory
def cleanup(directory):
    sync(directory)
    if boundary == 'cleanup' and commit_written: die(boundary)
e._sync_directory = cleanup
seed = Path(sys.argv[1]) / 'card_data/builtin_oracle_seed.json'
ledger = Path(sys.argv[1]) / 'tests/fixtures/full155_export_audit/approved17-ledger.json'
e._write_outputs([(paths[0], seed.read_text()), (paths[1], ledger.read_text())])
'''
    run = subprocess.run([sys.executable, '-c', code, str(BACKEND), *map(str, paths), boundary],
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == -signal.SIGKILL, run.stderr
    assert json.loads((paths[0].parent / 'kill-marker.json').read_text())['stage'] == boundary
    assert journal(paths).stat().st_mode & 0o777 == 0o600
    return run


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('boundary', ['prepared', 'after_first', 'after_second', 'torn_commit', 'committed', 'cleanup'])
def test_SIGKILL_explicit_restart_without_original_metadata_inputs(tmp_path, existing, boundary):
    paths, new, old = setup_pair(tmp_path, existing)
    before = snapshot(paths)
    sentinel = tmp_path / 'unrelated-user-file'
    sentinel.write_bytes(b'never remove this')
    kill_publication(paths, boundary)
    # This assertion deliberately does NOT require immediate atomic pair visibility.
    run = run_recovery(paths)
    assert run.returncode == 0, run.stderr
    if boundary in ('committed', 'cleanup'):
        assert [p.read_bytes() for p in paths] == new
    else:
        assert snapshot(paths) == before
    assert not journal(paths).exists()
    assert not list(tmp_path.glob('.oracle-*'))
    assert sentinel.read_bytes() == b'never remove this'
    again = run_recovery(paths)
    assert again.returncode == 0 and 'no files certified or changed' in again.stdout
    assert not (tmp_path / 'missing.sqlite').exists()


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('separate', [False, True])
def test_full155_prior17_success_and_exact_byte_idempotence(tmp_path, existing, separate):
    paths, new, _ = setup_pair(tmp_path, existing, separate)
    exporter._write_outputs([(p, raw.decode()) for p, raw in zip(paths, new)])
    first = snapshot(paths)
    exporter._write_outputs([(p, raw.decode()) for p, raw in zip(paths, new)])
    assert snapshot(paths) == first
    assert [p.read_bytes() for p in paths] == new
    assert len(json.loads(new[0])['cards']) == 155 and len(json.loads(new[1])) == 17
    assert not journal(paths).exists()
    assert all(item[1] == (0o640 if existing else 0o600) for item in first)


@pytest.mark.parametrize('existing', [False, True])
def test_second_failure_rollback_failure_retains_originals_for_restart(tmp_path, monkeypatch, existing):
    paths, new, _ = setup_pair(tmp_path, existing)
    before = snapshot(paths)
    replace = exporter.os.replace
    def fail(source, dest):
        if Path(dest) == paths[1] or str(source).endswith('.old'):
            raise OSError('injected replacement/rollback failure')
        return replace(source, dest)
    with monkeypatch.context() as patch:
        patch.setattr(exporter.os, 'replace', fail)
        if existing:
            with pytest.raises(RuntimeError, match='journal retained'):
                exporter._write_outputs([(p, raw.decode()) for p, raw in zip(paths, new)])
            assert journal(paths).exists()
        else:
            with pytest.raises(OSError):
                exporter._write_outputs([(p, raw.decode()) for p, raw in zip(paths, new)])
            assert snapshot(paths) == before
            return
    run = run_recovery(paths)
    assert run.returncode == 0, run.stderr
    assert snapshot(paths) == before


def test_interrupted_rollback_repeat_restores_original_pair(tmp_path, monkeypatch):
    paths, _, _ = setup_pair(tmp_path)
    before = snapshot(paths)
    kill_publication(paths, 'after_second')
    replace = exporter.os.replace
    def fail(source, dest):
        if Path(dest) == paths[1]:
            raise OSError('second rollback fails')
        return replace(source, dest)
    with monkeypatch.context() as patch:
        patch.setattr(exporter.os, 'replace', fail)
        with pytest.raises(OSError):
            exporter._recover_publication(paths)
    assert snapshot(paths)[0] == before[0] and journal(paths).exists()
    run = run_recovery(paths)
    assert run.returncode == 0, run.stderr
    assert snapshot(paths) == before


@pytest.mark.parametrize('boundary', ['after_first', 'committed'])
def test_later_user_edit_refuses_before_any_recovery_mutation(tmp_path, boundary):
    paths, _, _ = setup_pair(tmp_path)
    kill_publication(paths, boundary)
    paths[1].write_bytes(b'user later edit')
    before = {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    run = run_recovery(paths)
    assert run.returncode != 0 and 'recovery refused' in run.stderr
    assert {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


@pytest.mark.parametrize('change', ['checksum', 'foreign_stage', 'old_backup', 'symlink', 'journal_mode'])
def test_tamper_foreign_and_symlink_refuse_unchanged(tmp_path, change):
    paths, _, _ = setup_pair(tmp_path)
    kill_publication(paths, 'after_first')
    jp = journal(paths)
    record = json.loads(jp.read_text().splitlines()[0])
    if change == 'symlink':
        paths[1].unlink()
        target = tmp_path / 'unrelated'
        target.write_bytes(b'private user bytes')
        paths[1].symlink_to(target)
    elif change == 'journal_mode':
        jp.chmod(0o644)
    else:
        if change == 'checksum':
            record['sha256'] = '0' * 64
        elif change == 'foreign_stage':
            record['payload']['entries'][0]['stage'] = str(tmp_path / 'unrelated')
        else:
            record['payload']['entries'][0]['old']['bytes'] = base64.b64encode(b'wrong backup').decode()
        if change != 'checksum':
            record['sha256'] = exporter._raw_hash(record['payload'])
        jp.write_text(json.dumps(record) + '\n')
    before = {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    run = run_recovery(paths)
    assert run.returncode != 0
    assert {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_pending_journal_refuses_normal_cli_before_missing_DB_read(tmp_path):
    paths, _, _ = setup_pair(tmp_path)
    kill_publication(paths, 'after_first')
    before = snapshot(paths)
    run = subprocess.run([sys.executable, str(SCRIPT), '--output', str(paths[0]), '--fact-ledger', str(paths[1]),
                          '--database', str(tmp_path / 'never-created.sqlite')], capture_output=True, text=True, timeout=20)
    assert run.returncode != 0 and 'Pending publication journal' in run.stderr
    assert not (tmp_path / 'never-created.sqlite').exists() and snapshot(paths) == before


def test_active_owner_refuses_recovery(tmp_path):
    paths, _, _ = setup_pair(tmp_path)
    kill_publication(paths, 'after_first')
    fd = os.open(journal(paths), os.O_RDWR)
    try:
        exporter._lock_journal(fd, journal(paths))
        before = snapshot(paths)
        run = run_recovery(paths)
        assert run.returncode != 0 and snapshot(paths) == before
    finally:
        os.close(fd)


@pytest.mark.parametrize('mode', ['symlink', 'hardlink', 'same'])
def test_output_alias_refusal_before_mutation(tmp_path, mode):
    paths, new, _ = setup_pair(tmp_path)
    paths[1].unlink()
    if mode == 'symlink':
        paths[1].symlink_to(paths[0])
    elif mode == 'hardlink':
        os.link(paths[0], paths[1])
    else:
        paths[1] = paths[0]
    before = snapshot(paths)
    with pytest.raises(ValueError):
        exporter._write_outputs([(p, raw.decode()) for p, raw in zip(paths, new)])
    assert snapshot(paths) == before


def test_recovery_requires_explicit_output(tmp_path):
    run = subprocess.run([sys.executable, str(SCRIPT), '--fact-ledger', str(tmp_path / 'facts'), '--recover-publication'],
                         capture_output=True, text=True, timeout=20)
    assert run.returncode != 0 and 'requires explicit' in run.stderr
    assert not list(tmp_path.iterdir())


def test_foreign_trailing_record_is_not_misclassified_as_torn_commit(tmp_path):
    paths, _, _ = setup_pair(tmp_path)
    kill_publication(paths, 'after_first')
    with journal(paths).open('ab') as stream:
        stream.write(b'foreign bytes, not a commit prefix')
    before = snapshot(paths), journal(paths).read_bytes()
    run = run_recovery(paths)
    assert run.returncode != 0 and 'Invalid publication commit' in run.stderr
    assert (snapshot(paths), journal(paths).read_bytes()) == before


def test_journal_inode_replacement_refuses_before_mutation(tmp_path):
    paths, _, _ = setup_pair(tmp_path)
    kill_publication(paths, 'after_first')
    jp = journal(paths)
    fd = os.open(jp, os.O_RDWR)
    try:
        exporter._lock_journal(fd, jp)
        data, committed = exporter._read_journal(fd, paths)
        replacement = tmp_path / 'foreign-journal'
        replacement.write_bytes(jp.read_bytes())
        replacement.chmod(0o600)
        os.replace(replacement, jp)
        before = snapshot(paths), jp.read_bytes()
        with pytest.raises(ValueError, match='identity changed'):
            exporter._finish_publication(fd, jp, paths, data, committed)
        assert (snapshot(paths), jp.read_bytes()) == before
    finally:
        os.close(fd)


def test_input_hardlink_alias_refuses_without_database_read(tmp_path):
    paths, _, _ = setup_pair(tmp_path)
    protected = tmp_path / 'opaque-input.sqlite'
    os.link(paths[0], protected)
    before = snapshot(paths), protected.read_bytes()
    run = subprocess.run([sys.executable, str(SCRIPT), '--output', str(paths[0]),
                          '--fact-ledger', str(paths[1]), '--database', str(protected),
                          '--recover-publication'], capture_output=True, text=True, timeout=20)
    assert run.returncode != 0 and 'must not overwrite canonical inputs' in run.stderr
    assert (snapshot(paths), protected.read_bytes()) == before


@pytest.mark.parametrize('call', [1, 2])
def test_stage_fsync_failure_keeps_original_pair_and_no_journal(tmp_path, monkeypatch, call):
    paths, new, _ = setup_pair(tmp_path)
    before = snapshot(paths)
    fsync = exporter.os.fsync
    count = 0
    def fail(fd):
        nonlocal count
        count += 1
        if count == call:
            raise OSError('stage fsync failure')
        return fsync(fd)
    with monkeypatch.context() as patch:
        patch.setattr(exporter.os, 'fsync', fail)
        with pytest.raises(OSError, match='stage fsync'):
            exporter._write_outputs([(p, raw.decode()) for p, raw in zip(paths, new)])
    assert snapshot(paths) == before
    assert set(tmp_path.iterdir()) == set(paths)


def test_commit_fsync_error_never_rolls_back_complete_recorded_generation(tmp_path, monkeypatch):
    paths, new, _ = setup_pair(tmp_path)
    append = exporter._append_record
    def fail(fd, record):
        append(fd, record)
        if 'committed' in record:
            raise OSError('commit acknowledgement failed')
    with monkeypatch.context() as patch:
        patch.setattr(exporter, '_append_record', fail)
        with pytest.raises(OSError, match='commit acknowledgement'):
            exporter._write_outputs([(p, raw.decode()) for p, raw in zip(paths, new)])
    assert [p.read_bytes() for p in paths] == new
    assert not journal(paths).exists()


def test_exclusive_stage_collision_never_deletes_foreign_user_file(tmp_path, monkeypatch):
    paths, new, _ = setup_pair(tmp_path)
    nonce = 'a' * 32
    foreign = tmp_path / f'.oracle-{nonce}-0.new'
    foreign.write_bytes(b'preexisting user file')
    before = snapshot(paths), foreign.read_bytes()
    class Fixed:
        hex = nonce
    monkeypatch.setattr(exporter.uuid, 'uuid4', lambda: Fixed())
    with pytest.raises(FileExistsError):
        exporter._write_outputs([(p, raw.decode()) for p, raw in zip(paths, new)])
    assert (snapshot(paths), foreign.read_bytes()) == before


def test_SIGKILL_during_first_rollback_then_fresh_process_resumes(tmp_path):
    paths, _, _ = setup_pair(tmp_path)
    before = snapshot(paths)
    kill_publication(paths, 'after_second')
    code = '''
import os, signal, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from scripts import export_builtin_oracle_seed as e
paths = [Path(p) for p in sys.argv[2:4]]
replace = e.os.replace
def die_after_restore(source, dest):
    result = replace(source, dest)
    if Path(dest) == paths[0]:
        with (paths[0].parent / 'rollback-kill-marker').open('w') as stream:
            stream.write(str(os.getpid())); stream.flush(); os.fsync(stream.fileno())
        os.kill(os.getpid(), signal.SIGKILL)
    return result
e.os.replace = die_after_restore
e._recover_publication(paths)
'''
    run = subprocess.run([sys.executable, '-c', code, str(BACKEND), *map(str, paths)],
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == -signal.SIGKILL, run.stderr
    assert snapshot(paths)[0] == before[0] and journal(paths).exists()
    assert (tmp_path / 'rollback-kill-marker').exists()
    resumed = run_recovery(paths)
    assert resumed.returncode == 0, resumed.stderr
    assert snapshot(paths) == before and not journal(paths).exists()


def test_every_exact_commit_prefix_is_uncommitted_until_complete(tmp_path):
    paths, _, _ = setup_pair(tmp_path)
    kill_publication(paths, 'after_first')
    jp = journal(paths)
    prepared = jp.read_bytes()
    data = json.loads(prepared)['payload']
    commit = exporter._journal_record({'committed': exporter._raw_hash(data)})
    for count in range(len(commit) + 1):
        jp.write_bytes(prepared + commit[:count])
        fd = os.open(jp, os.O_RDWR)
        try:
            recorded, committed = exporter._read_journal(fd, paths)
            assert recorded == data
            assert committed == (count == len(commit))
        finally:
            os.close(fd)
