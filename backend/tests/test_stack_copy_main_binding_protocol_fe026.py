"""Module-cache protocol controls, not application imports or card fixtures."""
import importlib
import importlib.util
import sys
import types

import pytest

from tests import test_stack_copy_printed_b720_fidelity as fidelity


SITES = (
    'test_original_first_consumer_receives_complete_printed_card',
    'test_full_raw_roles_and_remaining_uncaptured_boundaries_are_explicit',
    'test_ordinary_canonical_birth_preserves_controlled_physical_resources_and_rng',
    'test_full_canonical_arsonist_preserves_the_original_trigger_copy_sequence',
)


def invoke(site, patch):
    body = getattr(fidelity, site)
    if site == SITES[0]:
        body(patch, *fidelity.SUBJECTS[0])
    else:
        body()


def absent_with_restoration(patch):
    # Register both transitions so even a subsequently imported entry is undone.
    patch.setitem(sys.modules, 'main', types.ModuleType('main'))
    patch.delitem(sys.modules, 'main')


class MainProtocolLoader:
    """Execute a real Python import without executing the application main.py."""
    module = None

    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'main':
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        self.module = types.ModuleType(spec.name)
        return self.module

    def exec_module(self, module):
        assert module is self.module


def mutate_inside_real_body(patch, site, mutate):
    if site in (SITES[0], SITES[2]):
        target, name = fidelity.original, '_state'
    elif site == SITES[1]:
        target, name = fidelity, 'raw_card'
    else:
        target, name = fidelity.original, 'test_triggered_ability_copy_uses_trigger_clause_for_legal_targets'
    delegate = getattr(target, name)
    calls = []

    def forwarded(*args, **kwargs):
        result = delegate(*args, **kwargs)
        if not calls:
            mutate()
        calls.append(True)
        return result

    patch.setattr(target, name, forwarded)
    return calls


@pytest.mark.parametrize('site', SITES)
@pytest.mark.parametrize('binding_kind', ('module', 'sentinel'))
def test_protocol_preexisting_main_binding_is_legitimate_and_unchanged(monkeypatch, site, binding_kind):
    binding = types.ModuleType('main') if binding_kind == 'module' else object()
    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, 'main', binding)
        invoke(site, patch)
        assert sys.modules['main'] is binding


@pytest.mark.parametrize('site', SITES)
def test_protocol_initial_absence_remains_required(monkeypatch, site):
    with monkeypatch.context() as patch:
        absent_with_restoration(patch)
        invoke(site, patch)
        assert 'main' not in sys.modules


@pytest.mark.parametrize('site', SITES)
@pytest.mark.parametrize('mutation', ('new_import', 'replacement', 'removal'))
def test_protocol_body_import_replacement_or_removal_is_rejected(monkeypatch, site, mutation):
    with monkeypatch.context() as patch:
        if mutation == 'new_import':
            absent_with_restoration(patch)
            loader = MainProtocolLoader()
            patch.setattr(sys, 'meta_path', [loader, *sys.meta_path])

            def mutate():
                loaded = importlib.import_module('main')
                assert loaded is loader.module
        else:
            binding = types.ModuleType('main')
            patch.setitem(sys.modules, 'main', binding)

            def mutate():
                if mutation == 'replacement':
                    patch.setitem(sys.modules, 'main', types.ModuleType('main'))
                else:
                    patch.delitem(sys.modules, 'main')

        forwarded = mutate_inside_real_body(patch, site, mutate)
        with pytest.raises(AssertionError, match='main'):
            invoke(site, patch)
        assert forwarded
