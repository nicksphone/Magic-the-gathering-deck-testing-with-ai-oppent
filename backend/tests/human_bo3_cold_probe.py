"""Committed test-only cold public lookup; no lifespan or writable SQL."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlsplit


def read_cold_match(match_id):
    from persistence.db import DATABASE_PATH

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, '-m', 'tests.human_bo3_cold_probe', str(DATABASE_PATH), match_id],
        cwd=root / 'backend', env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True, timeout=60, check=True)
    return json.loads(result.stdout)


def run(database, match_id):
    root = Path(__file__).resolve().parents[2]
    path = Path(database)
    assert os.environ['MTG_ISOLATED_TEST_ROOT'] == str(root)
    assert not (root / '.git').exists()
    assert (root / '.private-choice-audit-source').read_text() == str(root)
    assert path == root / 'backend/mtg_lab.db' and path.is_file()
    assert all(not part.is_symlink() for part in (path, *path.parents))
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    def guard(event, args):
        if event == 'sqlite3.connect':
            uri = urlsplit(os.fsdecode(args[0]))
            assert (uri.scheme == 'file' and not uri.netloc
                    and Path(unquote(uri.path)) == path
                    and parse_qs(uri.query) == {'mode': ['ro']}), 'Cold SQL must be readonly'
        if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo',
                     'subprocess.Popen', 'os.system', 'os.fork', 'os.exec', 'os.posix_spawn'}:
            raise RuntimeError('Cold read has no network or process authority')
        if event == 'open' and not isinstance(args[0], int):
            mode, flags = args[1:3]
            assert not (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
                        or isinstance(mode, str) and any(c in mode for c in 'wax+')), 'Cold read cannot write'

    sys.addaudithook(guard)
    from sqlmodel import create_engine
    import persistence.db as db

    db.engine.dispose()
    db.engine = create_engine('sqlite:///' + path.as_uri() + '?mode=ro&uri=true')
    import main
    from fastapi.testclient import TestClient
    from game_state.serializers import serialize_match_snapshot

    try:
        assert not main.ACTIVE_MATCHES
        # No context manager: no startup, bootstrap, owner epoch or eager restore.
        client = TestClient(main.app)
        try:
            response = client.get('/matches/' + match_id)
            assert response.status_code == 200, response.text
            controller = main.ACTIVE_MATCHES[match_id]
            value = {'pid': os.getpid(), 'readonly': True, 'view': response.json(),
                     'snapshot': serialize_match_snapshot(controller.state),
                     'controller': main._controller_snapshot(controller)}
        finally:
            client.close()
    finally:
        db.engine.dispose()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    return value


if __name__ == '__main__':
    assert len(sys.argv) == 3
    print(json.dumps(run(sys.argv[1], sys.argv[2])))
