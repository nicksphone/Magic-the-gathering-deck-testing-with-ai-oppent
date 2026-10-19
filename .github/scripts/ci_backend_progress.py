"""Passive, nonfinal public progress; raw ledgers remain runner-private."""
from collections import Counter
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import sys
import time


INTERVAL_SECONDS = 60
MAX_RECORD_BYTES = 8 * 1024 * 1024

# Isolated mode must not import backend code or honor a private PYTHONPATH.
helper = Path(__file__).absolute().with_name('ci_backend_metadata.py')
if any(path.is_symlink() for path in (*helper.parents, helper)):
    raise RuntimeError('PATH_REJECTED')
spec = importlib.util.spec_from_file_location('progress_public_metadata', helper)
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)
git = metadata.git


class Tail:
    """Consume complete JSONL records once; never normalize away an ancestor."""

    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.identity = None
        self.pending = b''
        self.codes = set()
        self.blocked = False

    def read(self):
        if self.blocked:
            return []
        if metadata.has_symlink_component(self.path):
            self.codes.add('PATH_REJECTED')
            self.blocked = True
            return []
        try:
            if not self.path.exists():
                if self.identity is not None:
                    self.codes.add('LEDGER_REPLACED')
                    self.blocked = True
                return []
            if not self.path.is_file():
                self.codes.add('PATH_REJECTED')
                self.blocked = True
                return []
            stat = self.path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if self.identity is not None and (identity != self.identity or stat.st_size < self.offset):
                self.codes.add('LEDGER_REPLACED')
                self.blocked = True
                return []
            self.identity = identity
            result = []
            with self.path.open('rb') as stream:
                stream.seek(self.offset)
                while data := stream.read(65536):
                    self.offset += len(data)
                    lines = (self.pending + data).split(b'\n')
                    self.pending = lines.pop()
                    for line in lines:
                        try:
                            if len(line) > MAX_RECORD_BYTES:
                                raise ValueError
                            row = metadata.json_value(line.decode('utf-8'))
                            if type(row) is not dict:
                                raise ValueError
                            result.append(row)
                        except (ValueError, UnicodeError, metadata.MetadataError):
                            self.codes.add('LEDGER_INVALID')
                    if len(self.pending) > MAX_RECORD_BYTES:
                        self.codes.add('LEDGER_INVALID')
                        self.blocked = True
                        self.pending = b''
                        break
            return result
        except OSError:
            self.codes.add('LEDGER_UNAVAILABLE')
            return []


class Progress:
    def __init__(self, evidence, source):
        self.evidence, self.source = Path(evidence), Path(source)
        self.tails = {name: Tail(self.evidence / name) for name in (
            'session.jsonl', 'discovered.jsonl', 'collected.json', 'started.jsonl', 'phases.jsonl')}
        self.public = None
        self.commit = None
        self.state = 'before_session'
        self.discovered, self.collected, self.started, self.completed = set(), set(), set(), set()
        self.collection_seen = False
        self.phases = {}
        self.counts = Counter()
        self.last_started = self.last_reported = self.last_completed = None
        self.codes = set()

    def identity(self, nodeid):
        return {'node_sha256': metadata.node(nodeid), 'public_test': self.public.resolve(nodeid)}

    def observe(self):
        row = {'schema_version': 1, 'nonfinal': True, 'source_commit': None,
               'session_state': 'before_session',
               'counts': {'discovered': 0, 'collected': 0, 'started': 0, 'completed': 0,
                          'failed_phases': 0, 'skipped_phases': 0, 'xfail_phases': 0},
               'phase_counts': {}, 'last_started': None, 'last_reported': None,
               'last_completed': None, 'disk_free_bytes': None, 'disk_available_bytes': None,
               'degraded_codes': []}
        if any(metadata.has_symlink_component(path) or not path.is_dir()
               for path in (self.evidence, self.source)) or metadata.has_symlink_component(self.source / '.git'):
            row['degraded_codes'] = ['PATH_REJECTED']
            return row
        try:
            if self.public is None:
                self.commit = git(self.source, 'rev-parse', 'HEAD').strip()
                if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', self.commit):
                    raise ValueError
                self.public = metadata.PublicDefinitions(self.source, self.commit)
            commit_path = self.evidence / 'source-head.txt'
            if metadata.has_symlink_component(commit_path):
                row['degraded_codes'] = ['PATH_REJECTED']
                return row
            if commit_path.exists() and metadata.read_text(self.evidence, 'source-head.txt').strip() != self.commit:
                raise ValueError
        except (OSError, ValueError, UnicodeError, metadata.MetadataError):
            row['degraded_codes'] = ['SOURCE_UNAVAILABLE']
            return row
        row['source_commit'] = self.commit
        for name, tail in self.tails.items():
            for value in tail.read():
                try:
                    if name == 'session.jsonl':
                        event = value['event']
                        if event == 'start' and self.state == 'before_session':
                            self.state = 'collecting'
                        elif event == 'finish' and self.state in ('collecting', 'running'):
                            if type(value['exitstatus']) is not int or not 0 <= value['exitstatus'] <= 255:
                                raise ValueError
                            self.state = 'finished'
                        else:
                            raise ValueError
                    elif name == 'collected.json':
                        nodes = value['nodeids']
                        metadata.node_list(nodes)
                        if self.collection_seen or len(nodes) != len(set(nodes)):
                            raise ValueError
                        self.collected = set(nodes)
                        self.collection_seen = True
                        if self.state != 'finished':
                            self.state = 'running'
                    else:
                        nodeid = value['nodeid']
                        metadata.node(nodeid)
                        if name in ('discovered.jsonl', 'started.jsonl'):
                            target = self.discovered if name == 'discovered.jsonl' else self.started
                            if nodeid in target:
                                raise ValueError
                            target.add(nodeid)
                            if name == 'started.jsonl':
                                self.last_started = self.identity(nodeid)
                        else:
                            phase, outcome = value['phase'], value['outcome']
                            if phase not in ('setup', 'call', 'teardown') or outcome not in ('passed', 'failed', 'skipped'):
                                raise ValueError
                            key = (nodeid, phase)
                            if key in self.phases:
                                raise ValueError
                            self.phases[key] = outcome
                            self.counts[phase + '/' + outcome] += 1
                            self.counts['xfail'] += int('wasxfail' in value)
                            self.last_reported = {**self.identity(nodeid), 'phase': phase, 'outcome': outcome}
                            required = ('setup', 'call', 'teardown') if self.phases.get((nodeid, 'setup')) == 'passed' else ('setup', 'teardown')
                            if nodeid not in self.collected:
                                self.codes.add('LEDGER_INVALID')
                            elif nodeid not in self.completed and all((nodeid, p) in self.phases for p in required):
                                self.completed.add(nodeid)
                                self.last_completed = self.identity(nodeid)
                except (KeyError, TypeError, ValueError, SyntaxError, UnicodeError, metadata.MetadataError):
                    self.codes.add('LEDGER_INVALID')
            self.codes.update(tail.codes)
        if self.phases and not self.started:
            self.codes.add('START_LEDGER_MISSING')
        codes = self.codes | ({'PARTIAL_RECORD'} if any(t.pending for t in self.tails.values()) else set())
        try:
            stat = os.statvfs(self.evidence)
            row.update(disk_free_bytes=stat.f_bfree * stat.f_frsize,
                       disk_available_bytes=stat.f_bavail * stat.f_frsize)
        except OSError:
            codes.add('DISK_UNAVAILABLE')
        row.update(session_state=self.state, counts={
            'discovered': len(self.discovered), 'collected': len(self.collected),
            'started': len(self.started), 'completed': len(self.completed),
            'failed_phases': sum(v for k, v in self.counts.items() if k.endswith('/failed')),
            'skipped_phases': sum(v for k, v in self.counts.items() if k.endswith('/skipped')),
            'xfail_phases': self.counts['xfail']},
            phase_counts={k: v for k, v in self.counts.items() if '/' in k},
            last_started=self.last_started, last_reported=self.last_reported,
            last_completed=self.last_completed, degraded_codes=sorted(codes))
        return row


def due(now, previous_time, previous_state, state):
    return previous_time is None or now - previous_time >= INTERVAL_SECONDS or state != previous_state


def main(args=None):
    args = sys.argv[1:] if args is None else args
    if len(args) != 2:
        print('CI_PROGRESS_ARGUMENT_ERROR', file=sys.stderr)
        return 2
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    progress = Progress(*args)
    started_at = time.monotonic()
    observation_sequence = 0
    previous_time = previous_state = None
    while True:
        try:
            row = progress.observe()
            now = time.monotonic()
            elapsed = now - started_at
            if not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError
        except Exception:
            print('CI_PROGRESS_INTERNAL_DEGRADED', file=sys.stderr)
            return 2
        if stopping or due(now, previous_time, previous_state, row['session_state']):
            row.update(observation_sequence=observation_sequence, elapsed_seconds=elapsed)
            try:
                print(json.dumps(row, sort_keys=True), flush=True)
            except OSError:
                return 2
            previous_time, previous_state = now, row['session_state']
            observation_sequence += 1
        if stopping or row['session_state'] == 'finished':
            return 0
        time.sleep(1)


if __name__ == '__main__':
    raise SystemExit(main())
