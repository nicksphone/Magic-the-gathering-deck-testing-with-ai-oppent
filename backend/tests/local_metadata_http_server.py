"""Run unchanged production app on an inherited loopback socket; deny outbound I/O."""
import json
import os
from pathlib import Path
import socket
import signal
import sys

backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend))
os.chdir(backend)
os.environ.pop('MTG_DEBUG_HANDS', None)
ledger = Path(sys.argv[2])
allowed_database = backend / 'mtg_lab.db'
network = []
blocked = []

def flush():
    ledger.write_text(json.dumps({'pid': os.getpid(), 'allowed_loopback_outgoing': network,
                      'blocked_external_attempts': blocked, 'debug_hands_enabled': False}, indent=2))

def guard(event, args):
    if event == 'socket.getaddrinfo' and args[0] not in ('127.0.0.1', '::1', None):
        blocked.append({'event': event, 'host': str(args[0])})
        flush()
        raise AssertionError('External DNS forbidden')
    if event == 'socket.connect':
        address = args[1]
        if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
            blocked.append({'event': event, 'address': str(address)})
            flush()
            raise AssertionError('External connection forbidden')
        network.append({'event': event, 'address': str(address)})
        flush()
    if event == 'socket.bind':
        blocked.append({'event': event, 'address': str(args[1])})
        flush()
        raise AssertionError('Server must use its inherited ephemeral socket')
    if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
        assert Path(str(args[0])).resolve() == allowed_database, args[0]

sys.addaudithook(guard)
flush()
# Uvicorn re-raises captured SIGTERM to its previous handler after graceful exit.
signal.signal(signal.SIGTERM, lambda *_: None)
import uvicorn
listener = socket.socket(fileno=int(sys.argv[1]))
assert listener.getsockname()[0] == '127.0.0.1'
assert listener.getsockname()[1] not in (9999, 5173)
try:
    uvicorn.Server(uvicorn.Config('main:app', host='127.0.0.1', port=0,
                   workers=1, log_level='info')).run(sockets=[listener])
finally:
    flush()
