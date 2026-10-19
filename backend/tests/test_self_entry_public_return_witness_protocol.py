"""Canonical witness serialization protocols, not knowledge-admission controls."""
import ast
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.observations import observe_cards
from tests import test_self_entry_fixed_damage_desired as desired


class EmptyDictSubclass(dict):
    pass


def observation_state(snapshot):
    state, _, public_card, _ = desired.original.setup(1, 'sniper', suppress_entry=False)
    observe_cards(state, [public_card])
    for viewer in (1, 2):
        state.card_observations[viewer][public_card]['knowledge_snapshot'] = deepcopy(snapshot)
    return state, public_card


def capture_actual_witness(state, bounced):
    tree = ast.parse(Path(desired.__file__).read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'test_actual_canonical_self_entry_and_independent_controls')
    witness = next(node.value for node in ast.walk(function) if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'witness'
                           for target in node.targets))
    expression = next(value for key, value in zip(witness.keys, witness.values)
                      if isinstance(key, ast.Constant) and key.value == 'observed_records')
    return eval(compile(ast.Expression(expression), 'actual-public-witness', 'eval'),
                {'state': state, 'bounced': bounced, 'deepcopy': deepcopy,
                 'original': desired.original})


def canonical_records(state, card_id):
    records = desired.original.serialize_match_snapshot(state)['card_observations']
    return {viewer: deepcopy(records[str(viewer)][card_id]) for viewer in (1, 2)}


def test_native_empty_dictionary_uses_complete_canonical_record():
    state, card_id = observation_state({})
    captured = capture_actual_witness(state, card_id)
    assert captured == canonical_records(state, card_id)
    assert all('knowledge_snapshot' not in record for record in captured.values())
    assert all(state.card_observations[viewer][card_id]['knowledge_snapshot'] == {}
               for viewer in (1, 2))


@pytest.mark.parametrize('snapshot', [
    pytest.param(None, id='none'),
    pytest.param(False, id='false'),
    pytest.param(0, id='zero'),
    pytest.param('', id='empty-string'),
    pytest.param([], id='empty-list'),
    pytest.param(EmptyDictSubclass(), id='dict-subclass'),
])
def test_other_empty_types_are_not_omitted(snapshot):
    state, card_id = observation_state(snapshot)
    captured = capture_actual_witness(state, card_id)
    assert captured == canonical_records(state, card_id)
    for record in captured.values():
        assert 'knowledge_snapshot' in record
        assert record['knowledge_snapshot'] == snapshot
        assert type(record['knowledge_snapshot']) is type(snapshot)


def test_nonempty_snapshot_is_retained_without_field_projection():
    # Opaque serializer metadata is not an eligible knowledge profile or game Oracle.
    snapshot = {'ready_for_match': False, 'protocol_only': {'nested': [False, None, 'retain']}}
    state, card_id = observation_state(snapshot)
    captured = capture_actual_witness(state, card_id)
    assert captured == canonical_records(state, card_id)
    assert all(record['knowledge_snapshot'] == snapshot for record in captured.values())
    captured[1]['knowledge_snapshot']['protocol_only']['nested'].append('copy-only')
    assert captured[2]['knowledge_snapshot'] == snapshot
    assert all(state.card_observations[viewer][card_id]['knowledge_snapshot'] == snapshot
               for viewer in (1, 2))


def test_capture_has_integer_viewers_and_never_mutates_root():
    state, card_id = observation_state({})
    before = desired.original.serialize_match_snapshot(state)
    original_observations = deepcopy(state.card_observations)
    captured = capture_actual_witness(state, card_id)
    assert set(captured) == {1, 2} and all(type(viewer) is int for viewer in captured)
    captured[1]['name'] = 'copy-only protocol label'
    assert desired.original.serialize_match_snapshot(state) == before
    assert state.card_observations == original_observations
    assert captured[2] == canonical_records(state, card_id)[2]
