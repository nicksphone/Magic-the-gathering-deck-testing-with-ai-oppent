"""Actual public-source inverses; no backend, HTTP or execution permission."""
from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from tests import interface_scope_compatibility as api


BACKEND = Path(__file__).parents[1]


def test_actual_current_main_requires_both_exact_historical_inverses():
    current = (BACKEND / 'main.py').read_bytes()
    recipe = api.CONTRACT['production']['main.py']
    assert api.LAND_CHOICE_MAIN_DELTA['old_sha256'] == api.CURRENT_MAIN_DELTA['new_sha256']
    predecessor = api._restore(current.decode(), api.LAND_CHOICE_MAIN_DELTA)
    assert hashlib.sha256(predecessor.encode()).hexdigest() == api.CURRENT_MAIN_DELTA['new_sha256']
    accepted = api._restore(predecessor, api.CURRENT_MAIN_DELTA)
    assert hashlib.sha256(accepted.encode()).hexdigest() == api.ACCEPTED_MAIN_DELTA['new_sha256']
    intermediate = api.restore_reviewed_source('main.py', current, recipe['new_sha256'])
    assert api._restore(accepted, api.ACCEPTED_MAIN_DELTA).encode() == intermediate
    assert hashlib.sha256(intermediate).hexdigest() == recipe['new_sha256']
    historical = api._restore(intermediate.decode(), recipe)
    assert hashlib.sha256(historical.encode()).hexdigest() == recipe['old_sha256']
    assert api.compatible_product_hash('main.py', current, recipe['old_sha256']) == hashlib.sha256(current).hexdigest()
    assert hashlib.sha256(current).hexdigest() == api.LAND_CHOICE_MAIN_DELTA['new_sha256']


def test_actual_private_fixture_restores_only_reviewed_delver_identity_clause():
    name = 'tests/private_choice_boundary_fixture_server.py'
    recipe = api.ACCEPTED_DELTAS['accepted_private_fixture_delta']
    restored = api.restore_reviewed_source(name, (BACKEND / name).read_bytes(), recipe['old_sha256'])
    assert hashlib.sha256(restored).hexdigest() == recipe['old_sha256']
    assert b"    state.id = str(uuid4())\n" in restored
    assert b"    if family == 'officer':\n" not in restored


def test_mutation_inside_private_fixture_identity_hunk_is_rejected():
    name = 'tests/private_choice_boundary_fixture_server.py'
    raw = (BACKEND / name).read_bytes()
    changed = raw.replace(b"if family == 'officer':", b"if family == 'delver':", 1)
    assert changed != raw
    with pytest.raises(AssertionError):
        api.restore_reviewed_source(name, changed,
                                    api.ACCEPTED_DELTAS['accepted_private_fixture_delta']['old_sha256'])


@pytest.mark.parametrize('index', range(12))
def test_every_current_main_hunk_mutation_is_rejected(index):
    recipe = api.ACCEPTED_MAIN_DELTA
    lines = (BACKEND / 'main.py').read_text().splitlines(keepends=True)
    start = recipe['hunks'][index]['start']
    lines[start] += '# unauthorized current hunk\n'
    with pytest.raises(AssertionError):
        api.compatible_product_hash('main.py', ''.join(lines).encode(),
                                    api.CONTRACT['production']['main.py']['old_sha256'])


@pytest.mark.parametrize('name,key', [
    ('main.py', 'accepted_main_delta'),
    ('tests/private_choice_boundary_fixture_server.py', 'accepted_private_fixture_delta'),
])
def test_outside_current_hunks_is_not_authorized_by_whole_file_repins(name, key):
    raw = (BACKEND / name).read_bytes() + b'\n# unauthorized outside\n'
    with pytest.raises(AssertionError):
        api.restore_reviewed_source(name, raw, api.ACCEPTED_DELTAS[key]['old_sha256'])


@pytest.mark.parametrize('mutation', ['intermediate_sha', 'intermediate_body'])
def test_intermediate_sha_and_body_cannot_be_substituted(mutation):
    recipe = deepcopy(api.ACCEPTED_MAIN_DELTA)
    if mutation == 'intermediate_sha':
        recipe['old_sha256'] = '0' * 64
    else:
        recipe['hunks'][0]['old'] += '# unauthorized intermediate\n'
    with pytest.raises(AssertionError):
        api._restore((BACKEND / 'main.py').read_text(), recipe)


def test_unknown_source_and_wrong_historical_operand_are_rejected():
    raw = (BACKEND / 'main.py').read_bytes()
    with pytest.raises(AssertionError):
        api.restore_reviewed_source('foreign.py', raw, api.ACCEPTED_MAIN_DELTA['old_sha256'])
    with pytest.raises(AssertionError):
        api.restore_reviewed_source('main.py', raw, '0' * 64)


def test_original_recipe_and_repository_operands_remain_immutable():
    assert hashlib.sha256(api.PATH.read_bytes()).hexdigest() == 'bc0cde4e6e52f6ce2b76c64f68688c3a649271e415b24bd581ce431a4e7c08f3'
    recipe = api.CONTRACT['production']['persistence/repository.py']
    raw = (BACKEND / 'persistence/repository.py').read_bytes()
    assert api.compatible_product_hash('persistence/repository.py', raw, recipe['old_sha256']) == api.ACCEPTED_REPOSITORY_DELTA['new_sha256']
