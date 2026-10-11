"""Paid entry calls preserve the raw Oracle argument through the trace fixture."""
import pytest

from rules_engine import events
from tests import test_trigger_instruction_compilation_audit as audit

TRACE_FIXTURE = audit.compilation_trace.__wrapped__


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_entry_trace_forwards_exact_raw_oracle_and_complete_effect(seat, monkeypatch, tmp_path):
    fixture = TRACE_FIXTURE(monkeypatch, tmp_path)
    trace = next(fixture)
    forwarded = events._trigger_from_oracle
    calls = []

    def observe(*args, **kwargs):
        if kwargs.get('event') == 'enters_battlefield':
            calls.append((args[1], kwargs.get('raw_entry_oracle')))
        return forwarded(*args, **kwargs)

    monkeypatch.setattr(events, '_trigger_from_oracle', observe)
    try:
        state, cid, action = audit.position('Cloudblazer', seat)
        raw = state.cards[cid].oracle_text
        library, life = list(state.players[seat].library), state.players[seat].life
        state = audit.pending(state, seat, action, 'Cloudblazer')
        entries = [value for source, value in calls if source == cid]
        assert entries and all(value == raw for value in entries)
        item = audit.item_for(state, cid)
        compiled = [row['compiled'] for row in trace
                    if row.get('source') == cid and row.get('event') == 'enters_battlefield']
        assert compiled and all(row['effect_key'] == item.effect_key for row in compiled)
        result = audit.passes(state)
        assert result.players[seat].hand == list(reversed(library[-2:]))
        assert result.players[seat].life == life + 2
    finally:
        next(fixture, None)
