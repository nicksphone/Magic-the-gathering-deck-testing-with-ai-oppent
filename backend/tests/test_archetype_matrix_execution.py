"""Bounded adapter tests, never a pilot/matrix measurement or strength claim."""
from collections import Counter
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path

import pytest

from scripts.archetype_matrix_plan import build_plan, digest


def adapter():
    name = 'scripts.archetype_matrix_execution'
    assert importlib.util.find_spec(name) is not None, 'Matrix execution adapter is missing'
    return importlib.import_module(name)


@pytest.fixture
def matrix():
    return build_plan('a' * 40,
        (Path(__file__).parents[1] / 'decks/builtin_decks.py').read_text())


def test_pilot_has_36_fresh_seat_balanced_cycle_cells_without_mutating_matrix(matrix):
    original = deepcopy(matrix)
    pilot = adapter().build_pilot(matrix, 'archetype-pilot-20261116-v2-unit')
    assert matrix == original
    assert pilot['kind'] == 'pilot' and pilot['matrix_sha256'] == digest(matrix)
    assert pilot['run_id'] != matrix['run_id']
    assert pilot['seeds'] == [2026111901, 2026111902]
    assert len(pilot['cells']) == len({c['cell_id'] for c in pilot['cells']}) == 36
    assert not ({c['cell_id'] for c in pilot['cells']} & {c['cell_id'] for c in matrix['cells']})
    assert not (set(pilot['seeds']) & set(matrix['seeds']))
    assert Counter((c['seed'], c['deck_a_seat']) for c in pilot['cells']) == {
        (2026111901, 1): 9, (2026111901, 2): 9,
        (2026111902, 1): 9, (2026111902, 2): 9}
    names = sorted(matrix['decks'])
    expected = {tuple(sorted((names[i], names[(i+1) % 9]))) for i in range(9)}
    assert {(c['deck_a'], c['deck_b']) for c in pilot['cells']} == expected
    assert pilot['policy'] == matrix['policy']
    assert adapter().validate_pilot(pilot) is None


@pytest.mark.parametrize('field', ['seed', 'cell', 'policy', 'revision', 'decks', 'matrix_digest', 'kind'])
def test_pilot_edits_are_refused_before_execution(matrix, field):
    module = adapter()
    pilot = module.build_pilot(matrix, 'archetype-pilot-20261116-v2-unit')
    if field == 'seed': pilot['seeds'][0] = 2026111501
    elif field == 'cell': pilot['cells'].pop()
    elif field == 'policy': pilot['policy']['max_seconds'] = 1000
    elif field == 'revision': pilot['revision'] = 'b' * 40
    elif field == 'decks': pilot['matrix']['decks']['Burn'] = matrix['source_decks']['Burn']
    elif field == 'matrix_digest': pilot['matrix_sha256'] = 'b' * 64
    else: pilot['kind'] = 'matrix'
    with pytest.raises(ValueError): module.validate_pilot(pilot)


def test_old_run_ids_and_non_pilot_identity_refuse(matrix):
    for name in (matrix['run_id'], '110', 'pilot', '', None):
        with pytest.raises(ValueError): adapter().build_pilot(matrix, name)


def test_changed_builtin_or_budget_refuses_instead_of_scheduling(matrix):
    matrix['policy']['max_cpu_seconds_per_game'] = 900
    with pytest.raises(ValueError): adapter().build_pilot(matrix, 'archetype-pilot-20261116-v2-unit')


def test_same_cell_adapter_accepts_frozen_matrix_and_separate_pilot(matrix):
    module = adapter()
    assert callable(getattr(module, 'execution_matrix', None)), 'Frozen cell-plan admission is missing'
    assert module.execution_matrix(matrix) == matrix
    pilot = module.build_pilot(matrix, 'archetype-pilot-20261116-v2-unit')
    assert module.execution_matrix(pilot) == matrix
    broken = deepcopy(matrix); broken['policy']['max_ticks'] += 1
    with pytest.raises(ValueError): module.execution_matrix(broken)
