"""Finite Phase1 public repository inverse; no application imports or runtime."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy

import pytest

from tests import interface_scope_compatibility as api


NAME = 'persistence/repository.py'
BACKEND = Path(__file__).parents[1]
OLD = 'a177b4fd46bc67ea43cabd83759093745fe319f6012c276adf625cb4abfc1eee'
CURRENT = '44126ef9c93abe862727048a9d675d48ba5e7d4ec444e8a664732bdf215ad7d3'
COMMITS = ['cd271b9edac81018e68a64cafd35ec9ca1b71530',
           '357680de093b0048b96f1f8596defae0f19f5b9d']


def test_public_authority_and_both_original_repository_operands_are_exact():
    declared = json.loads(api.REPOSITORY_DELTA_PATH.read_bytes())
    assert declared['accepted_public_commits'] == COMMITS
    assert declared['source'] == NAME
    assert declared['intermediate_sha256'] == '184c1039a5cea1377524bd24bd9d3dafbd46bab214280554a1483ed5ad2c1376'
    recipe = api.ACCEPTED_REPOSITORY_DELTA
    assert recipe == declared['accepted_repository_delta']
    assert (recipe['old_sha256'], recipe['new_sha256']) == (OLD, CURRENT)
    current = (BACKEND / NAME).read_bytes()
    assert hashlib.sha256(current).hexdigest() == CURRENT
    reviewed = api.restore_reviewed_source(NAME, current, OLD)
    assert hashlib.sha256(reviewed).hexdigest() == OLD
    historical = api.CONTRACT['production'][NAME]
    assert historical['new_sha256'] == OLD
    restored = api._restore(reviewed.decode(), historical).encode()
    assert hashlib.sha256(restored).hexdigest() == historical['old_sha256']
    for raw in (current, reviewed, restored):
        assert api.compatible_product_hash(NAME, raw, historical['old_sha256']) == hashlib.sha256(raw).hexdigest()
    assert api.restore_reviewed_source(NAME, reviewed, OLD) == reviewed


def test_every_new_repository_hunk_mutation_is_rejected_by_both_entry_points():
    recipe = api.ACCEPTED_REPOSITORY_DELTA
    original = (BACKEND / NAME).read_text().splitlines(keepends=True)
    assert recipe['hunks']
    for hunk in recipe['hunks']:
        lines = original.copy()
        lines[hunk['start']] += '# unauthorized approved-hunk edit\n'
        changed = ''.join(lines).encode()
        with pytest.raises(AssertionError):
            api.restore_reviewed_source(NAME, changed, OLD)
        with pytest.raises(AssertionError):
            api.compatible_product_hash(NAME, changed, api.CONTRACT['production'][NAME]['old_sha256'])


@pytest.mark.parametrize('prefix,suffix', [(b'# unauthorized\n', b''), (b'', b'\n# unauthorized\n')])
def test_outside_source_edits_are_not_admitted(prefix, suffix):
    current = prefix + (BACKEND / NAME).read_bytes() + suffix
    with pytest.raises(AssertionError):
        api.restore_reviewed_source(NAME, current, OLD)
    with pytest.raises(AssertionError):
        api.compatible_product_hash(NAME, current, api.CONTRACT['production'][NAME]['old_sha256'])


@pytest.mark.parametrize('operand', ['null_name', 'unknown_name', 'null_source', 'null_history', 'wrong_history'])
def test_unadmitted_operands_fail_closed(operand):
    name, current, historical = NAME, (BACKEND / NAME).read_bytes(), OLD
    if operand == 'null_name':
        name = None
    elif operand == 'unknown_name':
        name = 'foreign.py'
    elif operand == 'null_source':
        current = None
    elif operand == 'null_history':
        historical = None
    else:
        historical = api.CONTRACT['production'][NAME]['old_sha256']
    with pytest.raises((AssertionError, AttributeError, TypeError)):
        api.restore_reviewed_source(name, current, historical)


@pytest.mark.parametrize('mutation', ['old_sha', 'old_body', 'new_body', 'start', 'end', 'null_hunks'])
def test_bad_recipe_cannot_restore_current_source(mutation):
    recipe = deepcopy(api.ACCEPTED_REPOSITORY_DELTA)
    if mutation == 'old_sha':
        recipe['old_sha256'] = '0' * 64
    elif mutation == 'old_body':
        recipe['hunks'][0]['old'] += '# unauthorized historical body\n'
    elif mutation == 'new_body':
        recipe['hunks'][0]['new'] += '# unauthorized current body\n'
    elif mutation in {'start', 'end'}:
        recipe['hunks'][0][mutation] += 1
    else:
        recipe['hunks'] = None
    with pytest.raises((AssertionError, TypeError)):
        api._restore((BACKEND / NAME).read_text(), recipe)


def test_changed_recipe_bytes_are_rejected_before_use(monkeypatch):
    path = api.REPOSITORY_DELTA_PATH
    original = Path.read_bytes
    monkeypatch.setattr(Path, 'read_bytes', lambda self: original(self) + b' ' if self == path else original(self))
    with pytest.raises(AssertionError):
        runpy.run_path(api.__file__)


def test_original_contract_json_and_costs_are_not_replaced():
    pins = {
        api.PATH: 'bc0cde4e6e52f6ce2b76c64f68688c3a649271e415b24bd581ce431a4e7c08f3',
        api.DELTA_PATH: '5ec2d971a754c734fd4a378368398461664be3b48138150092e74dce9fb8bc40',
        BACKEND / 'tests/fixtures/private_cold_http_interface/reviewed_25ef_pins.json':
            'd9b3fb5971fec581558fa45d0279a100675a06e81e9758566dc870856beeb4a9',
        BACKEND / 'rules_engine/costs.py': '9294bde1dc08d5cf78df988ae7efeea53ab20d0e65152c94b855a428fb0cca6c',
    }
    for path, sha in pins.items():
        raw = path.read_bytes()
        if path == BACKEND / 'rules_engine/costs.py':
            raw = api.restore_reviewed_source('rules_engine/costs.py', raw, sha)
        assert hashlib.sha256(raw).hexdigest() == sha
    assert api.CONTRACT == json.loads(api.PATH.read_bytes())
