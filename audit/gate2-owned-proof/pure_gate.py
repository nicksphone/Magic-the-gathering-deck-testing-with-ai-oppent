"""Install native denial before pytest imports or test collection."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT.parent / 'evidence'
blocked = []

class PureDenied(PermissionError, AssertionError):
    pass

def audit(event, args):
    if (event.startswith(('sqlite3.', 'socket.')) or event in {
        'subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty',
        'os.posix_spawn', 'os.exec', 'pty.spawn',
    }):
        blocked.append(event)
        raise PureDenied('Pure Gate2 denies SQL, sockets and children: ' + event)

sys.addaudithook(audit)
import _sqlite3
import _socket
import subprocess
probes = [lambda: _sqlite3.connect(':memory:'), _socket.socket,
          lambda: subprocess.run(['true']), lambda: os.system('true'), os.fork]
for probe in probes:
    try:
        probe()
    except PermissionError:
        pass
    else:
        raise AssertionError('Native denial probe escaped')
precollection = list(blocked)
sys.path[:0] = [str(ROOT / 'backend'), str(Path(__file__).parent)]
import pytest

class Proof:
    def pytest_sessionfinish(self, session, exitstatus):
        pins = {}
        for name, module in sorted(sys.modules.items()):
            if name.split('.')[0] not in {'rules_engine', 'effects', 'game_state',
                    'card_data', 'knowledge', 'scripts', 'ai', 'persistence', 'inventory'}:
                continue
            filename = getattr(module, '__file__', None)
            if filename:
                path = Path(filename).resolve()
                assert path.is_relative_to(ROOT), (name, path)
                pins[name] = {'path': str(path.relative_to(ROOT)),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        assert not (ROOT / 'backend/mtg_lab.db').exists()
        receipt = {'exit': int(exitstatus), 'root': str(ROOT), 'python': sys.executable,
                   'precollection_denials': precollection, 'all_denials': blocked,
                   'import_pins': pins, 'default_database_absent': True}
        with (EVIDENCE / os.environ['GATE2_RECEIPT']).open('x') as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)

raise SystemExit(pytest.main(sys.argv[1:], plugins=[Proof()]))
