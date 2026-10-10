"""Genuine closed-file read-only worker; no lifespan, owner or bootstrap writes."""
import json
import os
from pathlib import Path
import sys

from tests.cold_restart_http_support import facts, local_file


def run(config, output):
    root = Path(config['root'])
    data = Path(config['data'])
    path = local_file(config['database'])
    assert root.resolve() == root and not (root / '.git').exists()
    assert (root / '.private').read_text() == str(root)
    assert (root / '.private-choice-audit-source').read_text() == str(root)
    assert os.environ['MTG_ISOLATED_TEST_ROOT'] == str(root)
    assert Path(__file__).resolve().parents[2] == root
    assert path.parent == data and not path.is_relative_to(root)
    default = root / 'backend/mtg_lab.db'
    assert not default.exists() and not default.is_symlink()
    assert Path(output).parent == data
    assert os.environ['MTG_PRIVATE_CHOICE_ROOT'] == str(root)
    assert (root / '.private-choice-owned').read_text() == os.environ['MTG_PRIVATE_CHOICE_TOKEN']
    assert data == root.parent / 'cold-restart-data' / root.name
    allowed = set()
    def guard(event, args):
        if event == 'socket.connect':
            raise PermissionError('Read-only worker has no network authority')
        if event == 'sqlite3.connect':
            assert args[0] == path.as_uri() + '?mode=ro', 'Only the declared readonly file is authorized'
            allowed.add(str(path))
    sys.addaudithook(guard)
    assert config['parent_pid'] != os.getpid()
    assert not Path('/proc', str(config['previous_pid'])).exists(), 'Previous native worker still live'
    result = {'pid': os.getpid(), 'readonly': True, 'connections_closed': False}
    try:
        actual = facts(path)
        result['facts'] = actual
        assert actual['raw_sha256'] == config['expected']['raw_sha256'], 'Closed-file raw hash changed'
        assert actual['sql'] == config['expected']['sql'], 'Persistent gameplay SQL changed in readonly worker'
        assert actual == config['expected']
        if config.get('audit') is not None:
            from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
            stored = facts(path, config['match_id'])['match']
            assert stored['state'] == config['audit']['state']
            restored = serialize_match_snapshot(deserialize_match_snapshot(stored['state']))
            # Match HTTP JSON transport of integer keys and RNG tuples, not SQL facts.
            assert json.loads(json.dumps(restored)) == config['audit']['state']
            assert stored['controller'] == config['audit']['controller']
            assert stored['controller']['revision'] == config['audit']['revision']
        result['verified'] = True
    except BaseException as exc:
        result['failure'] = str(exc)
        raise
    finally:
        handles = []
        for fd in Path('/proc/self/fd').iterdir():
            try:
                target = str(fd.readlink())
            except FileNotFoundError:
                continue
            if target.startswith(str(data)) and ('.sqlite3' in target or 'capacity-owner.lock' in target):
                handles.append(target)
        assert not default.exists() and not default.is_symlink()
        assert 'main' not in sys.modules
        result['sqlite_paths'] = sorted(allowed)
        result['open_handles'] = handles
        result['connections_closed'] = not handles
        Path(output).write_text(json.dumps(result))
        assert not handles


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
