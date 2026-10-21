"""Real helper registration scope; no shared module or canonical-data repair."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TARGET = 'Wandering Archaic // Explore the Vastlands'
LEGACY_SHA = 'ffb6877741439134938257c07262d58dcfd56050eb221211e20d8c6e7de7b332'
SOURCES_SHA = 'cb515e9c199a4dba208e3a9c22af8bec840dcc265aeffe9b453706d39d56f994'


def _fresh_helper():
    name = '_remaining_named_binding_scope_' + uuid4().hex
    spec = importlib.util.spec_from_file_location(name, HERE / 'remaining_named_birth_fixtures.py')
    assert spec is not None and spec.loader is not None
    subject = importlib.util.module_from_spec(spec)
    assert name not in sys.modules
    spec.loader.exec_module(subject)
    assert name not in sys.modules
    return subject


def _legacy_tables():
    encoded = (HERE / 'fixtures/modal_spell_faces.json').read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == LEGACY_SHA
    # Separate imports decode the same physical JSON into distinct table/row identities.
    bare, namespaced = json.loads(encoded), json.loads(encoded)
    assert bare == namespaced and bare is not namespaced
    assert bare[TARGET] is not namespaced[TARGET]
    return bare, namespaced


def _official_raw():
    encoded = (HERE / 'fixtures/browser_positive83/SOURCES.json').read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == SOURCES_SHA
    record = json.loads(encoded)['cards'][TARGET]
    encoded = (ROOT / record['path']).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == record['file_sha256']
    assert record['location'] == ['line', 25]
    raw = json.loads(encoded.splitlines()[24])
    canonical = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == record['object_sha256']
    assert (raw['object'], raw['name'], raw['id'], raw['oracle_id'], len(raw)) == (
        'card', TARGET, record['id'], record['oracle_id'], record['fields'])
    return raw


def _order_profile(reverse):
    subject = _fresh_helper()
    bare, namespaced = _legacy_tables()
    first, second = (namespaced, bare) if reverse else (bare, namespaced)
    before = deepcopy((first, second))
    expected = _official_raw()
    subject.bind_modal(first, TARGET)
    assert subject.modal_raw(first, TARGET) == expected
    subject.bind_modal(second, TARGET)
    # The second registration must not revoke the first genuine caller's admission.
    with patch.object(subject, 'raw_card', wraps=subject.raw_card) as lookup:
        admitted = subject.modal_raw(first, TARGET)
        print('\n::notice title=Modal fixture binding observation::' + json.dumps({
            'schema': 1,
            'order': 'reverse' if reverse else 'forward',
            'first_admitted': admitted is not None,
            'raw_lookup_calls': lookup.call_count,
        }, separators=(',', ':')), file=sys.__stdout__, flush=True)
        assert admitted is not None, 'Second table registration revoked the first canonical RAW binding'
        assert admitted == expected
        lookup.assert_called_once_with(TARGET)
    assert subject.modal_raw(second, TARGET) == expected
    assert (first, second) == before


def _registered():
    subject = _fresh_helper()
    table, _ = _legacy_tables()
    subject.bind_modal(table, TARGET)
    assert subject.modal_raw(table, TARGET) == _official_raw()
    return subject, table


def _assert_bypasses_raw(subject, table, name):
    before = deepcopy(table)
    with patch.object(subject, 'raw_card', wraps=subject.raw_card) as lookup:
        assert subject.modal_raw(table, name) is None
        lookup.assert_not_called()
    assert table == before


def test_forward_table_registration_preserves_first_full_raw_admission():
    _order_profile(False)


def test_reverse_table_registration_preserves_first_full_raw_admission():
    _order_profile(True)


def test_unregistered_deepcopy_bypasses_raw():
    subject, table = _registered()
    _assert_bypasses_raw(subject, deepcopy(table), TARGET)


def test_replaced_row_bypasses_raw():
    subject, table = _registered()
    table[TARGET] = deepcopy(table[TARGET])
    _assert_bypasses_raw(subject, table, TARGET)


def test_nested_mutation_bypasses_raw():
    subject, table = _registered()
    table[TARGET]['card_faces'][0]['oracle_text'] += ' '
    _assert_bypasses_raw(subject, table, TARGET)


def test_foreign_name_bypasses_raw():
    subject, table = _registered()
    foreign = 'Valki, God of Lies // Tibalt, Cosmic Impostor'
    assert foreign in table and foreign != TARGET
    _assert_bypasses_raw(subject, table, foreign)
