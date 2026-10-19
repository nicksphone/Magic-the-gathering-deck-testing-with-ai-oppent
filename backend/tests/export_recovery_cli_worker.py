"""Actual exporter.main in a separate process, with bounded publication faults only."""
import json
import os
from pathlib import Path
import signal
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import export_builtin_oracle_seed as exporter


def main():
    index = sys.argv.index('--audit-fault')
    mode = sys.argv[index + 1]
    del sys.argv[index:index + 2]
    index = sys.argv.index('--audit-marker')
    marker = Path(sys.argv[index + 1])
    del sys.argv[index:index + 2]
    if mode not in ('none', 'kill_after_first', 'kill_after_commit'):
        raise ValueError('Unsupported audit fault')
    seed = Path(sys.argv[sys.argv.index('--output') + 1]).resolve()
    replace, append = exporter.os.replace, exporter._append_record
    def die(boundary):
        with marker.open('w') as stream:
            json.dump({'boundary': boundary, 'pid': os.getpid()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.kill(os.getpid(), signal.SIGKILL)
    def replacement(source, dest):
        result = replace(source, dest)
        if mode == 'kill_after_first' and Path(dest).resolve() == seed:
            die(mode)
        return result
    def record(fd, payload):
        append(fd, payload)
        if mode == 'kill_after_commit' and 'committed' in payload:
            die(mode)
    def forbidden(*args, **kwargs):
        raise AssertionError('Network forbidden in exporter audit')
    socket.socket.connect = forbidden
    exporter.os.replace = replacement
    exporter._append_record = record
    exporter.main()


if __name__ == '__main__':
    main()
