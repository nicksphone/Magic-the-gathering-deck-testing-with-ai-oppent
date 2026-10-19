"""Pure path/transition policy; no native lock, SQL, backup or bootstrap proof."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import create_engine

import persistence.capacity as capacity
import persistence.job_retention as retention
from persistence.job_retention import local_path


DEFAULT = Path(capacity.__file__).resolve().parents[1] / 'mtg_lab.db'


def default_file_state():
    if not DEFAULT.exists():
        return None
    stat = DEFAULT.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
            sha256(DEFAULT.read_bytes()).hexdigest())


def test_exact_application_default_validates_without_creation():
    before = default_file_state()
    assert capacity.application_database_path(DEFAULT, existing=False) == DEFAULT
    assert default_file_state() == before


def test_offline_default_rejection_is_unchanged():
    with pytest.raises(ValueError, match='source-relative application database'):
        local_path(DEFAULT, existing=False)


def test_application_seam_still_rejects_network_filesystem(monkeypatch):
    read_text = Path.read_text
    mounts = ('1 0 0:1 / / rw - ext4 fixture rw\n'
              '2 1 0:2 / /mnt/rchfiles rw - nfs fixture:/export rw\n')
    monkeypatch.setattr(retention.Path, 'read_text', lambda path, *a, **kw:
                        mounts if path == Path('/proc/self/mountinfo') else read_text(path, *a, **kw))
    with pytest.raises(ValueError, match='recognized local filesystem'):
        capacity.application_database_path(Path('/mnt/rchfiles/codex-storage/not-a-database.txt'), existing=False)


def test_default_owner_backup_requires_actual_acquisition_before_io(tmp_path, monkeypatch):
    import scripts.verify_storage_restore as backup
    calls = []
    before = default_file_state()
    monkeypatch.setattr(backup, '_backup_validated_database', lambda *a, **kw: calls.append(True))
    engine = create_engine('sqlite:///' + str(DEFAULT))
    try:
        owner = capacity.DatabaseOwner(engine)
        with pytest.raises(capacity.CapacityIntegrityError, match='Live initialized owner'):
            owner.backup(tmp_path / 'backup.txt')
        assert calls == [] and default_file_state() == before
    finally:
        engine.dispose()


def test_unregistered_owner_is_rejected_before_descriptor_access():
    engine = create_engine('sqlite:///' + str(DEFAULT))
    try:
        owner = capacity.DatabaseOwner(engine)
        # Deliberately fake descriptor, never an acquired native lock.
        owner.fd = 999999999
        with pytest.raises(capacity.CapacityIntegrityError, match='Registered owner'):
            owner.require(ready=False)
    finally:
        engine.dispose()


def job_values(status):
    return dict(status=status, request_json='{}', result_json=None, error=None,
                completed_matches=1, total_matches=1, started_at=1.0, finished_at=2.0)


@pytest.mark.parametrize('status', ['queued','running','completed','failed','canceled','retired'])
def test_retired_tombstone_cannot_be_rewritten_or_restored(status):
    with pytest.raises(capacity.CapacityIntegrityError, match='explicit operator maintenance'):
        capacity.validate_job_transition(SimpleNamespace(**job_values('retired')), job_values(status))


def test_generic_writer_cannot_create_a_retired_tombstone():
    with pytest.raises(capacity.CapacityIntegrityError, match='explicit operator maintenance'):
        capacity.validate_job_transition(None, job_values('retired'))


@pytest.mark.parametrize('status', ['completed','failed','canceled'])
def test_terminal_job_cannot_restart(status):
    with pytest.raises(capacity.CapacityIntegrityError, match='immutable'):
        capacity.validate_job_transition(SimpleNamespace(**job_values(status)), job_values('queued'))


@pytest.mark.parametrize('field,value', [('result_json','{}'),('error','restored'),
                                       ('finished_at',3.0),('completed_matches',2)])
def test_terminal_fields_cannot_be_rewritten(field, value):
    original = job_values('completed')
    with pytest.raises(capacity.CapacityIntegrityError, match='immutable'):
        capacity.validate_job_transition(SimpleNamespace(**original), dict(original, **{field:value}))


@pytest.mark.parametrize('status', ['completed','failed','canceled'])
def test_equal_existing_terminal_record_is_not_changed(status):
    values = job_values(status)
    assert capacity.validate_job_transition(SimpleNamespace(**values), values) is None
