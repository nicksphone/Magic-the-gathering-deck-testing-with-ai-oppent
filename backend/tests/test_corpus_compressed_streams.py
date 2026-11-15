"""Literal bulk/artifact formats; no canonical card or gameplay facts."""
from contextlib import closing
import gzip
import json
import sqlite3

import pytest

from scripts import corpus_knowledge_readiness as corpus
from scripts.sync_all_card_knowledge import read_cards


ROWS = [{'protocol': True}, {'sequence': 2}]
LINES = b'{"protocol": true}\n\n  \n{"sequence": 2}\n'


def test_plain_json_lines(tmp_path):
    path = tmp_path / 'protocol.jsonl'
    path.write_bytes(LINES)
    assert list(read_cards(path)) == ROWS


def test_plain_json_array(tmp_path):
    path = tmp_path / 'protocol.json'
    path.write_text(json.dumps(ROWS), encoding='utf-8')
    assert list(read_cards(path)) == ROWS


def test_gzip_json_lines(tmp_path):
    path = tmp_path / 'protocol.jsonl.gz'
    path.write_bytes(gzip.compress(LINES))
    assert list(read_cards(path)) == ROWS


def test_gzip_json_array(tmp_path):
    path = tmp_path / 'protocol.json.gz'
    path.write_bytes(gzip.compress(json.dumps(ROWS).encode('utf-8')))
    assert list(read_cards(path)) == ROWS


def test_empty_gzip_json_lines(tmp_path):
    path = tmp_path / 'protocol.jsonl.gz'
    path.write_bytes(gzip.compress(b'\n \n'))
    assert list(read_cards(path)) == []


def test_malformed_gzip_is_rejected(tmp_path):
    path = tmp_path / 'protocol.jsonl.gz'
    path.write_bytes(b'not a gzip stream')
    with pytest.raises(gzip.BadGzipFile):
        list(read_cards(path))


def test_truncated_gzip_is_rejected(tmp_path):
    path = tmp_path / 'protocol.jsonl.gz'
    path.write_bytes(gzip.compress(LINES)[:-8])
    with pytest.raises(EOFError):
        list(read_cards(path))


def test_manifest_only_artifact_validates_in_owned_scratch(tmp_path):
    source = tmp_path / 'source.db'
    artifact = tmp_path / 'protocol.jsonl.gz'
    scratch = tmp_path / 'scratch.db'
    artifact.write_bytes(gzip.compress(json.dumps({
        'manifest': {'version': corpus.VERSION, 'snapshot': 'literal-format-protocol'},
    }).encode('utf-8') + b'\n'))
    with closing(sqlite3.connect(source)) as conn:
        conn.execute('CREATE TABLE cardknowledge (id INTEGER PRIMARY KEY)')
        conn.commit()
        before = corpus.file_hash(source)
        result = corpus.validate_artifact(conn, artifact, scratch,
                                          snapshot='literal-format-protocol', full_audit=False)
        assert result['validated_import_rows'] == 0
        assert result['source_snapshot_sha256'] == 'literal-format-protocol'
        assert result['artifact_sha256'] == corpus.file_hash(artifact)
        assert result['stored_row_hashes_verified'] and result['sqlite_transaction_committed']
        assert corpus.file_hash(source) == before
    assert scratch.is_file()


def test_artifact_snapshot_mismatch_removes_new_scratch(tmp_path):
    source = tmp_path / 'source.db'
    artifact = tmp_path / 'protocol.jsonl.gz'
    scratch = tmp_path / 'scratch.db'
    artifact.write_bytes(gzip.compress(json.dumps({
        'manifest': {'version': corpus.VERSION, 'snapshot': 'different-protocol'},
    }).encode('utf-8') + b'\n'))
    with closing(sqlite3.connect(source)) as conn:
        conn.execute('CREATE TABLE cardknowledge (id INTEGER PRIMARY KEY)')
        conn.commit()
        with pytest.raises(ValueError, match='different canonical snapshot'):
            corpus.validate_artifact(conn, artifact, scratch,
                                     snapshot='literal-format-protocol', full_audit=False)
    assert not scratch.exists()
