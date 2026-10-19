"""Canonical audit data integrity only; no card family certification."""
import hashlib
import json
from pathlib import Path


def test_raw_canonical_human_flow_records_are_pinned_and_unchanged():
    directory = Path(__file__).parent / 'fixtures/human_flow_audit'
    content = (directory / 'canonical.json').read_bytes()
    raw = json.loads(content)
    provenance = json.loads((directory / 'provenance.json').read_text())
    assert hashlib.sha256(content).hexdigest() == provenance['canonical_json_sha256']
    assert provenance['http_requests'] == 0 and not provenance['facts_modified']
    assert provenance['rows_scanned'] == 38690
    assert len(raw) == 8
    for name, pin in provenance['rows'].items():
        assert raw[name]['name'] == name
        assert raw[name]['id'] == pin['id'] and raw[name]['oracle_id'] == pin['oracle_id']
    committed = json.loads((Path(__file__).parent / 'fixtures/activated_sacrifice_identity/canonical.json').read_text())
    for name in ('Hangarback Walker', 'Phyrexian Tower', 'Glorious Anthem'):
        if name in committed:
            for field in ('id', 'oracle_id', 'oracle_text', 'mana_cost', 'power', 'toughness', 'type_line', 'keywords'):
                assert raw[name].get(field) == committed[name].get(field), (name, field)
    shark = next(row for row in json.loads((Path(__file__).parent / 'fixtures/ai_oracle_semantics.json').read_text())
                 if row['name'] == 'Shark Typhoon')
    for field in ('oracle_text', 'mana_cost', 'type_line', 'colors'):
        assert raw['Shark Typhoon'][field] == shark[field], field
