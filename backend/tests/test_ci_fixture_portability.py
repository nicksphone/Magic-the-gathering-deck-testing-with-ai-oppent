"""Audit receipts are opt-in; ordinary tests still verify canonical facts."""
import json

import pytest


def test_shared_facts_and_records_need_no_audit_phase(monkeypatch, tmp_path):
    import test_suncleanser_desired as fixture
    from tests import test_land_activation_paid as land

    monkeypatch.delenv('ADMISSION_PHASE', raising=False)
    monkeypatch.setattr(fixture, 'PHASE', None)
    output = tmp_path / 'not-created'
    monkeypatch.setattr(fixture, 'OUT', output)
    facts = fixture.facts.__wrapped__()
    state = fixture.g.position(facts, 1)
    fixture.record('ordinary', state)
    land.record('ordinary-land', state)
    assert facts['Suncleanser']['id'] == '3644df41-b690-4581-ac7d-c85cec75411f'
    assert not output.exists()


def test_explicit_audit_phase_keeps_exclusive_canonical_receipts(monkeypatch, tmp_path):
    import test_suncleanser_desired as fixture

    monkeypatch.setattr(fixture, 'PHASE', 'portable-audit')
    monkeypatch.setattr(fixture, 'OUT', tmp_path)
    facts = fixture.facts.__wrapped__()
    state = fixture.g.position(facts, 1)
    fixture.record('observed', state, canonical=True)
    assert json.loads((tmp_path / 'portable-audit-facts.json').read_text())['cards']
    receipt = json.loads((tmp_path / 'portable-audit-observed.json').read_text())
    assert receipt['observed'] == {'canonical': True}
    assert receipt['snapshot'] == json.loads(json.dumps(fixture.serialize_match_snapshot(state)))
    with pytest.raises(FileExistsError):
        fixture.record('observed', state)
