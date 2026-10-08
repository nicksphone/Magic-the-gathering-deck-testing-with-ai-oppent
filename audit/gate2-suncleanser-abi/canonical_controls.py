"""Bounded full canonical auxiliary controls; never alter the 155-name inventory."""
import gzip
import json
from pathlib import Path

import inventory as inv
import test_suncleanser_desired as s


def load_controls(names):
    proof = json.loads((s.HERE / 'provenance.json').read_text())
    bulk = Path(proof['bulk_path'])
    assert inv.sha(bulk) == proof['bulk_sha256']
    rows = {name: [] for name in names}
    size = 0
    with gzip.open(bulk, 'rb') as stream:
        for count in range(1, inv.MAX_RECORDS + 1):
            line = stream.readline(inv.MAX_LINE_BYTES + 1)
            if not line:
                break
            size += len(line)
            assert len(line) <= inv.MAX_LINE_BYTES and size <= inv.MAX_EXPANDED_BYTES
            raw = json.loads(line)
            if raw.get('name') in rows and raw.get('lang') == 'en':
                rows[raw['name']].append(raw)
        else:
            raise AssertionError('Canonical record bound exceeded')
    assert inv.sha(bulk) == proof['bulk_sha256']
    assert all(len(values) == 1 for values in rows.values()), 'Auxiliary join must be unique'
    return {name: values[0] for name, values in rows.items()}, {
        'bulk_sha256': proof['bulk_sha256'], 'records': count-1, 'expanded_bytes': size,
        'join': 'unique-English-name-representative', 'scope': 'auxiliary control, not retained155 admission expansion'}
