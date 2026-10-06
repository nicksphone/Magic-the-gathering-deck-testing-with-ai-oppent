"""Immutable raw source evidence, not mechanic coverage certification."""
import hashlib
import json
from pathlib import Path

DIRECTORY = Path(__file__).parent / 'fixtures'


def test_transform_raw_records_and_existing_cathar_are_pinned():
    folder = DIRECTORY / 'human_transform_audit'
    provenance = json.loads((folder / 'provenance.json').read_text())
    raw = (folder / 'canonical.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == provenance['canonical_sha256']
    assert provenance['canonical_sha256'] == 'd5f3d85b5ede1e70b0572a75f5b0059df273d372ed84255b42092f4dc5423743'
    assert provenance['compressed_sha256'] == '17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13'
    assert provenance['records_scanned'] == 38690
    assert provenance['facts_modified'] is False and provenance['http_requests'] == 0
    rows = json.loads(raw)
    delver = rows['Delver of Secrets // Insectile Aberration']
    assert delver['object'] == 'card' and delver['layout'] == 'transform'
    assert delver['id'] == '6904ea20-e504-47da-95a0-08739fdde260'
    for name, row in rows.items():
        assert row['object'] == 'card'
        assert provenance['ids'][name] == {'id': row['id'], 'oracle_id': row['oracle_id']}
    assert [face['name'] for face in delver['card_faces']] == ['Delver of Secrets', 'Insectile Aberration']
    assert [face['power'] for face in delver['card_faces']] == ['1', '3']
    assert [face['toughness'] for face in delver['card_faces']] == ['1', '2']
    assert 'You may reveal that card.' in delver['card_faces'][0]['oracle_text']
    cathar = (DIRECTORY / 'cathar_canonical/0dbac7ce-a6fa-466e-b6ba-173cf2dec98e.json').read_bytes()
    assert hashlib.sha256(cathar).hexdigest() == '94233236a6701e7dc6ee9320241b56c40a5dcc9c0351d08bc6f41776df909faa'
    faces = json.loads(cathar)['card_faces']
    assert [face['name'] for face in faces] == ['Brutal Cathar', 'Moonrage Brute']
    assert [face['colors'] for face in faces] == [['W'], ['R']]
