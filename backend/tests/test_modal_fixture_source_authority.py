"""Finite in-memory source mutations must fail before a real fixture is built."""
import ast
import hashlib
from pathlib import Path

import pytest

from tests import modal_contract_support as support


SUBJECT = Path(__file__).with_name('browser_fixture_server.py')
BASELINE = Path(__file__).parent / 'fixtures/modal_fixture_source_authority/baseline-browser-fixture.py.txt'
APPROVED = 'f2dc14a6efe794b7c0b1fef22ba030ef85866debff920961a2138baef13b66a1'


def fixture_node(text):
    return next(node for node in ast.parse(text).body
                if isinstance(node, ast.FunctionDef) and node.name == 'fixture')


@pytest.mark.parametrize('face_kind', ['copy_target', 'counter_payment_1'])
@pytest.mark.parametrize('mutation', [
    'stale_baseline', 'changed_approved_hunk', 'unrelated_inside_body', 'untouched_branch',
])
def test_actual_canonical_fixture_rejects_unauthorized_source_before_birth(monkeypatch, face_kind, mutation):
    original = SUBJECT.read_text()
    node = fixture_node(original)
    assert hashlib.sha256(ast.get_source_segment(original, node).encode()).hexdigest() == APPROVED
    if mutation == 'stale_baseline':
        data = BASELINE.read_bytes()
        assert hashlib.sha256(data).hexdigest() == '25f3e9c1d42ddf2ee4164ca98f71bce36af2eaf216f70ee8f7fa75f1fa38b714'
        changed = data.decode()
    elif mutation == 'changed_approved_hunk':
        marker = '        deck = [entry("Island", 60)]'
        assert marker in original
        changed = original.replace(marker, '        deck = [entry("Island", 59)]', 1)
    elif mutation == 'unrelated_inside_body':
        lines = original.splitlines(keepends=True)
        lines.insert(node.body[0].lineno - 1, '    unauthorized_fixture_marker = 1\n')
        changed = ''.join(lines)
    else:
        marker = '        state = MatchFactory.from_decks(deck, deck, seed=913)'
        assert original.count(marker) == 1
        changed = original.replace(marker, marker.replace('913', '914'))
    changed_node = fixture_node(changed)
    assert hashlib.sha256(ast.get_source_segment(changed, changed_node).encode()).hexdigest() != APPROVED
    calls = []

    def forbidden_birth(*args, **kwargs):
        calls.append('constructor')
        raise AssertionError('Constructor must not be reached')

    def forbidden_consumer(*args, **kwargs):
        calls.append('consumer')
        raise AssertionError('Consumer must not be reached')

    read_text = Path.read_text

    def substitute(path, *args, **kwargs):
        if path == SUBJECT:
            return changed
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', substitute)
    monkeypatch.setattr(support.MatchFactory, 'from_decks', staticmethod(forbidden_birth))
    monkeypatch.setattr(support, 'RulesEngine', forbidden_consumer)
    with pytest.raises(AssertionError):
        support.canonical_fixture(face_kind)
    assert calls == []
