"""Actual module admission and native pytest evaluation; no archive body reads."""
import ast
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from _pytest.outcomes import Failed
from _pytest.skipping import evaluate_skip_marks


TARGET = Path(__file__).with_name('test_ai_opaque_top_choose_horizon.py')
ARCHIVED_CASE = 'test_saved_turn16_live_agent_restored_roots_and_opportunity_count'


def archive_path():
    tree = ast.parse(TARGET.read_text())
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'NATURAL' for t in n.targets))
    return Path(ast.literal_eval(assignment.value.args[0]))


def load_with_probe(probe):
    archive = archive_path()
    original = Path.exists
    calls = []

    def exists(path):
        if path == archive:
            calls.append(path)
            return probe()
        return original(path)

    with patch.object(Path, 'exists', exists):
        namespace = runpy.run_path(str(TARGET))
    return namespace, calls


def test_public_module_collects_without_touching_unreadable_optional_archive():
    def forbidden():
        raise PermissionError('Synthetic unreadable optional archive')

    namespace, calls = load_with_probe(forbidden)
    assert callable(namespace['test_live_horizon_retains_only_count_value_and_root_immutability'])
    assert callable(namespace[ARCHIVED_CASE])
    assert calls == []


@pytest.mark.parametrize('availability', ['absent', 'available', 'unreadable'])
def test_archived_cases_retain_original_skip_admit_and_permission_failure(availability):
    # Load using an absent synthetic metadata result, never the real archive.
    namespace, _ = load_with_probe(lambda: False)
    function = namespace[ARCHIVED_CASE]

    class Archive:
        def exists(self):
            if availability == 'unreadable':
                raise PermissionError('Synthetic unreadable optional archive')
            return availability == 'available'

    function.__globals__['NATURAL'] = Archive()
    item = SimpleNamespace(
        obj=function,
        config=None,
        ihook=SimpleNamespace(pytest_markeval_namespace=lambda **kwargs: []),
        iter_markers=lambda name: (mark for mark in function.pytestmark if mark.name == name),
    )
    if availability == 'unreadable':
        with pytest.raises(Failed, match='PermissionError: Synthetic unreadable optional archive'):
            evaluate_skip_marks(item)
    else:
        result = evaluate_skip_marks(item)
        if availability == 'absent':
            assert result is not None and result.reason == 'Optional archived natural decision fixture'
        else:
            assert result is None
