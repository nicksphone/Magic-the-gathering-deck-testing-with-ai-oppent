"""Internal protocol only: no injected frame is announced or resolved in a game."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from rules_engine import events
from tests.agent_control_facts import ROWS
from tests.test_source_linked_exile import position, raw_card, Zone

PREIMAGE = (Path(__file__).parent / 'fixtures/agent_self_entry/targeted_trigger_clause_preimage.py.txt').read_bytes()
assert hashlib.sha256(PREIMAGE).hexdigest() == 'bca775ce96d421be02247d284990474b1d2f4b767d76d4a68a8231cc78bdea49'
NAMESPACE = dict(vars(events))
exec(compile(PREIMAGE, 'immutable229_targeted_trigger_clause', 'exec'), NAMESPACE)
BASELINE = NAMESPACE['_targeted_trigger_clause']


@pytest.mark.parametrize('case', ['transformed', 'entry_transform', 'malformed_self', 'different_subject', 'source_none'])
def test_existing_generic_resolution_protocol_falls_through(case):
    state, _ = position(1)
    source = raw_card(state, ROWS['Agent of Treachery'], 1, Zone.HAND)
    clause = 'When this creature enters or transforms into Agent of Treachery, gain control of target permanent.'
    if case == 'malformed_self':
        clause = 'When this creature enters, gain control of target permanent. Unknown suffix.'
    elif case == 'different_subject':
        clause = 'When another creature enters, gain control of target permanent.'
    item = SimpleNamespace(effect_key='change_control', source_card_id=None if case == 'source_none' else source.id,
        payload={'__trigger_event': 'transformed' if case in {'transformed', 'source_none'} else 'enters_battlefield',
                 '__trigger_full_clause': clause,
                 '__trigger_resolution_text': 'gain control of target permanent.'})
    assert not state.stack
    assert BASELINE(state, item) == clause
    assert events._targeted_trigger_clause(state, item) == clause
    assert not state.stack


@pytest.mark.parametrize('suffix', [' Unknown suffix.', ' (Unknown parenthetical.)'])
def test_unqualified_self_protocol_without_generic_marker_stays_untargeted(suffix):
    state, _ = position(1)
    source = raw_card(state, ROWS['Agent of Treachery'], 1, Zone.HAND)
    item = SimpleNamespace(effect_key='change_control', source_card_id=source.id,
        payload={'__trigger_event': 'enters_battlefield', '__trigger_full_clause':
                 'When this creature enters, gain control of target permanent.' + suffix})
    assert not state.stack
    assert BASELINE(state, item) is None
    assert events._targeted_trigger_clause(state, item) is None


def test_complete_new_self_protocol_is_additive_not_a_legacy_certificate():
    state, _ = position(1)
    source = raw_card(state, ROWS['Agent of Treachery'], 1, Zone.HAND)
    clause = 'When this creature enters, gain control of target permanent.'
    item = SimpleNamespace(effect_key='change_control', source_card_id=source.id,
        payload={'__trigger_event': 'enters_battlefield', '__trigger_full_clause': clause})
    assert BASELINE(state, item) is None
    assert events._targeted_trigger_clause(state, item) == clause
    assert not state.stack
