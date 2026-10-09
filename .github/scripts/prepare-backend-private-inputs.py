"""Restore the sealed private regression input without printing its contents."""
import base64
import gzip
import hashlib
import io
import os
from pathlib import Path
import sys

WITNESS_SHA256 = 'c2eac237fe12c4783e65ccf692c239591378e3d6ad893fcbec31cecf8af9f653'
MAX_BYTES = 8_000_000


def restore_witness(environ, directory):
    parts = [environ.get(f'MTG_HEAT_WITNESS_{number:02d}', '') for number in range(1, 14)]
    if not all(parts) or any(len(part) > 48_000 for part in parts):
        raise ValueError('Protected Heat regression input is missing or oversized')
    try:
        encoded = base64.b64decode(''.join(parts), validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as stream:
            payload = stream.read(MAX_BYTES + 1)
    except (ValueError, OSError, EOFError):
        raise ValueError('Protected Heat regression input cannot be decoded') from None
    if len(payload) > MAX_BYTES or hashlib.sha256(payload).hexdigest() != WITNESS_SHA256:
        raise ValueError('Protected Heat regression input failed its sealed hash')
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    destination = directory / 'sealed-self-removal-witness.json'
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(payload)
    return destination


if __name__ == '__main__':
    restore_witness(os.environ, sys.argv[1])
    print('Protected Heat regression input restored and sealed hash verified')
