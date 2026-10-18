"""Literal source-text compatibility only; never execute the historical fixture."""
import hashlib
from pathlib import Path

import pytest

from tests import interface_scope_compatibility as api
from tests.test_interface_scope_76_mutations import function


MODULE = 'test_events_apnap.py'
NAME = 'test_sacrifice_emits_sacrifice_trigger_for_creature'
IDENTITY = MODULE + ':' + NAME


def test_canonical_fixture_inverse_preserves_all_historical_digest_operands():
    source = Path(__file__).with_name(MODULE).read_text()
    current = function(source, NAME)
    assert hashlib.sha256(current.encode()).hexdigest() == (
        '7969f39952949ec76c0010735c8f2ae41a7b25639e33ad2b479e36d1a63b4b29')
    restored = api.restore_printed_protocol_source(MODULE, source)
    historical = function(restored, NAME)
    assert hashlib.sha256(historical.encode()).hexdigest() == (
        'df7f2d08b8579ed6fe545a1582ba388d9cebb3afbbb337a619a113b83412cfe9')
    assert api.restore_printed_protocol_source(MODULE, restored) == restored
    assert len(api.EXPECTED_FUNCTIONS) == 60 and len(api.FINITE['functions']) == 14
    assert IDENTITY not in api.FINITE['functions']
    assert api.EXPECTED_FUNCTIONS[IDENTITY] == hashlib.sha256(historical.encode()).hexdigest()
    path = Path(__file__).parent / 'fixtures/rules_printed_facts_e4/UNCHANGED_FUNCTION_SHA256.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        '94a314f7a95f8a1f538f06c181c274324b2afef2d97414f8d1c8ce29dd7e3559')


@pytest.mark.parametrize('mutation', ('constructor', 'action', 'assertion', 'signature',
                                    'missing', 'duplicate'))
def test_fixture_inverse_rejects_inside_and_outside_source_changes(mutation):
    source = Path(__file__).with_name(MODULE).read_text()
    segment = function(source, NAME)
    if mutation == 'missing':
        changed = source.replace(segment, '', 1)
    elif mutation == 'duplicate':
        changed = source + '\n' + segment + '\n'
    else:
        before, after = {
            'constructor': ('owner=1,', 'owner=2,'),
            'action': ('sacrifice(state, 1,', 'sacrifice(state, 2,'),
            'assertion': ('item.controller == 1', 'item.controller == 2'),
            'signature': ('-> None:', '-> bool:'),
        }[mutation]
        assert before in segment
        changed_segment = segment.replace(before, after, 1)
        changed = source.replace(segment, changed_segment, 1)
    assert changed != source
    with pytest.raises(AssertionError):
        api.restore_printed_protocol_source(MODULE, changed)
