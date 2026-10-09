"""Source lease and native file ownership for the bounded HTTP fixtures."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]


def source_lease():
    assert Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve() == ROOT
    assert (ROOT / '.private').read_text() == str(ROOT) and not (ROOT / '.git').exists()
    assert not ROOT.is_symlink()
    return ROOT


def source_default_identity():
    path = ROOT / 'backend/mtg_lab.db'
    return path.lstat() if path.exists() or path.is_symlink() else None


@contextmanager
def owned_database(engine):
    from sqlmodel import SQLModel
    from persistence.capacity import DatabaseOwner, initialize_capacity
    owner = DatabaseOwner(engine).acquire()
    try:
        SQLModel.metadata.create_all(engine, tables=[
            table for table in SQLModel.metadata.sorted_tables
            if table.name not in {'resourcecapacity', 'resourcereservation'}])
        backup = owner.path.with_name(owner.path.stem + '.before-capacity-' + owner.epoch + '.sqlite3')
        initialize_capacity(owner, backup)
        owner.open_admission()
        yield owner
    finally:
        owner.fence_admission()
        owner.drain_producers(timeout=5)
        assert engine.pool.checkedout() == 0
        owner.close()
        assert owner.fd is None and not owner.producers


@contextmanager
def api_context(monkeypatch, request, storage):
    from fastapi.testclient import TestClient
    from sqlmodel import create_engine
    import main
    import persistence.db as db
    root = source_lease()
    assert Path(main.__file__).resolve().parent == root / 'backend'
    original_default = source_default_identity()
    directory = root / 'http-cases' / hashlib.sha256(request.node.nodeid.encode()).hexdigest()
    directory.mkdir(parents=True, exist_ok=False)
    default = directory / 'mtg_lab.db'
    assert not default.exists() and not default.is_symlink()
    # Native capacity ownership does not support in-memory SQLite.
    path = directory / 'state.sqlite3'
    engine = create_engine('sqlite:///' + str(path), connect_args={'check_same_thread': False})
    api = SimpleNamespace(main=main, engine=engine, client=None, path=path,
                          storage=storage, directory=directory, closed=False)
    ownership = owned_database(engine)

    def close():
        if not api.closed:
            if api.client is not None:
                api.client.close()
            ownership.__exit__(None, None, None)
            api.closed = True

    api.close = close
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {})
    assert main.get_repo not in main.app.dependency_overrides
    ownership.__enter__()
    try:
        # No lifespan: retain the explicit owner through repository operations.
        api.client = TestClient(main.app)
        yield api
    finally:
        close()
        assert not default.exists() and not default.is_symlink()
        assert source_default_identity() == original_default
