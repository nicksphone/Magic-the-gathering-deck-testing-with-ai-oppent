"""Finite source-byte goldens; no application, HTTP, SQL, or Git execution."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import runpy

import pytest

from tests import interface_scope_compatibility as api
from tests import test_rules_printed_facts_e4_fidelity as original


TESTS = Path(__file__).parent
PATH = TESTS / 'fixtures/interface_scope_compatibility/accepted_76_source_inverses.json'
DATA = json.loads(PATH.read_bytes())
EXPECTED_PATH = TESTS / 'fixtures/rules_printed_facts_e4/UNCHANGED_FUNCTION_SHA256.json'
EXPECTED = json.loads(EXPECTED_PATH.read_bytes())
IDENTITIES = tuple(DATA['functions'])
UNTOUCHED = tuple(sorted(set(EXPECTED) - set(IDENTITIES)))
PREFIX = '    events = [{"card_id": cid, "controller": player_id} for cid in ids]\n'
SUFFIX = '    emit_event_batch(state, "sacrifice", events)\n'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def function(text, name):
    nodes = [node for node in ast.parse(text).body
             if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(nodes) == 1
    return ast.get_source_segment(text, nodes[0])


def normalize(module, text):
    normalizer = getattr(api, 'restore_printed_protocol_source', None)
    assert callable(normalizer), 'Finite source normalizer must be installed'
    return normalizer(module, text)


def edges(text):
    before, remaining = text.split(PREFIX)
    middle, after = remaining.split(SUFFIX)
    return before, middle, after


def keyword():
    return (TESTS.parent / 'rules_engine/keyword_actions.py').read_text()


def test_existing_fidelity_guard_reconstructs_all_sixty_original_operands():
    original.test_pristine_old_protocol_functions_remain_source_exact()
    assert len(EXPECTED) == 60 and len(IDENTITIES) == 14 and len(UNTOUCHED) == 46
    assert hashlib.sha256(EXPECTED_PATH.read_bytes()).hexdigest() == (
        '94a314f7a95f8a1f538f06c181c274324b2afef2d97414f8d1c8ce29dd7e3559')


@pytest.mark.parametrize('identity', IDENTITIES)
def test_each_approved_function_reconstructs_its_original_digest(identity):
    module, name = identity.split(':')
    source = (TESTS / module).read_text()
    restored = normalize(module, source)
    assert digest(function(restored, name)) == EXPECTED[identity]
    assert digest(function(source, name)) == DATA['functions'][identity]['new_sha256']


@pytest.mark.parametrize('identity', IDENTITIES)
def test_each_historical_function_remains_an_accepted_exact_input(identity):
    module, name = identity.split(':')
    source = (TESTS / module).read_text()
    segment = function(source, name)
    historical = api._restore(segment, DATA['functions'][identity])
    input_source = source.replace(segment, historical, 1)
    restored = normalize(module, input_source)
    assert function(restored, name) == historical
    assert digest(historical) == EXPECTED[identity]


@pytest.mark.parametrize('identity', IDENTITIES)
def test_every_approved_hunk_still_rejects_changed_bytes(identity):
    module, name = identity.split(':')
    source = (TESTS / module).read_text()
    segment = function(source, name)
    for hunk in DATA['functions'][identity]['hunks']:
        if not hunk['new']:
            continue
        inside = re.sub(r'(?m)^([ \t]*)([A-Za-z_]\w*)', r'\1\2 ', hunk['new'], count=1)
        assert inside != hunk['new']
        changed = segment.replace(hunk['new'], inside, 1)
        assert changed != segment
        with pytest.raises(AssertionError):
            normalize(module, source.replace(segment, changed, 1))


@pytest.mark.parametrize('identity', IDENTITIES)
def test_each_function_rejects_changes_outside_approved_hunks(identity):
    module, name = identity.split(':')
    source = (TESTS / module).read_text()
    segment = function(source, name)
    changed = segment + '\n    assert True  # unauthorized outside inverse\n'
    with pytest.raises(AssertionError):
        normalize(module, source.replace(segment, changed, 1))


@pytest.mark.parametrize('identity', UNTOUCHED)
def test_all_forty_six_untouched_functions_keep_original_mutation_rejection(monkeypatch, identity):
    module, name = identity.split(':')
    path = TESTS / module
    source = path.read_text()
    current_segment = function(source, name)
    segment = function(normalize(module, source), name)
    assert digest(segment) == EXPECTED[identity]
    changed = source.replace(current_segment, current_segment + '\n    assert True  # unauthorized\n', 1)
    assert changed != source
    read_text = Path.read_text
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'read_text', lambda self, *a, **k:
                      changed if self == path else read_text(self, *a, **k))
        with pytest.raises(AssertionError):
            original.test_pristine_old_protocol_functions_remain_source_exact()


@pytest.mark.parametrize('change', ['missing', 'duplicate'])
def test_missing_or_duplicate_protected_function_is_not_normalized(change):
    module, name = IDENTITIES[0].split(':')
    source = (TESTS / module).read_text()
    segment = function(source, name)
    changed = source.replace(segment, '', 1) if change == 'missing' else source + '\n' + segment + '\n'
    with pytest.raises(AssertionError):
        normalize(module, changed)


def test_unknown_module_is_not_a_new_normalization_admission():
    with pytest.raises(AssertionError):
        normalize('foreign.py', 'def unreviewed():\n    pass\n')


def test_changed_new_recipe_bytes_are_rejected_before_use(monkeypatch):
    read_bytes = Path.read_bytes
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'read_bytes', lambda self:
                      read_bytes(self) + b' ' if self == PATH else read_bytes(self))
        with pytest.raises(AssertionError):
            runpy.run_path(api.__file__)


@pytest.mark.parametrize('mutation', ['old_sha', 'old_body', 'new_body', 'start', 'end', 'hunks'])
def test_corrupt_function_recipe_cannot_reconstruct_expected_history(mutation):
    identity = IDENTITIES[0]
    module, name = identity.split(':')
    source = function((TESTS / module).read_text(), name)
    recipe = deepcopy(DATA['functions'][identity])
    if mutation == 'old_sha':
        recipe['old_sha256'] = '0' * 64
    elif mutation in {'old_body', 'new_body'}:
        recipe['hunks'][0]['old' if mutation == 'old_body' else 'new'] += '# corrupt\n'
    elif mutation in {'start', 'end'}:
        recipe['hunks'][0][mutation] += 1
    else:
        recipe['hunks'] = None
    with pytest.raises((AssertionError, TypeError)):
        api._restore(source, recipe)


def test_keyword_current_dispatch_restores_the_original_prefix_and_suffix():
    restored = api.restore_keyword_edges(keyword())
    before, middle, after = edges(restored)
    assert digest(before) == api.CONTRACT['keyword_prefix']['old_sha256']
    assert digest(after) == api.CONTRACT['keyword_suffix']['old_sha256']
    assert middle == edges(keyword())[1]


@pytest.mark.parametrize('level', ['current', '2fd', 'historical'])
def test_keyword_previously_approved_inputs_stay_supported(level):
    raw = keyword()
    before, middle, after = edges(raw)
    if level != 'current':
        before = api._restore(before, DATA['keyword']['prefix'])
    if level == 'historical':
        before = api._restore(before, api.CONTRACT['keyword_prefix'])
    restored = api.restore_keyword_edges(before + PREFIX + middle + SUFFIX + after)
    assert digest(edges(restored)[0]) == api.CONTRACT['keyword_prefix']['old_sha256']
    assert edges(restored)[1] == middle


@pytest.mark.parametrize('index', range(6))
def test_each_new_keyword_hunk_rejects_a_changed_line(index):
    raw = keyword()
    hunk = DATA['keyword']['prefix']['hunks'][index]
    changed = raw.replace(hunk['new'], hunk['new'] + '# unauthorized dispatch\n', 1)
    assert changed != raw
    with pytest.raises(AssertionError):
        api.restore_keyword_edges(changed)


def test_keyword_unrelated_function_is_not_admitted_by_current_inverse():
    raw = keyword()
    changed = raw.replace('def ninjutsu_cost(', 'def unknown_cost(', 1)
    assert changed != raw
    with pytest.raises(AssertionError):
        api.restore_keyword_edges(changed)


def test_keyword_sacrifice_middle_is_returned_unmodified_not_replaced_from_git():
    before, middle, after = edges(keyword())
    middle += '    # protected sacrifice-slice sentinel, not an approved production edit\n'
    result = api.restore_keyword_edges(before + PREFIX + middle + SUFFIX + after)
    assert edges(result)[1] == middle


def test_only_exact_approved_public_commits_are_declared():
    assert DATA['function_delta_predecessor'] == '091e7e4eed2b0be6dd1b7f9fe38068dc42833a79'
    assert DATA['keyword']['approved_commits'] == [
        'a2fbcc99ca4b093224e93c5c2fde98db7e8804e3',
        '0efab0bf86cc41e9b2e7aa511db465c351255e92']
    for identity, recipe in DATA['functions'].items():
        assert recipe['old_sha256'] == EXPECTED[identity]
        assert [row['commit'] for row in recipe['approved_git_lineage']] == [
            '0efab0bf86cc41e9b2e7aa511db465c351255e92']
