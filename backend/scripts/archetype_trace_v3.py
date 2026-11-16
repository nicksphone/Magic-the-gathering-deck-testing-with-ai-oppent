"""Bounded private JSONL with a domain-separated, ordered SHA256 record chain."""
from contextlib import contextmanager, nullcontext
import hashlib
import json
import re
import time

MAX_TRACE_BYTES = 64*1024*1024
CHECKPOINT_INTERVAL = 64
CHAIN_KEYS = frozenset({'sequence', 'previous_record_sha256', 'record_sha256'})
KINDS = frozenset({'initial', 'action', 'rejected', 'final'})


class TraceLimit(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def record_digest(value):
    return hashlib.sha256(b'mtg-archetype-v3-record\0'+canonical(value)).hexdigest()


def is_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


class CpuAccounting:
    """Non-overlapping process CPU buckets; total process CPU is separate."""
    def __init__(self):
        self.seconds = {}
        self.calls = {}
        self.active = False

    @contextmanager
    def measure(self, name):
        if self.active:
            yield
            return
        started = time.process_time()
        self.active = True
        try:
            yield
        finally:
            self.seconds[name] = self.seconds.get(name, 0.0)+time.process_time()-started
            self.calls[name] = self.calls.get(name, 0)+1
            self.active = False

    def snapshot(self):
        total = time.process_time()
        return {'category_seconds': dict(self.seconds), 'category_calls': dict(self.calls),
                'process_cpu_seconds': total,
                'unattributed_cpu_seconds': max(0.0, total-sum(self.seconds.values()))}


def checkpoint_reasons(before, after, step, *, final=False):
    if type(step) is not int or step < 0 or type(final) is not bool:
        raise ValueError('Invalid checkpoint boundary')
    reasons = []
    if (step+1) % CHECKPOINT_INTERVAL == 0:
        reasons.append('periodic')
    if step % 100 == 0:
        reasons.append('handler')
    if any(before.get(key) != after.get(key) for key in (
            'pending_mechanic_choice', 'pending_trigger_order', 'pending_replacement_choice')):
        reasons.append('choice')
    if before.get('pregame_pending') != after.get('pregame_pending'):
        reasons.append('pregame')
    if final:
        reasons.append('final')
    return reasons


class TraceWriter:
    def __init__(self, stream, *, max_bytes=MAX_TRACE_BYTES, accounting=None):
        if type(max_bytes) is not int or not 0 < max_bytes <= MAX_TRACE_BYTES:
            raise ValueError('Invalid trace quota')
        self.stream, self.max_bytes, self.accounting = stream, max_bytes, accounting
        self.sequence, self.total_bytes, self.last_digest = 0, 0, None
        self.closed = False

    def measure(self, name):
        return self.accounting.measure(name) if self.accounting else nullcontext()

    def emit(self, value):
        if (type(value) is not dict or CHAIN_KEYS & value.keys() or self.closed
                or value.get('kind') not in KINDS
                or (self.sequence == 0) != (value.get('kind') == 'initial')):
            raise ValueError('Invalid trace record')
        with self.measure('trace_encode_hash'):
            row = {**value, 'sequence': self.sequence,
                   'previous_record_sha256': self.last_digest}
            sha = record_digest(row)
            data = canonical({**row, 'record_sha256': sha})+b'\n'
        if self.total_bytes+len(data) > self.max_bytes:
            raise TraceLimit('Trace quota exceeded before next record')
        with self.measure('trace_write_flush'):
            written = 0
            while written < len(data):
                size = self.stream.write(data[written:])
                if type(size) is not int or not 0 < size <= len(data)-written:
                    raise OSError('Trace write did not make valid progress')
                written += size
            self.stream.flush()
        self.total_bytes += len(data)
        self.last_digest = sha
        self.sequence += 1
        self.closed = value['kind'] == 'final'


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate trace key')
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError('Nonfinite trace number')


def read_records(stream, *, max_bytes=MAX_TRACE_BYTES):
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_TRACE_BYTES:
        raise ValueError('Invalid trace quota')
    sequence, total, previous, final = 0, 0, None, False
    while True:
        raw = stream.readline(max_bytes-total+1)
        if not raw:
            break
        total += len(raw)
        if total > max_bytes:
            raise TraceLimit('Trace exceeds declared quota')
        if final or not raw.endswith(b'\n'):
            raise ValueError('Unexpected or incomplete trace record')
        try:
            row = json.loads(raw, object_pairs_hook=_unique, parse_constant=_invalid_constant)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise ValueError('Invalid trace JSON') from exc
        if (type(row) is not dict or not CHAIN_KEYS.issubset(row)
                or type(row['sequence']) is not int or row['sequence'] != sequence
                or row['previous_record_sha256'] != previous
                or not is_sha(row['record_sha256']) or row.get('kind') not in KINDS
                or (sequence == 0) != (row.get('kind') == 'initial')):
            raise ValueError('Trace ordering or binding differs')
        body = {key:value for key,value in row.items() if key != 'record_sha256'}
        if record_digest(body) != row['record_sha256']:
            raise ValueError('Trace record digest differs')
        previous, final = row['record_sha256'], row['kind'] == 'final'
        sequence += 1
        yield row
    if not sequence or not final:
        raise ValueError('Trace has no complete final record')
