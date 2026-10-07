"""Test-only cold native restore/ASGI probe; never starts application lifespan."""
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit


def install_guard():
    root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']).absolute()
    assert root.resolve() == root and not root.is_symlink()
    assert (root / '.private').read_text() == str(root) and not (root / '.git').exists()
    assert not (root / 'backend/mtg_lab.db').exists()
    allowed = set()
    def guard(event, args):
        if event == 'socket.connect':
            raise PermissionError('External sockets forbidden in owned ASGI qualification')
        if event != 'sqlite3.connect':
            return
        value = os.fsdecode(args[0])
        if value == ':memory:':
            allowed.add(value)
            return
        value = unquote(urlsplit(value).path) if value.startswith('file:') else value
        path = Path(value)
        assert path.is_absolute() and path.resolve().is_relative_to(root / 'http-cases'), value
        assert path.suffix == '.sqlite3' and not path.is_symlink(), value
        assert all(not part.is_symlink() for part in [path.parent, *path.parents]), value
        allowed.add(str(path))
    sys.addaudithook(guard)
    sys.path.insert(0, str(root / 'backend'))
    return root, allowed


def import_proof(root):
    rows = {}
    for name, module in sorted(sys.modules.items()):
        if name not in {'main', 'api_contracts'} and name.split('.')[0] not in {
                'ai', 'effects', 'rules_engine', 'game_state', 'card_data',
                'persistence', 'knowledge', 'tests'}:
            continue
        value = getattr(module, '__file__', None)
        if value:
            path = Path(value).resolve()
            assert path.is_relative_to(root / 'backend'), (name, str(path))
            rows[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return rows


def run(config, output):
    root, allowed = install_guard()
    assert config['root'] == str(root) and config['parent_pid'] != os.getpid()
    path = Path(config['database'])
    assert path.resolve().is_relative_to(root / 'http-cases') and not path.is_symlink()
    open_handles = []
    for fd in (Path('/proc') / str(config['parent_pid']) / 'fd').iterdir():
        try:
            value = str(fd.readlink())
        except FileNotFoundError:
            continue
        if value in {str(path), str(path) + '-wal', str(path) + '-shm'}:
            open_handles.append(value)
    assert not open_handles, open_handles
    from fastapi.testclient import TestClient
    from sqlmodel import Session, create_engine
    from persistence.repository import Repository
    from tests.test_temporary_characteristics_http import (
        public, snapshot, db_dump, digest, controller_view, resolve_http, cleanup_http,
        assert_changed, card_view,
    )
    import main
    import persistence.db as db
    engine = create_engine('sqlite:///' + str(path), connect_args={'check_same_thread': False})
    main.engine = db.engine = engine
    main.ACTIVE_MATCHES = {}
    def repository():
        with Session(engine) as session:
            yield Repository(session)
    main.app.dependency_overrides[main.get_repo] = repository
    client = TestClient(main.app)
    result = None
    try:
        api = SimpleNamespace(main=main, engine=engine, client=client)
        sql_before = db_dump(engine)
        with Session(engine) as session:
            main._restore_active_matches(Repository(session), config['match_id'])
        controller = main.ACTIVE_MATCHES[config['match_id']]
        restored = snapshot(controller.state)
        restored_config = controller_view(api, controller)
        assert restored == config['state'] and restored_config == config['controller']
        value = public(api, controller, config['hidden_id'])
        assert value == config['public'] and db_dump(engine) == sql_before
        result = {'pid': os.getpid(), 'parent_pid': config['parent_pid'],
                  'parent_handles_closed': True, 'restored_state': restored,
                  'restored_controller': restored_config, 'restored_public': value,
                  'initial_sql_sha256': digest(sql_before)}
        if config['stage'] == 'pending':
            assert len(controller.state.stack) == 1
            assert '__announced_target_references' in controller.state.stack[-1].payload
            resolve_http(api, controller, config['hidden_id'])
            value = public(api, controller, config['hidden_id'])
            assert_changed(value, config['seat'], config['target_id'], config['name'])
        else:
            assert not controller.state.stack
            assert_changed(value, config['seat'], config['target_id'], config['name'])
            cleanup_http(api, controller, config['hidden_id'])
            value = public(api, controller, config['hidden_id'])
            card = card_view(value, config['seat'], config['target_id'])
            assert card['type_line'] == card['base_type_line'] and card['colors'] == ['G']
            assert (card['power'], card['toughness']) == (2, 3) and 'flying' in card['keywords']
        result.update(after=snapshot(controller.state), final_public=value,
                      final_controller=controller_view(api, controller),
                      final_sql_sha256=digest(db_dump(engine)))
    finally:
        client.close()
        main.app.dependency_overrides.clear()
        assert engine.pool.checkedout() == 0
        engine.dispose()
        assert not (root / 'backend/mtg_lab.db').exists()
    result.update(connections_closed=True, modules=import_proof(root),
                  sql_paths=sorted(allowed), executable=sys.executable)
    with Path(output).open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
