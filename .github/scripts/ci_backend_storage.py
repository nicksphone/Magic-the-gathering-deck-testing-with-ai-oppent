"""Private bounded diagnostics and cooperative disk-pressure interruption.

Not a filesystem quota/kernel sandbox. Unknown scratch/owners are never removed.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time

LOG_BYTES = 8 * 1024 * 1024  # Total current + previous bytes, per diagnostic stream.
RESERVE_BYTES = 64 * 1024 * 1024
MIN_FREE_BYTES = 1024 ** 3
MIN_FREE_INODES = 4096
RESERVE_NAME = '.ci-terminal-reserve'
STATUS_BYTES = 4096
STATVFS = os.fstatvfs


def canonical(root):
    root = Path(root)
    if (not root.is_absolute() or root.resolve(strict=True) != root or not root.is_dir()
            or any(p.is_symlink() for p in (root, *root.parents))):
        raise RuntimeError('STORAGE_PATH')
    return root


def identity(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError('STORAGE_PATH')
    return info.st_dev, info.st_ino


def exclusive(path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    return os.fdopen(fd, 'wb')


class BoundedStream:
    def __init__(self, root, name, *, limit=LOG_BYTES):
        self.root = canonical(root)
        if name not in {'runner.log', 'pytest.log'} or type(limit) is not int or limit < 2:
            raise RuntimeError('STORAGE_PATH')
        self.path = self.root / name
        self.previous = self.root / (name + '.previous')
        self.receipt = self.root / (name + '.stream.json')
        if any(os.path.lexists(p) for p in (self.path, self.previous, self.receipt)):
            raise RuntimeError('STORAGE_PATH')
        self.root_identity = self.root.stat().st_dev, self.root.stat().st_ino
        self.stream = exclusive(self.path)
        self.identities = {self.path: identity(self.path)}
        self.part_limit = limit // 2
        self.observed = 0
        self.digest = hashlib.sha256()

    def check(self):
        if canonical(self.root).stat().st_dev != self.root_identity[0] or self.root.stat().st_ino != self.root_identity[1]:
            raise RuntimeError('STORAGE_CHANGED')
        for path, pin in self.identities.items():
            if identity(path) != pin:
                raise RuntimeError('STORAGE_CHANGED')
        if self.previous not in self.identities and os.path.lexists(self.previous):
            raise RuntimeError('STORAGE_CHANGED')

    def write(self, data):
        if type(data) is not bytes:
            raise TypeError('STORAGE_BYTES')
        self.check()
        self.observed += len(data)
        self.digest.update(data)
        view = memoryview(data)
        while view:
            if self.stream.tell() == self.part_limit:
                self.stream.flush()
                self.stream.close()
                self.check()
                os.replace(self.path, self.previous)
                self.identities = {self.previous: identity(self.previous)}
                self.stream = exclusive(self.path)
                self.identities[self.path] = identity(self.path)
            size = min(len(view), self.part_limit-self.stream.tell())
            self.stream.write(view[:size])
            view = view[size:]

    def close(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.check()
        self.stream.close()
        retained = sum(path.stat().st_size for path in self.identities)
        value = {'schema': 1, 'observed_bytes': self.observed, 'retained_bytes': retained,
                 'dropped_bytes': self.observed-retained, 'truncated': self.observed != retained,
                 'full_stream_sha256': self.digest.hexdigest(), 'full_raw_retained': self.observed == retained}
        with exclusive(self.receipt) as stream:
            stream.write((json.dumps(value, sort_keys=True)+'\n').encode())
        return value

    def abort(self):
        self.stream.close()


def write_status(root, value):
    data = (json.dumps(value, sort_keys=True)+'\n').encode()
    if len(data) > STATUS_BYTES:
        raise RuntimeError('STORAGE_STATUS')
    path = root / 'storage-status.json'
    identity(path)
    fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
    try:
        os.pwrite(fd, data.ljust(STATUS_BYTES, b' '), 0)
        os.fsync(fd)
    finally:
        os.close(fd)


def prepare(root, *, reserve_bytes=RESERVE_BYTES):
    root = canonical(root)
    if type(reserve_bytes) is not int or reserve_bytes <= 0:
        raise RuntimeError('STORAGE_PATH')
    names = [RESERVE_NAME, 'storage-status.json']
    if any(os.path.lexists(root / name) for name in names):
        raise RuntimeError('STORAGE_PATH')
    with exclusive(root / RESERVE_NAME) as stream:
        os.posix_fallocate(stream.fileno(), 0, reserve_bytes)
        os.fsync(stream.fileno())
    pin = identity(root / RESERVE_NAME)
    with exclusive(root / 'storage-status.json') as stream:
        stream.write(b' ' * STATUS_BYTES)
        os.fsync(stream.fileno())
    write_status(root, {'schema': 1, 'state': 'reserved', 'reason': None,
                       'reserve_identity': list(pin), 'free_bytes': None, 'free_inodes': None})
    # Allocate directory entries before decoding/testing. Blank collection/exit
    # placeholders are explicitly invalid, never fabricated zero/pass evidence.
    for name in ('session.jsonl', 'discovered.jsonl', 'phases.jsonl', 'subtests.jsonl',
                 'collection-errors.jsonl', 'deselected.jsonl', 'failures.jsonl',
                 'failure-signatures.jsonl', 'started.jsonl', 'collected.json',
                 'pytest-exit-code.txt', 'tee-exit-code.txt', 'coverage.json'):
        with exclusive(root / name):
            pass


class StoragePressure:
    def __init__(self, root):
        self.root = canonical(root)
        self.root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.root_identity = self.root.stat().st_dev, self.root.stat().st_ino
        self.status_identity = identity(self.root / 'storage-status.json')
        self.status = json.loads((self.root / 'storage-status.json').read_text())
        if (type(self.status.get('schema')) is not int or self.status['schema'] != 1
                or self.status.get('state') != 'reserved' or self.status.get('reason') is not None
                or type(self.status.get('reserve_identity')) is not list
                or any(type(n) is not int for n in self.status['reserve_identity'])
                or self.status.get('reserve_identity') != list(identity(self.root / RESERVE_NAME))):
            os.close(self.root_fd)
            raise RuntimeError('STORAGE_CHANGED')
        self.stopped = False
        self.reason = None

    def release(self):
        info = canonical(self.root).stat()
        if ((info.st_dev, info.st_ino) != self.root_identity
                or identity(self.root / 'storage-status.json') != self.status_identity):
            raise RuntimeError('STORAGE_CHANGED')
        path = self.root / RESERVE_NAME
        if self.status['state'] == 'reserved':
            if list(identity(path)) != self.status['reserve_identity']:
                raise RuntimeError('STORAGE_CHANGED')
            path.unlink()  # Only the fresh, pinned reserve; never a scratch root.
            self.status['state'] = 'released'

    def sample(self, values=None):
        if self.stopped:
            return True
        try:
            values = STATVFS(self.root_fd) if values is None else values
            numbers = (values.f_bavail, values.f_frsize, values.f_favail)
            if any(type(n) is not int or n < 0 for n in numbers) or values.f_frsize == 0:
                raise ValueError
            free = values.f_bavail * values.f_frsize
            self.status.update(free_bytes=free, free_inodes=values.f_favail)
            reason = ('byte-pressure' if free <= MIN_FREE_BYTES else
                      'inode-pressure' if values.f_favail <= MIN_FREE_INODES else None)
        except (OSError, ValueError, AttributeError):
            reason = 'observation-error'
        if reason:
            self.stopped = True
            self.reason = reason
            self.release()  # Return headroom before writing interruption evidence.
            self.status.update(state='pressure-stopped', reason=reason)
        write_status(self.root, self.status)
        return self.stopped

    def close(self):
        try:
            self.release()
            write_status(self.root, self.status)
        finally:
            os.close(self.root_fd)


def process_identity(pid):
    # A supervised sibling of this watcher, not a PID supplied by test metadata.
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return int(fields[1]), int(fields[19])  # parent PID and start tick, Linux ABI.


def watch(root, pid):
    if type(pid) is not int or pid <= 0:
        raise RuntimeError('STORAGE_PROCESS')
    try:
        pin = process_identity(pid)
    except FileNotFoundError:
        return 0  # Parent wait retains the actual short-lived child's exit.
    if pin[0] != os.getppid():
        raise RuntimeError('STORAGE_PROCESS')
    guard = StoragePressure(root)
    try:
        while True:
            try:
                if process_identity(pid) != pin:
                    return 0
            except FileNotFoundError:
                return 0
            try:
                stopped = guard.sample()
            except (OSError, RuntimeError):
                stopped = True
            if stopped:
                # Recheck the exact unreaped child before a purpose-bound signal.
                if process_identity(pid) == pin:
                    os.kill(pid, signal.SIGINT)
                return 2
            time.sleep(1)
    finally:
        guard.close()


def pytest_configure(config):
    # Bash background jobs inherit SIGINT ignored; restore pytest's normal
    # interruption behavior only in this opt-in, supervised CI invocation.
    if os.environ.get('MTG_CI_STORAGE_GUARD') == '1':
        signal.signal(signal.SIGINT, signal.default_int_handler)


def main():
    sink = None
    try:
        operation, value, *rest = sys.argv[1:]
        root = canonical(value)
        if operation == 'reserve' and not rest:
            prepare(root)
        elif operation == 'watch' and len(rest) == 1:
            return watch(root, int(rest[0]))
        elif operation == 'release' and not rest:
            if json.loads((root / 'storage-status.json').read_text()).get('state') == 'reserved':
                StoragePressure(root).close()
        elif operation == 'stream' and len(rest) == 1:
            sink = BoundedStream(root, rest[0])
            for data in iter(lambda: sys.stdin.buffer.read(65536), b''):
                sink.write(data)
            sink.close()
        else:
            raise RuntimeError('STORAGE_ARGUMENTS')
        return 0
    except (OSError, RuntimeError, ValueError, TypeError):
        if sink is not None:
            sink.abort()
        # Drain even a failed sink: do not cause a private producer BrokenPipe.
        for _ in iter(lambda: sys.stdin.buffer.read(65536), b''):
            pass
        print('CI_BACKEND_STORAGE_ERROR', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
