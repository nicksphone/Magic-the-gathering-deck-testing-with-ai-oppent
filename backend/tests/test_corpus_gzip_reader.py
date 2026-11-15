"""Compressed JSON-lines protocol and ownership, without canonical card data."""
import gzip
import io
import json
import os

import pytest

from scripts import corpus_knowledge_readiness as corpus


PAYLOAD = b'{"protocol": true}\n\n  \n{"sequence": 2}\n'
ROWS = [{'protocol': True}, {'sequence': 2}]


def test_caller_owned_stream_decodes_lines_and_stays_open():
    raw = io.BytesIO(gzip.compress(PAYLOAD))
    assert list(corpus.read_cards_gzip(raw)) == ROWS
    assert not raw.closed
    raw.seek(0)
    reader = corpus.read_cards_gzip(raw)
    assert next(reader) == ROWS[0]
    reader.close()
    assert not raw.closed


def test_caller_owned_stream_stays_open_after_decode_error():
    raw = io.BytesIO(gzip.compress(b'{invalid json}\n'))
    with pytest.raises(json.JSONDecodeError):
        list(corpus.read_cards_gzip(raw))
    assert not raw.closed


@pytest.mark.parametrize('path_kind', ['path', 'string', 'bytes'])
def test_file_path_decodes_nonempty_json_lines(tmp_path, path_kind):
    path = tmp_path / 'protocol.jsonl.gz'
    path.write_bytes(gzip.compress(PAYLOAD))
    source = path if path_kind == 'path' else str(path) if path_kind == 'string' else os.fsencode(path)
    assert list(corpus.read_cards_gzip(source)) == ROWS
