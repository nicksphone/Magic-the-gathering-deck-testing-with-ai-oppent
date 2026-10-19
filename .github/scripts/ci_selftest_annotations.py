"""Forward the public selftest stream; annotate only hashed failure parent IDs."""
import hashlib
import re
import sys


CHUNK_BYTES = 4096
LINE_BYTES = 4096
MAX_ANNOTATIONS = 512
HEADER = re.compile(
    rb'(?P<status>FAIL|ERROR): (?P<method>test_[A-Za-z0-9_]+) '
    rb'\((?P<parent>test_[A-Za-z0-9_]+\.[A-Za-z_][A-Za-z0-9_]*\.(?P=method))\)'
    rb'(?: (?:\([^\x00-\x1f\x7f]*\)|\[[^\x00-\x1f\x7f]*\]'
    rb'(?: \([^\x00-\x1f\x7f]*\))?))?\r?\n')
IMPORT_ERROR = re.compile(
    rb'(?P<status>ERROR): (?P<method>test_[A-Za-z0-9_]+) '
    rb'\((?P<parent>unittest\.loader\._FailedTest\.(?P=method))\)\r?\n')


def forward(reader, output, notices):
    pending = b''
    overlong = False
    seen = set()
    status = 0
    try:
        while True:
            chunk = reader.readline(CHUNK_BYTES)
            if not chunk:
                break
            if output.write(chunk) != len(chunk):
                return 2
            output.flush()
            if not overlong:
                if len(pending) + len(chunk) > LINE_BYTES:
                    pending = b''
                    overlong = True
                else:
                    pending += chunk
            if not chunk.endswith(b'\n'):
                continue
            match = None if overlong else (
                HEADER.fullmatch(pending) or IMPORT_ERROR.fullmatch(pending))
            pending, overlong = b'', False
            if match is None:
                continue
            key = (match['status'], match['parent'])
            if key in seen:
                continue
            if len(seen) == MAX_ANNOTATIONS:
                status = 2
                continue
            seen.add(key)
            digest = hashlib.sha256(match['parent']).hexdigest().encode('ascii')
            notice = b'::error::' + match['status'] + b' ' + digest + b'\n'
            if notices.write(notice) != len(notice):
                return 2
            notices.flush()
    except (OSError, ValueError):
        return 2
    return status


if __name__ == '__main__':
    sys.exit(forward(sys.stdin.buffer, sys.stdout.buffer, sys.stderr.buffer))
