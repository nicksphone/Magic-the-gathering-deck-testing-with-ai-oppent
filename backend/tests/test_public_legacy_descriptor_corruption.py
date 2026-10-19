"""Public native-capture controls; the protected six-case test never executes."""
import ast
from copy import deepcopy
from pathlib import Path

import pytest

from effects import handlers
from game_state.serializers import serialize_match_snapshot
from rules_engine.events import capture_last_known_battlefield
from tests import test_natural_heat_target_audit as audit
from tests.test_public_legacy_lki_protocol import (
    canonical, check_parity, parity_case, pre_capture, public_position,
)


def install_descriptor_protocol(monkeypatch):
    """Compile only the actual descriptor installation and observation assertion."""
    path = Path(audit.__file__)
    tree = ast.parse(path.read_bytes())
    test = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == 'test_private_legacy_adapter_rejects_independent_protocol_corruption')
    selector = ast.parse("corruption == 'descriptor'", mode='eval').body
    branches = [node for node in ast.walk(test) if isinstance(node, ast.If)
                and ast.dump(node.test) == ast.dump(selector)]
    branch = next(node for node in branches if not isinstance(node.body[0], ast.Assert))
    observation = next((node for node in branches if isinstance(node.body[0], ast.Assert)), None)
    assert not any(isinstance(node, ast.Name) and node.id in
                   {'exact_state', 'receipts', 'witness'}
                   for statement in branch.body for node in ast.walk(statement))
    wrapper = ast.parse('def install(monkeypatch):\n    pass\n').body[0]
    check = ast.parse('def assert_observed():\n    pass\n').body[0]
    check.body = deepcopy(observation.body) if observation is not None else [ast.Pass()]
    wrapper.body = [*deepcopy(branch.body), check,
                    ast.Return(value=ast.Name(id='assert_observed', ctx=ast.Load()))]
    module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
    namespace = {'__name__': audit.__name__, 'serialize_match_snapshot': serialize_match_snapshot,
                 'deepcopy': deepcopy}
    exec(compile(module, str(path), 'exec'), namespace)
    return namespace['install'](monkeypatch)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('record_kind', ['missing', 'valid'])
def test_old_descriptor_hook_mutates_only_after_native_descriptor_returns(monkeypatch, seat, record_kind):
    state, card, context = public_position(seat, 'Grizzly Bears', record_kind)
    expected = pre_capture(state, card, context)['__copiable_lki']
    original = handlers.token_copy_descriptor
    mutations = []
    calls = []

    def old_hook(target):
        calls.append(target.id)
        # Exact old expression: ActionRejected precedes both mutation and counter.
        result = {**original(target), 'mana_cost': 'incorrect'}
        mutations.append(target.id)
        return result

    monkeypatch.setattr(handlers, 'token_copy_descriptor', old_hook)
    capture_last_known_battlefield(state, card.id)
    captured = card.last_known_battlefield['__copiable_lki']
    assert calls == [card.id]
    assert mutations == ([card.id] if record_kind == 'valid' else [])
    if record_kind == 'missing':
        assert captured == expected
        assert captured['descriptor'] is None
        assert captured['unavailable'] == 'missing_copiable_characteristics'
    else:
        assert captured['descriptor'] == {**expected['descriptor'], 'mana_cost': 'incorrect'}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('record_kind', ['missing', 'null', 'empty', 'valid'])
def test_actual_descriptor_branch_corrupts_serialized_LKI_not_native_state(monkeypatch, seat, record_kind):
    assert_observed = install_descriptor_protocol(monkeypatch)
    state, card, context, clean, historical = parity_case(seat, record_kind)
    expected_lki = context['departed_lki'][card.id]['__copiable_lki']
    assert card.last_known_battlefield['__copiable_lki'] == expected_lki
    check_parity(clean, historical, context)
    before = canonical(serialize_match_snapshot(state))
    pre_before = canonical(context)
    bad = audit.serialize_match_snapshot(state)
    expected = deepcopy(clean)
    descriptor = expected['cards'][card.id]['last_known_battlefield']['__copiable_lki']['descriptor']
    expected['cards'][card.id]['last_known_battlefield']['__copiable_lki']['descriptor'] = {
        **(descriptor or {}), 'mana_cost': 'incorrect',
    }
    assert bad == expected
    assert_observed()
    assert canonical(serialize_match_snapshot(state)) == before
    assert canonical(context) == pre_before
    with pytest.raises(AssertionError):
        check_parity(bad, historical, context)
    assert canonical(serialize_match_snapshot(state)) == before
    assert canonical(context) == pre_before


def test_unrelated_assertion_cannot_satisfy_descriptor_negative(monkeypatch):
    assert_observed = install_descriptor_protocol(monkeypatch)
    with pytest.raises(AssertionError):
        raise AssertionError('Independent public baseline failure, not descriptor corruption')
    with pytest.raises(AssertionError):
        assert_observed()


@pytest.mark.parametrize('seat', [1, 2])
def test_serialization_without_captured_LKI_cannot_count_as_a_mutation(monkeypatch, seat):
    assert_observed = install_descriptor_protocol(monkeypatch)
    state, _card, _context = public_position(seat, 'Grizzly Bears', 'valid')
    expected = serialize_match_snapshot(state)
    assert audit.serialize_match_snapshot(state) == expected
    assert serialize_match_snapshot(state) == expected
    with pytest.raises(AssertionError):
        assert_observed()
