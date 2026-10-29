"""Finite historical-source reconciliation rejects edits INSIDE and outside seams."""
import importlib
import importlib.util
from pathlib import Path

import pytest


def support():
    name = 'tests.interface_scope_compatibility'
    assert importlib.util.find_spec(name) is not None, 'Finite compatibility API not installed'
    return importlib.import_module(name)


@pytest.mark.parametrize('name', ['main.py', 'persistence/repository.py'])
def test_real_public_production_delta_reconciles_history_but_mutations_do_not(name):
    api = support()
    raw = (Path(__file__).parents[1] / name).read_bytes()
    recipe = api.CONTRACT['production'][name]
    assert api.compatible_product_hash(name, raw, recipe['old_sha256']) == (
        api.LAND_CHOICE_MAIN_DELTA['new_sha256'] if name == 'main.py' else api.ACCEPTED_REPOSITORY_DELTA['new_sha256'])
    with pytest.raises(AssertionError):
        api.compatible_product_hash(name, raw + b'\n# unauthorized\n', recipe['old_sha256'])
    mutation_recipe = api.ACCEPTED_REPOSITORY_DELTA if name == 'persistence/repository.py' else recipe
    hunk = next(h for h in mutation_recipe['hunks'] if h['new'])
    changed = raw.replace(hunk['new'].encode(), hunk['new'].replace('import ', 'import  ', 1).encode(), 1)
    if changed == raw:
        changed = raw.replace(hunk['new'].encode(), (hunk['new'] + '# unauthorized\n').encode(), 1)
    assert changed != raw
    with pytest.raises(AssertionError):
        api.compatible_product_hash(name, changed, recipe['old_sha256'])


def test_keyword_approved_dispatch_and_unrelated_helper_mutations_still_reject():
    api = support()
    raw = (Path(__file__).parents[1] / 'rules_engine/keyword_actions.py').read_text()
    api.restore_keyword_edges(raw)
    for changed in (raw.replace('return finish_choice(state, player_id, action)', 'return False', 1),
                    raw.replace('def ninjutsu_cost(', 'def changed_cost(', 1)):
        assert changed != raw
        with pytest.raises(AssertionError):
            api.restore_keyword_edges(changed)


def test_only_exact_existing_github_branch_has_a_historical_worker_undo():
    api = support()
    raw = Path(__file__).with_name('import_identity_fix_worker.py').read_text()
    restored = api.restore_worker_platform('import_identity_fix_worker.py', raw)
    assert "assert str(root).startswith('/home/nick/') or str(root).startswith('/tmp/')" in restored
    with pytest.raises(AssertionError):
        api.restore_worker_platform('import_identity_fix_worker.py',
                                    raw.replace('assert_github_owned_source()', 'pass', 1))
