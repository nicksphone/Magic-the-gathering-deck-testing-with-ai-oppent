"""Source metadata only: historical constructors remain inert strings."""
import ast
import hashlib
from pathlib import Path

import pytest

from tests.interface_scope_compatibility import restore_printed_protocol_source


ROOT = Path(__file__).parent
MODULE = 'test_events_apnap.py'
NAME = 'test_controller_scoped_etb_trigger_does_not_fire_for_opponent_creature'
OLD_SHA = '0b88c9de7bf599b7c2c181464d9a65079214c7a3500cdee117f66563cfbe4080'


def segment(source):
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.FunctionDef) and node.name == NAME]
    assert len(nodes) == 1
    return ast.get_source_segment(source, nodes[0])


def test_current_controller_constructor_restores_exact_original_function_hash():
    restored = restore_printed_protocol_source(MODULE, (ROOT / MODULE).read_text())
    assert hashlib.sha256(segment(restored).encode()).hexdigest() == OLD_SHA


def test_controller_constructor_restoration_is_idempotent():
    restored = restore_printed_protocol_source(MODULE, (ROOT / MODULE).read_text())
    assert restore_printed_protocol_source(MODULE, restored) == restored


def test_controller_helper_and_outside_hunk_mutations_are_rejected():
    source = (ROOT / MODULE).read_text()
    target = segment(source)
    for changed in (
        target.replace('_controller_etb_card(1)', '_unreviewed_controller_card(1)'),
        target + '\n    assert False',
        target + '\n    state.active_player = 2',
    ):
        assert changed != target
        with pytest.raises(AssertionError):
            restore_printed_protocol_source(MODULE, source.replace(target, changed, 1))


def test_original_golden_recipes_and_canonical_raw_remain_pinned():
    pins = {
        'rules_printed_facts_e4/UNCHANGED_FUNCTION_SHA256.json':
            '94a314f7a95f8a1f538f06c181c274324b2afef2d97414f8d1c8ce29dd7e3559',
        'interface_scope_compatibility/reviewed_task13_fixture_inverses.json':
            'f4e505e4cc13a7004cea39aca02e820de72c17675dc9232be9616c23d44c98bc',
        'entry_observers_S2/canonical.jsonl':
            '8f337660b08660748a0b47d9590a40e106303e578bff37277bbda05dd89018ba',
        'entry_observers_S2/provenance.json':
            '176023ccd22c6e1825e4a985ad373dff84734c0c203878b4cbf1cc127f4ba3d7',
    }
    for filename, digest in pins.items():
        assert hashlib.sha256((ROOT / 'fixtures' / filename).read_bytes()).hexdigest() == digest
